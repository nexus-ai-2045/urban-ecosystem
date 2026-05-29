"""
test_urban_simulation.py — §13.3 シミュレーション検証の機械化テスト (WO-URBAN-004)。

正本:
  - docs/ai-ecosystem-tool-spec.md §9 行動ルール / §13.3 検証 / §20 境界ケース
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

カバレッジ:
  - §13.3.1 完走・出力: 100 体 × 24 tick / 3 jsonl + summary
  - §13.3.2 決定論: 同一 seed → 3 jsonl byte 一致 / seed 変化で interaction 件数変化
  - §13.3.3 invariant: bbox+500m / 連続 tick 移動 STEP_M*1.1 以下 /
                       visit poi 存在 / interaction agent_ids 存在・重複なし /
                       08:00-10:00 office_worker 過半数 commute|work
  - §13.3.4 関係性: relationship_delta は §9.9 隣接遷移のみ / conflict 後 score 減少
  - data_loader 通過: load_agent_states/load_visit_records/load_interaction_events
  - CLI: --sample 経路 / --seed / 静的データ入力経路
"""

import filecmp
import json
import math
import subprocess
import sys
import tempfile
import warnings
from collections import Counter
from pathlib import Path

import pytest

from environments.urban_2d import rules
from environments.urban_2d.data_loader import (
    load_agent_states,
    load_interaction_events,
    load_pois,
    load_visit_records,
)
from environments.urban_2d.models import (
    ACTION_VALUES,
    AGENT_STATUS_VALUES,
    INTERACTION_TYPE_VALUES,
    RELATIONSHIP_STATE_VALUES,
)
from environments.urban_2d.simulation import (
    Simulation,
    load_inputs,
    tick_to_day_time,
)
from tools.generate_urban_sample import generate as gen_sample

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI = _PROJECT_ROOT / "tools" / "urban_simulation_cli.py"

# relationship state の順序 (§9.9 / score 連続性検証用)。
# rival は acquaintance/stranger からの conflict 分岐だが、score の直線順序は
# rival < stranger < acquaintance < friend < close_friend。
_REL_ORDER = ["rival", "stranger", "acquaintance", "friend", "close_friend"]
_REL_IDX = {s: i for i, s in enumerate(_REL_ORDER)}

# §9.9 type → score 増減。1 イベントの score 変化はこの集合のいずれか。
_SCORE_DELTAS = set(rules.SCORE_DELTA.values())


# ─────────────────────────────────────────────────────────────────────────────
# fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_inputs():
    """100 agent / 300 POI の合成静的データを生成し (pois, profiles, dir) を返す。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tmp = tempfile.mkdtemp(prefix="urban_sim_in_")
        gen_sample(tmp, seed=42, agents=100, pois=300, ticks=24, run_id="urban_sample")
        pois, profiles = load_inputs(
            Path(tmp) / "pois.geojson",
            Path(tmp) / "agent_profiles_N100.json",
        )
    return pois, profiles, Path(tmp)


def _run_sim(pois, profiles, *, seed=42, ticks=24, run_id="r"):
    """Simulation を simulate して sim インスタンスを返す (出力ファイルは書かない)。"""
    sim = Simulation(pois, profiles, seed=seed, ticks=ticks, run_id=run_id)
    sim.simulate()
    return sim


# ─────────────────────────────────────────────────────────────────────────────
# §13.3.1 完走・出力
# ─────────────────────────────────────────────────────────────────────────────

def test_completes_100_agents_24_ticks(sample_inputs):
    """100 体・24 tick で例外なく完走し agent_states 行数が一致する (§13.3.1)。"""
    pois, profiles, _ = sample_inputs
    assert len(profiles) == 100
    sim = _run_sim(pois, profiles, ticks=24)
    # 100 agent × 24 tick = 2400 行
    assert len(sim.agent_states) == 100 * 24


def test_emits_four_files(sample_inputs, tmp_path):
    """3 jsonl + summary.json が出力される (§13.3.1)。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "urban_demo"
    summary = Simulation(pois, profiles, seed=42, ticks=24, run_id="urban_demo").run(out)

    for name in (
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "summary.json",
    ):
        assert (out / name).exists(), f"{name} が出力されていない"

    # summary.json は data-contract §Summary JSON の required を満たす
    assert summary["run_id"] == "urban_demo"
    assert summary["seed"] == 42
    assert summary["ticks"] == 24
    assert summary["agents"] == 100
    assert summary["pois"] == 300
    # summary の interactions は interaction_events.jsonl 行数と一致する
    with (out / "interaction_events.jsonl").open(encoding="utf-8") as f:
        event_lines = [line for line in f if line.strip()]
    assert summary["interactions"] == len(event_lines)


