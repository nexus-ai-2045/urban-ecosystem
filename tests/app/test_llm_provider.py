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
    ALLOWED_CATEGORIES_19_3_1,
    LLMProvider,
    RuleBasedProvider,
    VertexGeminiProvider,
    build_destination_prompt,
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

        # SDK インストール済みでも未インストールを再現する。
        # sys.modules に None を入れると、その名前の import は ImportError になる
        # (pop だけだと SDK 実在環境では re-import が成功してしまうため None 注入を使う)。
        import sys
        blocked = ["google.genai", "google.genai.types", "google.genai.errors"]
        saved = {k: sys.modules.get(k) for k in blocked}
        for k in blocked:
            sys.modules[k] = None
        try:
            with pytest.raises(ImportError, match="google-genai"):
                provider.complete("prompt")
        finally:
            for k in blocked:
                if saved[k] is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = saved[k]


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


# ─────────────────────────────────────────────────────────────────────────────
# choose_destination_category — §10.2 行動決定 LLM 化
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleBasedChooseDestinationCategory:
    """RuleBasedProvider.choose_destination_category の決定論テスト。"""

    @pytest.fixture(autouse=True)
    def provider(self) -> RuleBasedProvider:
        return RuleBasedProvider()

    _ALLOWED = ["amenity-cafe", "amenity-restaurant", "amenity-fast_food"]
    _CTX = {"agent_id": 1, "role": "office_worker", "current_time": "12:00:00"}

    def test_returns_string(self, provider):
        """戻り値が str。"""
        result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert isinstance(result, str)

    def test_returns_empty_string(self, provider):
        """RuleBasedProvider は必ず "" を返す (§9.3 fallback シグナル)。"""
        result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == "", f"RuleBased は '' を返すべきだが {result!r} が返った"

    def test_deterministic_same_input(self, provider):
        """同一引数に対して常に同一出力 (決定論)。"""
        results = [
            provider.choose_destination_category(self._CTX, self._ALLOWED)
            for _ in range(5)
        ]
        assert len(set(results)) == 1

    def test_empty_allowed_categories(self, provider):
        """allowed_categories が空でもクラッシュしない。"""
        result = provider.choose_destination_category(self._CTX, [])
        assert isinstance(result, str)

    def test_is_abstract_method_implemented(self, provider):
        """LLMProvider の抽象メソッドが実装されている。"""
        assert hasattr(provider, "choose_destination_category")
        assert callable(provider.choose_destination_category)

    def test_context_ignored(self, provider):
        """コンテキストの内容に関わらず同一出力 (RuleBased は context を無視)。"""
        ctx_a = {"agent_id": 1, "role": "office_worker", "current_time": "09:00:00"}
        ctx_b = {"agent_id": 99, "role": "student", "current_time": "20:00:00"}
        r_a = provider.choose_destination_category(ctx_a, self._ALLOWED)
        r_b = provider.choose_destination_category(ctx_b, self._ALLOWED)
        assert r_a == r_b == ""


