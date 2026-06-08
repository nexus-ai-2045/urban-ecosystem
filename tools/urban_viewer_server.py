"""
urban_viewer_server.py — Urban Ecosystem リプレイビューア FastAPI サーバー。

正本: docs/ai-ecosystem-tool-spec.md §17.3 / §21

エンドポイント:
  GET /                 ビューア HTML (GOOGLE_MAPS_API_KEY 注入 or fallback)
  GET /static/{path}    静的アセット (JS/CSS)
  GET /api/health       ヘルスチェック
  GET /api/runs         利用可能 run_id 一覧
  POST /api/runs        小規模 sample simulation run 生成
  GET /api/operator-mode        operator viewpoint state
  POST /api/operator-mode/entry agent inspection viewpoint に入る
  POST /api/operator-mode/return replay viewpoint に戻る
  GET /api/world-bridge         三層 world bridge state
  POST /api/world-bridge/transition world layer を移動する
  GET /api/agent-roster         guide / partner などの抽象role state
  POST /api/agent-roster/select active role を選択する
  GET /api/motif-arcs           public-safe motif arc pack
  POST /api/motif-arcs/evaluate motif arc の受け入れ条件を確認する
  GET /api/assessment-lab       assessment / benchmark category state
  POST /api/assessment-lab/evaluate benchmark category を評価する
  GET /api/governance-fde       governance / FDE packet state
  POST /api/governance-fde/decide FDE decision packet を評価する
  GET /api/repo-skill-mesh      repo-as-skill / distributed ops guard state
  POST /api/repo-skill-mesh/evaluate skill call / distributed ops plan を評価する
  GET /api/intake-lifecycle     intake / worldbuilding / lifecycle guard state
  POST /api/intake-lifecycle/draft intake draft candidate を評価する
  GET /api/settings     ランタイム設定状態 (秘密値は返さない)
  POST /api/settings    ランタイム設定更新 (process-local / 永続保存なし)
  GET /api/data/{run_id}/{file}  データファイル配信 (許可リスト 11 件)

セキュリティ:
  - GOOGLE_MAPS_API_KEY はサーバー env から読み、HTML に注入する。
    コード・git・ログに平文で出さない (§5.1.1)。
  - run_id / file のパストラバーサル防止: 許可リスト方式 (§21.3.1)。
  - CORS: 同一オリジン (§21.6)。CORSMiddleware は追加しない。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.llm_provider import make_llm_provider
from environments.urban_2d.data_loader import load_roads
from environments.urban_2d.road_graph import build_road_graph
from environments.urban_2d.simulation import Simulation, load_inputs
from tools.generate_urban_sample import generate as generate_sample
from tools.urban_viewer.labels import ALL_LABELS

# ─────────────────────────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────────────────────────

# 許可ファイル一覧 (§21.3.1 / data-contract §File Names)
ALLOWED_FILES: frozenset[str] = frozenset({
    "pois.geojson",
    "aois.geojson",
    "roadnet.geojson",
    "agent_profiles_N100.json",
    "activity_plans.jsonl",
    "agent_states.jsonl",
    "poi_visit_records.jsonl",
    "interaction_events.jsonl",
    "relationships.jsonl",
    "summary.json",
    "metrics.json",
})

# agent_profiles_N<N>.json は可変エージェント数 (N=10 等) に対応するため正規表現で許可する。
# パストラバーサルは _validate_run_and_file の ".." / "/" チェックで別途防止済み (数字のみ許容)。
AGENT_PROFILES_RE = re.compile(r"^agent_profiles_N\d+\.json$")

# ファイル拡張子 -> Content-Type
CONTENT_TYPES: dict[str, str] = {
    ".geojson": "application/geo+json",
    ".json":    "application/json",
    ".jsonl":   "application/x-ndjson",
}

# 現在の viewer API は local data source のみ実装済み。
SUPPORTED_DATA_SOURCES: frozenset[str] = frozenset({"local"})

# UI から変更されたランタイム設定。ファイルには保存しない。
_RUNTIME_CONFIG: dict[str, str] = {}

# MVP-001 Sentinel Operator Entry: process-local の toy state。
# replay data や simulation state は変更しない。
_OPERATOR_MODE_STATE: dict[str, object] = {
    "viewpoint": "replay",
    "status": "idle",
    "run_id": "",
    "agent_id": None,
    "trigger_class": "",
    "failure_state": "",
    "message": "replay viewpoint",
}
_OPERATOR_TRIGGER_CLASSES: frozenset[str] = frozenset({
    "entry_intent",
    "operator_entry",
    "wake_phrase_class",
})

# MVP-002 World Bridge State Model: process-local の toy state。
# data contract と replay / simulation state は変更しない。
WORLD_LAYERS: tuple[str, ...] = ("physical", "simulated", "liminal")
MINIMUM_WORLD_PACKET_FIELDS: tuple[str, ...] = (
    "place_and_environment",
    "rules_of_possibility",
    "social_fabric",
    "resources_and_power",
    "history_and_memory",
    "daily_life_signal",
    "change_pressure",
)
_WORLD_BRIDGE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("simulated", "liminal"),
    ("liminal", "simulated"),
    ("liminal", "physical"),
    ("physical", "liminal"),
})
_WORLD_LAYER_DESCRIPTIONS: dict[str, str] = {
    "physical": "現実側の観測、制約、人間レビューを扱うlayer。",
    "simulated": "replay、agent state、scenario stateを観測するlayer。",
    "liminal": "physical と simulated の間で、entry gate と return gateを扱う境界layer。",
}
_MINIMUM_WORLD_PACKET: dict[str, dict[str, object]] = {
    "place_and_environment": {"ready": True, "note": "run dataと地図表示の観測対象がある。"},
    "rules_of_possibility": {"ready": True, "note": "viewerは観測用で、simulation stateを直接変更しない。"},
    "social_fabric": {"ready": True, "note": "agent profile、role、visit recordを観測できる。"},
    "resources_and_power": {"ready": True, "note": "API、runtime settings、human gateの境界を分ける。"},
    "history_and_memory": {"ready": True, "note": "replay tickとrun summaryを履歴として扱う。"},
    "daily_life_signal": {"ready": True, "note": "移動、訪問、時刻、選択agentを日常信号として表示する。"},
    "change_pressure": {"ready": True, "note": "layer transition要求を変化圧として扱う。"},
}
_WORLD_BRIDGE_STATE: dict[str, object] = {
    "current_layer": "simulated",
    "previous_layer": "",
    "status": "ready",
    "failure_state": "",
    "message": "simulated layer",
}
_EVENT_MUSIC_SIGNAL: dict[str, object] = {
    "status": "planned_signal",
    "available": False,
    "message": "8-bit cueは後続MVP候補。ここでは体験信号だけを表示する。",
}

# MVP-003 Guide And Agent Roster: process-local の抽象role state。
# 実人物、作品由来role、現実の監視/追跡手順は扱わない。
AGENT_ROSTER_ROLES: tuple[str, ...] = (
    "guide",
    "partner",
    "monitoring",
    "pursuit",
    "intervention",
    "field-support",
    "supervisor",
)
_AGENT_ROSTER_DEFINITIONS: dict[str, dict[str, object]] = {
    "guide": {
        "responsibility": "operatorへ現在状態を説明する。",
        "layer": "liminal",
        "can": "world layer、entry state、次の安全な選択肢を説明する。",
        "cannot": "operatorの代わりに決定しない。",
    },
    "partner": {
        "responsibility": "operatorの意図を整理する。",
        "layer": "liminal",
        "can": "目的、迷い、戻り先を言語化する。",
        "cannot": "agent controlを実行しない。",
    },
    "monitoring": {
        "responsibility": "replay内の変化を観測する。",
        "layer": "simulated",
        "can": "anomaly、stale、heartbeat欠落をtoy replay内で検出する。",
        "cannot": "現実の監視手順を提供しない。",
    },
    "pursuit": {
        "responsibility": "simulation内の対象推移を追う。",
        "layer": "simulated",
        "can": "toy replay上の対象agentやevent chainを追う。",
        "cannot": "real-world trackingに接続しない。",
    },
    "intervention": {
        "responsibility": "安全な介入候補を提示する。",
        "layer": "liminal",
        "can": "safe action候補、rollback候補、gate理由を示す。",
        "cannot": "直接stateを変更しない。",
    },
    "field-support": {
        "responsibility": "physical layer由来の制約を説明する。",
        "layer": "physical",
        "can": "human approval、cost、運用制約を説明する。",
        "cannot": "cloudや外部APIを勝手に実行しない。",
    },
    "supervisor": {
        "responsibility": "role間の衝突を調停する。",
        "layer": "liminal",
        "can": "gate、責任境界、handoff先を整理する。",
        "cannot": "user oversightを置き換えない。",
    },
}
_AGENT_ROSTER_STATE: dict[str, object] = {
    "active_role": "guide",
    "status": "ready",
    "failure_state": "",
    "message": "guide role ready",
}

# MVP-004 Motif Arc Pack: public-safe motif の受け入れ判定。
MOTIF_ARC_IDS: tuple[str, ...] = (
    "equivalent-exchange-pair",
    "pillar-council-arc",
    "unstable-power-arc",
    "boundary-war-arc",
    "fighter-archetype-set",
    "social-tech-mirror-lab",
    "judgment-game-arc",
    "ecological-mediation-arc",
    "pilot-sync-arc",
    "next-motif-expansion-slot",
)
_MOTIF_ARCS: dict[str, dict[str, object]] = {
    "equivalent-exchange-pair": {
        "name": "Equivalent Exchange Pair",
        "core": "cost、restoration、pair dependency",
        "archetypes": ["relationship pattern", "pressure source", "recovery path"],
        "world_fields": ["rules_of_possibility", "resources_and_power", "history_and_memory"],
        "gate": "public-safe naming review",
    },
    "pillar-council-arc": {
        "name": "Pillar Council Arc",
        "core": "guardian、council、patron、corruption-prime structure",
        "archetypes": ["actor role", "relationship pattern", "pressure source"],
        "world_fields": ["social_fabric", "resources_and_power", "change_pressure"],
        "gate": "public-safe naming review",
    },
    "unstable-power-arc": {
        "name": "Unstable Power Arc",
        "core": "city-scale instability、uncontrolled power、containment dynamics",
        "archetypes": ["pressure source", "failure mode", "transition path"],
        "world_fields": ["place_and_environment", "rules_of_possibility", "change_pressure"],
        "gate": "safety review",
    },
    "boundary-war-arc": {
        "name": "Boundary War Arc",
        "core": "boundary logic、external pressure、protector、strategist、elite intervention",
        "archetypes": ["actor role", "pressure source", "relationship pattern"],
        "world_fields": ["place_and_environment", "social_fabric", "history_and_memory"],
        "gate": "public-safe naming review",
    },
    "fighter-archetype-set": {
        "name": "Fighter Archetype Set",
        "core": "discipline、rivalry、precision、training、event-duel",
        "archetypes": ["actor role", "relationship pattern", "recovery path"],
        "world_fields": ["daily_life_signal", "rules_of_possibility", "change_pressure"],
        "gate": "public-safe naming review",
    },
    "social-tech-mirror-lab": {
        "name": "Social-Tech Mirror Lab",
        "core": "technology distortion、identity、trust、short scenario",
        "archetypes": ["pressure source", "failure mode", "relationship pattern"],
        "world_fields": ["social_fabric", "daily_life_signal", "change_pressure"],
        "gate": "social-risk review",
    },
    "judgment-game-arc": {
        "name": "Judgment Game Arc",
        "core": "judgment、surveillance、inference、counter-inference",
        "archetypes": ["actor role", "pressure source", "failure mode"],
        "world_fields": ["rules_of_possibility", "social_fabric", "resources_and_power"],
        "gate": "safety review",
    },
    "ecological-mediation-arc": {
        "name": "Ecological Mediation Arc",
        "core": "environmental negotiation、swarm intelligence、non-human agency",
        "archetypes": ["actor role", "relationship pattern", "transition path"],
        "world_fields": ["place_and_environment", "social_fabric", "history_and_memory"],
        "gate": "world packet review",
    },
    "pilot-sync-arc": {
        "name": "Pilot Sync Arc",
        "core": "synchronization threshold、bio-machine pressure、identity strain",
        "archetypes": ["relationship pattern", "pressure source", "failure mode"],
        "world_fields": ["rules_of_possibility", "social_fabric", "change_pressure"],
        "gate": "public-safe naming review",
    },
    "next-motif-expansion-slot": {
        "name": "Next Motif Expansion Slot",
        "core": "future motif intake with TODO or explicit classification",
        "archetypes": ["transition path", "pressure source", "recovery path"],
        "world_fields": list(MINIMUM_WORLD_PACKET_FIELDS),
        "gate": "human review",
    },
}
_MOTIF_ARC_STATE: dict[str, object] = {
    "active_motif_id": "equivalent-exchange-pair",
    "status": "ready",
    "failure_state": "",
    "message": "motif arc ready",
}

# MVP-005 Assessment And Benchmark Lab: deceptionや危険live testではなく、
# 境界認識・意図推定・harness品質をtoy benchmarkとして扱う。
ASSESSMENT_CATEGORY_IDS: tuple[str, ...] = (
    "human-ai-assessment-lab",
    "post-singularity-scenario-boundary",
    "chaotic-three-body-world-benchmark",
    "frontier-ai-capability-layer-benchmark",
    "scale-simplification-simulation-benchmark",
    "agent-harness-layer-benchmark",
)
_ASSESSMENT_CATEGORIES: dict[str, dict[str, object]] = {
    "human-ai-assessment-lab": {
        "name": "Human/AI Assessment Lab",
        "evaluates": "human-likeness、intention inference、boundary recognition",
        "input": "toy dialogue、operator intent、role state",
        "output": "calibrated assessment note",
        "fail": "deception誘導、人格詐称、境界曖昧化",
    },
    "post-singularity-scenario-boundary": {
        "name": "Post-Singularity Scenario Boundary",
        "evaluates": "bounded scenario familyと不確実性",
        "input": "assumptions、known limits、failure conditions",
        "output": "scenario boundary card",
        "fail": "予言化、確定未来扱い、危険な実行案",
    },
    "chaotic-three-body-world-benchmark": {
        "name": "Chaotic Three-Body World Benchmark",
        "evaluates": "initial-condition sensitivity、stable-window",
        "input": "small changes in world packet",
        "output": "stability comparison",
        "fail": "protected narrative再現、物理/数学の断定ミス",
    },
    "frontier-ai-capability-layer-benchmark": {
        "name": "Frontier AI Capability Layer Benchmark",
        "evaluates": "long-horizon autonomy、tool use、governance gate",
        "input": "capability layer checklist",
        "output": "safe capability map",
        "fail": "lab/model ranking、private capability claim",
    },
    "scale-simplification-simulation-benchmark": {
        "name": "Scale-Simplification Simulation Benchmark",
        "evaluates": "micro social layerとmacro physical layerの対応",
        "input": "simplified scenario pair",
        "output": "scale mapping note",
        "fail": "external post body引用、過度な一般化",
    },
    "agent-harness-layer-benchmark": {
        "name": "Agent Harness Layer Benchmark",
        "evaluates": "model capabilityとharness qualityの分離",
        "input": "goals、permissions、tool routing、recovery checks",
        "output": "harness assessment card",
        "fail": "modelだけに責任を寄せる、approval UX欠落",
    },
}
_ASSESSMENT_LAB_STATE: dict[str, object] = {
    "active_category_id": "human-ai-assessment-lab",
    "status": "ready",
    "failure_state": "",
    "message": "assessment lab ready",
}

# MVP-006 Governance And Fractal Decision: user oversightをagent化せず、
# FDE packetでproposal / review / execution / oversightを分ける。
GOVERNANCE_LAYER_IDS: tuple[str, ...] = ("proposal", "review", "execution", "oversight")
FDE_STEP_IDS: tuple[str, ...] = ("entry", "packet", "evidence", "decision", "closure")
FDE_DECISION_IDS: tuple[str, ...] = ("proceed", "revise", "watch", "parking-lot", "reject")
_GOVERNANCE_LAYERS: dict[str, dict[str, str]] = {
    "proposal": {
        "name": "Proposal Branch",
        "responsibility": "変更案を作る",
        "input": "TODO、benchmark result、operator intent",
        "output": "proposal packet",
        "gate": "source category review",
    },
    "review": {
        "name": "Review Branch",
        "responsibility": "証拠とriskを確認する",
        "input": "proposal packet、tests、drift checks",
        "output": "review note",
        "gate": "governance review",
    },
    "execution": {
        "name": "Execution Branch",
        "responsibility": "承認済み作業だけ実行する",
        "input": "reviewed proposal、allowed write paths",
        "output": "PR / docs / work order",
        "gate": "human gate",
    },
    "oversight": {
        "name": "User Oversight",
        "responsibility": "公開境界と異議申し立てを保持する",
        "input": "PR state、release state、user instruction",
        "output": "approval / stop / rollback request",
        "gate": "user oversight",
    },
}
_FDE_STEPS: dict[str, dict[str, str]] = {
    "entry": {
        "name": "Entry",
        "meaning": "何を判断するかを明確にする",
    },
    "packet": {
        "name": "Packet",
        "meaning": "source category、scope、allowed write paths、gateを束ねる",
    },
    "evidence": {
        "name": "Evidence",
        "meaning": "tests、CI、static scan、human review statusを集める",
    },
    "decision": {
        "name": "Decision",
        "meaning": "proceed、revise、watch、parking-lot、rejectを選ぶ",
    },
    "closure": {
        "name": "Closure",
        "meaning": "merge、handoff、next MVP、rollback conditionを記録する",
    },
}

# MVP-007 Repo-as-Skill And Distributed Ops: 実際のrecursive call / P2P / cloud実行ではなく、
# guardが揃った計画かどうかだけをstatelessに評価する。
SKILL_FAMILY_IDS: tuple[str, ...] = (
    "operator-entry-skill",
    "world-bridge-skill",
    "guide-roster-skill",
    "motif-intake-skill",
    "assessment-skill",
    "governance-skill",
    "distributed-ops-skill",
    "intake-lifecycle-skill",
)
_SKILL_FAMILIES: dict[str, dict[str, str]] = {
    "operator-entry-skill": {
        "responsibility": "entry / return / trigger boundary",
        "guard": "human gate、public-safe trigger",
    },
    "world-bridge-skill": {
        "responsibility": "world layer / Minimum World Packet",
        "guard": "data contract review",
    },
    "guide-roster-skill": {
        "responsibility": "guide / partner / monitoring / intervention",
        "guard": "role boundary",
    },
    "motif-intake-skill": {
        "responsibility": "motif acceptance / parking-lot",
        "guard": "public-safe naming gate",
    },
    "assessment-skill": {
        "responsibility": "benchmark / harness assessment",
        "guard": "safety review",
    },
    "governance-skill": {
        "responsibility": "FDE packet / oversight",
        "guard": "user oversight",
    },
    "distributed-ops-skill": {
        "responsibility": "P2P / cloud capacity planning",
        "guard": "trust / cost / approval gate",
    },
    "intake-lifecycle-skill": {
        "responsibility": "add request / stale / heartbeat",
        "guard": "draft-only automation gate",
    },
}

# MVP-008 Intake Lifecycle And Worldbuilding Pipeline: 外部writeではなく、
# source -> public-safe candidate -> TODO/gate のdraft化だけをstatelessに評価する。
INTAKE_REQUEST_CLASSES: tuple[str, ...] = ("accepted", "parking-lot", "watch", "rejected/out-of-scope")
INTAKE_SOURCE_CATEGORIES: tuple[str, ...] = (
    "project-hypothesis",
    "public-policy",
    "external-benchmark",
    "local-source-abstraction",
    "chat-context",
)
_INTAKE_PIPELINE_STEPS: tuple[dict[str, str], ...] = (
    {"step": "receive", "output": "request stub", "gate": "source containment"},
    {"step": "classify", "output": "context idea class", "gate": "classification required"},
    {"step": "source_category", "output": "source category", "gate": "public-safe source"},
    {"step": "public_safe_name", "output": "abstract name", "gate": "naming validator"},
    {"step": "minimum_world_packet", "output": "world packet", "gate": "world richness"},
    {"step": "todo_or_gate", "output": "TODO ID or watch reason", "gate": "coverage guarantee"},
    {"step": "draft_artifact", "output": "docs/work-order candidate", "gate": "human review"},
    {"step": "optional_external_issue", "output": "approved external write only", "gate": "explicit approval"},
)
_INTAKE_VALIDATOR_RULES: tuple[dict[str, str], ...] = (
    {"rule": "protected_names", "rejects": "protected names as implementation IDs"},
    {"rule": "private_paths", "rejects": "private absolute paths"},
    {"rule": "external_post_body", "rejects": "quoted external post body"},
    {"rule": "secret_like_strings", "rejects": "secret-like strings"},
    {"rule": "todo_coverage", "rejects": "accepted idea without TODO ID"},
    {"rule": "source_category", "rejects": "TODO without source category"},
)
INTAKE_WORLD_PACKET_FIELDS: tuple[str, ...] = (
    "world_layer",
    "actor_role",
    "conflict",
    "constraint",
    "signal",
    "transition",
    "failure_state",
)

# run_id バリデーション正規表現 (§21.1)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

# プレースホルダ文字列 (index.html 内のプレースホルダ)
_PLACEHOLDER_KEY     = "%%GOOGLE_MAPS_API_KEY%%"
_PLACEHOLDER_MAP_ID  = "%%GOOGLE_MAPS_MAP_ID%%"
_PLACEHOLDER_SCRIPT  = "%%MAPS_SCRIPT_TAG%%"

# ─────────────────────────────────────────────────────────────────────────────
# 設定 (環境変数)
# ─────────────────────────────────────────────────────────────────────────────

def _get_maps_api_key() -> str:
    """GOOGLE_MAPS_API_KEY を環境変数から取得する。未設定時は空文字列。"""
    return _RUNTIME_CONFIG.get("GOOGLE_MAPS_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", "")).strip()


def _get_maps_map_id() -> str:
    """GOOGLE_MAPS_MAP_ID を環境変数から取得する。未設定時は空文字列。"""
    return _RUNTIME_CONFIG.get("GOOGLE_MAPS_MAP_ID", os.environ.get("GOOGLE_MAPS_MAP_ID", "")).strip()


def _get_data_source() -> str:
    """DATA_SOURCE 環境変数。現時点の実装済み値は 'local' のみ。"""
    return _RUNTIME_CONFIG.get("DATA_SOURCE", os.environ.get("DATA_SOURCE", "local"))


def _get_data_root() -> Path:
    """ローカルデータルートディレクトリ。DATA_DIR env or デフォルト data/。"""
    data_dir = _RUNTIME_CONFIG.get("DATA_DIR", os.environ.get("DATA_DIR", ""))
    if data_dir:
        return Path(data_dir).expanduser()
    # urban-ecosystem ルートの data/ ディレクトリ
    return Path(__file__).parent.parent / "data"


def _get_llm_provider() -> str:
    """LLM_PROVIDER。現シミュレーション CLI の既定は rule。"""
    return _RUNTIME_CONFIG.get("LLM_PROVIDER", os.environ.get("LLM_PROVIDER", "rule")).strip() or "rule"


def _get_llm_model() -> str:
    """LLM_MODEL。ローカル/クラウド provider の任意表示設定。"""
    return _RUNTIME_CONFIG.get("LLM_MODEL", os.environ.get("LLM_MODEL", "")).strip()


def _get_llm_base_url() -> str:
    """LLM_BASE_URL。ローカル OpenAI-compatible server 等の任意表示設定。"""
    return _RUNTIME_CONFIG.get("LLM_BASE_URL", os.environ.get("LLM_BASE_URL", "")).strip()


def _get_llm_model_dir() -> str:
    """LLM_MODEL_DIR。ローカルモデルディレクトリの任意表示設定。"""
    return _RUNTIME_CONFIG.get("LLM_MODEL_DIR", os.environ.get("LLM_MODEL_DIR", "")).strip()


def _get_google_cloud_project() -> str:
    """GOOGLE_CLOUD_PROJECT。Vertex AI 利用時のプロジェクト設定。"""
    return _RUNTIME_CONFIG.get(
        "GOOGLE_CLOUD_PROJECT",
        os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    ).strip()


def _set_runtime_value(name: str, value: object) -> None:
    """UI から受け取った設定値を process-local に保存する。"""
    if value is None:
        _RUNTIME_CONFIG.pop(name, None)
        return
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{name} must be a string")
    cleaned = value.strip()
    if cleaned:
        _RUNTIME_CONFIG[name] = cleaned
    else:
        _RUNTIME_CONFIG.pop(name, None)


def _settings_body() -> dict:
    """UI 表示用の設定状態を返す。秘密値そのものは返さない。"""
    data_root = _get_data_root().expanduser()
    llm_provider = _get_llm_provider()
    llm_model_dir = _get_llm_model_dir()
    api_key = _get_maps_api_key()
    map_id = _get_maps_map_id()
    google_project = _get_google_cloud_project()
    data_source = _get_data_source()
    return {
        "maps": {
            "api_key": "present" if api_key else "absent",
            "map_id": "" if map_id == "DEMO_MAP_ID" else map_id,
            "map_id_state": (
                "demo" if map_id == "DEMO_MAP_ID"
                else "present" if map_id
                else "absent"
            ),
            "env": {
                "api_key": "GOOGLE_MAPS_API_KEY",
                "map_id": "GOOGLE_MAPS_MAP_ID",
            },
        },
        "data": {
            "source": data_source,
            "source_supported": data_source in SUPPORTED_DATA_SOURCES,
            "root": str(data_root),
            "root_exists": data_root.is_dir(),
            "env": {
                "source": "DATA_SOURCE",
                "root": "DATA_DIR",
            },
        },
        "llm": {
            "provider": llm_provider,
            "provider_supported": llm_provider in {"rule", "local", "vertex"},
            "model": _get_llm_model(),
            "base_url": _get_llm_base_url(),
            "model_dir": llm_model_dir,
            "model_dir_exists": bool(llm_model_dir) and Path(llm_model_dir).expanduser().is_dir(),
            "env": {
                "provider": "LLM_PROVIDER",
                "model": "LLM_MODEL",
                "base_url": "LLM_BASE_URL",
                "model_dir": "LLM_MODEL_DIR",
            },
        },
        "cloud": {
            "google_cloud_project": google_project,
            "google_cloud_project_state": "present" if google_project else "absent",
            "env": {
                "project": "GOOGLE_CLOUD_PROJECT",
            },
        },
        "runtime_only": True,
    }


def _make_configured_llm_provider():
    """現在の runtime settings から LLMProvider を作る。"""
    provider = _get_llm_provider()
    if provider == "rule":
        return make_llm_provider("rule")
    if provider == "local":
        model_name = _get_llm_model() or _get_llm_model_dir() or "local-model"
        return make_llm_provider(
            "local",
            base_url=_get_llm_base_url() or "http://127.0.0.1:11434/v1",
            model=model_name,
        )
    if provider == "vertex":
        project = _get_google_cloud_project()
        if not project:
            raise HTTPException(
                status_code=400,
                detail="GOOGLE_CLOUD_PROJECT is required when LLM_PROVIDER=vertex",
            )
        return make_llm_provider(
            "vertex",
            project=project,
            model=_get_llm_model() or "gemini-2.5-flash",
        )
    raise HTTPException(status_code=400, detail="LLM_PROVIDER must be rule, local, or vertex")


def _require_int_range(body: dict, key: str, default: int, *, minimum: int, maximum: int) -> int:
    """JSON body から整数を取り、範囲検証する。"""
    raw = body.get(key, default)
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise HTTPException(status_code=400, detail=f"{key} must be an integer")
    if raw < minimum or raw > maximum:
        raise HTTPException(status_code=400, detail=f"{key} must be between {minimum} and {maximum}")
    return raw


def _create_sample_run(body: dict) -> dict:
    """sample 入力を生成して simulation run を作る。"""
    run_id = body.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="run_id must match ^[A-Za-z0-9_-]{1,128}$")

    seed = _require_int_range(body, "seed", 42, minimum=0, maximum=2_147_483_647)
    agents = _require_int_range(body, "agents", 100, minimum=1, maximum=1_000)
    pois = _require_int_range(body, "pois", 300, minimum=3, maximum=2_000)
    ticks = _require_int_range(body, "ticks", 288, minimum=1, maximum=2_016)

    data_root = _get_data_root().expanduser()
    data_root.mkdir(parents=True, exist_ok=True)
    out_dir = data_root / run_id
    if out_dir.exists():
        raise HTTPException(status_code=409, detail=f"run already exists: {run_id}")

    created_run_dir = False
    try:
        generate_sample(
            out_dir,
            seed=seed,
            agents=agents,
            pois=pois,
            ticks=ticks,
            run_id=run_id,
        )
        created_run_dir = True
        pois_path = out_dir / "pois.geojson"
        profiles_path = out_dir / f"agent_profiles_N{agents}.json"
        aois_path = out_dir / "aois.geojson"
        roadnet_path = out_dir / "roadnet.geojson"
        loaded_pois, profiles = load_inputs(pois_path, profiles_path)
        roads = load_roads(roadnet_path)
        road_graph = build_road_graph(roads)
        provider = _make_configured_llm_provider()
        sim = Simulation(
            loaded_pois,
            profiles,
            seed=seed,
            ticks=ticks,
            run_id=run_id,
            aois=_count_features(aois_path),
            roads=_count_features(roadnet_path),
            road_graph=road_graph,
            llm_provider=provider,
        )
        summary = sim.run(out_dir)
    except HTTPException:
        if created_run_dir:
            shutil.rmtree(out_dir, ignore_errors=True)
        raise
    except Exception as exc:
        if created_run_dir:
            shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "run": summary,
        "settings": _settings_body(),
    }


def _data_source_error(data_source: str) -> str:
    """未対応 DATA_SOURCE の説明を返す。"""
    if data_source == "gcs":
        return (
            "DATA_SOURCE=gcs is configured, but GCS serving is not implemented. "
            "Use DATA_SOURCE=local until GCS support is wired."
        )
    return (
        f"Unsupported DATA_SOURCE={data_source!r}. "
        "Supported values in this build: local."
    )


def _ensure_data_source_supported() -> None:
    """ローカル以外の DATA_SOURCE を明示的な 501 にする。"""
    data_source = _get_data_source()
    if data_source not in SUPPORTED_DATA_SOURCES:
        raise HTTPException(status_code=501, detail=_data_source_error(data_source))


def _js_string_literal(value: str) -> str:
    """環境変数値を JavaScript string literal として安全に埋め込む。"""
    return json.dumps(value, ensure_ascii=False)


def _replace_js_placeholder_literal(source: str, placeholder: str, value: str) -> str:
    """`"%%PLACEHOLDER%%"` 形式を JSON-safe な JS literal に置き換える。"""
    return source.replace(f'"{placeholder}"', _js_string_literal(value))


def _path_is_within(path: Path, root: Path) -> bool:
    """resolve 済み path が resolve 済み root 配下にあるかを返す。"""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# HTML 生成 (APIキー注入 / §5.1.1)
# ─────────────────────────────────────────────────────────────────────────────

_VIEWER_HTML_PATH = Path(__file__).parent / "urban_viewer" / "index.html"


def _build_viewer_html(api_key: str, map_id: str) -> str:
    """index.html のプレースホルダを置き換えてレスポンス HTML を生成する。

    api_key が空の場合:
      - %%GOOGLE_MAPS_API_KEY%% はそのまま残す → app.js が fallback を検出。
      - %%MAPS_SCRIPT_TAG%% は空文字に置き換える (Maps bootstrap loader を出力しない)。

    api_key が設定されている場合:
      - %%GOOGLE_MAPS_API_KEY%% を注入する。
      - %%MAPS_SCRIPT_TAG%% に bootstrap loader の <script> タグを注入する。
      - キー値はログに出力しない。
    """
    html = _VIEWER_HTML_PATH.read_text(encoding="utf-8")

    if api_key:
        # Maps JavaScript API bootstrap loader タグ (§5.1.3)。
        # Google 公式の inline bootstrap loader パターン。
        # バックティック文字列は JavaScript テンプレートリテラルなので
        # Python f-string ではなく str.format を使わずそのまま連結する。
        js_loader = (
            "(g=>{var h,a,k,"
            'p="The Google Maps JavaScript API",'
            'c="google",l="importLibrary",q="__ib__",'
            "m=document,b=window;"
            "b=b[c]||(b[c]={});"
            "var d=b.maps||(b.maps={}),"
            "r=new Set,"
            "e=new URLSearchParams,"
            "u=()=>h||(h=new Promise(async(f,n)=>{"
            'await (a=m.createElement("script"));'
            'e.set("libraries",[...r]+"");'
            "for(k in g)e.set(k.replace(/[A-Z]/g,t=>\"_\"+t[0].toLowerCase()),g[k]);"
            'e.set("callback",c+".maps."+q);'
            # JavaScript テンプレートリテラル (バックティック) をそのまま埋め込む
            "a.src=`https://maps.googleapis.com/maps/api/js?`+e;"
            "d[q]=f;"
            'a.onerror=()=>h=n(Error(p+" could not load."));'
            "a.nonce=m.querySelector(\"script[nonce]\")?.nonce||\"\";"
            "m.head.append(a)}));"
            'd[l]?console.warn(p+" only loads once. Ignoring:",g):'
            "(d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n)))})"
        )
        usable_map_id = bool(map_id and map_id != "DEMO_MAP_ID")
        js_config_parts = ["key: " + _js_string_literal(api_key)]
        if usable_map_id:
            js_config_parts.append("mapIds: [" + _js_string_literal(map_id) + "]")
        js_config = "{" + ", ".join(js_config_parts) + "}"
        script_tag = (
            "<script>\n"
            "  " + js_loader + "(" + js_config + ");\n"
            "</script>"
        )
        html = html.replace(_PLACEHOLDER_SCRIPT, script_tag)
        html = _replace_js_placeholder_literal(html, _PLACEHOLDER_KEY, api_key)
        if not usable_map_id:
            # API key 設定済みだが GOOGLE_MAPS_MAP_ID 未設定/DEMO_MAP_ID → Map ID は注入しない。
            # Advanced Marker は使わず、クライアント側で通常 Marker に落とす。
            logging.getLogger(__name__).warning(
                "GOOGLE_MAPS_MAP_ID 未設定または DEMO_MAP_ID: 通常 Marker で Google Maps を表示します"
            )
        map_id_val = map_id if usable_map_id else ""
        html = _replace_js_placeholder_literal(html, _PLACEHOLDER_MAP_ID, map_id_val)
    else:
        # キー未設定: Maps スクリプトを出力しない / プレースホルダをそのまま残す
        # app.js はプレースホルダ文字列を検出して fallback アダプタに切り替える
        html = html.replace(_PLACEHOLDER_SCRIPT, "<!-- Maps API key not set: using fallback map -->")
        # _PLACEHOLDER_KEY と _PLACEHOLDER_MAP_ID はそのまま残す

    return html

# ─────────────────────────────────────────────────────────────────────────────
# run 列挙 (§21.1 / §21.2)
# ─────────────────────────────────────────────────────────────────────────────

def _list_runs() -> list[dict]:
    """data/ 配下で summary.json を持つディレクトリを run として列挙する。

    §21.1: summary.json の存在をマニフェスト代わりとする。
    §21.2: runs 配列は started_at 降順。
    """
    _ensure_data_source_supported()
    data_root = _get_data_root()
    runs = []

    if not data_root.is_dir():
        return runs

    for subdir in sorted(data_root.iterdir()):
        if not subdir.is_dir():
            continue
        summary_path = subdir / "summary.json"
        if not summary_path.exists():
            continue
        run_id = subdir.name
        if not RUN_ID_RE.match(run_id):
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # API の run_id は /api/data/{run_id}/... でロード可能なディレクトリ名に固定する。
        summary_run_id = summary.get("run_id")
        run = {
            "run_id":      run_id,
            "seed":        summary.get("seed",         0),
            "ticks":       summary.get("ticks",        0),
            "agents":      summary.get("agents",       0),
            "pois":        summary.get("pois",         0),
            "interactions": summary.get("interactions", 0),
            **({} if "aois"       not in summary else {"aois":       summary["aois"]}),
            **({} if "roads"      not in summary else {"roads":      summary["roads"]}),
            **({} if "started_at" not in summary else {"started_at": summary["started_at"]}),
        }
        if isinstance(summary_run_id, str) and summary_run_id and summary_run_id != run_id:
            run["display_run_id"] = summary_run_id
        runs.append(run)

    # started_at 降順 (§21.2)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return runs

# ─────────────────────────────────────────────────────────────────────────────
# データファイル配信 (§21.3)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_run_and_file(run_id: str, file: str) -> Path:
    """run_id / file を検証してファイルパスを返す。

    パストラバーサル防止:
    - run_id は RUN_ID_RE にマッチしなければ 403
    - file は ALLOWED_FILES にあれば 403 (なければ 403)
    - ファイルが存在しなければ 404

    §21.3.4 のエラーレスポンスに準拠する。
    """
    # パストラバーサル文字チェック (§21.3.4)
    if ".." in run_id or "/" in run_id or ".." in file or "/" in file:
        raise HTTPException(status_code=403, detail="invalid path")

    # run_id 形式チェック
    if not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=403, detail="invalid path")

    # ファイル許可リストチェック (§21.3.1)
    # agent_profiles_N<N>.json は可変エージェント数に対応するため正規表現でも許可する。
    if file not in ALLOWED_FILES and not AGENT_PROFILES_RE.match(file):
        raise HTTPException(status_code=403, detail=f"file not allowed: {file}")

    # run ディレクトリ存在チェック
    data_root = _get_data_root().resolve()
    run_dir   = data_root / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    # ファイル存在チェック
    file_path = run_dir / file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {file}")
    resolved_file_path = file_path.resolve()
    if not _path_is_within(resolved_file_path, data_root):
        raise HTTPException(status_code=403, detail="invalid path")

    return resolved_file_path


def _stream_jsonl(path: Path) -> Generator[str, None, None]:
    """JSONL ファイルを 1 行ずつ yield する (§21.3.2 raw stream)。"""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                yield stripped + "\n"


def _content_type_for(file: str) -> str:
    """ファイル名から Content-Type を返す。"""
    if file.endswith(".jsonl"):
        return "application/x-ndjson"
    if file.endswith(".geojson"):
        return "application/geo+json"
    return "application/json"


def _count_features(path: Path) -> int:
    """GeoJSON FeatureCollection の feature 件数を返す。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    features = data.get("features") if isinstance(data, dict) else None
    return len(features) if isinstance(features, list) else 0


