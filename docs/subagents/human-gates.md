# Human Gates

この文書は、サブエージェントが自律実行を止め、人間の判断を待つ境界を定義する。

## Gate Summary

| Gate | Name | Human decision |
|---|---|---|
| G0 | Work order approval | 目的、範囲、変更可能ファイル、実験予算を承認する |
| G1 | Model change approval | 地理・環境・物理・制度モデルの前提変更を承認する |
| G2 | Experiment plan approval | 長時間 run、広い sweep、新しい PDCA cycle を承認する |
| G3 | Significant result review | 重要結果の解釈、研究上の結論、公開可能な主張をレビューする |
| G4 | Integration approval | merge、正式ドキュメント更新、次 Phase 移行を承認する |

## G0: Work Order Approval

エージェントが実装・実験を開始する前に、人間が以下を確認する。

- 作業目的
- 作業の終了条件
- 変更可能ファイル
- 変更禁止ファイル
- 実行してよいコマンド
- 実験 run の上限
- 必要な review role

## G1: Model Change Approval

以下に該当する場合、実装前に `model-change-proposal-template.md` を使って提案を作り、人間レビューを待つ。

- 月南極の地理表現を変える
- フレア、日照、通信途絶などの環境イベントの意味を変える
- バッテリー、移動、発電、熱、通信、資源採集などの物理近似を変える
- データ共有、安全区域、相互運用性などの制度・インフラモデルを入れる
- 評価指標の定義を変える
- 国際探査ロードマップの解釈をコードやシナリオの前提にする

## G2: Experiment Plan Approval

エージェントは承認済み範囲内の短時間実験と小さな sweep を実行できる。以下は人間承認を必要とする。

- overnight run
- `--limit` なしの大きな batch
- 新しい PDCA cycle の開始
- モデル pull や外部サービス利用が必要な実験
- 実験結果ディレクトリが大きくなる設定
- 既存の比較軸を変える sweep

## G3: Significant Result Review

エージェントは diagnostics、failure mode、report、次 sweep 案を作成できる。ただし、以下は人間が決める。

- 創発行動が観測されたという結論
- モデルが妥当であるという結論
- 国際制度差や主体差に関する解釈
- 論文化、対外説明、発表資料に使う主張
- 次 Phase へ進む判断

## G4: Integration Approval

以下は人間承認後に行う。

- main への merge
- PR 作成または push
- 正式なロードマップ文書の更新
- `AGENTS.md`、`CLAUDE.md`、共通運用仕様の大きな変更
- 後方互換性を壊す変更

## Stop Conditions

エージェントは以下を検出したら作業を止め、報告する。

- `core/` の設計変更が必要になった
- `materials/` の変更が必要になった
- 既存 `water_exploration` の互換性が壊れた
- テストが失敗し、原因が作業範囲外にある
- 実験結果から大きな方針転換が示唆された
- 国際制度や国別シナリオの解釈リスクが出た
- 承認済みの実験予算を超えそうになった

## Approved Tuning Boundary Template

```yaml
approved_tuning_bounds:
  run.agents.communication_radius: [4.0, 16.0]
  run.survival.battery_initial: [40.0, 90.0]
  scenario.resources.density: [0.25, 0.9]
  scenario.events.*.intensity: [0.0, 0.9]

requires_human_approval:
  - new_scenario
  - new_metric_definition
  - core_change
  - geography_model_change
  - environment_model_change
  - physics_model_change
  - policy_model_change
  - overnight_run
  - publishable_conclusion
```
