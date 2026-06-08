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

import { FallbackMapAdapter }  from "./fallback_map_adapter.js?v=20260606-realflow";
import { GoogleMapsAdapter }   from "./google_maps_adapter.js?v=20260606-realflow";
import {
    updateLegend,
    updateAgentDetail,
    updateLoadStatus,
    updateLivePanel,
    updateMapStatus,
    updateOperatorModePanel,
    updateWorldBridgePanel,
    updateAgentRosterPanel,
    updateMotifArcPanel,
    updateAssessmentLabPanel,
    updateGovernanceFdePanel,
    updateTimeDisplay,
    updateSlider,
    updatePlayButton,
    updateRunSelector,
} from "./ui_panels.js?v=20260606-realflow";

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

const RUN_CREATE_LIMITS = {
    seed: { min: 0, max: 2_147_483_647 },
    ticks: { min: 1, max: 2016 },
    agents: { min: 1, max: 1_000 },
    pois: { min: 3, max: 2_000 },
};

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
        mapPreference: "auto",
        mapsKey:    hasApiKey ? "present" : "absent",
        dataSource: "local",
        mapId:      MAPS_MAP_ID && !MAPS_MAP_ID.startsWith("%%") ? MAPS_MAP_ID : "",
        settings:   null,
    },
    operatorMode: {
        viewpoint: "replay",
        status: "idle",
        runId: "",
        agentId: null,
        triggerClass: "",
        failureState: "",
        message: "replay viewpoint",
    },
    worldBridge: {
        currentLayer: "simulated",
        previousLayer: "",
        status: "ready",
        failureState: "",
        message: "simulated layer",
        availableLayers: [],
        packetReady: false,
        packetCount: 0,
        signalStatus: "planned_signal",
    },
    agentRoster: {
        activeRole: "guide",
        status: "ready",
        failureState: "",
        message: "guide role ready",
        roles: [],
        active: null,
        operatorBoundary: "",
    },
    motifArcs: {
        activeMotifId: "equivalent-exchange-pair",
        status: "ready",
        failureState: "",
        message: "motif arc ready",
        motifs: [],
        active: null,
    },
    assessmentLab: {
        activeCategoryId: "human-ai-assessment-lab",
        status: "ready",
        failureState: "",
        message: "assessment lab ready",
        categories: [],
        active: null,
    },
    governanceFde: {
        activeDecision: "watch",
        status: "ready",
        failureState: "",
        message: "governance FDE ready",
        layers: [],
        fdeSteps: [],
        decisions: [],
        numericProtocol: null,
        oversight: null,
    },
    selection: { agentId: null },
    layerVisible: {
        poi:   false,
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
const createRunBtn  = document.getElementById("btn-create-run");
const createRunStatusEl = document.getElementById("create-run-status");
const newRunIdInput = document.getElementById("new-run-id-input");
const newRunSeedInput = document.getElementById("new-run-seed-input");
const newRunTicksInput = document.getElementById("new-run-ticks-input");
const newRunAgentsInput = document.getElementById("new-run-agents-input");
const newRunPoisInput = document.getElementById("new-run-pois-input");
const runLimitCapacityEl = document.getElementById("run-limit-capacity");
const runLimitPreviewEl = document.getElementById("run-limit-preview");
const runLoadScoreEl = document.getElementById("run-load-score");
const layerPoi      = document.getElementById("layer-poi");
const layerAoi      = document.getElementById("layer-aoi");
const layerRoad     = document.getElementById("layer-road");
const layerAgent    = document.getElementById("layer-agent");
const mapModeSel    = document.getElementById("map-mode-select");
const settingsBtn   = document.getElementById("btn-settings");
const settingsPanel = document.getElementById("settings-panel");
const saveSettingsBtn = document.getElementById("btn-save-settings");
const settingsStatusEl = document.getElementById("settings-status");
const mapsApiKeyInput = document.getElementById("maps-api-key-input");
const mapsMapIdInput = document.getElementById("maps-map-id-input");
const dataDirInput = document.getElementById("data-dir-input");
const llmProviderSel = document.getElementById("llm-provider-select");
const llmModelInput = document.getElementById("llm-model-input");
const llmBaseUrlInput = document.getElementById("llm-base-url-input");
const llmModelDirInput = document.getElementById("llm-model-dir-input");
const googleCloudProjectInput = document.getElementById("google-cloud-project-input");
const operatorViewpointEl = document.getElementById("operator-viewpoint");
const operatorTargetEl = document.getElementById("operator-target");
const operatorStatusEl = document.getElementById("operator-status");
const operatorMessageEl = document.getElementById("operator-message");
const operatorEntryBtn = document.getElementById("btn-operator-entry");
const operatorReturnBtn = document.getElementById("btn-operator-return");
const worldBridgeLayerEl = document.getElementById("world-bridge-layer");
const worldBridgePacketEl = document.getElementById("world-bridge-packet");
const worldBridgeSignalEl = document.getElementById("world-bridge-signal");
const worldBridgeTargetSel = document.getElementById("world-bridge-target-select");
const worldBridgeTransitionBtn = document.getElementById("btn-world-bridge-transition");
const worldBridgeAgentContextInput = document.getElementById("world-bridge-agent-context");
const worldBridgeMessageEl = document.getElementById("world-bridge-message");
const agentRosterActiveEl = document.getElementById("agent-roster-active");
const agentRosterRoleSel = document.getElementById("agent-roster-role-select");
const agentRosterSelectBtn = document.getElementById("btn-agent-roster-select");
const agentRosterLayerEl = document.getElementById("agent-roster-layer");
const agentRosterBoundaryEl = document.getElementById("agent-roster-boundary");
const agentRosterGuidanceEl = document.getElementById("agent-roster-guidance");
const motifArcStatusEl = document.getElementById("motif-arc-status");
const motifArcSelectEl = document.getElementById("motif-arc-select");
const motifArcEvaluateBtn = document.getElementById("btn-motif-arc-evaluate");
const motifArcArchetypeEl = document.getElementById("motif-arc-archetype");
const motifArcWorldEl = document.getElementById("motif-arc-world");
const motifArcCoreEl = document.getElementById("motif-arc-core");
const assessmentLabStatusEl = document.getElementById("assessment-lab-status");
const assessmentLabSelectEl = document.getElementById("assessment-lab-select");
const assessmentLabEvaluateBtn = document.getElementById("btn-assessment-lab-evaluate");
const assessmentLabInputEl = document.getElementById("assessment-lab-input");
const assessmentLabOutputEl = document.getElementById("assessment-lab-output");
const assessmentLabFailEl = document.getElementById("assessment-lab-fail");
const governanceFdeStatusEl = document.getElementById("governance-fde-status");
const governanceFdeDecisionSel = document.getElementById("governance-fde-decision-select");
const governanceFdeDecideBtn = document.getElementById("btn-governance-fde-decide");
const governanceFdeOversightEl = document.getElementById("governance-fde-oversight");
const governanceFdeStepsEl = document.getElementById("governance-fde-steps");
const governanceFdeNumericEl = document.getElementById("governance-fde-numeric");

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

const operatorEls = {
    viewpoint: operatorViewpointEl,
    target: operatorTargetEl,
    status: operatorStatusEl,
    message: operatorMessageEl,
    entryButton: operatorEntryBtn,
    returnButton: operatorReturnBtn,
};

const worldBridgeEls = {
    layer: worldBridgeLayerEl,
    packet: worldBridgePacketEl,
    signal: worldBridgeSignalEl,
    targetSelect: worldBridgeTargetSel,
    transitionButton: worldBridgeTransitionBtn,
    agentContextInput: worldBridgeAgentContextInput,
    message: worldBridgeMessageEl,
};

const agentRosterEls = {
    active: agentRosterActiveEl,
    roleSelect: agentRosterRoleSel,
    selectButton: agentRosterSelectBtn,
    layer: agentRosterLayerEl,
    boundary: agentRosterBoundaryEl,
    guidance: agentRosterGuidanceEl,
};

const motifArcEls = {
    status: motifArcStatusEl,
    select: motifArcSelectEl,
    evaluateButton: motifArcEvaluateBtn,
    archetype: motifArcArchetypeEl,
    world: motifArcWorldEl,
    core: motifArcCoreEl,
};

const assessmentLabEls = {
    status: assessmentLabStatusEl,
    select: assessmentLabSelectEl,
    evaluateButton: assessmentLabEvaluateBtn,
    input: assessmentLabInputEl,
    output: assessmentLabOutputEl,
    fail: assessmentLabFailEl,
};

const governanceFdeEls = {
    status: governanceFdeStatusEl,
    select: governanceFdeDecisionSel,
    decideButton: governanceFdeDecideBtn,
    oversight: governanceFdeOversightEl,
    fde: governanceFdeStepsEl,
    numeric: governanceFdeNumericEl,
};

// ─────────────────────────────────────────────────────────────────────────────
// 初期化
// ─────────────────────────────────────────────────────────────────────────────

async function initAdapter() {
    const desiredMode = _resolveDesiredMapMode();
    if (desiredMode === "google" && hasApiKey) {
        try {
            if (mapCanvas) mapCanvas.style.display = "none";
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
    await refreshSettingsStatus();
    await refreshHealthStatus();
    await refreshOperatorMode();
    await refreshWorldBridge();
    await refreshAgentRoster();
    await refreshMotifArcs();
    await refreshAssessmentLab();
    await refreshGovernanceFde();
    _updateRunLimitsDisplay();

    // run 一覧を取得して selector に反映
    const runs = await fetchRuns();
    updateRunSelector(runSel, runs);
    _setDefaultNewRunId(runs);

    // イベント配線
    wireEvents();

    // 最初の run を自動ロード (ある場合)
    if (runs && runs.length > 0) {
        await loadRun(runs[0].run_id);
    }
}

function _setDefaultNewRunId(runs) {
    if (!newRunIdInput) return;
    const existing = new Set((runs || []).map((run) => run.run_id));
    if (newRunIdInput.value && !existing.has(newRunIdInput.value)) return;
    const stamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 12);
    newRunIdInput.value = `ui_demo_${stamp}`;
}

function _resolveDesiredMapMode() {
    if (state.runtime.mapPreference === "fallback") return "fallback";
    if (state.runtime.mapPreference === "google") return "google";
    return hasApiKey ? "google" : "fallback";
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

async function refreshOperatorMode() {
    try {
        const res = await fetch(`${API_BASE}/api/operator-mode`);
        if (!res.ok) return;
        const json = await res.json();
        _setOperatorModeState(json);
    } catch {
        updateOperatorRuntimePanel();
    }
}

async function refreshWorldBridge() {
    try {
        const res = await fetch(`${API_BASE}/api/world-bridge`);
        if (!res.ok) return;
        const json = await res.json();
        _setWorldBridgeState(json);
    } catch {
        updateWorldBridgeRuntimePanel();
    }
}

async function refreshAgentRoster() {
    try {
        const res = await fetch(`${API_BASE}/api/agent-roster`);
        if (!res.ok) return;
        const json = await res.json();
        _setAgentRosterState(json);
    } catch {
        updateAgentRosterRuntimePanel();
    }
}

async function refreshMotifArcs() {
    try {
        const res = await fetch(`${API_BASE}/api/motif-arcs`);
        if (!res.ok) return;
        const json = await res.json();
        _setMotifArcState(json);
    } catch {
        updateMotifArcRuntimePanel();
    }
}

async function refreshAssessmentLab() {
    try {
        const res = await fetch(`${API_BASE}/api/assessment-lab`);
        if (!res.ok) return;
        const json = await res.json();
        _setAssessmentLabState(json);
    } catch {
        updateAssessmentLabRuntimePanel();
    }
}

async function refreshGovernanceFde() {
    try {
        const res = await fetch(`${API_BASE}/api/governance-fde`);
        if (!res.ok) return;
        const json = await res.json();
        _setGovernanceFdeState(json);
    } catch {
        updateGovernanceFdeRuntimePanel();
    }
}

/** /api/settings を取得し、設定パネルに反映する。 */
async function refreshSettingsStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/settings`);
        if (!res.ok) return;
        const json = await res.json();
        state.runtime.settings = json;
        state.runtime.mapsKey = json.maps?.api_key || state.runtime.mapsKey;
        state.runtime.mapId = json.maps?.map_id || "";
        state.runtime.dataSource = json.data?.source || state.runtime.dataSource;
        _populateSettingsForm(json);
        updateMapRuntimeStatus();
    } catch (error) {
        console.warn("settings の読み込みに失敗しました", error);
    }
}

function _populateSettingsForm(settings) {
    if (!settings) return;
    if (mapsApiKeyInput) mapsApiKeyInput.value = "";
    if (mapsMapIdInput) mapsMapIdInput.value = settings.maps?.map_id || "";
    if (dataDirInput) dataDirInput.value = settings.data?.root || "";
    if (llmProviderSel) llmProviderSel.value = settings.llm?.provider || "rule";
    if (llmModelInput) llmModelInput.value = settings.llm?.model || "";
    if (llmBaseUrlInput) llmBaseUrlInput.value = settings.llm?.base_url || "";
    if (llmModelDirInput) llmModelDirInput.value = settings.llm?.model_dir || "";
    if (googleCloudProjectInput) {
        googleCloudProjectInput.value = settings.cloud?.google_cloud_project || "";
    }
}

async function saveSettings() {
    if (settingsStatusEl) {
        settingsStatusEl.className = "settings-status";
        settingsStatusEl.textContent = "反映中...";
    }
    const payload = {
        maps: {
            map_id: mapsMapIdInput?.value || "",
        },
        data: {
            source: "local",
            root: dataDirInput?.value || "",
        },
        llm: {
            provider: llmProviderSel?.value || "rule",
            model: llmModelInput?.value || "",
            base_url: llmBaseUrlInput?.value || "",
            model_dir: llmModelDirInput?.value || "",
        },
        cloud: {
            google_cloud_project: googleCloudProjectInput?.value || "",
        },
    };
    const apiKeyValue = mapsApiKeyInput?.value || "";
    if (apiKeyValue) {
        payload.maps.api_key = apiKeyValue;
    }

    try {
        const res = await fetch(`${API_BASE}/api/settings`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(payload),
        });
        const json = await res.json();
        if (!res.ok) {
            throw new Error(json.detail || "settings update failed");
        }
        state.runtime.settings = json;
        state.runtime.mapsKey = json.maps?.api_key || state.runtime.mapsKey;
        state.runtime.mapId = json.maps?.map_id || "";
        state.runtime.dataSource = json.data?.source || state.runtime.dataSource;
        _populateSettingsForm(json);
        updateMapRuntimeStatus();
        const needsReload = apiKeyValue || Boolean(mapsMapIdInput?.value);
        if (settingsStatusEl) {
            settingsStatusEl.className = "settings-status settings-status--ok";
            settingsStatusEl.textContent = needsReload
                ? "反映しました。地図キー変更は再読み込みで有効になります。"
                : "反映しました。";
        }
        if (needsReload) {
            window.setTimeout(() => window.location.reload(), 700);
            return;
        }
        const runs = await fetchRuns();
        updateRunSelector(runSel, runs);
        if (runs && runs.length > 0) {
            await loadRun(runs[0].run_id);
        }
    } catch (error) {
        if (settingsStatusEl) {
            settingsStatusEl.className = "settings-status settings-status--error";
            settingsStatusEl.textContent = String(error.message || error);
        }
    }
}

function _readIntegerInput(inputEl, fallback) {
    const value = parseInt(inputEl?.value || "", 10);
    return Number.isInteger(value) ? value : fallback;
}

function _readIntegerInputState(inputEl, fallback, label) {
    const raw = inputEl?.value;
    const parsed = parseInt(raw, 10);
    if (raw === undefined || raw === null || String(raw).trim() === "") {
        return {
            value: fallback,
            valid: false,
            issue: `${label}は空欄です`,
        };
    }
    if (!Number.isInteger(parsed)) {
        return {
            value: fallback,
            valid: false,
            issue: `${label}は整数で入力してください`,
        };
    }
    return { value: parsed, valid: true, issue: "" };
}

function _formatRunLoadScore({ ticks, agents, pois }) {
    if (ticks <= 0 || agents <= 0 || pois <= 0) return "—";
    const normalized = [
        ticks / RUN_CREATE_LIMITS.ticks.max,
        agents / RUN_CREATE_LIMITS.agents.max,
        pois / RUN_CREATE_LIMITS.pois.max,
    ];
    const avgRatio = (normalized[0] + normalized[1] + normalized[2]) / normalized.length;
    const pct = Math.round(avgRatio * 100);
    if (pct >= 90) return `高負荷（${pct}%）`;
    if (pct >= 60) return `やや重め（${pct}%）`;
    return `軽量（${pct}%）`;
}

function _runPayloadFromInputs() {
    const seed = _readIntegerInputState(newRunSeedInput, 42, "seed");
    const ticks = _readIntegerInputState(newRunTicksInput, 288, "ticks");
    const agents = _readIntegerInputState(newRunAgentsInput, 100, "agents");
    const pois = _readIntegerInputState(newRunPoisInput, 300, "pois");

    const runId = (newRunIdInput?.value || "").trim();
    const issues = [];
    if (!runId) issues.push("Run ID は必須です");

    if (!seed.valid && seed.issue) issues.push(seed.issue);
    if (!ticks.valid && ticks.issue) issues.push(ticks.issue);
    if (!agents.valid && agents.issue) issues.push(agents.issue);
    if (!pois.valid && pois.issue) issues.push(pois.issue);

    const rangeChecks = [
        {
            label: "seed",
            value: seed.value,
            valid: seed.value >= RUN_CREATE_LIMITS.seed.min && seed.value <= RUN_CREATE_LIMITS.seed.max,
            issue: `seed は ${RUN_CREATE_LIMITS.seed.min}〜${RUN_CREATE_LIMITS.seed.max} で指定してください`,
        },
        {
            label: "ticks",
            value: ticks.value,
            valid: ticks.value >= RUN_CREATE_LIMITS.ticks.min && ticks.value <= RUN_CREATE_LIMITS.ticks.max,
            issue: `ticks は ${RUN_CREATE_LIMITS.ticks.min}〜${RUN_CREATE_LIMITS.ticks.max} で指定してください`,
        },
        {
            label: "agents",
            value: agents.value,
            valid: agents.value >= RUN_CREATE_LIMITS.agents.min && agents.value <= RUN_CREATE_LIMITS.agents.max,
            issue: `agents は ${RUN_CREATE_LIMITS.agents.min}〜${RUN_CREATE_LIMITS.agents.max} で指定してください`,
        },
        {
            label: "pois",
            value: pois.value,
            valid: pois.value >= RUN_CREATE_LIMITS.pois.min && pois.value <= RUN_CREATE_LIMITS.pois.max,
            issue: `pois は ${RUN_CREATE_LIMITS.pois.min}〜${RUN_CREATE_LIMITS.pois.max} で指定してください`,
        },
    ];

    for (const check of rangeChecks) {
        if (!check.valid) issues.push(check.issue);
    }

    const uniqueIssues = [...new Set(issues)];
    return {
        runId,
        seedValue: seed.value,
        ticksValue: ticks.value,
        agentsValue: agents.value,
        poisValue: pois.value,
        payload: {
            mode: "sample",
            run_id: runId,
            seed: seed.value,
            ticks: ticks.value,
            agents: agents.value,
            pois: pois.value,
        },
        valid: uniqueIssues.length === 0,
        issues: uniqueIssues,
        issueText: uniqueIssues.join(" / "),
        loadScoreText: _formatRunLoadScore({
            ticks: ticks.value,
            agents: agents.value,
            pois: pois.value,
        }),
    };
}

function _updateRunLimitsDisplay() {
    if (runLimitCapacityEl) {
        runLimitCapacityEl.textContent = `ticks ${RUN_CREATE_LIMITS.ticks.min}〜${RUN_CREATE_LIMITS.ticks.max}, agents ${RUN_CREATE_LIMITS.agents.min}〜${RUN_CREATE_LIMITS.agents.max}, pois ${RUN_CREATE_LIMITS.pois.min}〜${RUN_CREATE_LIMITS.pois.max}`;
    }
    const state = _runPayloadFromInputs();
    if (runLimitPreviewEl) {
        runLimitPreviewEl.textContent = `ticks ${state.ticksValue} / ${RUN_CREATE_LIMITS.ticks.max}, agents ${state.agentsValue} / ${RUN_CREATE_LIMITS.agents.max}, pois ${state.poisValue} / ${RUN_CREATE_LIMITS.pois.max}`;
        runLimitPreviewEl.classList.remove("status-pill--ok", "status-pill--warning", "status-pill--muted");
        if (state.valid) {
            runLimitPreviewEl.classList.add("status-pill--ok");
        } else {
            runLimitPreviewEl.classList.add("status-pill--warning");
        }
        runLimitPreviewEl.title = state.issueText || "入力値は上限内です";
    }
    if (runLoadScoreEl) {
        runLoadScoreEl.textContent = state.loadScoreText;
        runLoadScoreEl.classList.remove("status-pill--ok", "status-pill--warning", "status-pill--muted");
        const scoreText = state.loadScoreText;
        if (scoreText.startsWith("高負荷")) {
            runLoadScoreEl.classList.add("status-pill--warning");
        } else if (scoreText.startsWith("やや重め")) {
            runLoadScoreEl.classList.add("status-pill--warning");
        } else {
            runLoadScoreEl.classList.add("status-pill--ok");
        }
    }
}

async function createRunFromForm() {
    if (!createRunBtn) return;

    const state = _runPayloadFromInputs();
    if (!state.valid) {
        _setCreateRunStatus(state.issueText || "入力に問題があります。", true);
        return;
    }
    const payload = state.payload;
    createRunBtn.disabled = true;
    _setCreateRunStatus("生成中...");
    try {
        const res = await fetch(`${API_BASE}/api/runs`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(payload),
        });
        const json = await res.json();
        if (!res.ok) {
            throw new Error(json.detail || "run creation failed");
        }
        const runs = await fetchRuns();
        updateRunSelector(runSel, runs);
        const createdRunId = json.run?.run_id || state.runId;
        if (runSel) runSel.value = createdRunId;
        _setDefaultNewRunId(runs);
        _setCreateRunStatus("生成しました。", false);
        await loadRun(createdRunId);
    } catch (error) {
        _setCreateRunStatus(String(error.message || error), true);
    } finally {
        createRunBtn.disabled = false;
    }
}

function _setCreateRunStatus(message, isError = false) {
    if (!createRunStatusEl) return;
    createRunStatusEl.className = isError
        ? "settings-status settings-status--error"
        : "settings-status settings-status--ok";
    createRunStatusEl.textContent = message;
}

/**
 * run のデータファイルを取得する。
 * @param {string} runId
 * @param {string} file
 * @returns {Promise<Object|string|null>}
 */
async function fetchRunFile(runId, file) {
    try {
        const res = await fetch(`${API_BASE}/api/data/${encodeURIComponent(runId)}/${file}`);
        if (!res.ok) return null;
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("x-ndjson") || ct.includes("jsonl")) {
            // JSONL: テキストを行分割して JSON パース
            const text = await res.text();
            return text.trim().split("\n").filter(Boolean).map(l => JSON.parse(l));
        }
        return res.json();
    } catch (error) {
        console.warn(`run file の読み込みに失敗しました: ${file}`, error);
        return null;
    }
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
    await returnOperatorMode(false);

    const summaryData = await fetchRunFile(runId, "summary.json");
    const profileCount = Number.isInteger(summaryData?.agents) && summaryData.agents > 0
        ? summaryData.agents
        : 100;
    const profilesFile = `agent_profiles_N${profileCount}.json`;
    let profilesFileLoaded = profilesFile;
    let profilesFileFallbackUsed = false;

    // 並列ロード (poi_visit_records.jsonl は任意 / §5.2)
    let [poisData, aoisData, roadsData, profilesData, statesRaw, visitRecordsRaw] = await Promise.all([
        fetchRunFile(runId, "pois.geojson"),
        fetchRunFile(runId, "aois.geojson"),
        fetchRunFile(runId, "roadnet.geojson"),
        fetchRunFile(runId, profilesFile),
        fetchRunFile(runId, "agent_states.jsonl"),
        fetchRunFile(runId, "poi_visit_records.jsonl"),
    ]);
    if (!Array.isArray(profilesData) && profilesFile !== "agent_profiles_N100.json") {
        const fallbackProfilesData = await fetchRunFile(runId, "agent_profiles_N100.json");
        if (Array.isArray(fallbackProfilesData)) {
            profilesData = fallbackProfilesData;
            profilesFileLoaded = "agent_profiles_N100.json";
            profilesFileFallbackUsed = true;
        }
    }

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
            file:   profilesFileFallbackUsed ? `${profilesFileLoaded} (fallback)` : profilesFileLoaded,
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
    updateOperatorRuntimePanel();
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
    const nextTick = tickIndex < ticks.length - 1 ? ticks[tickIndex + 1] : null;
    const nextStateMap = new Map();
    if (nextTick !== null) {
        for (const s of statesByTick.get(nextTick) || []) {
            nextStateMap.set(s.agent_id, s);
        }
    }

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
        const next = nextStateMap.get(s.agent_id);
        return {
            id:  s.agent_id,
            lat: s.lat,
            lon: s.lon,
            action: s.action,
            status: s.status,
            role:   profile?.role || "other",
            label,
            moving: _isMovingAction(s.action),
            nextLat: next?.lat,
            nextLon: next?.lon,
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
    updateOperatorRuntimePanel();
}

function _setOperatorModeState(json) {
    state.operatorMode = {
        viewpoint: json.viewpoint || "replay",
        status: json.status || "idle",
        runId: json.run_id || "",
        agentId: json.agent_id ?? null,
        triggerClass: json.trigger_class || "",
        failureState: json.failure_state || "",
        message: json.message || "replay viewpoint",
    };
    updateOperatorRuntimePanel();
}

function updateOperatorRuntimePanel() {
    updateOperatorModePanel(operatorEls, {
        viewpoint: state.operatorMode.viewpoint,
        status: state.operatorMode.status,
        agentId: state.operatorMode.agentId,
        selectedAgentId: state.selection.agentId,
        failureState: state.operatorMode.failureState,
        message: state.operatorMode.message,
    });
}

function _setWorldBridgeState(json) {
    const fields = json.minimum_world_packet?.fields || {};
    const readyCount = Object.values(fields).filter((field) => field && field.ready).length;
    state.worldBridge = {
        currentLayer: json.current_layer || "simulated",
        previousLayer: json.previous_layer || "",
        status: json.status || "ready",
        failureState: json.failure_state || "",
        message: json.message || "simulated layer",
        availableLayers: Array.isArray(json.available_layers) ? json.available_layers : [],
        packetReady: Boolean(json.minimum_world_packet?.ready),
        packetCount: readyCount,
        signalStatus: json.event_music_signal?.status || "planned_signal",
    };
    updateWorldBridgeRuntimePanel();
}

function updateWorldBridgeRuntimePanel() {
    updateWorldBridgePanel(worldBridgeEls, state.worldBridge);
}

function _setAgentRosterState(json) {
    state.agentRoster = {
        activeRole: json.active_role || "guide",
        status: json.status || "ready",
        failureState: json.failure_state || "",
        message: json.message || "guide role ready",
        roles: Array.isArray(json.roles) ? json.roles : [],
        active: json.active || null,
        operatorBoundary: json.operator_boundary || "",
    };
    updateAgentRosterRuntimePanel();
}

function updateAgentRosterRuntimePanel() {
    updateAgentRosterPanel(agentRosterEls, state.agentRoster);
}

function _setMotifArcState(json) {
    state.motifArcs = {
        activeMotifId: json.active_motif_id || "equivalent-exchange-pair",
        status: json.status || "ready",
        failureState: json.failure_state || "",
        message: json.message || "motif arc ready",
        motifs: Array.isArray(json.motifs) ? json.motifs : [],
        active: json.active || null,
    };
    updateMotifArcRuntimePanel();
}

function updateMotifArcRuntimePanel() {
    updateMotifArcPanel(motifArcEls, state.motifArcs);
}

function _setAssessmentLabState(json) {
    state.assessmentLab = {
        activeCategoryId: json.active_category_id || "human-ai-assessment-lab",
        status: json.status || "ready",
        failureState: json.failure_state || "",
        message: json.message || "assessment lab ready",
        categories: Array.isArray(json.categories) ? json.categories : [],
        active: json.active || null,
    };
    updateAssessmentLabRuntimePanel();
}

function updateAssessmentLabRuntimePanel() {
    updateAssessmentLabPanel(assessmentLabEls, state.assessmentLab);
}

function _setGovernanceFdeState(json) {
    state.governanceFde = {
        activeDecision: json.active_decision || "watch",
        status: json.status || "ready",
        failureState: json.failure_state || "",
        message: json.message || "governance FDE ready",
        layers: Array.isArray(json.layers) ? json.layers : [],
        fdeSteps: Array.isArray(json.fde_steps) ? json.fde_steps : [],
        decisions: Array.isArray(json.decisions) ? json.decisions : [],
        numericProtocol: json.numeric_protocol || null,
        oversight: json.oversight || null,
    };
    updateGovernanceFdeRuntimePanel();
}

function updateGovernanceFdeRuntimePanel() {
    updateGovernanceFdePanel(governanceFdeEls, state.governanceFde);
}

async function enterOperatorMode() {
    const agentId = state.selection.agentId;
    if (agentId === null || agentId === undefined) {
        state.operatorMode.message = "先にエージェントを選択してください。";
        state.operatorMode.failureState = "target_not_found";
        updateOperatorRuntimePanel();
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/operator-mode/entry`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
                run_id: state.runtime.runId,
                agent_id: agentId,
                trigger_class: "entry_intent",
            }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setOperatorModeState(detail.operator_mode || {
                viewpoint: "replay",
                status: "blocked",
                failure_state: detail.failure_state || "entry_not_allowed",
                message: detail.message || "entry failed",
            });
            return;
        }
        _setOperatorModeState(json);
    } catch (error) {
        state.operatorMode = {
            viewpoint: "replay",
            status: "blocked",
            runId: "",
            agentId: null,
            triggerClass: "",
            failureState: "entry_not_allowed",
            message: String(error.message || error),
        };
        updateOperatorRuntimePanel();
    }
}

