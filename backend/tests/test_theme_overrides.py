# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""The owner's own colours and font pair on top of a square's theme (rootsquares W18-R18): validation, package gate, API, column."""

import datetime as dt
import re
from pathlib import Path

import pytest
from flask import Flask

from app.platform import theme_overrides as to
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

LOOK = {"colors": {"bg": "#F6F1E7", "ink": "#2b2a28", "acc": "#c2410c"}, "fonts": "soft"}


def _signed_in(api: Flask):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-look:look@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    return c, h


def _square(c, h, slug: str, package: str):
    return c.post(f"{PREFIX}/squares", json={"name": slug, "slug": slug, "theme_id": "pearl", "launch_package": package}, headers=h).json


def test_parse_cleans_colours_and_refuses_the_rest() -> None:
    assert to.parse(None) is None and to.parse({}) is None and to.parse({"colors": None, "fonts": None}) is None
    assert to.parse(LOOK) == {"colors": {"bg": "#f6f1e7", "ink": "#2b2a28", "acc": "#c2410c"}, "fonts": "soft"}
    assert to.parse({"colors": {"bg": "fff", "ink": "#000", "acc": "00f"}})["colors"] == {"bg": "#ffffff", "ink": "#000000", "acc": "#0000ff"}
    for bad in ("red", [], {"colors": {"bg": "#fff"}}, {"colors": {"bg": "x", "ink": "#000", "acc": "#000"}}, {"fonts": "comic"}, {"size": 3}):
        with pytest.raises(ValueError):
            to.parse(bad)


def test_the_gate_is_square_and_above_and_a_square_before_packages_counts_as_grove() -> None:
    assert [p for p in ("roots", "square", "grove", "event", None) if to.allowed(p)] == ["square", "grove", None]


def test_a_damaged_column_means_nothing_chosen() -> None:
    assert to.from_json(None) is None and to.from_json("") is None and to.from_json("{not json") is None and to.from_json('{"fonts": "comic"}') is None
    assert to.from_json(to.to_json(to.parse(LOOK))) == to.parse(LOOK)


def test_the_font_pair_ids_equal_the_square_apps_list() -> None:
    src = (Path(__file__).resolve().parents[2] / "square" / "frontend" / "src" / "themes" / "fontPairs.ts").read_text(encoding="utf-8")
    assert re.findall(r"\{ id: '([a-z]+)'", src) == list(to.FONT_PAIR_IDS)


