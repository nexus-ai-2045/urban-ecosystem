/**
 * fallback_map_adapter.js — APIキー無し fallback 地図アダプタ。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.1.5
 * インターフェース: map_adapter.js (init / setLayer / upsertAgents / highlight / onAgentClick)
 *
 * 投影: 全データの lat/lon から bounds を計算し、線形変換で canvas 座標へ写す。
 *   x = (lon - lonMin) / (lonMax - lonMin) * width
 *   y = (latMax - lat) / (latMax - latMin) * height  (lat 上が小さい y)
 * Web Mercator は採用しない。CI/テスト主経路として境界内収束のみを保証する。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

/**
 * @typedef {Object} LatLon
 * @property {number} lat
 * @property {number} lon
 */

/**
 * @typedef {Object} AgentMarkerData
 * @property {number} id
 * @property {number} lat
 * @property {number} lon
 * @property {string|null} [action]
 * @property {string|null} [status]
 */

/** canvas のパディング (px) — 最大 bounds を少し縮めて余白を作る */
const CANVAS_PADDING = 20;

/** エージェント円の半径 (px) */
const AGENT_RADIUS = 7;

/** POI 点の半径 (px) */
const POI_RADIUS = 3;

/** カテゴリ -> 色マッピング */
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

/** エージェント選択時の強調色 */
const HIGHLIGHT_COLOR = "#ff0000";
/** エージェントのデフォルト色 */
const AGENT_DEFAULT_COLOR = "#2c3e50";

/** 友達リンク線の色 (半透明の暖色) */
const SOCIAL_LINK_COLOR = "rgba(230, 120, 30, 0.6)";
/** 友達リンク線の太さ (px) */
const SOCIAL_LINK_WIDTH = 2;
/** 友達マーカー強調リングの色 */
const FRIEND_RING_COLOR = "rgba(230, 120, 30, 0.9)";

export class FallbackMapAdapter {
    /**
     * @param {HTMLCanvasElement} canvas
     */
    constructor(canvas) {
        this._canvas = canvas;
        this._ctx = canvas.getContext("2d");

        // bounds: 全 GeoJSON / agent データから動的計算
        this._bounds = null;  // { latMin, latMax, lonMin, lonMax }

        // レイヤーデータ保持
        this._layers = {
            poi:   { geojson: null, visible: true },
            aoi:   { geojson: null, visible: true },
            road:  { geojson: null, visible: false },  // 既定非表示 (app.js と統一 / 意味の薄い飾り)
            agent: { markers: [],   visible: true },
        };

        // 選択中 agentId
        this._selectedAgentId = null;

        // クリックコールバック (agentId: number) => void
        this._agentClickCb = null;

        // クリックイベントを canvas に登録
        this._canvas.addEventListener("click", this._handleClick.bind(this));

        // リサイズ対応
        this._resizeObserver = new ResizeObserver(() => this._redraw());
        this._resizeObserver.observe(this._canvas.parentElement || document.body);

        // 友達リンクデータ (drawSocialLinks で上書き / clearSocialLinks でリセット)
        this._socialLinks = null;  // { center: {id,lat,lon}, friends: [{id,lat,lon}] } | null
    }

    // ─────────────────────────────────────────────────────────────────────────
    // adapter 公開インターフェース (map_adapter.js 準拠)
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * アダプタ初期化。canvas サイズを親要素に合わせ、背景を描画する。
     * @param {Object} [_options] - 現時点では未使用 (Google Maps adapter との互換)
     */
    init(_options = {}) {
        this._fitCanvas();
        this._drawBackground();
    }

    /**
     * GeoJSON レイヤーのデータをセットし、表示/非表示を切り替える。
     * @param {"poi"|"aoi"|"road"} name
     * @param {boolean} visible
     * @param {Object|null} [geojson] - GeoJSON FeatureCollection (初回のみ渡す)
     */
    setLayer(name, visible, geojson = null) {
        if (!(name in this._layers)) return;
        if (geojson !== null) {
            this._layers[name].geojson = geojson;
            this._recomputeBounds();
        }
        this._layers[name].visible = visible;
        this._redraw();
    }

