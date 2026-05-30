/**
 * labels.js — 内部英語コードから日本語表示ラベルへの変換マップ (フロントエンド版)。
 *
 * 正本: docs/subagents/work-orders/wo-urban-010-human-readable-labels.yaml
 * バックエンド対応: tools/urban_viewer/labels.py (SSOT は Python 側)
 *
 * 設計方針:
 *   - 内部 JSONL / contract の値は英語コードのまま維持する (out_of_scope)。
 *   - ビューア表示時にのみ本モジュールのマップを使って変換する。
 *   - 未知コードは getLabel() でコードをそのまま返す (後方互換)。
 *   - /api/labels エンドポイントと値が一致すること。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

// ─────────────────────────────────────────────────────────────────────────────
// POI カテゴリ (§19.3.1 全 12 種)
// ─────────────────────────────────────────────────────────────────────────────

export const CATEGORY_LABELS = Object.freeze({
    "amenity-cafe":       "カフェ",
    "amenity-restaurant": "レストラン",
    "amenity-fast_food":  "ファストフード",
    "amenity-bar":        "バー",
    "shop-convenience":   "コンビニ",
    "shop-clothing":      "衣料品店",
    "shop-supermarket":   "スーパー",
    "leisure-park":       "公園",
    "amenity-school":     "学校",
    "office-building":    "オフィスビル",
    "home-residential":   "住宅",
    "other-misc":         "その他",
});

// ─────────────────────────────────────────────────────────────────────────────
// エージェント役割 (contract §Enumerations / Agent role)
// ─────────────────────────────────────────────────────────────────────────────

export const ROLE_LABELS = Object.freeze({
    "office_worker": "会社員",
    "student":       "学生",
    "other":         "その他",
});

// ─────────────────────────────────────────────────────────────────────────────
// 交流イベント種別 (contract §Enumerations / InteractionEvent.type)
// ─────────────────────────────────────────────────────────────────────────────

export const INTERACTION_TYPE_LABELS = Object.freeze({
    "meeting":      "出会い",
    "conversation": "会話",
    "conflict":     "口論",
    "farewell":     "別れ",
});

// ─────────────────────────────────────────────────────────────────────────────
// 行動理由 (contract §Enumerations / AgentState.action / VisitRecord.reason)
// ─────────────────────────────────────────────────────────────────────────────

export const ACTION_LABELS = Object.freeze({
    "commute":   "通勤",
    "work":      "仕事",
    "study":     "勉強",
    "lunch":     "昼食",
    "errand":    "用事",
    "social":    "交流",
    "go_home":   "帰宅",
    "wander":    "散策",
    "no_target": "目的地なし",
});

// ─────────────────────────────────────────────────────────────────────────────
// ヘルパー
// ─────────────────────────────────────────────────────────────────────────────

/**
 * code を labelMap で日本語ラベルに変換する。
 * 未知コードはコード文字列をそのまま返す (後方互換 / out_of_scope 要件)。
 * @param {Readonly<Record<string,string>>} labelMap
 * @param {string} code
 * @returns {string}
 */
export function getLabel(labelMap, code) {
    if (!code && code !== 0) return "";
    const key = String(code);
    return Object.prototype.hasOwnProperty.call(labelMap, key) ? labelMap[key] : key;
}