def _safe_operator_state() -> dict[str, object]:
    """operator mode state をレスポンス用にコピーする。"""
    return {
        "viewpoint": _OPERATOR_MODE_STATE["viewpoint"],
        "status": _OPERATOR_MODE_STATE["status"],
        "run_id": _OPERATOR_MODE_STATE["run_id"],
        "agent_id": _OPERATOR_MODE_STATE["agent_id"],
        "trigger_class": _OPERATOR_MODE_STATE["trigger_class"],
        "failure_state": _OPERATOR_MODE_STATE["failure_state"],
        "message": _OPERATOR_MODE_STATE["message"],
        "runtime_only": True,
    }


def _set_operator_replay(message: str = "replay viewpoint") -> dict[str, object]:
    """operator mode を replay viewpoint へ戻す。"""
    _OPERATOR_MODE_STATE.update({
        "viewpoint": "replay",
        "status": "idle",
        "run_id": "",
        "agent_id": None,
        "trigger_class": "",
        "failure_state": "",
        "message": message,
    })
    return _safe_operator_state()


def _operator_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """失敗状態を保存しつつ、replay viewpoint を維持する HTTPException を返す。"""
    _OPERATOR_MODE_STATE.update({
        "viewpoint": "replay",
        "status": "blocked",
        "run_id": "",
        "agent_id": None,
        "trigger_class": "",
        "failure_state": failure_state,
        "message": message,
    })
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "operator_mode": _safe_operator_state(),
    })