def test_a_square_owner_sets_reads_and_clears_the_look(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-one", "square")
    assert sq["theme_overrides"] is None
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    put = c.put(url, json={"overrides": LOOK}, headers=h)
    assert put.status_code == 200 and put.json["theme_id"] == "pearl" and put.json["theme_overrides"]["colors"]["bg"] == "#f6f1e7"
    assert c.put(url, json={"theme_id": "marquee-showbill"}, headers=h).json["theme_overrides"]["fonts"] == "soft"  # a theme change keeps the owner's look
    assert c.put(url, json={"overrides": {"fonts": "bold"}}, headers=h).json["theme_overrides"] == {"fonts": "bold"}  # a new choice replaces the old one
    cleared = c.put(url, json={"overrides": None}, headers=h)
    assert cleared.status_code == 200 and cleared.json["theme_overrides"] is None and cleared.json["theme_id"] == "marquee-showbill"


def test_bad_overrides_are_refused_and_nothing_is_stored(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-two", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    assert c.put(url, json={"overrides": {"colors": {"bg": "nope", "ink": "#000", "acc": "#000"}}}, headers=h).status_code == 422
    assert c.put(url, json={"overrides": {"fonts": "comic"}}, headers=h).status_code == 422
    assert c.put(url, json={"theme_id": "nonsense"}, headers=h).status_code == 422
    assert c.put(url, json={}, headers=h).json["theme_overrides"] is None


def test_root_cannot_set_a_look_but_can_choose_a_theme_and_clear(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-root", "roots")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    denied = c.put(url, json={"overrides": LOOK}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"
    assert c.put(url, json={"theme_id": "marquee-showbill"}, headers=h).json["theme_id"] == "marquee-showbill"  # presets are for every square
    assert c.put(url, json={"overrides": None}, headers=h).status_code == 200


def test_someone_elses_square_is_not_found(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-three", "square")
    other = {**HEADERS, "Authorization": "Bearer fake:u-other2:other2@example.com"}
    assert c.put(f"{PREFIX}/squares/{sq['id']}/theme", json={"overrides": LOOK}, headers=other).status_code == 404


def test_a_square_on_a_retired_theme_keeps_it_and_can_save_a_look_but_nobody_can_choose_it(api: Flask) -> None:
    from sqlalchemy import select

    from app.platform.models import Square

    c, h = _signed_in(api)
    sq = _square(c, h, "look-retired", "square")
    db = api.extensions["db_factory"]()()
    db.scalar(select(Square).where(Square.slug == "look-retired")).theme_id = "stillwater"  # a theme offered before W18-R25
    db.commit()
    db.close()
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    assert c.put(url, json={"overrides": LOOK}, headers=h).json["theme_id"] == "stillwater"  # saving a look leaves the theme alone
    assert c.put(url, json={"theme_id": "stillwater"}, headers=h).status_code == 200  # keeping it is allowed
    assert c.put(url, json={"theme_id": "pearl"}, headers=h).status_code == 200  # moving to an offered one is allowed
    assert c.put(url, json={"theme_id": "stillwater"}, headers=h).status_code == 422  # and the way back is closed
    other = _square(c, h, "look-new", "square")
    assert c.post(f"{PREFIX}/squares", json={"name": "n", "slug": "look-new2", "theme_id": "stillwater"}, headers=h).status_code == 422
    assert other["theme_id"] == "pearl"


def test_spinners_are_a_list_of_known_ids_each_once_and_empty_means_nothing_chosen() -> None:
    assert to.parse({"spinners": ["diya", "ring", "diya"]}) == {"spinners": ["diya", "ring"]}
    assert to.parse({"spinners": []}) is None and to.parse({"spinners": None}) is None
    assert to.parse({"fonts": "soft", "spinners": ["kite"]}) == {"fonts": "soft", "spinners": ["kite"]}
    for bad in ({"spinners": "diya"}, {"spinners": ["nope"]}, {"spinners": [1]}, {"spinners": {"diya": 1}}):
        with pytest.raises(ValueError):
            to.parse(bad)


def test_the_spinner_ids_equal_the_square_apps_six_occasions_of_nine() -> None:
    root = Path(__file__).resolve().parents[2] / "square" / "frontend" / "src"
    built_in = re.findall(r"'([a-z-]+)'", re.search(r"SPINNER_VARIANTS = \[([^\]]+)\]", (root / "utils" / "spinner.ts").read_text(encoding="utf-8")).group(1))  # type: ignore[union-attr]
    art = re.findall(r'"id": "([a-z-]+)"', (root / "themes" / "spinnerArt.ts").read_text(encoding="utf-8"))
    festival = ["ring", "chakra", "dhak", "shankha", "lantern", "holi", "sparkler", "pongal-pot", "sunrise"]
    assert built_in == festival and len(art) == 54  # the festival set first, then the other five occasions
    assert art[:9] == built_in
    assert list(to.SPINNER_IDS) == art


def test_a_square_owner_keeps_spinners_and_root_cannot(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-spin", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    put = c.put(url, json={"overrides": {"spinners": ["diya", "kite"]}}, headers=h)
    assert put.status_code == 200 and put.json["theme_overrides"]["spinners"] == ["diya", "kite"]
    assert c.put(url, json={"overrides": {"spinners": ["nope"]}}, headers=h).status_code == 422
    assert c.put(url, json={"overrides": {"spinners": []}}, headers=h).json["theme_overrides"] is None
    root = _square(c, h, "look-spin-root", "roots")
    denied = c.put(f"{PREFIX}/squares/{root['id']}/theme", json={"overrides": {"spinners": ["diya"]}}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"


def test_shapes_are_known_options_per_part_and_nothing_chosen_means_nothing() -> None:
    assert to.parse({"shape": {"buttons": "pill", "photos": "arch"}}) == {"shape": {"buttons": "pill", "photos": "arch"}}
    assert to.parse({"shape": {}}) is None and to.parse({"shape": {"buttons": None}}) is None and to.parse({"shape": None}) is None
    assert to.parse({"fonts": "soft", "shape": {"edges": "line"}}) == {"fonts": "soft", "shape": {"edges": "line"}}
    for bad in (
        {"shape": "pill"},
        {"shape": {"buttons": "blob"}},
        {"shape": {"cards": "pill"}},
        {"shape": {"corners": "round"}},
        {"shape": {"buttons": ["pill"]}},
    ):
        with pytest.raises(ValueError):
            to.parse(bad)


def test_the_shape_options_equal_the_square_apps_lists() -> None:
    src = (Path(__file__).resolve().parents[2] / "square" / "frontend" / "src" / "themes" / "shapes.ts").read_text(encoding="utf-8")
    for _part, const in (("buttons", "BUTTON_SHAPE_IDS"), ("cards", "CARD_SHAPE_IDS"), ("photos", "PHOTO_SHAPE_IDS"), ("edges", "EDGE_SHAPE_IDS")):
        assert f"export const {const} = Object.keys(" in src, const  # the ids are the keys of the option tables
    table = {"buttons": "BUTTON_SHAPES", "cards": "CARD_SHAPES", "photos": "PHOTO_SHAPES", "edges": "EDGE_SHAPES"}
    for part, const in table.items():
        block = src.split(f"export const {const}", 1)[1].split("\nexport ", 1)[0].split("\n}\n", 1)[0]
        keys = re.findall(r"(?:^  |[{,] )([a-z]+): ", block, re.M)
        assert tuple(k for k in keys if k not in ("photo", "person", "border", "drop")) == to.SHAPE_OPTIONS[part], const


def test_a_square_owner_sets_shapes_and_root_cannot(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-shape", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    put = c.put(url, json={"overrides": {"shape": {"buttons": "pill", "cards": "soft"}}}, headers=h)
    assert put.status_code == 200 and put.json["theme_overrides"]["shape"] == {"buttons": "pill", "cards": "soft"}
    assert c.put(url, json={"overrides": {"shape": {"buttons": "blob"}}}, headers=h).status_code == 422
    assert c.put(url, json={"overrides": {"shape": {}}}, headers=h).json["theme_overrides"] is None
    root = _square(c, h, "look-shape-root", "roots")
    denied = c.put(f"{PREFIX}/squares/{root['id']}/theme", json={"overrides": {"shape": {"buttons": "pill"}}}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"


def test_feel_is_known_options_per_part_and_nothing_chosen_means_nothing() -> None:
    assert to.parse({"feel": {"mode": "dark", "density": "airy"}}) == {"feel": {"mode": "dark", "density": "airy"}}
    assert to.parse({"feel": {"text": "large", "divider": "line"}}) == {"feel": {"text": "large", "divider": "line"}}
    assert to.parse({"feel": {}}) is None and to.parse({"feel": {"motion": None}}) is None and to.parse({"feel": None}) is None
    assert to.parse({"shape": {"buttons": "pill"}, "feel": {"switch": "hide"}}) == {"shape": {"buttons": "pill"}, "feel": {"switch": "hide"}}
    for bad in (
        {"feel": "dark"},
        {"feel": {"mode": "blue"}},
        {"feel": {"density": "pill"}},
        {"feel": {"text": "huge"}},
        {"feel": {"divider": "dots"}},
        {"feel": {"speed": "fast"}},
        {"feel": {"mode": ["dark"]}},
    ):
        with pytest.raises(ValueError):
            to.parse(bad)


def test_the_feel_options_equal_the_square_apps_lists() -> None:
    src = (Path(__file__).resolve().parents[2] / "square" / "frontend" / "src" / "themes" / "feel.ts").read_text(encoding="utf-8")
    block = src.split("export const FEEL_OPTIONS", 1)[1].split("\n}\n", 1)[0]
    for part, ids in to.FEEL_OPTIONS.items():
        found = re.search(rf"  {part}: \[([^\]]*)\]", block)
        assert found, part
        assert tuple(re.findall(r"'([a-z]+)'", found.group(1))) == ids, part


def test_a_square_owner_sets_feel_and_root_cannot(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-feel", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    put = c.put(url, json={"overrides": {"feel": {"mode": "system", "motion": "calm"}}}, headers=h)
    assert put.status_code == 200 and put.json["theme_overrides"]["feel"] == {"mode": "system", "motion": "calm"}
    assert c.put(url, json={"overrides": {"feel": {"mode": "blue"}}}, headers=h).status_code == 422
    assert c.put(url, json={"overrides": {"feel": {}}}, headers=h).json["theme_overrides"] is None
    root = _square(c, h, "look-feel-root", "roots")
    denied = c.put(f"{PREFIX}/squares/{root['id']}/theme", json={"overrides": {"feel": {"mode": "dark"}}}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"


NOW = dt.datetime(2026, 10, 22, 9, 0, tzinfo=dt.UTC)


def test_dark_colours_are_three_hex_colours_like_the_light_ones() -> None:
    dark = {"bg": "#101820", "ink": "#E8EFE9", "acc": "#3ddc97"}
    assert to.parse({"colors": LOOK["colors"], "colors_dark": dark})["colors_dark"] == {"bg": "#101820", "ink": "#e8efe9", "acc": "#3ddc97"}
    assert to.parse({"colors_dark": None}) is None
    for bad in ({"colors_dark": {"bg": "#000"}}, {"colors_dark": {"bg": "red", "ink": "#fff", "acc": "#fff"}}, {"colors_dark": "dark"}):
        with pytest.raises(ValueError):
            to.parse(bad)


def test_the_draft_lives_beside_the_live_look_and_the_public_function_never_shows_it() -> None:
    stored = to.make_draft(to.to_json({"fonts": "soft"}), {"fonts": "bold", "feel": {"text": "large"}}, "garden", False, NOW)
    assert to.from_json(stored) == {"fonts": "soft"}  # the public and owner "live" view has no draft
    out = to.draft_out(stored, NOW)
    assert out and out["look"] == {"fonts": "bold", "feel": {"text": "large"}} and out["has_passcode"] and not out["expired"]
    assert "passcode_hash" not in out and "garden" not in str(out) and "garden" not in stored  # only a hash is stored, and never shown
    assert to.draft_out(stored, NOW + dt.timedelta(days=15))["expired"] is True  # type: ignore[index]
    assert to.draft_out(to.to_json({"fonts": "soft"}), NOW) is None


def test_saving_again_keeps_the_link_and_the_passcode_unless_asked() -> None:
    first = to.make_draft(None, {"fonts": "bold"}, "garden", False, NOW)
    link = to.draft_out(first, NOW)["token"]  # type: ignore[index]
    again = to.make_draft(first, {"fonts": "soft"}, None, False, NOW + dt.timedelta(days=3))
    assert to.draft_out(again, NOW)["token"] == link and to.draft_out(again, NOW)["has_passcode"]  # type: ignore[index]
    assert to.draft_out(to.make_draft(first, {"fonts": "soft"}, "", False, NOW), NOW)["has_passcode"] is False  # type: ignore[index]
    assert to.draft_out(to.make_draft(first, {"fonts": "soft"}, None, True, NOW), NOW)["token"] != link  # type: ignore[index]
    with pytest.raises(ValueError):
        to.make_draft(None, {}, None, False, NOW)  # nothing to share
    with pytest.raises(ValueError):
        to.make_draft(None, {"fonts": "bold"}, "abc", False, NOW)  # a passcode of 4 to 40 characters


def test_publishing_replaces_the_live_look_and_removes_the_draft() -> None:
    stored = to.make_draft(to.to_json({"fonts": "soft"}), {"fonts": "bold"}, None, False, NOW)
    assert to.from_json(to.publish_draft(stored)) == {"fonts": "bold"} and to.draft_out(to.publish_draft(stored), NOW) is None
    assert to.publish_draft(to.to_json({"fonts": "soft"})) is None
    assert to.draft_out(to.drop_draft(stored), NOW) is None and to.from_json(to.drop_draft(stored)) == {"fonts": "soft"}
    assert to.draft_out(to.with_live(stored, {"fonts": "newsroom"}), NOW) is not None  # saving the live look keeps the draft


def test_an_owner_shares_a_draft_and_publishes_it(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-draft", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    assert c.put(url, json={"overrides": {"fonts": "soft"}}, headers=h).status_code == 200
    put = c.put(f"{url}/draft", json={"look": {"fonts": "bold"}, "passcode": "garden", "theme_id": "marquee-showbill"}, headers=h)
    shared = put.json["look_draft"]
    assert put.status_code == 200 and shared["look"] == {"fonts": "bold"} and shared["has_passcode"] and shared["token"]
    assert put.json["theme_overrides"] == {"fonts": "soft"}
    kept = c.put(url, json={"overrides": {"fonts": "newsroom"}}, headers=h)  # Save look keeps the shared draft
    assert kept.json["look_draft"]["look"] == {"fonts": "bold"}
    assert c.put(f"{url}/draft", json={"look": {"fonts": "nope"}}, headers=h).status_code == 422
    assert c.put(f"{url}/draft", json={"look": {}}, headers=h).status_code == 422
    assert c.put(f"{url}/draft", json={"look": {"fonts": "bold"}, "theme_id": "no-such-theme"}, headers=h).status_code == 422
    pub = c.post(f"{url}/draft/publish", headers=h)
    assert shared["theme_id"] == "marquee-showbill"
    assert pub.status_code == 200 and pub.json["theme_overrides"] == {"fonts": "bold"} and pub.json["look_draft"] is None
    assert pub.json["theme_id"] == "marquee-showbill"
    assert c.post(f"{url}/draft/publish", headers=h).status_code == 404
    c.put(f"{url}/draft", json={"look": {"fonts": "soft"}}, headers=h)
    gone = c.delete(f"{url}/draft", headers=h)
    assert gone.status_code == 200 and gone.json["look_draft"] is None and gone.json["theme_overrides"] == {"fonts": "bold"}


def test_root_cannot_share_a_draft(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-draft-pub", "square")  # a Square-package owner can
    url = f"{PREFIX}/squares/{sq['id']}/theme/draft"
    assert c.put(url, json={"look": {"fonts": "bold"}}, headers=h).status_code == 200
    root = _square(c, h, "look-draft-root", "roots")
    denied = c.put(f"{PREFIX}/squares/{root['id']}/theme/draft", json={"look": {"fonts": "bold"}}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"


def _season(**over):
    return {"name": "Diwali", "start": "2026-10-28", "end": "2026-11-12", "yearly": False, "look": {"fonts": "bold"}, **over}


def test_seasons_are_checked_and_get_ids() -> None:
    clean = to.parse_seasons([_season(theme_id="pearl"), _season(name="Christmas", start="2026-12-20", end="2027-01-05", yearly=True)])
    assert [x["name"] for x in clean] == ["Diwali", "Christmas"] and clean[0]["theme_id"] == "pearl" and clean[0]["id"] != clean[1]["id"]
    assert to.parse_seasons(None) == [] and to.parse_seasons([]) == []
    for bad in (
        [_season(name="")], [_season(name="x" * 41)], [_season(start="28-10-2026")], [_season(start="2026-02-30")], [_season(end="2026-10-01")],
        [_season(look={})], [_season(look={"fonts": "nope"})], [_season(extra=1)], ["x"], [_season()] * 13,
    ):
        with pytest.raises(ValueError):
            to.parse_seasons(bad)
    assert to.parse_seasons([_season(end="2026-10-01", yearly=True)])  # a yearly season may cross the new year


def test_a_season_covers_its_days_and_a_yearly_one_repeats_across_the_new_year() -> None:
    d = dt.date
    once = to.parse_seasons([_season()])[0]
    assert to.season_active(once, d(2026, 10, 28)) and to.season_active(once, d(2026, 11, 12)) and not to.season_active(once, d(2026, 11, 13))
    assert not to.season_active(once, d(2027, 11, 1))
    yearly = to.parse_seasons([_season(start="2026-12-20", end="2027-01-05", yearly=True)])[0]
    assert to.season_active(yearly, d(2030, 12, 31)) and to.season_active(yearly, d(2031, 1, 5)) and not to.season_active(yearly, d(2031, 1, 6))


def test_seasons_stay_beside_the_live_look_and_the_draft() -> None:
    seasons = to.parse_seasons([_season()])
    stored = to.with_seasons(to.make_draft(to.to_json({"fonts": "soft"}), {"fonts": "bold"}, None, False, NOW), seasons)
    assert to.from_json(stored) == {"fonts": "soft"} and to.seasons_out(stored) == seasons and to.draft_out(stored, NOW) is not None
    assert to.seasons_out(to.with_live(stored, {"fonts": "newsroom"})) == seasons  # Save look keeps them
    assert to.seasons_out(to.drop_draft(stored)) == seasons and to.seasons_out(to.publish_draft(stored)) == seasons
    assert to.seasons_out(to.make_draft(stored, {"fonts": "soft"}, None, False, NOW)) == seasons
    assert to.with_seasons(None, []) is None and to.seasons_out("{not json") == []


def test_an_owner_saves_seasons_and_root_cannot(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = _square(c, h, "look-seasons", "square")
    url = f"{PREFIX}/squares/{sq['id']}/theme"
    assert sq["look_seasons"] == []
    put = c.put(f"{url}/seasons", json={"seasons": [_season(theme_id="marquee-showbill")]}, headers=h)
    assert put.status_code == 200 and put.json["look_seasons"][0]["name"] == "Diwali" and put.json["theme_overrides"] is None
    kept = c.put(url, json={"overrides": {"fonts": "soft"}}, headers=h)  # Save look keeps the seasons
    assert kept.json["look_seasons"][0]["name"] == "Diwali" and kept.json["theme_overrides"] == {"fonts": "soft"}
    assert c.put(f"{url}/seasons", json={"seasons": [_season(look={})]}, headers=h).status_code == 422
    assert c.put(f"{url}/seasons", json={"seasons": [_season(theme_id="no-such-theme")]}, headers=h).status_code == 422
    assert c.put(f"{url}/seasons", json={"seasons": []}, headers=h).json["look_seasons"] == []
    root = _square(c, h, "look-seasons-root", "roots")
    denied = c.put(f"{PREFIX}/squares/{root['id']}/theme/seasons", json={"seasons": [_season()]}, headers=h)
    assert denied.status_code == 403 and denied.json["code"] == "package_required"


def test_the_old_motion_none_is_read_as_calm() -> None:
    assert to.parse({"feel": {"motion": "none"}}) == {"feel": {"motion": "calm"}}
    assert to.parse({"feel": {"motion": "nolift"}}) == {"feel": {"motion": "nolift"}}


def test_own_fonts_are_checked_against_the_google_list_and_stored_with_their_category() -> None:
    clean = to.parse({"type": {"display": {"f": "Lora"}, "body": {"f": "Karla"}, "accent": "dancing"}})
    assert clean is not None
    assert clean["type"]["display"]["f"] == "Lora" and clean["type"]["display"]["c"] == "serif"
    assert clean["type"]["display"]["w"] == [400, 700] and clean["type"]["accent"] == "dancing"
    # the category and weights are the server's, whatever the owner sent
    forged = to.parse({"type": {"body": {"f": "Karla", "c": "monospace", "w": [100]}}})
    assert forged is not None and forged["type"]["body"]["c"] == "sans-serif" and forged["type"]["body"]["w"] == [400, 700]
    # a family with one weight loads that one
    gloock = to.parse({"type": {"display": {"f": "Gloock"}}})
    assert gloock is not None and gloock["type"]["display"]["w"] == [400]
    # a stored value read again gives the same
    assert to.parse(clean) == clean


@pytest.mark.parametrize(
    "bad",
    [
        {"type": {"display": {"f": "Not A Real Font"}}},
        {"type": {"display": {"f": "Lora; } body { display:none"}}},
        {"type": {"display": "Lora"}},
        {"type": {"accent": "comic-sans"}},
        {"type": {"title": {"f": "Lora"}}},
        {"type": "Lora"},
    ],
)
def test_own_fonts_that_are_not_offered_are_refused(bad: dict) -> None:
    with pytest.raises(ValueError):
        to.parse(bad)


def test_the_google_font_lists_of_the_server_and_the_picker_are_equal() -> None:
    root = Path(__file__).resolve().parents[2]
    server = (root / "backend" / "app" / "platform" / "google_fonts.json").read_text(encoding="utf-8")
    picker = (root / "frontend" / "platform" / "src" / "themes" / "googleFonts.json").read_text(encoding="utf-8")
    assert server == picker
    assert len(to.google_fonts()) > 1500 and "Lora" in to.google_fonts()


def test_the_accent_ids_equal_the_square_apps_list() -> None:
    src = (Path(__file__).resolve().parents[2] / "square" / "frontend" / "src" / "themes" / "customFonts.ts").read_text(encoding="utf-8")
    block = src.split("export const ACCENTS", 1)[1].split("\n}\n", 1)[0]
    assert tuple(re.findall(r"^  '?([a-z-]+)'?: \{", block, re.M)) == to.ACCENT_IDS[:-1]  # "headings" is no font of its own
