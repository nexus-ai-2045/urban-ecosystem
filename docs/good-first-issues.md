# Good First Issue Candidates

公開協業の初回入口として扱いやすい候補です。実際に GitHub issue 化する前に、maintainer が範囲を確認してください。

## 1. ローカル起動手順の再現性レビュー

GitHub issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/10>

目的: README のセットアップ、データ生成、シミュレーション、ビューア起動が初見で通るか確認する。

成果物:

- 実行環境
- 実行したコマンド
- 成功 / 失敗した箇所
- つまずいた説明
- README 改善案

範囲:

- ドキュメント修正のみ
- API キー、Google Cloud、Vertex AI は使わない

## 2. fallback 地図ビューアの UI レビュー

GitHub issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/11>

目的: API キーなしで表示される fallback 地図の見やすさ、ラベル、操作感をレビューする。

成果物:

- スクリーンショットまたは短い観察メモ
- 表示崩れ、読みにくい文言、改善案
- 変更する場合は `tools/urban_viewer/` に限定した小さな PR

範囲:

- Google Maps API は使わない
- シミュレーションモデルは変更しない

## 3. 未決仕様へのコメント

目的: `docs/spec-open-points.md` の未決事項を読み、優先順位や判断材料を整理する。

成果物:

- issue コメントまたは小さな docs PR
- 「今決めるべきこと」と「後でよいこと」の分類
- 不明点や追加調査が必要な点

範囲:

- 仕様の正式採用は maintainer 判断
- コード変更は任意

## 4. テスト名と失敗メッセージの読みやすさ改善

目的: 初回 contributor がテスト失敗を理解しやすいように、テスト名、assert message、fixture 名を改善する。

成果物:

- 小さなテスト改善 PR
- `pytest tests/ -q` の結果

範囲:

- 振る舞い変更なし
- テスト対象コードの大きな変更なし

## 5. 課金境界・秘密情報境界の説明レビュー

GitHub issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/12>

目的: README と CONTRIBUTING の課金境界、API キー、`.env`、生成データの扱いが初見で伝わるか確認する。

成果物:

- 説明不足の指摘
- 誤解されそうな箇所の修正案
- 必要なら docs PR

範囲:

- 実 API 呼び出しはしない
- 秘密情報の実例は貼らない