class TestVertexGeminiChooseDestinationCategory:
    """VertexGeminiProvider.choose_destination_category の mock テスト (実 Gemini 不使用)。"""

    _ALLOWED = ["amenity-cafe", "amenity-restaurant", "amenity-fast_food"]
    _CTX = {"agent_id": 5, "role": "other", "current_time": "12:30:00"}

    def _make_provider(self, response_text: str) -> VertexGeminiProvider:
        """指定テキストを返す mock クライアント付き VertexGeminiProvider を返す。"""
        mock_client = _make_mock_client(response_text)
        provider = VertexGeminiProvider(client=mock_client)
        return provider

    # ── 正常選択 ──────────────────────────────────────────────────────────────

    def test_returns_valid_category(self):
        """Gemini が有効カテゴリを返した場合、そのカテゴリを返す。"""
        provider = self._make_provider("amenity-cafe")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == "amenity-cafe"

    def test_returns_any_valid_category(self):
        """allowed_categories のいずれかが返る。"""
        provider = self._make_provider("amenity-restaurant")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result in self._ALLOWED

    def test_strips_trailing_punctuation(self):
        """末尾の句読点を除去してカテゴリを認識する。"""
        provider = self._make_provider("amenity-fast_food。")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == "amenity-fast_food"

    def test_multiline_response_finds_category(self):
        """複数行応答でも有効カテゴリを取り出せる。"""
        provider = self._make_provider("以下が選択カテゴリです:\namenity-cafe\n説明文")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == "amenity-cafe"

    # ── 不正カテゴリ検出 → fallback ────────────────────────────────────────────

    def test_invalid_category_returns_empty_string(self):
        """allowed_categories 外のカテゴリが返った場合は "" を返す (fallback シグナル)。"""
        provider = self._make_provider("home-residential")  # allowed 外
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == ""

    def test_garbage_response_returns_empty_string(self):
        """意味不明な応答は "" を返す。"""
        provider = self._make_provider("申し訳ありませんが、わかりません。")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == ""

    def test_empty_response_returns_empty_string(self):
        """空応答は "" を返す。"""
        provider = self._make_provider("")
        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            result = provider.choose_destination_category(self._CTX, self._ALLOWED)
        assert result == ""

    def test_empty_allowed_categories_returns_empty_string(self):
        """allowed_categories が空なら "" を返す (API 呼び出し不要)。"""
        provider = self._make_provider("amenity-cafe")
        result = provider.choose_destination_category(self._CTX, [])
        assert result == ""
        # API を呼び出していないことも確認
        provider._client.models.generate_content.assert_not_called()

    # ── uses temperature=0.0 (決定論) ─────────────────────────────────────────

    def test_called_with_temperature_zero(self):
        """temperature=0.0 で complete を呼ぶ (決定論的選択)。"""
        mock_client = _make_mock_client("amenity-cafe")
        provider = VertexGeminiProvider(client=mock_client)

        # complete() をラップしてコールを追跡する
        original_complete = provider.complete
        call_kwargs_store = []

        def _wrapped_complete(prompt, **kwargs):
            call_kwargs_store.append(kwargs)
            return original_complete(prompt, **kwargs)

        provider.complete = _wrapped_complete

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            provider.choose_destination_category(self._CTX, self._ALLOWED)

        assert call_kwargs_store, "complete() が呼ばれていない"
        assert call_kwargs_store[0].get("temperature") == 0.0, (
            "temperature=0.0 で呼ばれていない"
        )


# ─────────────────────────────────────────────────────────────────────────────
# build_destination_prompt
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildDestinationPrompt:
    """build_destination_prompt が §10.3 入力 + allowed_categories を含むプロンプトを組む。"""

    _ALLOWED = ["amenity-cafe", "amenity-restaurant", "amenity-fast_food"]
    _CTX = {
        "agent_id": 10,
        "role": "office_worker",
        "current_time": "12:00:00",
        "current_location": "poi_office_001",
    }

    def test_returns_string(self):
        """戻り値が str。"""
        result = build_destination_prompt(context=self._CTX, allowed_categories=self._ALLOWED)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_all_allowed_categories(self):
        """許可カテゴリが全てプロンプトに含まれる。"""
        prompt = build_destination_prompt(context=self._CTX, allowed_categories=self._ALLOWED)
        for cat in self._ALLOWED:
            assert cat in prompt, f"カテゴリ {cat!r} がプロンプトに含まれていない"

    def test_contains_context_fields(self):
        """コンテキストの各フィールドがプロンプトに含まれる。"""
        prompt = build_destination_prompt(context=self._CTX, allowed_categories=self._ALLOWED)
        assert "10" in prompt          # agent_id
        assert "office_worker" in prompt
        assert "12:00:00" in prompt
        assert "poi_office_001" in prompt

    def test_task_instruction_present(self):
        """タスク指示が含まれる。"""
        prompt = build_destination_prompt(context=self._CTX, allowed_categories=self._ALLOWED)
        assert "タスク" in prompt or "カテゴリ" in prompt

    def test_optional_context_omitted_when_missing(self):
        """None の任意フィールドはプロンプトに現れない。"""
        ctx_minimal = {"agent_id": 1, "role": "other"}
        prompt = build_destination_prompt(context=ctx_minimal, allowed_categories=self._ALLOWED)
        assert "None" not in prompt

    def test_empty_allowed_categories(self):
        """allowed_categories が空でもクラッシュしない。"""
        prompt = build_destination_prompt(context=self._CTX, allowed_categories=[])
        assert isinstance(prompt, str)


# ─────────────────────────────────────────────────────────────────────────────
# ALLOWED_CATEGORIES_19_3_1 定数
# ─────────────────────────────────────────────────────────────────────────────

