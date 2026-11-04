# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""A square's logo, uploaded as the request body and kept in the platform's public bucket (rootsquares W6-R53)."""

from flask import Flask

from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _square(api: Flask, who: str = "lg"):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    made = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": f"first-{who}", "theme_id": "paper-brick"}, headers=h).json
    return c, h, made["id"]


def _upload(c, h, sid, data=PNG, kind="image/png"):
    return c.post(f"{PREFIX}/squares/{sid}/logo", data=data, headers={**h, "Content-Type": kind})


def test_upload_replace_and_remove(api: Flask) -> None:
    c, h, sid = _square(api)
    assert c.get(f"{PREFIX}/squares/{sid}", headers=h).json["logo_url"] is None
    first = _upload(c, h, sid)
    assert first.status_code == 200 and "square-logos/" in first.json["logo_url"] and first.json["logo_url"].endswith(".png")
    storage = api.extensions["providers"].storage
    assert len(storage.objects) == 1
    second = _upload(c, h, sid)
    assert second.json["logo_url"] != first.json["logo_url"] and len(storage.objects) == 1  # the old file is gone
    assert c.get(f"{PREFIX}/squares", headers=h).json["items"][0]["logo_url"] == second.json["logo_url"]
    removed = c.delete(f"{PREFIX}/squares/{sid}/logo", headers=h)
    assert removed.status_code == 200 and removed.json["logo_url"] is None and not storage.objects


def test_refuses_wrong_files(api: Flask) -> None:
    c, h, sid = _square(api)
    assert _upload(c, h, sid, b"<svg onload=alert(1)/>", "image/svg+xml").status_code == 422
    assert _upload(c, h, sid, b"not a png at all", "image/png").status_code == 422  # magic bytes do not match
    assert _upload(c, h, sid, b"", "image/png").status_code == 422
    assert _upload(c, h, sid, PNG + b"0" * 1_000_000, "image/png").status_code == 422
    assert _upload(c, h, sid, b"RIFF0000WAVE", "image/webp").status_code == 422
    assert _upload(c, h, sid, b"RIFF0000WEBP", "image/webp").status_code == 200
    assert not [k for k in api.extensions["providers"].storage.objects if k.endswith(".svg")]


def test_only_the_squares_organisation_may_change_it(api: Flask) -> None:
    c, h, sid = _square(api, "own")
    other = {**HEADERS, "Authorization": "Bearer fake:u-x:x@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other"}, headers=other).status_code == 201
    assert _upload(c, other, sid).status_code == 404
    assert c.delete(f"{PREFIX}/squares/{sid}/logo", headers=other).status_code == 404


def test_a_second_logo_for_dark_backgrounds(api: Flask) -> None:
    """W6-R65: the light and the dark logo are kept apart; each can be replaced or removed on its own."""
    c, h, sid = _square(api, "dk")
    light = _upload(c, h, sid)
    dark = c.post(f"{PREFIX}/squares/{sid}/logo?variant=dark", data=PNG, headers={**h, "Content-Type": "image/png"})
    assert dark.status_code == 200 and dark.json["logo_url"] == light.json["logo_url"] and "/dark-" in dark.json["logo_dark_url"]
    assert len(api.extensions["providers"].storage.objects) == 2
    assert c.get(f"{PREFIX}/squares", headers=h).json["items"][0]["logo_dark_url"] == dark.json["logo_dark_url"]
    gone = c.delete(f"{PREFIX}/squares/{sid}/logo?variant=dark", headers=h)
    assert gone.json["logo_dark_url"] is None and gone.json["logo_url"] == light.json["logo_url"]
    assert len(api.extensions["providers"].storage.objects) == 1
    bad = c.post(f"{PREFIX}/squares/{sid}/logo?variant=blue", data=PNG, headers={**h, "Content-Type": "image/png"})
    assert bad.status_code == 422
