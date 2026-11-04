"""Gated features (W14-R25): the package decides message reminders and repeating events; nothing is deleted, reading stays, the jobs skip."""

from unittest.mock import patch

from app import features
from app.events import series as series_logic
from app.events.models import Event
from app.extensions import db
from app.messages import rules
from app.messages.models import MessageRule
from tests.test_event_series import _admin, _new_app, _sunday_event


def test_the_browser_is_told_which_features_the_package_has():
    assert features.features_for("square", None) == []
    assert features.features_for("grove", None) == ["message_reminders", "repeating_events"]
    assert features.features_for("", None) == ["message_reminders", "repeating_events"]  # a square made before packages counts as Grove
    assert features.features_for("event", None) == ["message_reminders"]  # the Event pass has reminders for its ticket holders, no repeating
    assert features.features_for("grove", ("events",)) == ["repeating_events"]  # a feature needs its module on
    assert features.features_for("custom", None) == ["message_reminders", "repeating_events"]  # a custom package has them all (W19-R20); its modules decide which show


def test_without_a_served_square_every_feature_is_on():
    app = _new_app()
    with app.test_request_context():
        assert all(features.feature_enabled(k) for k in features.FEATURE_KEYS)


def test_a_square_package_cannot_change_reminders_but_can_read_and_delete_them():
    app = _new_app()
    with app.app_context():
        rule = MessageRule(name="Day before", trigger="event_before", offset_days=1, send_hour=9, subject="S", body_html="<p>x</p>")
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id
        body = {"name": "New", "trigger": "event_before", "offset_days": 1, "subject": "S", "body_html": "<p>x</p>"}
        with patch("app.features.current_package", return_value="square"):
            refused = _admin(app, "post", "/api/admin/messages/rules", json=body)
            assert refused.status_code == 403 and refused.get_json()["code"] == "feature_not_in_package" and refused.get_json()["feature"] == "message_reminders"
            assert _admin(app, "patch", f"/api/admin/messages/rules/{rule_id}", json={"enabled": False}).status_code == 403
            assert _admin(app, "get", "/api/admin/messages/rules").status_code == 200  # reading stays
            assert rules.run_rules() == 0  # the job skips the square
            assert _admin(app, "delete", f"/api/admin/messages/rules/{rule_id}").status_code == 204  # taking one away stays possible
        assert _admin(app, "post", "/api/admin/messages/rules", json=body).status_code == 201  # Grove can
        db.drop_all()


def test_a_square_package_cannot_repeat_an_event_and_the_top_up_skips_it():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        with patch("app.features.current_package", return_value="square"):
            refused = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly", "interval_weeks": 1})
            assert refused.status_code == 403 and refused.get_json()["feature"] == "repeating_events"
            assert Event.query.count() == 1
            assert series_logic.extend_all() == 0
        assert _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly", "interval_weeks": 1}).status_code == 201
        with patch("app.features.current_package", return_value="square"):
            assert series_logic.extend_all() == 0  # an existing series is left as it is
        db.drop_all()