    /**
     * エージェントマーカーを一括更新する。
     * @param {AgentMarkerData[]} agents - 現 tick の全 agent 状態リスト
     */
    upsertAgents(agents) {
        this._layers.agent.markers = agents.slice();
        this._redraw();
    }

    /**
     * 指定 agentId を強調表示する (null で解除)。
     * @param {number|null} agentId
     */
    highlight(agentId) {
        this._selectedAgentId = agentId;
        this._redraw();
    }

    /**
     * agent クリック時のコールバックを登録する。
     * @param {(agentId: number) => void} cb
     */
    onAgentClick(cb) {
        this._agentClickCb = cb;
    }

    /**
     * agent レイヤーの表示/非表示を切り替える。
     * @param {boolean} visible
     */
    setAgentLayerVisible(visible) {
        this._layers.agent.visible = visible;
        this._redraw();
    }

    /**
     * 選択中 agent から友達への社会的リンク線を描画する。
     * @param {{ id:number, lat:number, lon:number }} centerAgent
     * @param {Array<{ id:number, lat:number, lon:number }>} friendAgents
     */
    drawSocialLinks(centerAgent, friendAgents) {
        this._socialLinks = { center: centerAgent, friends: friendAgents };
        this._redraw();
    }

    /**
     * 社会的リンク線をすべて消去する。
     */
    clearSocialLinks() {
        this._socialLinks = null;
        this._redraw();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 内部: 座標変換
    // ─────────────────────────────────────────────────────────────────────────

    /** bounds 全体 (GeoJSON + agent) を再計算する */
    _recomputeBounds() {
        let latMin = Infinity, latMax = -Infinity;
        let lonMin = Infinity, lonMax = -Infinity;

        const updateBounds = (lat, lon) => {
            if (lat < latMin) latMin = lat;
            if (lat > latMax) latMax = lat;
            if (lon < lonMin) lonMin = lon;
            if (lon > lonMax) lonMax = lon;
        };

        // GeoJSON FeatureCollection から座標を収集
        for (const layerKey of ["poi", "aoi", "road"]) {
            const geo = this._layers[layerKey].geojson;
            if (!geo) continue;
            this._collectGeoJsonCoords(geo, updateBounds);
        }

        // agent 初期位置
        for (const a of this._layers.agent.markers) {
            updateBounds(a.lat, a.lon);
        }

        if (latMin === Infinity) {
            // データなし: 渋谷周辺デフォルト
            this._bounds = { latMin: 35.655, latMax: 35.670, lonMin: 139.695, lonMax: 139.710 };
        } else {
            // 点データ保護: 少し余裕を持たせる
            const dlat = Math.max((latMax - latMin) * 0.05, 0.001);
            const dlon = Math.max((lonMax - lonMin) * 0.05, 0.001);
            this._bounds = {
                latMin: latMin - dlat,
                latMax: latMax + dlat,
                lonMin: lonMin - dlon,
                lonMax: lonMax + dlon,
            };
        }
    }

    /**
     * GeoJSON FeatureCollection を走査して座標コールバックを呼ぶ。
     * @param {Object} geo
     * @param {(lat:number, lon:number) => void} cb
     */
    _collectGeoJsonCoords(geo, cb) {
        if (!geo || !Array.isArray(geo.features)) return;
        for (const feature of geo.features) {
            if (!feature || !feature.geometry) continue;
            this._collectGeomCoords(feature.geometry, cb);
        }
    }

    /**
     * GeoJSON geometry から座標を再帰収集する。[lon, lat] 順。
     * @param {Object} geom
     * @param {(lat:number, lon:number) => void} cb
     */
    _collectGeomCoords(geom, cb) {
        if (!geom) return;
        const t = geom.type;
        if (t === "Point") {
            const [lon, lat] = geom.coordinates;
            cb(lat, lon);
        } else if (t === "LineString" || t === "MultiPoint") {
            for (const [lon, lat] of geom.coordinates) cb(lat, lon);
        } else if (t === "Polygon" || t === "MultiLineString") {
            for (const ring of geom.coordinates)
                for (const [lon, lat] of ring) cb(lat, lon);
        } else if (t === "MultiPolygon") {
            for (const poly of geom.coordinates)
                for (const ring of poly)
                    for (const [lon, lat] of ring) cb(lat, lon);
        }
    }

    /**
     * (lat, lon) -> canvas (x, y) 線形変換。
     * §5.1.5:
     *   x = (lon - lonMin) / (lonMax - lonMin) * width
     *   y = (latMax - lat) / (latMax - latMin) * height
     * @returns {{ x: number, y: number }}
     */
    _project(lat, lon) {
        const b = this._bounds;
        if (!b) return { x: 0, y: 0 };
        const w = this._canvas.width - CANVAS_PADDING * 2;
        const h = this._canvas.height - CANVAS_PADDING * 2;
        const dlon = b.lonMax - b.lonMin;
        const dlat = b.latMax - b.latMin;
        const x = CANVAS_PADDING + (dlon > 0 ? (lon - b.lonMin) / dlon * w : w / 2);
        const y = CANVAS_PADDING + (dlat > 0 ? (b.latMax - lat) / dlat * h : h / 2);
        return { x, y };
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 内部: 描画
    // ─────────────────────────────────────────────────────────────────────────

    /** canvas を親要素のサイズに合わせる */
    _fitCanvas() {
        const parent = this._canvas.parentElement;
        if (parent) {
            this._canvas.width  = parent.clientWidth  || 800;
            this._canvas.height = parent.clientHeight || 600;
        }
    }

    /** 全レイヤーを再描画する */
    _redraw() {
        const ctx = this._ctx;
        const w = this._canvas.width;
        const h = this._canvas.height;

        // 背景クリア
        ctx.clearRect(0, 0, w, h);
        this._drawBackground();

        if (!this._bounds) this._recomputeBounds();

        // AOI (半透明ポリゴン)
        if (this._layers.aoi.visible && this._layers.aoi.geojson) {
            this._drawAois(this._layers.aoi.geojson);
        }

        // Road (折れ線) — 意味の薄い飾りとして淡く描画
        if (this._layers.road.visible && this._layers.road.geojson) {
            this._drawRoads(this._layers.road.geojson);
        }

        // POI (点)
        if (this._layers.poi.visible && this._layers.poi.geojson) {
            this._drawPois(this._layers.poi.geojson);
        }

        // 友達リンク線 (agent より下のレイヤーに描画)
        if (this._socialLinks) {
            this._drawSocialLinkLines(this._socialLinks.center, this._socialLinks.friends);
        }

        // Agent (番号付き円)
        if (this._layers.agent.visible) {
            this._drawAgents(this._layers.agent.markers);
        }
    }

    /** グリッドライン付きの fallback 背景 */
    _drawBackground() {
        const ctx = this._ctx;
        const w = this._canvas.width;
        const h = this._canvas.height;

        ctx.fillStyle = "#f0f0e8";
        ctx.fillRect(0, 0, w, h);

        ctx.strokeStyle = "#d0d0c8";
        ctx.lineWidth = 0.5;
        const step = 40;
        for (let x = 0; x < w; x += step) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
        }
        for (let y = 0; y < h; y += step) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }

        // fallback ラベル
        ctx.fillStyle = "#aaaaaa";
        ctx.font = "12px sans-serif";
        ctx.fillText("Fallback Map (no API key)", 8, h - 6);
    }