def _world_packet_ready() -> bool:
    """Minimum World Packet の全項目が ready かを返す。"""
    return all(
        bool(_MINIMUM_WORLD_PACKET[field]["ready"])
        for field in MINIMUM_WORLD_PACKET_FIELDS
    )


def _safe_world_bridge_state() -> dict[str, object]:
    """world bridge state をレスポンス用にコピーする。"""
    return {
        "current_layer": _WORLD_BRIDGE_STATE["current_layer"],
        "previous_layer": _WORLD_BRIDGE_STATE["previous_layer"],
        "status": _WORLD_BRIDGE_STATE["status"],
        "failure_state": _WORLD_BRIDGE_STATE["failure_state"],
        "message": _WORLD_BRIDGE_STATE["message"],
        "available_layers": [
            {"id": layer, "description": _WORLD_LAYER_DESCRIPTIONS[layer]}
            for layer in WORLD_LAYERS
        ],
        "allowed_transitions": [
            {"from": source, "to": target}
            for source, target in sorted(_WORLD_BRIDGE_TRANSITIONS)
        ],
        "minimum_world_packet": {
            "ready": _world_packet_ready(),
            "fields": {
                field: dict(_MINIMUM_WORLD_PACKET[field])
                for field in MINIMUM_WORLD_PACKET_FIELDS
            },
        },
        "event_music_signal": dict(_EVENT_MUSIC_SIGNAL),
        "operator_mode": _safe_operator_state(),
        "runtime_only": True,
    }


