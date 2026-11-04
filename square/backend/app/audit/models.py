from sqlalchemy import func

from app.extensions import db


class AuditLog(db.Model):
    """One row per logged admin action. Written only via app.audit.service.log_action() —
    never constructed directly outside that function or a test.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    # Always set — every call site sits behind a require_role("admin") blueprint.
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    # e.g. "user", "membership", "order", "event", "album", "media", "news", "ticket_type" —
    # null for settings_updated (a singleton, no target id).
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<AuditLog {self.action!r}>"
