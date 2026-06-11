/**
 * ui_panels.js — 凡例 / エージェント詳細 / 時刻コントロールの DOM 生成と更新。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.2 / §5.3 / §5.4
 *
 * - 凡例: POI カテゴリ別件数 / 総 POI・AOI・agent 数
 * - エージェント詳細: ID / 名前 / 年齢 / 性別 / description / 現在時刻 / 位置 / POI / action / social network ids
 * - 時刻コントロール: 再生/停止 / ステップ / 速度 / スライダー / 時刻表示
 *
 * このモジュールは DOM 操作専用。状態は app.js の ViewerState が保持する。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

import { CATEGORY_COLORS } from "./colors.js";
import {
    CATEGORY_LABELS,
    ROLE_LABELS,
    INTERACTION_TYPE_LABELS,
    ACTION_LABELS,
    getLabel,
} from "./labels.js";

// ──────────────────────────────────────────────────────────────────────────────
// マップ状態 / ライブパネル
// ───────────────────────────────────────────────────────────────────────────

/**
 * 左パネルの地図状態と設定表示を更新する。
 * @param {Object} els
 * @param {{ mode:string, mapsKey:string, dataSource:string, mapId:string }} info
 */
export function updateMapStatus(els, info) {
    if (!els) return;

    const usingGoogleMaps = info.mode === "Google Maps";
    const mapsKeyPresent = info.mapsKey === "present";

    if (els.modeValue) {
        els.modeValue.textContent = info.mode || "Fallback";
        els.modeValue.classList.toggle("status-pill--ok", usingGoogleMaps);
        els.modeValue.classList.toggle("status-pill--warning", !usingGoogleMaps);
        els.modeValue.classList.toggle("status-pill--muted", false);
    }
    if (els.mapsKeyValue) {
        els.mapsKeyValue.textContent = mapsKeyPresent ? "設定済み" : "未設定";
    }
    if (els.mapHealthValue) {
        els.mapHealthValue.textContent = usingGoogleMaps
            ? "Google Maps"
            : "Fallback表示";
    }
    if (els.dataSourceValue) {
        els.dataSourceValue.textContent = info.dataSource || "local";
    }
    if (els.mapIdValue) {
        els.mapIdValue.textContent = info.mapId || "未設定";
    }
    if (els.googleMapsConfigValue) {
        els.googleMapsConfigValue.textContent = mapsKeyPresent ? "接続可能" : "未接続";
    }
}

/**
 * MVP-001 Operator panel を更新する。
 * @param {Object} els
 * @param {{ viewpoint:string, status:string, agentId:number|null, selectedAgentId:number|null, message:string, failureState:string }} snapshot
 */
export function updateOperatorModePanel(els, snapshot) {
    if (!els) return;
    const viewpoint = snapshot.viewpoint || "replay";
    const active = viewpoint === "inspection";
    if (els.viewpoint) {
        els.viewpoint.textContent = viewpoint;
        els.viewpoint.classList.toggle("status-pill--ok", active);
        els.viewpoint.classList.toggle("status-pill--muted", !active);
        els.viewpoint.classList.toggle("status-pill--warning", Boolean(snapshot.failureState));
    }
    if (els.target) {
        const target = snapshot.agentId ?? snapshot.selectedAgentId;
        els.target.textContent = target == null ? "未選択" : `Agent ${target}`;
    }
    if (els.status) {
        els.status.textContent = snapshot.status || "idle";
    }
    if (els.message) {
        els.message.className = snapshot.failureState
            ? "settings-status settings-status--error"
            : "settings-status";
        els.message.textContent = snapshot.message || "replay viewpoint";
    }
    if (els.entryButton) {
        els.entryButton.disabled = snapshot.selectedAgentId == null || active;
    }
    if (els.returnButton) {
        els.returnButton.disabled = !active;
    }
}

/**
 * MVP-002 World Bridge panel を更新する。
 * @param {Object} els
 * @param {{ currentLayer:string, status:string, failureState:string, message:string, packetReady:boolean, packetCount:number, signalStatus:string, availableLayers?:Object[] }} snapshot
 */
export function updateWorldBridgePanel(els, snapshot) {
    if (!els) return;
    const layer = snapshot.currentLayer || "simulated";
    const blocked = Boolean(snapshot.failureState);
    const isLiminal = layer === "liminal";
    if (els.layer) {
        els.layer.textContent = layer;
        els.layer.classList.toggle("status-pill--ok", !blocked && !isLiminal);
        els.layer.classList.toggle("status-pill--warning", blocked || isLiminal);
        els.layer.classList.toggle("status-pill--muted", false);
    }
    if (els.packet) {
        const count = Number.isFinite(snapshot.packetCount) ? snapshot.packetCount : 0;
        els.packet.textContent = snapshot.packetReady ? `${count}/7 ready` : `${count}/7 missing`;
    }
    if (els.signal) {
        els.signal.textContent = snapshot.signalStatus || "planned_signal";
    }
    if (els.targetSelect && Array.isArray(snapshot.availableLayers) && snapshot.availableLayers.length > 0) {
        const currentValue = els.targetSelect.value || layer;
        els.targetSelect.innerHTML = "";
        for (const item of snapshot.availableLayers) {
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = item.id;
            els.targetSelect.appendChild(option);
        }
        els.targetSelect.value = snapshot.availableLayers.some((item) => item.id === currentValue)
            ? currentValue
            : layer;
    }
    if (els.message) {
        els.message.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.message.textContent = snapshot.message || "world bridge ready";
    }
    if (els.transitionButton) {
        els.transitionButton.disabled = !snapshot.packetReady;
    }
}