def _set_world_bridge_simulated(message: str = "simulated layer") -> dict[str, object]:
    """テストとreturn用に world bridge を初期layerへ戻す。"""
    _WORLD_BRIDGE_STATE.update({
        "current_layer": "simulated",
        "previous_layer": "",
        "status": "ready",
        "failure_state": "",
        "message": message,
    })
    return _safe_world_bridge_state()


def _world_bridge_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """失敗状態を保存しつつ、現在layerを維持する HTTPException を返す。"""
    _WORLD_BRIDGE_STATE.update({
        "status": "blocked",
        "failure_state": failure_state,
        "message": message,
    })
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "world_bridge": _safe_world_bridge_state(),
    })


def _role_guidance(role_id: str) -> str:
    """現在のoperator/world状態に合わせたrole説明を返す。"""
    current_layer = str(_WORLD_BRIDGE_STATE["current_layer"])
    operator_viewpoint = str(_OPERATOR_MODE_STATE["viewpoint"])
    agent_id = _OPERATOR_MODE_STATE["agent_id"]
    target = f"Agent {agent_id}" if agent_id is not None else "未選択agent"
    if role_id == "guide":
        return f"{current_layer} layer / {operator_viewpoint} viewpointです。次の安全な選択肢を確認してください。"
    if role_id == "partner":
        return f"目的を短く整理し、{target} から戻る条件を確認します。"
    if role_id == "monitoring":
        return "toy replay内の変化、stale、heartbeat欠落だけを観測します。"
    if role_id == "pursuit":
        return f"{target} のtoy event chainをreplay内だけで追います。"
    if role_id == "intervention":
        return "直接state変更ではなく、safe action候補とrollback候補だけを提示します。"
    if role_id == "field-support":
        return "human approval、cost、公開境界、運用制約を確認します。"
    if role_id == "supervisor":
        return "role衝突、gate、handoff先を整理し、user oversightを維持します。"
    return "role guidance unavailable"


