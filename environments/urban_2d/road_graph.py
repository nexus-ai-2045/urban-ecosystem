"""
road_graph.py — roadnet.geojson からルーティンググラフを構築し最短経路を提供する。

正本:
  - docs/subagents/contracts/urban-ecosystem-data-contract.md §Road Feature
  - wo-urban-009-road-following-movement.yaml §acceptance

設計方針:
  - NetworkX は使わない (依存追加ゼロ)。純粋 Python の隣接リスト + Dijkstra で実装する。
  - ノードは Road の端点座標 (lon, lat) を丸め 6 桁でキーにし、重複ノードをマージする。
  - POI / initial_position は「最近傍道路ノードへスナップ」してからルーティングする。
  - グラフが非連結の場合: スナップ先ノードから到達不能なら直線フォールバック。
  - 決定論: グラフ構築はシード不要 (座標 id ソート)。ルーティング Dijkstra は
    タイブレークを (累積コスト, node_id 文字列) で固定し同一入力で同一経路を返す。

公開 API:
  - RoadGraph(roads: list[Road]) → グラフオブジェクト
  - RoadGraph.route(src_lat, src_lon, dst_lat, dst_lon) → list[(lat, lon)]
      src → dst の最短経路ノード列 (src/dst 座標スナップ込み)。
      到達不能 → [(dst_lat, dst_lon)] (直線フォールバック: 1 要素リスト)。
  - RoadGraph.snap_node(lat, lon) → (lat, lon)
      最近傍道路ノードの座標を返す。
  - build_road_graph(roads) → RoadGraph の便利関数
"""

from __future__ import annotations

import heapq
import math
from typing import Any

from .models import Road
from .rules import haversine_m

# ── 座標キー精度 (度) ──────────────────────────────────────────────────────────
# 6 桁 ≈ 0.1 m 精度。道路端点のマージ精度としてこれで十分。
_COORD_PRECISION = 6


def _coord_key(lon: float, lat: float) -> str:
    """(lon, lat) をグラフノード ID 文字列に変換する。"""
    return f"{round(lon, _COORD_PRECISION)},{round(lat, _COORD_PRECISION)}"


def _key_to_latlon(key: str) -> tuple[float, float]:
    """ノード ID 文字列から (lat, lon) を返す。"""
    lon_s, lat_s = key.split(",")
    return float(lat_s), float(lon_s)


# ─────────────────────────────────────────────────────────────────────────────
# RoadGraph
# ─────────────────────────────────────────────────────────────────────────────

