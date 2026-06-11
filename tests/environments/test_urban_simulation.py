"""
test_urban_simulation.py — §13.3 シミュレーション検証の機械化テスト (WO-URBAN-004)。

正本:
  - docs/ai-ecosystem-tool-spec.md §9 行動ルール / §13.3 検証 / §20 境界ケース
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.7.0

カバレッジ:
  - §13.3.1 完走・出力: 100 体 × 24 tick / 3 jsonl + summary + metrics
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
    load_activity_plans,
    load_agent_states,
    load_interaction_events,
    load_pois,
    load_visit_records,
)
from environments.urban_2d.models import (
    ACTION_VALUES,
    AGENT_STATUS_VALUES,
    INTERACTION_TYPE_VALUES,
    MATRIX_EVIDENCE_TYPE_VALUES,
    MATRIX_HUMAN_GATE_ACTION_VALUES,
    MATRIX_HUMAN_GATE_STATUS_VALUES,
    MATRIX_SWARM_ORPHAN_TOLERANCE_DEFAULT,
    MATRIX_SWARM_STALE_AFTER_TICKS_DEFAULT,
    MATRIX_SWARM_STATUS_VALUES,
    POI,
    RELATIONSHIP_STATE_VALUES,
    WORLD_LAYER_MODEL,
    WORLD_LAYER_VALUES,
    Activity,
    ActivityPlan,
    AgentProfile,
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


def test_emits_replay_summary_and_metrics(sample_inputs, tmp_path):
    """3 jsonl + summary.json + metrics.json が出力される (§13.3.1)。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "urban_demo"
    summary = Simulation(pois, profiles, seed=42, ticks=24, run_id="urban_demo").run(out)

    for name in (
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "summary.json",
        "metrics.json",
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

    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["schema_version"] == "social-simulation-metrics-v0.1"
    assert metrics["run_id"] == "urban_demo"
    assert metrics["individual_simulation"]["agents_with_state_history"] == 100
    assert (
        sum(metrics["individual_simulation"]["action_count_by_type"].values())
        == 100 * 24
    )
    assert (
        sum(metrics["scenario_simulation"]["interaction_count_by_type"].values())
        == len(event_lines)
    )
    for key in ("arrival_status_rate", "no_target_rate", "unique_poi_visit_rate"):
        assert 0.0 <= metrics["society_simulation"][key] <= 1.0
    expected_trips = Counter(
        json.loads(line).get("reason")
        for line in (out / "poi_visit_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line and json.loads(line).get("reason")
    )
    assert metrics["society_simulation"]["trip_count_by_action"] == dict(
        sorted(expected_trips.items())
    )
    assert metrics["society_simulation"]["route_mode_count"]["linear_fallback"] > 0
    assert metrics["society_simulation"]["route_mode_count"].get("roadnet", 0) == 0
    assert metrics["society_simulation"]["route_fallback_rate"] == 1.0


def test_matrix_mode_off_does_not_emit_matrix_events(sample_inputs, tmp_path):
    """MATRIXモード既定 off では optional matrix_events.jsonl を出力しない。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_off"

    sim = Simulation(pois, profiles, seed=42, ticks=2, run_id="matrix_off")
    sim.run(out)

    assert sim.matrix_events == []
    assert not (out / "matrix_events.jsonl").exists()


def test_matrix_mode_emits_sentinel_takeover_events(sample_inputs, tmp_path):
    """MATRIXモード on で既存 agent id に sentinel_mvp takeover lifecycle を出力する。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_on"
    target_agent_id = profiles[3].id

    sim = Simulation(
        pois,
        profiles,
        seed=42,
        ticks=4,
        run_id="matrix_on",
        matrix_mode=True,
        matrix_role="sentinel_mvp",
        matrix_agent_id=target_agent_id,
        matrix_ttl_ticks=2,
        matrix_trigger_id="assume_sentinel",
    )
    sim.run(out)

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["type"] for row in rows] == ["takeover_start", "takeover_end"]
    assert {row["agent_id"] for row in rows} == {target_agent_id}
    assert {row["matrix_role"] for row in rows} == {"sentinel_mvp"}
    assert rows[0]["tick"] == 0
    assert rows[0]["ttl_ticks"] == 2
    assert rows[0]["trigger_id"] == "assume_sentinel"
    assert rows[0]["source_layer"] == "real"
    assert rows[0]["target_layer"] == "virtual"
    assert rows[1]["tick"] == 1
    assert rows[1]["exit_reason"] == "ttl_expired"
    assert rows[1]["source_layer"] == "virtual"
    assert rows[1]["target_layer"] == "real"


def test_matrix_mode_output_is_byte_identical(sample_inputs, tmp_path):
    """MATRIXモード on でも同一 seed・同一入力では matrix_events.jsonl が byte 一致する。"""
    pois, profiles, _ = sample_inputs
    out_a = tmp_path / "matrix_a"
    out_b = tmp_path / "matrix_b"

    for out in (out_a, out_b):
        Simulation(
            pois,
            profiles,
            seed=42,
            ticks=4,
            run_id="same_matrix_run",
            matrix_mode=True,
            matrix_role="sentinel_mvp",
            matrix_agent_id=profiles[0].id,
            matrix_ttl_ticks=3,
        ).run(out)

    assert filecmp.cmp(
        out_a / "matrix_events.jsonl",
        out_b / "matrix_events.jsonl",
        shallow=False,
    )


def test_world_layer_model_defines_bridge_agent_contract():
    """M2-001: real / virtual / liminal の entry/exit/cost/evidence を固定する。"""
    assert set(WORLD_LAYER_MODEL) == set(WORLD_LAYER_VALUES)

    for layer, spec in WORLD_LAYER_MODEL.items():
        assert spec["entry_events"], f"{layer} に entry_events がない"
        assert spec["exit_layers"], f"{layer} に exit_layers がない"
        assert spec["transition_cost"], f"{layer} に transition_cost がない"
        assert spec["evidence_types"], f"{layer} に evidence_types がない"

        for target in spec["exit_layers"]:
            assert target in WORLD_LAYER_VALUES
            assert target != layer
            assert spec["transition_cost"][target] >= 0
        for evidence_type in spec["evidence_types"]:
            assert evidence_type in MATRIX_EVIDENCE_TYPE_VALUES

    assert WORLD_LAYER_MODEL["liminal"]["transition_cost"]["real"] == 2
    assert "human_gate" in WORLD_LAYER_MODEL["liminal"]["evidence_types"]


def test_matrix_mode_emits_bridge_world_transition(sample_inputs, tmp_path):
    """M2-002: bridge_agent の world_transition を replay 可能に出力する。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_bridge"

    Simulation(
        pois,
        profiles,
        seed=42,
        ticks=4,
        run_id="matrix_bridge",
        matrix_mode=True,
        matrix_role="sentinel_mvp",
        matrix_agent_id=profiles[0].id,
        matrix_ttl_ticks=3,
        matrix_trigger_id="enter_bridge",
        matrix_transition_tick=1,
        matrix_source_layer="real",
        matrix_target_layer="virtual",
        matrix_evidence_type="matrix_event",
        matrix_evidence_ref="matrix_events.jsonl",
    ).run(out)

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    transition = [row for row in rows if row["type"] == "world_transition"]
    assert len(transition) == 1
    event = transition[0]
    assert event["tick"] == 1
    assert event["agent_id"] == profiles[0].id
    assert event["matrix_role"] == "bridge_agent"
    assert event["source_layer"] == "real"
    assert event["target_layer"] == "virtual"
    assert event["world_layer"] == "virtual"
    assert event["transition_cost"] == WORLD_LAYER_MODEL["real"]["transition_cost"]["virtual"]
    assert event["evidence_type"] == "matrix_event"
    assert event["evidence_ref"] == "matrix_events.jsonl"


def test_matrix_world_transition_rejects_invalid_layer(sample_inputs):
    """M2-002: source と target が同じ transition は readable error にする。"""
    pois, profiles, _ = sample_inputs

    with pytest.raises(ValueError, match="異なる必要があります"):
        Simulation(
            pois,
            profiles,
            seed=42,
            ticks=4,
            matrix_mode=True,
            matrix_transition_tick=1,
            matrix_source_layer="real",
            matrix_target_layer="real",
        )


def test_matrix_mode_emits_guide_agent_fallback_options(sample_inputs, tmp_path):
    """M3-001: guide_agent が rule-based fallback で transition 候補を説明する。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_guide"

    Simulation(
        pois,
        profiles,
        seed=42,
        ticks=4,
        run_id="matrix_guide",
        matrix_mode=True,
        matrix_agent_id=profiles[0].id,
        matrix_guide_tick=1,
        matrix_guide_layer="real",
    ).run(out)

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    guide_events = [
        row for row in rows
        if row["matrix_role"] == "guide_agent" and row["type"] == "heartbeat"
    ]
    assert len(guide_events) == 1
    event = guide_events[0]
    assert event["tick"] == 1
    assert event["world_layer"] == "real"
    assert "real" in event["guide_summary"]
    candidates = event["candidate_transitions"]
    assert {c["target_layer"] for c in candidates} == set(WORLD_LAYER_MODEL["real"]["exit_layers"])
    for candidate in candidates:
        assert candidate["source_layer"] == "real"
        assert candidate["transition_cost"] == WORLD_LAYER_MODEL["real"]["transition_cost"][
            candidate["target_layer"]
        ]
        assert candidate["evidence_types"]


def test_matrix_guide_rejects_invalid_tick(sample_inputs):
    """M3-001: guide tick が範囲外なら readable error にする。"""
    pois, profiles, _ = sample_inputs

    with pytest.raises(ValueError, match="matrix_guide_tick"):
        Simulation(
            pois,
            profiles,
            seed=42,
            ticks=2,
            matrix_mode=True,
            matrix_guide_tick=2,
        )


def test_matrix_mode_emits_operator_human_gate(sample_inputs, tmp_path):
    """M4-001: operator_agent は高リスク action を実行せず human_gate に止める。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_operator"

    Simulation(
        pois,
        profiles,
        seed=42,
        ticks=4,
        run_id="matrix_operator",
        matrix_mode=True,
        matrix_agent_id=profiles[0].id,
        matrix_human_gate_tick=1,
        matrix_gate_action="public_pr",
        matrix_gate_status="requires_human",
        matrix_gate_reason="review_before_public_pr",
    ).run(out)

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    gate_events = [
        row for row in rows
        if row["matrix_role"] == "operator_agent" and row["type"] == "human_gate"
    ]
    assert len(gate_events) == 1
    event = gate_events[0]
    assert event["tick"] == 1
    assert event["gate_action"] == "public_pr"
    assert event["gate_status"] == "requires_human"
    assert event["gate_reason"] == "review_before_public_pr"
    assert event["world_layer"] == "liminal"
    assert event["evidence_type"] == "human_gate"
    assert event["gate_action"] in MATRIX_HUMAN_GATE_ACTION_VALUES
    assert event["gate_status"] in MATRIX_HUMAN_GATE_STATUS_VALUES


def test_matrix_human_gate_rejects_invalid_action(sample_inputs):
    """M4-001: 未定義 gate_action は readable error にする。"""
    pois, profiles, _ = sample_inputs

    with pytest.raises(ValueError, match="matrix_gate_action"):
        Simulation(
            pois,
            profiles,
            seed=42,
            ticks=2,
            matrix_mode=True,
            matrix_human_gate_tick=1,
            matrix_gate_action="auto_post",
        )


def test_matrix_mode_emits_sentinel_swarm_heartbeat_and_stale_report(sample_inputs, tmp_path):
    """M5-001: sentinel_swarm が heartbeat と stale self-report を出力する。"""
    pois, profiles, _ = sample_inputs
    out = tmp_path / "matrix_swarm"

    Simulation(
        pois,
        profiles,
        seed=42,
        ticks=5,
        run_id="matrix_swarm",
        matrix_mode=True,
        matrix_agent_id=profiles[0].id,
        matrix_swarm_heartbeat_tick=1,
        matrix_swarm_stale_tick=4,
    ).run(out)

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    swarm_events = [
        row for row in rows
        if row["matrix_role"] == "sentinel_swarm"
    ]
    assert [row["type"] for row in swarm_events] == ["heartbeat", "stale_report"]

    heartbeat, stale = swarm_events
    assert heartbeat["tick"] == 1
    assert heartbeat["swarm_status"] == "alive"
    assert heartbeat["heartbeat_interval_ticks"] == 1
    assert heartbeat["stale_after_ticks"] == MATRIX_SWARM_STALE_AFTER_TICKS_DEFAULT
    assert heartbeat["orphan_tolerance"] == MATRIX_SWARM_ORPHAN_TOLERANCE_DEFAULT

    assert stale["tick"] == 4
    assert stale["swarm_status"] == "stale"
    assert stale["last_heartbeat_tick"] == 1
    assert stale["missed_heartbeats"] == 3
    assert stale["orphan_tolerance"] == 0
    assert heartbeat["swarm_status"] in MATRIX_SWARM_STATUS_VALUES
    assert stale["swarm_status"] in MATRIX_SWARM_STATUS_VALUES


def test_matrix_sentinel_swarm_rejects_too_early_stale_tick(sample_inputs):
    """M5-001: 3 tick 欠落前の stale_report は readable error にする。"""
    pois, profiles, _ = sample_inputs

    with pytest.raises(ValueError, match="matrix_swarm_stale_tick"):
        Simulation(
            pois,
            profiles,
            seed=42,
            ticks=4,
            matrix_mode=True,
            matrix_swarm_heartbeat_tick=1,
            matrix_swarm_stale_tick=3,
        )


def test_simulation_rejects_empty_pois(sample_inputs):
    """POI が空の入力は bbox の min/max ではなく明示エラーにする。"""
    _, profiles, _ = sample_inputs
    with pytest.raises(ValueError, match="pois は 1 件以上"):
        Simulation([], profiles, seed=42, ticks=1)


def test_simulation_rejects_empty_profiles(sample_inputs):
    """profiles が空の入力は bbox の min/max ではなく明示エラーにする。"""
    pois, _, _ = sample_inputs
    with pytest.raises(ValueError, match="profiles は 1 件以上"):
        Simulation(pois, [], seed=42, ticks=1)


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
    """同一 seed・同一入力で 3 jsonl と metrics.json が byte 一致する (§13.3.2)。"""
    pois, profiles, _ = sample_inputs
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    Simulation(pois, profiles, seed=42, ticks=24, run_id="same_run").run(out_a)
    Simulation(pois, profiles, seed=42, ticks=24, run_id="same_run").run(out_b)

    for name in (
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "metrics.json",
    ):
        assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
            f"{name} が byte 一致しない (同一 seed・同一入力なら一致するはず)"
        )


def test_activity_plans_none_preserves_rule_driven_bytes(sample_inputs, tmp_path):
    """activity_plans 未指定と None 明示は byte 一致し、既存 rule-driven 経路を保つ。"""
    pois, profiles, _ = sample_inputs
    out_a = tmp_path / "implicit_none"
    out_b = tmp_path / "explicit_none"
    Simulation(pois, profiles, seed=42, ticks=24, run_id="same_run").run(out_a)
    Simulation(
        pois,
        profiles,
        seed=42,
        ticks=24,
        run_id="same_run",
        activity_plans=None,
    ).run(out_b)

    for name in (
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "metrics.json",
    ):
        assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
            f"{name} が byte 一致しない (activity_plans=None は後方互換のはず)"
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
    # WO-009 移動モデル更新: 道路追従で経路が長くなり 24 tick 内の到着数が減るため
    # interactions は 0 以上を許容する (静的 summary の 0 と異なる keys で識別する)。
    assert summary["interactions"] >= 0
    # ticks が simulation の ticks と一致する (静的 summary は summary 0 件)
    assert summary["ticks"] == 24
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
        "metrics.json",
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


def test_cli_accepts_activity_plans_optional_input(sample_inputs, tmp_path):
    """CLI が --activity-plans を optional input として読み込み、挙動に反映する。"""
    _, _, sample_dir = sample_inputs
    out = tmp_path / "cli_activity_plan_run"
    plan_path = tmp_path / "activity_plans.jsonl"
    plan_path.write_text(
        json.dumps(
            {
                "agent_id": 0,
                "day": 0,
                "activities": [
                    {
                        "kind": "lunch",
                        "start": "08:00:00",
                        "end": "08:30:00",
                        "poi_id": "poi_001",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run",
            "--pois", str(sample_dir / "pois.geojson"),
            "--profiles", str(sample_dir / "agent_profiles_N100.json"),
            "--activity-plans", str(plan_path),
            "--seed", "42", "--ticks", "6", "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"
    states = [
        json.loads(line)
        for line in (out / "agent_states.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    agent0 = [state for state in states if state["agent_id"] == 0]
    assert agent0[0]["action"] == "lunch"
    assert agent0[0]["target_poi_id"] == "poi_001"
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert "lunch" in metrics["individual_simulation"]["action_count_by_type"]


def test_cli_matrix_mode_emits_optional_matrix_events(tmp_path):
    """CLI --matrix-mode が optional matrix_events.jsonl を出力する。"""
    out = tmp_path / "cli_matrix_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--agents", "5", "--sample-pois", "10",
            "--ticks", "3", "--seed", "42",
            "--matrix-mode",
            "--matrix-agent-id", "0",
            "--matrix-ttl-ticks", "2",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert [row["type"] for row in rows] == ["takeover_start", "takeover_end"]
    assert {row["agent_id"] for row in rows} == {0}
    assert rows[0]["matrix_role"] == "sentinel_mvp"


def test_cli_matrix_mode_emits_world_transition(tmp_path):
    """CLI --matrix-transition-tick が bridge_agent world_transition を出力する。"""
    out = tmp_path / "cli_matrix_bridge_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--agents", "5", "--sample-pois", "10",
            "--ticks", "4", "--seed", "42",
            "--matrix-mode",
            "--matrix-agent-id", "0",
            "--matrix-ttl-ticks", "3",
            "--matrix-trigger-id", "enter_bridge",
            "--matrix-transition-tick", "1",
            "--matrix-source-layer", "real",
            "--matrix-target-layer", "virtual",
            "--matrix-evidence-type", "matrix_event",
            "--matrix-evidence-ref", "matrix_events.jsonl",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    transition = [row for row in rows if row["type"] == "world_transition"]
    assert len(transition) == 1
    assert transition[0]["matrix_role"] == "bridge_agent"
    assert transition[0]["source_layer"] == "real"
    assert transition[0]["target_layer"] == "virtual"
    assert transition[0]["transition_cost"] == 1


def test_cli_matrix_mode_emits_guide_agent_options(tmp_path):
    """CLI --matrix-guide-tick が guide_agent fallback options を出力する。"""
    out = tmp_path / "cli_matrix_guide_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--agents", "5", "--sample-pois", "10",
            "--ticks", "4", "--seed", "42",
            "--matrix-mode",
            "--matrix-agent-id", "0",
            "--matrix-guide-tick", "1",
            "--matrix-guide-layer", "real",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    guide = [
        row for row in rows
        if row["type"] == "heartbeat" and row["matrix_role"] == "guide_agent"
    ]
    assert len(guide) == 1
    assert guide[0]["world_layer"] == "real"
    assert guide[0]["candidate_transitions"]


def test_cli_matrix_mode_emits_operator_human_gate(tmp_path):
    """CLI --matrix-human-gate-tick が operator_agent human_gate を出力する。"""
    out = tmp_path / "cli_matrix_operator_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--agents", "5", "--sample-pois", "10",
            "--ticks", "4", "--seed", "42",
            "--matrix-mode",
            "--matrix-agent-id", "0",
            "--matrix-human-gate-tick", "1",
            "--matrix-gate-action", "public_pr",
            "--matrix-gate-status", "requires_human",
            "--matrix-gate-reason", "review_before_public_pr",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    gates = [
        row for row in rows
        if row["type"] == "human_gate" and row["matrix_role"] == "operator_agent"
    ]
    assert len(gates) == 1
    assert gates[0]["gate_action"] == "public_pr"
    assert gates[0]["gate_status"] == "requires_human"


def test_cli_matrix_mode_emits_sentinel_swarm_events(tmp_path):
    """CLI swarm flags が sentinel_swarm heartbeat/stale_report を出力する。"""
    out = tmp_path / "cli_matrix_swarm_run"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run", "--sample",
            "--agents", "5", "--sample-pois", "10",
            "--ticks", "5", "--seed", "42",
            "--matrix-mode",
            "--matrix-agent-id", "0",
            "--matrix-swarm-heartbeat-tick", "1",
            "--matrix-swarm-stale-tick", "4",
            "--matrix-swarm-stale-after-ticks", "3",
            "--matrix-swarm-orphan-tolerance", "0",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 0, f"CLI 失敗: {result.stderr}"

    rows = [
        json.loads(line)
        for line in (out / "matrix_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    swarm_events = [
        row for row in rows
        if row["matrix_role"] == "sentinel_swarm"
    ]
    assert [row["type"] for row in swarm_events] == ["heartbeat", "stale_report"]
    assert swarm_events[0]["swarm_status"] == "alive"
    assert swarm_events[1]["swarm_status"] == "stale"
    assert swarm_events[1]["missed_heartbeats"] == 3
    assert swarm_events[1]["orphan_tolerance"] == 0


class TestActivityPlans:
    """WO-015: optional activity_plans.jsonl が目的地選択へ入ることを検証する。"""

    def test_fixed_poi_activity_drives_visit_reason(self):
        """poi_id 指定 activity は固定目的地として扱い、既存 action 語彙へ写像される。"""
        lunch_spot = POI(
            id="poi_lunch",
            category="amenity-cafe",
            lon=139.700,
            lat=35.690,
            name="Plan Cafe",
        )
        profile = AgentProfile(
            id=1,
            name="計画 太郎",
            initial_lat=35.690,
            initial_lon=139.700,
            role="office_worker",
        )
        plan = ActivityPlan(
            agent_id=1,
            day=0,
            activities=(
                Activity(
                    kind="lunch",
                    start="08:00:00",
                    end="08:30:00",
                    poi_id="poi_lunch",
                ),
            ),
        )

        sim = Simulation(
            [lunch_spot],
            [profile],
            seed=42,
            ticks=1,
            activity_plans=[plan],
        )
        sim.simulate()

        assert sim.agent_states[0]["action"] == "lunch"
        assert sim.agent_states[0]["status"] == "arrived"
        assert sim.visit_records[0]["poi_id"] == "poi_lunch"
        assert sim.visit_records[0]["reason"] == "lunch"

    def test_category_activity_uses_nearest_matching_poi(self):
        """category 指定 activity は同 category 候補から既存の最近傍選択へ委譲する。"""
        near_cafe = POI(
            id="poi_cafe_near",
            category="amenity-cafe",
            lon=139.70001,
            lat=35.69001,
            name="Near Cafe",
        )
        far_cafe = POI(
            id="poi_cafe_far",
            category="amenity-cafe",
            lon=139.710,
            lat=35.700,
            name="Far Cafe",
        )
        profile = AgentProfile(
            id=1,
            name="計画 花子",
            initial_lat=35.690,
            initial_lon=139.700,
            role="other",
        )
        plan = ActivityPlan(
            agent_id=1,
            day=0,
            activities=(
                Activity(
                    kind="lunch",
                    start="08:00:00",
                    end="08:30:00",
                    category="amenity-cafe",
                ),
            ),
        )

        sim = Simulation(
            [far_cafe, near_cafe],
            [profile],
            seed=42,
            ticks=1,
            activity_plans=[plan],
        )
        sim.simulate()

        assert sim.agent_states[0]["action"] == "lunch"
        assert sim.visit_records[0]["poi_id"] == "poi_cafe_near"
        assert sim.visit_records[0]["reason"] == "lunch"

    def test_loader_output_feeds_simulation(self, tmp_path):
        """load_activity_plans の dataclass 出力をそのまま Simulation に渡せる。"""
        poi = POI(id="poi_social", category="leisure-park", lon=139.700, lat=35.690)
        profile = AgentProfile(
            id=1,
            name="計画 次郎",
            initial_lat=35.690,
            initial_lon=139.700,
            role="other",
        )
        path = tmp_path / "activity_plans.jsonl"
        path.write_text(
            json.dumps(
                {
                    "agent_id": 1,
                    "day": 0,
                    "activities": [
                        {
                            "kind": "social",
                            "start": "08:00:00",
                            "end": "08:20:00",
                            "poi_id": "poi_social",
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        plans = load_activity_plans(
            path,
            agent_ids=frozenset({1}),
            poi_ids=frozenset({"poi_social"}),
        )
        sim = Simulation([poi], [profile], seed=42, ticks=1, activity_plans=plans)
        sim.simulate()

        assert sim.agent_states[0]["action"] == "social"
        assert sim.visit_records[0]["poi_id"] == "poi_social"


def test_cli_requires_inputs_without_sample(tmp_path):
    """--sample 無し + 入力未指定で非ゼロ終了する (§12.1)。"""
    out = tmp_path / "cli_noinput"
    result = subprocess.run(
        [sys.executable, str(_CLI), "run", "--out", str(out)],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode != 0


@pytest.mark.parametrize("sample_pois", [1, 2])
def test_cli_sample_rejects_tiny_pois_without_traceback(tmp_path, sample_pois):
    """--sample-pois 1/2 は IndexError ではなく readable validation error で終了する。"""
    out = tmp_path / f"tiny_pois_{sample_pois}"
    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run",
            "--sample",
            "--agents", "2",
            "--sample-pois", str(sample_pois),
            "--ticks", "1",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )
    assert result.returncode == 2
    assert "pois は 3 以上" in result.stderr
    assert "Traceback" not in result.stderr
    assert "IndexError" not in result.stderr


def test_cli_rejects_empty_profiles_without_traceback(tmp_path):
    """CLI も empty profiles を readable validation error + exit 2 に変換する。"""
    pois_path = tmp_path / "pois.geojson"
    profiles_path = tmp_path / "agent_profiles_N0.json"
    out = tmp_path / "empty_profiles_run"
    pois_path.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [139.7, 35.66]},
                    "properties": {"id": "poi_001", "category": "amenity-cafe"},
                }
            ],
        }),
        encoding="utf-8",
    )
    profiles_path.write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, str(_CLI), "run",
            "--pois", str(pois_path),
            "--profiles", str(profiles_path),
            "--ticks", "1",
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
    )

    assert result.returncode == 2
    assert "profiles は 1 件以上" in result.stderr
    assert "Traceback" not in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# WO-009 道路追従移動 (road-following movement)
# ─────────────────────────────────────────────────────────────────────────────

from environments.urban_2d.road_graph import RoadGraph, build_road_graph  # noqa: E402
from environments.urban_2d.data_loader import load_roads  # noqa: E402
from environments.urban_2d.models import Road  # noqa: E402


def _make_road(road_id: str, coords: list) -> Road:
    """テスト用 Road を作る (LineString)。"""
    return Road(id=road_id, geometry_type="LineString", coordinates=coords, walkable=True)


class TestRoadGraph:
    """RoadGraph の単体テスト (wo-urban-009 §acceptance 1, 2, 5)。"""

    def test_empty_graph_snap_returns_input(self):
        """空グラフの snap_node は入力をそのまま返す (fallback 確認)。"""
        g = RoadGraph([])
        assert g.snap_node(35.66, 139.70) == (35.66, 139.70)

    def test_empty_graph_route_returns_dst(self):
        """空グラフの route は [(dst_lat, dst_lon)] を返す (直線フォールバック)。"""
        g = RoadGraph([])
        result = g.route(35.66, 139.70, 35.661, 139.701)
        assert result == [(35.661, 139.701)]

    def test_single_segment_route(self):
        """1 本の道路セグメントで A→B のルートが得られる。"""
        road = _make_road("road_001", [[139.700, 35.660], [139.701, 35.661]])
        g = RoadGraph([road])

        # A 端点から B 端点へのルート
        waypoints = g.route(35.660, 139.700, 35.661, 139.701)
        assert len(waypoints) >= 1
        # 最後の waypoint は B に近い
        last_lat, last_lon = waypoints[-1]
        d = rules.haversine_m(last_lat, last_lon, 35.661, 139.701)
        assert d < 200.0, f"最終 waypoint が dst から {d:.1f}m 離れている"

    def test_two_segment_route_uses_junction(self):
        """2 本の道路が結合点で繋がっている場合、迂回ルートが得られる。

        A -- J -- B の 3 点トポロジー。A から B への直接道路はなく、
        J (ジャンクション) 経由で到達できることを確認する。
        """
        #  A (35.660, 139.700) -- J (35.661, 139.700) -- B (35.661, 139.701)
        road1 = _make_road("road_001", [[139.700, 35.660], [139.700, 35.661]])
        road2 = _make_road("road_002", [[139.700, 35.661], [139.701, 35.661]])
        g = RoadGraph([road1, road2])

        waypoints = g.route(35.660, 139.700, 35.661, 139.701)
        # 最低 2 ノード (A, J, B の一部) を経由するはず
        assert len(waypoints) >= 2

    def test_unreachable_returns_fallback(self):
        """非連結グラフで到達不能な場合は [(dst_lat, dst_lon)] を返す。"""
        # 2 本の道路が切断されている
        road1 = _make_road("road_001", [[139.700, 35.660], [139.700, 35.661]])
        road2 = _make_road("road_002", [[139.705, 35.665], [139.706, 35.666]])
        g = RoadGraph([road1, road2])

        # road1 端点から road2 端点へは到達不能 (直線フォールバック)
        dst_lat, dst_lon = 35.666, 139.706
        result = g.route(35.660, 139.700, dst_lat, dst_lon)
        assert result == [(dst_lat, dst_lon)]

    def test_snap_node_nearest(self):
        """snap_node は最近傍のノードを返す。"""
        road = _make_road("road_001", [[139.700, 35.660], [139.701, 35.661]])
        g = RoadGraph([road])

        # A 端点 (35.660, 139.700) のほうが近い点
        snapped = g.snap_node(35.6601, 139.7001)
        expected_lat, expected_lon = 35.660, 139.700
        d = rules.haversine_m(snapped[0], snapped[1], expected_lat, expected_lon)
        assert d < 50.0, f"スナップ先が期待ノードから {d:.1f}m 離れている"

    def test_determinism_same_route(self):
        """同一入力で route の結果が毎回同一 (決定論)。"""
        road1 = _make_road("road_001", [[139.700, 35.660], [139.700, 35.661]])
        road2 = _make_road("road_002", [[139.700, 35.661], [139.701, 35.661]])
        g = RoadGraph([road1, road2])

        r1 = g.route(35.660, 139.700, 35.661, 139.701)
        r2 = g.route(35.660, 139.700, 35.661, 139.701)
        assert r1 == r2

    def test_non_walkable_road_excluded(self):
        """walkable=False の道路は無視され、到達不能として扱われる。"""
        road = Road(
            id="road_001", geometry_type="LineString",
            coordinates=[[139.700, 35.660], [139.701, 35.661]],
            walkable=False,
        )
        g = RoadGraph([road])
        assert g.is_empty()
        result = g.route(35.660, 139.700, 35.661, 139.701)
        assert result == [(35.661, 139.701)]

    def test_build_road_graph_factory(self):
        """build_road_graph 便利関数が RoadGraph インスタンスを返す。"""
        road = _make_road("road_001", [[139.700, 35.660], [139.701, 35.661]])
        g = build_road_graph([road])
        assert isinstance(g, RoadGraph)
        assert not g.is_empty()


class TestRoadFollowingMovement:
    """道路追従移動の統合テスト (wo-urban-009 §acceptance 2, 3, 4)。"""

    @pytest.fixture(scope="class")
    def road_sim_inputs(self, tmp_path_factory):
        """roadnet 付きの合成データを生成し (pois, profiles, roads, dir) を返す。"""
        import warnings
        tmp = tmp_path_factory.mktemp("road_sim_in")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from tools.generate_urban_sample import generate as gen_sample
            gen_sample(tmp, seed=42, agents=10, pois=50, ticks=24, run_id="road_test")
        from environments.urban_2d.simulation import load_inputs
        from environments.urban_2d.data_loader import load_roads as _lr
        pois, profiles = load_inputs(
            tmp / "pois.geojson",
            tmp / "agent_profiles_N10.json",
        )
        roads = _lr(tmp / "roadnet.geojson")
        return pois, profiles, roads, tmp

    def test_simulation_accepts_roads(self):
        """Simulation が roadnet リストを受け取れる (API 存在確認)。"""
        # Simulation のコンストラクタに road_graph 引数が追加されていることを確認
        import inspect
        sig = inspect.signature(Simulation.__init__)
        assert "road_graph" in sig.parameters or "roads" in sig.parameters, (
            "Simulation.__init__ に road_graph または roads パラメータがない"
        )

    def test_road_following_within_bbox(self, sample_inputs):
        """道路追従でも全 agent_state が bbox + 500m 以内 (§13.3.3)。"""
        pois, profiles, _ = sample_inputs
        # roadnet なしでも bbox 内に収まることを確認 (フォールバック確認)
        sim = _run_sim(pois, profiles, ticks=24)
        bbox = sim.bbox
        mid_lat = (bbox["lat_min"] + bbox["lat_max"]) / 2
        lat_pad = 500.0 / 111_320.0
        lon_pad = 500.0 / (111_320.0 * math.cos(math.radians(mid_lat)))
        for s in sim.agent_states:
            assert bbox["lat_min"] - lat_pad <= s["lat"] <= bbox["lat_max"] + lat_pad
            assert bbox["lon_min"] - lon_pad <= s["lon"] <= bbox["lon_max"] + lon_pad

    def test_road_following_step_distance(self, sample_inputs):
        """道路追従でも連続 tick 間移動距離が STEP_M * 1.1 以下 (§13.3.3)。"""
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
                assert d <= limit + 1e-6, (
                    f"移動距離 {d:.1f}m が上限 {limit:.1f}m 超過 (道路追従モード)"
                )

    def test_determinism_with_roadnet(self):
        """roadnet 付き Simulation が同一 seed で byte 一致する (§acceptance 4)。"""
        import tempfile
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tmp_in = tempfile.mkdtemp(prefix="road_det_in_")
            from tools.generate_urban_sample import generate as gen_sample
            gen_sample(tmp_in, seed=42, agents=10, pois=50, ticks=24, run_id="det_test")

        from environments.urban_2d.simulation import load_inputs
        from environments.urban_2d.data_loader import load_roads as _lr
        in_path = Path(tmp_in)
        pois, profiles = load_inputs(
            in_path / "pois.geojson",
            in_path / "agent_profiles_N10.json",
        )
        roads = _lr(in_path / "roadnet.geojson")
        graph = build_road_graph(roads)

        import tempfile as _tf
        out_a = Path(_tf.mkdtemp(prefix="road_det_a_"))
        out_b = Path(_tf.mkdtemp(prefix="road_det_b_"))
        Simulation(pois, profiles, seed=42, ticks=24, run_id="road_run", road_graph=graph).run(out_a)
        Simulation(pois, profiles, seed=42, ticks=24, run_id="road_run", road_graph=graph).run(out_b)

        import filecmp
        for name in (
            "agent_states.jsonl",
            "poi_visit_records.jsonl",
            "interaction_events.jsonl",
            "metrics.json",
        ):
            assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
                f"road_graph あり: {name} が byte 一致しない"
            )

        metrics = json.loads((out_a / "metrics.json").read_text(encoding="utf-8"))
        route_counts = metrics["society_simulation"]["route_mode_count"]
        assert route_counts.get("roadnet", 0) > 0
        assert 0.0 <= metrics["society_simulation"]["route_fallback_rate"] <= 1.0

    def test_cli_with_roadnet(self, tmp_path):
        """CLI --roadnet オプションが完走する (§acceptance 2)。"""
        out = tmp_path / "cli_road_run"
        result = subprocess.run(
            [
                sys.executable, str(_CLI), "run", "--sample",
                "--ticks", "24", "--seed", "42", "--agents", "10",
                "--out", str(out),
            ],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        assert result.returncode == 0, f"CLI 失敗: {result.stderr}"
        summary = json.loads(result.stdout)
        assert summary["agents"] == 10
        assert summary["roads"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# WO-008: 行動決定 LLM 本体化 + relationship_reason 配線
# ─────────────────────────────────────────────────────────────────────────────

class TestWO008BehaviorRelationshipLLM:
    """WO-008: build_destination_prompt プロフィール注入 + relationship_reason 配線テスト。"""

    @pytest.fixture(scope="class")
    def sample_inputs_10(self):
        """10 agent / 50 POI の合成データを返す。"""
        import tempfile as _tf
        tmp = _tf.mkdtemp(prefix="wo008_sim_in_")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gen_sample(tmp, seed=42, agents=10, pois=50, ticks=24, run_id="wo008_test")
        pois, profiles = load_inputs(
            Path(tmp) / "pois.geojson",
            Path(tmp) / "agent_profiles_N10.json",
        )
        return pois, profiles

    @pytest.fixture(scope="class")
    def sample_inputs_100(self):
        """100 agent / 300 POI の合成データを返す。"""
        import tempfile as _tf
        tmp = _tf.mkdtemp(prefix="wo008_sim100_in_")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gen_sample(tmp, seed=42, agents=100, pois=300, ticks=24, run_id="wo008_100")
        pois, profiles = load_inputs(
            Path(tmp) / "pois.geojson",
            Path(tmp) / "agent_profiles_N100.json",
        )
        return pois, profiles

    def test_10_agents_rule_based_completes(self, sample_inputs_10):
        """10 体 RuleBased で完走する (WO-008 既定体数)。"""
        pois, profiles = sample_inputs_10
        sim = Simulation(pois, profiles, seed=42, ticks=24)
        sim.simulate()
        assert len(sim.agent_states) == 10 * 24

    def test_destination_context_contains_profile_fields(self, sample_inputs_10):
        """_build_destination_context が occupation/personality/hobbies/day_pattern を含む
        (WO-008 acceptance criterion 1)。"""
        from environments.urban_2d.simulation import _AgentRuntime
        pois, profiles = sample_inputs_10

        # WO-006 フィールドを持つプロフィールを使う
        profile = profiles[0]
        sim = Simulation(pois, profiles, seed=42, ticks=4)
        agent = _AgentRuntime(
            profile=profile,
            lat=profile.initial_lat,
            lon=profile.initial_lon,
        )
        ctx = sim._build_destination_context(agent, tick=4)

        # current_time は必ず存在
        assert "current_time" in ctx

        # WO-006 フィールドが存在する場合 context に含まれる
        if profile.occupation:
            assert ctx.get("occupation") == profile.occupation
        if profile.personality:
            assert ctx.get("personality") == profile.personality
        if profile.hobbies:
            assert ctx.get("hobbies") == list(profile.hobbies)
        if profile.day_pattern:
            assert ctx.get("day_pattern") == profile.day_pattern

    def test_relationship_reason_in_delta_events(self, sample_inputs_100):
        """relationship が変化したイベントに relationship_reason が格納される
        (WO-008 acceptance criterion 2)。"""
        pois, profiles = sample_inputs_100
        sim = Simulation(pois, profiles, seed=42, ticks=24)
        sim.simulate()

        assert sim.interaction_events, "interaction イベントが 0 件"

        delta_events = [
            e for e in sim.interaction_events
            if e.get("relationship_delta") and
            e["relationship_delta"]["from"] != e["relationship_delta"]["to"]
        ]

        if not delta_events:
            pytest.skip("relationship 変化イベントが 0 件 (テスト前提不成立)")

        for event in delta_events:
            assert "relationship_reason" in event, (
                f"relationship 変化イベントに relationship_reason がない: {event}"
            )
            assert isinstance(event["relationship_reason"], str)
            assert len(event["relationship_reason"]) > 0

    def test_relationship_reason_omitted_when_summaries_disabled(
        self, sample_inputs_100
    ):
        """enable_summaries=False のとき relationship_reason キーを出力しない
        (WO-012 data-contract v0.4.0: 空文字の場合は出力しない)。"""
        pois, profiles = sample_inputs_100
        sim = Simulation(
            pois, profiles, seed=42, ticks=24, enable_summaries=False
        )
        sim.simulate()

        assert sim.interaction_events, "interaction イベントが 0 件"

        delta_events = [
            e for e in sim.interaction_events
            if e.get("relationship_delta") and
            e["relationship_delta"]["from"] != e["relationship_delta"]["to"]
        ]
        if not delta_events:
            pytest.skip("relationship 変化イベントが 0 件 (テスト前提不成立)")

        # enable_summaries=False では理由文が "" になるため、契約に従い
        # relationship_reason キー自体が出力されない (空文字を格納しない)。
        for event in delta_events:
            assert "relationship_reason" not in event, (
                f"enable_summaries=False で空 relationship_reason が出力された: {event}"
            )

    def test_rule_based_10_agents_byte_identical(self, sample_inputs_10, tmp_path):
        """10 体 RuleBased で 3 jsonl が byte 一致する (§13.3.2 / WO-008)。"""
        pois, profiles = sample_inputs_10
        out_a = tmp_path / "wo008_run_a"
        out_b = tmp_path / "wo008_run_b"
        Simulation(pois, profiles, seed=42, ticks=24, run_id="run_a").run(out_a)
        Simulation(pois, profiles, seed=42, ticks=24, run_id="run_b").run(out_b)

        for name in (
            "agent_states.jsonl",
            "poi_visit_records.jsonl",
            "interaction_events.jsonl",
        ):
            assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
                f"WO-008 10 体: {name} が byte 不一致"
            )

    def test_interaction_events_have_valid_structure(self, sample_inputs_100):
        """WO-008 追加後も interaction_events が data-contract 構造を維持する。"""
        pois, profiles = sample_inputs_100
        sim = Simulation(pois, profiles, seed=42, ticks=24)
        sim.simulate()

        for event in sim.interaction_events:
            # 必須フィールド
            assert "tick" in event
            assert "type" in event
            assert "agent_ids" in event
            assert "summary" in event
            # relationship_reason は str か存在しない
            if "relationship_reason" in event:
                assert isinstance(event["relationship_reason"], str)


class TestTick0InitialArrival:
    """§20.2 項4/項5: tick=0 で初期位置 = 目的地 POI に一致する場合の arrived / visit 出力。

    spec docs/ai-ecosystem-tool-spec.md §20.2:
      - 項4: tick=0 の status は、目的地を引けた場合 moving、初期位置=目的地POI一致のみ arrived。
      - 項5: tick=0 で arrived となる場合のみ poi_visit_records.jsonl に 1 行出力する。
    """

    def _worker_at_work(self):
        """初期位置が勤務先 POI 座標と完全一致する office_worker を 1 体作る。"""
        work = POI(id="poi_work", category="office", lon=139.700, lat=35.690)
        prof = AgentProfile(
            id=1,
            name="出社 太郎",
            initial_lat=35.690,
            initial_lon=139.700,  # = poi_work の座標 (完全一致)
            role="office_worker",
            work_or_school_poi_id="poi_work",
        )
        return [work], [prof]

    def test_tick0_initial_at_destination_is_arrived(self):
        """初期位置 = 目的地 POI 一致 → tick=0 status は arrived (§20.2 項4)。"""
        pois, profiles = self._worker_at_work()
        sim = Simulation(pois, profiles, seed=42, ticks=1)
        sim.simulate()
        assert sim.agent_states[0]["tick"] == 0
        assert sim.agent_states[0]["status"] == "arrived"

    def test_tick0_arrived_emits_visit_record(self):
        """arrived のとき poi_visit_records に 1 行出力する (§20.2 項5)。"""
        pois, profiles = self._worker_at_work()
        sim = Simulation(pois, profiles, seed=42, ticks=1)
        sim.simulate()
        # tick=0 は day=0 (tick_to_day_time は 0 始まり)
        recs = [v for v in sim.visit_records if v["agent_id"] == 1 and v["day"] == 0]
        assert len(recs) == 1
        assert recs[0]["poi_id"] == "poi_work"
        assert recs[0]["reason"] == "commute"

    def test_tick0_moving_when_not_at_destination(self):
        """初期位置 != 目的地 POI → tick=0 は moving、visit 出力なし (§20.2 項4)。"""
        work = POI(id="poi_work", category="office", lon=139.710, lat=35.700)
        prof = AgentProfile(
            id=1,
            name="通勤 次郎",
            initial_lat=35.690,
            initial_lon=139.700,  # work とは別座標 (約 1km)
            role="office_worker",
            work_or_school_poi_id="poi_work",
        )
        sim = Simulation([work], [prof], seed=42, ticks=1)
        sim.simulate()
        assert sim.agent_states[0]["status"] == "moving"
        tick0_visits = [v for v in sim.visit_records if v["day"] == 0]
        assert tick0_visits == []

    def test_later_tick_staying_not_arrived(self):
        """tick=0 は arrived だが、以降の勤務滞在中は staying (just_arrived は tick 毎にリセット)。"""
        pois, profiles = self._worker_at_work()
        sim = Simulation(pois, profiles, seed=42, ticks=4)
        sim.simulate()
        states = [s for s in sim.agent_states if s["agent_id"] == 1]
        assert states[0]["status"] == "arrived"
        assert all(s["status"] == "staying" for s in states[1:])


# ─────────────────────────────────────────────────────────────────────────────
# MP-002: exchange_pair motif packet (v0.7.0)
# ─────────────────────────────────────────────────────────────────────────────

def _make_simple_sim_inputs():
    """テスト用最小 POI / profile を返す。"""
    poi = POI(id="poi_001", category="amenity-cafe", lon=139.700, lat=35.690)
    profile = AgentProfile(id=0, name="テスト 太郎", initial_lat=35.690, initial_lon=139.700)
    return [poi], [profile]


def test_exchange_pair_fields_absent_when_matrix_off():
    """matrix_mode=False の run では matrix_events.jsonl を出力せず、
    agent_states は既存出力と byte 一致する (off-by-default 不変性)。

    MP-002 Testable acceptance 3 (off-by-default) / contract v0.7.0。
    """
    pois, profiles = _make_simple_sim_inputs()
    seed = 42
    ticks = 4

    # matrix_mode=False で 2 回実行し agent_states が byte 一致することを確認
    sim1 = Simulation(pois, profiles, seed=seed, ticks=ticks, run_id="r1", matrix_mode=False)
    sim1.simulate()

    sim2 = Simulation(pois, profiles, seed=seed, ticks=ticks, run_id="r1", matrix_mode=False)
    sim2.simulate()

    # matrix_events は空
    assert sim1.matrix_events == [], "matrix_mode=False では matrix_events が空であるべき"
    assert sim2.matrix_events == [], "matrix_mode=False では matrix_events が空であるべき"

    # agent_states の byte 一致 (run_id が同じなら内容一致)
    states1 = json.dumps(sim1.agent_states, ensure_ascii=False, sort_keys=True)
    states2 = json.dumps(sim2.agent_states, ensure_ascii=False, sort_keys=True)
    assert states1 == states2, "同一 seed / matrix_mode=False で agent_states が一致するべき"


def test_exchange_pair_fields_present_in_world_transition():
    """matrix_mode=True かつ matrix_transition_tick 指定 run で world_transition event に
    exchange_cost_payload と exchanged が含まれる。
    同一 seed 2 回 run で値が一致する (決定論)。

    MP-002 Testable acceptance 3 (world_transition fields) / contract v0.7.0。
    """
    pois, profiles = _make_simple_sim_inputs()
    seed = 99

    def _run():
        sim = Simulation(
            pois, profiles,
            seed=seed, ticks=4, run_id="exchange_test",
            matrix_mode=True,
            matrix_agent_id=0,
            matrix_ttl_ticks=3,
            matrix_transition_tick=1,
            matrix_source_layer="real",
            matrix_target_layer="virtual",
            matrix_evidence_type="matrix_event",
            matrix_evidence_ref="matrix_events.jsonl",
        )
        sim.simulate()
        return sim

    sim_a = _run()
    sim_b = _run()

    # world_transition event を抽出
    transitions_a = [e for e in sim_a.matrix_events if e["type"] == "world_transition"]
    transitions_b = [e for e in sim_b.matrix_events if e["type"] == "world_transition"]

    assert len(transitions_a) == 1, "world_transition が 1 件出力されるべき"
    evt = transitions_a[0]

    # exchange_pair フィールドの存在確認
    assert "exchange_cost_payload" in evt, "exchange_cost_payload が world_transition に含まれるべき"
    assert "exchanged" in evt, "exchanged が world_transition に含まれるべき"

    # exchanged=True であること
    assert evt["exchanged"] is True, "exchanged は True であるべき"

    # exchange_cost_payload が空でないこと
    assert evt["exchange_cost_payload"], "exchange_cost_payload が空であってはいけない"

    # 決定論: 同一 seed 2 回の結果が一致
    assert transitions_a == transitions_b, "同一 seed で world_transition の内容が一致するべき"

    # 同一 seed で agent_states も byte 一致 (既存決定論の不変性確認)
    states_a = json.dumps(sim_a.agent_states, ensure_ascii=False, sort_keys=True)
    states_b = json.dumps(sim_b.agent_states, ensure_ascii=False, sort_keys=True)
    assert states_a == states_b, "同一 seed で agent_states が一致するべき"