async function returnOperatorMode(updatePanel = true) {
    try {
        const res = await fetch(`${API_BASE}/api/operator-mode/return`, { method: "POST" });
        if (!res.ok) return;
        const json = await res.json();
        _setOperatorModeState(json);
    } catch {
        if (updatePanel) updateOperatorRuntimePanel();
    }
}

async function transitionWorldBridge() {
    const targetLayer = worldBridgeTargetSel?.value || "simulated";
    const requiresAgentContext = Boolean(worldBridgeAgentContextInput?.checked);
    try {
        const res = await fetch(`${API_BASE}/api/world-bridge/transition`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
                target_layer: targetLayer,
                reason_class: "operator_intent",
                requires_agent_context: requiresAgentContext,
            }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setWorldBridgeState(detail.world_bridge || {
                current_layer: state.worldBridge.currentLayer,
                status: "blocked",
                failure_state: detail.failure_state || "transition_not_allowed",
                message: detail.message || "transition failed",
            });
            return;
        }
        _setWorldBridgeState(json);
    } catch (error) {
        state.worldBridge = {
            ...state.worldBridge,
            status: "blocked",
            failureState: "transition_not_allowed",
            message: String(error.message || error),
        };
        updateWorldBridgeRuntimePanel();
    }
}

async function selectAgentRosterRole() {
    const roleId = agentRosterRoleSel?.value || "guide";
    try {
        const res = await fetch(`${API_BASE}/api/agent-roster/select`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ role_id: roleId }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setAgentRosterState(detail.agent_roster || {
                active_role: state.agentRoster.activeRole,
                status: "blocked",
                failure_state: detail.failure_state || "role_not_found",
                message: detail.message || "role selection failed",
            });
            return;
        }
        _setAgentRosterState(json);
    } catch (error) {
        state.agentRoster = {
            ...state.agentRoster,
            status: "blocked",
            failureState: "role_not_found",
            message: String(error.message || error),
        };
        updateAgentRosterRuntimePanel();
    }
}

