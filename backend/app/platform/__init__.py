"""Platform API over the small rootsquares platform database. Squares are separate Neon projects (ADR 026)."""

from __future__ import annotations

from app.platform.routes import API_PREFIX, register_platform

__all__ = ["API_PREFIX", "register_platform"]
