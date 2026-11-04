r"""What it is:   The theme builder.
What it does: Reads design/tenant-themes-v7/themes.json and writes every generated theme file of the platform, the backend and the square app. Never edit the generated files.
How to run:   From the repository root: python square/frontend/scripts/build_layout_themes.py; then restart the platform backend.
Read before:  docs/setup/21-layout-themes.md.
Read after:   npm run test:themes in frontend/; docs/setup/21-layout-themes.md.

Builds every file of the 56 themes (rootsquares W9-R10).

Reads  design/tenant-themes-v7/themes.json  (the 56 themes of RootSquares-Themes_v7: palettes in light and dark, fonts, shell, layout-kit mix, corner scales;
the 16 reference themes also carry `rth`, the structure of their layout) and writes
  frontend/platform/src/styles/themes.css                                the platform's --t-* theme file (all 56, light and dark)
  frontend/platform/src/themes/colors.ts                                  swatches for the theme pickers
  frontend/ui/src/themes/index.ts                                 the theme list of the platform (names, tags, shells, structure flags)
  square/frontend/src/styles/square-layout-themes.css            the --t-* and --lt-* blocks of the square app
  square/frontend/src/themes/layoutThemeFonts.ts                 the Google Fonts address of every theme
  square/frontend/src/layout-themes/layouts.generated.ts         structure of the reference layouts, and shell + kits of the engine themes
  backend/app/shared/config.py, backend/.env.example             the list of theme ids the platform offers
The default theme, paper-brick, is the original bca-oslo look: the square app gives it no layout.

Colours: the palettes are the design's (already corrected by it); text pairs that still fail WCAG AA 4.5:1 are moved to the nearest passing shade and
every correction is printed. Run from the repository root:  python square/frontend/scripts/build_layout_themes.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "design" / "tenant-themes-v7" / "themes.json"
OUT_PLATFORM_CSS = ROOT / "frontend" / "platform" / "src" / "styles" / "themes.css"
OUT_COLORS = ROOT / "frontend" / "platform" / "src" / "themes" / "colors.ts"
OUT_CATALOGUE = ROOT / "frontend" / "ui" / "src" / "themes" / "index.ts"
OUT_SQUARE_CSS = ROOT / "square" / "frontend" / "src" / "styles" / "square-layout-themes.css"
OUT_FONTS = ROOT / "square" / "frontend" / "src" / "themes" / "layoutThemeFonts.ts"
OUT_LAYOUTS = ROOT / "square" / "frontend" / "src" / "layout-themes" / "layouts.generated.ts"
OUT_EMAIL = ROOT / "square" / "backend" / "app" / "email" / "theme_palette.py"
# The colours of a square's e-mails (W13-R29), per theme id, from the light tokens of the theme. paper-brick keeps exactly the colours its e-mails had before the
# themes reached them (a thumb rule: the original look never changes).
EMAIL_PALETTE: dict[str, dict[str, str]] = {}
PAPER_BRICK_EMAIL = {"accent": "#A8422A", "on_accent": "#FDF8F1", "heading": "#4A3627", "body": "#6E5540", "muted": "#8A7359", "panel": "#F9F2E8",
                     "card": "#FDF8F1", "sunk": "#F4EADC", "border": "#E0D0BA"}
CONFIG_PY = ROOT / "backend" / "app" / "shared" / "config.py"
ENV_EXAMPLE = ROOT / "backend" / ".env.example"
DEFAULT_THEME = "paper-brick"
# The structures offered besides the default: three in each of the six families (W18-R25, docs/plans/themes-composer-plan.md). The other themes stay in the code,
# stay valid for a square already on one (LEGACY_THEMES) and are not offered; set to None to offer all.
LAUNCH_THEMES = ["sage-round", "linen-arch", "hush-pond", "ledger-gazette", "japandi-atelier", "terracotta-hall", "softform", "product", "clay-pastel", "pearl",
                 "mela-noir", "kash-meadow", "denim-linen", "product-console", "lotus-hour", "canopy-grove", "marquee-showbill"]

SERIF = {"Lora", "Cormorant Garamond", "Newsreader", "Playfair Display", "DM Serif Display", "Libre Baskerville", "Young Serif", "EB Garamond",
         "Gilda Display", "Instrument Serif", "Marcellus", "Fraunces", "Source Serif 4", "Crimson Pro", "Spectral", "Bitter", "Merriweather"}
SHELL_LABEL = {"bar": "Top bar", "side": "Left sidebar", "right": "Right sidebar", "mast": "Top masthead", "tabs": "Two-row tabs", "dock": "Bottom dock", "ref": "Reference layout"}
KIT_LABEL = {"K1": "cards", "K2": "rows", "K3": "ledger", "K4": "timeline", "K5": "bento"}
# platform structure flags (the tenant mock site of the platform reads these): header, hero, events
HEADER_OF_SHELL = {"bar": "left", "side": "sidebar", "right": "sidebar", "mast": "centered", "tabs": "two-row", "dock": "two-row"}
STATUS = {
    "light": {"success": "#1F5233", "success-bg": "#E1EFE6", "warning": "#5C3A00", "warning-bg": "#FBEBC8", "danger": "#8A1F14", "danger-bg": "#FBE3DF", "info": "#1E4A7A", "info-bg": "#E0ECF8"},
    "dark": {"success": "#A9DDB9", "success-bg": "#17301F", "warning": "#F2D08A", "warning-bg": "#35290C", "danger": "#F3B2A8", "danger-bg": "#3B1A15", "info": "#B5D3F0", "info-bg": "#152B40"},
}

KNOB_PREFIXES = ("--t-input-", "--t-btn-case", "--t-btn-tracking", "--t-badge-", "--t-tab-", "--t-nav-radius", "--t-card-pad")
notes: list[str] = []


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexc(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def lum(h: str) -> float:
    def ch(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(v) for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def mix(a: str, b: str, t: float) -> str:
    """t = share of b."""
    ra, rb = rgb(a), rgb(b)
    return hexc(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))  # type: ignore[arg-type]


def fix(label: str, c: str, grounds: list[str], need: float, toward: str) -> str:
    """The nearest shade of c (moving toward `toward`) that reaches `need` on every ground."""
    x, t = c, 0.0
    while not all(ratio(x, g) >= need for g in grounds) and t < 1:
        t += 0.02
        x = mix(c, toward, t)
    if x != c:
        notes.append(f"  {label}: {c} -> {x}")
    return x


def rgba(h: str, a: float) -> str:
    r, g, b = rgb(h)
    return f"rgba({r},{g},{b},{a})"


def neu(o: int, c: dict, dark: bool, inset: bool = False) -> str:
    """The soft pressed shadow of the neumorphic themes: a dark shadow low right, a light one high left."""
    d = rgba("#000000" if dark else c["ink"], 0.55 if dark else 0.17)
    lt = "rgba(255,255,255,.05)" if dark else "rgba(255,255,255,.9)"
    h = round(o / 2)
    if inset:
        return f"inset {h}px {h}px {o}px {d}, inset -{h}px -{h}px {o}px {lt}"
    return f"{o}px {o}px {round(o * 2.2)}px {d}, -{o}px -{o}px {round(o * 2.2)}px {lt}"


def stack(name: str) -> str:
    return f'"{name}",' + ("Georgia,serif" if name in SERIF else '"Helvetica Neue",Arial,sans-serif')


def palette(t: dict, mode: str) -> dict:
    """The unified palette of the design plus, for reference themes, the extras of their layout (second accent, panel, tiles, swatches)."""
    c = dict(t["l" if mode == "light" else "d"])
    if t.get("rth"):
        src = t["rth"]["light" if mode == "light" else "dark"]
        c.update({k: v for k, v in src.items() if k in ("acc2", "p", "pi", "pa", "ao", "t", "sw", "panel")})
    return c


def structure(t: dict) -> dict[str, str]:
    """The structure flags the platform's tenant mock site reads: header, hero, events, image shape, hero flip."""
    ev = "grid"
    if t.get("mix") and t["mix"][0] in ("K2", "K3"):
        ev = "list"
    rth = t.get("rth")
    if rth:
        ev = "list" if rth["ev"] in ("list", "table", "giant", "datarows", "agenda") else "grid"
    img = "square" if float(t["RS"]) < 0.5 else "round"
    return {"--t-header": HEADER_OF_SHELL.get(t["shell"], "left"), "--t-hero": "split", "--t-events": ev, "--t-image-shape": img, "--t-hero-flip": "0"}


