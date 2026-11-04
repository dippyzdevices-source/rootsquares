from sqlalchemy import func

from app.extensions import db


class EventVolunteer(db.Model):
    """Which events a `volunteer`-role User is allowed to scan check-ins for.

    Admins never need a row here — their check-in access is unrestricted (see
    `app/checkin/admin_routes.py`'s `_volunteer_can_access_event`). A demoted
    volunteer's rows are left in place rather than cleaned up on demotion —
    harmless dangling data, since `checkin_bp`'s role gate already blocks a
    plain `member` from every check-in route regardless of these rows.
    """

    __tablename__ = "event_volunteers"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_event_volunteers_event_user"),
    )

    def __repr__(self) -> str:
        return f"<EventVolunteer event_id={self.event_id} user_id={self.user_id}>"
