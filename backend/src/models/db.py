import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

try:
    from pgvector.sqlalchemy import Vector

    VECTOR_TYPE = Vector(384)
except ImportError:
    from sqlalchemy import JSON

    VECTOR_TYPE = JSON  # fallback for environments without pgvector


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------


class UserProfile(Base):
    __tablename__ = "user_profile"
    __table_args__ = (UniqueConstraint("external_sub", "external_iss"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_sub: Mapped[str] = mapped_column(Text, nullable=False)
    external_iss: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    agent_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'person'"))

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", foreign_keys="UserRole.user_id", back_populates="user"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey", foreign_keys="APIKey.user_id", back_populates="user"
    )
    source_memberships: Mapped[list["SourceMembership"]] = relationship(
        "SourceMembership", foreign_keys="SourceMembership.user_id", back_populates="user"
    )


# ---------------------------------------------------------------------------
# APIKey
# ---------------------------------------------------------------------------


class APIKey(Base):
    __tablename__ = "api_key"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=True
    )

    user: Mapped["UserProfile"] = relationship(
        "UserProfile", foreign_keys=[user_id], back_populates="api_keys"
    )

    __table_args__ = (Index("ix_api_key_user_id", "user_id"),)


# ---------------------------------------------------------------------------
# UserRole
# ---------------------------------------------------------------------------


