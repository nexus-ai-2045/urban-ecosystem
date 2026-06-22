/**
 * gsi_3d_live_adapter.js — MapLibre GL JS + 国土地理院最適化ベクトルタイルを使う live adapter。
 *
 * 正本: docs/gsi-3d-map-layer.md §gsi_3d_live
 * インターフェース: map_adapter.js (init / setLayer / upsertAgents / highlight / onAgentClick
 *                               / drawSocialLinks / clearSocialLinks)
 *
 * 設計方針:
 *   - extends は使わない (duck-typing)。
 *   - window.maplibregl 未ロード / options.forceUnavailable / window.__URBAN_FORCE_GSI_LIVE_FAIL__
 *     のいずれかで init() が throw → app.js が FallbackMapAdapter へ降格する。
 *   - 建物高さは固定値 (普通=10m / 堅牢=40m / 高層・大型=100m)。実際の高さではない旨を attribution に明記。
 *   - bounds は MapLibre fitBounds() で自力管理。app.js の _recomputeBounds には依存しない。
 *   - GSI tile 失敗時も attribution は除去しない (MapLibre デフォルト attributionControl が維持する)。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

// ─── タイル定数 ───────────────────────────────────────────────────────────────

/** 国土地理院 最適化ベクトルタイル XYZ URL */
const GSI_TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/{z}/{x}/{y}.pbf";

/** attribution に常時表示するテキスト (tile 失敗時も維持) */
const GSI_ATTRIBUTION =
    "出典：国土地理院最適化ベクトルタイル（実際の建物高さを示すものではない）";

/** 地物コード → 建物高さ (m) マッピング。実際の高さではない (GSI サンプル参照) */
const BUILDING_HEIGHT_MATCH = [
    "match",
    ["get", "ftCode"],
    // 堅牢建物 (3102): 40m
    [3102], 40,
    // 高層建物 (3111) / 大型建物 (3112): 100m
    [3111, 3112], 100,
    // 普通建物 (3101) その他: 10m
    10,
];

/** エージェントマーカーの強調 CSS クラス */
const HIGHLIGHT_CLASS = "gsi-live-marker--highlight";

/** 社会リンクの GeoJSON source / layer ID */
const SOCIAL_LINKS_SOURCE_ID = "gsi-live-social-links";
const SOCIAL_LINKS_LAYER_ID  = "gsi-live-social-links-layer";

// ─── アダプタ本体 ─────────────────────────────────────────────────────────────

export class Gsi3DLiveAdapter {
    /**
     * @param {HTMLElement} container - MapLibre が描画する DOM 要素
     */
    constructor(container) {
        /** @type {HTMLElement} */
        this._container = container;

        /** @type {maplibregl.Map|null} */
        this._map = null;

        /** @type {Map<number, maplibregl.Marker>} エージェント ID → Marker */
        this._markers = new Map();

        /** @type {((agentId: number) => void)|null} エージェントクリックコールバック */
        this._clickCallback = null;

        /** @type {number|null} 現在の強調エージェント ID */
        this._highlightedId = null;

        /** @type {boolean} setLayer 前に Map が ready かどうか */
        this._mapReady = false;

        /** @type {Map<string, Object>} レイヤー名 → 最新 GeoJSON (ready 前のバッファ) */
        this._pendingLayers = new Map();

        /** @type {boolean} agent マーカーの表示状態 (setLayer("agent", ...) で切替) */
        this._agentsVisible = true;
    }

    // ─── init ─────────────────────────────────────────────────────────────────

