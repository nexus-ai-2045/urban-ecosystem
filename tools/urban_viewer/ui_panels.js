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
    total.textContent = `POI: ${pois.length} / AOI: ${aois.length} / Agents: ${agentCount}`;
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
        lbl.textContent = cat;

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
 * @param {Map<number,string>} [profileMap] - agent id -> name マップ (友達名前解決用)
 * @param {Map<string,string>} [poiMap] - poi id -> 店名マップ (訪問先名前解決用)
 */
export function updateAgentDetail(detailEl, agentId, data, currentState, profileMap = new Map(), poiMap = new Map()) {
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

    const profiles = data.profiles || [];
    const profile  = profiles.find(p => p.id === agentId) || null;

    // ヘッダー: profile.name があれば「名前さん」、なければ「Agent N」
    const header = document.createElement("div");
    header.className   = "detail-header";
    header.textContent = profile && profile.name
        ? `${profile.name}さん`
        : `Agent ${agentId}`;
    detailEl.appendChild(header);

    if (profile) {
        appendRow(detailEl, "年齢",  profile.age         != null ? profile.age : "—");
        appendRow(detailEl, "性別",  profile.gender      || "—");
        appendRow(detailEl, "説明",  profile.description || "—");
        appendRow(detailEl, "role",  profile.role        || "—");

        // 友達リストを id -> 名前に解決して表示
        const snIds = Array.isArray(profile.social_networks) ? profile.social_networks : [];
        let friendDisplay;
        if (snIds.length === 0) {
            friendDisplay = "なし";
        } else {
            // 名前に解決できた友達を列挙し、解決できない id は数字のままフォールバック
            const names = snIds.map(id => profileMap.get(id) || String(id));
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
        appendRow(detailEl, "action",   currentState.action  || "—");
        appendRow(detailEl, "status",   currentState.status  || "—");

        // interaction summary: 空・null・undefined でもパネルが壊れないよう
        // 値がある時だけ表示する
        const summary = currentState.summary;
        if (summary != null && String(summary).trim() !== "") {
            appendRow(detailEl, "summary", String(summary));
        }
    }
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