/**
 * MVP-003 Role Roster panel を更新する。
 * @param {Object} els
 * @param {{ activeRole:string, status:string, failureState:string, message:string, active:Object|null, roles?:Object[], operatorBoundary:string }} snapshot
 */
export function updateAgentRosterPanel(els, snapshot) {
    if (!els) return;
    const activeRole = snapshot.activeRole || "guide";
    const blocked = Boolean(snapshot.failureState);
    const active = snapshot.active || {};
    if (els.active) {
        els.active.textContent = activeRole;
        els.active.classList.toggle("status-pill--ok", !blocked);
        els.active.classList.toggle("status-pill--warning", blocked);
        els.active.classList.toggle("status-pill--muted", false);
    }
    if (els.roleSelect && Array.isArray(snapshot.roles) && snapshot.roles.length > 0) {
        const currentValue = els.roleSelect.value || activeRole;
        els.roleSelect.innerHTML = "";
        for (const role of snapshot.roles) {
            const option = document.createElement("option");
            option.value = role.id;
            option.textContent = role.id;
            els.roleSelect.appendChild(option);
        }
        els.roleSelect.value = snapshot.roles.some((role) => role.id === currentValue)
            ? currentValue
            : activeRole;
    }
    if (els.layer) {
        els.layer.textContent = active.layer || "liminal";
    }
    if (els.boundary) {
        els.boundary.textContent = snapshot.operatorBoundary ? "human gate" : "human";
    }
    if (els.guidance) {
        els.guidance.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.guidance.textContent = active.guidance || snapshot.message || "role ready";
    }
    if (els.selectButton) {
        els.selectButton.disabled = false;
    }
}

/**
 * MVP-004 Motif Arc panel を更新する。
 * @param {Object} els
 * @param {{ activeMotifId:string, status:string, failureState:string, message:string, active:Object|null, motifs?:Object[] }} snapshot
 */
export function updateMotifArcPanel(els, snapshot) {
    if (!els) return;
    const active = snapshot.active || {};
    const blocked = Boolean(snapshot.failureState);
    if (els.status) {
        els.status.textContent = blocked ? snapshot.failureState : (snapshot.status || "ready");
        els.status.classList.toggle("status-pill--ok", !blocked);
        els.status.classList.toggle("status-pill--warning", blocked);
        els.status.classList.toggle("status-pill--muted", false);
    }
    if (els.select && Array.isArray(snapshot.motifs) && snapshot.motifs.length > 0) {
        const currentValue = els.select.value || snapshot.activeMotifId;
        els.select.innerHTML = "";
        for (const motif of snapshot.motifs) {
            const option = document.createElement("option");
            option.value = motif.motif_id;
            option.textContent = motif.public_safe_name;
            els.select.appendChild(option);
        }
        els.select.value = snapshot.motifs.some((motif) => motif.motif_id === currentValue)
            ? currentValue
            : snapshot.activeMotifId;
    }
    if (els.archetype) {
        els.archetype.textContent = active.archetype_ready ? "ready" : "missing";
    }
    if (els.world) {
        els.world.textContent = active.world_ready ? "ready" : "missing";
    }
    if (els.core) {
        els.core.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.core.textContent = active.core || snapshot.message || "motif gate ready";
    }
    if (els.evaluateButton) {
        els.evaluateButton.disabled = false;
    }
}

/**
 * MVP-005 Assessment Lab panel を更新する。
 * @param {Object} els
 * @param {{ activeCategoryId:string, status:string, failureState:string, message:string, active:Object|null, categories?:Object[] }} snapshot
 */
export function updateAssessmentLabPanel(els, snapshot) {
    if (!els) return;
    const active = snapshot.active || {};
    const blocked = Boolean(snapshot.failureState);
    if (els.status) {
        els.status.textContent = blocked ? snapshot.failureState : (snapshot.status || "ready");
        els.status.classList.toggle("status-pill--ok", !blocked);
        els.status.classList.toggle("status-pill--warning", blocked);
        els.status.classList.toggle("status-pill--muted", false);
    }
    if (els.select && Array.isArray(snapshot.categories) && snapshot.categories.length > 0) {
        const currentValue = els.select.value || snapshot.activeCategoryId;
        els.select.innerHTML = "";
        for (const category of snapshot.categories) {
            const option = document.createElement("option");
            option.value = category.category_id;
            option.textContent = category.public_safe_name;
            els.select.appendChild(option);
        }
        els.select.value = snapshot.categories.some((category) => category.category_id === currentValue)
            ? currentValue
            : snapshot.activeCategoryId;
    }
    if (els.input) {
        els.input.textContent = active.input || "toy scenario";
    }
    if (els.output) {
        els.output.textContent = active.output || "assessment note";
    }
    if (els.fail) {
        els.fail.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.fail.textContent = active.fail_condition || snapshot.message || "benchmark gate ready";
    }
    if (els.evaluateButton) {
        els.evaluateButton.disabled = false;
    }
}

