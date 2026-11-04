from sqlalchemy import func

from app.extensions import db


class ImportBatch(db.Model):
    """A record of one confirmed Excel import run — BCA-125 (import history). Written once,
    at confirm time, never updated — a permanent audit trail of who imported what and when.
    """

    __tablename__ = "import_batches"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    total_rows = db.Column(db.Integer, nullable=False)
    members_created = db.Column(db.Integer, nullable=False, default=0)
    memberships_created = db.Column(db.Integer, nullable=False, default=0)
    failed_rows = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    admin_user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<ImportBatch {self.filename!r} ({self.total_rows} rows)>"
