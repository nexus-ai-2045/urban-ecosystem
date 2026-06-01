# Discord から来た人へ

urban-ecosystem に興味を持ってくれてありがとうございます。

まずは小さく参加できます。コードを書かなくても大丈夫です。

## 30 秒で見る

- GitHub repo: <https://github.com/nexus-ai-2045/urban-ecosystem>
- 公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>
- 最初の issue:
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/10>
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/11>
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/12>
- 初回協力候補: [`docs/good-first-issues.md`](good-first-issues.md)
- 協力ガイド: [`CONTRIBUTING.md`](../CONTRIBUTING.md)

## 参加のしかた

### 1. 見るだけ

README を読んで、「何をするプロジェクトか分かるか」を Discord か GitHub issue にコメントしてください。

書いてほしいこと:

- 面白そうに見えた点
- 分かりにくかった点
- 最初に押したくなったリンク

### 2. 動かしてみる

API キーなしで動きます。Google Cloud の課金は発生しません。

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

ブラウザで `http://localhost:8080` を開いてください。

### 3. 小さく直す

最初はこのあたりが歓迎です。

- typo 修正
- README の分かりにくい説明の修正
- fallback 地図ビューアの見た目レビュー
- `docs/spec-open-points.md` へのコメント
- テスト名や失敗メッセージの読みやすさ改善

## やらないでほしいこと

- API キー、トークン、`.env` を貼らない
- Google Cloud / Vertex AI / Google Maps / Google Places を勝手に実行しない
- Cloud Run deploy をしない
- `data/` の生成物や大きな実験結果を commit しない
- ライセンス未定のまま大きな実装 PR を始めない

## Discord に貼る短文

```text
urban-ecosystem の公開協業入口を作っています。
まずは見るだけ・README再現性レビュー・fallback地図UIレビューから歓迎です。
APIキーなしで動くので、Google Cloud課金は発生しません。

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

公開協業 milestone:
https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1

初回協力候補:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/good-first-issues.md

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/10
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
https://github.com/nexus-ai-2045/urban-ecosystem/issues/12
```

## 迷ったら

Discord では「見た」「動いた」「ここで詰まった」の一言だけでも助かります。正式な議論や採否は GitHub issue / PR に残します。
