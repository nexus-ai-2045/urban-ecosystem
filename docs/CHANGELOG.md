# Changelog

このファイルはリリース単位の人間向け変更履歴です。
すべての commit は列挙せず、公開協力者と将来の maintainer が読むべき変更だけを要約します。

運用方針は [`docs/release-policy.md`](release-policy.md) を参照してください。

## [Unreleased]

### Added

- リポジトリ全体の release version と release note の運用方針を追加。

### Changed

- `CHANGELOG.md` を Git 履歴一覧から release-oriented な形式に変更。

## [v0.1.0] - 2026-06-03

初回公開 baseline 候補。tag 作成時にこの section を GitHub Release の本文に使う。

### Added

- 都市エージェントシミュレーションの初期実装を追加。
- FastAPI replay viewer と API key なしで動く fallback viewer を追加。
- 合成データ生成、ルールベース simulation、replay 用 JSONL 出力を追加。
- Google Maps / Google Places / Vertex AI Gemini の opt-in 経路を追加。
- data contract と work order ベースの実装運用を追加。
- fallback viewer smoke と CI の API key なし検証経路を追加。
- MIT License と公開協業の入口 docs を追加。

### Changed

- README / CONTRIBUTING / public collaboration docs を、初回協力者が API key なしで確認できる導線に整理。
- ローカル `.env` 読み込みを明示 opt-in に変更。
- viewer の状態表示、ライブ概要、設定表示、role 表示を改善。
- data contract を `0.4.0` まで更新し、`relationship_reason` を正式化。

### Fixed

- fallback viewer の layer label、highlight 解除、sample replay 生成、Vertex 実行例の CLI 引数を修正。
- Gemini 2.5 Flash の thinking 設定と SDK 未導入時の扱いを堅くした。

### Security

- API key、token、`.env`、内部 URL を公開 issue / PR / docs に貼らない方針を明記。
- Google Cloud / Maps / Places / Vertex AI は、環境変数を自分で設定した場合だけ使う課金境界を明記。
