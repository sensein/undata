"""PROV-O Pydantic v2 models — hand-authored fallback.

Normally generated via:
    gen-pydantic backend/data/prov-o.linkml.yaml --output backend/src/models/prov_o.py

Both linkml-owl-to-linkml and gen-pydantic fail on Python 3.14 (linkml.__init__
AttributeError: Format.JSON). This module was hand-authored from the LinkML YAML at
backend/data/prov-o.linkml.yaml, which itself mirrors the W3C PROV-O spec subset
defined in specs/011-metamodel-provenance/data-model.md.

Regenerate when linkml supports Python 3.14.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

PROV_CONTEXT = "https://www.w3.org/ns/prov.jsonld"


class Agent(BaseModel):
    """prov:Agent — something bearing responsibility for an activity or entity."""

    id: str = Field(alias="@id")
    type: str = Field(default="prov:Agent", alias="@type")
    name: str | None = Field(default=None, alias="foaf:name")

    model_config = {"populate_by_name": True}

    def to_jsonld(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(by_alias=True).items() if v is not None}


class Activity(BaseModel):
    """prov:Activity — an occurrence that generated or used entities."""

    id: str = Field(alias="@id")
    type: str = Field(default="prov:Activity", alias="@type")
    startedAtTime: str | None = Field(default=None, alias="prov:startedAtTime")
    endedAtTime: str | None = Field(default=None, alias="prov:endedAtTime")
    wasAssociatedWith: dict[str, str] | None = Field(
        default=None, alias="prov:wasAssociatedWith"
    )

    model_config = {"populate_by_name": True}

    def to_jsonld(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(by_alias=True).items() if v is not None}


class Entity(BaseModel):
    """prov:Entity — a thing that may have provenance."""

    id: str = Field(alias="@id")
    type: str = Field(default="prov:Entity", alias="@type")
    wasGeneratedBy: dict[str, str] | None = Field(default=None, alias="prov:wasGeneratedBy")
    wasAttributedTo: dict[str, str] | None = Field(default=None, alias="prov:wasAttributedTo")
    wasDerivedFrom: dict[str, str] | None = Field(default=None, alias="prov:wasDerivedFrom")

    model_config = {"populate_by_name": True}

    def to_jsonld(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(by_alias=True).items() if v is not None}


class Bundle(BaseModel):
    """prov:Bundle — a named set of provenance descriptions."""

    context: str = Field(default=PROV_CONTEXT, alias="@context")
    graph: list[dict[str, Any]] = Field(default_factory=list, alias="@graph")

    model_config = {"populate_by_name": True}

    def to_jsonld(self) -> dict[str, Any]:
        return {"@context": self.context, "@graph": self.graph}