def test_completes_without_llm_keys(sample_inputs, monkeypatch):
    """LLM 認証情報がなくてもルールベースで完走する (§13.3.1 / RuleBasedProvider)。"""
    # LLM 関連環境変数を消しても完走することを確認する
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "VERTEX_PROJECT", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    assert len(sim.agent_states) == 2400


# ─────────────────────────────────────────────────────────────────────────────
# §13.3.2 決定論・再現性
# ─────────────────────────────────────────────────────────────────────────────

def test_determinism_byte_identical(sample_inputs, tmp_path):
    """同一 seed・同一入力で 3 jsonl が byte 一致する (§13.3.2)。"""
    pois, profiles, _ = sample_inputs
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    Simulation(pois, profiles, seed=42, ticks=24, run_id="run_a").run(out_a)
    Simulation(pois, profiles, seed=42, ticks=24, run_id="run_b").run(out_b)

    for name in (
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
    ):
        assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
            f"{name} が byte 一致しない (run_id 差分は jsonl に影響しないはず)"
        )


def test_seed_change_varies_interactions(sample_inputs):
    """seed を変えると interaction_events 件数が変化する (§13.3.2)。"""
    pois, profiles, _ = sample_inputs
    sim42 = _run_sim(pois, profiles, seed=42, ticks=24)
    sim7 = _run_sim(pois, profiles, seed=7, ticks=24)
    assert len(sim42.interaction_events) != len(sim7.interaction_events), (
        "seed 変更で interaction 件数が変わらない = 乱数が効いていない"
    )


# ─────────────────────────────────────────────────────────────────────────────
# §13.3.3 挙動の妥当性 (invariant)
# ─────────────────────────────────────────────────────────────────────────────

def test_invariant_within_bbox_plus_500m(sample_inputs):
    """全 agent_state の lat/lon が bbox + 500m 以内 (§13.3.3 テレポート検知)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    bbox = sim.bbox
    mid_lat = (bbox["lat_min"] + bbox["lat_max"]) / 2
    lat_pad = 500.0 / 111_320.0
    lon_pad = 500.0 / (111_320.0 * math.cos(math.radians(mid_lat)))

    for s in sim.agent_states:
        assert bbox["lat_min"] - lat_pad <= s["lat"] <= bbox["lat_max"] + lat_pad
        assert bbox["lon_min"] - lon_pad <= s["lon"] <= bbox["lon_max"] + lon_pad


def test_invariant_step_distance(sample_inputs):
    """連続 tick 間の同一 agent 移動距離が STEP_M*1.1 以下 (§13.3.3)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    limit = rules.STEP_M * 1.1

    by_agent: dict[int, list[dict]] = {}
    for s in sim.agent_states:
        by_agent.setdefault(s["agent_id"], []).append(s)

    for rows in by_agent.values():
        rows.sort(key=lambda r: r["tick"])
        for a, b in zip(rows, rows[1:]):
            d = rules.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
            assert d <= limit + 1e-6, f"移動距離 {d:.1f}m が上限 {limit:.1f}m 超過"


def test_invariant_visit_poi_exists(sample_inputs):
    """各 visit record の poi_id が POI 集合に存在する (§13.3.3)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    poi_ids = {p.id for p in pois}
    for v in sim.visit_records:
        if v.get("poi_id") and v["poi_id"] != "initial_position":
            assert v["poi_id"] in poi_ids, f"visit poi_id {v['poi_id']} が未存在"


def test_invariant_interaction_agents_and_no_dup_pair(sample_inputs):
    """interaction agent_ids が profile に存在し同 tick 同ペア重複なし (§13.3.3)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    pids = {p.id for p in profiles}

    seen: set[tuple] = set()
    for e in sim.interaction_events:
        ids = e["agent_ids"]
        assert len(ids) >= 2 and len(set(ids)) == len(ids)
        assert list(ids) == sorted(ids), "agent_ids は昇順正規化されているべき"
        for a in ids:
            assert a in pids, f"interaction agent {a} が profile に未存在"
        key = (e["tick"], tuple(ids))
        assert key not in seen, f"同 tick 同ペア重複: {key}"
        seen.add(key)


