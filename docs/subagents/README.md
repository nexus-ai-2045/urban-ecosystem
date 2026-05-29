# Subagent Operating Specs

このディレクトリは、Codex と Claude Code の両方が読む共通のサブエージェント運用仕様である。

`AGENTS.md` と `CLAUDE.md` は入口であり、役割分担、human gate、work order の正本はこのディレクトリに置く。ツール固有の実行方法は入口文書に残してよいが、研究方針、権限境界、成果物形式はここを優先する。

## Files

| ファイル | 役割 |
|---|---|
| `operating-model.md` | サブエージェント全体の運用モデル |
| `human-gates.md` | 人間が承認・レビューする境界 |
| `work-order-template.yaml` | エージェントへ作業を渡すためのテンプレート |
| `model-change-proposal-template.md` | 地理・環境・物理・制度モデル変更の提案テンプレート |
| `roles/*.md` | 各サブエージェントの責務と成果物 |

## Basic Rule

エージェントは調査、実装、試験、パラメータ探索、レポート草案作成を進める。重要な方針決定、モデル前提の採用、長時間実験、重要結果の解釈、統合判断は人間が行う。
