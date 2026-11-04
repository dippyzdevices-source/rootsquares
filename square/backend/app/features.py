"""Gated features: separate screens or functions inside a module that only some launch packages include (W14-R25, docs/reference/packages-and-features.md).

A module is switched on or off by the owner (app/modules.py). A feature is one part of a module that the package decides: Square writes and sends messages,
Grove adds the automatic reminders. Nothing is hidden or deleted because of a package: the screen shows the feature locked, the server answers 403 to a change
and the background job skips it. Reading what already exists stays possible. A square made before packages existed has no package and counts as Grove.
Single-tenant mode (no square served, the test suite) has every feature.
"""

from __future__ import annotations

from flask import g, jsonify

from app.modules import module_enabled

GROVE = "grove"
EVENT_PASS = "event"
CUSTOM = "custom"  # agreed with one square (W19-R20): it has every gated feature of the modules that were agreed
DEFAULT_PACKAGE = GROVE

# key -> (module it belongs to, the packages that include it). Keep in step with docs/reference/packages-and-features.md section 6 and the browser's services/features.ts.
FEATURES: dict[str, tuple[str, tuple[str, ...]]] = {
    "message_reminders": ("messages", (GROVE, EVENT_PASS)),
    "repeating_events": ("events", (GROVE,)),
}
FEATURE_KEYS: tuple[str, ...] = tuple(FEATURES)
PACKAGE_NAMES = {"roots": "Root", "square": "Square", "grove": "Grove", "event": "Event pass", "custom": "Custom"}


def current_package() -> str | None:
    """The launch package of the square being served; None when no square is served (single-tenant mode)."""
    tenant = g.get("tenant") if g else None
    if tenant is None:
        return None
    return str(getattr(tenant, "package", "") or DEFAULT_PACKAGE)


def package_includes(key: str, package: str | None) -> bool:
    packages = FEATURES[key][1]
    return package is None or package == CUSTOM or package in packages


def feature_enabled(key: str) -> bool:
    """Is this feature available to the square being served? Its module must be on and its package must include it."""
    module = FEATURES[key][0]
    return module_enabled(module) and package_includes(key, current_package())


def features_for(package: str, modules: tuple[str, ...] | None) -> list[str]:
    """The feature keys a square has, for the browser (GET /api/square/config)."""
    return [k for k, (module, _) in FEATURES.items() if (modules is None or module in modules) and package_includes(k, package or DEFAULT_PACKAGE)]


def locked(key: str):
    """None when the feature is available; otherwise the 403 answer a change to it gets."""
    if feature_enabled(key):
        return None
    names = [PACKAGE_NAMES.get(p, p) for p in FEATURES[key][1] if p != EVENT_PASS] or ["a larger"]
    return jsonify({"error": f"Included in the {names[0]} package.", "code": "feature_not_in_package", "feature": key}), 403
