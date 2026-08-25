#!/usr/bin/env python3
"""Render a run transcript as a single self-contained HTML page.

    python scripts/transcript_html.py runs/puzzles/Some_Puzzle.txt -o out.html

The text transcript is the record; this is the readable view of it. Reasoning
blocks run to tens of thousands of characters, so they collapse - the page is
meant to be skimmed on a phone, with the board, the menu and the choice
visible at a glance and the thinking available on demand.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

RULE = "=" * 72


def _clean_title(raw: str) -> str:
    """A readable name out of a puzzle filename.

    Puzzle files carry their collection and index in the name -
    `[GX_Spirit_Caller]I05_Home_of_the_Fiends` - which is useful in a
    directory listing and unreadable as a page title.
    """
    name = re.sub(r"^\[[^\]]*\]\s*", "", raw)      # collection prefix
    name = re.sub(r"^[A-Z]?\d+[_\s-]+", "", name)     # index within it
    name = name.replace("_", " ").strip()
    return name or raw


def parse(text: str) -> dict:
    out = {"title": "", "meta": [], "puzzle_text": "", "system": "", "steps": []}
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        out["title"] = _clean_title(lines[0][2:].strip())

    head, _, rest = text.partition(RULE)
    for line in head.splitlines()[1:]:
        if ":" in line and not line.startswith("##"):
            k, _, v = line.partition(":")
            if k.strip() and v.strip():
                out["meta"].append((k.strip(), v.strip()))
    if "## Puzzle text" in head:
        out["puzzle_text"] = head.split("## Puzzle text", 1)[1].strip()

    # Splitting a string that begins with the rule yields a leading empty
    # element, then label/body alternating - so pairs start at index 1.
    blocks = (RULE + rest).split(RULE)
    i = 1
    while i < len(blocks) - 1:
        label, body = blocks[i].strip(), blocks[i + 1]
        if label.startswith("SYSTEM PROMPT"):
            out["system"] = body.strip()
        elif label.startswith("DECISION"):
            m = re.match(r"DECISION (\d+)\s*\(model:\s*([^)]*)\)", label)
            step = {"n": m.group(1) if m else "?", "model": m.group(2).strip() if m else "",
                    "shown": "", "reasoning": "", "reply": "", "chose": ""}
            sent = body.split("--- model reasoning ---")[0]
            step["shown"] = sent.replace("--- sent to the model ---", "").strip()
            if "--- model reasoning ---" in body:
                step["reasoning"] = body.split("--- model reasoning ---")[1] \
                    .split("--- model replied ---")[0].strip()
            if "--- model replied ---" in body:
                tail = body.split("--- model replied ---")[1]
                step["reply"] = tail.split("--> harness took option:")[0].strip()
                if "--> harness took option:" in tail:
                    step["chose"] = tail.split("--> harness took option:")[1].strip().splitlines()[0]
            out["steps"].append(step)
        i += 2
    return out


def split_shown(shown: str) -> tuple[str, str, str]:
    """Recent events, board, and the numbered action menu."""
    events = ""
    if shown.startswith("RECENT EVENTS"):
        parts = shown.split("\n\n", 1)
        events = parts[0].replace("RECENT EVENTS", "").strip()
        shown = parts[1] if len(parts) > 1 else ""
    board, _, actions = shown.partition("ACTIONS")
    actions = actions.split("Reply with only")[0].strip()
    return events, board.strip(), actions


def esc(s: str) -> str:
    return html.escape(s or "")


def render(t: dict) -> str:
    meta = "".join(
        f'<div class="m"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>'
        for k, v in t["meta"])

    cards = []
    for s in t["steps"]:
        events, board, actions = split_shown(s["shown"])
        is_plan = s["shown"].strip() == "<planning request>"
        n = s["n"]
        head = ("The plan" if is_plan else f"Decision {n}")
        kind = "plan" if is_plan else "step"

        rows = []
        if events:
            rows.append(
                '<section class="evt"><h4>Since it last acted</h4><ul>'
                + "".join(f"<li>{esc(l.strip())}</li>"
                          for l in events.splitlines() if l.strip())
                + "</ul></section>")
        if board:
            rows.append('<section class="brd"><h4>Board it was shown</h4>'
                        f'<pre>{esc(board)}</pre></section>')
        if actions:
            items = []
            for line in actions.splitlines():
                line = line.strip()
                m = re.match(r"(\d+)\)\s*(.*)", line)
                if not m:
                    continue
                picked = (m.group(1) == s["chose"])
                items.append(
                    f'<li class="{"on" if picked else ""}">'
                    f'<span class="ix">{esc(m.group(1))}</span>'
                    f'<span class="lb">{esc(m.group(2))}</span>'
                    f'{"<span class=chose>chosen</span>" if picked else ""}</li>')
            rows.append('<section class="act"><h4>Legal actions</h4>'
                        f'<ol class="menu">{"".join(items)}</ol></section>')
        if s["reasoning"]:
            rows.append(
                '<details class="think"><summary>Its reasoning '
                f'<span class="len">{len(s["reasoning"]):,} chars</span></summary>'
                f'<div class="body">{esc(s["reasoning"])}</div></details>')

        reply = s["reply"]
        if is_plan:
            rows.append(f'<section class="verdict plan-out"><h4>Line it settled on</h4>'
                        f'<div class="body">{esc(reply)}</div></section>')
        else:
            took = s["chose"]
            rows.append(
                '<section class="verdict"><h4>What it did</h4>'
                f'<p class="said">Replied <code>{esc(reply) or "(nothing)"}</code>'
                + (f' &rarr; took option <strong>{esc(took)}</strong>'
                   if took and took != "None"
                   else ' &rarr; <em class="warn">no answer; harness fell back'
                        ' to option 0</em>')
                + "</p></section>")

        cards.append(
            f'<article class="card {kind}" id="d{esc(n)}">'
            f'<header><span class="tag">{esc(head)}</span>'
            f'<span class="model">{esc(s["model"])}</span></header>'
            + "".join(rows) + "</article>")

    return TEMPLATE.format(
        title=esc(t["title"] or "Puzzle transcript"),
        meta=meta,
        puzzle=esc(t["puzzle_text"]),
        system=esc(t["system"]),
        count=len(t["steps"]),
        cards="\n".join(cards),
    )


TEMPLATE = """<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@400;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&display=swap">
<style>
:root {{
  --paper:#f3f4f2; --raise:#ffffff; --sunk:#e9ebe7;
  --ink:#171a1f; --ink-2:#4a5058; --ink-3:#767e88;
  --line:#d6d9d3;
  --amber:#a86a14; --teal:#0f6f60; --magenta:#98305f;
  --shadow:0 1px 2px rgba(20,24,30,.06),0 6px 18px rgba(20,24,30,.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#12151a; --raise:#191d24; --sunk:#0d1014;
    --ink:#e7e9e6; --ink-2:#a8b0b8; --ink-3:#79828c;
    --line:#272c34;
    --amber:#e0a95c; --teal:#4fc3ae; --magenta:#e07fa8;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"] {{
  --paper:#12151a; --raise:#191d24; --sunk:#0d1014;
  --ink:#e7e9e6; --ink-2:#a8b0b8; --ink-3:#79828c;
  --line:#272c34;
  --amber:#e0a95c; --teal:#4fc3ae; --magenta:#e07fa8;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Serif",Georgia,serif; line-height:1.6;
  -webkit-text-size-adjust:100%;
}}
.wrap {{ max-width:47rem; margin:0 auto; padding:1.25rem 1rem 5rem; }}
h1,h2,h3,h4,.tag,.model,dt,.ix {{
  font-family:"IBM Plex Sans Condensed",system-ui,sans-serif;
}}
h1 {{ font-size:clamp(1.7rem,6vw,2.5rem); line-height:1.1; margin:.2em 0 .1em;
     letter-spacing:-.01em; text-wrap:balance; }}
.sub {{ color:var(--ink-2); font-style:italic; margin:0 0 1.4rem; }}
dl.meta {{ display:grid; grid-template-columns:1fr; gap:0; margin:0 0 1.5rem;
  border-top:1px solid var(--line); }}
.m {{ display:flex; gap:1rem; justify-content:space-between; align-items:baseline;
  padding:.5rem 0; border-bottom:1px solid var(--line); }}
dt {{ margin:0; font-size:.72rem; text-transform:uppercase; letter-spacing:.09em;
  color:var(--ink-3); white-space:nowrap; }}
dd {{ margin:0; text-align:right; font-variant-numeric:tabular-nums; }}
details {{ border:1px solid var(--line); border-radius:2px; background:var(--raise);
  margin:0 0 1rem; }}
summary {{ cursor:pointer; padding:.7rem .85rem; font-family:"IBM Plex Sans Condensed",sans-serif;
  font-weight:600; font-size:.9rem; }}
summary:focus-visible {{ outline:2px solid var(--amber); outline-offset:2px; }}
.len {{ color:var(--ink-3); font-weight:400; font-size:.8rem; }}
details .body {{ padding:0 .85rem .85rem; white-space:pre-wrap;
  font-size:.85rem; color:var(--ink-2); border-top:1px solid var(--line);
  padding-top:.75rem; max-height:26rem; overflow:auto; }}
.card {{ background:var(--raise); border:1px solid var(--line); border-radius:3px;
  box-shadow:var(--shadow); margin:0 0 1.1rem; overflow:hidden; }}
.card > header {{ display:flex; justify-content:space-between; align-items:center;
  gap:.75rem; padding:.6rem .85rem; background:var(--sunk);
  border-bottom:1px solid var(--line); }}
.tag {{ font-weight:700; letter-spacing:.02em; }}
.model {{ font-size:.72rem; color:var(--ink-3); font-family:"IBM Plex Mono",monospace; }}
.card.plan > header {{ background:color-mix(in srgb,var(--teal) 14%,var(--sunk));
  border-bottom-color:var(--teal); }}
.card section, .card details {{ margin:0; }}
.card section {{ padding:.85rem; border-bottom:1px solid var(--line); }}
.card details {{ border:0; border-bottom:1px solid var(--line); border-radius:0; }}
.card > *:last-child {{ border-bottom:0; }}
h4 {{ margin:0 0 .5rem; font-size:.7rem; text-transform:uppercase;
  letter-spacing:.1em; color:var(--ink-3); font-weight:600; }}
pre {{ margin:0; font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:.7rem;
  line-height:1.55; overflow-x:auto; background:var(--sunk); padding:.7rem;
  border-radius:2px; }}
.evt ul {{ margin:0; padding-left:1.1rem; font-size:.88rem; color:var(--ink-2); }}
ol.menu {{ list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:.2rem; }}
ol.menu li {{ display:flex; align-items:baseline; gap:.6rem; padding:.3rem .45rem;
  border-radius:2px; font-size:.9rem; }}
ol.menu li.on {{ background:color-mix(in srgb,var(--amber) 16%,transparent);
  box-shadow:inset 3px 0 0 var(--amber); }}
.ix {{ font-family:"IBM Plex Mono",monospace; font-size:.75rem; color:var(--ink-3);
  min-width:1.5rem; font-variant-numeric:tabular-nums; }}
li.on .ix {{ color:var(--amber); font-weight:600; }}
.lb {{ flex:1; }}
.chose {{ font-family:"IBM Plex Sans Condensed",sans-serif; font-size:.62rem;
  text-transform:uppercase; letter-spacing:.1em; color:var(--amber); }}
.verdict {{ background:color-mix(in srgb,var(--amber) 7%,transparent); }}
.verdict.plan-out {{ background:color-mix(in srgb,var(--teal) 8%,transparent); }}
.said {{ margin:0; }}
code {{ font-family:"IBM Plex Mono",monospace; font-size:.85em;
  background:var(--sunk); padding:.1em .4em; border-radius:2px; }}
.warn {{ color:var(--magenta); font-style:normal; font-weight:600; }}
.plan-out .body {{ white-space:pre-wrap; font-size:.9rem; }}
.note {{ font-size:.85rem; color:var(--ink-2); border-left:2px solid var(--line);
  padding-left:.85rem; margin:0 0 1.5rem; white-space:pre-wrap; }}
footer {{ margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line);
  font-size:.8rem; color:var(--ink-3); }}
</style>
<div class="wrap">
<h1>{title}</h1>
<p class="sub">Every prompt the agent received, and every choice it made.</p>
<dl class="meta">{meta}</dl>
<details><summary>The puzzle, as its author wrote it</summary>
<div class="body">{puzzle}</div></details>
<details><summary>System prompt <span class="len">sent once, cached, reused for all {count} decisions</span></summary>
<div class="body">{system}</div></details>
{cards}
<footer>Generated by scripts/transcript_html.py from the run transcript.</footer>
</div>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    t = parse(Path(a.transcript).read_text())
    Path(a.out).write_text(render(t))
    print(f"{len(t['steps'])} decisions -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
