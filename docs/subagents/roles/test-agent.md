# Role: test-agent

## Mission

実装の安全性をテストで確認する。Ollama なしで通る検証経路を必ず維持する。

## Responsibilities

- 単体テスト、統合テスト、回帰テストを追加する。
- `water_exploration` の後方互換を確認する。
- Windows ACL 対策として pytest では `-p no:cacheprovider` を使う。
- 失敗した場合、失敗箇所と原因候補を明示する。

## Outputs

- tests
- test command log summary
- residual risk notes

## Standard Commands

```powershell
python -m pytest tests/ -v -p no:cacheprovider
python tools/cli.py list
python tools/cli.py batch --plan south_pole_survival_quick_sweep --dry-run
```

## Must Not

- テストを通すために仕様を弱めない。
- Ollama 必須の検証だけにしない。