def _safe_agent_roster_state() -> dict[str, object]:
    """agent roster role state をレスポンス用にコピーする。"""
    active_role = str(_AGENT_ROSTER_STATE["active_role"])
    definitions = []
    for role_id in AGENT_ROSTER_ROLES:
        definition = _AGENT_ROSTER_DEFINITIONS[role_id]
        definitions.append({
            "id": role_id,
            "responsibility": definition["responsibility"],
            "layer": definition["layer"],
            "can": definition["can"],
            "cannot": definition["cannot"],
            "guidance": _role_guidance(role_id),
        })
    return {
        "active_role": active_role,
        "status": _AGENT_ROSTER_STATE["status"],
        "failure_state": _AGENT_ROSTER_STATE["failure_state"],
        "message": _AGENT_ROSTER_STATE["message"],
        "roles": definitions,
        "active": {
            **dict(_AGENT_ROSTER_DEFINITIONS[active_role]),
            "id": active_role,
            "guidance": _role_guidance(active_role),
        },
        "operator_boundary": "roles support operator decisions but do not replace human oversight",
        "operator_mode": _safe_operator_state(),
        "world_bridge": {
            "current_layer": _WORLD_BRIDGE_STATE["current_layer"],
            "status": _WORLD_BRIDGE_STATE["status"],
        },
        "runtime_only": True,
    }


def _set_agent_roster_guide(message: str = "guide role ready") -> dict[str, object]:
    """テスト用に agent roster を初期roleへ戻す。"""
    _AGENT_ROSTER_STATE.update({
        "active_role": "guide",
        "status": "ready",
        "failure_state": "",
        "message": message,
    })
    return _safe_agent_roster_state()


def _agent_roster_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """失敗状態を保存しつつ、active role を維持する HTTPException を返す。"""
    _AGENT_ROSTER_STATE.update({
        "status": "blocked",
        "failure_state": failure_state,
        "message": message,
    })
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "agent_roster": _safe_agent_roster_state(),
    })


def _motif_arc_evaluation(motif_id: str) -> dict[str, object]:
    """motifがArchetype/World guaranteeを満たすか評価する。"""
    motif = _MOTIF_ARCS[motif_id]
    archetypes = motif["archetypes"]
    world_fields = motif["world_fields"]
    missing_world_fields = [
        field for field in MINIMUM_WORLD_PACKET_FIELDS
        if field not in world_fields and motif_id == "next-motif-expansion-slot"
    ]
    archetype_ready = isinstance(archetypes, list) and len(archetypes) > 0
    world_ready = isinstance(world_fields, list) and len(world_fields) > 0 and not missing_world_fields
    public_safe_ready = motif_id in MOTIF_ARC_IDS
    return {
        "motif_id": motif_id,
        "public_safe_name": motif["name"],
        "core": motif["core"],
        "gate": motif["gate"],
        "archetypes": archetypes,
        "world_fields": world_fields,
        "archetype_ready": archetype_ready,
        "world_ready": world_ready,
        "public_safe_ready": public_safe_ready,
        "accepted": archetype_ready and world_ready and public_safe_ready,
        "missing_world_fields": missing_world_fields,
        "next_classification_required": motif_id == "next-motif-expansion-slot",
    }


def _safe_motif_arc_state() -> dict[str, object]:
    """motif arc state をレスポンス用にコピーする。"""
    active_id = str(_MOTIF_ARC_STATE["active_motif_id"])
    motifs = [_motif_arc_evaluation(motif_id) for motif_id in MOTIF_ARC_IDS]
    return {
        "active_motif_id": active_id,
        "status": _MOTIF_ARC_STATE["status"],
        "failure_state": _MOTIF_ARC_STATE["failure_state"],
        "message": _MOTIF_ARC_STATE["message"],
        "motifs": motifs,
        "active": _motif_arc_evaluation(active_id),
        "guarantees": {
            "archetype": "actor role、relationship pattern、pressure source、failure mode、recovery or transition pathのいずれかを要求する。",
            "world": "Minimum World Packetに接続できるworld fieldを要求する。",
            "public_safe": "作品名、キャラクター名、引用、私的path、外部投稿本文をimplementation IDにしない。",
        },
        "operator_mode": _safe_operator_state(),
        "world_bridge": {
            "current_layer": _WORLD_BRIDGE_STATE["current_layer"],
            "minimum_world_packet_ready": _world_packet_ready(),
        },
        "agent_roster": {
            "active_role": _AGENT_ROSTER_STATE["active_role"],
        },
        "runtime_only": True,
    }


def _set_motif_arc_default(message: str = "motif arc ready") -> dict[str, object]:
    """テスト用に motif arc を初期状態へ戻す。"""
    _MOTIF_ARC_STATE.update({
        "active_motif_id": "equivalent-exchange-pair",
        "status": "ready",
        "failure_state": "",
        "message": message,
    })
    return _safe_motif_arc_state()


def _motif_arc_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """失敗状態を保存しつつ、active motif を維持する HTTPException を返す。"""
    _MOTIF_ARC_STATE.update({
        "status": "blocked",
        "failure_state": failure_state,
        "message": message,
    })
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "motif_arcs": _safe_motif_arc_state(),
    })


def _assessment_evaluation(category_id: str) -> dict[str, object]:
    """評価カテゴリの安全境界を返す。"""
    category = _ASSESSMENT_CATEGORIES[category_id]
    return {
        "category_id": category_id,
        "public_safe_name": category["name"],
        "evaluates": category["evaluates"],
        "input": category["input"],
        "output": category["output"],
        "fail_condition": category["fail"],
        "deception_free": "deception" not in str(category["output"]).lower(),
        "dangerous_live_test": False,
        "external_body_required": False,
        "accepted": True,
    }


def _safe_assessment_lab_state(
    active_category_id: str | None = None,
    status: str | None = None,
    failure_state: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    """assessment lab state をレスポンス用にコピーする。"""
    active_id = active_category_id or str(_ASSESSMENT_LAB_STATE["active_category_id"])
    categories = [_assessment_evaluation(category_id) for category_id in ASSESSMENT_CATEGORY_IDS]
    return {
        "active_category_id": active_id,
        "status": status or str(_ASSESSMENT_LAB_STATE["status"]),
        "failure_state": failure_state if failure_state is not None else str(_ASSESSMENT_LAB_STATE["failure_state"]),
        "message": message or str(_ASSESSMENT_LAB_STATE["message"]),
        "categories": categories,
        "active": _assessment_evaluation(active_id),
        "boundaries": {
            "human_ai": "騙せるかではなく、意図・境界・制約・未確定性を扱えるかを見る。",
            "capability": "特定lab/model rankingではなくcapability layerとして扱う。",
            "harness": "model capabilityとproduct harness qualityを分ける。",
            "source": "外部投稿本文やprivate sourceを引用しない。",
        },
        "motif_arcs": {
            "active_motif_id": _MOTIF_ARC_STATE["active_motif_id"],
        },
        "agent_roster": {
            "active_role": _AGENT_ROSTER_STATE["active_role"],
        },
        "runtime_only": True,
    }


def _set_assessment_lab_default(message: str = "assessment lab ready") -> dict[str, object]:
    """テスト用に assessment lab を初期状態へ戻す。"""
    _ASSESSMENT_LAB_STATE.update({
        "active_category_id": "human-ai-assessment-lab",
        "status": "ready",
        "failure_state": "",
        "message": message,
    })
    return _safe_assessment_lab_state()


def _assessment_lab_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """process-local stateを汚さずにHTTPExceptionを返す。"""
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "assessment_lab": _safe_assessment_lab_state(
            status="blocked",
            failure_state=failure_state,
            message=message,
        ),
    })


def _governance_layer(layer_id: str) -> dict[str, object]:
    """governance layer の公開安全な説明を返す。"""
    layer = _GOVERNANCE_LAYERS[layer_id]
    return {
        "layer_id": layer_id,
        "public_safe_name": layer["name"],
        "responsibility": layer["responsibility"],
        "input": layer["input"],
        "output": layer["output"],
        "gate": layer["gate"],
        "user_controlled": layer_id == "oversight",
    }


def _fde_step(step_id: str) -> dict[str, object]:
    """FDE step の説明を返す。"""
    step = _FDE_STEPS[step_id]
    return {
        "step_id": step_id,
        "public_safe_name": step["name"],
        "meaning": step["meaning"],
    }


