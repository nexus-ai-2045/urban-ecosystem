#!/usr/bin/env python3
"""urban_simulation_cli.py — WO-URBAN-004 ルールベースシミュレーション実行 CLI。

正本:
  - docs/ai-ecosystem-tool-spec.md §12.1 CLI 仕様 / §9 行動ルール / §13.3 検証
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

scope:
  profiles + POI から §9 のルールで agent_states.jsonl / poi_visit_records.jsonl /
  interaction_events.jsonl / summary.json を生成する。LLM は呼ばない。

使い方:
  # 静的データを内部生成してから simulate (--sample)
  python tools/urban_simulation_cli.py run --sample --out /tmp/urban_rule_run

  # 既存の静的データを入力に simulate
  python tools/urban_simulation_cli.py run \
      --pois data/pois.geojson \
      --profiles data/agent_profiles_N100.json \
      --seed 42 --out experiments/results/urban_demo

  --aois / --roadnet は MVP では summary 件数集計のみに使う (シミュレーションは
  直線補間移動のため road を使わない / §16 未決 #2)。

決定論:
  --seed で random.Random(seed) を初期化する。同一 seed・同一入力で 3 jsonl が
  byte 一致する (§13.3.2)。summary.json は started_at を含むため対象外。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

# urban-ecosystem ルートを import path に追加する。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from environments.urban_2d.data_loader import load_aois, load_roads  # noqa: E402
from environments.urban_2d.simulation import Simulation, load_inputs  # noqa: E402

# run_id バリデーション (spec §21.1 / パストラバーサル防止)
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _count_features(path: Path | None) -> int:
    """GeoJSON FeatureCollection の feature 件数を返す (無ければ 0)。"""
    if path is None or not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    feats = data.get("features") if isinstance(data, dict) else None
    return len(feats) if isinstance(feats, list) else 0


def _resolve_run_id(out_dir: Path) -> str:
    """--out 末尾ディレクトリ名から run_id を取得・検証する (spec §21.1)。"""
    run_id = out_dir.name
    if not _RUN_ID_RE.match(run_id):
        raise ValueError(
            f"run_id (--out 末尾) は ^[A-Za-z0-9_-]{{1,128}}$ に一致する必要があります: {run_id!r}"
        )
    return run_id


def _generate_sample(
    sample_dir: Path, *, seed: int, agents: int, pois: int, ticks: int
) -> Path:
    """generate_urban_sample.generate を呼び静的データを sample_dir に作る。

    入力データ生成は WO-URBAN-002 の責務 (tools/generate_urban_sample.py)。
    本 CLI は変更せず import して利用するだけ (scope 厳守)。
    """
    from tools.generate_urban_sample import generate as gen_sample

    gen_sample(
        sample_dir,
        seed=seed,
        agents=agents,
        pois=pois,
        ticks=ticks,
        run_id="urban_sample",
    )
    return sample_dir


def _run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    run_id = _resolve_run_id(out_dir)

    sample_tmp: tempfile.TemporaryDirectory | None = None
    aois_path = Path(args.aois) if args.aois else None
    roadnet_path = Path(args.roadnet) if args.roadnet else None

    if args.sample:
        # --sample: 静的データを一時 dir に内部生成してから simulate
        sample_tmp = tempfile.TemporaryDirectory(prefix="urban_sample_")
        sample_dir = _generate_sample(
            Path(sample_tmp.name),
            seed=args.seed,
            agents=args.agents,
            pois=args.pois_count,
            ticks=args.ticks,
        )
        pois_path = sample_dir / "pois.geojson"
        profiles_path = sample_dir / f"agent_profiles_N{args.agents}.json"
        aois_path = sample_dir / "aois.geojson"
        roadnet_path = sample_dir / "roadnet.geojson"
    else:
        if not args.pois or not args.profiles:
            print(
                "error: --sample 無しの場合は --pois と --profiles が必須です",
                file=sys.stderr,
            )
            return 2
        pois_path = Path(args.pois)
        profiles_path = Path(args.profiles)

    try:
        pois, profiles = load_inputs(pois_path, profiles_path)
        aoi_count = _count_features(aois_path)
        road_count = _count_features(roadnet_path)

        sim = Simulation(
            pois,
            profiles,
            seed=args.seed,
            ticks=args.ticks,
            run_id=run_id,
            aois=aoi_count,
            roads=road_count,
        )
        summary = sim.run(out_dir)
    finally:
        if sample_tmp is not None:
            sample_tmp.cleanup()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="urban-ecosystem ルールベースシミュレーション (§9 / WO-URBAN-004)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="シミュレーションを実行する")
    run_p.add_argument("--sample", action="store_true",
                       help="静的データを内部生成してから simulate する")
    run_p.add_argument("--pois", help="pois.geojson のパス (--sample 無しで必須)")
    run_p.add_argument("--profiles", help="agent_profiles_*.json のパス (--sample 無しで必須)")
    run_p.add_argument("--aois", help="aois.geojson のパス (任意 / summary 件数のみ)")
    run_p.add_argument("--roadnet", help="roadnet.geojson のパス (任意 / summary 件数のみ)")
    run_p.add_argument("--seed", type=int, default=42, help="乱数 seed (既定 42)")
    run_p.add_argument("--ticks", type=int, default=24, help="シミュレーション tick 数 (既定 24)")
    run_p.add_argument("--agents", type=int, default=100,
                       help="--sample 生成時のエージェント数 (既定 100)")
    run_p.add_argument("--sample-pois", dest="pois_count", type=int, default=300,
                       help="--sample 生成時の POI 数 (既定 300)")
    run_p.add_argument("--out", required=True, help="出力ディレクトリ (末尾が run_id)")
    run_p.set_defaults(func=_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