/**
 * MVP-006 Governance / FDE panel を更新する。
 * @param {Object} els
 * @param {{ activeDecision:string, status:string, failureState:string, message:string, layers?:Object[], fdeSteps?:Object[], decisions?:string[], numericProtocol?:Object, oversight?:Object }} snapshot
 */
export function updateGovernanceFdePanel(els, snapshot) {
    if (!els) return;
    const blocked = Boolean(snapshot.failureState);
    if (els.status) {
        els.status.textContent = blocked ? snapshot.failureState : (snapshot.activeDecision || "watch");
        els.status.classList.toggle("status-pill--ok", !blocked && snapshot.activeDecision === "proceed");
        els.status.classList.toggle("status-pill--warning", blocked || snapshot.activeDecision !== "proceed");
        els.status.classList.toggle("status-pill--muted", false);
    }
    if (els.select && Array.isArray(snapshot.decisions) && snapshot.decisions.length > 0) {
        const currentValue = els.select.value || snapshot.activeDecision;
        els.select.innerHTML = "";
        for (const decision of snapshot.decisions) {
            const option = document.createElement("option");
            option.value = decision;
            option.textContent = decision;
            els.select.appendChild(option);
        }
        els.select.value = snapshot.decisions.includes(currentValue)
            ? currentValue
            : snapshot.activeDecision;
    }
    if (els.oversight) {
        const role = snapshot.oversight?.user_role || "external_monitor";
        els.oversight.textContent = snapshot.oversight?.human_gate_required
            ? `${role} / human gate`
            : role;
    }
    if (els.fde) {
        const steps = Array.isArray(snapshot.fdeSteps) ? snapshot.fdeSteps : [];
        els.fde.textContent = steps.map((step) => step.step_id).join(" -> ") || "entry -> packet -> evidence -> decision -> closure";
    }
    if (els.numeric) {
        els.numeric.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        const status = snapshot.numericProtocol?.status || "parking-lot";
        const reason = snapshot.numericProtocol?.reason || snapshot.message || "numeric protocol stays parking-lot";
        els.numeric.textContent = `${status}: ${reason}`;
    }
    if (els.decideButton) {
        els.decideButton.disabled = false;
    }
}

/**
 * MVP-007 Repo Skill Mesh panel を更新する。
 * @param {Object} els
 * @param {{ activeSkillId:string, status:string, failureState:string, message:string, skillFamilies?:Object[], recursiveGuard?:Object, distributedOps?:Object, cloudCapacity?:Object }} snapshot
 */
export function updateRepoSkillMeshPanel(els, snapshot) {
    if (!els) return;
    const blocked = Boolean(snapshot.failureState);
    if (els.status) {
        els.status.textContent = blocked ? snapshot.failureState : (snapshot.status || "ready");
        els.status.classList.toggle("status-pill--ok", !blocked);
        els.status.classList.toggle("status-pill--warning", blocked);
        els.status.classList.toggle("status-pill--muted", false);
    }
    if (els.select && Array.isArray(snapshot.skillFamilies) && snapshot.skillFamilies.length > 0) {
        const currentValue = els.select.value || snapshot.activeSkillId;
        els.select.innerHTML = "";
        for (const skill of snapshot.skillFamilies) {
            const option = document.createElement("option");
            option.value = skill.skill_id;
            option.textContent = skill.skill_id;
            els.select.appendChild(option);
        }
        els.select.value = snapshot.skillFamilies.some((skill) => skill.skill_id === currentValue)
            ? currentValue
            : snapshot.activeSkillId;
    }
    if (els.depth) {
        els.depth.textContent = `max ${snapshot.recursiveGuard?.maximum_depth ?? 3}`;
    }
    if (els.distributed) {
        els.distributed.textContent = snapshot.distributedOps?.implementation_allowed
            ? "allowed"
            : "design-spike";
    }
    if (els.cloud) {
        els.cloud.textContent = snapshot.cloudCapacity?.execution_allowed
            ? "allowed"
            : "approval required";
    }
    if (els.guard) {
        els.guard.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.guard.textContent = snapshot.message || "repo skill mesh ready";
    }
    if (els.evaluateButton) {
        els.evaluateButton.disabled = false;
    }
}

/**
 * MVP-008 Intake Lifecycle panel を更新する。
 * @param {Object} els
 * @param {{ activeClass:string, status:string, failureState:string, message:string, requestClasses?:string[], sourceCategories?:string[], minimumWorldPacket?:Object, lifecycle?:Object, draftCandidate?:Object }} snapshot
 */
