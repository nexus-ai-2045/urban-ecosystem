"""
test_llm_provider.py — app/llm_provider.py の単体テスト (spec §10)。

カバレッジ:
  - RuleBasedProvider: 決定論出力 / テンプレ文一致 / フォールバック
  - VertexGeminiProvider: mock クライアントでリクエスト構築・応答パース検証
                           (実 Gemini 呼ばない / SDK import しない)
  - make_llm_provider: ファクトリ ("rule"/"vertex"/不正 kind)
  - build_prompt: §10.3 必須マーカー含む / prompt_type 別
  - sim との統合: RuleBased で sim を回し既存決定論テスト pass

実 LLM を呼ぶテストはゼロ (CI/CD 環境で Vertex AI 認証情報不要)。
"""

from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートを import path に追加する (conftest.py 依存を避ける)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.llm_provider import (
    LLMProvider,
    RuleBasedProvider,
    VertexGeminiProvider,
    build_prompt,
    make_llm_provider,
)


# ─────────────────────────────────────────────────────────────────────────────
# RuleBasedProvider
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleBasedProvider:
    """RuleBasedProvider の決定論・テンプレ文テスト。"""

    @pytest.fixture(autouse=True)
    def provider(self) -> RuleBasedProvider:
        return RuleBasedProvider()

    # ── LLMProvider ABC を実装していることの確認 ────────────────────────────────

    def test_is_llm_provider_subclass(self, provider):
        """RuleBasedProvider は LLMProvider のサブクラス。"""
        assert isinstance(provider, LLMProvider)

    def test_has_complete_method(self, provider):
        """complete() メソッドを持つ。"""
        assert callable(getattr(provider, "complete", None))

    # ── テンプレ文 — simulation._summary_text と同一出力 ─────────────────────

    @pytest.mark.parametrize("ev_type,expected_verb", [
        ("meeting",      "が出会った"),
        ("conversation", "が会話した"),
        ("conflict",     "が口論した"),
        ("farewell",     "が別れた"),
    ])
    def test_template_summary_verb(self, provider, ev_type, expected_verb):
        """各 event_type のテンプレ動詞が仕様通り (§9.8.2 / simulation._summary_text 同一)。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=3,
            agent_b_id=7,
            event_type=ev_type,
            location_poi_id="poi_001",
        )
        result = provider.complete(prompt)
        assert expected_verb in result
        assert "エージェント 3" in result
        assert "7" in result
        assert "poi_001" in result

    def test_summary_matches_simulation_summary_text(self, provider):
        """complete() の出力が simulation._summary_text と byte 一致する。"""
        from environments.urban_2d.simulation import Simulation

        ev_type = "conversation"
        a_id = 10
        b_id = 20
        poi_id = "poi_cafe_001"

        # simulation 側のテンプレ文
        expected = Simulation._summary_text(ev_type, a_id, b_id, poi_id)

        # provider 側の出力
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=a_id,
            agent_b_id=b_id,
            event_type=ev_type,
            location_poi_id=poi_id,
        )
        actual = provider.complete(prompt)
        assert actual == expected, (
            f"provider 出力 {actual!r} が simulation テンプレ {expected!r} と不一致"
        )

    # ── 決定論: 同一プロンプト → 同一出力 ────────────────────────────────────

    def test_determinism_same_prompt(self, provider):
        """同一プロンプトに対して常に同一出力を返す。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=1,
            agent_b_id=2,
            event_type="meeting",
            location_poi_id="poi_010",
        )
        results = [provider.complete(prompt) for _ in range(5)]
        assert len(set(results)) == 1, "同一プロンプトで異なる出力が返った"

    def test_determinism_different_events(self, provider):
        """異なる event_type では異なる出力を返す。"""
        def _complete(ev_type):
            p = build_prompt(
                prompt_type="summary",
                agent_a_id=1,
                agent_b_id=2,
                event_type=ev_type,
                location_poi_id="poi_bar_001",
            )
            return provider.complete(p)

        results = {ev: _complete(ev) for ev in ("meeting", "conversation", "conflict", "farewell")}
        assert len(set(results.values())) == 4, "event_type が異なるのに同一出力"

    # ── フォールバック: マーカー欠落時 ─────────────────────────────────────────

    def test_fallback_on_empty_prompt(self, provider):
        """マーカーのないプロンプトでもクラッシュしない。"""
        result = provider.complete("こんにちは")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_on_missing_markers(self, provider):
        """一部マーカーが欠落してもクラッシュしない。"""
        result = provider.complete("event_type: meeting\nagent_a_id: 1")
        assert isinstance(result, str)

    # ── temperature / max_tokens は無視される ─────────────────────────────────

    def test_ignores_temperature_and_max_tokens(self, provider):
        """temperature / max_tokens の値に関係なく同一出力。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=5,
            agent_b_id=6,
            event_type="farewell",
            location_poi_id="poi_park_001",
        )
        r1 = provider.complete(prompt, temperature=0.0, max_tokens=10)
        r2 = provider.complete(prompt, temperature=1.0, max_tokens=512)
        assert r1 == r2


# ─────────────────────────────────────────────────────────────────────────────
# VertexGeminiProvider (mock client)
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_response(text: str) -> MagicMock:
    """Gemini SDK レスポンス mock を作る。"""
    resp = MagicMock()
    resp.text = text
    return resp


def _make_mock_client(response_text: str = "mock summary") -> MagicMock:
    """Gemini SDK クライアント mock を作る。

    client.models.generate_content() が呼ばれると _make_mock_response を返す。
    """
    client = MagicMock()
    client.models.generate_content.return_value = _make_mock_response(response_text)
    return client


class TestVertexGeminiProvider:
    """VertexGeminiProvider の mock クライアントテスト (実 SDK / 実 Gemini 不使用)。"""

    # ── LLMProvider サブクラス確認 ─────────────────────────────────────────────

    def test_is_llm_provider_subclass(self):
        """VertexGeminiProvider は LLMProvider のサブクラス。"""
        provider = VertexGeminiProvider(client=_make_mock_client())
        assert isinstance(provider, LLMProvider)

    # ── リクエスト構築の検証 ──────────────────────────────────────────────────

    def test_calls_generate_content_with_prompt(self):
        """complete() が client.models.generate_content を呼んでいる。"""
        mock_client = _make_mock_client("テスト応答")
        provider = VertexGeminiProvider(model="gemini-2.0-flash", client=mock_client)

        # GenerateContentConfig は SDK 型だが mock では不要。
        # patch して型エラーを回避しつつ呼び出し引数だけ検証する。
        with patch("app.llm_provider.VertexGeminiProvider.complete",
                   wraps=provider.complete) as _:
            pass

        # 直接 mock クライアントで呼び出しを確認する
        # (SDK の GenerateContentConfig は import しない)
        prompt = "テストプロンプト"

        # GenerateContentConfig import を mock する
        mock_config_cls = MagicMock()
        mock_config_instance = MagicMock()
        mock_config_cls.return_value = mock_config_instance

        with patch.dict("sys.modules", {
            "google": MagicMock(),
            "google.genai": MagicMock(),
            "google.genai.types": MagicMock(GenerateContentConfig=mock_config_cls),
        }):
            # SDK 型を mock したうえで complete を呼ぶ
            provider2 = VertexGeminiProvider(model="gemini-test", client=mock_client)
            result = provider2.complete(prompt, temperature=0.5, max_tokens=128)

        # generate_content が呼ばれた
        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args

        # model と contents が渡された
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        args = call_kwargs.args if call_kwargs.args else ()
        # contents = prompt
        all_args = args + tuple(kwargs.values())
        assert prompt in all_args or any(prompt == v for v in kwargs.values()), (
            f"prompt が generate_content に渡されていない: {call_kwargs}"
        )

    def test_returns_response_text(self):
        """complete() が response.text を返す。"""
        expected = "エージェント 1 と 2 が出会った (場所: poi_park_001)。"
        mock_client = _make_mock_client(expected)
        provider = VertexGeminiProvider(client=mock_client)

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.complete("dummy prompt")

        assert result == expected

    def test_strips_trailing_newline(self):
        """応答末尾の改行を除去する。"""
        mock_client = _make_mock_client("応答テキスト\n")
        provider = VertexGeminiProvider(client=mock_client)

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.complete("prompt")

        assert not result.endswith("\n")
        assert result == "応答テキスト"

    def test_model_name_passed_to_client(self):
        """モデル名が generate_content に渡される。"""
        mock_client = _make_mock_client("ok")
        provider = VertexGeminiProvider(model="gemini-custom-model", client=mock_client)

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            provider.complete("prompt")

        call_kwargs = mock_client.models.generate_content.call_args
        # model 引数を確認
        passed = (
            call_kwargs.kwargs.get("model")
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert passed == "gemini-custom-model", (
            f"モデル名が正しく渡されていない: {call_kwargs}"
        )

    # ── SDK 未インストール時の ImportError ─────────────────────────────────────

    def test_import_error_when_sdk_missing(self):
        """SDK (google.genai) が未インストール時に明確な ImportError を上げる。"""
        # client=None で遅延 import パスを通す
        provider = VertexGeminiProvider(client=None)

        # sys.modules から google.genai を消して未インストール状態を再現する
        import sys
        saved = {}
        for key in list(sys.modules.keys()):
            if "google" in key:
                saved[key] = sys.modules.pop(key)
        try:
            with pytest.raises(ImportError, match="google-genai"):
                provider.complete("prompt")
        finally:
            sys.modules.update(saved)


# ─────────────────────────────────────────────────────────────────────────────
# make_llm_provider ファクトリ
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeLlmProvider:
    """make_llm_provider ファクトリのテスト。"""

    def test_rule_returns_rule_based_provider(self):
        """kind='rule' で RuleBasedProvider が返る。"""
        p = make_llm_provider("rule")
        assert isinstance(p, RuleBasedProvider)

    def test_vertex_returns_vertex_provider(self):
        """kind='vertex' で VertexGeminiProvider が返る。"""
        mock_client = _make_mock_client()
        p = make_llm_provider("vertex", client=mock_client)
        assert isinstance(p, VertexGeminiProvider)

    def test_unknown_kind_raises_value_error(self):
        """未知の kind で ValueError が上がる。"""
        with pytest.raises(ValueError, match="未知の LLM プロバイダ kind"):
            make_llm_provider("openai")

    def test_default_kind_is_rule(self):
        """引数なしで RuleBasedProvider が返る。"""
        p = make_llm_provider()
        assert isinstance(p, RuleBasedProvider)

    def test_vertex_opts_forwarded(self):
        """vertex 時に opts が VertexGeminiProvider に渡される。"""
        mock_client = _make_mock_client()
        p = make_llm_provider("vertex", model="gemini-test", client=mock_client)
        assert isinstance(p, VertexGeminiProvider)
        assert p.model == "gemini-test"


# ─────────────────────────────────────────────────────────────────────────────
# build_prompt
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildPrompt:
    """build_prompt が §10.3 入力を含むプロンプトを組み立てるテスト。"""

    def test_contains_required_markers(self):
        """必須マーカー (event_type / agent_a_id / agent_b_id / location_poi_id) を含む。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=1,
            agent_b_id=2,
            event_type="conversation",
            location_poi_id="poi_cafe_001",
        )
        assert "event_type:" in prompt
        assert "agent_a_id:" in prompt
        assert "agent_b_id:" in prompt
        assert "location_poi_id:" in prompt

    def test_marker_values_correct(self):
        """マーカー値が引数と一致する。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=42,
            agent_b_id=99,
            event_type="meeting",
            location_poi_id="poi_park_007",
        )
        assert "event_type: meeting" in prompt
        assert "agent_a_id: 42" in prompt
        assert "agent_b_id: 99" in prompt
        assert "location_poi_id: poi_park_007" in prompt

    def test_summary_prompt_type(self):
        """prompt_type='summary' でタスク説明が含まれる。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=1,
            agent_b_id=2,
            event_type="conflict",
            location_poi_id="poi_bar_001",
        )
        assert "要約" in prompt or "summary" in prompt.lower() or "タスク" in prompt

    def test_relationship_reason_prompt_type(self):
        """prompt_type='relationship_reason' でタスク説明が含まれる。"""
        prompt = build_prompt(
            prompt_type="relationship_reason",
            agent_a_id=3,
            agent_b_id=5,
            event_type="farewell",
            location_poi_id="poi_station_001",
        )
        assert "理由" in prompt or "関係" in prompt or "タスク" in prompt

    def test_optional_context_included(self):
        """任意コンテキストフィールドが含まれる (§10.3)。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=1,
            agent_b_id=2,
            event_type="conversation",
            location_poi_id="poi_001",
            current_time="12:00:00",
            relationship_state="acquaintance",
            nearby_pois=["poi_002", "poi_003"],
            agent_a_profile={"name": "Tanaka Ken", "age": 35},
            agent_b_profile={"name": "Sato Makoto", "age": 28},
        )
        assert "12:00:00" in prompt
        assert "acquaintance" in prompt
        assert "poi_002" in prompt
        assert "Tanaka Ken" in prompt

    def test_optional_fields_omitted_when_none(self):
        """None の任意フィールドはプロンプトに現れない。"""
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=1,
            agent_b_id=2,
            event_type="meeting",
            location_poi_id="poi_001",
        )
        # 省略フィールドが None として文字列に残らない
        assert "None" not in prompt

    def test_returns_string(self):
        """戻り値が str。"""
        result = build_prompt(
            prompt_type="summary",
            agent_a_id=0,
            agent_b_id=1,
            event_type="meeting",
            location_poi_id="poi_000",
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────────────
# SDK import なし確認 (最重要: RuleBased 経路でのモジュール import 安全性)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoSdkImportForRuleBased:
    """RuleBased 経路で google.genai SDK が import されないことを確認する。"""

    def test_import_llm_provider_without_sdk(self):
        """app.llm_provider の import 自体は SDK なしで成功する。"""
        # SDK が存在しなくても import できる (遅延 import のため)
        import importlib
        import sys

        # 念のため sys.modules から google.genai を外す
        saved = {}
        for key in list(sys.modules.keys()):
            if key.startswith("google.genai") or key == "google":
                saved[key] = sys.modules.pop(key)
        try:
            # 再 import を強制
            if "app.llm_provider" in sys.modules:
                del sys.modules["app.llm_provider"]
            import app.llm_provider as m
            assert hasattr(m, "LLMProvider")
            assert hasattr(m, "RuleBasedProvider")
            assert hasattr(m, "make_llm_provider")
        finally:
            sys.modules.update(saved)
            # app.llm_provider を再ロードしてキャッシュを戻す
            if "app.llm_provider" in sys.modules:
                del sys.modules["app.llm_provider"]
            import app.llm_provider  # noqa: F401

    def test_rule_based_complete_without_sdk(self):
        """SDK なしで RuleBasedProvider.complete() が動作する。"""
        provider = make_llm_provider("rule")
        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=0,
            agent_b_id=1,
            event_type="meeting",
            location_poi_id="poi_001",
        )
        # SDK なしで完走する
        result = provider.complete(prompt)
        assert isinstance(result, str)
        assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────────────
# sim との統合: RuleBased で既存決定論テストを pass させる
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulationWithRuleBasedProvider:
    """RuleBasedProvider を渡した Simulation が byte 一致決定論を維持する。"""

    @pytest.fixture(scope="class")
    def sample_inputs(self):
        """100 agent / 300 POI の合成入力を生成する。"""
        from environments.urban_2d.simulation import load_inputs
        from tools.generate_urban_sample import generate as gen_sample

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tmp = tempfile.mkdtemp(prefix="llm_prov_test_")
            gen_sample(tmp, seed=42, agents=100, pois=300, ticks=24, run_id="urban_sample")
            pois, profiles = load_inputs(
                Path(tmp) / "pois.geojson",
                Path(tmp) / "agent_profiles_N100.json",
            )
        return pois, profiles

    def test_rule_based_provider_accepted(self, sample_inputs):
        """Simulation が RuleBasedProvider を受け付けて完走する。"""
        from environments.urban_2d.simulation import Simulation
        pois, profiles = sample_inputs
        provider = make_llm_provider("rule")
        sim = Simulation(pois, profiles, seed=42, ticks=24, llm_provider=provider)
        sim.simulate()
        assert len(sim.agent_states) == 100 * 24

    def test_determinism_with_rule_based(self, sample_inputs, tmp_path):
        """RuleBasedProvider 渡し・なし両方で 3 jsonl が byte 一致する (§13.3.2)。"""
        import filecmp
        from environments.urban_2d.simulation import Simulation

        pois, profiles = sample_inputs
        provider = make_llm_provider("rule")

        out_a = tmp_path / "run_with_provider"
        out_b = tmp_path / "run_no_provider"

        Simulation(pois, profiles, seed=42, ticks=24, run_id="run_a",
                   llm_provider=provider).run(out_a)
        # provider=None → 内部で RuleBasedProvider を遅延生成する
        Simulation(pois, profiles, seed=42, ticks=24, run_id="run_b",
                   llm_provider=None).run(out_b)

        for name in (
            "agent_states.jsonl",
            "poi_visit_records.jsonl",
            "interaction_events.jsonl",
        ):
            assert filecmp.cmp(out_a / name, out_b / name, shallow=False), (
                f"{name}: provider 渡しと None で byte 不一致"
            )

    def test_summary_content_with_rule_based(self, sample_inputs):
        """RuleBasedProvider の summary が simulation テンプレ文と一致する。"""
        from environments.urban_2d.simulation import Simulation
        pois, profiles = sample_inputs
        provider = make_llm_provider("rule")
        sim = Simulation(pois, profiles, seed=42, ticks=24, llm_provider=provider)
        sim.simulate()

        assert sim.interaction_events, "interaction イベントが 1 件も発生していない"

        # 各 summary が simulation._summary_text テンプレ形式と一致する
        for event in sim.interaction_events:
            expected = Simulation._summary_text(
                event["type"],
                event["agent_ids"][0],
                event["agent_ids"][1],
                event["location_poi_id"],
            )
            assert event["summary"] == expected, (
                f"summary 不一致: {event['summary']!r} != {expected!r}"
            )
