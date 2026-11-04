"""Newsletter fold-in, step 2 (W14-R18, docs/plans/newsletter-fold-in-plan.md): copy the old newsletter issues into Messages.

Every issue becomes a Message of kind "update" (News) whose audience is the newsletter subscribers: sent issues as sent history (subject, body, counters,
dates; there are no per-person rows to copy), drafts as drafts, scheduled issues as scheduled messages. The copy is idempotent (an issue records the message
it became in `moved_to_message_id` and is never copied twice), never deletes or changes the old issue's content, and refuses while an issue is being sent.
An issue that was copied is skipped by the old scheduler, so a scheduled newsletter goes out once, from Messages.
"""

from __future__ import annotations

from app.extensions import db
from app.messages.models import Message
from app.newsletter.models import NewsletterIssue

# `last_subscriber_id` of an old issue sent only to pasted addresses (the old engine's way of skipping every subscriber)
SKIP_SUBSCRIBERS_CURSOR = 2_147_483_647


class IssueSendingError(RuntimeError):
    """An issue is being sent right now; the copy waits until it is finished."""


def _audience(issue: NewsletterIssue) -> dict:
    extras = issue.extra_recipients.split()
    if issue.last_subscriber_id == SKIP_SUBSCRIBERS_CURSOR and extras:  # an issue sent or planned for pasted addresses only
        return {"type": "custom", "params": {"emails": " ".join(extras)}}
    return {"type": "subscribers", "params": {}}


def copy_issues_to_messages() -> dict:
    """Copy every issue not copied yet. Returns {"copied": n, "already": n, "extras_dropped": [issue ids]}: an unsent issue that was meant for the
    subscribers AND pasted addresses keeps only the subscribers (one audience per newsletter, the owner's decision); its id is listed so it can be checked."""
    if NewsletterIssue.query.filter_by(status="sending").first() is not None:
        raise IssueSendingError("A newsletter is being sent. Wait until it is sent, then copy again.")
    copied = 0
    dropped: list[int] = []
    for issue in NewsletterIssue.query.filter(NewsletterIssue.moved_to_message_id.is_(None)).order_by(NewsletterIssue.id).all():
        audience = _audience(issue)
        if issue.status in ("draft", "scheduled") and audience["type"] == "subscribers" and issue.extra_recipients.split():
            dropped.append(issue.id)
        message = Message(
            kind="update",
            channel="email",
            subject=issue.subject,
            body_html=issue.body_html,
            audience=audience,
            status=issue.status if issue.status in ("draft", "scheduled", "sent") else "draft",
            source=f"newsletter:{issue.id}",
            recipients_total=issue.recipients_total,
            sent_count=issue.sent_count,
            failed_count=issue.failed_count,
            skipped_count=0,
            scheduled_for=issue.scheduled_for if issue.status == "scheduled" else None,
            sent_at=issue.sent_at,
            sent_by_user_id=issue.sent_by_user_id,
            created_at=issue.created_at,
        )
        db.session.add(message)
        db.session.flush()
        issue.moved_to_message_id = message.id
        copied += 1
    db.session.commit()
    return {"copied": copied, "already": NewsletterIssue.query.filter(NewsletterIssue.moved_to_message_id.isnot(None)).count() - copied, "extras_dropped": dropped}
