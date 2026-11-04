from app.audit.models import AuditLog
from app.auth.models import User
from app.extensions import db


def log_action(
    actor: User,
    action: str,
    description: str,
    target_type: str | None = None,
    target_id: int | None = None,
) -> None:
    """The only way any code creates an AuditLog row. Does its own add+commit, separate from
    the caller's own commit for the primary change — call this AFTER that commit succeeds, so
    audit logging can never block or corrupt the actual admin action it's recording.
    """
    entry = AuditLog(
        actor_user_id=actor.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
    )
    db.session.add(entry)
    db.session.commit()
