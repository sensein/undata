"""V2 schema shape model — content-addressed class shapes."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class SchemaShapeV2(Base):
    __tablename__ = "schema_shape_v2"

    id: Mapped[int] = mapped_column(primary_key=True)
    semantic_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uri: Mapped[str] = mapped_column(String(255), unique=True)
    semantic: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    provenance: Mapped[list["SchemaProvenanceV2"]] = relationship(
        back_populates="schema_shape", cascade="all, delete-orphan", lazy="selectin"
    )


class SchemaProvenanceV2(Base):
    __tablename__ = "schema_provenance_v2"
    __table_args__ = (
        UniqueConstraint("schema_shape_id", "source", "name", name="uq_schema_prov_source_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_shape_id: Mapped[int] = mapped_column(
        ForeignKey("schema_shape_v2.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    schema_shape: Mapped["SchemaShapeV2"] = relationship(back_populates="provenance")
