/**
 * google_maps_adapter.js — Google Maps JavaScript API アダプタ。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.1.2 / §5.1.3
 * インターフェース: map_adapter.js (init / setLayer / upsertAgents / highlight / onAgentClick)
 *
 * - Maps JavaScript API を importLibrary() で動的ロードする (§5.1.3)
 * - POI/AOI/Road は google.maps.Data layer で管理する (§5.1.2)
 * - Agent は AdvancedMarkerElement + PinElement で管理する (Map ID 必須)
 * - marker manager は後から @googlemaps/markerclusterer を差し込める構造にする
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

import { CATEGORY_COLORS } from "./colors.js";

/** フォールバック Map ID (開発/テスト専用。本番は GOOGLE_MAPS_MAP_ID を使う) */
const FALLBACK_MAP_ID = "DEMO_MAP_ID";

/** role -> ピン背景色 (AdvancedMarkerElement) */
const ROLE_COLORS = {
    "office_worker": "#3498db",
    "student":       "#f1c40f",
    "other":         "#2c3e50",
};

const DEFAULT_ROLE_COLOR = "#2c3e50";
const HIGHLIGHT_COLOR    = "#e74c3c";

/** 友達リンク線の色 (半透明の暖色) */
const SOCIAL_LINK_COLOR  = "#e6781e";
/** 友達リンク線の太さ (px) */
const SOCIAL_LINK_WEIGHT = 2;

/** デフォルト地図中心 (渋谷周辺) */
const DEFAULT_CENTER = { lat: 35.6628, lng: 139.7025 };
const DEFAULT_ZOOM   = 14;

export class GoogleMapsAdapter {
    /**
     * @param {HTMLElement} container - 地図を描画する DOM 要素
     * @param {string} apiKey - Google Maps JavaScript API キー
     * @param {string} [mapId] - AdvancedMarkerElement 用 Map ID
     */
    constructor(container, apiKey, mapId) {
        this._container = container;
        this._apiKey    = apiKey;
        this._mapId     = mapId || FALLBACK_MAP_ID;

        this._map   = null;
        this._ready = false;

        // レイヤー: Data インスタンスを name -> Data のマップで管理
        this._dataLayers = { poi: null, aoi: null, road: null };

        // agent: id -> AdvancedMarkerElement のマップ
        this._agentMarkers = new Map();

        // agent: id -> PinElement のマップ (highlight で背景色を差し替えるために保持)
        this._agentPins = new Map();

        // agent: id -> role 別色 のマップ (highlight 解除時に正しい色に戻すために保持)
        this._agentRoleColors = new Map();

        // 選択中 agent
        this._selectedAgentId = null;

        // agentClick コールバック
        this._agentClickCb = null;

        // MakerClusterer 拡張ポイント (後付け用 / §5.1.2 acceptance)
        this._markerClusterer = null;

        // 友達リンク線 (google.maps.Polyline) のリスト
        this._socialLinkPolylines = [];
    }

    // ─────────────────────────────────────────────────────────────────────────
    // adapter 公開インターフェース
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Maps API をロードして地図を初期化する。
     * @param {Object} [options]
     * @param {{ lat: number, lng: number }} [options.center]
     * @param {number} [options.zoom]
     * @returns {Promise<void>}
     */
    async init(options = {}) {
        // bootstrap loader が google.maps を用意するまで待機
        await this._waitForGoogleMaps();

        const { Map } = await google.maps.importLibrary("maps");
        const center = options.center || DEFAULT_CENTER;
        const zoom   = options.zoom   || DEFAULT_ZOOM;

        this._map = new Map(this._container, {
            center,
            zoom,
            mapId: this._mapId,
        });

        // Data レイヤーを3枚作成
        for (const name of ["poi", "aoi", "road"]) {
            const data = new google.maps.Data({ map: this._map });
            this._dataLayers[name] = data;
        }

        this._applyDataLayerStyles();
        this._ready = true;
    }

    /**
     * GeoJSON レイヤーのデータをセットし、表示/非表示を切り替える。
     * @param {"poi"|"aoi"|"road"|"agent"} name
     * @param {boolean} visible
     * @param {Object|null} [geojson] - GeoJSON FeatureCollection
     */
    setLayer(name, visible, geojson = null) {
        if (name === "agent") {
            for (const marker of this._agentMarkers.values()) {
                marker.map = visible ? this._map : null;
            }
            return;
        }

        const layer = this._dataLayers[name];
        if (!layer) return;

        if (geojson !== null) {
            // 既存 feature を削除してから追加
            layer.forEach(f => layer.remove(f));
            layer.addGeoJson(geojson);
        }
        layer.setMap(visible ? this._map : null);
    }

