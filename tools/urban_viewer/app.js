/**
 * app.js — ViewerState / 再生ループ / イベント配線。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.5 / §8.1
 *
 * - ViewerState を単一オブジェクトとして管理する。
 * - GOOGLE_MAPS_API_KEY の有無でアダプタを差し替える。
 * - 再生ループは requestAnimationFrame ベース (setInterval は使わない / §5.1.4)。
 * - adapter は描画専用。状態は本ファイルが保持する。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

import { FallbackMapAdapter }  from "./fallback_map_adapter.js";
import { GoogleMapsAdapter }   from "./google_maps_adapter.js";
import {
    updateLegend,
    updateAgentDetail,
    updateTimeDisplay,
    updateSlider,
    updatePlayButton,
    updateRunSelector,
} from "./ui_panels.js";

// ─────────────────────────────────────────────────────────────────────────────
// 定数
// ─────────────────────────────────────────────────────────────────────────────

/** API キー注入プレースホルダー: サーバーが HTML 生成時に置き換える */
const MAPS_API_KEY = "%%GOOGLE_MAPS_API_KEY%%";

/** Map ID 注入プレースホルダー: サーバーが HTML 生成時に置き換える */
const MAPS_MAP_ID  = "%%GOOGLE_MAPS_MAP_ID%%";

/** API サーバー base URL (同一オリジン) */
const API_BASE = "";

/** requestAnimationFrame の実時間あたり tick 数: speed(1|2|5) x を何 ms で 1 tick 進めるか */
const MS_PER_TICK_AT_1X = 1000;  // 1x = 1 tick/秒 (5分刻みを1秒で表示)

// ─────────────────────────────────────────────────────────────────────────────
// ViewerState 初期値
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @typedef {Object} ViewerState
 * @property {{ pois:Object[], aois:Object[], roads:Object[], profiles:Object[] }} data
 * @property {{ ticks:number[], tickIndex:number, playing:boolean, speed:1|2|5, statesByTick:Map<number,Object[]> }} replay
 * @property {{ agentId:number|null }} selection
 * @property {{ poi:boolean, aoi:boolean, road:boolean, agent:boolean }} layerVisible
 */