class RoadGraph:
    """roadnet から構築した無向重み付きグラフ。

    ノード: road 端点の (lon, lat) 座標を丸め 6 桁でキー化した文字列。
    エッジ: road セグメントの両端ノード間 (Haversine 距離を重みとする無向エッジ)。
    MultiLineString は sub-segment ごとに辺を追加する。

    利用例::
        graph = RoadGraph(roads)
        waypoints = graph.route(src_lat, src_lon, dst_lat, dst_lon)
        # waypoints は (lat, lon) タプルのリスト (src スナップ点を含む)
    """

    def __init__(self, roads: list[Road]) -> None:
        """グラフを構築する。roads が空の場合もエラーにはならない (空グラフ)。"""
        # _adj: node_id → list[(neighbor_id, weight_m)]
        self._adj: dict[str, list[tuple[str, float]]] = {}
        # _node_latlon: node_id → (lat, lon) キャッシュ
        self._node_latlon: dict[str, tuple[float, float]] = {}

        for road in roads:
            if not road.walkable:
                continue
            segs = self._segments_from_road(road)
            for (lon_a, lat_a), (lon_b, lat_b) in segs:
                id_a = _coord_key(lon_a, lat_a)
                id_b = _coord_key(lon_b, lat_b)
                if id_a == id_b:
                    continue  # 長さゼロのセグメントを無視する
                w = haversine_m(lat_a, lon_a, lat_b, lon_b)
                self._ensure_node(id_a, lat_a, lon_a)
                self._ensure_node(id_b, lat_b, lon_b)
                self._adj[id_a].append((id_b, w))
                self._adj[id_b].append((id_a, w))

    # ── 内部ユーティリティ ──────────────────────────────────────────────────────

    def _ensure_node(self, node_id: str, lat: float, lon: float) -> None:
        """ノードが未登録なら初期化する。"""
        if node_id not in self._adj:
            self._adj[node_id] = []
            self._node_latlon[node_id] = (lat, lon)

    @staticmethod
    def _segments_from_road(road: Road) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """Road オブジェクトからセグメントのリストを返す。

        LineString: [[lon, lat], ...] → 連続するペアが 1 セグメント。
        MultiLineString: [[[lon, lat], ...], ...] → 各 sub-line で連続ペア。
        """
        coords = road.coordinates
        if road.geometry_type == "LineString":
            return [
                ((coords[i][0], coords[i][1]), (coords[i + 1][0], coords[i + 1][1]))
                for i in range(len(coords) - 1)
                if len(coords) >= 2
            ]
        if road.geometry_type == "MultiLineString":
            segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
            for line in coords:
                for i in range(len(line) - 1):
                    if len(line) >= 2:
                        segs.append(
                            ((line[i][0], line[i][1]), (line[i + 1][0], line[i + 1][1]))
                        )
            return segs
        return []

    # ── 公開 API ────────────────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """グラフにノードが 1 件もないか (walkable road ゼロ)。"""
        return len(self._adj) == 0

    def snap_node(self, lat: float, lon: float) -> tuple[float, float]:
        """(lat, lon) に最近傍の道路ノード座標を返す。

        グラフが空の場合は入力座標をそのまま返す。
        同距離のノードは node_id (文字列) 昇順で安定的に決める (決定論)。
        """
        if not self._node_latlon:
            return (lat, lon)
        best_id: str = ""
        best_d = math.inf
        for nid, (nlat, nlon) in self._node_latlon.items():
            d = haversine_m(lat, lon, nlat, nlon)
            if d < best_d or (d == best_d and (best_id == "" or nid < best_id)):
                best_d = d
                best_id = nid
        return self._node_latlon[best_id]

    def route(
        self,
        src_lat: float,
        src_lon: float,
        dst_lat: float,
        dst_lon: float,
    ) -> list[tuple[float, float]]:
        """src → dst の最短経路ノード列 (lat, lon) を返す。

        - src / dst は最近傍ノードにスナップしてから探索する。
        - 到達不能またはグラフが空の場合は [(dst_lat, dst_lon)] を返す (直線フォールバック)。
        - 同一コストのパスは node_id 昇順で安定化する (決定論タイブレーク)。

        戻り値の先頭は src スナップ点、末尾は dst スナップ点。
        dst スナップ点から実際の dst 座標へのスナップは呼び出し元が行う。
        """
        if self.is_empty():
            return [(dst_lat, dst_lon)]

        src_nid = _coord_key(*self._latlon_to_key(src_lat, src_lon))
        dst_nid = _coord_key(*self._latlon_to_key(dst_lat, dst_lon))

        if src_nid == dst_nid:
            # 同一ノード → 目的地への 1 ステップ
            return [self._node_latlon[dst_nid]]

        path = self._dijkstra(src_nid, dst_nid)
        if path is None:
            # 到達不能 → 直線フォールバック
            return [(dst_lat, dst_lon)]
        return [self._node_latlon[n] for n in path]

    def _latlon_to_key(self, lat: float, lon: float) -> tuple[float, float]:
        """(lat, lon) を最近傍ノードの (lon, lat) に変換する (snap 済み)。"""
        snapped_lat, snapped_lon = self.snap_node(lat, lon)
        return snapped_lon, snapped_lat

    def _dijkstra(self, src: str, dst: str) -> list[str] | None:
        """src → dst の最短経路ノード id リストを返す。到達不能なら None。

        タイブレーク: (累積コスト, node_id) の辞書順で安定化する (決定論)。
        """
        # heap: (cost, tiebreak_id, node_id)
        heap: list[tuple[float, str, str]] = [(0.0, src, src)]
        dist: dict[str, float] = {src: 0.0}
        prev: dict[str, str] = {}

        while heap:
            cost, _, cur = heapq.heappop(heap)
            if cur == dst:
                return self._reconstruct(prev, src, dst)
            if cost > dist.get(cur, math.inf):
                continue
            for nb, w in self._adj.get(cur, []):
                new_cost = cost + w
                if new_cost < dist.get(nb, math.inf):
                    dist[nb] = new_cost
                    prev[nb] = cur
                    heapq.heappush(heap, (new_cost, nb, nb))
        return None

    @staticmethod
    def _reconstruct(prev: dict[str, str], src: str, dst: str) -> list[str]:
        """prev dict から src → dst のパスを再構成する。"""
        path: list[str] = []
        cur = dst
        while cur != src:
            path.append(cur)
            cur = prev[cur]
        path.append(src)
        path.reverse()
        return path


# ─────────────────────────────────────────────────────────────────────────────
# 公開ファクトリ
# ─────────────────────────────────────────────────────────────────────────────

def build_road_graph(roads: list[Road]) -> RoadGraph:
    """Road リストから RoadGraph を構築して返す (便利関数)。"""
    return RoadGraph(roads)