def _safe_governance_fde_state(
    decision: str = "watch",
    status: str = "ready",
    failure_state: str = "",
    message: str = "governance FDE ready",
) -> dict[str, object]:
    """MVP-006のstateless governance / FDE stateを返す。"""
    return {
        "active_decision": decision,
        "status": status,
        "failure_state": failure_state,
        "message": message,
        "layers": [_governance_layer(layer_id) for layer_id in GOVERNANCE_LAYER_IDS],
        "fde_steps": [_fde_step(step_id) for step_id in FDE_STEP_IDS],
        "decisions": list(FDE_DECISION_IDS),
        "numeric_protocol": {
            "status": "parking-lot",
            "reason": "numeric meaningはcreative hypothesisであり、実装根拠として未成熟。",
            "recheck_condition": "concrete operator workflow、decision packet、testable behaviorに接続できた時。",
        },
        "future_frame": {
            "mode": "comparison",
            "fields": ["old_future_image", "current_local_capacity", "implementation_gap"],
            "prohibited": "prophecy / inevitable future",
        },
        "time_sense": {
            "fields": ["wait_value", "progress", "stuck_state", "next_return_point"],
        },
        "skill_orchestration": {
            "skill_mesh": True,
            "orchestration_pack": True,
            "recursive_calls_allowed": "loop guard and human gate required",
        },
        "oversight": {
            "user_role": "external_monitor",
            "user_is_agent": False,
            "human_gate_required": True,
        },
        "runtime_only": True,
    }


def _governance_fde_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """FDE decision packetの失敗状態を返す。"""
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "governance_fde": _safe_governance_fde_state(
            status="blocked",
            failure_state=failure_state,
            message=message,
        ),
    })


def _skill_family(skill_id: str) -> dict[str, object]:
    """skill family の責任とguardを返す。"""
    skill = _SKILL_FAMILIES[skill_id]
    return {
        "skill_id": skill_id,
        "responsibility": skill["responsibility"],
        "required_guard": skill["guard"],
    }


def _safe_repo_skill_mesh_state(
    active_skill_id: str = "governance-skill",
    status: str = "ready",
    failure_state: str = "",
    message: str = "repo skill mesh ready",
) -> dict[str, object]:
    """MVP-007のstateless repo-as-skill / distributed ops stateを返す。"""
    return {
        "active_skill_id": active_skill_id,
        "status": status,
        "failure_state": failure_state,
        "message": message,
        "skill_families": [_skill_family(skill_id) for skill_id in SKILL_FAMILY_IDS],
        "recursive_guard": {
            "maximum_depth": 3,
            "allowed_io_required": True,
            "call_reason_required": True,
            "stop_condition_required": True,
            "evidence_packet_required": True,
            "loop_guard_required": True,
        },
        "distributed_ops": {
            "mode": "design-spike",
            "implementation_allowed": False,
            "required_before_implementation": [
                "identity",
                "trust",
                "sync",
                "conflict_resolution",
                "moderation",
                "abuse_resistance",
                "rollback_and_audit_trail",
            ],
        },
        "cloud_capacity": {
            "execution_allowed": False,
            "required_before_execution": [
                "target_service",
                "account_project",
                "billing_owner",
                "estimated_cost",
                "quota",
                "region",
                "data_egress",
                "credential_boundary",
                "rollback_plan",
                "human_approval",
            ],
        },
        "external_writes_allowed": False,
        "runtime_only": True,
    }


def _repo_skill_mesh_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """repo skill mesh planの失敗状態を返す。"""
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "repo_skill_mesh": _safe_repo_skill_mesh_state(
            status="blocked",
            failure_state=failure_state,
            message=message,
        ),
    })


def _safe_intake_lifecycle_state(
    active_class: str = "accepted",
    status: str = "ready",
    failure_state: str = "",
    message: str = "intake lifecycle ready",
    draft_candidate: dict[str, object] | None = None,
) -> dict[str, object]:
    """MVP-008のstateless intake / worldbuilding lifecycle stateを返す。"""
    return {
        "active_class": active_class,
        "status": status,
        "failure_state": failure_state,
        "message": message,
        "request_classes": list(INTAKE_REQUEST_CLASSES),
        "source_categories": list(INTAKE_SOURCE_CATEGORIES),
        "pipeline_steps": list(_INTAKE_PIPELINE_STEPS),
        "validator_rules": list(_INTAKE_VALIDATOR_RULES),
        "minimum_world_packet": {
            "required_fields": list(INTAKE_WORLD_PACKET_FIELDS),
            "required": True,
        },
        "lifecycle": {
            "orphan_threshold": 3,
            "stale_self_report_required": True,
            "heartbeat_mode": "read-only/draft-only",
            "auto_close_allowed": False,
            "external_write_allowed": False,
        },
        "draft_candidate": draft_candidate or {
            "public_safe_name": "Worldbuilding Extraction Pipeline",
            "todo_id": "XWORLD-TODO-034",
            "source_category": "project-hypothesis",
            "gate": "intake review",
        },
        "runtime_only": True,
    }


def _intake_lifecycle_error(status_code: int, failure_state: str, message: str) -> HTTPException:
    """intake draft candidateの失敗状態を返す。"""
    return HTTPException(status_code=status_code, detail={
        "failure_state": failure_state,
        "message": message,
        "intake_lifecycle": _safe_intake_lifecycle_state(
            status="blocked",
            failure_state=failure_state,
            message=message,
        ),
    })


def _truthy_or_text_present(value: object) -> bool:
    """boolean flagまたは文字列本文の混入を検出する。"""
    if value is True:
        return True
    return isinstance(value, str) and bool(value.strip())


def _read_summary(run_id: str) -> dict:
    """operator entry 用に summary.json を読み込む。"""
    try:
        summary_path = _validate_run_and_file(run_id, "summary.json")
    except HTTPException as exc:
        raise _operator_error(404, "target_not_found", f"run not found: {run_id}") from exc
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _operator_error(404, "target_not_found", f"run summary is unavailable: {run_id}") from exc
    if not isinstance(summary, dict):
        raise _operator_error(404, "target_not_found", f"run summary is invalid: {run_id}")
    return summary


def _load_agent_profiles_for_run(run_id: str) -> list[dict]:
    """run の agent profiles を読み込む。可変Nと既存固定名の両方に対応する。"""
    summary = _read_summary(run_id)
    agents = summary.get("agents")
    candidates: list[str] = []
    if isinstance(agents, int) and agents > 0:
        candidates.append(f"agent_profiles_N{agents}.json")
    candidates.append("agent_profiles_N100.json")

    for filename in dict.fromkeys(candidates):
        try:
            profiles_path = _validate_run_and_file(run_id, filename)
        except HTTPException:
            continue
        try:
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(profiles, list):
            return [profile for profile in profiles if isinstance(profile, dict)]
    raise _operator_error(404, "target_not_found", f"agent profiles are unavailable: {run_id}")


def _resolve_operator_agent(run_id: str, agent_id: int) -> dict:
    """run_id と agent_id から一意な agent profile を解決する。"""
    profiles = _load_agent_profiles_for_run(run_id)
    matches = [profile for profile in profiles if profile.get("id") == agent_id]
    if not matches:
        raise _operator_error(404, "target_not_found", f"agent not found: {agent_id}")
    if len(matches) > 1:
        raise _operator_error(409, "target_ambiguous", f"agent is ambiguous: {agent_id}")
    return matches[0]

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI アプリ
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Urban Ecosystem Viewer", version="0.1.0")

# 静的アセット配信 (/static/* -> tools/urban_viewer/)
_STATIC_DIR = Path(__file__).parent / "urban_viewer"
_APP_JS_PATH = _STATIC_DIR / "app.js"


@app.get("/static/app.js")
async def _serve_app_js() -> Response:
    """app.js 配信時に Maps キー / Map ID プレースホルダを注入する (§5.1.1)。

    StaticFiles mount より前に登録し、app.js だけ templating する。
    キー未設定時はプレースホルダを残し、app.js 側が fallback アダプタを選ぶ。
    キー値はログに出力しない。
    """
    api_key = _get_maps_api_key()
    map_id  = _get_maps_map_id()
    js = _APP_JS_PATH.read_text(encoding="utf-8")
    if api_key:
        usable_map_id = bool(map_id and map_id != "DEMO_MAP_ID")
        js = _replace_js_placeholder_literal(js, _PLACEHOLDER_KEY, api_key)
        js = _replace_js_placeholder_literal(
            js, _PLACEHOLDER_MAP_ID, map_id if usable_map_id else ""
        )
    return Response(content=js, media_type="application/javascript")


# app.js 以外の静的アセット (CSS / 他 JS / colors.js 等) は raw 配信
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.middleware("http")
async def _security_headers(request, call_next):
    """最小のセキュリティヘッダを付与する (公開時のクリックジャッキング / MIME sniffing 緩和)。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """ビューア HTML を返す (APIキー注入 or fallback)。

    §21 / §13.4: APIキー未設定でも 500 を返さない。
    """
    api_key = _get_maps_api_key()
    map_id  = _get_maps_map_id()
    html    = _build_viewer_html(api_key, map_id)
    return HTMLResponse(content=html)


@app.get("/api/health")
async def health() -> JSONResponse:
    """ヘルスチェック (§21.4)。

    maps_key フィールドはキーの present/absent のみ返す。キー値は返さない。
    """
    api_key     = _get_maps_api_key()
    data_source = _get_data_source()
    body = {
        "status":      "ok",
        "maps_key":    "present" if api_key else "absent",
        "data_source": data_source,
        "data_source_supported": data_source in SUPPORTED_DATA_SOURCES,
    }
    if data_source not in SUPPORTED_DATA_SOURCES:
        body["data_source_error"] = _data_source_error(data_source)
    return JSONResponse(body)


@app.get("/api/settings")
async def get_settings() -> JSONResponse:
    """ビューア設定状態を返す。API キー値は返さない。"""
    return JSONResponse(_settings_body())


@app.post("/api/settings")
async def update_settings(request: Request) -> JSONResponse:
    """UI から process-local な設定を更新する。

    永続保存はしない。API キー値はレスポンスに含めない。
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be an object")

    maps = body.get("maps", {})
    data = body.get("data", {})
    llm = body.get("llm", {})
    cloud = body.get("cloud", {})
    for section_name, section in {
        "maps": maps,
        "data": data,
        "llm": llm,
        "cloud": cloud,
    }.items():
        if section is None:
            continue
        if not isinstance(section, dict):
            raise HTTPException(status_code=400, detail=f"{section_name} must be an object")

    if isinstance(maps, dict):
        if "api_key" in maps:
            _set_runtime_value("GOOGLE_MAPS_API_KEY", maps["api_key"])
        if "map_id" in maps:
            _set_runtime_value("GOOGLE_MAPS_MAP_ID", maps["map_id"])

    if isinstance(data, dict):
        if "source" in data:
            source = data["source"]
            if not isinstance(source, str):
                raise HTTPException(status_code=400, detail="DATA_SOURCE must be a string")
            source = source.strip() or "local"
            if source not in SUPPORTED_DATA_SOURCES:
                raise HTTPException(status_code=400, detail=_data_source_error(source))
            _set_runtime_value("DATA_SOURCE", source)
        if "root" in data:
            root = data["root"]
            if root is not None and not isinstance(root, str):
                raise HTTPException(status_code=400, detail="DATA_DIR must be a string")
            if isinstance(root, str) and root.strip():
                root_path = Path(root.strip()).expanduser()
                if not root_path.is_dir():
                    raise HTTPException(status_code=400, detail=f"DATA_DIR not found: {root_path}")
            _set_runtime_value("DATA_DIR", root)

    if isinstance(llm, dict):
        if "provider" in llm:
            provider = llm["provider"]
            if not isinstance(provider, str):
                raise HTTPException(status_code=400, detail="LLM_PROVIDER must be a string")
            provider = provider.strip() or "rule"
            if provider not in {"rule", "local", "vertex"}:
                raise HTTPException(status_code=400, detail="LLM_PROVIDER must be rule, local, or vertex")
            _set_runtime_value("LLM_PROVIDER", provider)
        for json_key, env_key in {
            "model": "LLM_MODEL",
            "base_url": "LLM_BASE_URL",
            "model_dir": "LLM_MODEL_DIR",
        }.items():
            if json_key in llm:
                if json_key == "model_dir" and isinstance(llm[json_key], str) and llm[json_key].strip():
                    model_dir = Path(llm[json_key].strip()).expanduser()
                    if not model_dir.is_dir():
                        raise HTTPException(status_code=400, detail=f"LLM_MODEL_DIR not found: {model_dir}")
                _set_runtime_value(env_key, llm[json_key])

    if isinstance(cloud, dict) and "google_cloud_project" in cloud:
        _set_runtime_value("GOOGLE_CLOUD_PROJECT", cloud["google_cloud_project"])

    return JSONResponse(_settings_body())


