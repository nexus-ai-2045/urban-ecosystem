/**
 * colors.js — カテゴリカラー定義の SSOT。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.1 / §5.3
 *
 * ui_panels.js / fallback_map_adapter.js / google_maps_adapter.js が
 * このモジュールを import して使う。3 箇所の重複定義を解消する。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

/**
 * POI カテゴリ -> 色マッピング。
 * キー・カラーコードは変更禁止 (spec §5.1 / 凡例との一致が前提)。
 * @type {Readonly<Record<string, string>>}
 */
export const CATEGORY_COLORS = Object.freeze({
    "amenity-cafe":        "#a0522d",
    "amenity-restaurant":  "#e67e22",
    "amenity-fast_food":   "#e74c3c",
    "amenity-bar":         "#8e44ad",
    "shop-convenience":    "#27ae60",
    "shop-clothing":       "#2980b9",
    "shop-supermarket":    "#16a085",
    "leisure-park":        "#2ecc71",
    "amenity-school":      "#f1c40f",
    "office-building":     "#3498db",
    "home-residential":    "#95a5a6",
    "other-misc":          "#7f8c8d",
});

/**
 * Agent role -> color mapping（キャラらしさを出すための色分け）
 */
export const ROLE_COLORS = Object.freeze({
    "student":       "#9b59b6",   // 紫（学生らしい）
    "office_worker": "#3498db",   // 青（サラリーマンらしい）
    "other":         "#7f8c8d",   // グレー
});