async function evaluateMotifArc() {
    const motifId = motifArcSelectEl?.value || "equivalent-exchange-pair";
    try {
        const res = await fetch(`${API_BASE}/api/motif-arcs/evaluate`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ motif_id: motifId }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setMotifArcState(detail.motif_arcs || {
                active_motif_id: state.motifArcs.activeMotifId,
                status: "blocked",
                failure_state: detail.failure_state || "motif_name_not_safe",
                message: detail.message || "motif evaluation failed",
            });
            return;
        }
        _setMotifArcState(json);
    } catch (error) {
        state.motifArcs = {
            ...state.motifArcs,
            status: "blocked",
            failureState: "motif_name_not_safe",
            message: String(error.message || error),
        };
        updateMotifArcRuntimePanel();
    }
}

async function evaluateAssessmentLab() {
    const categoryId = assessmentLabSelectEl?.value || "human-ai-assessment-lab";
    try {
        const res = await fetch(`${API_BASE}/api/assessment-lab/evaluate`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ category_id: categoryId }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setAssessmentLabState(detail.assessment_lab || {
                active_category_id: state.assessmentLab.activeCategoryId,
                status: "blocked",
                failure_state: detail.failure_state || "scenario_unbounded",
                message: detail.message || "assessment evaluation failed",
            });
            return;
        }
        _setAssessmentLabState(json);
    } catch (error) {
        state.assessmentLab = {
            ...state.assessmentLab,
            status: "blocked",
            failureState: "scenario_unbounded",
            message: String(error.message || error),
        };
        updateAssessmentLabRuntimePanel();
    }
}