    /**
     * エージェントマーカーを一括更新する。
     * 既存 AdvancedMarkerElement の .position を再代入する (§5.1.4 生成/破棄しない)。
     * @param {import('./fallback_map_adapter.js').AgentMarkerData[]} agents
     */
    async upsertAgents(agents) {
        if (!this._ready) return;

        const { AdvancedMarkerElement, PinElement } =
            await google.maps.importLibrary("marker");

        const seenIds = new Set();
        for (const agent of agents) {
            seenIds.add(agent.id);
            const latLng = new google.maps.LatLng(agent.lat, agent.lon);

            if (this._agentMarkers.has(agent.id)) {
                // 位置・glyph・title を更新し、前 tick で非表示にしたマーカーを再表示する (§5.1.4 / WO-007)
                // WO-007 acceptance: tick 毎・run 跨ぎで glyph / title を更新する。
                const marker = this._agentMarkers.get(agent.id);
                marker.position = latLng;
                marker.map = this._map;
                // glyph / title を最新の label で更新する (profile ロード後の run 跨ぎ対応)
                const pin = this._agentPins.get(agent.id);
                if (pin) {
                    const glyphText = agent.label != null ? String(agent.label) : String(agent.id);
                    pin.glyph = glyphText;
                }
                const titleText = agent.label != null
                    ? `${agent.label} (id:${agent.id})`
                    : `Agent ${agent.id}`;
                marker.title = titleText;
            } else {
                // 新規作成
                const role  = agent.role || "other";
                // 選択中なら強調色、それ以外はロール別色
                const color = (agent.id === this._selectedAgentId)
                    ? HIGHLIGHT_COLOR
                    : (ROLE_COLORS[role] || DEFAULT_ROLE_COLOR);
                // glyph: label フィールドがあれば名前の短縮形を表示、なければ id
                const glyphText = agent.label != null ? String(agent.label) : String(agent.id);
                const pin   = new PinElement({
                    glyph:           glyphText,
                    background:      color,
                    borderColor:     "#ffffff",
                    glyphColor:      "#ffffff",
                });
                // title: ツールチップに短縮ラベルを表示
                const titleText = agent.label != null
                    ? `${agent.label} (id:${agent.id})`
                    : `Agent ${agent.id}`;
                const marker = new AdvancedMarkerElement({
                    map:      this._map,
                    position: latLng,
                    content:  pin.element,
                    title:    titleText,
                });
                marker.addListener("click", () => {
                    if (this._agentClickCb) this._agentClickCb(agent.id);
                });
                this._agentMarkers.set(agent.id, marker);
                this._agentPins.set(agent.id, pin);
                // role 別色を保存。highlight 解除時に正しい色に戻すために参照する
                this._agentRoleColors.set(agent.id, ROLE_COLORS[role] || DEFAULT_ROLE_COLOR);
            }
        }

        // 今 tick に存在しない agent マーカーを非表示にする。
        // marker / pin の参照は保持し、再出現時は上の既存マーカーパスで
        // marker.map を復元する (delete すると再表示・highlight が壊れる)。
        for (const [id, marker] of this._agentMarkers) {
            if (!seenIds.has(id)) {
                marker.map = null;
            }
        }

        // markerclusterer 拡張ポイント: クラスタを再描画
        if (this._markerClusterer) {
            this._markerClusterer.clearMarkers();
            this._markerClusterer.addMarkers([...this._agentMarkers.values()]);
        }
    }

    /**
     * 指定 agentId を強調表示する (null で解除)。
     * PinElement の background を差し替えて視覚的に強調する。
     * 前回選択だったマーカーをロール別のデフォルト色に戻してから新規選択を強調する。
     * @param {number|null} agentId
     */
    highlight(agentId) {
        const prevId = this._selectedAgentId;
        this._selectedAgentId = agentId;

        // 前回選択マーカーを role 別色に戻す
        if (prevId !== null && prevId !== undefined && prevId !== agentId) {
            const prevPin = this._agentPins.get(prevId);
            if (prevPin) {
                // _agentRoleColors に upsertAgents 時の role 別色が保存されているため、
                // DEFAULT_ROLE_COLOR 固定ではなく正しい role 色 (office_worker=青 / student=黄 など) に戻す
                prevPin.background = this._agentRoleColors.get(prevId) || DEFAULT_ROLE_COLOR;
            }
        }

        // 新規選択マーカーを強調色にする
        if (agentId !== null && agentId !== undefined) {
            const pin = this._agentPins.get(agentId);
            if (pin) {
                pin.background = HIGHLIGHT_COLOR;
            }
        }
    }