/** @type {ViewerState} */
const state = {
    data: {
        pois:     [],
        aois:     [],
        roads:    [],
        profiles: [],
    },
    replay: {
        ticks:       [],
        tickIndex:   0,
        playing:     false,
        speed:       1,
        statesByTick: new Map(),
    },
    selection: { agentId: null },
    layerVisible: {
        poi:   true,
        aoi:   true,
        road:  true,
        agent: true,
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// adapter (キー有無で切り替え)
// ─────────────────────────────────────────────────────────────────────────────

/** @type {FallbackMapAdapter|GoogleMapsAdapter} */
let adapter = null;

/** Google Maps を使うかどうか */
const hasApiKey = MAPS_API_KEY && !MAPS_API_KEY.startsWith("%%");

// ─────────────────────────────────────────────────────────────────────────────
// DOM 要素
// ─────────────────────────────────────────────────────────────────────────────

const mapContainer  = document.getElementById("map-container");
const mapCanvas     = document.getElementById("map-canvas");
const legendEl      = document.getElementById("legend-panel");
const detailEl      = document.getElementById("detail-panel");
const timeEl        = document.getElementById("time-display");
const playBtn       = document.getElementById("btn-play");
const stepBtn       = document.getElementById("btn-step");
const speedSel      = document.getElementById("speed-select");
const sliderEl      = document.getElementById("time-slider");
const runSel        = document.getElementById("run-select");
const loadBtn       = document.getElementById("btn-load");
const layerPoi      = document.getElementById("layer-poi");
const layerAoi      = document.getElementById("layer-aoi");
const layerRoad     = document.getElementById("layer-road");
const layerAgent    = document.getElementById("layer-agent");

// ─────────────────────────────────────────────────────────────────────────────
// 初期化
// ─────────────────────────────────────────────────────────────────────────────

async function initAdapter() {
    if (hasApiKey) {
        adapter = new GoogleMapsAdapter(mapContainer, MAPS_API_KEY, MAPS_MAP_ID);
    } else {
        // fallback: canvas を使う
        if (mapCanvas) mapCanvas.style.display = "block";
        if (mapContainer) mapContainer.style.position = "relative";
        adapter = new FallbackMapAdapter(mapCanvas);
    }
    await adapter.init();
    adapter.onAgentClick(handleAgentClick);
}

async function main() {
    // アダプタ初期化
    await initAdapter();

    // run 一覧を取得して selector に反映
    const runs = await fetchRuns();
    updateRunSelector(runSel, runs);

    // イベント配線
    wireEvents();

    // 最初の run を自動ロード (ある場合)
    if (runs && runs.length > 0) {
        await loadRun(runs[0].run_id);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// API 取得
// ─────────────────────────────────────────────────────────────────────────────

/** /api/runs を取得する */
async function fetchRuns() {
    try {
        const res = await fetch(`${API_BASE}/api/runs`);
        if (!res.ok) return [];
        const json = await res.json();
        return json.runs || [];
    } catch {
        return [];
    }
}

/**
 * run のデータファイルを取得する。
 * @param {string} runId
 * @param {string} file
 * @returns {Promise<Object|string|null>}
 */
async function fetchRunFile(runId, file) {
    const res = await fetch(`${API_BASE}/api/data/${encodeURIComponent(runId)}/${file}`);
    if (!res.ok) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("x-ndjson") || ct.includes("jsonl")) {
        // JSONL: テキストを行分割して JSON パース
        const text = await res.text();
        return text.trim().split("\n").filter(Boolean).map(l => JSON.parse(l));
    }
    return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// run ロード
// ─────────────────────────────────────────────────────────────────────────────

/**
 * run_id を指定してデータをロードし、地図を初期表示する。
 * @param {string} runId
 */
async function loadRun(runId) {
    if (!runId) return;

    // 並列ロード
    const [poisData, aoisData, roadsData, profilesData, statesRaw] = await Promise.all([
        fetchRunFile(runId, "pois.geojson"),
        fetchRunFile(runId, "aois.geojson"),
        fetchRunFile(runId, "roadnet.geojson"),
        fetchRunFile(runId, "agent_profiles_N100.json"),
        fetchRunFile(runId, "agent_states.jsonl"),
    ]);

    // data を正規化してセット
    state.data.pois     = poisData?.features?.map(f => ({
        ...f.properties,
        lat: f.geometry?.coordinates?.[1],
        lon: f.geometry?.coordinates?.[0],
    })) || [];
    state.data.aois     = aoisData?.features    || [];
    state.data.roads    = roadsData?.features   || [];
    state.data.profiles = Array.isArray(profilesData) ? profilesData : [];

    // agent_states を tick 別にインデックス化
    const statesByTick = new Map();
    for (const s of (statesRaw || [])) {
        if (!statesByTick.has(s.tick)) statesByTick.set(s.tick, []);
        statesByTick.get(s.tick).push(s);
    }
    const ticks = [...statesByTick.keys()].sort((a, b) => a - b);

    state.replay.statesByTick = statesByTick;
    state.replay.ticks        = ticks;
    state.replay.tickIndex    = 0;
    state.replay.playing      = false;

    // GeoJSON レイヤーを adapter にセット
    if (poisData)   adapter.setLayer("poi",   state.layerVisible.poi,   poisData);
    if (aoisData)   adapter.setLayer("aoi",   state.layerVisible.aoi,   aoisData);
    if (roadsData)  adapter.setLayer("road",  state.layerVisible.road,  roadsData);

    // fallback adapter に bounds を再計算させる
    if (adapter instanceof FallbackMapAdapter) {
        adapter._recomputeBounds();
    }

    // 凡例更新
    updateLegend(legendEl, state.data, state.data.profiles.length);

    // 初期表示
    renderCurrentTick();
    updatePlayButton(playBtn, false);
    updateSlider(sliderEl, Math.max(0, ticks.length - 1), 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// 描画
// ─────────────────────────────────────────────────────────────────────────────

/** 現在の tickIndex を描画する */
function renderCurrentTick() {
    const { ticks, tickIndex, statesByTick } = state.replay;
    if (ticks.length === 0) return;

    const tick       = ticks[tickIndex];
    const agentStates = statesByTick.get(tick) || [];

    // adapter.upsertAgents に渡すデータ
    const markerData = agentStates.map(s => ({
        id:  s.agent_id,
        lat: s.lat,
        lon: s.lon,
        action: s.action,
        status: s.status,
        role: state.data.profiles.find(p => p.id === s.agent_id)?.role || "other",
    }));

    adapter.upsertAgents(markerData);
    adapter.setLayer("agent", state.layerVisible.agent);

    // 時刻表示
    const representative = agentStates[0] || null;
    updateTimeDisplay(timeEl, representative);
    updateSlider(sliderEl, Math.max(0, ticks.length - 1), tickIndex);

    // 詳細パネル更新
    const selectedState = agentStates.find(s => s.agent_id === state.selection.agentId) || null;
    updateAgentDetail(detailEl, state.selection.agentId, state.data, selectedState);
}

// ─────────────────────────────────────────────────────────────────────────────
// 再生ループ (requestAnimationFrame ベース / §5.1.4)
// ─────────────────────────────────────────────────────────────────────────────

let _lastTickTime = 0;
let _rafHandle    = null;

/**
 * 再生ループフレーム。
 * @param {DOMHighResTimeStamp} now
 */
function playLoop(now) {
    if (!state.replay.playing) return;

    const msPerTick = MS_PER_TICK_AT_1X / state.replay.speed;
    if (now - _lastTickTime >= msPerTick) {
        _lastTickTime = now;
        stepTick();
    }

    _rafHandle = requestAnimationFrame(playLoop);
}

/** 再生開始 */
function startPlay() {
    state.replay.playing = true;
    _lastTickTime = performance.now();
    _rafHandle = requestAnimationFrame(playLoop);
    updatePlayButton(playBtn, true);
}

/** 再生停止 */
function stopPlay() {
    state.replay.playing = false;
    if (_rafHandle) {
        cancelAnimationFrame(_rafHandle);
        _rafHandle = null;
    }
    updatePlayButton(playBtn, false);
}

/** 1 tick 進める */
function stepTick() {
    const { ticks, tickIndex } = state.replay;
    if (tickIndex >= ticks.length - 1) {
        stopPlay();
        return;
    }
    state.replay.tickIndex = tickIndex + 1;
    renderCurrentTick();
}

// ─────────────────────────────────────────────────────────────────────────────
// イベントハンドラ
// ─────────────────────────────────────────────────────────────────────────────

/** agent クリック */
function handleAgentClick(agentId) {
    state.selection.agentId = agentId;
    adapter.highlight(agentId);

    const tick         = state.replay.ticks[state.replay.tickIndex];
    const agentStates  = state.replay.statesByTick.get(tick) || [];
    const currentState = agentStates.find(s => s.agent_id === agentId) || null;
    updateAgentDetail(detailEl, agentId, state.data, currentState);
}

/** イベント配線 */
function wireEvents() {
    // 再生/停止
    if (playBtn) {
        playBtn.addEventListener("click", () => {
            if (state.replay.playing) stopPlay();
            else startPlay();
        });
    }

    // ステップ
    if (stepBtn) {
        stepBtn.addEventListener("click", () => {
            stopPlay();
            stepTick();
        });
    }

    // 速度
    if (speedSel) {
        speedSel.addEventListener("change", () => {
            const val = parseInt(speedSel.value, 10);
            if (val === 1 || val === 2 || val === 5) {
                state.replay.speed = val;
            }
        });
    }

    // スライダー
    if (sliderEl) {
        sliderEl.addEventListener("input", () => {
            const idx = parseInt(sliderEl.value, 10);
            if (!isNaN(idx)) {
                stopPlay();
                state.replay.tickIndex = idx;
                renderCurrentTick();
            }
        });
    }

    // run 選択 & ロードボタン
    if (loadBtn && runSel) {
        loadBtn.addEventListener("click", async () => {
            const runId = runSel.value;
            if (runId) await loadRun(runId);
        });
    }

    // レイヤートグル
    const layerToggleMap = [
        [layerPoi,   "poi"],
        [layerAoi,   "aoi"],
        [layerRoad,  "road"],
        [layerAgent, "agent"],
    ];
    for (const [checkbox, name] of layerToggleMap) {
        if (!checkbox) continue;
        checkbox.addEventListener("change", () => {
            state.layerVisible[name] = checkbox.checked;
            if (name === "agent") {
                adapter.setLayer("agent", checkbox.checked);
            } else {
                adapter.setLayer(name, checkbox.checked);
            }
        });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// エントリポイント
// ─────────────────────────────────────────────────────────────────────────────

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
} else {
    main();
}
