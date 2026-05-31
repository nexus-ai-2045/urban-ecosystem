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

// ─────────────────────────────────────────────────────────────────────────────
// 凡例パネル
// ─────────────────────────────────────────────────────────────────────────────

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
    total.textContent = `POI: ${pois.length} / AOI: ${aois.length} / エージェント: ${agentCount}`;
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

// ─────────────────────────────────────────────────────────────────────────────
// エージェント詳細パネル
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// 時刻コントロール
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
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
            // ロード失敗
            status.textContent    = "読込失敗";
            status.classList.add("load-status--error");
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
 * @param {Array<{run_id:string, agents:number, ticks:number}>} runs
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
        opt.textContent = `${run.run_id} (agents:${run.agents} ticks:${run.ticks})`;
        selectEl.appendChild(opt);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 内部ユーティリティ
// ─────────────────────────────────────────────────────────────────────────────

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