async function decideGovernanceFde() {
    const decision = governanceFdeDecisionSel?.value || "watch";
    try {
        const res = await fetch(`${API_BASE}/api/governance-fde/decide`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
                decision,
                human_gate: true,
                evidence: ["local-tests", "static-scan", "human-review-surface"],
            }),
        });
        const json = await res.json();
        if (!res.ok) {
            const detail = json.detail || {};
            _setGovernanceFdeState(detail.governance_fde || {
                active_decision: state.governanceFde.activeDecision,
                status: "blocked",
                failure_state: detail.failure_state || "packet_missing_evidence",
                message: detail.message || "FDE decision failed",
            });
            return;
        }
        _setGovernanceFdeState(json);
    } catch (error) {
        state.governanceFde = {
            ...state.governanceFde,
            status: "blocked",
            failureState: "packet_missing_evidence",
            message: String(error.message || error),
        };
        updateGovernanceFdeRuntimePanel();
    }
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
            moving: _isMovingAction(s.action),
            nextLat: next?.lat,
            nextLon: next?.lon,
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

function _isMovingAction(action) {
    return action === "move" || action === "walking" || action === "commute";
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
    updateOperatorRuntimePanel();
}

function updateMapRuntimeStatus() {
    updateMapStatus(mapStatusEls, {
        mode:       state.runtime.mapMode,
        preference: state.runtime.mapPreference,
        mapsKey:    state.runtime.mapsKey,
        dataSource: state.runtime.dataSource,
        mapId:      state.runtime.mapId,
    });
}

