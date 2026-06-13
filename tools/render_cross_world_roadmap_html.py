"""Render the Cross-world Operator Mode roadmap HTML preview.

The Markdown roadmap is the source of truth. This renderer keeps the richer
homepage-style HTML from drifting when roadmap content changes.
"""

from __future__ import annotations

import argparse
import difflib
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_MD = PROJECT_ROOT / "docs" / "cross-world-operator-roadmap.md"
ROADMAP_HTML = PROJECT_ROOT / "docs" / "cross-world-operator-roadmap.html"


@dataclass(frozen=True)
class Phase:
    number: int
    source_title: str
    display_title: str
    description: str
    bullets: list[str]


PHASE_TITLES = {
    "Operator MVP": "最初の操作モードを作る",
    "Motif Arcs": "世界観パックを取り込む",
    "Assessment / World Layers": "評価と世界レイヤーを作る",
    "Governance / Operations": "運用と合議制にする",
}

PHASE_DESCRIPTIONS = {
    "Operator MVP": "エージェントの視点に入り、世界を渡り、案内・監視・介入の最小単位を作る。",
    "Motif Arcs": "人物名ではなく、代償、評議会、暴走、境界、訓練、監視、環境交渉、同期などの構造として取り込む。",
    "Assessment / World Layers": "人間とAIの境界、三層世界、イベント感、混沌、規模、能力評価を安全な評価枠にする。",
    "Governance / Operations": "FDE、外部監視、repo-as-skill、分散運用、クラウド境界、世界構築pipelineを運用へ接続する。",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _version(markdown: str) -> str:
    match = re.search(r"^- Version: `([^`]+)`", markdown, flags=re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def _section(markdown: str, title: str) -> str:
    pattern = re.compile(rf"^## {re.escape(title)}\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def _bullets(section_body: str) -> list[str]:
    return [line[2:].strip(" `") for line in section_body.splitlines() if line.startswith("- ")]


def parse_phases(markdown: str) -> list[Phase]:
    body = _section(markdown, "ロードマップ概要")
    if not body:
        return [
            Phase(1, "Operator MVP", "最初の操作モードを作る", PHASE_DESCRIPTIONS["Operator MVP"], ["Sentinel MVP"]),
        ]

    chunks = re.split(r"^### Phase\s+([0-9]+):\s+(.+?)\s*$", body, flags=re.MULTILINE)
    phases: list[Phase] = []
    for index in range(1, len(chunks), 3):
        number = int(chunks[index])
        source_title = chunks[index + 1].strip()
        content = chunks[index + 2]
        bullets = _bullets(content)
        paragraphs = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.startswith("- ") and not line.startswith("### ")
        ]
        description = " ".join(paragraphs)
        if not description:
            description = PHASE_DESCRIPTIONS.get(source_title, "正本ロードマップから同期されたフェーズ。")
        phases.append(
            Phase(
                number=number,
                source_title=source_title,
                display_title=PHASE_TITLES.get(source_title, source_title),
                description=description,
                bullets=bullets,
            )
        )
    return phases


def _non_goals(markdown: str) -> list[str]:
    goals = _bullets(_section(markdown, "Non-goals"))
    return goals or [
        "固有キャラクターをそのまま再現しない。",
        "保護された台詞をコードに埋め込まない。",
        "未レビューの外部投稿、外部チケット作成、クラウド変更をしない。",
    ]


def _minimum_world_packet(markdown: str) -> list[str]:
    packet = _bullets(_section(markdown, "Minimum World Packet"))
    return packet or [
        "place and environment",
        "rules of possibility",
        "social fabric",
        "resources and power",
        "history and memory",
        "daily life signal",
        "change pressure",
    ]


def _phase_html(phases: list[Phase]) -> str:
    cards: list[str] = []
    for phase in phases:
        bullets = "\n".join(f"              <li>{html.escape(item)}</li>" for item in phase.bullets[:12])
        cards.append(
            f"""          <article class="phase">
            <div class="phase-number">{phase.number:02d}</div>
            <div>
              <h3>{html.escape(phase.display_title)}</h3>
              <p>{html.escape(phase.description)}</p>
              <span class="id">Phase {phase.number}: {html.escape(phase.source_title)}</span>
            </div>
            <ul>
{bullets}
            </ul>
          </article>"""
        )
    return "\n\n".join(cards)


def _list_html(items: list[str]) -> str:
    return "\n".join(f"          <li>{html.escape(item)}</li>" for item in items)


def generate_html(project_root: Path = PROJECT_ROOT) -> str:
    markdown = _read(project_root / "docs" / "cross-world-operator-roadmap.md")
    version = _version(markdown)
    phases = parse_phases(markdown)
    non_goals = _non_goals(markdown)
    packet_items = _minimum_world_packet(markdown)
    phase_cards = _phase_html(phases)
    non_goal_items = _list_html(non_goals)
    packet_cards = "\n".join(
        f"""          <article class="mini-card">
            <strong>{html.escape(item)}</strong>
          </article>"""
        for item in packet_items
    )

    return f"""<!doctype html>
<!-- Generated by tools/render_cross_world_roadmap_html.py; do not edit by hand. -->
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>世界をまたぐ操作モード ロードマップ</title>
  <style>
    :root {{
      --bg: #f5f3ee;
      --paper: #fffefa;
      --ink: #202124;
      --muted: #62615b;
      --line: #d8d2c4;
      --teal: #0f766e;
      --blue: #315f8f;
      --amber: #b86b16;
      --coral: #b94e48;
      --shadow: 0 24px 60px rgba(31, 28, 20, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.7;
    }}
    a {{ color: var(--teal); text-underline-offset: 3px; }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 1px solid rgba(32, 33, 36, 0.1);
      background: rgba(245, 243, 238, 0.86);
      backdrop-filter: blur(14px);
    }}
    .nav-inner {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .brand {{ font-weight: 800; }}
    .nav-links {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.92rem; }}
    .nav-links a {{ color: var(--muted); text-decoration: none; }}
    .hero {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 44px 20px 28px;
      display: grid;
      grid-template-columns: minmax(0, 0.92fr) minmax(360px, 1.08fr);
      gap: 30px;
      align-items: center;
    }}
    .eyebrow {{ margin: 0 0 10px; color: var(--teal); font-size: 0.9rem; font-weight: 800; }}
    h1, h2, h3 {{ letter-spacing: 0; line-height: 1.22; }}
    h1 {{ margin: 0; font-size: clamp(2.3rem, 5vw, 4.8rem); max-width: 9.5em; }}
    h2 {{ margin: 0 0 16px; font-size: clamp(1.65rem, 3vw, 2.4rem); }}
    h3 {{ margin: 0 0 8px; font-size: 1.08rem; }}
    p {{ margin: 0; }}
    .lead {{ margin-top: 18px; color: #3d3c37; font-size: 1.12rem; max-width: 36rem; }}
    .hero-actions {{ margin-top: 22px; display: flex; gap: 10px; flex-wrap: wrap; }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 14px;
      color: var(--ink);
      background: var(--paper);
      text-decoration: none;
      font-weight: 700;
    }}
    .button.primary {{ border-color: #174c49; background: #174c49; color: #fff; }}
    .hero-visual {{
      margin: 0;
      border: 1px solid rgba(32, 33, 36, 0.12);
      border-radius: 8px;
      overflow: hidden;
      background: var(--paper);
      box-shadow: var(--shadow);
    }}
    .hero-visual img {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; }}
    .hero-visual figcaption {{
      padding: 10px 12px;
      color: var(--muted);
      font-size: 0.86rem;
      border-top: 1px solid var(--line);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 20px 20px 64px; }}
    section {{ margin-top: 52px; }}
    .summary-grid, .proof-grid, .packet-grid, .docs-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 14px;
    }}
    .summary-card, .phase, .gate, .mini-card, .doc-link {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .summary-card strong {{
      display: block;
      margin-bottom: 5px;
      color: var(--teal);
      font-size: 1.45rem;
      line-height: 1.1;
    }}
    .summary-card span, .id {{ color: var(--muted); }}
    .id {{
      display: block;
      margin-top: 8px;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.78rem;
    }}
    .journey {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .world {{
      position: relative;
      min-height: 170px;
      overflow: hidden;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .world::after {{
      content: "";
      position: absolute;
      right: -44px;
      bottom: -54px;
      width: 150px;
      height: 150px;
      border: 18px solid rgba(15, 118, 110, 0.12);
      border-radius: 999px;
    }}
    .world.simulated::after {{ border-color: rgba(49, 95, 143, 0.15); }}
    .world.liminal::after {{ border-color: rgba(184, 107, 22, 0.16); }}
    .world small {{ display: block; color: var(--muted); font-weight: 700; margin-bottom: 8px; }}
    .timeline {{ display: grid; gap: 12px; }}
    .phase {{
      display: grid;
      grid-template-columns: 56px minmax(0, 1fr) minmax(220px, 0.45fr);
      gap: 16px;
      align-items: start;
    }}
    .phase-number {{
      width: 42px;
      height: 42px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #fff;
      background: var(--teal);
      font-weight: 800;
    }}
    .phase:nth-child(2) .phase-number {{ background: var(--blue); }}
    .phase:nth-child(3) .phase-number {{ background: var(--amber); }}
    .phase:nth-child(4) .phase-number {{ background: var(--coral); }}
    .phase p {{ color: #3d3c37; }}
    .phase ul, .plain-list {{ margin: 0; padding-left: 1.1rem; color: var(--muted); }}
    .gate {{ border-left: 5px solid var(--amber); }}
    .gate strong, .mini-card strong {{ display: block; margin-bottom: 6px; }}
    .doc-link {{ display: block; min-height: 110px; text-decoration: none; color: var(--ink); }}
    .doc-link span {{ display: block; margin-top: 8px; color: var(--muted); font-size: 0.92rem; }}
    footer {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 0 20px 42px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    @media (max-width: 860px) {{
      .hero, .journey, .phase {{ grid-template-columns: 1fr; }}
      .hero {{ padding-top: 26px; }}
      .phase-number {{ width: 36px; height: 36px; }}
    }}
  </style>
</head>
<body>
  <div class="site-shell">
    <nav class="nav" aria-label="ページ内ナビゲーション">
      <div class="nav-inner">
        <div class="brand">世界をまたぐ操作モード</div>
        <div class="nav-links">
          <a href="#overview">概要</a>
          <a href="#worlds">三つの世界</a>
          <a href="#roadmap">ロードマップ</a>
          <a href="#gates">保証</a>
          <a href="#docs">正本</a>
        </div>
      </div>
    </nav>

    <header class="hero">
      <div>
        <p class="eyebrow">Cross-world Operator Mode / Version: {html.escape(version)}</p>
        <h1>AIエージェントを、世界ごと動かせるようにする。</h1>
        <p class="lead">
          これは、複数の世界レイヤーをまたいで、観測・操作・案内・レビューを行うためのロードマップです。
          まずは「誰に入るか」よりも、「どの世界で、何を見て、どこまで動かしてよいか」を決めます。
        </p>
        <div class="hero-actions">
          <a class="button primary" href="#roadmap">次に作るものを見る</a>
          <a class="button" href="cross-world-operator-todo.html">未実装TODOを見る</a>
        </div>
      </div>
      <figure class="hero-visual">
        <img src="assets/cross-world-roadmap-hero.png" alt="三層の世界、操作ノード、レビューゲートを抽象的に表したロードマップのキービジュアル">
        <figcaption>三つの世界、操作ノード、レビューゲートを一枚にまとめた抽象イメージ。</figcaption>
      </figure>
    </header>

    <main>
      <section id="overview">
        <h2>一言でいうと</h2>
        <div class="summary-grid">
          <article class="summary-card"><strong>入る</strong><span>エージェントの視点に入り、何を見ているかを確認する。</span></article>
          <article class="summary-card"><strong>渡る</strong><span>現実、シミュレーション、あいだの世界を行き来する。</span></article>
          <article class="summary-card"><strong>守る</strong><span>操作できる範囲、公開してよい名前、人間レビューを明確にする。</span></article>
          <article class="summary-card"><strong>増やす</strong><span>新しいモチーフや世界観を、安全な抽象名に変換して追加する。</span></article>
        </div>
      </section>

      <section id="worlds">
        <h2>舞台は三つ</h2>
        <div class="journey">
          <article class="world physical"><small>1 / 現実</small><h3>人間が責任を持つ場所</h3><p>レビュー、承認、公開判断、費用、アカウント、クラウド利用などはここで扱う。</p><span class="id">physical</span></article>
          <article class="world simulated"><small>2 / 仮想</small><h3>試しに動かす場所</h3><p>エージェント、世界ルール、ベンチマーク、シナリオを小さく試す。</p><span class="id">simulated</span></article>
          <article class="world liminal"><small>3 / 境界</small><h3>意味をつなぐ場所</h3><p>現実と仮想の差分、違和感、保留、判断待ちを置く。</p><span class="id">liminal</span></article>
        </div>
      </section>

      <section id="roadmap">
        <h2>ロードマップ</h2>
        <div class="timeline">
{phase_cards}
        </div>
      </section>

      <section id="gates">
        <h2>保証すること</h2>
        <div class="proof-grid">
          <article class="gate"><strong>世界観がない追加は入れない</strong><p>人物や役割だけではなく、最低限の世界要素を確認してから採用する。</p></article>
          <article class="gate"><strong>公開名は抽象化する</strong><p>作品名、キャラクター名、決め台詞、私的パス、外部投稿本文は実装IDにしない。</p></article>
          <article class="gate"><strong>外部書き込みは人間が止める</strong><p>GitHub issue、Linear、クラウド、外部チャット、公開PRは、人間レビュー前に自動実行しない。</p></article>
          <article class="gate"><strong>残った論点も行き先を持つ</strong><p>採用、保留、監視、対象外のどれかに分類し、採用なら必ずTODO IDを持たせる。</p></article>
        </div>
      </section>

      <section>
        <h2>Minimum World Packet</h2>
        <div class="packet-grid">
{packet_cards}
        </div>
      </section>

      <section>
        <h2>やらないこと</h2>
        <ul class="plain-list">
{non_goal_items}
        </ul>
      </section>

      <section id="docs">
        <h2>正本と関連ドキュメント</h2>
        <div class="docs-row">
          <a class="doc-link" href="cross-world-operator-roadmap.md">ロードマップ正本<span>このHTMLの生成元。</span></a>
          <a class="doc-link" href="cross-world-operator-todo.html">未実装TODO<span>残っている作業と保証マトリクス。</span></a>
          <a class="doc-link" href="cross-world-operator-linear-drafts.md">Linear起票案<span>MVP単位に分けた内部管理用ドラフト。</span></a>
          <a class="doc-link" href="subagents/work-orders/wo-urban-018-cross-world-operator-roadmap.yaml">Work order<span>書き込み範囲、ゲート、受け入れ条件。</span></a>
        </div>
      </section>
    </main>

    <footer>
      <p>Generated from docs/cross-world-operator-roadmap.md / Status: draft / Owner: manager / Urban Ecosystem data contract は変更しない。</p>
    </footer>
  </div>
</body>
</html>
"""


def write_html(project_root: Path = PROJECT_ROOT) -> None:
    target = project_root / "docs" / "cross-world-operator-roadmap.html"
    target.write_text(generate_html(project_root), encoding="utf-8")


def check_html(project_root: Path = PROJECT_ROOT) -> bool:
    target = project_root / "docs" / "cross-world-operator-roadmap.html"
    current = _read(target)
    expected = generate_html(project_root)
    if current == expected:
        return True
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(target),
        tofile=f"{target} (generated)",
    )
    sys.stderr.writelines(diff)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="render Cross-world roadmap HTML")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    if args.write:
        write_html()
        return 0
    return 0 if check_html() else 1


if __name__ == "__main__":
    raise SystemExit(main())