    /**
     * agent クリック時のコールバックを登録する。
     * @param {(agentId: number) => void} cb
     */
    onAgentClick(cb) {
        this._agentClickCb = cb;
    }

    /**
     * 選択中 agent から友達への社会的リンク線を描画する。
     * 既存の線はクリアしてから新しく引く。
     * @param {{ id:number, lat:number, lon:number }} centerAgent
     * @param {Array<{ id:number, lat:number, lon:number }>} friendAgents
     */
    drawSocialLinks(centerAgent, friendAgents) {
        this.clearSocialLinks();
        if (!centerAgent || !friendAgents || friendAgents.length === 0) return;

        const centerLatLng = new google.maps.LatLng(centerAgent.lat, centerAgent.lon);

        for (const friend of friendAgents) {
            const friendLatLng = new google.maps.LatLng(friend.lat, friend.lon);
            const polyline = new google.maps.Polyline({
                path:          [centerLatLng, friendLatLng],
                strokeColor:   SOCIAL_LINK_COLOR,
                strokeOpacity: 0.6,
                strokeWeight:  SOCIAL_LINK_WEIGHT,
                icons: [{
                    icon:   { path: google.maps.SymbolPath.FORWARD_OPEN_ARROW, scale: 2 },
                    offset: "50%",
                }],
                map: this._map,
            });
            this._socialLinkPolylines.push(polyline);
        }
    }

    /**
     * drawSocialLinks で描画した社会的リンク線をすべて消去する。
     */
    clearSocialLinks() {
        for (const poly of this._socialLinkPolylines) {
            poly.setMap(null);
        }
        this._socialLinkPolylines = [];
    }

    /**
     * MarkerClusterer を後付けで設定する拡張ポイント。
     * playback の upsertAgents を書き換えずに使える (acceptance §5.1.2)。
     * @param {Object} clusterer - @googlemaps/markerclusterer の MarkerClusterer インスタンス
     */
    setMarkerClusterer(clusterer) {
        this._markerClusterer = clusterer;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 内部
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * google.maps が利用可能になるまで待機する (bootstrap loader がコールバックを呼ぶまで)。
     * timeout_ms 以内にロードされない場合は reject する (無限待ち防止)。
     * @param {number} [timeoutMs=10000] - タイムアウト時間 (ミリ秒)
     * @returns {Promise<void>}
     */
    _waitForGoogleMaps(timeoutMs = 10000) {
        return new Promise((resolve, reject) => {
            // 既にロード済みなら即 resolve
            if (typeof google !== "undefined" && google.maps) {
                resolve();
                return;
            }

            let rafHandle = null;

            const timeoutId = setTimeout(() => {
                if (rafHandle !== null) cancelAnimationFrame(rafHandle);
                reject(new Error(
                    `Google Maps SDK が ${timeoutMs}ms 以内にロードされませんでした。` +
                    " APIキーと bootstrap loader の設定を確認してください。"
                ));
            }, timeoutMs);

            const check = () => {
                if (typeof google !== "undefined" && google.maps) {
                    clearTimeout(timeoutId);
                    resolve();
                } else {
                    rafHandle = requestAnimationFrame(check);
                }
            };

            rafHandle = requestAnimationFrame(check);
        });
    }

    /** Data レイヤーごとにスタイル関数を設定する */
    _applyDataLayerStyles() {
        // POI: Point -> category で色分け
        this._dataLayers.poi.setStyle((feature) => {
            const category = feature.getProperty("category") || "";
            const color = CATEGORY_COLORS[category] || "#888888";
            return {
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 5,
                    fillColor: color,
                    fillOpacity: 0.9,
                    strokeColor: "#ffffff",
                    strokeWeight: 1,
                },
            };
        });

        // AOI: Polygon -> 半透明
        this._dataLayers.aoi.setStyle({
            fillColor:   "#66bb6a",
            fillOpacity: 0.2,
            strokeColor: "#43a047",
            strokeWeight: 1.5,
        });

        // Road: LineString -> 淡い細線 (表示専用の飾りと分かる程度に薄く)
        this._dataLayers.road.setStyle({
            strokeColor:   "#b0a898",
            strokeWeight:  1.0,
            strokeOpacity: 0.35,
        });
    }
}
