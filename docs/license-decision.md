# ライセンス決定メモ

status: decided

urban-ecosystem のライセンスは MIT License に決定しました。外部 contributor からの PR も、MIT License で公開できる内容として扱います。

Tracking issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/21>

## 決定

- 採用ライセンス: MIT License
- 外部 contributor からの PR: MIT License で公開できる内容として受け付ける
- サンプルデータ、生成データ、ドキュメント: repository 内の配布物として MIT License の対象に含める
- 商用利用、研究利用、派生利用: MIT License の範囲で許可する

## 採用理由

MIT License は、初回公開協業で参加ハードルを低く保ちやすく、README 再現性レビュー、UI レビュー、小さな修正 PR を受けやすい。都市シミュレーションの実験 repository として、広く試してもらう目的にも合う。

一方で、Apache-2.0 のような特許許諾の明示は持たない。特許・商標・データ権利などの追加条件が必要になった場合は、別 issue で方針を見直す。

## 比較した候補

| 候補 | 向いている場合 | 注意点 |
|---|---|---|
| MIT | 広く使ってもらいたい、制約を最小にしたい | 今回採用。特許許諾は明示されない |
| Apache-2.0 | 企業利用や特許許諾も意識したい | MIT より文面が重い |
| AGPL-3.0 | ネットワーク越しの派生利用にも公開義務を求めたい | contributor と利用者の心理的ハードルが高い |

## 公開協業での扱い

- 初回募集は README 再現性レビュー、fallback 地図 UI レビュー、課金境界レビューから始める。
- 大きな実装 PR も、issue で目的と範囲を共有し、MIT License で公開できる内容として進める。
- API key、token、個人情報、内部 URL は貼らない。

## 完了条件

- `LICENSE` file が repository root にある。
- README のライセンス欄が MIT License を指している。
- CONTRIBUTING と公開協業の現在地から、ライセンス未決の停止点が消えている。
- Tracking issue #21 を close できる。
