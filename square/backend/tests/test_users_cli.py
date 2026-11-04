"""Tests for users cli (4 tests), e.g. promote sets an existing users role; promote fails for an unknown email; promote fails for an invalid role."""
from app import create_app
from app.auth.models import User
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_promote_sets_an_existing_users_role():
    app = _new_app()
    with app.app_context():
        db.session.add(User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member"))
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["users", "promote", "a@b.com", "admin"])

        assert result.exit_code == 0
        user = User.query.filter_by(email="a@b.com").one()
        assert user.role == "admin"

        db.drop_all()


def test_promote_fails_for_an_unknown_email():
    app = _new_app()
    with app.app_context():
        runner = app.test_cli_runner()
        result = runner.invoke(args=["users", "promote", "nobody@example.com", "admin"])

        assert result.exit_code != 0

        db.drop_all()


def test_promote_fails_for_an_invalid_role():
    app = _new_app()
    with app.app_context():
        db.session.add(User(auth_user_id="sb-2", auth_provider="supabase", email="c@d.com", role="member"))
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["users", "promote", "c@d.com", "superuser"])

        assert result.exit_code != 0
        user = User.query.filter_by(email="c@d.com").one()
        assert user.role == "member"

        db.drop_all()


def test_promote_accepts_the_volunteer_role():
    app = _new_app()
    with app.app_context():
        db.session.add(User(auth_user_id="sb-3", auth_provider="supabase", email="e@f.com", role="member"))
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["users", "promote", "e@f.com", "volunteer"])

        assert result.exit_code == 0
        user = User.query.filter_by(email="e@f.com").one()
        assert user.role == "volunteer"

        db.drop_all()