export function updateIntakeLifecyclePanel(els, snapshot) {
    if (!els) return;
    const blocked = Boolean(snapshot.failureState);
    if (els.status) {
        els.status.textContent = blocked ? snapshot.failureState : (snapshot.status || "ready");
        els.status.classList.toggle("status-pill--ok", !blocked);
        els.status.classList.toggle("status-pill--warning", blocked);
        els.status.classList.toggle("status-pill--muted", false);
    }
    if (els.select && Array.isArray(snapshot.requestClasses) && snapshot.requestClasses.length > 0) {
        const currentValue = els.select.value || snapshot.activeClass;
        els.select.innerHTML = "";
        for (const requestClass of snapshot.requestClasses) {
            const option = document.createElement("option");
            option.value = requestClass;
            option.textContent = requestClass;
            els.select.appendChild(option);
        }
        els.select.value = snapshot.requestClasses.includes(currentValue) ? currentValue : snapshot.activeClass;
    }
    if (els.source) {
        const categories = Array.isArray(snapshot.sourceCategories) ? snapshot.sourceCategories : [];
        els.source.textContent = categories.length ? categories.join(" / ") : "確認中";
    }
    if (els.world) {
        const packet = snapshot.minimumWorldPacket || {};
        const fields = packet.requiredFields || packet.required_fields || [];
        els.world.textContent = Array.isArray(fields) && fields.length ? `${fields.length} fields` : "確認中";
    }
    if (els.lifecycle) {
        const lifecycle = snapshot.lifecycle || {};
        const threshold = lifecycle.orphanThreshold ?? lifecycle.orphan_threshold ?? "?";
        const heartbeat = lifecycle.heartbeatMode || lifecycle.heartbeat_mode || "確認中";
        els.lifecycle.textContent = `orphan ${threshold} / ${heartbeat}`;
    }
    if (els.candidate) {
        const candidate = snapshot.draftCandidate || {};
        els.candidate.className = blocked
            ? "settings-status settings-status--error"
            : "settings-status";
        els.candidate.textContent = blocked
            ? (snapshot.message || snapshot.failureState || "intake lifecycle draft failed")
            : (candidate.publicSafeName || candidate.public_safe_name || snapshot.message || "draft candidate ready");
    }
    if (els.draftButton) {
        els.draftButton.disabled = false;
    }
}

/**
 * 右パネルのリアルタイム概要を更新する。
 * @param {Object} els
 * @param {{ runId:string, playing:boolean, tick:number, tickTotal:number, day:number|string, time:string, agents:number, moving:number, selectedAgentId:number|null, recentVisits?:Object[] }} snapshot
 */
export function updateLivePanel(els, snapshot) {
    if (!els) return;

    if (els.playbackState) {
        els.playbackState.textContent = snapshot.playing ? "再生中" : "停止中";
        els.playbackState.classList.toggle("status-pill--ok", snapshot.playing);
        els.playbackState.classList.toggle("status-pill--muted", !snapshot.playing);
    }
    if (els.runId) {
        els.runId.textContent = snapshot.runId || "—";
    }
    if (els.tick) {
        els.tick.textContent = `${snapshot.tick || 0} / ${snapshot.tickTotal || 0}`;
    }
    if (els.time) {
        const day = snapshot.day ?? 0;
        els.time.textContent = `Day ${day} ${snapshot.time || "08:00:00"}`;
    }
    if (els.agentCount) {
        els.agentCount.textContent = String(snapshot.agents || 0);
    }
    if (els.movingCount) {
        els.movingCount.textContent = String(snapshot.moving || 0);
    }
    if (els.selectedAgent) {
        els.selectedAgent.textContent = snapshot.selectedAgentId == null
            ? "なし"
            : `Agent ${snapshot.selectedAgentId}`;
    }
    if (els.activityList) {
        updateLiveActivityList(els.activityList, snapshot.recentVisits || []);
    }
}

/**
 * MATRIXモードの現在 tick 表示を更新する。
 * @param {HTMLElement} panelEl
 * @param {{ enabled:boolean, activeTakeovers?:Object[], currentEvents?:Object[], currentWorldLayer?:string, worldLayerReason?:string }} snapshot
 */