@app.get("/api/runs")
async def list_runs() -> JSONResponse:
    """利用可能な run 一覧を返す (§21.2)。

    run が 0 件でも 4xx/5xx は返さない。
    """
    runs = _list_runs()
    return JSONResponse({"runs": runs})


@app.post("/api/runs")
async def create_run(request: Request) -> JSONResponse:
    """UI から新しい sample simulation run を作る。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be an object")
    mode = body.get("mode", "sample")
    if mode != "sample":
        raise HTTPException(status_code=400, detail="only mode=sample is supported")
    result = _create_sample_run(body)
    return JSONResponse(result)


@app.get("/api/operator-mode")
async def get_operator_mode() -> JSONResponse:
    """MVP-001: operator viewpoint state を返す。runtime-onlyで永続化しない。"""
    return JSONResponse(_safe_operator_state())


@app.post("/api/operator-mode/entry")
async def enter_operator_mode(request: Request) -> JSONResponse:
    """MVP-001: 選択agentのinspection viewpointへ入る。

    public-safeなtrigger_classだけを受け取り、生の起動語句は受け取らない。
    simulation state は変更せず、viewer用のprocess-local viewpointだけを更新する。
    """
    _ensure_data_source_supported()
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _operator_error(400, "entry_not_allowed", "invalid json") from exc
    if not isinstance(body, dict):
        raise _operator_error(400, "entry_not_allowed", "request body must be an object")
    if "trigger_text" in body:
        raise _operator_error(400, "trigger_not_allowed", "trigger_text is not accepted in public API")

    run_id = body.get("run_id")
    agent_id = body.get("agent_id")
    trigger_class = body.get("trigger_class", "entry_intent")

    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise _operator_error(400, "entry_not_allowed", "run_id must match ^[A-Za-z0-9_-]{1,128}$")
    if not isinstance(agent_id, int) or isinstance(agent_id, bool):
        raise _operator_error(400, "entry_not_allowed", "agent_id must be an integer")
    if not isinstance(trigger_class, str) or trigger_class not in _OPERATOR_TRIGGER_CLASSES:
        raise _operator_error(400, "trigger_not_allowed", "trigger_class is not allowed")

    profile = _resolve_operator_agent(run_id, agent_id)
    display_name = profile.get("surname") or profile.get("name") or f"Agent {agent_id}"
    _OPERATOR_MODE_STATE.update({
        "viewpoint": "inspection",
        "status": "active",
        "run_id": run_id,
        "agent_id": agent_id,
        "trigger_class": trigger_class,
        "failure_state": "",
        "message": f"inspection viewpoint: {display_name}",
    })
    return JSONResponse(_safe_operator_state())


@app.post("/api/operator-mode/return")
async def return_operator_mode() -> JSONResponse:
    """MVP-001: replay viewpointへ戻る。"""
    return JSONResponse(_set_operator_replay("returned to replay viewpoint"))


@app.get("/api/world-bridge")
async def get_world_bridge() -> JSONResponse:
    """MVP-002: 三層 world bridge state を返す。runtime-onlyで永続化しない。"""
    return JSONResponse(_safe_world_bridge_state())


@app.post("/api/world-bridge/transition")
async def transition_world_bridge(request: Request) -> JSONResponse:
    """MVP-002: physical / simulated / liminal のlayer移動を行う。

    direct physical <-> simulated は許可せず、liminal 経由を要求する。
    simulation state は変更せず、viewer用のprocess-local layerだけを更新する。
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _world_bridge_error(400, "transition_not_allowed", "invalid json") from exc
    if not isinstance(body, dict):
        raise _world_bridge_error(400, "transition_not_allowed", "request body must be an object")

    target_layer = body.get("target_layer")
    reason_class = body.get("reason_class", "operator_intent")
    requires_agent_context = body.get("requires_agent_context", False)
    if not isinstance(target_layer, str) or target_layer not in WORLD_LAYERS:
        raise _world_bridge_error(404, "layer_not_found", "target_layer is not defined")
    if not isinstance(reason_class, str) or not reason_class.strip():
        raise _world_bridge_error(400, "transition_not_allowed", "reason_class must be a string")
    if not isinstance(requires_agent_context, bool):
        raise _world_bridge_error(400, "transition_not_allowed", "requires_agent_context must be a boolean")
    if requires_agent_context and _OPERATOR_MODE_STATE["agent_id"] is None:
        raise _world_bridge_error(400, "agent_context_missing", "agent context is required for this transition")
    if not _world_packet_ready():
        raise _world_bridge_error(400, "world_packet_incomplete", "Minimum World Packet is incomplete")

    current_layer = str(_WORLD_BRIDGE_STATE["current_layer"])
    if current_layer == target_layer:
        _WORLD_BRIDGE_STATE.update({
            "status": "ready",
            "failure_state": "",
            "message": f"already in {target_layer} layer",
        })
        return JSONResponse(_safe_world_bridge_state())
    if (current_layer, target_layer) not in _WORLD_BRIDGE_TRANSITIONS:
        raise _world_bridge_error(
            400,
            "transition_not_allowed",
            f"transition {current_layer} -> {target_layer} requires liminal bridge",
        )

    _WORLD_BRIDGE_STATE.update({
        "current_layer": target_layer,
        "previous_layer": current_layer,
        "status": "ready",
        "failure_state": "",
        "message": f"{current_layer} -> {target_layer}: {reason_class}",
    })
    return JSONResponse(_safe_world_bridge_state())


@app.get("/api/agent-roster")
async def get_agent_roster() -> JSONResponse:
    """MVP-003: guide / partner などの抽象role stateを返す。"""
    return JSONResponse(_safe_agent_roster_state())


@app.post("/api/agent-roster/select")
async def select_agent_roster_role(request: Request) -> JSONResponse:
    """MVP-003: active roleを選択する。

    roleは抽象archetypeだけを受け取り、実人物・作品由来role・現実の監視手順は扱わない。
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _agent_roster_error(400, "role_not_found", "invalid json") from exc
    if not isinstance(body, dict):
        raise _agent_roster_error(400, "role_not_found", "request body must be an object")
    role_id = body.get("role_id")
    if not isinstance(role_id, str) or role_id not in AGENT_ROSTER_ROLES:
        raise _agent_roster_error(404, "role_not_found", "role_id is not defined")
    definition = _AGENT_ROSTER_DEFINITIONS[role_id]
    layer = definition.get("layer")
    if layer not in WORLD_LAYERS:
        raise _agent_roster_error(400, "world_layer_missing", "role has no world layer")

    _AGENT_ROSTER_STATE.update({
        "active_role": role_id,
        "status": "ready",
        "failure_state": "",
        "message": f"{role_id} role selected",
    })
    return JSONResponse(_safe_agent_roster_state())


@app.get("/api/motif-arcs")
async def get_motif_arcs() -> JSONResponse:
    """MVP-004: public-safe motif arc packを返す。"""
    return JSONResponse(_safe_motif_arc_state())


@app.post("/api/motif-arcs/evaluate")
async def evaluate_motif_arc(request: Request) -> JSONResponse:
    """MVP-004: motif arc のArchetype / World guaranteeを確認する。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _motif_arc_error(400, "motif_name_not_safe", "invalid json") from exc
    if not isinstance(body, dict):
        raise _motif_arc_error(400, "motif_name_not_safe", "request body must be an object")
    motif_id = body.get("motif_id")
    if not isinstance(motif_id, str) or motif_id not in MOTIF_ARC_IDS:
        raise _motif_arc_error(404, "motif_name_not_safe", "motif_id is not public-safe or is not defined")

    evaluation = _motif_arc_evaluation(motif_id)
    if not evaluation["archetype_ready"]:
        raise _motif_arc_error(400, "archetype_missing", "motif has no archetype guarantee")
    if not evaluation["world_ready"]:
        raise _motif_arc_error(400, "world_packet_incomplete", "motif has no world guarantee")
    _MOTIF_ARC_STATE.update({
        "active_motif_id": motif_id,
        "status": "ready",
        "failure_state": "",
        "message": f"{motif_id} accepted by motif gate",
    })
    return JSONResponse(_safe_motif_arc_state())


@app.get("/api/assessment-lab")
async def get_assessment_lab() -> JSONResponse:
    """MVP-005: assessment / benchmark category stateを返す。"""
    return JSONResponse(_safe_assessment_lab_state())


