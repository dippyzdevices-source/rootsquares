"""Tests for settings home content (11 tests), e.g. home content is empty by default and cleaned when an admin sets it; home content refuses wrong shapes and too long texts; logo size and name style are choices."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _patch(client, headers, body):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return client.patch("/api/admin/settings", json={"home_content": body}, headers=headers)


def test_home_content_is_empty_by_default_and_cleaned_when_an_admin_sets_it():
    """rootsquares W6-R64: a square sets its own home page, header and footer words."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        assert client.get("/api/settings").get_json()["home_content"] == {}
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {
                "headline": "  Bengal, kept alive in Oslo ",
                "local_line": "অসলোয় বাংলার প্রাণ",
                "eyebrow": "   ",
                "unknown_key": "dropped",
                "stats": [{"value": "16", "label": "years"}, {"value": "", "label": "no number"}, {"value": "410", "label": "members"}],
            },
        )
        assert ok.status_code == 200
        assert ok.get_json()["home_content"] == {
            "headline": "Bengal, kept alive in Oslo",
            "local_line": "অসলোয় বাংলার প্রাণ",
            "stats": [{"value": "16", "label": "years"}, {"value": "410", "label": "members"}],
        }
        assert client.get("/api/settings").get_json()["home_content"]["headline"] == "Bengal, kept alive in Oslo"
        assert _patch(client, headers, {}).get_json()["home_content"] == {}  # an empty object clears it
        db.drop_all()


def test_home_content_refuses_wrong_shapes_and_too_long_texts():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        bad = [
            "text",
            {"headline": "x" * 121},
            {"headline": 5},
            {"stats": "no"},
            {"stats": [{"value": "1", "label": "a"}] * 4},
            {"stats": [{"value": "1" * 13, "label": "a"}]},
            {"stats": ["x"]},
        ]
        assert [_patch(client, headers, b).status_code for b in bad] == [400] * len(bad)
        assert client.get("/api/settings").get_json()["home_content"] == {}
        db.drop_all()


def test_logo_size_and_name_style_are_choices():
    """W6-R67: the logo size and how the name is written are chosen from a short list, empty = the default."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(client, headers, {"logo_size": "large", "name_style": "caps"})
        assert ok.status_code == 200 and ok.get_json()["home_content"] == {"logo_size": "large", "name_style": "caps"}
        assert _patch(client, headers, {"logo_size": "", "name_style": ""}).get_json()["home_content"] == {}
        assert [_patch(client, headers, b).status_code for b in ({"logo_size": "huge"}, {"name_style": "bold"}, {"logo_size": 5})] == [400, 400, 400]
        db.drop_all()


def test_footer_words_and_social_links_are_optional_and_checked():
    """W6-R70: footer registration line, description, copyright line and social links; anything left empty is simply not shown."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {
                "footer_registration": " Org. nr. 995757664 ",
                "footer_blurb": "A cultural association.",
                "footer_copyright": "(c) 2026 BCA Oslo, Bengali Cultural Association",
                "social_links": [
                    {"network": "facebook", "url": " https://www.facebook.com/bcaoslo "},
                    {"network": "instagram", "url": ""},
                    {"network": "youtube", "url": "https://youtube.com/@bca"},
                ],
            },
        )
        content = ok.get_json()["home_content"]
        assert ok.status_code == 200
        assert content["footer_registration"] == "Org. nr. 995757664" and content["footer_blurb"] == "A cultural association."
        assert content["social_links"] == [{"network": "facebook", "url": "https://www.facebook.com/bcaoslo"}, {"network": "youtube", "url": "https://youtube.com/@bca"}]
        twice = _patch(client, headers, {"social_links": [{"network": "facebook", "url": "https://a.example"}, {"network": "facebook", "url": "https://b.example"}]})
        assert twice.get_json()["home_content"]["social_links"] == [{"network": "facebook", "url": "https://a.example"}]  # one link per network
        assert _patch(client, headers, {}).get_json()["home_content"] == {}  # everything off again
        bad = [
            {"social_links": [{"network": "myspace", "url": "https://x.example"}]},
            {"social_links": [{"network": "facebook", "url": "http://insecure.example"}]},
            {"social_links": [{"network": "facebook", "url": "javascript:alert(1)"}]},
            {"social_links": "no"},
            {"social_links": [{"network": "facebook", "url": "https://a.example"}] * 4},
            {"footer_copyright": "x" * 161},
        ]
        assert [_patch(client, headers, b).status_code for b in bad] == [400] * len(bad)
        db.drop_all()


