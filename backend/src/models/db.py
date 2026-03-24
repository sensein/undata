"""SQLAlchemy models for the undata registry — matches flat-file entity types."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class Element(Base):
    __tablename__ = "elements"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    data_type: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(100))
    pattern: Mapped[str | None] = mapped_column(Text)
    value_domain: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    min_value: Mapped[float | None] = mapped_column(Float)
    max_value: Mapped[float | None] = mapped_column(Float)
    type_ref: Mapped[str | None] = mapped_column(String(255))
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("ix_elements_sha256", "sha256"),
        Index("ix_elements_data_type", "data_type"),
    )


class Schema(Base):
    __tablename__ = "schemas"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    properties: Mapped[list] = mapped_column(JSONB, default=list)
    subclass_of: Mapped[str | None] = mapped_column(String(255))
    is_mixin: Mapped[bool | None] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Value(Base):
    __tablename__ = "values"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(500))
    value_type: Mapped[str | None] = mapped_column(String(50))
    ontology_id: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (Index("ix_values_label", "label"),)


class ValueSet(Base):
    __tablename__ = "valuesets"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500))
    members: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CurationFlag(Base):
    __tablename__ = "curation_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_ref: Mapped[str] = mapped_column(String(500))
    flag_type: Mapped[str] = mapped_column(String(50))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    llm_verification: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_curation_flags_status", "status"),
        Index("ix_curation_flags_type", "flag_type"),
    )


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_ref: Mapped[str] = mapped_column(String(500))
    contribution_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    contributor: Mapped[str] = mapped_column(String(255))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class RunSummary(Base):
    __tablename__ = "run_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[str] = mapped_column(String(50))
    completed_at: Mapped[str | None] = mapped_column(String(50))
    entity_counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    enrichment_rate: Mapped[dict | None] = mapped_column(JSONB)
    curation_flags: Mapped[dict | None] = mapped_column(JSONB)
    delta: Mapped[dict | None] = mapped_column(JSONB)
    timing: Mapped[dict | None] = mapped_column(JSONB)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    external_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="contributor")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