    /** AOI を半透明ポリゴンで描画する */
    _drawAois(geojson) {
        const ctx = this._ctx;
        for (const feature of geojson.features || []) {
            if (!feature.geometry) continue;
            const t = feature.geometry.type;
            const polys = t === "Polygon"
                ? [feature.geometry.coordinates]
                : t === "MultiPolygon"
                    ? feature.geometry.coordinates
                    : [];
            for (const rings of polys) {
                ctx.beginPath();
                for (let ri = 0; ri < rings.length; ri++) {
                    const ring = rings[ri];
                    for (let i = 0; i < ring.length; i++) {
                        const [lon, lat] = ring[i];
                        const { x, y } = this._project(lat, lon);
                        if (i === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                    ctx.closePath();
                }
                ctx.fillStyle = "rgba(100, 180, 100, 0.18)";
                ctx.fill();
                ctx.strokeStyle = "rgba(60, 140, 60, 0.5)";
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }
    }

    /** Road を折れ線で描画する (意味の薄い飾りとして淡く表示) */
    _drawRoads(geojson) {
        const ctx = this._ctx;
        ctx.strokeStyle = "rgba(180, 170, 160, 0.35)";
        ctx.lineWidth = 0.7;
        for (const feature of geojson.features || []) {
            if (!feature.geometry) continue;
            const t = feature.geometry.type;
            const lines = t === "LineString"
                ? [feature.geometry.coordinates]
                : t === "MultiLineString"
                    ? feature.geometry.coordinates
                    : [];
            for (const coords of lines) {
                ctx.beginPath();
                for (let i = 0; i < coords.length; i++) {
                    const [lon, lat] = coords[i];
                    const { x, y } = this._project(lat, lon);
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.stroke();
            }
        }
    }

    /** POI をカテゴリ別色の点で描画する */
    _drawPois(geojson) {
        const ctx = this._ctx;
        for (const feature of geojson.features || []) {
            if (!feature.geometry || feature.geometry.type !== "Point") continue;
            const [lon, lat] = feature.geometry.coordinates;
            const { x, y } = this._project(lat, lon);
            const category = (feature.properties || {}).category || "";
            const color = CATEGORY_COLORS[category] || "#888888";
            ctx.beginPath();
            ctx.arc(x, y, POI_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        }
    }

    /** Agent を番号付き円で描画する */
    _drawAgents(agents) {
        const ctx = this._ctx;
        for (const agent of agents) {
            const { x, y } = this._project(agent.lat, agent.lon);
            const isSelected = agent.id === this._selectedAgentId;
            const color = isSelected ? HIGHLIGHT_COLOR : AGENT_DEFAULT_COLOR;

            // 外枠
            ctx.beginPath();
            ctx.arc(x, y, AGENT_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = isSelected ? "#ffeeee" : "#ffffff";
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = isSelected ? 2.5 : 1.5;
            ctx.stroke();

            // 番号テキスト
            ctx.fillStyle = color;
            ctx.font = `${isSelected ? "bold " : ""}8px sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(String(agent.id), x, y);
        }
        // テキスト描画後にデフォルトに戻す
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
    }

    /**
     * 選択中 agent から友達への社会的リンク線を描画する内部メソッド。
     * agent レイヤーより下(先)に描画することで線がマーカーの下になる。
     * @param {{ id:number, lat:number, lon:number }} center
     * @param {Array<{ id:number, lat:number, lon:number }>} friends
     */
    _drawSocialLinkLines(center, friends) {
        if (!center || !friends || friends.length === 0) return;
        const ctx = this._ctx;
        const { x: cx, y: cy } = this._project(center.lat, center.lon);

        ctx.save();
        ctx.strokeStyle = SOCIAL_LINK_COLOR;
        ctx.lineWidth   = SOCIAL_LINK_WIDTH;
        ctx.setLineDash([5, 3]);  // 破線で道路線と区別

        for (const friend of friends) {
            const { x: fx, y: fy } = this._project(friend.lat, friend.lon);
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(fx, fy);
            ctx.stroke();

            // 友達マーカー位置に強調リングを追加
            ctx.beginPath();
            ctx.arc(fx, fy, AGENT_RADIUS + 4, 0, Math.PI * 2);
            ctx.strokeStyle = FRIEND_RING_COLOR;
            ctx.lineWidth   = 1.5;
            ctx.setLineDash([]);
            ctx.stroke();
            // 次の線描画のためにスタイルを戻す
            ctx.strokeStyle = SOCIAL_LINK_COLOR;
            ctx.lineWidth   = SOCIAL_LINK_WIDTH;
            ctx.setLineDash([5, 3]);
        }

        ctx.restore();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 内部: クリック判定
    // ─────────────────────────────────────────────────────────────────────────

    /** canvas クリック -> agent ヒット判定 */
    _handleClick(event) {
        if (!this._agentClickCb || !this._layers.agent.visible) return;
        const rect = this._canvas.getBoundingClientRect();
        const cx = event.clientX - rect.left;
        const cy = event.clientY - rect.top;

        for (const agent of this._layers.agent.markers) {
            const { x, y } = this._project(agent.lat, agent.lon);
            const dx = cx - x;
            const dy = cy - y;
            if (dx * dx + dy * dy <= (AGENT_RADIUS + 4) ** 2) {
                this._agentClickCb(agent.id);
                return;
            }
        }
    }
}