    /**
     * MapLibre Map を初期化する。
     *
     * @param {Object} [options]
     * @param {boolean} [options.forceUnavailable] - テスト用強制失敗フラグ
     * @throws {Error} window.maplibregl 未ロード / forceUnavailable / __URBAN_FORCE_GSI_LIVE_FAIL__
     */
    init(options = {}) {
        // 利用不可条件: fallback 降格テスト用フラグ
        if (
            options.forceUnavailable ||
            (typeof window !== "undefined" && window.__URBAN_FORCE_GSI_LIVE_FAIL__)
        ) {
            throw new Error("GSI 3D Live adapter unavailable (forceUnavailable or test flag)");
        }

        // MapLibre GL JS が window.maplibregl としてロード済みであることを確認する
        if (typeof window === "undefined" || !window.maplibregl) {
            throw new Error(
                "GSI 3D Live adapter unavailable: window.maplibregl が見つかりません。" +
                "EXPERIMENTAL_GSI_TILE が有効なときだけ使用できます。"
            );
        }

        const maplibregl = window.maplibregl;

        // コンテナを初期化する
        this._container.style.position = "relative";
        // コンテナ内の既存コンテンツをクリアしてから Map を生成する
        const mapDiv = document.createElement("div");
        mapDiv.style.width = "100%";
        mapDiv.style.height = "100%";
        this._container.appendChild(mapDiv);

        // MapLibre Map を生成する
        this._map = new maplibregl.Map({
            container: mapDiv,
            // GSI ベクトルタイルを style の source として設定する
            style: {
                version: 8,
                // glyphs (font) は定義しない: 本 style に symbol/text レイヤーが無いため不要。
                // 第三者 (MapLibre demo) サーバーへの font fetch を発生させないことを明示。
                sources: {
                    "gsi-bvmap": {
                        type: "vector",
                        tiles: [GSI_TILE_URL],
                        minzoom: 4,
                        maxzoom: 16,
                        attribution: GSI_ATTRIBUTION,
                    },
                },
                layers: [
                    // 背景色 (海・背景)
                    {
                        id: "background",
                        type: "background",
                        paint: { "background-color": "#e8f0ee" },
                    },
                    // 道路 (RdCL source-layer)
                    {
                        id: "road-line",
                        type: "line",
                        source: "gsi-bvmap",
                        "source-layer": "RdCL",
                        paint: {
                            "line-color": "#b0a89a",
                            "line-width": [
                                "interpolate", ["linear"], ["zoom"],
                                10, 0.5,
                                14, 1.5,
                                16, 3,
                            ],
                        },
                    },
                    // 建物フットプリント (BldA source-layer) — 底面
                    {
                        id: "building-fill",
                        type: "fill-extrusion",
                        source: "gsi-bvmap",
                        "source-layer": "BldA",
                        paint: {
                            "fill-extrusion-color": [
                                "match",
                                ["get", "ftCode"],
                                [3102], "#8fa8a6",
                                [3111, 3112], "#6a8888",
                                "#a8b8b6",
                            ],
                            // 固定高さ: 普通=10m / 堅牢=40m / 高層・大型=100m (実際の高さではない)
                            "fill-extrusion-height": BUILDING_HEIGHT_MATCH,
                            "fill-extrusion-base": 0,
                            "fill-extrusion-opacity": 0.75,
                        },
                    },
                ],
            },
            // 初期表示は渋谷周辺 (replay データのデフォルト中心)
            center: [139.700, 35.660],
            zoom: 14,
            pitch: 45,
            attributionControl: true,
        });

        // Map が load 完了したら pending layer を適用する
        this._map.on("load", () => {
            this._mapReady = true;
            for (const [name, geojson] of this._pendingLayers.entries()) {
                this._applyGeoJsonLayer(name, geojson);
            }
            this._pendingLayers.clear();
        });

        return Promise.resolve();
    }

    // ─── setLayer ─────────────────────────────────────────────────────────────

    /**
     * GeoJSON レイヤーを設定する。
     *
     * @param {"poi"|"aoi"|"road"|"agent"} name
     * @param {boolean} visible
     * @param {Object|null} [geojson]
     */
    setLayer(name, visible, geojson = null) {
        if (!geojson) {
            // data なし: 可視性だけ切り替える
            this._setLayerVisibility(name, visible);
            return;
        }

        if (!this._mapReady) {
            // Map が load 完了前: バッファリングして load 後に適用する
            this._pendingLayers.set(name, geojson);
            return;
        }

        this._applyGeoJsonLayer(name, geojson);
        this._setLayerVisibility(name, visible);

        // GeoJSON が空でなければ bounds に合わせる (自力管理)
        const features = geojson.features || [];
        if (features.length > 0) {
            this._fitBoundsToGeojson(geojson);
        }
    }

    /**
     * GeoJSON を MapLibre の source / layer として追加または更新する。
     * @private
     */
    _applyGeoJsonLayer(name, geojson) {
        if (!this._map) return;
        const sourceId = `gsi-live-${name}`;
        const layerId  = `gsi-live-${name}-layer`;

        if (this._map.getSource(sourceId)) {
            /** @type {maplibregl.GeoJSONSource} */
            const src = this._map.getSource(sourceId);
            src.setData(geojson);
        } else {
            this._map.addSource(sourceId, {
                type: "geojson",
                data: geojson,
            });
            this._map.addLayer(_makeLayerSpec(name, sourceId, layerId));
        }
    }

