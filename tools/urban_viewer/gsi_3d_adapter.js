/**
 * gsi_3d_adapter.js - API key free deterministic GSI 3D style canvas adapter.
 *
 * This is the local replay adapter that can later be swapped for MapLibre /
 * GSI vector tiles. It does not fetch external tiles, so CI and API-key-free
 * viewer paths stay deterministic.
 */

"use strict";

import { FallbackMapAdapter } from "./fallback_map_adapter.js?v=20260606-realflow";

const ATTRIBUTION_CLASS = "gsi-3d-attribution";

export class Gsi3DAdapter extends FallbackMapAdapter {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {HTMLElement|null} container
     */
    constructor(canvas, container = null) {
        super(canvas);
        this._container = container || canvas.parentElement || null;
    }

    init(options = {}) {
        if (window.__URBAN_FORCE_GSI_3D_FAIL__ || options.forceUnavailable) {
            throw new Error("GSI 3D adapter unavailable");
        }
        super.init(options);
        this._ensureAttribution();
    }

    _ensureAttribution() {
        if (!this._container) return;
        this._container.style.position = "relative";
        let attribution = this._container.querySelector(`.${ATTRIBUTION_CLASS}`);
        if (!attribution) {
            attribution = document.createElement("div");
            attribution.className = ATTRIBUTION_CLASS;
            this._container.appendChild(attribution);
        }
        attribution.textContent = "出典: 国土地理院";
    }

    _drawBackground() {
        const ctx = this._ctx;
        const w = this._canvas.width;
        const h = this._canvas.height;

        const gradient = ctx.createLinearGradient(0, 0, w, h);
        gradient.addColorStop(0, "#e8f0ee");
        gradient.addColorStop(0.58, "#d8e6e3");
        gradient.addColorStop(1, "#cbd8d5");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h);

        ctx.save();
        ctx.translate(w * 0.5, h * 0.42);
        ctx.rotate(-Math.PI / 10);
        ctx.strokeStyle = "rgba(82, 105, 103, 0.16)";
        ctx.lineWidth = 1;
        const step = 34;
        for (let x = -w; x < w; x += step) {
            ctx.beginPath();
            ctx.moveTo(x, -h);
            ctx.lineTo(x, h);
            ctx.stroke();
        }
        for (let y = -h; y < h; y += step) {
            ctx.beginPath();
            ctx.moveTo(-w, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }
        ctx.restore();

        ctx.fillStyle = "rgba(35, 52, 54, 0.62)";
        ctx.font = "12px sans-serif";
        ctx.fillText("GSI 3D Layer (local replay)", 8, h - 22);
        ctx.fillText("出典: 国土地理院", 8, h - 7);
    }

    _drawAois(geojson) {
        for (const feature of geojson.features || []) {
            if (!feature.geometry) continue;
            const type = feature.geometry.type;
            const polygons = type === "Polygon"
                ? [feature.geometry.coordinates]
                : type === "MultiPolygon"
                    ? feature.geometry.coordinates
                    : [];
            for (const rings of polygons) {
                const projected = [];
                for (const ring of rings) {
                    projected.push(ring.map(([lon, lat]) => this._project(lat, lon)));
                }
                this._drawExtrudedPolygon(projected, feature.properties || {});
            }
        }
    }

    _drawExtrudedPolygon(rings, properties) {
        if (!rings.length || !rings[0].length) return;
        const ctx = this._ctx;
        const heightSeed = String(properties.id || properties.name || "").length;
        const height = 8 + (heightSeed % 5) * 5;
        const dx = height * 0.58;
        const dy = -height;

        ctx.save();
        ctx.translate(dx, dy);
        this._traceRings(rings);
        ctx.fillStyle = "rgba(120, 147, 145, 0.42)";
        ctx.fill();
        ctx.strokeStyle = "rgba(64, 90, 92, 0.34)";
        ctx.stroke();
        ctx.restore();

        this._traceRings(rings);
        ctx.fillStyle = "rgba(76, 119, 117, 0.26)";
        ctx.fill();
        ctx.strokeStyle = "rgba(44, 74, 76, 0.42)";
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    _traceRings(rings) {
        const ctx = this._ctx;
        ctx.beginPath();
        for (const ring of rings) {
            for (let i = 0; i < ring.length; i++) {
                const { x, y } = ring[i];
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
        }
    }

    _drawRoads(geojson) {
        const ctx = this._ctx;
        ctx.strokeStyle = "rgba(65, 82, 86, 0.34)";
        ctx.lineWidth = 1.2;
        super._drawRoads(geojson);
    }
}