export function updateMatrixPanel(panelEl, snapshot) {
    if (!panelEl) return;

    while (panelEl.firstChild) panelEl.removeChild(panelEl.firstChild);

    const header = document.createElement("div");
    header.className = "matrix-panel-header";
    const title = document.createElement("span");
    title.textContent = "MATRIX";
    const pill = document.createElement("span");
    pill.className = "status-pill";
    pill.classList.add(snapshot.enabled ? "status-pill--ok" : "status-pill--muted");
    pill.textContent = snapshot.enabled ? "on" : "off";
    header.appendChild(title);
    header.appendChild(pill);
    panelEl.appendChild(header);

    const active = Array.isArray(snapshot.activeTakeovers) ? snapshot.activeTakeovers : [];
    const current = Array.isArray(snapshot.currentEvents) ? snapshot.currentEvents : [];
    appendWorldLayerSummary(panelEl, snapshot);

    if (!snapshot.enabled) {
        const empty = document.createElement("div");
        empty.className = "matrix-panel-empty";
        empty.textContent = "この run には MATRIX イベントがありません";
        panelEl.appendChild(empty);
        return;
    }

    if (active.length === 0 && current.length === 0) {
        const empty = document.createElement("div");
        empty.className = "matrix-panel-empty";
        empty.textContent = "現在 tick の takeover はありません";
        panelEl.appendChild(empty);
        return;
    }

    const list = document.createElement("ul");
    list.className = "matrix-event-list";
    for (const item of active.slice(0, 3)) {
        const row = document.createElement("li");
        const role = item.matrix_role || "matrix";
        const agent = item.agent_id != null ? `A${item.agent_id}` : "Agent";
        row.textContent = `active / ${role} -> ${agent}`;
        list.appendChild(row);
    }
    for (const event of current.slice(0, 3)) {
        list.appendChild(buildMatrixEventRow(event));
    }
    panelEl.appendChild(list);
}

function buildMatrixEventRow(event) {
    const row = document.createElement("li");
    const role = event.matrix_role || "matrix";
    const agent = event.agent_id != null ? `A${event.agent_id}` : "Agent";

    const title = document.createElement("div");
    title.className = "matrix-event-title";
    title.textContent = `${event.type || "event"} / ${role} / ${agent}`;
    row.appendChild(title);

    const fieldGroups = matrixOptionalFieldGroups(event);
    for (const group of fieldGroups) {
        const groupEl = document.createElement("div");
        groupEl.className = "matrix-event-fields";

        const label = document.createElement("div");
        label.className = "matrix-event-fields-label";
        label.textContent = group.label;
        groupEl.appendChild(label);

        for (const field of group.fields) {
            if (!Object.prototype.hasOwnProperty.call(event, field)) continue;
            const fieldEl = document.createElement("div");
            fieldEl.className = "matrix-event-field";

            const key = document.createElement("span");
            key.className = "matrix-event-field-key";
            key.textContent = field;
            fieldEl.appendChild(key);

            const value = document.createElement("span");
            value.className = "matrix-event-field-value";
            value.textContent = formatMatrixFieldValue(event[field]);
            fieldEl.appendChild(value);

            groupEl.appendChild(fieldEl);
        }

        if (groupEl.childElementCount > 1) {
            row.appendChild(groupEl);
        }
    }

    return row;
}

function matrixOptionalFieldGroups(event) {
    if (event.type === "world_transition") {
        return [{
            label: "Exchange pair",
            fields: ["exchange_cost_payload", "exchanged"],
        }];
    }
    if (event.type === "takeover_start") {
        return [{
            label: "Oath chain",
            fields: ["hierarchy_rank", "sworn_duty"],
        }];
    }
    if (event.type === "stale_report") {
        return [{
            label: "Unstable city core",
            fields: ["core_instability_level", "stabilization_phase"],
        }];
    }
    return [];
}

function formatMatrixFieldValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "object") {
        try {
            return JSON.stringify(value);
        } catch {
            return String(value);
        }
    }
    return String(value);
}

function appendWorldLayerSummary(panelEl, snapshot) {
    const currentLayer = snapshot.currentWorldLayer || "real";
    const wrap = document.createElement("div");
    wrap.className = "matrix-world";

    const label = document.createElement("div");
    label.className = "matrix-world-label";
    label.textContent = "World layer";
    wrap.appendChild(label);

    const chips = document.createElement("div");
    chips.className = "matrix-world-chips";
    for (const layer of ["real", "virtual", "liminal"]) {
        const chip = document.createElement("span");
        chip.className = "matrix-world-chip";
        chip.classList.toggle("matrix-world-chip--active", layer === currentLayer);
        chip.textContent = layer;
        chips.appendChild(chip);
    }
    wrap.appendChild(chips);

    const reason = document.createElement("div");
    reason.className = "matrix-world-reason";
    reason.textContent = snapshot.worldLayerReason || "default_real";
    wrap.appendChild(reason);

    panelEl.appendChild(wrap);
}

/**
 * ライブパネルの直近の動きを更新する。
 * @param {HTMLElement} listEl
 * @param {Object[]} visits
 */
function updateLiveActivityList(listEl, visits) {
    while (listEl.firstChild) listEl.removeChild(listEl.firstChild);

    if (!Array.isArray(visits) || visits.length === 0) {
        const item = document.createElement("li");
        item.className = "live-activity-empty";
        const text = document.createElement("span");
        text.className = "live-activity-text";
        text.textContent = "直近の訪問はありません";
        item.appendChild(text);
        listEl.appendChild(item);
        return;
    }

    for (const visit of visits.slice(0, 4)) {
        const item = document.createElement("li");

        const time = document.createElement("span");
        time.className = "live-activity-time";
        time.textContent = visit.time || "--:--";

        const text = document.createElement("span");
        text.className = "live-activity-text";
        const agent = visit.agent_id != null ? `A${visit.agent_id}` : "Agent";
        const poi = visit.poi_name || visit.poi_id || "POI";
        const reason = visit.reason ? ` / ${visit.reason}` : "";
        text.textContent = `${agent} ${poi}${reason}`;

        item.appendChild(time);
        item.appendChild(text);
        listEl.appendChild(item);
    }
}

