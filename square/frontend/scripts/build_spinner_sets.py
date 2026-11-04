r"""What it is:   The spinner-set builder.
What it does: Reads design/spinner-sets/Spinner Sets.dc.html (the spinners of the design project "Spinner Sets", six occasions of nine) and writes the generated files of the square app. Never edit the generated files by hand.
How to run:   From the repository root: python square/frontend/scripts/build_spinner_sets.py
Read before:  design/spinner-sets/Spinner Sets.dc.html; docs/plans/themes-shapes-plan.md (the spinner step).
Read after:   npx vitest run src/themes/spinnerArt.spec.ts in square/frontend.

Writes
  square/frontend/src/themes/spinnerArt.ts     the 54 spinners: id, name, occasion, one sentence, and the SVG (colours as var(--c1..c3, --ink, --bg), size var(--sz))
  square/frontend/src/styles/spinner-sets.css  the keyframes the SVGs use (sp-*)
  frontend/platform/src/themes/spinnerSets.ts           the same list for the platform's Theme page (plus the five built-in motifs by name), where the owner chooses which to keep
  frontend/platform/src/styles/spinner-sets.css         the same keyframes
  backend/app/platform/spinner_ids.py          the 54 ids the platform accepts in a square's kept spinners
Colours and size are given by the component that draws the SVG (BaseSpinner.vue), from the square's theme tokens; the design's own demo colours are not copied.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "design" / "spinner-sets" / "Spinner Sets.dc.html"
OUT_TS = ROOT / "square" / "frontend" / "src" / "themes" / "spinnerArt.ts"
OUT_CSS = ROOT / "square" / "frontend" / "src" / "styles" / "spinner-sets.css"
OUT_PLATFORM_TS = ROOT / "frontend" / "platform" / "src" / "themes" / "spinnerSets.ts"
OUT_PLATFORM_CSS = ROOT / "frontend" / "platform" / "src" / "styles" / "spinner-sets.css"
OUT_BACKEND = ROOT / "backend" / "app" / "platform" / "spinner_ids.py"
CARD = '<div style="background:var(--bg);border:1px solid var(--line);border-radius:14px;overflow:hidden">'
ALLOWED_VARS = {"--bg", "--c1", "--c2", "--c3", "--ink", "--sz", "--track"}


def parse(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for sec in re.split(r"<section style=", text)[1:]:
        head = re.search(r"<h2[^>]*>([^<]+)</h2><span[^>]*>([^<]+)</span>", sec)
        if head is None:
            raise SystemExit("a section has no heading")
        occasion, blurb = html.unescape(head.group(1)), html.unescape(head.group(2))
        for card in sec.split(CARD)[1:]:
            art = re.search(r'<div style="height:170px;display:grid;place-items:center">(.*?)</div><div style="padding:14px 18px 18px', card, re.S)
            name = re.search(r"<b [^>]*>([^<]+)</b>", card)
            code = re.search(r"<code[^>]*>([^<]+)</code>", card)
            desc = re.search(r'<span style="font-size:13px[^>]*>([^<]+)</span>', card)
            if not (art and name and code and desc):
                raise SystemExit(f"a card in {occasion} is missing its art, name, code or sentence")
            out.append({"id": code.group(1), "name": html.unescape(name.group(1)), "set": occasion, "blurb": blurb, "desc": html.unescape(desc.group(1)), "svg": art.group(1).strip()})
    return out


def _style(**kw: str) -> str:
    return ";".join(f"{k.replace('_', '-')}:{v}" for k, v in kw.items())


def _loops() -> dict[str, list[dict[str, str]]]:
    """The four lists the design's own script builds for its `sc-for` loops (mala, rangoli, equalizer, confetti), written out here so the SVG is plain."""
    cs = ["var(--c1)", "var(--c2)", "var(--c3)"]
    fill = "transform-box:fill-box;transform-origin:%s;"
    r12 = [{"t": f"rotate({i * 30} 12 12)", "s": f"animation:sp-fade 1.2s linear {i * 0.1:.2f}s infinite"} for i in range(12)]
    g9 = []
    for i in range(9):
        r, c = i // 3, i % 3
        g9.append({"x": str(6 + c * 6), "y": str(6 + r * 6), "f": "var(--c2)" if i == 4 else "var(--c1)", "s": fill % "center" + f"animation:sp-bloom 1.4s ease-in-out {(r + c) * 0.18:.2f}s infinite"})
    dur = [0.9, 1.1, 0.8, 1.2, 1]
    eq5 = [{"x": f"{2.6 + i * 4.2:.1f}", "f": "var(--c2)" if i % 2 else "var(--c1)", "s": fill % "50% 100%" + f"animation:sp-eq {dur[i]}s ease-in-out {-i * 0.23:.2f}s infinite"} for i in range(5)]
    cf8 = [{"t": f"rotate({i * 45} 12 12)", "f": cs[i % 3], "s": fill % "center" + f"animation:sp-pop 1.3s ease-out {i * 0.04:.2f}s infinite"} for i in range(8)]
    return {"r12": r12, "g9": g9, "eq5": eq5, "cf8": cf8}


