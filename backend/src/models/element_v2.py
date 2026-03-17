"""V2 element model — content-addressed identity with provenance.

Uses undata-library's hashing and models for content-addressed identity.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class ElementV2(Base):
    __tablename__ = "element_v2"

    id: Mapped[int] = mapped_column(primary_key=True)
    semantic_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uri: Mapped[str] = mapped_column(String(255), unique=True)
    semantic: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    provenance: Mapped[list["ElementProvenanceV2"]] = relationship(
        back_populates="element", cascade="all, delete-orphan", lazy="selectin"
    )


class ElementProvenanceV2(Base):
    __tablename__ = "element_provenance_v2"
    __table_args__ = (
        UniqueConstraint("element_id", "source", "name", name="uq_elem_prov_source_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    element_id: Mapped[int] = mapped_column(ForeignKey("element_v2.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    class_: Mapped[str] = mapped_column("class", String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    required: Mapped[bool | None] = mapped_column()
    multivalued: Mapped[bool | None] = mapped_column()
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    element: Mapped["ElementV2"] = relationship(back_populates="provenance")