// ────────────────────────────────────────────────────────────────────────────
// 凡例パネル
// ─────────────────────────────────────────────────────────────────────────

/**
 * 凡例パネルを更新する。
 * DOM 要素を直接生成し innerHTML は使わない (XSS 防止)。
 * @param {HTMLElement} legendEl
 * @param {Object} data - ViewerState.data
 * @param {number} agentCount
 */
export function updateLegend(legendEl, data, agentCount) {
    if (!legendEl) return;

    const pois = data.pois || [];
    const aois = data.aois || [];

    // カテゴリ別集計
    const catCount = {};
    for (const poi of pois) {
        const cat = poi.category || "unknown";
        catCount[cat] = (catCount[cat] || 0) + 1;
    }

    // 既存 DOM を空にして再構築
    while (legendEl.firstChild) legendEl.removeChild(legendEl.firstChild);

    const header = document.createElement("div");
    header.className   = "legend-header";
    header.textContent = "凡例";
    legendEl.appendChild(header);

    const total = document.createElement("div");
    total.className   = "legend-total";
    total.textContent = `POI ${pois.length} / AOI ${aois.length} / 住人 ${agentCount}`;
    legendEl.appendChild(total);

    const cats = document.createElement("div");
    cats.className = "legend-cats";
    for (const [cat, cnt] of Object.entries(catCount).sort()) {
        const color = CATEGORY_COLORS[cat] || "#888888";
        const item  = document.createElement("div");
        item.className = "legend-item";

        const dot = document.createElement("span");
        dot.className = "legend-dot";
        // style.background は setAttribute ではなくプロパティ代入 (値はコードで決定)
        dot.style.background = color;

        const lbl = document.createElement("span");
        lbl.className   = "legend-label";
        // 内部コードを日本語ラベルに変換 (未知カテゴリはコードをそのまま表示)
        lbl.textContent = getLabel(CATEGORY_LABELS, cat);

        const count = document.createElement("span");
        count.className   = "legend-count";
        count.textContent = String(cnt);

        item.appendChild(dot);
        item.appendChild(lbl);
        item.appendChild(count);
        cats.appendChild(item);
    }
    legendEl.appendChild(cats);
}

// ────────────────────────────────────────────────────────────────────────────
// エージェント詳細パネル
// ────────────────────────────────────────────────────────────────────────────

/**
 * エージェント詳細パネルを更新する。
 * DOM 要素を直接生成し innerHTML は使わない (XSS 防止)。
 * @param {HTMLElement} detailEl
 * @param {number|null} agentId - 選択中 agent id (null で空表示)
 * @param {Object} data - ViewerState.data
 * @param {Object|null} currentState - 現 tick の AgentState オブジェクト
 * @param {Map<number,Object>} [profileMap] - agent id -> profile オブジェクトのマップ (WO-007: id -> 全 profile)
 * @param {Map<string,string>} [poiMap] - poi id -> 店名マップ (訪問先名前解決用)
 * @param {Object[]} [visitRecords] - poi_visit_records.jsonl の全レコード (§5.2 / §5.5)
 */
