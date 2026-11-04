"""The list of squares carries each square's organisation name (W26-R27), so the dashboard can group the squares of several organisations under their names.
No network."""

from flask import Flask

from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _login(api: Flask, who: str):  # noqa: F811
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    return c, h


def test_each_square_carries_the_name_of_its_organisation(api: Flask) -> None:  # noqa: F811
    c, h = _login(api, "orgname")
    r = c.post(f"{PREFIX}/squares", json={"name": "Club squares", "slug": "org-name-one", "theme_id": "paper-brick", "launch_package": "grove"}, headers=h)
    assert r.status_code in (201, 202)
    assert r.json["org_name"] == "Club orgname"
    listed = c.get(f"{PREFIX}/squares", headers=h).json["items"]
    assert [(s["slug"], s["org_name"], s["org_id"] == r.json["org_id"]) for s in listed] == [("org-name-one", "Club orgname", True)]
