import secrets

from sqlalchemy import func

from app.extensions import db


def _new_token() -> str:
    return secrets.token_urlsafe(24)


class Subscriber(db.Model):
    """One newsletter subscriber. Deliberately minimal (GDPR data minimisation): just the email,
    when consent was given, and the status. `token` is the secret in the unsubscribe link, so
    anyone holding an email can leave without logging in. Rows are never needed for anything but
    mailing, and an admin can erase one outright."""

    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    # Stored lower-cased; unique.
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    token = db.Column(db.String(64), nullable=False, unique=True, default=_new_token)
    # "pending" (asked, not yet confirmed by the link in the e-mail: double opt-in, W15-R9) | "subscribed" | "unsubscribed"
    status = db.Column(db.String(20), nullable=False, default="subscribed")
    consented_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    unsubscribed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Subscriber {self.id} ({self.status})>"


class NewsletterIssue(db.Model):
    """One newsletter email an admin composes and sends to every current subscriber.
    `status`: draft -> (scheduled ->) sending -> sent. Progress counters are updated per recipient while
    sending (see app/newsletter/service.py); `last_subscriber_id` is the resume cursor."""

    __tablename__ = "newsletter_issues"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="draft")
    recipients_total = db.Column(db.Integer, nullable=False, default=0)
    sent_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    last_subscriber_id = db.Column(db.Integer, nullable=False, default=0)
    # One-off extra addresses (e.g. a distribution list) chosen at send time: lower-cased,
    # whitespace-separated. They are mailed after the subscribers; `extras_sent` is their cursor.
    extra_recipients = db.Column(db.Text, nullable=False, default="")
    extras_sent = db.Column(db.Integer, nullable=False, default=0)
    sent_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # The Message this issue was copied into (newsletter fold-in step 2, app/newsletter/fold_in.py); a copied issue is never sent again from here.
    moved_to_message_id = db.Column(db.Integer, nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Set while status is "scheduled" (draft -> scheduled -> sending -> sent): the moment the
    # background scheduler starts the send. Kept after it fires, as a record of what was planned.
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NewsletterIssue {self.id} ({self.status})>"
