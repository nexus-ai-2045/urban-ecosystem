# LLM社会シミュレーション採用メモ

status: draft
version: 0.1.0
owner: manager
updated: 2026-06-04

## 目的

arXiv 2412.03563「From Individual to Society: A Survey on Social Simulation Driven by Large Language Model-based Agents」の分類を、Urban Ecosystem の現在の軽量・決定論 MVP に取り込む。

本メモは「LLMに毎 tick の行動を決めさせる」ための採用メモではない。現行の replay / interaction / relationship ログを、Individual / Scenario / Society Simulation の三層で評価できるようにする。

## 採用する読み替え

| 論文側の分類 | Urban Ecosystem での読み替え | 最初に見る証拠 |
| --- | --- | --- |
| Individual Simulation | 各 agent の profile / action / state history が十分に残っているか | `agent_profiles_N100.json`, `agent_states.jsonl` |
| Scenario Simulation | 都市内の出会い・会話・衝突・別れが局面として再生できるか | `interaction_events.jsonl`, `relationship_delta`, `relationship_reason` |
| Society Simulation | 集団として POI 偏り、同時滞在、関係ネットワーク密度などが観測できるか | `metrics.json`, `summary.json` |

## 今回採用すること

- `metrics.json` を追加し、replay から再計算できる評価指標を出す。
- `summary.json` は実行概要、`metrics.json` は比較・評価用に分離する。
- 指標は実行時刻や外部 API 状態を含めず、RuleBasedProvider 経路では同一 seed・同一入力で byte 一致させる。
- LLM は interaction summary / relationship_reason / profile 生成補助のような説明層に限定する。

## 今回採用しないこと

- LLM に tick ごとの状態遷移を直接決めさせない。
- 実在人物の再現や現実世界の行動予測には使わない。
- MATSim / SUMO / ActivitySim のような重い外部シミュレータを直接組み込まない。
- public contract を story / lore 由来の内部 claim 管理に寄せない。

## 指標の初期形

`metrics.json` は次の三層を持つ。

```text
individual_simulation:
  - agents_with_state_history
  - action_diversity
  - action_count_by_type
  - profile_coverage

scenario_simulation:
  - interaction_count_by_type
  - relationship_delta_count
  - relationship_reason_count
  - co_presence_distribution
  - repeated_interaction_pairs

society_simulation:
  - arrival_status_rate
  - no_target_rate
  - poi_visit_entropy
  - unique_poi_visit_rate
  - social_network_density
```

## 採用順序

1. `metrics.json` を出力する。
2. data contract / viewer allowlist に `metrics.json` を追加する。
3. metrics の byte 再現性と replay 整合をテストする。
4. 後続で UI 表示や run 比較へ広げる。

## 参照

- arXiv 2412.03563: https://arxiv.org/pdf/2412.03563
- 既存採用メモ: `docs/regional-simulation-adoption-research.md`
- データ契約: `docs/subagents/contracts/urban-ecosystem-data-contract.md`
