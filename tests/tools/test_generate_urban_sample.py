"""test_generate_urban_sample.py — WO-URBAN-002 合成データ生成の検証。

正本:
  - docs/ai-ecosystem-tool-spec.md §19 (合成データ生成仕様)
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

scope (§19 準拠 / 2026-05-29 CEO 確定):
  本スクリプトは静的データのみを生成する。挙動ログ (agent_states /
  poi_visit_records / interaction_events) は WO-URBAN-004 の責務であり、
  生成しないことを明示的に検証する。

カバレッジ:
  - 出力ファイル: 静的 5 ファイルを生成し、挙動 jsonl を生成しない
  - 件数: agents/pois/aois/roads と summary の counts 一致
  - 決定論: 同一 seed で静的 4 ファイルが byte 一致 (§19.7)
  - seed 効果: seed を変えると出力が変化する
  - bbox: 全 POI 座標が bbox 内 (§19.2)
  - 命名/参照: data_loader 検証を全て通過 (§13.1 / dangling 参照ゼロ)
  - social_networks: 自己ループなし / 重複なし / 対称
  - CLI: main() が動作し summary を返す
"""

import hashlib
import json
from pathlib import Path

import pytest

from environments.urban_2d.data_loader import (
    load_agent_profiles,
    load_aois,
    load_pois,
    load_roads,
)
from tools.generate_urban_sample import (
    BBOX,
    DEFAULT_AGENTS,
    DEFAULT_POIS,
    generate,
    main,
)

