from sqlalchemy import select

from app.extensions import db
from app.members.models import Member


def member_name_for_user(user_id: int | None) -> str | None:
    """Look up the display name for a user via their linked Member profile.

    User (app.auth.models.User) has no name column of its own — only the linked Member does,
    and the two are linked by Member.user_id, not the other way round. Shared by every admin
    route that needs to show "who did this" (orders, tickets, audit log).
    """
    if user_id is None:
        return None
    member = db.session.execute(select(Member).where(Member.user_id == user_id)).scalar_one_or_none()
    return member.name if member else None
