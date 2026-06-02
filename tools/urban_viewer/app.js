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
    updateLoadStatus,
    updateLivePanel,
    updateMapStatus,
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

/** Google Maps を使うかどうか */
const hasApiKey = MAPS_API_KEY && !MAPS_API_KEY.startsWith("%%");

/** requestAnimationFrame の実時間あたり tick 数: speed(1|2|5) x を何 ms で 1 tick 進めるか */
const MS_PER_TICK_AT_1X = 1000;  // 1x = 1 tick/秒 (5分刻みを1秒で表示)

// ─────────────────────────────────────────────────────────────────────────────
// ViewerState 初期値
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @typedef {Object} ViewerState
 * @property {{ pois:Object[], aois:Object[], roads:Object[], profiles:Object[], visitRecords:Object[] }} data
 * @property {{ ticks:number[], tickIndex:number, playing:boolean, speed:1|2|5, statesByTick:Map<number,Object[]> }} replay
 * @property {{ agentId:number|null }} selection
 * @property {{ poi:boolean, aoi:boolean, road:boolean, agent:boolean }} layerVisible
 * @property {Map<number,Object>} profileMapCache - loadRun 時に 1 度だけ構築して再利用する profileMap (#5)
 */

/** @type {ViewerState} */
const state = {
    data: {
        pois:         [],
        aois:         [],
        roads:        [],
        profiles:     [],
        /** poi_visit_records.jsonl のレコード一覧 (§5.2 / §5.5) */
        visitRecords: [],
    },
    replay: {
        ticks:       [],
        tickIndex:   0,
        playing:     false,
        speed:       1,
        statesByTick: new Map(),
    },
    runtime: {
        runId:      "",
        mapMode:    "Fallback",
        mapsKey:    hasApiKey ? "present" : "absent",
        dataSource: "local",
        mapId:      MAPS_MAP_ID && !MAPS_MAP_ID.startsWith("%%") ? MAPS_MAP_ID : "",
    },
    selection: { agentId: null },
    layerVisible: {
        poi:   true,
        aoi:   true,
        road:  false,   // ランダム道路はデフォルト非表示 (意味の薄い飾り)
        agent: true,
    },
    /** profiles から構築した id -> profile マップ。loadRun 時に 1 度だけ生成してキャッシュ (#5) */
    profileMapCache: new Map(),
};

// ─────────────────────────────────────────────────────────────────────────────
// adapter (キー有無で切り替え)
// ─────────────────────────────────────────────────────────────────────────────

/** @type {FallbackMapAdapter|GoogleMapsAdapter} */
let adapter = null;

// ─────────────────────────────────────────────────────────────────────────────
// DOM 要素
// ─────────────────────────────────────────────────────────────────────────────

const mapContainer  = document.getElementById("map-container");
const mapCanvas     = document.getElementById("map-canvas");
const legendEl      = document.getElementById("legend-panel");
const detailEl      = document.getElementById("detail-panel");
const loadStatusEl  = document.getElementById("load-status");
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
const settingsBtn   = document.getElementById("btn-settings");
const settingsPanel = document.getElementById("settings-panel");

const mapStatusEls = {
    modeValue:      document.getElementById("map-mode-value"),
    mapsKeyValue:   document.getElementById("maps-key-value"),
    mapHealthValue: document.getElementById("map-health-value"),
    dataSourceValue: document.getElementById("data-source-value"),
    mapIdValue:     document.getElementById("map-id-value"),
    googleMapsConfigValue: document.getElementById("google-maps-config-value"),
};

const liveEls = {
    playbackState: document.getElementById("playback-state"),
    runId:         document.getElementById("live-run-id"),
    tick:          document.getElementById("live-tick"),
    time:          document.getElementById("live-time"),
    agentCount:    document.getElementById("live-agent-count"),
    movingCount:   document.getElementById("live-moving-count"),
    selectedAgent: document.getElementById("live-selected-agent"),
    activityList:  document.getElementById("live-activity-list"),
};

// ─────────────────────────────────────────────────────────────────────────────
// 初期化
// ─────────────────────────────────────────────────────────────────────────────

async function initAdapter() {
    if (hasApiKey) {
        try {
            adapter = new GoogleMapsAdapter(mapContainer, MAPS_API_KEY, MAPS_MAP_ID);
            await adapter.init();
            state.runtime.mapMode = "Google Maps";
            updateMapRuntimeStatus();
            adapter.onAgentClick(handleAgentClick);
            return;
        } catch (error) {
            console.warn("Google Maps の初期化に失敗したため fallback 地図に切り替えます。", error);
            state.runtime.mapMode = "Fallback";
        }
    } else {
        state.runtime.mapMode = "Fallback";
    }

    // fallback: canvas を使う
    if (mapCanvas) mapCanvas.style.display = "block";
    if (mapContainer) mapContainer.style.position = "relative";
    adapter = new FallbackMapAdapter(mapCanvas);
    await adapter.init();
    updateMapRuntimeStatus();
    adapter.onAgentClick(handleAgentClick);
}

async function main() {
    // アダプタ初期化
    await initAdapter();
    await refreshHealthStatus();

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

/** /api/health を取得し、公開可能な present/absent 状態だけ UI に反映する。 */
async function refreshHealthStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (!res.ok) return;
        const json = await res.json();
        state.runtime.mapsKey = json.maps_key || state.runtime.mapsKey;
        state.runtime.dataSource = json.data_source || state.runtime.dataSource;
        updateMapRuntimeStatus();
    } catch {
        updateMapRuntimeStatus();
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

    state.runtime.runId = runId;

    const summaryData = await fetchRunFile(runId, "summary.json");
    const profileCount = Number.isInteger(summaryData?.agents) && summaryData.agents > 0
        ? summaryData.agents
        : 100;
    const profilesFile = `agent_profiles_N${profileCount}.json`;

    // 並列ロード (poi_visit_records.jsonl は任意 / §5.2)
    const [poisData, aoisData, roadsData, profilesData, statesRaw, visitRecordsRaw] = await Promise.all([
        fetchRunFile(runId, "pois.geojson"),
        fetchRunFile(runId, "aois.geojson"),
        fetchRunFile(runId, "roadnet.geojson"),
        fetchRunFile(runId, profilesFile),
        fetchRunFile(runId, "agent_states.jsonl"),
        fetchRunFile(runId, "poi_visit_records.jsonl"),
    ]);

    // data を正規化してセット
    state.data.pois     = poisData?.features?.map(f => ({
        ...f.properties,
        lat: f.geometry?.coordinates?.[1],
        lon: f.geometry?.coordinates?.[0],
    })) || [];
    state.data.aois         = aoisData?.features    || [];
    state.data.roads        = roadsData?.features   || [];
    state.data.profiles     = Array.isArray(profilesData) ? profilesData : [];
    /** poi_visit_records.jsonl: 任意ファイル。null (ロード失敗) の場合は空配列にフォールバック */
    state.data.visitRecords = Array.isArray(visitRecordsRaw) ? visitRecordsRaw : [];

    // profileMap を loadRun 時に 1 度だけ構築してキャッシュする (#5)
    // _renderInterpolated (RAF 60fps) と renderCurrentTick の両方がこれを参照する
    state.profileMapCache = _buildProfileMap(state.data.profiles);

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

    // ロード結果をデータ読込パネルに表示する (§5.2: 件数 / 検証結果 / エラー件数)
    updateLoadStatus(loadStatusEl, [
        {
            file:   "pois.geojson",
            count:  poisData     ? state.data.pois.length            : null,
            errors: 0,
        },
        {
            file:   "aois.geojson",
            count:  aoisData     ? state.data.aois.length            : null,
            errors: 0,
        },
        {
            file:   "roadnet.geojson",
            count:  roadsData    ? state.data.roads.length           : null,
            errors: 0,
        },
        {
            file:   profilesFile,
            count:  profilesData ? state.data.profiles.length        : null,
            errors: 0,
        },
        {
            file:   "poi_visit_records.jsonl",
            // 任意ファイル: ロード失敗 (null) と 0 件を区別するため visitRecordsRaw で判定
            count:  visitRecordsRaw !== null ? state.data.visitRecords.length : null,
            errors: 0,
        },
        {
            file:   "agent_states.jsonl",
            // 実 record 件数 (全 agent × tick の行数) を表示する (#4)
            // ticks.length (distinct tick 数) ではなく statesRaw の配列長を使う
            count:  statesRaw    ? statesRaw.length                  : null,
            errors: 0,
        },
    ]);

    // 凡例更新
    updateLegend(legendEl, state.data, state.data.profiles.length);

    // 初期表示 (upsertAgents が async のため await する)
    await renderCurrentTick();
    updatePlayButton(playBtn, false);
    updateSlider(sliderEl, Math.max(0, ticks.length - 1), 0);
    updateLiveRuntimePanel();
}

// ─────────────────────────────────────────────────────────────────────────────
// 描画
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 現在の tickIndex を描画する。
 * upsertAgents が非同期のため async にする。
 * RAF コールバック (playLoop) からは fire-and-forget で呼び出す。
 * @returns {Promise<void>}
 */
async function renderCurrentTick() {
    const { ticks, tickIndex, statesByTick } = state.replay;
    if (ticks.length === 0) return;

    const tick       = ticks[tickIndex];
    const agentStates = statesByTick.get(tick) || [];

    // profileMap は loadRun 時にキャッシュ済みのものを再利用する (#5: 毎フレーム再生成を避ける)
    // profiles は loadRun 後不変なのでキャッシュが最新であることが保証される
    const profileMap = state.profileMapCache;
    const poiMap     = _buildPoiMap(state.data.pois);

    // adapter.upsertAgents に渡すデータ
    // label: マーカー表示用の短縮名。surname があれば surname を使い、なければ name 先頭文字列 (WO-007)
    const markerData = agentStates.map(s => {
        const profile = profileMap.get(s.agent_id);
        let label;
        if (profile) {
            // surname ベース (WO-007): surname があれば使う。なければ name 先頭文字列にフォールバック
            label = profile.surname || (profile.name ? profile.name.slice(0, 2) : String(s.agent_id));
        } else {
            label = String(s.agent_id);
        }
        return {
            id:  s.agent_id,
            lat: s.lat,
            lon: s.lon,
            action: s.action,
            status: s.status,
            role:   profile?.role || "other",
            label,
        };
    });

    // GoogleMapsAdapter は async / FallbackMapAdapter は sync。
    // 両者の戻り値を await することで未解決 Promise を残さない。
    await adapter.upsertAgents(markerData);
    adapter.setLayer("agent", state.layerVisible.agent);

    // 選択中 agent の友達リンクを現在位置に追従更新
    _updateSocialLinks(agentStates);

    // 時刻表示
    const representative = agentStates[0] || null;
    updateTimeDisplay(timeEl, representative);
    updateSlider(sliderEl, Math.max(0, ticks.length - 1), tickIndex);

    // 詳細パネル更新
    const selectedState = agentStates.find(s => s.agent_id === state.selection.agentId) || null;
    // profileMap / poiMap は上記で構築済み。visitRecords は state.data に格納済み
    updateAgentDetail(
        detailEl,
        state.selection.agentId,
        state.data,
        selectedState,
        profileMap,
        poiMap,
        state.data.visitRecords,
    );
    updateLiveRuntimePanel(agentStates);
}

// ─────────────────────────────────────────────────────────────────────────────
// 再生ループ (requestAnimationFrame ベース / §5.1.4)
// ─────────────────────────────────────────────────────────────────────────────

let _lastTickTime = 0;
let _rafHandle    = null;

/**
 * 再生ループフレーム。
 * 隣接 tick 間の lat/lon を線形補間して描画フレーム単位で中間位置を表示する (§5.1.4)。
 * 状態の真値 (tickIndex) はここでは変えない。補間は描画専用。
 * @param {DOMHighResTimeStamp} now
 */
function playLoop(now) {
    if (!state.replay.playing) return;

    const msPerTick = MS_PER_TICK_AT_1X / state.replay.speed;
    const elapsed   = now - _lastTickTime;

    if (elapsed >= msPerTick) {
        // tick 境界を越えたら真値を進める
        _lastTickTime = now;
        stepTick();
    } else {
        // tick 境界前: 描画専用の補間座標でマーカーを更新する
        const alpha = Math.max(0, Math.min(1, elapsed / msPerTick));
        _renderInterpolated(alpha);
    }

    _rafHandle = requestAnimationFrame(playLoop);
}

/**
 * 補間座標でエージェントマーカーを更新する (§5.1.4)。
 * tickIndex の真値は変えず、描画専用の中間位置を生成する。
 * @param {number} alpha - 補間係数 [0, 1]
 */
function _renderInterpolated(alpha) {
    const { ticks, tickIndex, statesByTick } = state.replay;
    if (ticks.length === 0) return;

    const currentTick = ticks[tickIndex];
    // 最終 tick では補間しない
    const nextTick    = tickIndex < ticks.length - 1 ? ticks[tickIndex + 1] : null;

    const currentAgentStates = statesByTick.get(currentTick) || [];
    const nextAgentStates    = nextTick != null ? (statesByTick.get(nextTick) || []) : [];

    // 次 tick 状態を agent_id で高速引き当てするマップを構築
    const nextStateMap = new Map();
    for (const s of nextAgentStates) {
        nextStateMap.set(s.agent_id, s);
    }

    // profileMap は loadRun 時にキャッシュ済みのものを再利用する (#5: RAF 毎の再生成を排除)
    const profileMap = state.profileMapCache;

    // 補間座標を生成して adapter に渡す
    const markerData = currentAgentStates.map(s => {
        const profile = profileMap.get(s.agent_id);
        let label;
        if (profile) {
            label = profile.surname || (profile.name ? profile.name.slice(0, 2) : String(s.agent_id));
        } else {
            label = String(s.agent_id);
        }

        // 次 tick の状態があれば線形補間。なければ現在位置をそのまま使う
        const next = nextStateMap.get(s.agent_id);
        const lat  = next ? (s.lat + (next.lat - s.lat) * alpha) : s.lat;
        const lon  = next ? (s.lon + (next.lon - s.lon) * alpha) : s.lon;

        return {
            id:     s.agent_id,
            lat,
            lon,
            action: s.action,
            status: s.status,
            role:   profile?.role || "other",
            label,
        };
    });

    // fire-and-forget: 補間描画は軽量のため Promise エラーはコンソールに出る
    adapter.upsertAgents(markerData);
}

/** 再生開始 */
function startPlay() {
    state.replay.playing = true;
    _lastTickTime = performance.now();
    _rafHandle = requestAnimationFrame(playLoop);
    updatePlayButton(playBtn, true);
    updateLiveRuntimePanel();
}

/** 再生停止 */
function stopPlay() {
    state.replay.playing = false;
    if (_rafHandle) {
        cancelAnimationFrame(_rafHandle);
        _rafHandle = null;
    }
    updatePlayButton(playBtn, false);
    updateLiveRuntimePanel();
}

/**
 * 1 tick 進める。
 * renderCurrentTick は async だが、playLoop (RAF) から呼ばれる経路があるため
 * fire-and-forget にする。Promise エラーはコンソールに出る。
 */
function stepTick() {
    const { ticks, tickIndex } = state.replay;
    if (tickIndex >= ticks.length - 1) {
        stopPlay();
        return;
    }
    state.replay.tickIndex = tickIndex + 1;
    renderCurrentTick(); // fire-and-forget (RAF 経路)
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

    // 友達リンクを描画 (クリック時に即時反映)
    _updateSocialLinks(agentStates);

    // profileMap はキャッシュを参照 (#5) / poiMap は pois から都度構築
    const profileMap = state.profileMapCache;
    const poiMap     = _buildPoiMap(state.data.pois);
    updateAgentDetail(
        detailEl,
        agentId,
        state.data,
        currentState,
        profileMap,
        poiMap,
        state.data.visitRecords,
    );
    updateLiveRuntimePanel(agentStates);
}

function updateMapRuntimeStatus() {
    updateMapStatus(mapStatusEls, {
        mode:       state.runtime.mapMode,
        mapsKey:    state.runtime.mapsKey,
        dataSource: state.runtime.dataSource,
        mapId:      state.runtime.mapId,
    });
}

function updateLiveRuntimePanel(agentStates = null) {
    const { ticks, tickIndex, statesByTick, playing } = state.replay;
    const tick = ticks[tickIndex] ?? 0;
    const currentAgentStates = agentStates || statesByTick.get(tick) || [];
    const representative = currentAgentStates[0] || null;
    const moving = currentAgentStates.filter(s => s.status === "moving").length;

    updateLivePanel(liveEls, {
        runId:           state.runtime.runId,
        playing,
        tick,
        tickTotal:       ticks.length,
        day:             representative?.day ?? 0,
        time:            representative?.time || "08:00:00",
        agents:          currentAgentStates.length,
        moving,
        selectedAgentId: state.selection.agentId,
        recentVisits:    _getRecentVisits(representative?.day ?? 0, representative?.time || "08:00:00"),
    });
}

/**
 * 現在時刻以前の POI 訪問から、ライブ表示用の直近リストを返す。
 * @param {number} currentDay
 * @param {string} currentTime
 * @returns {Object[]}
 */
function _getRecentVisits(currentDay, currentTime) {
    if (!Array.isArray(state.data.visitRecords) || state.data.visitRecords.length === 0) {
        return [];
    }

    const poiMap = _buildPoiMap(state.data.pois);
    return state.data.visitRecords
        .filter((rec) => {
            const day = rec.day ?? 0;
            const time = rec.time ?? "";
            return day < currentDay || (day === currentDay && time <= currentTime);
        })
        .sort((a, b) => {
            const dayDiff = (b.day ?? 0) - (a.day ?? 0);
            if (dayDiff !== 0) return dayDiff;
            return String(b.time ?? "").localeCompare(String(a.time ?? ""));
        })
        .slice(0, 4)
        .map((rec) => ({
            ...rec,
            poi_name: rec.poi_id ? (poiMap.get(rec.poi_id) || rec.poi_id) : "",
        }));
}

/**
 * profiles 配列から id -> profile オブジェクトのマップを生成する (WO-007)。
 * 旧: id -> name 文字列。新: id -> profile (name / surname / given / role 等を含む)。
 * ui_panels.js の updateAgentDetail は profileMap.get(id) で profile を取得して
 * surname / given フィールドを詳細パネルの表示に使う。
 * @param {Array<{id:number, name?:string, surname?:string, given?:string}>} profiles
 * @returns {Map<number, Object>}
 */
function _buildProfileMap(profiles) {
    const map = new Map();
    for (const p of profiles) {
        if (p.id != null) map.set(p.id, p);
    }
    return map;
}

/**
 * pois 配列から poi_id -> 店名のマップを生成する。
 * state.data.pois は loadRun で feature.properties を展開したオブジェクト配列。
 * name がなければエントリを作らない (呼び出し側で id フォールバック)。
 * @param {Array<{id:string, name?:string}>} pois
 * @returns {Map<string, string>}
 */
function _buildPoiMap(pois) {
    const map = new Map();
    for (const poi of pois) {
        if (poi.id != null && poi.name) map.set(String(poi.id), poi.name);
    }
    return map;
}

/**
 * 選択中 agent の友達リンクを現 tick の位置で更新する。
 * 選択なし / 友達なし の場合はリンクをクリアする。
 * @param {Array<{agent_id:number, lat:number, lon:number}>} agentStates - 現 tick の全 agent 状態
 */
function _updateSocialLinks(agentStates) {
    const selectedId = state.selection.agentId;
    if (selectedId === null || selectedId === undefined) {
        adapter.clearSocialLinks();
        return;
    }

    // 選択中 agent のプロフィールから social_networks を取得
    const profile = state.data.profiles.find(p => p.id === selectedId) || null;
    const friendIds = Array.isArray(profile?.social_networks) ? profile.social_networks : [];

    if (friendIds.length === 0) {
        adapter.clearSocialLinks();
        return;
    }

    // 選択中 agent の現在位置
    const centerState = agentStates.find(s => s.agent_id === selectedId) || null;
    if (!centerState) {
        adapter.clearSocialLinks();
        return;
    }

    // 友達の現在位置を収集 (現 tick にいる友達のみ)
    const friendAgents = [];
    for (const fid of friendIds) {
        const fs = agentStates.find(s => s.agent_id === fid);
        if (fs) friendAgents.push({ id: fid, lat: fs.lat, lon: fs.lon });
    }

    adapter.drawSocialLinks(
        { id: selectedId, lat: centerState.lat, lon: centerState.lon },
        friendAgents,
    );
}

/** イベント配線 */
function wireEvents() {
    if (settingsBtn && settingsPanel) {
        settingsBtn.addEventListener("click", () => {
            const isOpen = !settingsPanel.hidden;
            settingsPanel.hidden = isOpen;
            settingsBtn.setAttribute("aria-expanded", String(!isOpen));
        });
    }

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
        sliderEl.addEventListener("input", async () => {
            const idx = parseInt(sliderEl.value, 10);
            if (!isNaN(idx)) {
                stopPlay();
                state.replay.tickIndex = idx;
                await renderCurrentTick();
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
