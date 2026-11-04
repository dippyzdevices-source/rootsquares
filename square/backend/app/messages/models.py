from sqlalchemy import func

from app.extensions import db


class Message(db.Model):
    """One message to a group of people (the Messages module, wave 14).

    `kind`: "update" (news from the association; people can opt out, the opt-out list is honoured) or "service" (a practical notice about something
    the person booked, bought or joined: no opt-out). `audience` is a rule worked out at send time ({"type": "ticket_holders", "params": {...}}, see
    app/messages/audiences.py), never a stored list of people. `channel` is "email" today; SMS would be another channel (app/messages/channels.py).
    `status`: draft -> (scheduled ->) sending -> sent. `source`: "manual" or "rule:<id>" (a reminder rule made it).
    """

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, default="update")
    channel = db.Column(db.String(10), nullable=False, default="email")
    subject = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    audience = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    source = db.Column(db.String(30), nullable=False, default="manual")
    recipients_total = db.Column(db.Integer, nullable=False, default=0)
    sent_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    skipped_count = db.Column(db.Integer, nullable=False, default=0)
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sent_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Message {self.id} {self.kind} {self.status}>"


class MessageRecipient(db.Model):
    """The people one message went (or will go) to, written when the send starts: it is both the log and the resume cursor.
    Holds an address and a name, so the erasure job anonymises it (app/members/erasure.py). `status`: queued | sent | failed | skipped (opted out)."""

    __tablename__ = "message_recipients"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, default="")
    # Values for the {{placeholders}} of this person (name, event title, due date, ...).
    context = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(10), nullable=False, default="queued", index=True)


class MessageSuppression(db.Model):
    """The do-not-contact list: addresses that opted out of "update" messages. One list for every audience. Lower-cased, unique."""

    __tablename__ = "message_suppressions"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class MessageRule(db.Model):
    """An automatic reminder: when `trigger` is true for a target `offset_days` ahead, a "service" message is made and sent at `send_hour` (site time).
    Triggers: "event_before" (ticket holders of an event that starts in N days), "membership_ending" (memberships that end in N days),
    "period_due" (membership periods unpaid that start in N days)."""

    __tablename__ = "message_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    trigger = db.Column(db.String(30), nullable=False)
    offset_days = db.Column(db.Integer, nullable=False, default=1)
    send_hour = db.Column(db.Integer, nullable=False, default=9)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    subject = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MessageRuleRun(db.Model):
    """One target a rule has already handled ("event:12", "ending:2026-11-01"): the unique pair is what stops a reminder going out twice."""

    __tablename__ = "message_rule_runs"
    __table_args__ = (db.UniqueConstraint("rule_id", "target_key"),)

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("message_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    target_key = db.Column(db.String(60), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
