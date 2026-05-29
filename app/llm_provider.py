"""
llm_provider.py — LLMProvider 抽象と具体実装 (spec §10)。

正本:
  - docs/ai-ecosystem-tool-spec.md §10.1 Provider 抽象 / §10.2 LLM 対象 / §10.3 プロンプト入力

責務:
  - LLMProvider ABC (§10.1 シグネチャ厳守)
  - RuleBasedProvider: LLM を呼ばない決定論テキスト (MVP 既定)
  - VertexGeminiProvider: Vertex AI Gemini を ADC で呼ぶ (opt-in)
  - make_llm_provider: ファクトリ関数
  - build_prompt: §10.3 構造化入力から会話要約用・関係理由用プロンプトを組む

決定論方針:
  RuleBasedProvider は simulation.py の _summary_text と完全同一のテンプレ文を返す。
  これにより RuleBased 経路で agent_states / interaction_events / poi_visit_records が
  byte 一致する (§13.3.2)。

SDK の遅延 import:
  VertexGeminiProvider の complete / __init__ の中でのみ google.genai を import する。
  RuleBasedProvider 経路やテスト実行時に SDK が未インストールでも import エラーにならない。

安全規則:
  - プロンプト本文・応答テキストを info ログに出力しない (§6 ルール準拠)
  - API キー / 認証情報をコードに書かない
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# §10.1 LLMProvider ABC
# ─────────────────────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """LLM プロバイダ抽象基底クラス (spec §10.1)。

    すべての実装は complete() を実装する。
    呼び出し側は必ず Provider 抽象越しに使う (LLM の直接呼び出し禁止)。
    """

    @abstractmethod
    def complete(self, prompt: str, *, temperature: float = 0.7, max_tokens: int = 256) -> str:
        """プロンプトを受け取りテキスト応答を返す (§10.1 シグネチャ厳守)。

        Args:
            prompt: 送信するプロンプトテキスト。
            temperature: サンプリング温度 (0.0〜1.0)。RuleBased では無視。
            max_tokens: 応答の最大トークン数。RuleBased では無視。

        Returns:
            応答テキスト (末尾の改行は含まない)。
        """


# ─────────────────────────────────────────────────────────────────────────────
# RuleBasedProvider — MVP 既定 / 決定論 / SDK 不要
# ─────────────────────────────────────────────────────────────────────────────

class RuleBasedProvider(LLMProvider):
    """MVP 既定プロバイダ。LLM を呼ばず決定論テキストを返す (spec §10.1)。

    complete() は prompt からイベント種別・エージェント ID・POI ID を抽出し、
    simulation.py の _summary_text と完全同一のテンプレ文を返す。
    同一入力には常に同一出力を返す (byte 一致保証 §13.3.2)。
    """

    # 会話要約用プロンプトのキーワードマーカー (build_prompt が埋め込む)
    _MARKER_EV_TYPE = "event_type:"
    _MARKER_AGENT_A = "agent_a_id:"
    _MARKER_AGENT_B = "agent_b_id:"
    _MARKER_POI = "location_poi_id:"

    def complete(self, prompt: str, *, temperature: float = 0.7, max_tokens: int = 256) -> str:
        """プロンプトのメタデータからテンプレ文を生成して返す。

        build_prompt が生成したプロンプトに含まれるマーカー行を解析し、
        simulation.py の _summary_text と同一のテンプレ文を返す。
        マーカーが見つからない場合はフォールバック文を返す。
        """
        ev_type = self._extract(prompt, self._MARKER_EV_TYPE)
        agent_a = self._extract(prompt, self._MARKER_AGENT_A)
        agent_b = self._extract(prompt, self._MARKER_AGENT_B)
        poi_id = self._extract(prompt, self._MARKER_POI)

        if ev_type and agent_a and agent_b and poi_id:
            return self._template_summary(ev_type, int(agent_a), int(agent_b), poi_id)

        # フォールバック: プロンプト種別が不明な場合
        return "（ルールベース応答）"

    @staticmethod
    def _extract(prompt: str, marker: str) -> Optional[str]:
        """prompt 中の 'marker <value>' 行から value を取り出す。"""
        for line in prompt.splitlines():
            stripped = line.strip()
            if stripped.startswith(marker):
                value = stripped[len(marker):].strip()
                return value if value else None
        return None

    @staticmethod
    def _template_summary(ev_type: str, a_id: int, b_id: int, poi_id: str) -> str:
        """simulation.py の _summary_text と完全同一のテンプレ文を返す。

        この実装は simulation._summary_text の複製であり、両者が同一出力を
        返すことが byte 一致 (§13.3.2) の根拠である。変更時は両方を同期する。
        """
        verb = {
            "meeting": "が出会った",
            "conversation": "が会話した",
            "conflict": "が口論した",
            "farewell": "が別れた",
        }.get(ev_type, "が交流した")
        return f"エージェント {a_id} と {b_id} {verb} (場所: {poi_id})。"


# ─────────────────────────────────────────────────────────────────────────────
# VertexGeminiProvider — opt-in / ADC 認証 / SDK 遅延 import
# ─────────────────────────────────────────────────────────────────────────────

class VertexGeminiProvider(LLMProvider):
    """Vertex AI Gemini を ADC (Application Default Credentials) で呼ぶプロバイダ。

    SDK: google-genai (pip install google-genai)。
    認証: gcloud auth application-default login または Cloud Run の Workload Identity。
    環境変数: GOOGLE_CLOUD_PROJECT が必須 (Vertex エンドポイント決定に使用)。

    遅延 import:
        complete / __init__ の内部でのみ SDK を import する。
        SDK 未インストールでも RuleBasedProvider 経路・テストは動作する。

    client 注入:
        テスト用に client 引数で mock クライアントを渡せる。
        None (既定) の場合は SDK から生成する。
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        project: Optional[str] = None,
        location: str = "us-central1",
        client: Optional[Any] = None,
    ) -> None:
        """初期化。

        Args:
            model: Gemini モデル名 (既定 gemini-2.5-flash / Vertex GA)。
            project: GCP プロジェクト ID。None の場合 ADC から自動取得。
            location: Vertex AI リージョン (既定 us-central1)。
            client: テスト用 mock クライアント。None で本番 SDK クライアントを生成。
        """
        self.model = model
        self.project = project
        self.location = location
        self._client = client  # None の場合は complete 内で遅延生成

    def _get_client(self) -> Any:
        """SDK クライアントを返す (遅延生成)。"""
        if self._client is not None:
            return self._client

        # 遅延 import: SDK が未インストールの環境でも RuleBased 経路は動く
        try:
            import google.genai as genai  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "VertexGeminiProvider を使用するには google-genai パッケージが必要です。\n"
                "  pip install google-genai\n"
                "ルールベース (LLM なし) で動かす場合は RuleBasedProvider を使用してください。"
            ) from e

        client = genai.Client(
            vertexai=True,
            project=self.project,
            location=self.location,
        )
        self._client = client
        return client

    def complete(self, prompt: str, *, temperature: float = 0.7, max_tokens: int = 256) -> str:
        """Vertex AI Gemini にプロンプトを送り応答テキストを返す。

        Args:
            prompt: 送信するプロンプト。
            temperature: サンプリング温度。
            max_tokens: 最大出力トークン数。

        Returns:
            応答テキスト (末尾改行なし)。

        Raises:
            ImportError: google-genai SDK が未インストールの場合。
            Exception: Vertex AI API 呼び出しエラーの場合。
        """
        # 遅延 import (generate_content 呼び出しに必要な型のみ)
        try:
            from google.genai.types import GenerateContentConfig  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "VertexGeminiProvider を使用するには google-genai パッケージが必要です。\n"
                "  pip install google-genai"
            ) from e

        client = self._get_client()

        # プロンプト本文・応答テキストは info ログに出さない (§6 ルール)
        logger.debug("Vertex Gemini へリクエストを送信 (model=%s)", self.model)

        config = GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        logger.debug("Vertex Gemini からレスポンスを受信")

        # テキスト部分を取り出す
        text: str = response.text if hasattr(response, "text") else ""
        return text.rstrip("\n")


