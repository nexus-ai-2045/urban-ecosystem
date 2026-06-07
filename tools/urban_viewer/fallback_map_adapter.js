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

import { CATEGORY_COLORS, ROLE_COLORS } from "./colors.js";

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
 * @property {string} [label] - マーカーに表示する短縮ラベル (苗字2文字など / 省略時は id)
 */

/** canvas のパディング (px) — 最大 bounds を少し縮めて余白を作る */
const CANVAS_PADDING = 20;

/** エージェント円の半径 (px) */
const AGENT_RADIUS = 4;

/** POI 点の半径 (px) */
const POI_RADIUS = 3;

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

function _hexToRgba(hex, alpha) {
    const value = String(hex || "").replace("#", "");
    if (!/^[0-9a-fA-F]{6}$/.test(value)) {
        return `rgba(44, 62, 80, ${alpha})`;
    }
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

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
            poi:   { geojson: null, visible: false },
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

        // Agent (密度 -> 移動方向 -> 点)
        if (this._layers.agent.visible) {
            this._drawAgentDensity(this._layers.agent.markers);
            this._drawAgentMovement(this._layers.agent.markers);
            this._drawAgents(this._layers.agent.markers);
        }

        this._drawLayerStateIndicator();
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

    /** fallback canvas 上に POI / AOI / road の表示状態を小さく反映する */
    _drawLayerStateIndicator() {
        const ctx = this._ctx;
        const entries = [
            ["poi", "#2f80ed"],
            ["aoi", "#27ae60"],
            ["road", "#7f8c8d"],
        ];
        const size = 8;
        const gap = 4;
        const x0 = Math.max(8, this._canvas.width - entries.length * (size + gap) - 8);
        const y = Math.max(8, this._canvas.height - size - 8);

        entries.forEach(([name, color], index) => {
            const x = x0 + index * (size + gap);
            ctx.fillStyle = this._layers[name].visible ? color : "#ffffff";
            ctx.fillRect(x, y, size, size);
            ctx.strokeStyle = "#222222";
            ctx.strokeRect(x, y, size, size);
        });
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
                ctx.fillStyle = "rgba(100, 180, 100, 0.10)";
                ctx.fill();
                ctx.strokeStyle = "rgba(60, 140, 60, 0.38)";
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
            const roleColor = ROLE_COLORS[agent.role] || AGENT_DEFAULT_COLOR;
            const color = isSelected ? HIGHLIGHT_COLOR : roleColor;

            // 実地図の歩行者に見えるよう、通常時は小さな半透明点にする。
            ctx.beginPath();
            ctx.arc(x, y, isSelected ? AGENT_RADIUS + 2 : AGENT_RADIUS, 0, Math.PI * 2);
            ctx.globalAlpha = isSelected ? 1 : 0.62;
            ctx.fillStyle = isSelected ? "rgba(255, 238, 238, 0.95)" : color;
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = isSelected ? 2.5 : 1;
            ctx.stroke();
            ctx.globalAlpha = 1;

            if (isSelected) {
                const labelText = agent.label != null ? String(agent.label) : String(agent.id);
                ctx.fillStyle = color;
                ctx.font = "bold 8px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(labelText, x, y);
            }
        }
        // テキスト描画後にデフォルトに戻す
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
    }

    _drawAgentDensity(agents) {
        const ctx = this._ctx;
        ctx.save();
        ctx.globalCompositeOperation = "multiply";
        for (const agent of agents) {
            const { x, y } = this._project(agent.lat, agent.lon);
            const color = ROLE_COLORS[agent.role] || AGENT_DEFAULT_COLOR;
            const gradient = ctx.createRadialGradient(x, y, 1, x, y, agent.moving ? 15 : 20);
            gradient.addColorStop(0, _hexToRgba(color, agent.moving ? 0.16 : 0.22));
            gradient.addColorStop(1, _hexToRgba(color, 0));
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(x, y, agent.moving ? 15 : 20, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    _drawAgentMovement(agents) {
        const ctx = this._ctx;
        ctx.save();
        ctx.lineWidth = 1;
        for (const agent of agents) {
            if (!agent.moving || !Number.isFinite(agent.nextLat) || !Number.isFinite(agent.nextLon)) continue;
            const { x, y } = this._project(agent.lat, agent.lon);
            const next = this._project(agent.nextLat, agent.nextLon);
            const dx = next.x - x;
            const dy = next.y - y;
            if (dx * dx + dy * dy < 4) continue;
            const color = ROLE_COLORS[agent.role] || AGENT_DEFAULT_COLOR;
            ctx.strokeStyle = _hexToRgba(color, 0.28);
            ctx.fillStyle = _hexToRgba(color, 0.28);
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(next.x, next.y);
            ctx.stroke();

            const angle = Math.atan2(dy, dx);
            const arrowX = x + dx * 0.72;
            const arrowY = y + dy * 0.72;
            ctx.beginPath();
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX - Math.cos(angle - 0.55) * 5, arrowY - Math.sin(angle - 0.55) * 5);
            ctx.lineTo(arrowX - Math.cos(angle + 0.55) * 5, arrowY - Math.sin(angle + 0.55) * 5);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();
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