class UserRole(Base):
    __tablename__ = "user_role"
    __table_args__ = (Index("ix_user_role_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    user: Mapped["UserProfile"] = relationship(
        "UserProfile", foreign_keys=[user_id], back_populates="roles"
    )


# ---------------------------------------------------------------------------
# SchemaSource
# ---------------------------------------------------------------------------


class SchemaSource(Base):
    __tablename__ = "schema_source"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    elements: Mapped[list["DataElement"]] = relationship("DataElement", back_populates="source")


# ---------------------------------------------------------------------------
# SourceMembership
# ---------------------------------------------------------------------------


class SourceMembership(Base):
    __tablename__ = "source_membership"
    __table_args__ = (Index("ix_source_membership_user_source", "user_id", "source_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_source.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    user: Mapped["UserProfile"] = relationship(
        "UserProfile", foreign_keys=[user_id], back_populates="source_memberships"
    )
    source: Mapped["SchemaSource"] = relationship("SchemaSource")


# ---------------------------------------------------------------------------
# DataElement
# ---------------------------------------------------------------------------


class DataElement(Base):
    __tablename__ = "data_element"
    __table_args__ = (
        UniqueConstraint("source_id", "source_local_id"),
        Index("ix_data_element_uri", "uri", unique=True),
        Index("ix_data_element_source_id", "source_id"),
        Index("ix_data_element_superseded_by", "superseded_by"),
        Index("ix_data_element_active", "deleted_at", postgresql_where="deleted_at IS NULL"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uri: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_source.id"), nullable=True
    )
    source_local_id: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element_version.id"), nullable=True
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    element_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'scalar'"))
    node_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'field'"))

    source: Mapped["SchemaSource | None"] = relationship("SchemaSource", back_populates="elements")
    current_version: Mapped["DataElementVersion | None"] = relationship(
        "DataElementVersion",
        foreign_keys=[current_version_id],
        lazy="select",
    )
    versions: Mapped[list["DataElementVersion"]] = relationship(
        "DataElementVersion",
        foreign_keys="DataElementVersion.element_id",
        back_populates="element",
        order_by="DataElementVersion.version_num",
    )
    children: Mapped[list["DataElementChild"]] = relationship(
        "DataElementChild",
        foreign_keys="DataElementChild.parent_id",
        back_populates="parent",
        order_by="DataElementChild.position",
    )
    alias_memberships: Mapped[list["AliasGroupMember"]] = relationship(
        "AliasGroupMember", back_populates="element"
    )
    mapping_inputs: Mapped[list["MappingInput"]] = relationship(
        "MappingInput", back_populates="element"
    )


# ---------------------------------------------------------------------------
# DataElementVersion
# ---------------------------------------------------------------------------


class DataElementVersion(Base):
    __tablename__ = "data_element_version"
    __table_args__ = (
        Index("ix_dev_unit", "unit"),
        Index(
            "ix_dev_semantic_graph",
            "semantic_graph",
            postgresql_using="gin",
            postgresql_ops={"semantic_graph": "jsonb_path_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=False
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    multivalued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    semantic_graph: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_embedding: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )  # VECTOR(384) via migration
    description_embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    element: Mapped["DataElement"] = relationship(
        "DataElement", foreign_keys=[element_id], back_populates="versions"
    )
    creator: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[created_by])


# ---------------------------------------------------------------------------
# DataElementChild
# ---------------------------------------------------------------------------


class DataElementChild(Base):
    __tablename__ = "data_element_child"
    __table_args__ = (
        Index("ix_dec_parent_id", "parent_id"),
        Index("ix_dec_child_id", "child_id"),
    )

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)

    parent: Mapped["DataElement"] = relationship(
        "DataElement", foreign_keys=[parent_id], back_populates="children"
    )
    child: Mapped["DataElement"] = relationship("DataElement", foreign_keys=[child_id])


# ---------------------------------------------------------------------------
# MappingFunction
# ---------------------------------------------------------------------------


class MappingFunction(Base):
    __tablename__ = "mapping_function"
    __table_args__ = (Index("ix_mapping_function_uri", "uri", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uri: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    function_type: Mapped[str] = mapped_column(String(50), nullable=False)
    output_element_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=True
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_function_version.id"), nullable=True
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    output_element: Mapped["DataElement | None"] = relationship(
        "DataElement", foreign_keys=[output_element_id]
    )
    current_version: Mapped["MappingFunctionVersion | None"] = relationship(
        "MappingFunctionVersion",
        foreign_keys=[current_version_id],
    )
    versions: Mapped[list["MappingFunctionVersion"]] = relationship(
        "MappingFunctionVersion",
        foreign_keys="MappingFunctionVersion.mapping_id",
        back_populates="mapping",
        order_by="MappingFunctionVersion.version_num",
    )
    inputs: Mapped[list["MappingInput"]] = relationship(
        "MappingInput",
        back_populates="mapping",
        order_by="MappingInput.position",
    )


# ---------------------------------------------------------------------------
# MappingInput
# ---------------------------------------------------------------------------


class MappingInput(Base):
    __tablename__ = "mapping_input"
    __table_args__ = (Index("ix_mapping_input_element_id", "element_id"),)

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_function.id"), primary_key=True
    )
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    mapping: Mapped["MappingFunction"] = relationship("MappingFunction", back_populates="inputs")
    element: Mapped["DataElement"] = relationship("DataElement", back_populates="mapping_inputs")


# ---------------------------------------------------------------------------
# MappingFunctionVersion
# ---------------------------------------------------------------------------


class MappingFunctionVersion(Base):
    __tablename__ = "mapping_function_version"
    __table_args__ = (Index("ix_mfv_created_by", "created_by"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_function.id"), nullable=False
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    expression_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    inverse_mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mapping_function.id"), nullable=True
    )
    sssom_predicate: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    mapping: Mapped["MappingFunction"] = relationship(
        "MappingFunction", foreign_keys=[mapping_id], back_populates="versions"
    )
    creator: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[created_by])


# ---------------------------------------------------------------------------
# AliasGroup
# ---------------------------------------------------------------------------


class AliasGroup(Base):
    __tablename__ = "alias_group"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sssom_predicate: Mapped[str] = mapped_column(Text, nullable=False, default="skos:exactMatch")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detection_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    members: Mapped[list["AliasGroupMember"]] = relationship(
        "AliasGroupMember", back_populates="alias_group"
    )


# ---------------------------------------------------------------------------
# AliasGroupMember
# ---------------------------------------------------------------------------


class AliasGroupMember(Base):
    __tablename__ = "alias_group_member"

    alias_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alias_group.id"), primary_key=True
    )
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )

    alias_group: Mapped["AliasGroup"] = relationship("AliasGroup", back_populates="members")
    element: Mapped["DataElement"] = relationship("DataElement", back_populates="alias_memberships")


# ---------------------------------------------------------------------------
# DynamicSchema
# ---------------------------------------------------------------------------


class DynamicSchema(Base):
    __tablename__ = "dynamic_schema"
    __table_args__ = (
        Index("ix_dynamic_schema_uri", "uri", unique=True),
        Index("ix_dynamic_schema_superseded_by", "superseded_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uri: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), nullable=True
    )
    is_mixin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    schema_elements: Mapped[list["DynamicSchemaElement"]] = relationship(
        "DynamicSchemaElement",
        back_populates="schema",
        order_by="DynamicSchemaElement.position",
    )


# ---------------------------------------------------------------------------
# DynamicSchemaElement
# ---------------------------------------------------------------------------


class DynamicSchemaElement(Base):
    __tablename__ = "dynamic_schema_element"
    __table_args__ = (
        Index("ix_dse_schema_id", "schema_id"),
        Index("ix_dse_element_id", "element_id"),
    )

    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), primary_key=True
    )
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    field_alias: Mapped[str | None] = mapped_column(Text, nullable=True)

    schema: Mapped["DynamicSchema"] = relationship(
        "DynamicSchema", back_populates="schema_elements"
    )
    element: Mapped["DataElement"] = relationship("DataElement")


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_record", "record_type", "record_id"),
        Index("ix_audit_log_actor_id", "actor_id"),
        Index("ix_audit_log_timestamp", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_type: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    version_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diff: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    caused_by_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_log.id"), nullable=True
    )

    actor: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[actor_id])


