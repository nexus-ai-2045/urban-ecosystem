# 初回協力候補

公開協業の初回入口として扱いやすい候補です。

最初はコード実装を広く募集せず、レビュー・再現性確認・小さな文書修正から始めます。

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

現在の viewer は、左側にデータ読込・レイヤー・マップ状態・設定、中央に地図、右側にライブ概要・凡例・エージェント詳細、下部に再生コントロールを持ちます。Google Maps API キーがない場合は、左側のマップ状態が fallback / Maps API absent になることも確認対象です。

成果物:

- スクリーンショットまたは短い観察メモ
- 左側パネル、地図、右側ライブ概要、下部コントロールのうち見づらい箇所
- 表示崩れ、読みにくい文言、改善案
- 変更する場合は `tools/urban_viewer/` に限定した小さな PR

範囲:

- Google Maps API は使わない
- シミュレーションモデルは変更しない
- API キー、token、`.env`、個人情報は書かない

## 3. 課金境界・秘密情報境界の説明レビュー

GitHub issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/12>

目的: README と CONTRIBUTING の課金境界、API キー、`.env`、生成データの扱いが初見で伝わるか確認する。

成果物:

- 説明不足の指摘
- 誤解されそうな箇所の修正案
- 必要なら docs PR

範囲:

- 実 API 呼び出しはしない
- 秘密情報の実例は貼らない

## まだ広く募集しないもの

- issue で目的と範囲を共有していない大きな機能実装
- Google Cloud / Vertex AI / Google Maps / Google Places を実際に呼ぶ作業
- Cloud Run deploy
- シミュレーションモデルの前提変更