def expand(svg: str, loops: dict[str, list[dict[str, str]]]) -> str:
    """Replaces each <sc-for list="{{ name }}" as="p">body</sc-for> by the body once per item, with {{ p.key }} filled in."""
    def one(m: re.Match[str]) -> str:
        items = loops.get(m.group(1))
        if items is None:
            raise SystemExit(f"a loop over {m.group(1)} has no list in this script")
        return "".join(re.sub(r"\{\{ p\.(\w+) \}\}", lambda k, it=it: it[k.group(1)], m.group(2)) for it in items)
    return re.sub(r'<sc-for list="\{\{ (\w+) \}\}"[^>]*>(.*?)</sc-for>', one, svg, flags=re.S)


def check(items: list[dict[str, str]]) -> None:
    ids = [o["id"] for o in items]
    if len(set(ids)) != len(ids):
        raise SystemExit("two spinners share an id")
    for o in items:
        svg = o["svg"]
        if not svg.startswith("<svg") or not svg.endswith("</svg>"):
            raise SystemExit(f"{o['id']} is not one SVG")
        if "{{" in svg or "sc-for" in svg:
            raise SystemExit(f"{o['id']} still has a template placeholder")
        if re.search(r"<script|\son[a-z]+\s*=|javascript:|<foreignObject|<iframe|<image|href=", svg, re.I):
            raise SystemExit(f"{o['id']} has markup that is not drawing")
        bad = set(re.findall(r"var\((--[a-z0-9-]+)", svg)) - ALLOWED_VARS
        if bad:
            raise SystemExit(f"{o['id']} uses variables the component does not set: {sorted(bad)}")



# The colours of a spinner (W18-R29). The design draws every spinner in three colours: a main colour (--c1), a lighter warm one (--c2) and a quiet cool one (--c3), plus --ink and --bg.
# A theme has one accent, so the second and third are derived from it the way the design's own are related to its terracotta: --c2 lighter and turned 40 degrees, --c3 turned 155 degrees
# and less saturated (on the design's terracotta oklch(.5 .15 35) that gives its saffron (.74 .14 75) and teal (.52 .09 190)). Where the browser has no relative colours the theme's own
# accent tokens are used. `dark` is the design's own dark tone (for the always-dark check-in scanner); `muted` is a quiet spinner in grey.
CSS_TARGETS = {
    "square": {
        "main": "--ds-action-primary", "accent": "--ds-action-accent", "quiet": "--ds-text-muted", "ink": "--ds-text-heading", "bg": "--ds-surface-card", "track": "--ds-border-default",
        "faint": "--ds-text-faint", "strong": "--ds-border-strong", "track_dark": "--ds-border-on-dark",
    },
    "platform": {
        "main": "--color-primary", "accent": "--color-brass", "quiet": "--color-text-muted", "ink": "--color-text", "bg": "--color-surface", "track": "--color-border-strong",
        "faint": "--color-text-muted", "strong": "--color-border-strong", "track_dark": "--color-border-strong",
    },
}


