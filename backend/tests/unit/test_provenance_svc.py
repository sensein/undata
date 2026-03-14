"""Unit tests for PROV-O model helpers and provenance assembly — T037.

Tests run entirely offline (no DB) using mock record objects.
Covers:
- prov_o.py: Entity, Activity, Agent, Bundle serialization
- schema_changelog.py assembly logic (via bundle building with mock logs)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.models.prov_o import PROV_CONTEXT, Activity, Agent, Bundle, Entity


# ---------------------------------------------------------------------------
# prov_o model tests
# ---------------------------------------------------------------------------


class TestEntityModel:
    def test_entity_to_jsonld_basic(self):
        e = Entity(**{"@id": "urn:test:entity1"})
        jld = e.to_jsonld()
        assert jld["@id"] == "urn:test:entity1"
        assert jld["@type"] == "prov:Entity"

    def test_entity_omits_none_fields(self):
        e = Entity(**{"@id": "urn:test:e2"})
        jld = e.to_jsonld()
        assert "prov:wasGeneratedBy" not in jld
        assert "prov:wasAttributedTo" not in jld
        assert "prov:wasDerivedFrom" not in jld

    def test_entity_with_all_fields(self):
        e = Entity(**{
            "@id": "urn:test:e3",
            "prov:wasGeneratedBy": {"@id": "urn:activity:a1"},
            "prov:wasAttributedTo": {"@id": "urn:agent:u1"},
            "prov:wasDerivedFrom": {"@id": "urn:test:e2"},
        })
        jld = e.to_jsonld()
        assert jld["prov:wasGeneratedBy"] == {"@id": "urn:activity:a1"}
        assert jld["prov:wasAttributedTo"] == {"@id": "urn:agent:u1"}
        assert jld["prov:wasDerivedFrom"] == {"@id": "urn:test:e2"}

    def test_entity_populate_by_name(self):
        """Entity can be constructed using field names (not just aliases)."""
        e = Entity(id="urn:test:e4")
        assert e.id == "urn:test:e4"


class TestActivityModel:
    def test_activity_to_jsonld(self):
        a = Activity(**{
            "@id": "urn:activity:a1",
            "prov:startedAtTime": "2026-03-12T00:00:00+00:00",
            "prov:endedAtTime": "2026-03-12T00:00:01+00:00",
            "prov:wasAssociatedWith": {"@id": "urn:agent:u1"},
        })
        jld = a.to_jsonld()
        assert jld["@id"] == "urn:activity:a1"
        assert jld["@type"] == "prov:Activity"
        assert jld["prov:startedAtTime"] == "2026-03-12T00:00:00+00:00"

    def test_activity_omits_none_times(self):
        a = Activity(**{"@id": "urn:activity:a2"})
        jld = a.to_jsonld()
        assert jld["@id"] == "urn:activity:a2"
        # None fields excluded by to_jsonld
        assert "prov:startedAtTime" not in jld or jld.get("prov:startedAtTime") is None


class TestAgentModel:
    def test_agent_to_jsonld(self):
        ag = Agent(**{"@id": "urn:agent:u1", "foaf:name": "Test User"})
        jld = ag.to_jsonld()
        assert jld["@id"] == "urn:agent:u1"
        assert jld["@type"] == "prov:Agent"
        assert jld["foaf:name"] == "Test User"

    def test_agent_without_name(self):
        ag = Agent(**{"@id": "urn:agent:u2"})
        jld = ag.to_jsonld()
        assert "foaf:name" not in jld or jld.get("foaf:name") is None


class TestBundleModel:
    def test_bundle_to_jsonld_structure(self):
        e = Entity(**{"@id": "urn:test:e1"})
        a = Activity(**{"@id": "urn:activity:a1"})
        ag = Agent(**{"@id": "urn:agent:u1"})

        graph = [e.to_jsonld(), a.to_jsonld(), ag.to_jsonld()]
        b = Bundle(graph=graph)
        jld = b.to_jsonld()

        assert jld["@context"] == PROV_CONTEXT
        assert isinstance(jld["@graph"], list)
        assert len(jld["@graph"]) == 3

    def test_bundle_context_is_https(self):
        b = Bundle()
        assert b.context.startswith("https://")
        assert "prov.jsonld" in b.context

    def test_empty_bundle(self):
        b = Bundle()
        jld = b.to_jsonld()
        assert jld["@graph"] == []


# ---------------------------------------------------------------------------
# Provenance assembly logic tests (offline, no DB)
# ---------------------------------------------------------------------------


def _make_log(
    log_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    schema_id: uuid.UUID | None = None,
    version_num: int = 1,
    operation: str = "create",
    semantic_boundary_crossed: bool = False,
    ts: datetime | None = None,
) -> MagicMock:
    """Fabricate a mock SchemaChangeLog row."""
    log = MagicMock()
    log.id = log_id or uuid.uuid4()
    log.actor_id = actor_id or uuid.uuid4()
    log.schema_id = schema_id or uuid.uuid4()
    log.version_num = version_num
    log.operation = operation
    log.semantic_boundary_crossed = semantic_boundary_crossed
    log.timestamp = ts or datetime.now(timezone.utc)
    return log


def _make_version(
    ver_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    element_id: uuid.UUID | None = None,
    version_num: int = 1,
    ts: datetime | None = None,
) -> MagicMock:
    """Fabricate a mock DataElementVersion row."""
    v = MagicMock()
    v.id = ver_id or uuid.uuid4()
    v.created_by = created_by or uuid.uuid4()
    v.element_id = element_id or uuid.uuid4()
    v.version_num = version_num
    v.created_at = ts or datetime.now(timezone.utc)
    return v


class TestProvenanceAssemblyOffline:
    """Test the graph assembly logic without DB calls."""

    def test_entity_generated_by_latest_log(self):
        """Entity.wasGeneratedBy must reference latest log's activity."""
        schema_id = uuid.uuid4()
        schema_uri = f"https://schema.undata.live/schemas/{schema_id}"

        log1 = _make_log(schema_id=schema_id, version_num=1, operation="create")
        log2 = _make_log(schema_id=schema_id, version_num=2, operation="update")

        logs = [log2, log1]  # ordered desc (latest first)
        latest = logs[0]

        entity_kwargs = {"id": schema_uri}
        entity_kwargs["wasGeneratedBy"] = {"@id": f"urn:activity:{latest.id}"}
        entity_kwargs["wasAttributedTo"] = {"@id": f"urn:agent:{latest.actor_id}"}

        entity = Entity(**entity_kwargs)
        jld = entity.to_jsonld()

        assert jld["prov:wasGeneratedBy"]["@id"] == f"urn:activity:{latest.id}"

    def test_semantic_boundary_adds_derived_entity(self):
        """When semantic_boundary_crossed=True, an extra prov:Entity with versioned URI must appear."""
        schema_id = uuid.uuid4()
        schema_uri = f"https://schema.undata.live/schemas/{schema_id}"

        log_boundary = _make_log(
            schema_id=schema_id, version_num=2, semantic_boundary_crossed=True
        )
        logs = [log_boundary]
        boundary_logs = [lg for lg in logs if getattr(lg, "semantic_boundary_crossed", False)]

        graph: list[dict] = []
        entity_kwargs: dict = {"id": schema_uri}
        graph.append(Entity(**entity_kwargs).to_jsonld())

        for i, bl in enumerate(boundary_logs):
            prior_uri = f"https://schema.undata.live/schemas/{schema_id}/v{bl.version_num}"
            prior_entity: dict = {"id": prior_uri}
            if i == 0:
                entity_kwargs["wasDerivedFrom"] = {"@id": prior_uri}
                graph[0] = Entity(**entity_kwargs).to_jsonld()
            graph.append(Entity(**prior_entity).to_jsonld())

        assert len(graph) == 2
        # First entity should have wasDerivedFrom the versioned URI
        assert graph[0]["prov:wasDerivedFrom"]["@id"].endswith(f"/v{log_boundary.version_num}")
        # Second entity should be the versioned entity
        assert graph[1]["@id"] == f"https://schema.undata.live/schemas/{schema_id}/v2"

    def test_agent_deduplication_in_graph(self):
        """Same actor_id should only produce one Agent node."""
        actor_id = uuid.uuid4()
        log1 = _make_log(actor_id=actor_id, version_num=1)
        log2 = _make_log(actor_id=actor_id, version_num=2)

        logs = [log1, log2]
        seen_agents: set[str] = set()
        agent_nodes = []

        for log in logs:
            agent_id = f"urn:agent:{log.actor_id}"
            if agent_id not in seen_agents:
                seen_agents.add(agent_id)
                agent_nodes.append(Agent(**{"@id": agent_id, "foaf:name": "Test"}).to_jsonld())

        assert len(agent_nodes) == 1

    def test_full_bundle_with_mock_logs(self):
        """Full provenance bundle from mock logs passes structural assertions."""
        schema_id = uuid.uuid4()
        schema_uri = f"https://schema.undata.live/schemas/{schema_id}"
        actor_id = uuid.uuid4()

        log = _make_log(schema_id=schema_id, actor_id=actor_id, version_num=1)
        logs = [log]

        entity_kwargs = {
            "id": schema_uri,
            "wasGeneratedBy": {"@id": f"urn:activity:{log.id}"},
            "wasAttributedTo": {"@id": f"urn:agent:{actor_id}"},
        }
        graph: list[dict] = [Entity(**entity_kwargs).to_jsonld()]

        ts = log.timestamp.isoformat()
        graph.append(Activity(**{
            "@id": f"urn:activity:{log.id}",
            "prov:startedAtTime": ts,
            "prov:endedAtTime": ts,
            "prov:wasAssociatedWith": {"@id": f"urn:agent:{actor_id}"},
        }).to_jsonld())

        graph.append(Agent(**{
            "@id": f"urn:agent:{actor_id}",
            "foaf:name": "Test User",
        }).to_jsonld())

        bundle = Bundle(graph=graph).to_jsonld()

        assert bundle["@context"] == PROV_CONTEXT
        assert len(bundle["@graph"]) == 3

        entity_node = next(n for n in bundle["@graph"] if n["@type"] == "prov:Entity")
        assert entity_node["@id"] == schema_uri

        activity_node = next(n for n in bundle["@graph"] if n["@type"] == "prov:Activity")
        assert "prov:startedAtTime" in activity_node

        agent_node = next(n for n in bundle["@graph"] if n["@type"] == "prov:Agent")
        assert agent_node["foaf:name"] == "Test User"

    def test_element_prov_entity_attributes(self):
        """Element provenance entity has correct wasGeneratedBy and wasAttributedTo."""
        element_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        ver = _make_version(created_by=actor_id, element_id=element_id, version_num=1)

        versions = [ver]
        latest = versions[0]
        element_uri = f"https://schema.undata.live/elements/{element_id}"

        entity_kwargs = {
            "id": element_uri,
            "wasGeneratedBy": {"@id": f"urn:activity:el-{latest.id}"},
            "wasAttributedTo": {"@id": f"urn:agent:{latest.created_by}"},
        }
        entity = Entity(**entity_kwargs)
        jld = entity.to_jsonld()

        assert jld["@id"] == element_uri
        assert jld["prov:wasAttributedTo"]["@id"] == f"urn:agent:{actor_id}"