export function updateAgentDetail(detailEl, agentId, data, currentState, profileMap = new Map(), poiMap = new Map(), visitRecords = []) {
    if (!detailEl) return;

    // 既存 DOM を空にして再構築
    while (detailEl.firstChild) detailEl.removeChild(detailEl.firstChild);

    if (agentId === null || agentId === undefined) {
        const placeholder = document.createElement("div");
        placeholder.className   = "detail-placeholder";
        placeholder.textContent = "エージェントをクリックして詳細を表示";
        detailEl.appendChild(placeholder);
        return;
    }

    // profileMap から profile を取得する (WO-007: profileMap は id -> 全 profile)
    const profile = profileMap.get(agentId) || null;

    // ヘッダー: WO-007 surname ベース表示。
    //   - surname + given がある場合: 「surname given さん」(例: 「井上 翔さん」)
    //   - それ以外で name がある場合: 「name さん」(後方互換フォールバック)
    //   - profile なし: 「Agent N」
    const header = document.createElement("div");
    header.className = "detail-header";
    if (profile) {
        const surname = profile.surname || "";
        const given   = profile.given   || "";
        if (surname && given) {
            header.textContent = `${surname} ${given}さん`;
        } else if (profile.name) {
            header.textContent = `${profile.name}さん`;
        } else {
            header.textContent = `Agent ${agentId}`;
        }
    } else {
        header.textContent = `Agent ${agentId}`;
    }
    detailEl.appendChild(header);

    if (profile) {
        appendRow(detailEl, "年齢",  profile.age         != null ? profile.age : "—");
        appendRow(detailEl, "性別",  profile.gender      || "—");
        appendRow(detailEl, "説明",  profile.description || "—");
        // role は日本語ラベルで表示 (内部コードは保持)
        appendRow(detailEl, "役割", profile.role
            ? getLabel(ROLE_LABELS, profile.role)
            : "—");

        // 友達リストを id -> 名前に解決して表示
        // profileMap は id -> 全 profile オブジェクトなので .name を取り出す (WO-007)
        const snIds = Array.isArray(profile.social_networks) ? profile.social_networks : [];
        let friendDisplay;
        if (snIds.length === 0) {
            friendDisplay = "なし";
        } else {
            // 名前に解決できた友達を列挙し、解決できない id は数字のままフォールバック
            const names = snIds.map(id => {
                const fp = profileMap.get(id);
                return fp ? (fp.name || String(id)) : String(id);
            });
            // 5件超は件数を末尾に追加
            if (names.length > 5) {
                friendDisplay = names.slice(0, 5).join(", ") + `…(${names.length})`;
            } else {
                friendDisplay = names.join(", ");
            }
        }
        appendRow(detailEl, "友達", friendDisplay);
    }

    if (currentState) {
        const hr = document.createElement("hr");
        hr.className = "detail-divider";
        detailEl.appendChild(hr);

        const latVal = typeof currentState.lat === "number" ? currentState.lat.toFixed(5) : "—";
        const lonVal = typeof currentState.lon === "number" ? currentState.lon.toFixed(5) : "—";

        // POI id を店名に解決 (name がなければ id そのままフォールバック)
        const currentPoiRaw = currentState.current_poi_id || null;
        const targetPoiRaw  = currentState.target_poi_id  || null;
        const currentPoiLabel = currentPoiRaw
            ? (poiMap.get(currentPoiRaw) || currentPoiRaw)
            : "移動中";
        const targetPoiLabel = targetPoiRaw
            ? (poiMap.get(targetPoiRaw) || targetPoiRaw)
            : "—";

        appendRow(detailEl, "時刻",     `Day ${currentState.day} ${currentState.time}`);
        appendRow(detailEl, "現在位置", `${latVal}, ${lonVal}`);
        appendRow(detailEl, "現在 POI", currentPoiLabel);
        appendRow(detailEl, "目的 POI", targetPoiLabel);
        // action / status は日本語ラベルで表示 (内部コードは保持)
        appendRow(detailEl, "行動", currentState.action
            ? getLabel(ACTION_LABELS, currentState.action)
            : "—");
        appendRow(detailEl, "状態",   currentState.status  || "—");

        // 直近 POI / 理由: poi_visit_records.jsonl から選択中 agent の最新訪問を表示 (§5.2 / §5.5)
        // 現在の再生位置 (day / time) 以前のレコードだけを対象にする (#3)
        const latestVisit = _findLatestVisit(agentId, visitRecords, currentState.day, currentState.time);
        if (latestVisit) {
            const visitPoiRaw   = latestVisit.poi_id || null;
            const visitPoiLabel = visitPoiRaw
                ? (poiMap.get(visitPoiRaw) || visitPoiRaw)
                : "—";
            const visitReason   = latestVisit.reason || "—";
            const visitTime     = latestVisit.time   || "—";
            appendRow(detailEl, "直近 POI / 理由", `${visitPoiLabel} / ${visitReason} (${visitTime})`);

            // 直近の会話またはイベント (§5.3): visit record の reason / poi / timestamp を表示
            appendRow(detailEl, "直近の会話またはイベント",
                `${visitTime} — ${visitPoiLabel} にて ${visitReason}`);
        } else {
            appendRow(detailEl, "直近 POI / 理由", "—");
            appendRow(detailEl, "直近の会話またはイベント", "—");
        }
    }
}

/**
 * visitRecords から指定 agent_id の最新訪問レコードを返す。
 *
 * VisitRecord は tick を持たず day(int) + time("HH:MM:SS") で時刻を表す (#3)。
 * 「現在の再生位置 (currentDay / currentTime) 以下」のレコードのみを候補とし、
 * その中で (day, time) が最大のレコードを返す。
 * 候補がない場合は null を返す。
 *
 * @param {number} agentId
 * @param {Object[]} visitRecords
 * @param {number} currentDay  - 現在の再生 day (AgentState.day)
 * @param {string} currentTime - 現在の再生 time (AgentState.time, "HH:MM:SS")
 * @returns {Object|null}
 */
function _findLatestVisit(agentId, visitRecords, currentDay, currentTime) {
    if (!Array.isArray(visitRecords) || visitRecords.length === 0) return null;
    let best = null;
    for (const rec of visitRecords) {
        if (rec.agent_id !== agentId) continue;
        const rDay  = rec.day  ?? 0;
        const rTime = rec.time ?? "";
        // (day, time) タプル比較: 現在位置より未来のレコードを除外
        if (rDay > currentDay || (rDay === currentDay && rTime > currentTime)) {
            continue;
        }
        // 候補の中で最大 (day, time) を選択
        if (
            best === null ||
            rDay > best.day ||
            (rDay === best.day && rTime > (best.time ?? ""))
        ) {
            best = rec;
        }
    }
    return best;
}