    /**
     * レイヤーの可視性を切り替える。
     * @private
     */
    _setLayerVisibility(name, visible) {
        // agent は MapLibre layer ではなく Marker (this._markers) で管理するため、
        // marker DOM 要素の表示で可視性を切り替える (FallbackMapAdapter と挙動を揃える)。
        if (name === "agent") {
            this._agentsVisible = visible;
            for (const marker of this._markers.values()) {
                marker.getElement().style.display = visible ? "" : "none";
            }
            return;
        }
        if (!this._map) return;
        const layerId = `gsi-live-${name}-layer`;
        if (!this._map.getLayer(layerId)) return;
        this._map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
    }

    /**
     * GeoJSON の全 feature の bbox に fitBounds する。
     * @private
     */
    _fitBoundsToGeojson(geojson) {
        if (!this._map) return;
        const bbox = _computeBbox(geojson);
        if (!bbox) return;
        const [minLon, minLat, maxLon, maxLat] = bbox;
        const padding = 40; // px
        this._map.fitBounds(
            [[minLon, minLat], [maxLon, maxLat]],
            { padding, pitch: 45, duration: 500 },
        );
    }

    // ─── upsertAgents ─────────────────────────────────────────────────────────

    /**
     * エージェントマーカーを一括更新する。
     *
     * @param {Array<{id:number, lat:number, lon:number, label?:string}>} agents
     */
    upsertAgents(agents) {
        if (!this._map) return;
        const maplibregl = window.maplibregl;
        if (!maplibregl) return;

        const seen = new Set();
        for (const agent of agents) {
            seen.add(agent.id);
            let marker = this._markers.get(agent.id);
            if (!marker) {
                // 新規マーカーを作成する
                const el = _createMarkerElement(agent.id, agent.label || String(agent.id));
                el.addEventListener("click", () => {
                    if (this._clickCallback) this._clickCallback(agent.id);
                });
                // 現在の agent 可視性状態を新規マーカーにも反映する
                if (!this._agentsVisible) el.style.display = "none";
                marker = new maplibregl.Marker({ element: el })
                    .setLngLat([agent.lon, agent.lat])
                    .addTo(this._map);
                this._markers.set(agent.id, marker);
            } else {
                // 既存マーカーの位置を更新する
                marker.setLngLat([agent.lon, agent.lat]);
            }
        }

        // 存在しなくなったエージェントのマーカーを削除する
        for (const [id, marker] of this._markers.entries()) {
            if (!seen.has(id)) {
                marker.remove();
                this._markers.delete(id);
            }
        }
    }

    // ─── highlight ────────────────────────────────────────────────────────────

    /**
     * 指定 agentId を強調表示する (null で解除)。
     *
     * @param {number|null} agentId
     */
    highlight(agentId) {
        // 旧ハイライトを解除する
        if (this._highlightedId !== null) {
            const prev = this._markers.get(this._highlightedId);
            if (prev) prev.getElement().classList.remove(HIGHLIGHT_CLASS);
        }
        this._highlightedId = agentId;
        if (agentId !== null) {
            const marker = this._markers.get(agentId);
            if (marker) marker.getElement().classList.add(HIGHLIGHT_CLASS);
        }
    }

    // ─── onAgentClick ─────────────────────────────────────────────────────────

    /**
     * エージェントクリック時のコールバックを登録する。
     *
     * @param {(agentId: number) => void} cb
     */
    onAgentClick(cb) {
        this._clickCallback = cb;
    }

    // ─── drawSocialLinks ──────────────────────────────────────────────────────

    /**
     * 選択中 agent から友達 agent への社会的リンク線を描画する。
     *
     * @param {{ id:number, lat:number, lon:number }} centerAgent
     * @param {Array<{ id:number, lat:number, lon:number }>} friendAgents
     */
    drawSocialLinks(centerAgent, friendAgents) {
        if (!this._map || !this._mapReady) return;

        const geojson = {
            type: "FeatureCollection",
            features: friendAgents.map((friend) => ({
                type: "Feature",
                geometry: {
                    type: "LineString",
                    coordinates: [
                        [centerAgent.lon, centerAgent.lat],
                        [friend.lon, friend.lat],
                    ],
                },
                properties: { fromId: centerAgent.id, toId: friend.id },
            })),
        };

        if (this._map.getSource(SOCIAL_LINKS_SOURCE_ID)) {
            this._map.getSource(SOCIAL_LINKS_SOURCE_ID).setData(geojson);
        } else {
            this._map.addSource(SOCIAL_LINKS_SOURCE_ID, {
                type: "geojson",
                data: geojson,
            });
            this._map.addLayer({
                id: SOCIAL_LINKS_LAYER_ID,
                type: "line",
                source: SOCIAL_LINKS_SOURCE_ID,
                paint: {
                    "line-color": "rgba(230, 120, 30, 0.6)",
                    "line-width": 1.5,
                    "line-dasharray": [3, 2],
                },
            });
        }
    }

