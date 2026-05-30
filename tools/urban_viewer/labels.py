"""
labels.py — 内部英語コードから日本語表示ラベルへの変換マップ。

正本: docs/subagents/work-orders/wo-urban-010-human-readable-labels.yaml
仕様参照:
  - docs/ai-ecosystem-tool-spec.md §19.3.1 (POI カテゴリ 12 種)
  - docs/ai-ecosystem-tool-spec.md §5.3 (凡例・詳細パネル)
  - docs/subagents/contracts/urban-ecosystem-data-contract.md §Enumerations

設計方針:
  - 内部 JSONL / contract の値は英語コードのまま維持する (out_of_scope)。
  - ビューア表示時にのみ本モジュールのマップを使って変換する。
  - 未知コードは get_label() でコードをそのまま返す (後方互換)。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# POI カテゴリ (§19.3.1 全 12 種)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_LABELS: dict[str, str] = {
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
}

# ─────────────────────────────────────────────────────────────────────────────
# エージェント役割 (contract §Enumerations / Agent role)
# ─────────────────────────────────────────────────────────────────────────────

ROLE_LABELS: dict[str, str] = {
    "office_worker": "会社員",
    "student":       "学生",
    "other":         "その他",
}

# ─────────────────────────────────────────────────────────────────────────────
# 交流イベント種別 (contract §Enumerations / InteractionEvent.type)
# ─────────────────────────────────────────────────────────────────────────────

INTERACTION_TYPE_LABELS: dict[str, str] = {
    "meeting":      "出会い",
    "conversation": "会話",
    "conflict":     "口論",
    "farewell":     "別れ",
}

# ─────────────────────────────────────────────────────────────────────────────
# 行動理由 (contract §Enumerations / AgentState.action / VisitRecord.reason)
# ─────────────────────────────────────────────────────────────────────────────

ACTION_LABELS: dict[str, str] = {
    "commute":   "通勤",
    "work":      "仕事",
    "study":     "勉強",
    "lunch":     "昼食",
    "errand":    "用事",
    "social":    "交流",
    "go_home":   "帰宅",
    "wander":    "散策",
    "no_target": "目的地なし",
}

# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────


def get_label(label_map: dict[str, str], code: str) -> str:
    """code を label_map で日本語ラベルに変換する。

    未知コードはコード文字列をそのまま返す (後方互換 / out_of_scope 要件)。

    Args:
        label_map: CATEGORY_LABELS / ROLE_LABELS / ACTION_LABELS 等。
        code: 変換対象の英語コード。

    Returns:
        日本語ラベル文字列。未知コードは code をそのまま返す。
    """
    return label_map.get(code, code)


# ─────────────────────────────────────────────────────────────────────────────
# 全ラベルマップをまとめた辞書 (API レスポンス / JS 埋め込み用)
# ─────────────────────────────────────────────────────────────────────────────

ALL_LABELS: dict[str, dict[str, str]] = {
    "category":         CATEGORY_LABELS,
    "role":             ROLE_LABELS,
    "interaction_type": INTERACTION_TYPE_LABELS,
    "action":           ACTION_LABELS,
}
