# Release Policy

このリポジトリの公開向けバージョンとリリースノートの運用方針です。

## 方針

- リポジトリ全体のリリースは Git tag と `docs/CHANGELOG.md` で管理する。
- GitHub Releases は外部協力者向けの読みやすい告知と配布ページとして使う。
- `docs/CHANGELOG.md` は commit 一覧ではなく、リリース単位の人間向け変更履歴にする。
- データ契約の `version` とリポジトリ全体の release version は別物として扱う。

## Version Scheme

リポジトリ全体は `vMAJOR.MINOR.PATCH` の SemVer 形式を使う。

当面は `v0.x.y` とし、公開協業の入口、viewer、simulation、data contract が安定するまで `v1.0.0` には上げない。

| bump | 使う場面 |
|---|---|
| MAJOR | `v1.0.0` 以降で、公開 API、データ形式、主要 CLI、起動手順に破壊的変更がある時 |
| MINOR | 互換性を保った機能追加、viewer / simulation / public collaboration flow の意味ある追加 |
| PATCH | bug fix、docs correction、fallback smoke 修正、小さい互換維持修正 |

`v0.x.y` の間でも、破壊的変更は `docs/CHANGELOG.md` に明記する。

## Changelog Format

`docs/CHANGELOG.md` は Keep a Changelog 形式に寄せ、次の見出しを使う。

- `Added`
- `Changed`
- `Deprecated`
- `Removed`
- `Fixed`
- `Security`

すべての commit を列挙しない。外部協力者や将来の maintainer が「何が変わったか」を読める粒度に要約する。

## Release Checklist

1. `main` の CI が通っていることを確認する。
2. `docs/CHANGELOG.md` の `Unreleased` を対象 version に移す。
3. 必要なら `docs/subagents/contracts/urban-ecosystem-data-contract.md` など個別 contract の version と changelog を更新する。
4. `git tag vX.Y.Z` を作成する。
5. GitHub Release を作成し、`docs/CHANGELOG.md` の対象 section を元に要約する。
6. 公開協業 docs から参照が必要なら `README.md` または `docs/public-collaboration-status.md` を更新する。

## First Release

最初の公開 baseline は `v0.1.0` を候補とする。

`v0.1.0` は、次を満たす時に tag を打つ。

- MIT License が入っている。
- API key なしで fallback viewer の smoke が通る。
- 公開協業の入口が README / CONTRIBUTING / docs から辿れる。
- 秘密情報、内部 URL、未公開の個人運用メモが公開 release note に混ざっていない。