class TestAllowedCategories19_3_1:
    """§19.3.1 カテゴリ集合定数の検証。"""

    def test_has_12_categories(self):
        """§19.3.1 は 12 カテゴリ。"""
        assert len(ALLOWED_CATEGORIES_19_3_1) == 12

    def test_contains_required_categories(self):
        """必須カテゴリが含まれる (§19.3.1 テーブルより)。"""
        required = {
            "amenity-cafe",
            "amenity-restaurant",
            "amenity-fast_food",
            "amenity-bar",
            "shop-convenience",
            "shop-clothing",
            "shop-supermarket",
            "leisure-park",
            "amenity-school",
            "office-building",
            "home-residential",
            "other-misc",
        }
        assert required == set(ALLOWED_CATEGORIES_19_3_1)

    def test_no_duplicates(self):
        """重複なし。"""
        assert len(ALLOWED_CATEGORIES_19_3_1) == len(set(ALLOWED_CATEGORIES_19_3_1))


# ─────────────────────────────────────────────────────────────────────────────
# sim + Gemini fallback: 不正カテゴリでも sim が §9.3 rule で完走
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulationGeminiFallback:
    """Gemini 経路で不正カテゴリが返っても sim が rule fallback で完走する。"""

    @pytest.fixture(scope="class")
    def sample_inputs(self):
        """合成入力を生成する。"""
        from environments.urban_2d.simulation import load_inputs
        from tools.generate_urban_sample import generate as gen_sample

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tmp = tempfile.mkdtemp(prefix="llm_fallback_test_")
            gen_sample(tmp, seed=42, agents=100, pois=300, ticks=24, run_id="urban_sample")
            pois, profiles = load_inputs(
                Path(tmp) / "pois.geojson",
                Path(tmp) / "agent_profiles_N100.json",
            )
        return pois, profiles

    def _make_invalid_provider(self) -> VertexGeminiProvider:
        """常に不正カテゴリ (allowed 外) を返す mock provider を返す。"""
        mock_client = _make_mock_client("INVALID_CATEGORY_XYZ")
        provider = VertexGeminiProvider(client=mock_client)
        return provider

    def test_sim_completes_with_invalid_category(self, sample_inputs):
        """不正カテゴリ応答でも sim が例外なく完走する。"""
        from environments.urban_2d.simulation import Simulation

        pois, profiles = sample_inputs
        provider = self._make_invalid_provider()

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            sim = Simulation(pois, profiles, seed=42, ticks=24, llm_provider=provider)
            sim.simulate()

        assert len(sim.agent_states) == 100 * 24, "sim が完走しなかった"

    def test_sim_produces_interactions_with_invalid_category(self, sample_inputs):
        """不正カテゴリ fallback でも interaction が生成される。"""
        from environments.urban_2d.simulation import Simulation

        pois, profiles = sample_inputs
        provider = self._make_invalid_provider()

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            sim = Simulation(pois, profiles, seed=42, ticks=24, llm_provider=provider)
            sim.simulate()

        assert len(sim.interaction_events) > 0, "fallback 時に interaction が 0 件"

    def test_rulebase_byte_identical_with_invalid_gemini(self, sample_inputs, tmp_path):
        """RuleBased 経路と Gemini 不正カテゴリ経路で agent_states/visit_records が byte 一致。

        Gemini fallback = §9.3 ルール = RuleBased と同一候補 → POI 選択も同一。
        ただし interaction_events の summary は Gemini 版で異なる可能性があるため除外。
        (今回 summary 生成は完結・不変のため byte 一致するが、将来的に Gemini が
         summary を生成する場合に備えてここでは agent_states と visit_records のみ検証。)
        """
        import filecmp
        from environments.urban_2d.simulation import Simulation

        pois, profiles = sample_inputs
        invalid_provider = self._make_invalid_provider()

        out_rule = tmp_path / "run_rule"
        out_gemini_fallback = tmp_path / "run_gemini_fallback"

        Simulation(
            pois, profiles, seed=42, ticks=24, run_id="rule",
            llm_provider=make_llm_provider("rule"),
        ).run(out_rule)

        with patch.dict("sys.modules", {
            "google.genai.types": MagicMock(GenerateContentConfig=MagicMock()),
        }):
            Simulation(
                pois, profiles, seed=42, ticks=24, run_id="gemini_fallback",
                llm_provider=invalid_provider,
            ).run(out_gemini_fallback)

        for name in ("agent_states.jsonl", "poi_visit_records.jsonl"):
            assert filecmp.cmp(out_rule / name, out_gemini_fallback / name, shallow=False), (
                f"{name}: RuleBased と Gemini fallback で byte 不一致"
            )