def test_page_headings_are_cleaned_per_page_and_checked():
    """W6-R75: the heading words of each public page; empty keys and empty pages are dropped (the page keeps its own text)."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {"page_headings": {"events": {"eyebrow": " Programme ", "title": "What is on", "intro": "", "script_line": "  "}, "gallery": {"title": ""}, "contact": {"local_line": "যোগাযোগ"}}},
        )
        assert ok.status_code == 200
        assert ok.get_json()["home_content"] == {"page_headings": {"events": {"eyebrow": "Programme", "title": "What is on"}, "contact": {"local_line": "যোগাযোগ"}}}
        assert _patch(client, headers, {"page_headings": {}}).get_json()["home_content"] == {}
        bad = [
            {"page_headings": {"shop": {"title": "x"}}},
            {"page_headings": {"events": "x"}},
            {"page_headings": {"events": {"title": "x" * 121}}},
            {"page_headings": {"events": {"intro": 5}}},
            {"page_headings": []},
        ]
        assert [_patch(client, headers, b).status_code for b in bad] == [400] * len(bad)
        db.drop_all()


def test_gallery_band_keeps_only_set_words_and_coverage_is_off_unless_true():
    """rootsquares W7-R4: the band at the bottom of the gallery page is the square's own words."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(client, headers, {"gallery_band": {"title": " Old photos? ", "text": "", "eyebrow": "  ", "show_coverage": False}})
        assert ok.get_json()["home_content"] == {"gallery_band": {"title": "Old photos?"}}
        on = _patch(client, headers, {"gallery_band": {"title": "Old photos?", "button_label": "Send", "show_coverage": True}})
        assert on.get_json()["home_content"]["gallery_band"] == {"title": "Old photos?", "button_label": "Send", "show_coverage": True}
        assert _patch(client, headers, {"gallery_band": {}}).get_json()["home_content"] == {}
        assert _patch(client, headers, {"gallery_band": {"title": "x" * 121}}).status_code == 400
        assert _patch(client, headers, {"gallery_band": {"show_coverage": "yes"}}).status_code == 400
        assert _patch(client, headers, {"gallery_band": "text"}).status_code == 400
        db.drop_all()


def test_news_band_keeps_only_set_words_and_magazines_are_off_unless_true():
    """rootsquares W7-R5: the newsletter band on the news page and the Magazines tab are the square's own choices."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(client, headers, {"news_band": {"title": " The newsletter ", "consent": "", "show_magazines": False}})
        assert ok.get_json()["home_content"] == {"news_band": {"title": "The newsletter"}}
        on = _patch(client, headers, {"news_band": {"consent": "You agree.", "show_magazines": True}, "gallery_band": {"title": "Photos"}})
        assert on.get_json()["home_content"] == {"news_band": {"consent": "You agree.", "show_magazines": True}, "gallery_band": {"title": "Photos"}}
        assert _patch(client, headers, {"news_band": {"title": "x" * 121}}).status_code == 400
        assert _patch(client, headers, {"news_band": {"show_magazines": 1}}).status_code == 400
        assert _patch(client, headers, {"news_band": []}).status_code == 400
        db.drop_all()


def test_contact_page_keeps_only_complete_questions_and_set_words():
    """rootsquares W7-R9: the questions and the footnote on the contact page are the square's own."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {"contact_page": {"faq_title": " Common questions ", "footnote_text": "", "faq": [{"title": "Where?", "content": "At the hall."}, {"title": "No answer", "content": ""}, {"title": "", "content": ""}]}},
        )
        assert ok.get_json()["home_content"] == {"contact_page": {"faq_title": "Common questions", "faq": [{"title": "Where?", "content": "At the hall."}]}}
        assert _patch(client, headers, {"contact_page": {}}).get_json()["home_content"] == {}
        assert _patch(client, headers, {"contact_page": {"faq": [{"title": "q", "content": "a"}] * 6}}).status_code == 400
        assert _patch(client, headers, {"contact_page": {"faq": [{"title": "x" * 151, "content": "a"}]}}).status_code == 400
        assert _patch(client, headers, {"contact_page": {"faq": ["text"]}}).status_code == 400
        assert _patch(client, headers, {"contact_page": {"footnote_link": "x" * 61}}).status_code == 400
        assert _patch(client, headers, {"contact_page": []}).status_code == 400
        db.drop_all()