def test_invariant_max_interactions_per_tick(sample_inputs):
    """1 tick あたり interaction が MAX_INTERACTIONS_PER_TICK 以下 (§9.8.2 / §20.3)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    per_tick = Counter(e["tick"] for e in sim.interaction_events)
    for tick, count in per_tick.items():
        assert count <= rules.MAX_INTERACTIONS_PER_TICK, (
            f"tick={tick} で interaction {count} 件 (上限 {rules.MAX_INTERACTIONS_PER_TICK})"
        )


def test_invariant_office_worker_commute_majority(sample_inputs):
    """08:00-10:00 帯で office_worker の過半数が commute|work reason を持つ (§13.3.3)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    office = {p.id for p in profiles if p.role == "office_worker"}
    assert office, "office_worker が存在しない"

    total = Counter()
    commute_like = Counter()
    for s in sim.agent_states:
        m = rules.minutes_of_tick(s["tick"])
        if 8 * 60 <= m < 10 * 60 and s["agent_id"] in office:
            total[s["agent_id"]] += 1
            if s["action"] in ("commute", "work"):
                commute_like[s["agent_id"]] += 1

    majority = sum(1 for a in total if commute_like[a] > total[a] / 2)
    assert majority > len(total) / 2, (
        f"08:00-10:00 で commute|work 過半数の office_worker は {majority}/{len(total)} 体"
    )


def test_enum_values_in_contract(sample_inputs):
    """出力の action/status/type が contract enum に収まる (§13.3.3 / data-contract)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    for s in sim.agent_states:
        assert s["action"] in ACTION_VALUES, f"未知 action {s['action']}"
        assert s["status"] in AGENT_STATUS_VALUES, f"未知 status {s['status']}"
    for e in sim.interaction_events:
        assert e["type"] in INTERACTION_TYPE_VALUES, f"未知 type {e['type']}"


# ─────────────────────────────────────────────────────────────────────────────
# §13.3.4 関係性遷移の妥当性
# ─────────────────────────────────────────────────────────────────────────────

def test_relationship_delta_adjacent(sample_inputs):
    """relationship_delta が §9.9 の隣接遷移のみ (飛躍なし) (§13.3.4)。

    1 イベントの score 変化は {+1,+2,-3,-1} のいずれかなので、from→to は
    score 連続変化で説明可能。stranger→close_friend のような飛躍は起きない。
    具体的には from→to の state index 差が 2 以下に収まることを確認する
    (+2 conversation が stranger(0)→acquaintance を跨いで friend まで届かない /
    -3 conflict が acquaintance→rival を 1 イベントで跨がない)。
    """
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    for e in sim.interaction_events:
        rd = e["relationship_delta"]
        assert rd["from"] in RELATIONSHIP_STATE_VALUES
        assert rd["to"] in RELATIONSHIP_STATE_VALUES
        # stranger→close_friend (差 3) のような飛躍を禁止する
        gap = abs(_REL_IDX[rd["from"]] - _REL_IDX[rd["to"]])
        assert gap <= 2, (
            f"relationship 飛躍を検出: {rd['from']}→{rd['to']} (gap={gap})"
        )


def test_relationship_score_continuous():
    """各 type の score 変化が §9.9 の増減集合に一致する (§13.3.4 / 単体)。"""
    assert rules.SCORE_DELTA["meeting"] == 1
    assert rules.SCORE_DELTA["conversation"] == 2
    assert rules.SCORE_DELTA["conflict"] == -3
    assert rules.SCORE_DELTA["farewell"] == -1
    # state しきい値 (§9.9)
    assert rules.state_from_score(-3) == "rival"
    assert rules.state_from_score(-2) == "stranger"
    assert rules.state_from_score(0) == "stranger"
    assert rules.state_from_score(1) == "acquaintance"
    assert rules.state_from_score(4) == "acquaintance"
    assert rules.state_from_score(5) == "friend"
    assert rules.state_from_score(9) == "friend"
    assert rules.state_from_score(10) == "close_friend"


def test_conflict_decreases_score(sample_inputs):
    """conflict イベント後のペア score が減少している (§13.3.4)。

    各 conflict イベントの from→to が score 減少方向 (state index 非増加)
    であることを確認する。conflict は score -3 のため state は同値か下位へ動く。
    """
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    conflicts = [e for e in sim.interaction_events if e["type"] == "conflict"]
    assert conflicts, "conflict イベントが 1 件も発生していない (テスト前提不成立)"
    for e in conflicts:
        rd = e["relationship_delta"]
        # score -3 のため state index は減少 or 同値 (下限 rival で据え置き)
        assert _REL_IDX[rd["to"]] <= _REL_IDX[rd["from"]], (
            f"conflict なのに関係が上昇: {rd['from']}→{rd['to']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# data_loader 通過
# ─────────────────────────────────────────────────────────────────────────────

def test_outputs_pass_data_loader(sample_inputs, tmp_path):
    """出力 3 jsonl が data_loader を例外なく通る (参照整合込み)。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "loader_check"
    Simulation(pois, profiles, seed=42, ticks=24, run_id="loader_check").run(out)

    agent_ids = frozenset(p.id for p in profiles)
    poi_ids = frozenset(p.id for p in pois)

    with warnings.catch_warnings():
        warnings.simplefilter("error", category=UserWarning)  # 未知 enum も検出
        states = load_agent_states(
            out / "agent_states.jsonl", agent_ids=agent_ids, poi_ids=poi_ids
        )
        visits = load_visit_records(
            out / "poi_visit_records.jsonl", agent_ids=agent_ids, poi_ids=poi_ids
        )
        events = load_interaction_events(
            out / "interaction_events.jsonl", agent_ids=agent_ids, poi_ids=poi_ids
        )

    assert len(states) == 2400
    assert len(visits) >= 1
    assert len(events) >= 1


