r"""What it is:   The five festival spinners (ring, alpona, lotus, chakra, dhak) as SVG, for build_spinner_sets.py.
What it does: Writes out, as one SVG each in the same form as the 45 of the design project "Spinner Sets" (viewBox 24, colours --c1 --c2, --track, size --sz), what BaseSpinner.vue drew in code
              until W18 (the design system's own motifs: ring, alpona floor art, a lotus bloom, a rath chakra wheel, a dhak drum beat), with the same shapes, timings and delays.
How to run:   Imported by square/frontend/scripts/build_spinner_sets.py; nothing to run on its own.
Read before:  git history of square/frontend/src/components/ui/BaseSpinner.vue (the hand-coded version these replace).
Read after:   square/frontend/src/themes/spinnerArt.spec.ts.
"""
from __future__ import annotations

PETAL = "M12 2.3c2.5 3.2 3.5 5.5 3.5 7.2 0 1.6-1.6 2.8-3.5 2.8s-3.5-1.2-3.5-2.8c0-1.7 1-4 3.5-7.2z"
OPEN = '<svg viewBox="0 0 24 24" style="width:var(--sz);height:var(--sz);display:block;overflow:visible{extra}">'
ORIGIN = "transform-box:fill-box;transform-origin:center;"


def _svg(body: str, extra: str = "") -> str:
    return OPEN.format(extra=extra) + body + "</svg>"


def ring() -> str:
    # a track and a quarter arc at the top turning (the old CSS border ring: track colour all round, main colour on top)
    r = 10.7
    quarter = 2 * 3.14159265 * r / 4
    return _svg(
        f'<circle cx="12" cy="12" r="{r}" fill="none" stroke="var(--track)" stroke-width="2.6"></circle>'
        f'<circle cx="12" cy="12" r="{r}" fill="none" stroke="var(--c1)" stroke-width="2.6" stroke-dasharray="{quarter:.2f} 100" transform="rotate(-135 12 12)"></circle>',
        ";animation:sp-spin .42s linear infinite",
    )


def alpona() -> str:
    petals = "".join(
        f'<g transform="rotate({i * 45} 12 12) scale(1 .92) translate(0 .9)"><path d="{PETAL}" fill="var({"--c2" if i % 2 else "--c1"})" style="animation:sp-fade 1.1s linear {i * 0.1375:.3f}s infinite"></path></g>'
        for i in range(8)
    )
    return _svg(petals + '<circle cx="12" cy="12" r="1.5" fill="var(--c1)" opacity=".9"></circle>', ";animation:sp-spin 3.2s linear infinite")


def lotus() -> str:
    petals = "".join(
        f'<g transform="rotate({22.5 + i * 45} 12 12)"><path d="{PETAL}" fill="none" stroke="var({"--c2" if i % 2 else "--c1"})" stroke-width="1.5" stroke-linejoin="round" '
        f'style="transform-origin:12px 12px;animation:sp-fbloom 1.5s ease-in-out {i * 0.11:.2f}s infinite"></path></g>'
        for i in range(8)
    )
    return _svg(petals)


def chakra() -> str:
    ticks = "".join(
        f'<line x1="12" y1="3.4" x2="12" y2="8.6" stroke="var({"--c1" if i % 3 else "--c2"})" stroke-width="1.2" stroke-linecap="round" transform="rotate({i * 30} 12 12)" opacity="{".55" if i % 3 else "1"}"></line>'
        for i in range(12)
    )
    return _svg(
        '<circle cx="12" cy="12" r="10" fill="none" stroke="var(--track)" stroke-width="1.6"></circle>'
        '<circle cx="12" cy="12" r="10" fill="none" stroke="var(--c1)" stroke-width="1.6" stroke-linecap="round" stroke-dasharray="14 49"></circle>'
        + ticks + '<circle cx="12" cy="12" r="2.4" fill="var(--c1)"></circle>',
        ";animation:sp-fsteps 1.8s steps(12) infinite",
    )


def dhak() -> str:
    w, gap = 4.8, 3.0
    x0 = (24 - (3 * w + 2 * gap)) / 2
    bars = ""
    for i in range(3):
        h = 24 * (0.72 if i == 1 else 0.5)
        bars += (
            f'<rect x="{x0 + i * (w + gap):.1f}" y="{24 - h:.2f}" width="{w}" height="{h:.2f}" rx="{w / 2}" fill="var({"--c1" if i == 1 else "--c2"})" '
            f'style="{ORIGIN}animation:sp-fbeat .58s cubic-bezier(.3,0,.4,1) {i * 0.11:.2f}s infinite alternate"></rect>'
        )
    return _svg(bars)


# id, name, one sentence (written for the app: the design project's sentences are for its own 45), svg
FESTIVAL: list[tuple[str, str, str, str]] = [
    ("ring", "Ring", "A quarter arc turning round a track. Plain and quick; for any page, any group.", ring()),
    ("alpona", "Alpona", "Floor-art petals fading in turn as the pattern turns. For Durga Puja, Poila Boishakh and festival days.", alpona()),
    ("lotus", "Lotus", "A lotus opening petal by petal. For Saraswati Puja, Lakshmi Puja and quiet waits.", lotus()),
    ("chakra", "Chakra", "A rath wheel ticking round, spoke by spoke. For Rath Yatra, processions and fairs.", chakra()),
    ("dhak", "Dhak", "Three drum beats in turn. For aarti, Puja evenings and festival ticket pages.", dhak()),
]

# Keyframes of the festival five, as the design system's own (design-system.css ds-spin-steps, ds-sp-bloom, ds-sp-beat); the others come from the design project (sp-spin, sp-fade).
KEYFRAMES = (
    "@keyframes sp-fsteps{to{transform:rotate(360deg)}}\n"
    "@keyframes sp-fbloom{0%,100%{transform:scale(.62);opacity:.22}45%{transform:scale(1);opacity:1}}\n"
    "@keyframes sp-fbeat{0%,100%{transform:translateY(0) scaleY(1)}35%{transform:translateY(-38%) scaleY(1.16)}}"
)