def colour_css(target: str) -> str:
    t = CSS_TARGETS[target]
    return (
        ".rs-spinner-art { display: inline-flex; "
        f"--c1: var({t['main']}); --c2: var({t['accent']}); --c3: var({t['quiet']}); --ink: var({t['ink']}); --bg: var({t['bg']}); --track: var({t['track']}); }}\n"
        "@supports (color: oklch(from red l c h)) {\n"
        "  .rs-spinner-art { --c2: oklch(from var(--c1) calc(l + (1 - l) * 0.48) c calc(h + 40)); --c3: oklch(from var(--c1) l calc(c * 0.6) calc(h + 155)); }\n"
        "}\n"
        ".rs-spinner-art--dark { --c1: oklch(0.9 0.03 85); --c2: oklch(0.8 0.14 75); --c3: oklch(0.76 0.09 190); --ink: #f3ebdd; --bg: #231a14; "
        f"--track: var({t['track_dark']}); }}\n"
        f".rs-spinner-art--muted {{ --c1: var({t['faint']}); --c2: var({t['strong']}); --c3: var({t['track']}); --ink: var({t['faint']}); }}\n"
    )


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    items = parse(text)
    loops = _loops()
    for o in items:
        o["svg"] = expand(o["svg"], loops)
    items = [o for o in items if o["set"] == "Festivals"] + [o for o in items if o["set"] != "Festivals"]  # the festival set first, as the picker shows it (the design lists it last)
    check(items)
    frames = re.findall(r"^@keyframes sp-[a-z0-9]+\{.*\}$", text, re.M)
    used = set(re.findall(r"animation:\s*(sp-[a-z0-9]+)", " ".join(o["svg"] for o in items)))
    have = {re.match(r"@keyframes (sp-[a-z0-9]+)", f).group(1) for f in frames}  # type: ignore[union-attr]
    if used - have:
        raise SystemExit(f"keyframes missing: {sorted(used - have)}")
    occasions = list(dict.fromkeys(o["set"] for o in items))
    head = (
        "// GENERATED by square/frontend/scripts/build_spinner_sets.py from design/spinner-sets/Spinner Sets.dc.html (W18). Do not edit by hand.\n"
        "// The spinners of the design project \"Spinner Sets\": six occasions of nine, the festival set first.\n"
        "// `svg` is drawn by BaseSpinner.vue inside .rs-spinner-art, which sets --c1 --c2 --c3 --ink --bg --track --sz from the square's theme; the keyframes are in styles/spinner-sets.css.\n"
        "export interface SpinnerArt { id: string; name: string; set: string; desc: string; svg: string }\n\n"
    )
    body = "export const SPINNER_ART: SpinnerArt[] = " + json.dumps([{k: o[k] for k in ("id", "name", "set", "desc", "svg")} for o in items], ensure_ascii=False, indent=1) + "\n\n"
    body += "/** The occasions, with the line the design gives each (the festival set first). */\nexport const SPINNER_OCCASIONS: { name: string; blurb: string }[] = " + json.dumps(
        [{"name": s, "blurb": next(o["blurb"] for o in items if o["set"] == s)} for s in occasions], ensure_ascii=False, indent=1) + "\n"
    OUT_TS.write_text(head + body, encoding="utf-8")
    css_head = (
        "/* GENERATED by square/frontend/scripts/build_spinner_sets.py from design/spinner-sets/Spinner Sets.dc.html (W18). Do not edit by hand.\n"
        "   The keyframes and the colours of the spinner SVGs of themes/%s. */\n"
    )
    keyframes = "\n".join(frames) + "\n"
    OUT_CSS.write_text(css_head % "spinnerArt.ts" + keyframes + colour_css("square"), encoding="utf-8")
    OUT_PLATFORM_CSS.write_text(css_head % "spinnerSets.ts" + keyframes + colour_css("platform"), encoding="utf-8")
    platform_head = head.replace("BaseSpinner.vue inside", "the Theme page's spinner picker inside").replace("from the square's theme", "from the platform's colours").replace(
        "styles/spinner-sets.css", "src/styles/spinner-sets.css")
    OUT_PLATFORM_TS.write_text(platform_head + body, encoding="utf-8")
    ids = [o["id"] for o in items]
    doc = (
        '"""GENERATED by square/frontend/scripts/build_spinner_sets.py (W18). Do not edit by hand.\n\n'
        'The ids of the spinners a square may keep (theme_overrides.spinners): the six occasions of the spinner sets, nine each."""\n\n'
    )
    OUT_BACKEND.write_text(doc + "from __future__ import annotations\n\nSPINNER_IDS: tuple[str, ...] = (\n" + "".join(f'    "{i}",\n' for i in ids) + ")\n", encoding="utf-8")
    print(f"{len(items)} spinners in {len(occasions)} occasions; {len(frames)} keyframes")


if __name__ == "__main__":
    sys.exit(main())