# 再現性検証対象 (§19.7): summary.json は started_at を含むため除外。
DETERMINISTIC_FILES = (
    "pois.geojson",
    "aois.geojson",
    "roadnet.geojson",
    "agent_profiles_N100.json",
)
BEHAVIORAL_FILES = (
    "agent_states.jsonl",
    "poi_visit_records.jsonl",
    "interaction_events.jsonl",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def gen_dir(tmp_path: Path) -> Path:
    """既定パラメータで 1 run 生成し出力ディレクトリを返す。"""
    generate(tmp_path, seed=42, agents=DEFAULT_AGENTS, pois=DEFAULT_POIS, ticks=24)
    return tmp_path


# ── 出力ファイル ──────────────────────────────────────────────────────────────

def test_emits_static_files(gen_dir: Path) -> None:
    for fname in DETERMINISTIC_FILES + ("summary.json",):
        assert (gen_dir / fname).is_file(), f"{fname} が生成されていない"


def test_does_not_emit_behavioral_files(gen_dir: Path) -> None:
    """挙動ログは WO-004 の責務。WO-002 は生成しない (scope 境界)。"""
    for fname in BEHAVIORAL_FILES:
        assert not (gen_dir / fname).exists(), f"{fname} は WO-004 の責務 (生成禁止)"


# ── 件数 ─────────────────────────────────────────────────────────────────────

def test_default_counts(gen_dir: Path) -> None:
    pois = load_pois(gen_dir / "pois.geojson")
    aois = load_aois(gen_dir / "aois.geojson")
    roads = load_roads(gen_dir / "roadnet.geojson")
    poi_ids = frozenset(p.id for p in pois)
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json", poi_ids)

    assert len(profiles) == 100
    assert len(pois) == 300
    assert len(aois) == 10
    assert len(roads) == 299  # 隣接ペア方式 = n_pois - 1 (§19.6.2)


def test_summary_counts_match(gen_dir: Path) -> None:
    summary = json.loads((gen_dir / "summary.json").read_text())
    pois = load_pois(gen_dir / "pois.geojson")
    aois = load_aois(gen_dir / "aois.geojson")
    roads = load_roads(gen_dir / "roadnet.geojson")
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json")

    assert summary["agents"] == len(profiles)
    assert summary["pois"] == len(pois)
    assert summary["aois"] == len(aois)
    assert summary["roads"] == len(roads)
    assert summary["seed"] == 42
    assert summary["ticks"] == 24
    assert summary["interactions"] == 0  # 静的生成


def test_poi_category_distribution(gen_dir: Path) -> None:
    """§19.3.1 のカテゴリ別件数を厳密再現する。"""
    pois = load_pois(gen_dir / "pois.geojson")
    counts: dict[str, int] = {}
    for p in pois:
        counts[p.category] = counts.get(p.category, 0) + 1
    assert counts["home-residential"] == 75
    assert counts["office-building"] == 25
    assert counts["amenity-school"] == 5
    assert counts["amenity-cafe"] == 30
    assert counts["other-misc"] == 35


# ── 決定論 (§19.7) ────────────────────────────────────────────────────────────

def test_deterministic_same_seed(tmp_path: Path) -> None:
    d1, d2 = tmp_path / "run1", tmp_path / "run2"
    generate(d1, seed=42)
    generate(d2, seed=42)
    for fname in DETERMINISTIC_FILES:
        assert _sha256(d1 / fname) == _sha256(d2 / fname), f"{fname} が byte 一致しない"


def test_seed_changes_output(tmp_path: Path) -> None:
    d1, d2 = tmp_path / "s42", tmp_path / "s7"
    generate(d1, seed=42)
    generate(d2, seed=7)
    # POI 座標とプロフィールは seed 依存で変化する
    assert _sha256(d1 / "pois.geojson") != _sha256(d2 / "pois.geojson")
    assert _sha256(d1 / "agent_profiles_N100.json") != _sha256(d2 / "agent_profiles_N100.json")


def test_summary_excluded_from_reproducibility(tmp_path: Path) -> None:
    """summary.json は started_at を含むため byte 一致対象外 (内容は一致)。"""
    d1, d2 = tmp_path / "a", tmp_path / "b"
    s1 = generate(d1, seed=42)
    s2 = generate(d2, seed=42)
    # started_at 以外は一致
    s1.pop("started_at")
    s2.pop("started_at")
    assert s1 == s2


# ── 地理 (§19.2) ──────────────────────────────────────────────────────────────

def test_all_pois_within_bbox(gen_dir: Path) -> None:
    pois = load_pois(gen_dir / "pois.geojson")
    for p in pois:
        assert BBOX["lat_min"] <= p.lat <= BBOX["lat_max"], f"{p.id} lat 範囲外"
        assert BBOX["lon_min"] <= p.lon <= BBOX["lon_max"], f"{p.id} lon 範囲外"


# ── 命名 / 参照整合 (§13.1) ───────────────────────────────────────────────────

def test_passes_loader_validation(gen_dir: Path) -> None:
    """生成物が data_loader の §13.1 検証を全て通過する (参照解決込み)。"""
    pois = load_pois(gen_dir / "pois.geojson")
    poi_ids = frozenset(p.id for p in pois)
    load_aois(gen_dir / "aois.geojson")
    load_roads(gen_dir / "roadnet.geojson")
    # poi_ids を渡すことで home/work/school 参照と social dangling を検証
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json", poi_ids)
    assert len(profiles) == 100


def test_no_dangling_references(gen_dir: Path) -> None:
    pois = load_pois(gen_dir / "pois.geojson")
    poi_ids = frozenset(p.id for p in pois)
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json", poi_ids)
    agent_ids = frozenset(p.id for p in profiles)
    for p in profiles:
        if p.home_poi_id is not None:
            assert p.home_poi_id in poi_ids
        if p.work_or_school_poi_id is not None:
            assert p.work_or_school_poi_id in poi_ids
        for sn in p.social_networks:
            assert sn in agent_ids


def test_role_work_school_assignment(gen_dir: Path) -> None:
    """office_worker→poi_work / student→poi_school / other→なし (§19.4.3)。"""
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json")
    for p in profiles:
        if p.role == "office_worker":
            assert p.work_or_school_poi_id is not None
            assert p.work_or_school_poi_id.startswith("poi_work")
        elif p.role == "student":
            assert p.work_or_school_poi_id is not None
            assert p.work_or_school_poi_id.startswith("poi_school")
        else:  # other
            assert p.work_or_school_poi_id is None


def test_initial_position_matches_home(gen_dir: Path) -> None:
    """initial_position は home POI 座標と一致する (§19.4.4)。"""
    pois = load_pois(gen_dir / "pois.geojson")
    coords = {p.id: (p.lat, p.lon) for p in pois}
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json")
    for p in profiles:
        assert p.home_poi_id is not None
        hlat, hlon = coords[p.home_poi_id]
        assert p.initial_lat == hlat
        assert p.initial_lon == hlon


# ── social_networks (§19.5) ───────────────────────────────────────────────────

def test_social_networks_symmetric_no_self_no_dup(gen_dir: Path) -> None:
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json")
    sn = {p.id: set(p.social_networks) for p in profiles}
    for aid, friends in sn.items():
        assert aid not in friends, f"agent {aid} に自己ループ"
        assert len(friends) == len(profiles[aid].social_networks), "重複あり"
        for f in friends:
            assert aid in sn[f], f"非対称: {aid}->{f} だが {f}->{aid} なし"


def test_social_networks_mean_degree_reasonable(gen_dir: Path) -> None:
    """平均次数が概ね 5 (Erdős-Rényi mean_degree=5 / §19.5.1)。"""
    profiles = load_agent_profiles(gen_dir / "agent_profiles_N100.json")
    total = sum(len(p.social_networks) for p in profiles)
    mean = total / len(profiles)
    assert 3.0 <= mean <= 7.0, f"平均次数 {mean} が想定範囲外"


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_main(tmp_path: Path) -> None:
    rc = main(["--seed", "42", "--out-dir", str(tmp_path), "--agents", "100", "--pois", "300"])
    assert rc == 0
    assert (tmp_path / "agent_profiles_N100.json").is_file()


def test_custom_agent_count_filename(tmp_path: Path) -> None:
    generate(tmp_path, seed=42, agents=50, pois=300)
    assert (tmp_path / "agent_profiles_N50.json").is_file()
    profiles = load_agent_profiles(
        tmp_path / "agent_profiles_N50.json",
        frozenset(p.id for p in load_pois(tmp_path / "pois.geojson")),
    )
    assert len(profiles) == 50


# ── WO-006: rich profile フィールド (surname/given/occupation/personality/hobbies/day_pattern) ─

def test_rich_profile_fields_present(tmp_path: Path) -> None:
    """全エージェントに surname/given/occupation/personality/hobbies/day_pattern が存在する。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        assert "surname" in agent, f"id={agent['id']}: surname 欠落"
        assert "given" in agent, f"id={agent['id']}: given 欠落"
        assert "occupation" in agent, f"id={agent['id']}: occupation 欠落"
        assert "personality" in agent, f"id={agent['id']}: personality 欠落"
        assert "hobbies" in agent, f"id={agent['id']}: hobbies 欠落"
        assert "day_pattern" in agent, f"id={agent['id']}: day_pattern 欠落"


def test_surname_given_consistent_with_name(tmp_path: Path) -> None:
    """surname + given を結合すると name と一致する。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        assert agent["name"] == agent["surname"] + agent["given"], (
            f"id={agent['id']}: name={agent['name']!r} != surname={agent['surname']!r}+given={agent['given']!r}"
        )


def test_rich_profile_deterministic_agents10(tmp_path: Path) -> None:
    """--agents 10 で seed 固定 → byte 一致再現 (WO-006 決定論要件)。"""
    d1, d2 = tmp_path / "r1", tmp_path / "r2"
    import hashlib
    generate(d1, seed=42, agents=10, pois=300)
    generate(d2, seed=42, agents=10, pois=300)
    fname = "agent_profiles_N10.json"
    h1 = hashlib.sha256((d1 / fname).read_bytes()).hexdigest()
    h2 = hashlib.sha256((d2 / fname).read_bytes()).hexdigest()
    assert h1 == h2, f"{fname} が byte 一致しない"


def test_occupation_is_string(tmp_path: Path) -> None:
    """occupation は非空文字列。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        assert isinstance(agent["occupation"], str) and agent["occupation"], (
            f"id={agent['id']}: occupation が空/非文字列"
        )


def test_personality_is_string(tmp_path: Path) -> None:
    """personality は非空文字列。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        assert isinstance(agent["personality"], str) and agent["personality"], (
            f"id={agent['id']}: personality が空/非文字列"
        )


def test_hobbies_is_nonempty_list_of_strings(tmp_path: Path) -> None:
    """hobbies は 1 件以上の文字列リスト。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        h = agent["hobbies"]
        assert isinstance(h, list) and len(h) >= 1, (
            f"id={agent['id']}: hobbies が空/非リスト: {h!r}"
        )
        assert all(isinstance(x, str) and x for x in h), (
            f"id={agent['id']}: hobbies に空/非文字列要素: {h!r}"
        )


def test_day_pattern_is_string(tmp_path: Path) -> None:
    """day_pattern は非空文字列 (例: 'morning', 'night', 'balanced')。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    for agent in raw:
        assert isinstance(agent["day_pattern"], str) and agent["day_pattern"], (
            f"id={agent['id']}: day_pattern が空/非文字列"
        )


def test_cli_agents10(tmp_path: Path) -> None:
    """--agents 10 で CLI が正常終了し rich profile フィールドが存在する。"""
    rc = main(["--seed", "42", "--out-dir", str(tmp_path), "--agents", "10", "--pois", "300"])
    assert rc == 0
    raw = json.loads((tmp_path / "agent_profiles_N10.json").read_text())
    assert len(raw) == 10
    for agent in raw:
        assert "surname" in agent
        assert "day_pattern" in agent


def test_rich_profile_loader_round_trip(tmp_path: Path) -> None:
    """生成した rich profile を data_loader が正常ロードできる (optional フィールドは extra or named)。"""
    generate(tmp_path, seed=42, agents=10, pois=300)
    pois = load_pois(tmp_path / "pois.geojson")
    poi_ids = frozenset(p.id for p in pois)
    profiles = load_agent_profiles(tmp_path / "agent_profiles_N10.json", poi_ids)
    assert len(profiles) == 10
    # surname/given/occupation/personality/hobbies/day_pattern は named field または extra に存在する
    for p in profiles:
        # named field として存在する場合
        if hasattr(p, "surname"):
            assert p.surname is not None
        else:
            # extra に格納されている場合
            assert "surname" in p.extra