// ────────────────────────────────────────────────────────────────────────────
// 時刻コントロール
// ─────────────────────────────────────────────────────────────────────────

/**
 * 時刻表示ラベルを更新する。
 * @param {HTMLElement} timeEl - テキストを書き換える要素
 * @param {Object} currentState - agent_states の tick 代表 (全 agent 共通の tick/day/time)
 */
export function updateTimeDisplay(timeEl, currentState) {
    if (!timeEl || !currentState) return;
    timeEl.textContent = `Day: ${currentState.day}  Time: ${currentState.time}`;
}

/**
 * スライダーの max と value を設定する。
 * @param {HTMLInputElement} sliderEl
 * @param {number} max - tick 総数 - 1
 * @param {number} value - 現在 tickIndex
 */
export function updateSlider(sliderEl, max, value) {
    if (!sliderEl) return;
    sliderEl.max   = String(max);
    sliderEl.value = String(value);
}

/**
 * 再生/停止ボタンのテキストを更新する。
 * @param {HTMLButtonElement} btnEl
 * @param {boolean} playing
 */
export function updatePlayButton(btnEl, playing) {
    if (!btnEl) return;
    btnEl.textContent = playing ? "⏸ 停止" : "▶ 再生";
    btnEl.setAttribute("aria-label", playing ? "停止" : "再生");
}

// ─────────────────────────────────────────────────────────────────────────
// データ読込パネル
// ─────────────────────────────────────────────────────────────────────────────

/**
 * データ読込パネルにロード結果 (件数 / 検証結果 / エラー件数) を表示する (§5.2)。
 * DOM 要素を直接生成し innerHTML は使わない (XSS 防止)。
 *
 * @param {HTMLElement} statusEl - id="load-status" の要素
 * @param {Array<{file:string, count:number|null, errors:number}>} results
 *   - file: ファイル名
 *   - count: ロード件数 (null = ロード失敗)
 *   - errors: バリデーションエラー件数
 */
export function updateLoadStatus(statusEl, results) {
    if (!statusEl) return;

    // 既存 DOM を空にして再構築
    while (statusEl.firstChild) statusEl.removeChild(statusEl.firstChild);

    if (!results || results.length === 0) return;

    const list = document.createElement("ul");
    list.className = "load-status-list";

    for (const r of results) {
        const item = document.createElement("li");
        item.className = "load-status-item";

        const fileName = document.createElement("span");
        fileName.className   = "load-status-file";
        fileName.textContent = r.file;

        const status = document.createElement("span");
        status.className = "load-status-result";

        if (r.count === null) {
            if (r.optional) {
                status.textContent = "任意: なし";
                status.classList.add("load-status--ok");
            } else {
                // ロード失敗
                status.textContent    = "読込失敗";
                status.classList.add("load-status--error");
            }
        } else {
            // 成功: 件数とエラー件数を表示
            const errPart = r.errors > 0 ? ` / エラー: ${r.errors}` : "";
            status.textContent = `${r.count} 件${errPart}`;
            if (r.errors > 0) {
                status.classList.add("load-status--warning");
            } else {
                status.classList.add("load-status--ok");
            }
        }

        item.appendChild(fileName);
        item.appendChild(status);
        list.appendChild(item);
    }

    statusEl.appendChild(list);
}

/**
 * データ読込パネルに run 一覧を反映する。
 * @param {HTMLSelectElement} selectEl
 * @param {Array<{run_id:string, display_run_id?:string, agents:number, ticks:number}>} runs
 */
export function updateRunSelector(selectEl, runs) {
    if (!selectEl) return;
    // innerHTML = "" の代わりに DOM 操作でクリア
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    if (!runs || runs.length === 0) {
        const opt = document.createElement("option");
        opt.value    = "";
        opt.textContent = "利用可能な run がありません";
        opt.disabled = true;
        selectEl.appendChild(opt);
        return;
    }
    for (const run of runs) {
        const opt = document.createElement("option");
        opt.value = run.run_id;
        const label = run.display_run_id || run.run_id;
        opt.textContent = `${label} (agents:${run.agents} ticks:${run.ticks})`;
        selectEl.appendChild(opt);
    }
}

// ────────────────────────────────────────────────────────────────────────
// 内部ユーティリティ
// ────────────────────────────────────────────────────────────────────────────

/**
 * 詳細パネルに 1 行 (label / value) を DOM 要素として追加する。
 * innerHTML を使わず textContent でセットするため XSS リスクなし。
 * @param {HTMLElement} container
 * @param {string} label
 * @param {string|number} value
 */
function appendRow(container, label, value) {
    const div   = document.createElement("div");
    div.className = "detail-row";

    const lbl   = document.createElement("span");
    lbl.className   = "detail-label";
    lbl.textContent = label;

    const val   = document.createElement("span");
    val.className   = "detail-value";
    val.textContent = String(value);

    div.appendChild(lbl);
    div.appendChild(val);
    container.appendChild(div);
}