def tokens(t: dict, mode: str) -> dict[str, str]:
    c = palette(t, mode)
    dark = mode == "dark"
    rth = t.get("rth") or {}
    bg, card, sunk, ink, body, mute, line = c["bg"], c["card"], c["sunk"], c["ink"], c["body"], c["mute"], c["line"]
    black_white = "#ffffff" if dark else "#000000"
    grounds = [bg, card, sunk, c["hl"]]  # hl: the highlighted bands (hero, quote, tiles); W10-R6 found text below AA on them
    tag = f"{t['id']} {mode}"
    strong = fix(f"{tag} text-strong", ink, grounds, 7, black_white)
    text = fix(f"{tag} text", body, grounds, 4.5, ink)
    muted = fix(f"{tag} text-muted", mute, grounds, 4.5, ink)
    link = fix(f"{tag} link", c["acc"], grounds, 4.5, ink)
    g = c.get("acc2", c["g"])
    accent_text = fix(f"{tag} accent-text", c["g"], grounds, 4.5, ink)
    accent = c["acc"]
    on_primary = max([c["on"], "#ffffff", "#111111"], key=lambda o: ratio(o, accent))
    if ratio(on_primary, accent) < 4.5:
        toward = "#000000" if lum(on_primary) > 0.5 else "#ffffff"
        x, tt = accent, 0.0
        while ratio(on_primary, x) < 4.5 and tt < 1:
            tt += 0.02
            x = mix(c["acc"], toward, tt)
        notes.append(f"  {tag} accent fill: {accent} -> {x}")
        accent = x
    on_accent = max(["#ffffff", "#111111"], key=lambda o: ratio(o, g))
    hover = mix(accent, "#ffffff" if dark else "#000000", 0.10 if dark else 0.12)
    press = mix(accent, "#ffffff" if dark else "#000000", 0.20 if dark else 0.24)
    border_default = mix(line, mute, 0.4)
    border_strong = fix(f"{tag} border-strong", mix(line, mute, 0.8), [bg, card], 3, strong)
    inverse, on_inverse = c["inv"], c["iv"]
    RS = float(t["RS"])
    RP = int(t["RP"])

    def rc(n: int) -> int:
        return round(n * RS)

    r = int(rth["r"]) if rth else rc(20)
    br = (int(rth["br"]) if rth.get("br") is not None else (10 if r > 8 else r)) if rth else RP
    hard = rth.get("shell") == "pencil"
    if rth.get("neu"):
        sh = (neu(5, c, dark), neu(9, c, dark), neu(14, c, dark), "none")
    elif hard:
        sh = (f"2px 2px 0 {strong}", f"3px 3px 0 {strong}", f"5px 5px 0 {strong}", f"3px 3px 0 {strong}")
    elif r == 0:
        sh = ("none", "none", "none", "none")
    else:
        sh = (f"0 1px 3px {rgba(strong, .16)}", f"0 8px 20px -8px {rgba(strong, .16)}", f"0 24px 48px -16px {rgba(strong, .16)}", "none")
    dw = int(rth["dw"]) if rth else 700
    out: dict[str, str] = {
        "--t-bg": bg, "--t-surface": card, "--t-surface-sunken": sunk, "--t-inverse": inverse,
        "--t-accent-soft": mix(card, g, 0.28), "--t-primary-soft": c["hl"],
        "--t-text-strong": strong, "--t-text": text, "--t-text-muted": muted, "--t-on-inverse": on_inverse,
        "--t-on-primary": on_primary, "--t-link": link, "--t-accent-text": accent_text, "--t-on-accent": on_accent,
        "--t-border": line, "--t-border-default": border_default, "--t-border-strong": border_strong,
        "--t-accent": accent, "--t-accent-hover": hover, "--t-accent-press": press, "--t-accent-2": g,
        "--t-focus": link, "--t-btn-border": accent,
    }
    out.update({f"--t-{k}": v for k, v in STATUS[mode].items()})
    out.update({
        "--t-radius-sm": f"{min(rc(10), 12)}px", "--t-radius": f"{r}px", "--t-radius-lg": f"{min(round(r * 1.5), 40)}px", "--t-radius-btn": f"{br}px",
        "--t-radius-img": f"{r}px", "--t-density": "1", "--t-control-h": "44px", "--t-border-w": "1.5px" if hard else "1px",
        "--t-font-display": stack(t["display"]), "--t-font-body": stack(t["body"]),
        "--t-font-display-weight": str(dw), "--t-font-display-tracking": "-0.03em" if dw >= 700 else "-0.015em",
        "--t-eyebrow-case": "uppercase", "--t-eyebrow-tracking": ".12em" if rth.get("caps") else ".2em",
        "--t-shadow-sm": sh[0], "--t-shadow-md": sh[1], "--t-shadow-lg": sh[2], "--t-shadow-btn": sh[3],
    })
    out.update(structure(t))
    # Component knobs (W10-R6): the shapes and type of the controls of the member, admin and check-in side, derived from the theme's own corner scale,
    # button style and display face; read by src/styles/theme-components.css for every theme.
    serif = t["display"] in SERIF
    caps = bool(rth.get("caps"))
    out.update({
        "--t-input-radius": f"{min(12, round(r * 0.67)) if r > 0 else 0}px", "--t-input-h": "48px", "--t-input-bw": "1.5px" if hard else "1.5px",
        "--t-btn-case": "uppercase" if caps else "none", "--t-btn-tracking": ".08em" if caps else ".01em",
        "--t-badge-case": "uppercase" if caps else "none", "--t-badge-tracking": ".06em" if caps else "0", "--t-badge-weight": "700",
        "--t-tab-family": stack(t["display"]) if serif else stack(t["body"]), "--t-tab-style": "italic" if serif else "normal",
        "--t-tab-weight": "400" if serif else "600", "--t-tab-size": "20px" if serif else "14px",
        "--t-tab-case": "none" if serif else "uppercase", "--t-tab-tracking": "0" if serif else ".08em",
        "--t-nav-radius": "999px" if br > 20 else f"{min(br, 10)}px", "--t-card-pad": "24px",
    })
    return out