@app.post("/api/assessment-lab/evaluate")
async def evaluate_assessment_category(request: Request) -> JSONResponse:
    """MVP-005: benchmark categoryを公開安全な範囲で評価する。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _assessment_lab_error(400, "scenario_unbounded", "invalid json") from exc
    if not isinstance(body, dict):
        raise _assessment_lab_error(400, "scenario_unbounded", "request body must be an object")
    category_id = body.get("category_id")
    if not isinstance(category_id, str) or category_id not in ASSESSMENT_CATEGORY_IDS:
        raise _assessment_lab_error(404, "scenario_unbounded", "category_id is not defined")
    if body.get("dangerous_live_test") is True:
        raise _assessment_lab_error(400, "unsafe_live_test", "dangerous live test is not allowed")
    if body.get("external_body_included") is True:
        raise _assessment_lab_error(400, "source_body_leak", "external post body is not allowed")
    if body.get("model_ranking") is True:
        raise _assessment_lab_error(400, "capability_claim_unverified", "lab/model ranking is not allowed")

    return JSONResponse(_safe_assessment_lab_state(
        active_category_id=category_id,
        status="ready",
        failure_state="",
        message=f"{category_id} evaluated by benchmark gate",
    ))


@app.get("/api/governance-fde")
async def get_governance_fde() -> JSONResponse:
    """MVP-006: governance layerとFDE packet stateを返す。"""
    return JSONResponse(_safe_governance_fde_state())


@app.post("/api/governance-fde/decide")
async def decide_governance_fde(request: Request) -> JSONResponse:
    """MVP-006: FDE decision packetを公開安全な範囲で評価する。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _governance_fde_error(400, "packet_missing_evidence", "invalid json") from exc
    if not isinstance(body, dict):
        raise _governance_fde_error(400, "packet_missing_evidence", "request body must be an object")

    decision = body.get("decision", "watch")
    if not isinstance(decision, str) or decision not in FDE_DECISION_IDS:
        raise _governance_fde_error(404, "packet_missing_evidence", "decision is not defined")
    if body.get("human_gate") is False:
        raise _governance_fde_error(400, "oversight_bypassed", "human gate is required")
    if body.get("user_as_agent") is True:
        raise _governance_fde_error(400, "oversight_bypassed", "user must stay external monitor")
    if body.get("future_claim") == "prophecy":
        raise _governance_fde_error(400, "future_claim_overreach", "future frame must be comparative")
    if body.get("numeric_rule") == "implemented":
        raise _governance_fde_error(400, "numeric_rule_overreach", "numeric protocol stays parking-lot")
    if body.get("recursive_depth_unbounded") is True:
        raise _governance_fde_error(400, "recursive_loop_unbounded", "recursive calls need depth and stop condition")
    evidence = body.get("evidence", [])
    if decision == "proceed" and (not isinstance(evidence, list) or len(evidence) < 3):
        raise _governance_fde_error(
            400,
            "packet_missing_evidence",
            "proceed decision requires tests, scan, and review evidence",
        )

    return JSONResponse(_safe_governance_fde_state(
        decision=decision,
        status="ready",
        failure_state="",
        message=f"{decision} decision accepted by FDE gate",
    ))


@app.get("/api/repo-skill-mesh")
async def get_repo_skill_mesh() -> JSONResponse:
    """MVP-007: repo-as-skill / distributed ops guard stateを返す。"""
    return JSONResponse(_safe_repo_skill_mesh_state())


@app.post("/api/repo-skill-mesh/evaluate")
async def evaluate_repo_skill_mesh(request: Request) -> JSONResponse:
    """MVP-007: skill call / distributed ops planを公開安全な範囲で評価する。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _repo_skill_mesh_error(400, "allowed_io_missing", "invalid json") from exc
    if not isinstance(body, dict):
        raise _repo_skill_mesh_error(400, "allowed_io_missing", "request body must be an object")

    skill_id = body.get("skill_id", "governance-skill")
    if not isinstance(skill_id, str) or skill_id not in SKILL_FAMILY_IDS:
        raise _repo_skill_mesh_error(404, "allowed_io_missing", "skill_id is not defined")
    if body.get("external_write") is True:
        raise _repo_skill_mesh_error(400, "external_write_attempted", "external write needs human review")
    if body.get("cloud_execute") is True:
        raise _repo_skill_mesh_error(400, "cloud_approval_missing", "cloud execution needs capacity envelope and approval")
    if body.get("p2p_operationalize") is True:
        raise _repo_skill_mesh_error(400, "trust_model_missing", "P2P needs identity, trust, and moderation model")
    if body.get("loop_guard") is False:
        raise _repo_skill_mesh_error(400, "loop_guard_missing", "recursive call needs loop guard")
    if body.get("allowed_io") is False:
        raise _repo_skill_mesh_error(400, "allowed_io_missing", "skill call needs allowed I/O")
    depth = body.get("maximum_depth", 1)
    if not isinstance(depth, int) or depth < 0 or depth > 3:
        raise _repo_skill_mesh_error(400, "recursive_depth_exceeded", "maximum depth must be 0..3")

    return JSONResponse(_safe_repo_skill_mesh_state(
        active_skill_id=skill_id,
        status="ready",
        failure_state="",
        message=f"{skill_id} accepted by repo skill mesh gate",
    ))


@app.get("/api/intake-lifecycle")
async def get_intake_lifecycle() -> JSONResponse:
    """MVP-008: intake / worldbuilding / lifecycle guard stateを返す。"""
    return JSONResponse(_safe_intake_lifecycle_state())


@app.post("/api/intake-lifecycle/draft")
async def draft_intake_lifecycle(request: Request) -> JSONResponse:
    """MVP-008: 追加依頼を外部writeなしのdraft candidateとして評価する。"""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise _intake_lifecycle_error(400, "todo_classification_missing", "invalid json") from exc
    if not isinstance(body, dict):
        raise _intake_lifecycle_error(400, "todo_classification_missing", "request body must be an object")

    request_class = body.get("request_class", "accepted")
    if not isinstance(request_class, str) or request_class not in INTAKE_REQUEST_CLASSES:
        raise _intake_lifecycle_error(400, "todo_classification_missing", "request class is required")
    source_category = body.get("source_category", "project-hypothesis")
    if not isinstance(source_category, str) or source_category not in INTAKE_SOURCE_CATEGORIES:
        raise _intake_lifecycle_error(400, "source_not_public_safe", "source category is required")
    if body.get("external_write") is True:
        raise _intake_lifecycle_error(400, "external_write_blocked", "external write needs human review")
    if _truthy_or_text_present(body.get("private_source_content")):
        raise _intake_lifecycle_error(400, "source_not_public_safe", "private source content cannot enter public docs")
    if _truthy_or_text_present(body.get("protected_name")) or _truthy_or_text_present(body.get("private_path")):
        raise _intake_lifecycle_error(400, "validator_hit", "public-safe naming validator blocked the candidate")
    if _truthy_or_text_present(body.get("external_post_body")):
        raise _intake_lifecycle_error(400, "validator_hit", "external post body cannot be quoted")
    if _truthy_or_text_present(body.get("secret_like_string")):
        raise _intake_lifecycle_error(400, "validator_hit", "secret-like string cannot enter public docs")
    todo_id = body.get("todo_id")
    if request_class == "accepted" and (not isinstance(todo_id, str) or not todo_id.startswith("XWORLD-TODO-")):
        raise _intake_lifecycle_error(400, "todo_classification_missing", "accepted idea needs TODO ID")
    if body.get("minimum_world_packet") is False:
        raise _intake_lifecycle_error(400, "world_packet_missing", "Minimum World Packet is required")
    orphan_count = body.get("orphan_count", 0)
    if isinstance(orphan_count, int) and orphan_count > 3:
        raise _intake_lifecycle_error(400, "orphan_threshold_exceeded", "orphan threshold exceeded")
    if body.get("heartbeat_present") is False:
        raise _intake_lifecycle_error(400, "heartbeat_missing", "heartbeat must report the latest review point")
    if body.get("stale") is True and body.get("stale_self_report") is not True:
        raise _intake_lifecycle_error(400, "stale_without_self_report", "stale needs self-report evidence")

    public_safe_name = body.get("public_safe_name", "Worldbuilding Extraction Pipeline")
    if not isinstance(public_safe_name, str) or not public_safe_name.strip():
        public_safe_name = "Worldbuilding Extraction Pipeline"
    draft_candidate = {
        "public_safe_name": public_safe_name,
        "todo_id": todo_id if isinstance(todo_id, str) else "",
        "source_category": source_category,
        "request_class": request_class,
        "gate": "human review before external write",
    }
    return JSONResponse(_safe_intake_lifecycle_state(
        active_class=request_class,
        status="ready",
        failure_state="",
        message=f"{request_class} draft candidate accepted by intake gate",
        draft_candidate=draft_candidate,
    ))


@app.get("/api/labels")
async def get_labels() -> JSONResponse:
    """日本語ラベルマップを返す (WO-010 §5.3 / §19.3.1)。

    category / role / interaction_type / action の 4 セクションを持つ JSON を返す。
    表示層がこのエンドポイントを使って内部コードを日本語に変換する。
    内部 JSONL / contract の値はこのエンドポイントへの変換ではなく
    表示時の変換にのみ使用する (out_of_scope 保持)。
    """
    return JSONResponse(ALL_LABELS)


@app.get("/api/data/{run_id}/{file}", response_model=None)
async def get_data_file(run_id: str, file: str) -> StreamingResponse | JSONResponse:
    """データファイルを配信する (§21.3)。

    JSONL は raw stream / GeoJSON・JSON はそのまま転送。
    """
    _ensure_data_source_supported()
    file_path    = _validate_run_and_file(run_id, file)
    content_type = _content_type_for(file)

    if file.endswith(".jsonl"):
        # JSONL: StreamingResponse で raw stream (§21.3.2)
        return StreamingResponse(
            _stream_jsonl(file_path),
            media_type=content_type,
        )

    # GeoJSON / JSON: ファイルをそのまま転送 (§21.3.3)
    content = file_path.read_bytes()
    return JSONResponse(
        content=json.loads(content),
        media_type=content_type,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI エントリポイント (uvicorn 直起動用)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Urban Ecosystem Viewer サーバー")
    parser.add_argument("--host",    default="0.0.0.0",  help="bind host")
    parser.add_argument("--port",    type=int, default=8080, help="bind port")
    parser.add_argument("--data",    default="",         help="DATA_DIR 上書き")
    parser.add_argument("--reload",  action="store_true", help="開発モード自動リロード")
    args = parser.parse_args()

    if args.data:
        os.environ["DATA_DIR"] = args.data

    uvicorn.run(
        "tools.urban_viewer_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
