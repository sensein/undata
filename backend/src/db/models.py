"""SQLAlchemy ORM models for the undata backend."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # graceful fallback for environments without pgvector

from .session import Base


class Element(Base):
    __tablename__ = "elements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    data_type: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    value_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    type_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    embedding = Column(Vector(384), nullable=True) if Vector else None
    search_tsv = Column(TSVECTOR, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class Schema(Base):
    __tablename__ = "schemas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    subclass_of: Mapped[str | None] = mapped_column(String, nullable=True)
    is_mixin: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    properties: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    embedding = Column(Vector(384), nullable=True) if Vector else None
    search_tsv = Column(TSVECTOR, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class Value(Base):
    __tablename__ = "values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String, nullable=True)
    ontology_id: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    embedding = Column(Vector(384), nullable=True) if Vector else None
    search_tsv = Column(TSVECTOR, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class ValueSet(Base):
    __tablename__ = "valuesets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    members: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    ontology_annotations: Mapped[list] = mapped_column(JSONB, default=list)
    embedding = Column(Vector(384), nullable=True) if Vector else None
    search_tsv = Column(TSVECTOR, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class CurationFlag(Base):
    __tablename__ = "curation_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String)
    entity_ref: Mapped[str] = mapped_column(String)
    flag_type: Mapped[str] = mapped_column(String, index=True)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    llm_verification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True, server_default=text("'pending'"))
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))
    resolved_at = mapped_column(TIMESTAMP, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String)
    entity_ref: Mapped[str] = mapped_column(String)
    contribution_type: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String, server_default=text("'pending'"))
    contributor: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at = mapped_column(TIMESTAMP, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class RunSummary(Base):
    __tablename__ = "run_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    enrichment_rate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    curation_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_sub: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, server_default=text("'viewer'"))
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))
    revoked_at = mapped_column(TIMESTAMP, nullable=True)


class LinkHealthCheck(Base):
    __tablename__ = "link_health_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_type: Mapped[str] = mapped_column(String, index=True)  # "domain" or "ontology_prefix"
    target: Mapped[str] = mapped_column(String, unique=True)  # domain or prefix URL
    http_status: Mapped[int] = mapped_column(default=0)
    redirect_target: Mapped[str | None] = mapped_column(String, nullable=True)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=False)
    affected_entity_count: Mapped[int] = mapped_column(default=0)
    checked_at = mapped_column(TIMESTAMP, server_default=text("now()"))
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


class Transform(Base):
    __tablename__ = "transforms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_element: Mapped[str] = mapped_column(String, index=True)  # sha256 or URI of source element
    target_element: Mapped[str] = mapped_column(String, index=True)  # sha256 or URI of target element
    function_type: Mapped[str | None] = mapped_column(String, nullable=True)  # identity, unit_conversion, etc.
    input_type: Mapped[str | None] = mapped_column(String, nullable=True)
    output_type: Mapped[str | None] = mapped_column(String, nullable=True)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    expression_type: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, default=list)
    created_at = mapped_column(TIMESTAMP, server_default=text("now()"))


# Entity type → ORM model mapping
ENTITY_MODEL_MAP = {
    "elements": Element,
    "schemas": Schema,
    "values": Value,
    "valuesets": ValueSet,
    "transforms": Transform,
}