def extras(t: dict, mode: str, tk: dict[str, str]) -> dict[str, str]:
    """The --lt-* variables of the square app: panel colours, tiles, swatches, soft-shadow parts."""
    c = palette(t, mode)
    dark = mode == "dark"
    tag = f"{t['id']} {mode}"
    sunk, ink = c["sunk"], c["ink"]
    out: dict[str, str] = {"--lt-hand": '"Caveat",cursive', "--lt-mono": '"JetBrains Mono",ui-monospace,monospace'}
    out["--lt-panel"] = c.get("panel", c.get("p", tk["--t-inverse"]))
    pan = c.get("p", sunk)
    uses = "p" in c
    pi = c.get("pi", ink) if not uses else fix(f"{tag} panel text", c.get("pi", ink), [pan], 4.5, "#ffffff" if lum(pan) < 0.4 else "#000000")
    pa = c.get("pa", c["acc"]) if not uses else fix(f"{tag} panel accent", c.get("pa", c["acc"]), [pan], 4.5, "#ffffff" if lum(pan) < 0.4 else "#000000")
    ao = c.get("ao", c["on"])
    if uses and ratio(ao, pa) < 4.5:
        ao = max(["#ffffff", "#111111"], key=lambda o: ratio(o, pa))
        notes.append(f"  {tag} text on panel accent: {c.get('ao', c['on'])} -> {ao}")
    out["--lt-p"], out["--lt-pi"], out["--lt-pa"], out["--lt-ao"] = pan, pi, pa, ao
    for i, (tb, tf) in enumerate(c.get("t", [])):
        out[f"--lt-t{i}-bg"] = tb
        out[f"--lt-t{i}-fg"] = fix(f"{tag} tile {i}", tf, [tb], 4.5, "#ffffff" if lum(tb) < 0.4 else "#000000")
    for i, sw in enumerate(c.get("sw", [])):
        out[f"--lt-sw{i}"] = sw
        out[f"--lt-sw{i}-fg"] = "#2A2622" if lum(sw) > 0.3 else "#F8F4EC"
    if t["kind"] == "engine":  # the engine themes: the inverse colours are the panel colours (footer, quote bands, dock)
        ivm = fix(f"{tag} muted on inverse", c["ivm"], [c["inv"]], 4.5, c["iv"])
        out["--lt-p"], out["--lt-pi"], out["--lt-pa"], out["--lt-ao"], out["--lt-ivm"] = c["inv"], c["iv"], ivm, c["inv"], ivm
    rth = t.get("rth") or {}
    if rth.get("neu"):
        out["--lt-nd"] = f"{rth.get('nd', 8)}px"
        out["--lt-nsh"] = rgba("#000000" if dark else ink, 0.55 if dark else 0.17)
        out["--lt-nhl"] = "rgba(255,255,255,.05)" if dark else "rgba(255,255,255,.9)"
    return out