def test_tick_time_consistency(sample_inputs):
    """全 state の (day, time) が tick から導出した値と一致する (data-contract §Time and Tick)。"""
    pois, profiles, _ = sample_inputs
    sim = _run_sim(pois, profiles, ticks=24)
    for s in sim.agent_states:
        day, time_str = tick_to_day_time(s["tick"])
        assert s["day"] == day
        assert s["time"] == time_str


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def test_cli_sample_path(tmp_path):
    """CLI --sample 経路が完走し、リプレイ可能な自己完結 run を出力する (§12.1)。

    静的 (pois/aois/roadnet/agent_profiles) + 挙動 (agent_states/visit/interaction)
    + summary を同一 run dir に残すことで、ビューア (WO-003) が全レイヤーを描画できる。
    """
    out = tmp_path / "cli_sample_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--ticks", "24", "--seed", "42", "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"
    summary = json.loads(result.stdout)
    assert summary["run_id"] == "cli_sample_run"
    assert summary["agents"] == 100
    assert summary["aois"] == 10
    assert summary["roads"] == 299
    assert summary["interactions"] > 0  # sim summary で上書きされている (静的 0 ではない)
    # 静的 + 挙動の全ファイルが run dir 単体に揃う (viewer 消費可能)
    for name in (
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N100.json",
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "summary.json",
    ):
        assert (out / name).exists(), f"{name} が run dir に無い"


def test_cli_static_input_path(sample_inputs, tmp_path):
    """CLI が既存静的データ入力経路で完走する (§12.1)。"""
    _, _, sample_dir = sample_inputs
    out = tmp_path / "cli_static_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run",
            "--pois", str(sample_dir / "pois.geojson"),
            "--profiles", str(sample_dir / "agent_profiles_N100.json"),
            "--aois", str(sample_dir / "aois.geojson"),
            "--roadnet", str(sample_dir / "roadnet.geojson"),
            "--seed", "42", "--ticks", "24", "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"
    summary = json.loads(result.stdout)
    assert summary["run_id"] == "cli_static_run"
    assert summary["aois"] == 10
    assert summary["roads"] == 299


def test_cli_requires_inputs_without_sample(tmp_path):
    """--sample 無し + 入力未指定で非ゼロ終了する (§12.1)。"""
    out = tmp_path / "cli_noinput"
    result = subprocess.run(
        [sys.executable, str(_CLI), "run", "--out", str(out)],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode != 0
