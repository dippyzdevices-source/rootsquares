from sqlalchemy import func

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    auth_user_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    auth_provider = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50))
    role = db.Column(db.String(20), nullable=False, default="member")
    # Set while an erase request is pending and after the person is anonymised: the account can no longer sign in.
    disabled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User {self.email!r} ({self.role})>"