def bridge(t: dict, mode: str, tk: dict[str, str]) -> dict[str, str]:
    """The plain Tailwind colour tokens (--color-*, used by the Base* components, tables, inputs, drawers and toasts) in the theme's palette (W10-R6)."""
    c = palette(t, mode)
    dark = mode == "dark"
    sec = c.get("acc2", c["g"])
    sec = mix(sec, "#ffffff", 0.45) if (dark or lum(sec) < 0.3) else sec
    on_sec = max(["#111111", "#ffffff"], key=lambda o: ratio(o, sec))
    st = STATUS[mode]
    return {
        "--color-bg": tk["--t-bg"], "--color-surface": tk["--t-surface"], "--color-border": tk["--t-border"],
        "--color-primary": tk["--t-accent"], "--color-secondary": sec, "--color-accent": sec, "--color-on-secondary": on_sec,
        "--color-text": tk["--t-text-strong"], "--color-text-secondary": tk["--t-text-muted"],
        "--color-success": st["success"], "--color-success-bg": st["success-bg"], "--color-error": st["danger"], "--color-error-bg": st["danger-bg"],
        "--font-sans": tk["--t-font-body"],
    }


def block(sel: str, mode: str, tk: dict[str, str], keep: str) -> list[str]:
    lines = ["", f"{sel} {{"] + (["  color-scheme: dark;"] if mode == "dark" else [])
    lines += [f"  {k}: {v};" for k, v in tk.items() if k.startswith(keep)]
    lines.append("}")
    return lines


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))["themes"]
    ids = [t["id"] for t in spec]
    assert len(ids) == 56 and len(set(ids)) == 56 and DEFAULT_THEME in ids, ids

    platform = [
        "/*",
        " * Tenant themes: 56 themes, light and dark, on the --t-* token contract (W9-R10).",
        " * GENERATED by square/frontend/scripts/build_layout_themes.py from design/tenant-themes-v7/themes.json. Do not edit by hand.",
        " * Select with data-theme=\"<slug>\" and data-mode=\"light|dark\" on the tenant wrapper element (not on <html>: platform light/dark uses data-theme=\"dark\"",
        " * on <html>; the two are independent, see tests/themes.test.mjs). Components read only these variables and the named structure options",
        " * (--t-header, --t-hero, --t-events, --t-image-shape).",
        " */",
    ]
    square = [
        "/* GENERATED by square/frontend/scripts/build_layout_themes.py from design/tenant-themes-v7/themes.json (rootsquares W9-R10). Do not edit by hand.",
        "   One block per theme and mode: the --t-* contract and the --lt-* extras of the layouts. A square on a theme other than the default gets data-square-theme",
        "   on <html> (src/themes/applySquareTheme.ts). */",
    ]
    colors: dict[str, dict] = {}
    catalogue: list[dict] = []
    fonts: dict[str, str] = {}
    refs: dict[str, dict] = {}
    engines: dict[str, dict] = {}
    dark_default: list[str] = []
    for t in spec:
        tk_modes = {m: tokens(t, m) for m in ("light", "dark")}
        for m in ("light", "dark"):
            tk = tk_modes[m]
            ex = extras(t, m, tk)
            sel = f'[data-theme="{t["id"]}"]' if m == "light" else f'[data-theme="{t["id"]}"][data-mode="dark"]'
            platform += block(sel, m, {k: v for k, v in tk.items() if not k.startswith(KNOB_PREFIXES)}, "--t-")  # the component knobs are for the square app only
            if t["id"] != DEFAULT_THEME:
                sq = f'html[data-square-theme="{t["id"]}"] .ds-scope' if m == "light" else f'html.dark[data-square-theme="{t["id"]}"] .ds-scope,\nhtml[data-square-theme="{t["id"]}"] .ds-scope.ds-force-dark'
                square += block(sq, m, {**tk, **ex}, "--")
                hsel = f'html[data-square-theme="{t["id"]}"]' if m == "light" else f'html.dark[data-square-theme="{t["id"]}"]'
                square += block(hsel, m, bridge(t, m, tk), "--")
            c = palette(t, m)
            colors.setdefault(t["id"], {})[m] = {"bg": tk["--t-bg"], "ink": tk["--t-text-strong"], "accent": tk["--t-accent"], "g": c["g"], "inv": c["inv"], "serif": t["display"] in SERIF}
        fonts[t["id"]] = t["fonts"][0]
        if t["mode"] == "dark":
            dark_default.append(t["id"])
        st = tk_modes["light"]
        EMAIL_PALETTE[t["id"]] = dict(PAPER_BRICK_EMAIL) if t["id"] == DEFAULT_THEME else {
            "accent": st["--t-accent"], "on_accent": st["--t-on-primary"], "heading": st["--t-text-strong"], "body": st["--t-text"], "muted": st["--t-text-muted"],
            "panel": st["--t-bg"], "card": st["--t-surface"], "sunk": st["--t-surface-sunken"], "border": st["--t-border"]}
        catalogue.append({
            "id": t["id"], "name": t["name"], "n": t["n"], "kind": t["kind"], "suits": t["note"], "colour": t["colour"], "shell": t["shell"],
            "shellLabel": SHELL_LABEL[t["shell"]], "look": t["sig"] or " + ".join(dict.fromkeys(KIT_LABEL[k] for k in t["mix"])),
            "kits": [KIT_LABEL[k] for k in dict.fromkeys(t["mix"])] if t.get("mix") else [], "mode": t["mode"], "display": t["display"], "body": t["body"],
            "header": st["--t-header"], "hero": st["--t-hero"], "events": st["--t-events"], "img": st["--t-image-shape"],
            "corners": f"cards x{t['RS']}, buttons {'pill' if t['RP'] > 100 else str(t['RP']) + 'px'}",
        })
        if t["id"] == DEFAULT_THEME:
            continue
        if t.get("rth"):
            keys = ["shell", "sf", "hero", "ev", "gal", "news", "her", "mem", "con", "sh", "ft", "order", "mw", "px", "r", "br", "caps", "dw", "hb", "hbk", "nav", "nc", "neu", "nd", "emn", "emc", "ir", "fr", "alt", "altR"]
            r = t["rth"]
            refs[t["id"]] = {"name": t["name"], **{k: r[k] for k in keys if r.get(k) is not None}}
        else:
            RS = float(t["RS"])
            engines[t["id"]] = {"name": t["name"], "shell": t["shell"], "mix": t["mix"], "rs": RS, "rp": int(t["RP"]), "mode": t["mode"], "r": round(20 * RS), "dw": 700}

    OUT_PLATFORM_CSS.write_text("\n".join(platform) + "\n", encoding="utf-8")
    OUT_SQUARE_CSS.write_text("\n".join(square) + "\n", encoding="utf-8")
    OUT_FONTS.write_text("// GENERATED by square/frontend/scripts/build_layout_themes.py (rootsquares W9-R10). Do not edit by hand.\n// The Google Fonts address of every theme except the default, one per theme as its design file loads it.\nexport const LAYOUT_THEME_FONT_URLS: Record<string, string> = {\n"
                         + "\n".join(f"  '{i}': '{u}'," for i, u in fonts.items() if i != DEFAULT_THEME) + "\n}\n", encoding="utf-8")
    lay = ["// GENERATED by square/frontend/scripts/build_layout_themes.py (rootsquares W9-R10). Do not edit by hand.",
           "// Reference themes: the structure of their layout (shell, hero, one variant per section, order, widths). Engine themes: navigation shell, the layout kit",
           "// of each of six slots (K1 cards, K2 rows, K3 ledger, K4 timeline, K5 bento), corner scale and default mode.",
           "export const GENERATED_LAYOUTS = {"]
    lay += [f"  '{i}': {json.dumps(v, ensure_ascii=False)}," for i, v in refs.items()]
    lay += ["} as const", "", "export const GENERATED_ENGINES = {"]
    lay += [f"  '{i}': {json.dumps(v, ensure_ascii=False)}," for i, v in engines.items()]
    lay += ["} as const", "", "/** The themes that open dark until the visitor chooses. */", "export const DARK_BY_DEFAULT: string[] = ["]
    lay += [f"  '{i}'," for i in dark_default]
    lay.append("]")
    OUT_LAYOUTS.parent.mkdir(parents=True, exist_ok=True)
    OUT_LAYOUTS.write_text("\n".join(lay) + "\n", encoding="utf-8")

    def ent(i: str) -> str:
        c = colors[i]
        parts = []
        for m in ("light", "dark"):
            v = c[m]
            parts.append(f'    "{m}": {{ "bg": "{v["bg"]}", "ink": "{v["ink"]}", "accent": "{v["accent"]}", "g": "{v["g"]}", "inv": "{v["inv"]}", "serif": {str(v["serif"]).lower()} }}')
        return f'  "{i}": {{\n' + ",\n".join(parts) + "\n  },"

    OUT_EMAIL.write_text(
        "# GENERATED by square/frontend/scripts/build_layout_themes.py from design/tenant-themes-v7/themes.json (W13-R29). Do not edit by hand.\n"
        "# The colours of a square's e-mails per theme (light tokens, contrast-corrected like the site); paper-brick is pinned to its original e-mail colours.\n"
        "THEME_EMAIL_COLORS: dict[str, dict[str, str]] = " + json.dumps(EMAIL_PALETTE, indent=1) + "\n", encoding="utf-8")
    OUT_COLORS.write_text(
        "// GENERATED by square/frontend/scripts/build_layout_themes.py from design/tenant-themes-v7/themes.json (W9-R10). Do not edit by hand.\n"
        "// Page, heading, primary-action, second-accent and inverse colours per theme and mode, for the swatches of the theme pickers.\n"
        "export interface ThemeColors { bg: string; ink: string; accent: string; g: string; inv: string; serif: boolean }\n"
        "export const THEME_COLORS: Record<string, { light: ThemeColors; dark: ThemeColors }> = {\n" + "\n".join(ent(i) for i in ids) + "\n}\n", encoding="utf-8")
    for e in catalogue:
        e["flip"] = False
    unknown = [x for x in (LAUNCH_THEMES or []) if x not in ids]
    if unknown:
        raise SystemExit(f"LAUNCH_THEMES has unknown ids: {unknown}")
    enabled = list(ids) if LAUNCH_THEMES is None else [i for i in ids if i == DEFAULT_THEME or i in LAUNCH_THEMES]
    head = (
        "// GENERATED by square/frontend/scripts/build_layout_themes.py from design/tenant-themes-v7/themes.json (W9-R10). Do not edit by hand.\n"
        "// The 56 themes of the platform: names, tags and the structure flags of src/styles/themes.css (a test keeps them equal). The ids are also the backend's\n"
        "// ENABLED_THEME_IDS and the square app's theme ids. paper-brick is the original bca-oslo look; the others have their own layout in the square app.\n"
        "export type ThemeMode = 'light' | 'dark'\n"
        "export type HeaderLayout = 'left' | 'centered' | 'sidebar' | 'two-row'\n"
        "export type HeroLayout = 'split' | 'full' | 'text-first'\n"
        "export type ImageShape = 'arch' | 'round' | 'square'\n\n"
        "export interface ThemeDef {\n"
        "  id: string\n  name: string\n  /** Number in the design's theme list. */\n  n: number\n"
        "  /** ref = one of the 16 custom layouts; engine = one of the 40 built from a shell and layout kits. */\n  kind: 'engine' | 'ref'\n"
        "  /** Who it suits, in a sentence. */\n  suits: string\n  /** Colours, in words. */\n  colour: string\n  shell: string\n  shellLabel: string\n"
        "  /** How the site is laid out, in a few words. */\n  look: string\n  kits: string[]\n"
        "  /** The mode the theme opens in. */\n  mode: ThemeMode\n  display: string\n  body: string\n  header: HeaderLayout\n  hero: HeroLayout\n  flip: boolean\n"
        "  events: 'grid' | 'list'\n  img: ImageShape\n  corners: string\n}\n\n"
    )
    tail = (
        "\n\n/** The structures the product offers (paper-brick and 17 more, three in each family). Keep equal to backend ENABLED_THEME_IDS (a test checks it). */\n"
        f"export const ENABLED_THEME_IDS: string[] = {json.dumps(enabled)}\n"
        "export const THEMES: ThemeDef[] = ALL_THEMES.filter((t) => ENABLED_THEME_IDS.includes(t.id))\n"
        "/** Built and kept in the code, still valid for a square already on one; not offered to anyone new and not shown in the pickers. */\n"
        "export const LEGACY_THEMES: ThemeDef[] = ALL_THEMES.filter((t) => !ENABLED_THEME_IDS.includes(t.id))\n"
        "/** Themes shown as coming up: none planned (the pickers hide the section when this is empty). */\n"
        "export const COMING_THEMES: ThemeDef[] = []\n\n"
        "export const DEFAULT_TENANT_THEME = 'paper-brick'\n\n"
        "// Lookups by id cover every theme, so a square on a retired one still shows its name.\n"
        "export const getTheme = (id: string): ThemeDef | undefined => ALL_THEMES.find((t) => t.id === id)\n"
        "export const isThemeId = (id: unknown): id is string => typeof id === 'string' && ALL_THEMES.some((t) => t.id === id)\n"
    )
    OUT_CATALOGUE.write_text(head + "export const ALL_THEMES: ThemeDef[] = " + json.dumps(catalogue, ensure_ascii=False, indent=1) + " as ThemeDef[]" + tail, encoding="utf-8")

    ids_csv = ",".join(enabled)
    cfg =CONFIG_PY.read_text(encoding="utf-8")
    cfg = re.sub(r'ENABLED_THEME_IDS: str = "[^"]*"', f'ENABLED_THEME_IDS: str = "{ids_csv}"', cfg, count=1)
    cfg = re.sub(r"\(all (?:twenty since W9-R9|56 since W9-R10)\)", "(paper-brick and the launch set since W10-R8)", cfg)
    CONFIG_PY.write_text(cfg, encoding="utf-8")
    env = ENV_EXAMPLE.read_text(encoding="utf-8")
    ENV_EXAMPLE.write_text(re.sub(r"# ENABLED_THEME_IDS=[^\n]*", "# ENABLED_THEME_IDS=" + ids_csv, env, count=1), encoding="utf-8")
    print(f"{len(ids)} themes written; {len(refs)} reference layouts, {len(engines)} engine themes")
    print("Corrections to reach WCAG AA:" if notes else "No corrections needed.")
    print("\n".join(notes))


if __name__ == "__main__":
    main()
