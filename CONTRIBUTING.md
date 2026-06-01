# Contributing

urban-ecosystem への協力に興味を持ってくれてありがとうございます。

このプロジェクトは、都市の地図上で AI エージェントの 1 日を再生する実験的なシミュレーションです。初回の公開協業では、まず再現性、ドキュメント、UI の使い勝手、安全な実行境界を優先します。

## 最初に確認すること

- 既定の実行経路は無料です。Google Cloud、Google Maps、Vertex AI、Google Places は明示的に API キーやプロジェクトを設定した場合だけ使います。
- API キー、トークン、`.env`、個人情報、未公開データは issue、PR、commit、ログに貼らないでください。
- `data/` 配下の生成物や実験結果は原則コミットしません。
- ライセンスは未決定です。大きな外部貢献を始める前に、ライセンス方針の決定を待ってください。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/generate_urban_sample.py --agents 10 --seed 42 --out-dir data/sample
python tools/urban_simulation_cli.py run \
  --pois data/sample/pois.geojson \
  --profiles data/sample/agent_profiles_N10.json \
  --aois data/sample/aois.geojson \
  --roadnet data/sample/roadnet.geojson \
  --out data/sample
DATA_DIR="$PWD/data" PORT=8080 python -m app.main
```

ブラウザで `http://localhost:8080` を開くと、API キーなしの fallback 地図でリプレイできます。

## テスト

```bash
pytest tests/ -q
```

PR では、実行したテストと結果を本文に書いてください。ドキュメントだけの変更なら、その旨を書けば十分です。

## Pull Request の進め方

1. まず issue で目的と範囲を共有してください。
2. 変更範囲は小さく保ってください。
3. 課金 API、外部サービス、長時間実験、Cloud Run deploy を含む作業は maintainer の明示承認を待ってください。
4. 仕様、データ契約、公開主張を変える場合は、コード変更とは別に根拠と影響範囲を説明してください。
5. PR では、秘密情報が含まれていないことを確認してください。

## 歓迎する初回協力

- README の手順どおりにローカル起動できるかの確認
- fallback 地図ビューアの表示崩れ、操作感、文言の改善
- `docs/spec-open-points.md` の未決事項へのコメント
- テストの読みやすさ改善
- typo、リンク切れ、説明不足の修正

## 人間レビューが必要な境界

以下は maintainer 承認なしで進めないでください。

- Google Cloud / Vertex AI / Google Maps / Google Places を実際に呼ぶ作業
- Cloud Run deploy や公開 URL の変更
- ライセンス、ロードマップ、正式な仕様主張の変更
- シミュレーションのモデル前提や評価指標の変更
- 大量データ、長時間 run、大きな sweep
- 秘密情報、認証、課金、公開範囲に関わる変更