def test_about_page_keeps_only_set_words_and_complete_rows():
    """rootsquares W7-R10: the sections of the About page are the square's own."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {
                "about_page": {
                    "values_title": " Who are we ",
                    "what_text": "",
                    "values": [{"title": "Community first", "description": "Together."}, {"title": "", "description": "no title"}],
                    "timeline": [{"year": "2010", "title": "We began", "description": ""}, {"year": "2011", "title": "", "description": "x"}],
                }
            },
        )
        assert ok.get_json()["home_content"] == {
            "about_page": {
                "values_title": "Who are we",
                "values": [{"title": "Community first", "description": "Together."}],
                "timeline": [{"year": "2010", "title": "We began"}],
            }
        }
        assert _patch(client, headers, {"about_page": {}}).get_json()["home_content"] == {}
        assert _patch(client, headers, {"about_page": {"values": [{"title": "t"}] * 7}}).status_code == 400
        assert _patch(client, headers, {"about_page": {"timeline": [{"title": "t"}] * 11}}).status_code == 400
        assert _patch(client, headers, {"about_page": {"values": [{"title": "x" * 81}]}}).status_code == 400
        assert _patch(client, headers, {"about_page": {"timeline": ["text"]}}).status_code == 400
        assert _patch(client, headers, {"about_page": {"what_text": "x" * 1201}}).status_code == 400
        assert _patch(client, headers, {"about_page": {"involve_title": 5}}).status_code == 400
        assert _patch(client, headers, {"about_page": []}).status_code == 400
        db.drop_all()


def test_membership_page_keeps_only_lines_that_have_text():
    """rootsquares W7-R11: why join and how to join on the Membership page are the square's own."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(
            client,
            headers,
            {"membership_page": {"benefits_eyebrow": " Why join ", "benefits": [{"text": " Cheaper tickets "}, {"text": ""}], "steps": [{"text": ""}]}},
        )
        assert ok.get_json()["home_content"] == {"membership_page": {"benefits_eyebrow": "Why join", "benefits": [{"text": "Cheaper tickets"}]}}
        assert _patch(client, headers, {"membership_page": {}}).get_json()["home_content"] == {}
        assert _patch(client, headers, {"membership_page": {"steps": [{"text": "s"}] * 7}}).status_code == 400
        assert _patch(client, headers, {"membership_page": {"benefits": [{"text": "x" * 301}]}}).status_code == 400
        assert _patch(client, headers, {"membership_page": {"benefits": ["text"]}}).status_code == 400
        assert _patch(client, headers, {"membership_page": {"steps_eyebrow": "x" * 61}}).status_code == 400
        assert _patch(client, headers, {"membership_page": []}).status_code == 400
        db.drop_all()


def test_a_page_can_be_named_for_the_menu():
    """W11-R43: nav_label is kept per page, trimmed, limited to 40 characters, and an empty one is dropped."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        ok = _patch(client, headers, {"page_headings": {"heritage": {"nav_label": "  Peek Us  "}, "events": {"nav_label": ""}}})
        assert ok.status_code == 200
        assert ok.get_json()["home_content"] == {"page_headings": {"heritage": {"nav_label": "Peek Us"}}}
        assert _patch(client, headers, {"page_headings": {"heritage": {"nav_label": "x" * 41}}}).status_code == 400
        db.drop_all()
