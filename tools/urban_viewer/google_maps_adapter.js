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

/** フォールバック Map ID (開発/テスト専用。本番は GOOGLE_MAPS_MAP_ID を使う) */
const FALLBACK_MAP_ID = "DEMO_MAP_ID";

/** カテゴリ -> 色マッピング (POI Data layer スタイル用) */
const CATEGORY_COLORS = {
    "amenity-cafe":        "#a0522d",
    "amenity-restaurant":  "#e67e22",
    "amenity-fast_food":   "#e74c3c",
    "amenity-bar":         "#8e44ad",
    "shop-convenience":    "#27ae60",
    "shop-clothing":       "#2980b9",
    "shop-supermarket":    "#16a085",
    "leisure-park":        "#2ecc71",
    "amenity-school":      "#f1c40f",
    "office-building":     "#3498db",
    "home-residential":    "#95a5a6",
    "other-misc":          "#7f8c8d",
};

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
                // 位置のみ更新 (§5.1.4)
                const marker = this._agentMarkers.get(agent.id);
                marker.position = latLng;
            } else {
                // 新規作成
                const role  = agent.role || "other";
                const color = ROLE_COLORS[role] || DEFAULT_ROLE_COLOR;
                const pin   = new PinElement({
                    glyph:           String(agent.id),
                    background:      color,
                    borderColor:     "#ffffff",
                    glyphColor:      "#ffffff",
                });
                const marker = new AdvancedMarkerElement({
                    map:      this._map,
                    position: latLng,
                    content:  pin.element,
                    title:    `Agent ${agent.id}`,
                });
                marker.addListener("click", () => {
                    if (this._agentClickCb) this._agentClickCb(agent.id);
                });
                this._agentMarkers.set(agent.id, marker);
            }
        }

        // 今 tick に存在しない agent マーカーを非表示にする
        for (const [id, marker] of this._agentMarkers) {
            if (!seenIds.has(id)) marker.map = null;
        }

        // markerclusterer 拡張ポイント: クラスタを再描画
        if (this._markerClusterer) {
            this._markerClusterer.clearMarkers();
            this._markerClusterer.addMarkers([...this._agentMarkers.values()]);
        }
    }

    /**
     * 指定 agentId を強調表示する (null で解除)。
     * @param {number|null} agentId
     */
    highlight(agentId) {
        this._selectedAgentId = agentId;
        // TODO (Milestone 6): PinElement の背景色を差し替えて強調
        // MVP では詳細パネル側の強調表示で代替する
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

    /** google.maps が利用可能になるまで待機する (bootstrap loader がコールバックを呼ぶまで) */
    async _waitForGoogleMaps() {
        return new Promise((resolve) => {
            const check = () => {
                if (typeof google !== "undefined" && google.maps) {
                    resolve();
                } else {
                    requestAnimationFrame(check);
                }
            };
            check();
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