# ---------------------------------------------------------------------------
# SchemaClassInheritance
# ---------------------------------------------------------------------------


class SchemaClassInheritance(Base):
    __tablename__ = "schema_class_inheritance"

    parent_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    child_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), primary_key=True
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'is_a'"))

    parent_class: Mapped["DataElement"] = relationship("DataElement", foreign_keys=[parent_class_id])
    child_class: Mapped["DataElement"] = relationship("DataElement", foreign_keys=[child_class_id])


# ---------------------------------------------------------------------------
# SchemaEnumeration
# ---------------------------------------------------------------------------


class SchemaEnumeration(Base):
    __tablename__ = "schema_enumeration"
    __table_args__ = (UniqueConstraint("element_id", "value", name="uq_schema_enum_element_value"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    element: Mapped["DataElement"] = relationship("DataElement")


# ---------------------------------------------------------------------------
# ValidationRule
# ---------------------------------------------------------------------------


class ValidationRule(Base):
    __tablename__ = "validation_rule"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    rule_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'error'"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    element: Mapped["DataElement"] = relationship("DataElement")
    creator: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[created_by])
    changes: Mapped[list["ValidationRuleChange"]] = relationship(
        "ValidationRuleChange",
        foreign_keys="ValidationRuleChange.rule_id",
        back_populates="rule",
        order_by="ValidationRuleChange.timestamp",
    )


# ---------------------------------------------------------------------------
# ValidationRuleChange
# ---------------------------------------------------------------------------


class ValidationRuleChange(Base):
    __tablename__ = "validation_rule_change"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("validation_rule.id"), nullable=False
    )
    element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_element.id"), nullable=False
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    breaking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped["ValidationRule"] = relationship("ValidationRule", back_populates="changes")
    element: Mapped["DataElement"] = relationship("DataElement")
    actor: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[actor_id])


# ---------------------------------------------------------------------------
# SchemaMixin
# ---------------------------------------------------------------------------


class SchemaMixin(Base):
    __tablename__ = "schema_mixin"

    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), primary_key=True
    )
    mixin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    schema: Mapped["DynamicSchema"] = relationship("DynamicSchema", foreign_keys=[schema_id])
    mixin: Mapped["DynamicSchema"] = relationship("DynamicSchema", foreign_keys=[mixin_id])


# ---------------------------------------------------------------------------
# SchemaChangeLog
# ---------------------------------------------------------------------------


class SchemaChangeLog(Base):
    __tablename__ = "schema_change_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dynamic_schema.id"), nullable=False
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    breaking: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    semantic_boundary_crossed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    schema: Mapped["DynamicSchema"] = relationship("DynamicSchema", foreign_keys=[schema_id])
    actor: Mapped["UserProfile"] = relationship("UserProfile", foreign_keys=[actor_id])


# ---------------------------------------------------------------------------
# MigrationPathway
# ---------------------------------------------------------------------------


class MigrationPathway(Base):
    __tablename__ = "migration_pathway"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_schema_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_schema_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    inverse_pathway_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("migration_pathway.id"), nullable=True
    )
    steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    inverse_pathway: Mapped["MigrationPathway | None"] = relationship(
        "MigrationPathway", remote_side="MigrationPathway.id", foreign_keys=[inverse_pathway_id]
    )