# ─────────────────────────────────────────────────────────────────────────────
# ファクトリ
# ─────────────────────────────────────────────────────────────────────────────

def make_llm_provider(kind: str = "rule", **opts: Any) -> LLMProvider:
    """LLMProvider インスタンスを生成するファクトリ関数。

    Args:
        kind: "rule" (RuleBasedProvider) / "vertex" (VertexGeminiProvider)。
        **opts: VertexGeminiProvider に渡すオプション
                (model, project, location, client)。

    Returns:
        LLMProvider インスタンス。

    Raises:
        ValueError: 未知の kind の場合。
    """
    if kind == "rule":
        return RuleBasedProvider()
    if kind == "vertex":
        return VertexGeminiProvider(**opts)
    raise ValueError(f"未知の LLM プロバイダ kind: {kind!r}。'rule' または 'vertex' を指定してください。")


# ─────────────────────────────────────────────────────────────────────────────
# §10.3 プロンプトビルダ
# ─────────────────────────────────────────────────────────────────────────────

def build_prompt(
    *,
    prompt_type: str,
    # §10.3 構造化入力
    agent_a_id: int,
    agent_b_id: int,
    event_type: str,
    location_poi_id: str,
    # 追加コンテキスト (任意)
    agent_a_profile: Optional[dict[str, Any]] = None,
    agent_b_profile: Optional[dict[str, Any]] = None,
    current_time: Optional[str] = None,
    current_location: Optional[str] = None,
    nearby_pois: Optional[list[str]] = None,
    nearby_agents: Optional[list[int]] = None,
    recent_visits: Optional[list[dict[str, Any]]] = None,
    recent_interactions: Optional[list[dict[str, Any]]] = None,
    relationship_state: Optional[str] = None,
) -> str:
    """§10.3 構造化入力から LLM プロンプトを組み立てる。

    RuleBasedProvider.complete() がマーカー行を解析して決定論テキストを返す。
    VertexGeminiProvider では同プロンプトを Gemini に送信する。

    Args:
        prompt_type: "summary" (会話要約) または "relationship_reason" (関係変化理由)。
        agent_a_id: エージェント A の ID。
        agent_b_id: エージェント B の ID。
        event_type: interaction type (meeting / conversation / conflict / farewell)。
        location_poi_id: 発生場所の POI ID。
        agent_a_profile: エージェント A のプロフィール dict (任意)。
        agent_b_profile: エージェント B のプロフィール dict (任意)。
        current_time: 現在時刻 HH:MM:SS (任意)。
        current_location: 現在地の説明 (任意)。
        nearby_pois: 近傍 POI ID リスト (任意)。
        nearby_agents: 近傍エージェント ID リスト (任意)。
        recent_visits: 直近の visit record リスト (任意)。
        recent_interactions: 直近の interaction event リスト (任意)。
        relationship_state: 現在の関係状態 (stranger/acquaintance/friend 等) (任意)。

    Returns:
        LLMProvider.complete() に渡すプロンプト文字列。
    """
    lines: list[str] = []

    # ── RuleBased 用マーカー行 (complete() がここを解析する) ─────────────────
    lines.append(f"event_type: {event_type}")
    lines.append(f"agent_a_id: {agent_a_id}")
    lines.append(f"agent_b_id: {agent_b_id}")
    lines.append(f"location_poi_id: {location_poi_id}")

    # ── §10.3 構造化入力セクション ─────────────────────────────────────────────
    if prompt_type == "summary":
        lines.append("")
        lines.append("## タスク")
        lines.append(
            f"エージェント {agent_a_id} とエージェント {agent_b_id} が "
            f"'{event_type}' イベントを起こした。"
            f"場所: {location_poi_id}。"
            "この出来事の短い要約文 (1〜2 文) を日本語で生成してください。"
        )
    elif prompt_type == "relationship_reason":
        lines.append("")
        lines.append("## タスク")
        lines.append(
            f"エージェント {agent_a_id} とエージェント {agent_b_id} の関係が "
            f"'{event_type}' イベントにより変化した。"
            "この関係変化の理由を 1 文で日本語で説明してください。"
        )

    # ── §10.3 コンテキスト (任意フィールド) ─────────────────────────────────────
    lines.append("")
    lines.append("## コンテキスト")

    if current_time:
        lines.append(f"- 現在時刻: {current_time}")

    if current_location:
        lines.append(f"- 現在地: {current_location}")

    if agent_a_profile:
        lines.append(f"- エージェント {agent_a_id} プロフィール: {agent_a_profile}")

    if agent_b_profile:
        lines.append(f"- エージェント {agent_b_id} プロフィール: {agent_b_profile}")

    if nearby_pois:
        lines.append(f"- 近傍 POI: {', '.join(nearby_pois)}")

    if nearby_agents:
        lines.append(f"- 近傍エージェント: {nearby_agents}")

    if recent_visits:
        lines.append(f"- 直近の訪問: {recent_visits}")

    if recent_interactions:
        lines.append(f"- 直近のやりとり: {recent_interactions}")

    if relationship_state:
        lines.append(f"- 現在の関係状態: {relationship_state}")

    return "\n".join(lines)