    // ─── clearSocialLinks ─────────────────────────────────────────────────────

    /**
     * drawSocialLinks で描画した社会的リンク線をすべて消去する。
     */
    clearSocialLinks() {
        if (!this._map) return;
        if (this._map.getLayer(SOCIAL_LINKS_LAYER_ID)) {
            this._map.removeLayer(SOCIAL_LINKS_LAYER_ID);
        }
        if (this._map.getSource(SOCIAL_LINKS_SOURCE_ID)) {
            this._map.removeSource(SOCIAL_LINKS_SOURCE_ID);
        }
    }
}

// ─── ヘルパー関数 ─────────────────────────────────────────────────────────────

/**
 * レイヤー名に応じた MapLibre layer spec を返す。
 *
 * @param {"poi"|"aoi"|"road"|"agent"} name
 * @param {string} sourceId
 * @param {string} layerId
 * @returns {Object}
 */
function _makeLayerSpec(name, sourceId, layerId) {
    switch (name) {
        case "aoi":
            return {
                id: layerId,
                type: "fill",
                source: sourceId,
                filter: ["==", "$type", "Polygon"],
                paint: {
                    "fill-color": "rgba(76, 119, 117, 0.22)",
                    "fill-outline-color": "rgba(44, 74, 76, 0.5)",
                },
            };
        case "road":
            return {
                id: layerId,
                type: "line",
                source: sourceId,
                filter: ["==", "$type", "LineString"],
                paint: {
                    "line-color": "rgba(65, 82, 86, 0.5)",
                    "line-width": 1.2,
                },
            };
        case "poi":
            return {
                id: layerId,
                type: "circle",
                source: sourceId,
                filter: ["==", "$type", "Point"],
                paint: {
                    "circle-radius": 4,
                    "circle-color": "#4a7a6a",
                    "circle-opacity": 0.7,
                },
            };
        case "agent":
        default:
            // agent は upsertAgents の MapLibre Marker で管理するため layer は不要。
            // ただし呼ばれる可能性があるので空のレイヤーを返す。
            return {
                id: layerId,
                type: "circle",
                source: sourceId,
                filter: ["==", "$type", "Point"],
                paint: {
                    "circle-radius": 0,
                    "circle-opacity": 0,
                },
            };
    }
}

/**
 * エージェントマーカー DOM 要素を生成する。
 *
 * @param {number} agentId
 * @param {string} label
 * @returns {HTMLElement}
 */
function _createMarkerElement(agentId, label) {
    const el = document.createElement("div");
    el.className = "gsi-live-agent-marker";
    el.dataset.agentId = String(agentId);
    el.style.cssText = [
        "width:18px",
        "height:18px",
        "border-radius:50%",
        "background:#2c3e50",
        "border:2px solid #fff",
        "cursor:pointer",
        "display:flex",
        "align-items:center",
        "justify-content:center",
        "font-size:8px",
        "color:#fff",
        "font-family:sans-serif",
        "box-sizing:border-box",
        "user-select:none",
    ].join(";");
    el.textContent = String(label).slice(0, 2);
    return el;
}

/**
 * GeoJSON FeatureCollection の [minLon, minLat, maxLon, maxLat] bbox を返す。
 *
 * @param {Object} geojson
 * @returns {[number, number, number, number]|null}
 */
function _computeBbox(geojson) {
    let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
    let found = false;

    function processCoords(coords) {
        if (!Array.isArray(coords)) return;
        if (typeof coords[0] === "number") {
            // [lon, lat] の場合
            const [lon, lat] = coords;
            if (isFinite(lon) && isFinite(lat)) {
                if (lon < minLon) minLon = lon;
                if (lon > maxLon) maxLon = lon;
                if (lat < minLat) minLat = lat;
                if (lat > maxLat) maxLat = lat;
                found = true;
            }
            return;
        }
        for (const sub of coords) processCoords(sub);
    }

    for (const feature of (geojson.features || [])) {
        const geom = feature && feature.geometry;
        if (geom && geom.coordinates) processCoords(geom.coordinates);
    }

    return found ? [minLon, minLat, maxLon, maxLat] : null;
}
