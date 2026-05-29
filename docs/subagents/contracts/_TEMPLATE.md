---
id: contract-<short-slug>
status: draft   # draft | accepted | superseded
version: 0.1.0
owners:
  - work_order: <wo-id-A>
    role: <role>
  - work_order: <wo-id-B>
    role: <role>
reviewers: []   # human reviewers, if any
created: YYYY-MM-DD
updated: YYYY-MM-DD
supersedes: []  # contract ids
---

# Contract: <short title>

## Why

依存しあう複数の work order が **実装開始前** に合意すべき接点を 1 ファイルに固定する。
各 owner はこの contract に従って独立に実装する。実装中の調整はこのファイルの変更で行い、
口頭・チャットでの口約束で進めない。

## Scope

- **In scope** — この contract が固定する対象（関数シグネチャ、データクラス、JSONL 行形式、メッセージ型、CLI フラグなど）
- **Out of scope** — 実装方針・内部実装・エラー処理の詳細など、各 owner が自由に決めてよい部分

## Interface

### 1. 公開シンボル / 関数シグネチャ

```python
# module: <path/to/module.py>

def <function_name>(<args with types>) -> <return type>:
    """<one-line semantics>"""
```

入出力の意味、null/欠損の扱い、副作用の有無を 1 行ずつ書く。

### 2. データスキーマ（dataclass / TypedDict / Pydantic / dict）

```python
# module: <path>
@dataclass
class <Name>:
    field_a: int           # <semantics, units, valid range>
    field_b: str | None    # <semantics, when None>
```

### 3. JSONL / ファイル形式

```jsonc
// path: <results dir>/<filename>.jsonl
{
  "step": 0,           // int >= 0
  "agent_id": "A1",    // str, matches scenario config
  "key": "value"       // <semantics>
}
```

### 4. CLI / 設定キー

| key | type | default | semantics |
|---|---|---|---|
| `--example-flag` | bool | false | ... |

## Invariants

- 不変条件 1（例: 1 step 内で同一 agent_id の行は最大 1 つ）
- 不変条件 2

## Non-goals / Anti-requirements

- 含めないこと（暗黙の期待を排除する）

## Compatibility

- 後方互換性が必要か / 不要か
- 破壊的変更時の手順（version bump → 全 owner 承認 → 同 PR で消費側も更新）

## Verification

contract に対するテストを `tests/contracts/test_<slug>_contract.py` に置く。
最低限以下を assert する:

- `inspect.signature` がここで定義した型と一致
- スキーマの必須キーが揃う
- 不変条件のサンプル検証

## Change log

| version | date | change | approved_by |
|---|---|---|---|
| 0.1.0 | YYYY-MM-DD | initial draft | - |
