from sqlalchemy import func

from app.extensions import db


class LookupValue(db.Model):
    """One admin-editable option of a controlled list (a "value driver"), e.g. an expense
    category. `list_key` names the list (see `app/lookups/registry.py`), `value` is the stable
    identifier stored on other rows (never renamed), `label` is the display text. Retire a value
    with `is_active=False` — there is deliberately no delete, since old rows still reference it.
    """

    __tablename__ = "lookup_values"
    __table_args__ = (db.UniqueConstraint("list_key", "value", name="uq_lookup_values_list_value"),)

    id = db.Column(db.Integer, primary_key=True)
    list_key = db.Column(db.String(50), nullable=False, index=True)
    value = db.Column(db.String(60), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<LookupValue {self.list_key}:{self.value}>"
