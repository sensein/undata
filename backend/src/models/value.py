"""V2 value concept model — content-addressed categorical values."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class ValueConcept(Base):
    __tablename__ = "value_concept"

    id: Mapped[int] = mapped_column(primary_key=True)
    semantic_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uri: Mapped[str] = mapped_column(String(255), unique=True)
    semantic: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    provenance: Mapped[list["ValueProvenance"]] = relationship(
        back_populates="value_concept", cascade="all, delete-orphan", lazy="selectin"
    )


class ValueProvenance(Base):
    __tablename__ = "value_provenance"
    __table_args__ = (
        UniqueConstraint("value_concept_id", "source", "raw_value", name="uq_val_prov_source_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    value_concept_id: Mapped[int] = mapped_column(
        ForeignKey("value_concept.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(500), nullable=False)
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    value_concept: Mapped["ValueConcept"] = relationship(back_populates="provenance")