async function switchMapMode(preference) {
    stopPlay();
    state.runtime.mapPreference = preference === "google" || preference === "fallback"
        ? preference
        : "auto";
    if (mapModeSel) mapModeSel.value = state.runtime.mapPreference;

    const desiredMode = _resolveDesiredMapMode();
    if (desiredMode === "google" && !hasApiKey) {
        state.runtime.mapMode = "Fallback";
        updateMapRuntimeStatus();
        if (settingsStatusEl) {
            settingsStatusEl.className = "settings-status settings-status--error";
            settingsStatusEl.textContent = "Google Maps は API key 設定後の再読み込みで使えます。";
        }
        return;
    }

    await initAdapter();
    await _reapplyCurrentRunLayers();
    await renderCurrentTick();
}

async function _reapplyCurrentRunLayers() {
    const runId = state.runtime.runId;
    if (!runId) return;
    const [poisData, aoisData, roadsData] = await Promise.all([
        fetchRunFile(runId, "pois.geojson"),
        fetchRunFile(runId, "aois.geojson"),
        fetchRunFile(runId, "roadnet.geojson"),
    ]);
    if (poisData) adapter.setLayer("poi", state.layerVisible.poi, poisData);
    if (aoisData) adapter.setLayer("aoi", state.layerVisible.aoi, aoisData);
    if (roadsData) adapter.setLayer("road", state.layerVisible.road, roadsData);
    if (adapter instanceof FallbackMapAdapter) {
        adapter._recomputeBounds();
    }
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
 * slider から来た tickIndex を現在の replay 範囲内に丸める。
 * @param {number} idx
 * @returns {number}
 */
function _clampTickIndex(idx) {
    const maxIndex = Math.max(0, state.replay.ticks.length - 1);
    return Math.max(0, Math.min(maxIndex, idx));
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
    if (mapModeSel) {
        mapModeSel.value = state.runtime.mapPreference;
        mapModeSel.addEventListener("change", async () => {
            await switchMapMode(mapModeSel.value);
        });
    }
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener("click", async () => {
            await saveSettings();
        });
    }
    if (createRunBtn) {
        createRunBtn.addEventListener("click", async () => {
            await createRunFromForm();
        });
    }
    if (operatorEntryBtn) {
        operatorEntryBtn.addEventListener("click", async () => {
            await enterOperatorMode();
        });
    }
    if (operatorReturnBtn) {
        operatorReturnBtn.addEventListener("click", async () => {
            await returnOperatorMode();
        });
    }
    if (worldBridgeTransitionBtn) {
        worldBridgeTransitionBtn.addEventListener("click", async () => {
            await transitionWorldBridge();
        });
    }
    if (agentRosterSelectBtn) {
        agentRosterSelectBtn.addEventListener("click", async () => {
            await selectAgentRosterRole();
        });
    }
    if (motifArcEvaluateBtn) {
        motifArcEvaluateBtn.addEventListener("click", async () => {
            await evaluateMotifArc();
        });
    }
    if (assessmentLabEvaluateBtn) {
        assessmentLabEvaluateBtn.addEventListener("click", async () => {
            await evaluateAssessmentLab();
        });
    }
    if (governanceFdeDecideBtn) {
        governanceFdeDecideBtn.addEventListener("click", async () => {
            await decideGovernanceFde();
        });
    }
    for (const inputEl of [newRunTicksInput, newRunAgentsInput, newRunPoisInput, newRunSeedInput]) {
        if (!inputEl) continue;
        inputEl.addEventListener("input", _updateRunLimitsDisplay);
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
                state.replay.tickIndex = _clampTickIndex(idx);
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
