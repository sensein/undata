"""Generate detailed architecture diagrams for undata presentation.

Creates:
1. 30,000ft overview (system-level)
2. Pipeline detail (extract→transform stages)
3. Library detail (modules + protocols)
4. Backend detail (services + GraphQL)
5. Frontend detail (pages + components)
6. Data layer detail (storage engines)
7. Entity model detail (types + lifecycle)
8. Enrichment detail (strategies + evidence chain)
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Shared design tokens
W, H = 1920, 1200
BG = (255, 255, 255)
TEXT = (30, 41, 59)
TEAL = (14, 116, 144)
AMBER = (180, 83, 9)
MUTED = (100, 116, 139)
CARD = (241, 245, 249)
GREEN = (21, 128, 61)
ORANGE = (194, 65, 12)
PURPLE = (126, 34, 206)
RED = (185, 28, 28)
LTEAL = (207, 250, 254)
LAMBER = (254, 243, 199)
LGREEN = (220, 252, 231)
LPURPLE = (243, 232, 255)
LRED = (254, 226, 226)
LORANGE = (255, 237, 213)

OUT = Path(__file__).parent / "diagrams"
OUT.mkdir(exist_ok=True)

def _font(size, bold=False):
    for name in ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNSDisplay.ttf"]:
        try:
            return ImageFont.truetype(name, size, index=1 if bold and name.endswith(".ttc") else 0)
        except (OSError, IndexError):
            pass
    return ImageFont.load_default(size=size)

F_TITLE = _font(32, True)
F_HEAD = _font(22, True)
F_SUB = _font(18, True)
F_BODY = _font(16)
F_SMALL = _font(13)
F_TINY = _font(11)

def new_diagram(title, subtitle=""):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 20), title, fill=TEAL, font=F_TITLE)
    d.rectangle([60, 58, 400, 61], fill=TEAL)
    if subtitle:
        d.text((60, 68), subtitle, fill=MUTED, font=F_BODY)
    return img, d

def box(d, x, y, w, h, title, items, color, bg=None):
    bg = bg or BG
    d.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=bg, outline=color, width=2)
    d.text((x+12, y+8), title, fill=color, font=F_SUB)
    cy = y + 35
    for item in items:
        d.text((x+12, cy), item, fill=TEXT, font=F_SMALL)
        cy += 18
    return cy

def arrow_h(d, x1, y, x2, color=MUTED):
    d.line([(x1, y), (x2-8, y)], fill=color, width=2)
    d.polygon([(x2-8, y-4), (x2, y), (x2-8, y+4)], fill=color)

def arrow_v(d, x, y1, y2, color=MUTED):
    d.line([(x, y1), (x, y2-8)], fill=color, width=2)
    d.polygon([(x-4, y2-8), (x, y2), (x+4, y2-8)], fill=color)

def label(d, x, y, text, color=MUTED, font=None):
    d.text((x, y), text, fill=color, font=font or F_SMALL)

# ============================================================
# 1. 30,000ft Overview
# ============================================================
img, d = new_diagram("undata: System Architecture (30,000ft)", "Three layers + pipeline + knowledge sources")

# Users
box(d, 60, 110, 250, 180, "USERS", [
    "Data Engineers", "Standards Developers",
    "Curators", "Contributors",
    "Researchers", "Tool Builders",
], MUTED, CARD)

arrow_h(d, 310, 200, 370, TEAL)

# Frontend
box(d, 370, 110, 360, 180, "FRONTEND", [
    "Next.js + Apollo Client",
    "Entity browser + search",
    "Curation queue + chat",
    "Detail pages + ER navigation",
    "Downloads + admin",
], TEAL, LTEAL)

arrow_h(d, 730, 200, 790, AMBER)
label(d, 740, 180, "GraphQL", TEAL, F_TINY)

# Backend
box(d, 790, 110, 360, 180, "BACKEND", [
    "FastAPI + Strawberry GraphQL",
    "Audit + Chat + Export services",
    "Version + Discovery services",
    "Keycloak OIDC (3 roles)",
    "PROV-O audit trail",
], AMBER, LAMBER)

arrow_h(d, 1150, 200, 1210, GREEN)
label(d, 1155, 180, "StorageBackend", GREEN, F_TINY)

# Library
box(d, 1210, 110, 360, 180, "LIBRARY", [
    "Pure Python engine (no DB deps)",
    "Extract → Enrich → Align",
    "→ Commit → Transform",
    "8 source adapters",
    "436 tests • Python 3.14",
], GREEN, LGREEN)

# Ontology store
box(d, 1610, 110, 280, 180, "KNOWLEDGE", [
    "pyoxigraph RDF store",
    "13 ontologies (2.99M terms)",
    "268K embedded terms",
    "sentence-transformers",
    "litellm (LLM abstraction)",
], PURPLE, LPURPLE)

# Data stores row
arrow_v(d, 550, 290, 340, TEAL)
arrow_v(d, 970, 290, 340, AMBER)
arrow_v(d, 1390, 290, 340, GREEN)

box(d, 60, 340, 360, 140, "PostgreSQL 16", [
    "JSONB entities + provenance",
    "pgvector (384-dim embeddings)",
    "tsvector full-text search",
    "Audit log + releases",
], TEAL, LTEAL)

box(d, 460, 340, 350, 140, "pyoxigraph Store", [
    "RDF triples + SPARQL",
    "Named graphs per ontology",
    "Checksum-based dedup",
    "Metadata in dedicated graph",
], GREEN, LGREEN)

box(d, 850, 340, 350, 140, "File Backend", [
    "YAML entity files",
    "Parquet embeddings",
    "JSON LLM cache",
    "YAML curation flags",
], PURPLE, LPURPLE)

box(d, 1240, 340, 350, 140, "Keycloak", [
    "OIDC identity provider",
    "Contributor → Curator → Admin",
    "JWT token validation",
    "Per-mutation role checks",
], ORANGE, LORANGE)

# Pipeline
d.rounded_rectangle([60, 530, 1860, 720], radius=14, fill=CARD, outline=TEAL, width=2)
d.text((80, 540), "PIPELINE", fill=TEAL, font=F_HEAD)

stages = [
    ("Extract", "8 adapters → LinkML\n→ ClassifiedEntity", TEAL, 80),
    ("Enrich", "Embeddings + LLM\nSKOS annotations\nEvidence chains", GREEN, 420),
    ("Align", "Cross-source aliases\nAnnotation transfer\nGap detection", AMBER, 760),
    ("Commit", "SHA-256 hashing\nTwo-mode identity\nDedup + merge prov", PURPLE, 1100),
    ("Transform", "3 strategies:\nURI + Name + Embed\nMany-to-one", ORANGE, 1440),
]
for name, desc, color, x in stages:
    box(d, x, 575, 300, 120, name, desc.split("\n"), color)
    if x < 1440:
        arrow_h(d, x+300, 635, x+340, color)

# Sources
d.rounded_rectangle([60, 770, 1860, 930], radius=14, fill=CARD, outline=MUTED, width=2)
d.text((80, 780), "SOURCES", fill=MUTED, font=F_HEAD)
sources = [
    ("BIDS", "JSON Schema • 585 elem"),
    ("NWB", "Python/hdmf • 179 elem"),
    ("DANDI", "Pydantic • 398 elem"),
    ("openMINDS", "JSON-LD • 473 elem"),
    ("AIND", "JSON Schema • 556 elem"),
    ("OpenNeuro", "datalad/TSV • 28 elem"),
    ("ReproSchema", "JSON-LD • 4,836 elem"),
    ("NDA", "REST API • new"),
]
for i, (name, desc) in enumerate(sources):
    x = 80 + i * 220
    box(d, x, 810, 200, 100, name, desc.split(" • "), TEAL)

arrow_v(d, 960, 720, 770, MUTED)

# Ontologies
d.text((60, 960), "Ontologies:", fill=MUTED, font=F_SUB)
d.text((180, 960), "NCIT (209K) • PATO (2.8K) • NCBITaxon (20 spp filtered) • UBERON • HP • DICOM (5K) • RadLex (46K) • NIDM • HoMBA • EDAM", fill=TEXT, font=F_SMALL)
d.text((60, 985), "Knowledge:", fill=MUTED, font=F_SUB)
d.text((180, 985), "Cognitive Atlas • InterLex • NIH CDE • CDISC • FHIR • schema.org • QUDT units • CivicDB (curation model)", fill=TEXT, font=F_SMALL)

# Entity counts
d.rounded_rectangle([60, 1020, 1860, 1080], radius=10, fill=LTEAL, outline=TEAL, width=1)
d.text((80, 1035), "REGISTRY:", fill=TEAL, font=F_SUB)
d.text((220, 1035), "7,055 elements  •  1,005 schemas  •  15,881 values  •  2,426 valuesets  •  15 transforms  •  7 sources  •  14,984 curation flags", fill=TEXT, font=F_BODY)

# Speckit process
d.text((60, 1110), "Process:", fill=MUTED, font=F_SUB)
d.text((150, 1110), "speckit lifecycle: /specify → /clarify → /plan → /tasks → /analyze → /implement  •  38 features  •  Constitution v2.1.0 (7 principles)", fill=TEXT, font=F_SMALL)
d.text((60, 1135), "Testing:", fill=MUTED, font=F_SUB)
d.text((150, 1135), "436 library tests  •  16 transform tests  •  9 CI workflows  •  0 TypeScript errors  •  ruff lint + format", fill=TEXT, font=F_SMALL)
d.text((60, 1160), "Deploy:", fill=MUTED, font=F_SUB)
d.text((150, 1160), "docker compose up -d → everything running  •  Curated seed (70 elem, 7 sources)  •  Full registry at ~/.cache/undata/", fill=TEXT, font=F_SMALL)

img.save(str(OUT / "01_overview_30k.png"), quality=95)
print(f"  01_overview_30k.png")


# ============================================================
# 2. Pipeline Detail
# ============================================================
img, d = new_diagram("Pipeline Architecture (2,000ft)", "extract → enrich → align → commit → transform")

# Extract
box(d, 60, 100, 340, 480, "EXTRACT", [
    "BaseAdapter protocol:",
    "  extract(path) → [ClassifiedEntity]",
    "  to_linkml(path) → SchemaDefinition",
    "",
    "8 Registered Adapters:",
    "• BIDS — LinkML-first, JSON Schema",
    "• NWB — bridge venv (Python 3.12)",
    "• DANDI — Pydantic introspection",
    "• openMINDS — JSON-LD → LinkML",
    "• AIND — JSON Schema + $ref",
    "• OpenNeuro — datalad API + TSV",
    "• ReproSchema — JSON-LD + rel refs",
    "• NDA — REST API + value ranges",
    "",
    "Output: ClassifiedEntity",
    "  entity_type: CLASS|ATTRIBUTE|",
    "    ENUM_VALUE|VALUESET",
    "  semantic: dict (content)",
    "  provenance: dict (origin)",
    "  confidence: float",
    "  source_ref: SourceRef",
], TEAL, LTEAL)

arrow_h(d, 400, 340, 440, TEAL)

# Enrich
box(d, 440, 100, 340, 480, "ENRICH", [
    "Embedding Similarity:",
    "  all-MiniLM-L6-v2 (384-dim)",
    "  268K ontology terms indexed",
    "  cosine similarity threshold: 0.7",
    "",
    "SKOS Mapping Relations:",
    "  ≥0.95 → exactMatch",
    "  ≥0.85 → closeMatch",
    "  ≥0.70 → relatedMatch",
    "  hierarchy → broadMatch",
    "",
    "LLM Verification:",
    "  Borderline (0.5–0.7) → litellm",
    "  gpt-5.4-nano: 0.06s/pair",
    "  ollama/qwen3.5: 0.5s/pair",
    "  Batch 30, disk cache",
    "",
    "Evidence Chain:",
    "  score + URI verified + reasoning",
    "  Curated annotations protected",
], GREEN, LGREEN)

arrow_h(d, 780, 340, 820, GREEN)

# Align
box(d, 820, 100, 340, 480, "ALIGN", [
    "Cross-Source Alias Detection:",
    "  Embedding similarity between",
    "  elements from different sources",
    "",
    "Annotation Transfer:",
    "  Well-annotated → under-annotated",
    "  within alias groups",
    "",
    "Alias Groups:",
    "  Deduplicated by semantic hash",
    "  Report generated with scores",
    "",
    "Gap Detection:",
    "  Track ontology misses",
    "  Surface actionable needs",
    "",
    "Alignment Report:",
    "  Per-source pair summary",
    "  Candidate matches with scores",
], AMBER, LAMBER)

arrow_h(d, 1160, 340, 1200, AMBER)

# Commit
box(d, 1200, 100, 320, 480, "COMMIT", [
    "Content Addressing:",
    "  SHA-256 from semantic content",
    "",
    "Two-Mode Hashing:",
    "  Mode 1: Ontology-anchored",
    "    hash(type+unit+pattern+",
    "         constraints+ontology_uri)",
    "",
    "  Mode 2: Structural fallback",
    "    hash(type+unit+pattern+",
    "         class+attr+description)",
    "",
    "Deduplication:",
    "  Same hash → merge provenance",
    "  Short key: 12 hex chars",
    "",
    "Cross-References:",
    "  Schema props → element sha256",
    "  ValueSet members → value sha256",
    "  Class-aware (class,name)→sha",
], PURPLE, LPURPLE)

arrow_h(d, 1520, 340, 1560, PURPLE)

# Transform
box(d, 1560, 100, 300, 480, "TRANSFORM", [
    "Strategy 1: Shared Ontology URI",
    "  Same primary annotation",
    "  Original: 15 transforms",
    "",
    "Strategy 2: Name Matching",
    "  Case-insensitive prov name",
    "  Cross-source only",
    "  100+ transforms",
    "",
    "Strategy 3: Embedding Sim",
    "  Cosine > 0.8, cross-source",
    "  Capped at 500 pairs",
    "",
    "Detection Patterns:",
    "  identity, unit_conversion,",
    "  type_conversion, scaling,",
    "  value_mapping, structural",
    "",
    "Many-to-one:",
    "  source_elements[] field",
], ORANGE, LORANGE)

# Curation flags below
d.rounded_rectangle([60, 620, 1860, 730], radius=12, fill=CARD, outline=RED, width=1)
d.text((80, 630), "CURATION FLAGS", fill=RED, font=F_HEAD)
flags = ["ambiguous_match", "multiple_candidates", "needs_review", "suspicious_source",
         "provenance_bloat", "unresolved_unit", "unit_encoded_string", "unknown_transform"]
for i, f in enumerate(flags):
    x = 80 + i * 220
    d.text((x, 665), f"• {f}", fill=TEXT, font=F_SMALL)
d.text((80, 695), "14,984 flags tracked  •  Deduped by (entity_ref, flag_type)  •  Status: pending → approved | rejected | deferred", fill=MUTED, font=F_SMALL)

# NCBITaxon note
d.text((60, 760), "NCBITaxon Filter: 2.7M terms → 20 neuroscience-relevant species (human, mouse, rat, macaque, zebrafish, fly, worm, ...)", fill=MUTED, font=F_SMALL)
d.text((60, 785), "Index Staleness: ontology store checksum compared to embedding index checksum → auto-rebuild if stale", fill=MUTED, font=F_SMALL)

img.save(str(OUT / "02_pipeline_2k.png"), quality=95)
print(f"  02_pipeline_2k.png")


# ============================================================
# 3. Backend Detail
# ============================================================
img, d = new_diagram("Backend Architecture (2,000ft)", "FastAPI + Strawberry GraphQL + PostgreSQL 16")

# GraphQL Schema
box(d, 60, 100, 500, 500, "GRAPHQL SCHEMA", [
    "Queries:",
    "  element(sha256) → Element",
    "  browseElements(source, sort, search, first, after)",
    "  browseSchemas(source, sortBy, sortOrder, first, after)",
    "  browseValues(source, sortBy, sortOrder, first, after)",
    "  browseValuesets(source, sortBy, sortOrder, first, after)",
    "  browseTransforms(source, target, function_type)",
    "  search(query, mode: LEXICAL|SEMANTIC|BOTH, first)",
    "  curationQueue(flagType, status, first, after)",
    "  flagsForEntity(entityType, entityRef)",
    "  schemasUsingElement(sha256)",
    "  transformsForElement(sha256)",
    "  ontologyStoreInfo → OntologyStoreEntry[]",
    "  auditLog(entity, agent, activity, first)",
    "  enrichmentProposals(entity, status)",
    "  releases(releaseType)",
    "",
    "Mutations:",
    "  resolveFlag / batchResolveFlags",
    "  updateElement / updateSchema / updateValue",
    "  approveAnnotation / rejectAnnotation",
    "  versionElement(sha256, changes)",
    "  approveIngestion / rejectIngestion",
    "  reviewProposal / requestEnrichment",
    "  importRegistry / exportRegistry",
    "  checkDependencyVersions / tagRelease",
], TEAL, LTEAL)

arrow_h(d, 560, 350, 600, TEAL)

# Services
box(d, 600, 100, 400, 500, "SERVICES", [
    "audit_service.py:",
    "  write_audit(activity, agent, entity_type,",
    "    entity_ref, details) → AuditLog",
    "  Wired into ALL mutations",
    "",
    "chat_service.py:",
    "  chat_completion(messages, entity_context)",
    "  SSE streaming, tool execution",
    "  Configurable model (litellm)",
    "  Auto-suggest on entity load",
    "",
    "export_service.py:",
    "  export_full_registry(session, dir, version)",
    "  YAML entities + Parquet + manifest",
    "",
    "nightly_export.py:",
    "  Background asyncio task (daily)",
    "  Creates Release records",
    "",
    "version_service.py:",
    "  check_dependency_versions(session)",
    "  Checksum comparison → re-enrich",
    "",
    "discovery_service.py:",
    "  Poll OpenNeuro/DANDI APIs daily",
    "  Auto-approve known sources",
], AMBER, LAMBER)

arrow_h(d, 1000, 350, 1040, AMBER)

# DB Models
box(d, 1040, 100, 400, 500, "DB MODELS (SQLAlchemy)", [
    "Element: sha256, semantic{}, provenance[],",
    "  annotations[], curated_annotations[],",
    "  superseded_by, embedding(384), search_tsv",
    "",
    "Schema: sha256, properties[], subclass_of",
    "Value: sha256, label, value_type",
    "ValueSet: sha256, name, members[]",
    "",
    "Transform: sha256, source_element,",
    "  target_element, source_elements[],",
    "  function_type, expression",
    "",
    "CurationFlag: entity_type, entity_ref,",
    "  flag_type, context{}, status",
    "",
    "AuditLog: activity, agent, agent_type,",
    "  entity_type, entity_ref, details{}",
    "",
    "LLMEnrichmentProposal: proposed_value{},",
    "  reasoning, confidence, evidence{}",
    "",
    "Release: version, file_path, file_size",
    "OntologySource: name, url, term_count",
    "IngestionJob: status, entity_counts{}",
], GREEN, LGREEN)

# Auth
box(d, 1480, 100, 360, 220, "AUTHENTICATION", [
    "Keycloak OIDC",
    "JWT token validation",
    "Role hierarchy:",
    "  viewer → contributor → curator → admin",
    "",
    "Per-mutation enforcement:",
    "  _require_auth(info, 'curator')",
    "  Override agent from JWT",
], ORANGE, LORANGE)

# Infra
box(d, 1480, 350, 360, 250, "INFRASTRUCTURE", [
    "main.py:",
    "  Lifespan: create_all + nightly task",
    "  CORS middleware",
    "  /api/chat SSE endpoint",
    "  /api/downloads/ static files",
    "  /graphql mount",
    "",
    "Relay-style cursor pagination",
    "Apollo paginationMerge (dedup)",
    "JSONB source filter (@>)",
], PURPLE, LPURPLE)

img.save(str(OUT / "03_backend_2k.png"), quality=95)
print(f"  03_backend_2k.png")


# ============================================================
# 4. Frontend Detail
# ============================================================
img, d = new_diagram("Frontend Architecture (2,000ft)", "Next.js + Apollo Client + Tailwind CSS")

# Pages
box(d, 60, 100, 500, 550, "PAGES (app/)", [
    "/elements — Browse with sort, filter, search, scroll",
    "/elements/[id] — Detail: semantic + provenance + annotations",
    "/schemas — Browse schemas with sort + filter",
    "/schemas/[id] — Properties → element EntityTags",
    "/values — Browse values with sort + filter",
    "/valuesets — Browse valuesets, members → value links",
    "/transforms — Browse transforms, source/target links",
    "/sources — Source cards with entity counts",
    "/sources/[name] — Source detail with entity grid",
    "/search — Lexical | Semantic | Both mode toggle",
    "/curation — Queue with inline detail expansion",
    "/curation/chat — LLM assistant + entity context",
    "/activity — Activity feed",
    "/downloads — Nightly exports + versioned releases",
    "/admin/ontologies — pyoxigraph store + DB sources",
    "/admin/ingestion — Ingestion job queue",
    "/runs — Pipeline run summaries",
    "",
    "All pages:",
    "  Server-side sorting (sortBy/sortOrder)",
    "  Infinite scroll (IntersectionObserver)",
    "  Source filtering (provenance @> jsonb)",
    "  Cross-entity search",
], TEAL, LTEAL)

# Components
box(d, 600, 100, 460, 550, "COMPONENTS", [
    "EntityDataGrid — TanStack table + infinite scroll",
    "  onSortChange → server re-fetch",
    "  InfiniteScrollSentinel (200px rootMargin)",
    "  Case-insensitive sort, compact rows",
    "",
    "EntityDetailLayout — Consistent detail page",
    "  AnnotationChip (SKOS icon + score + evidence)",
    "  ProvenanceBadgeStrip (source badges, expandable)",
    "  Tabs: summary | flags | activity",
    "",
    "EvidenceChain — Evidence display component",
    "  ScoreBadge (green/yellow/red by threshold)",
    "  UriBadge (verified ✓ or unverified ?)",
    "  Expandable reasoning text",
    "",
    "ChatPanel — LLM curation assistant",
    "  SSE streaming, tool execution display",
    "  Auto-suggest on entity load",
    "",
    "EntityInlineDetail — Compact entity preview",
    "EntityTag — Sha256 → name chip with link",
    "PropertyTable — Schema props as EntityTags",
    "SourceBadge — Color-coded source indicator",
    "SearchBar — Global search with mode toggle",
    "Sidebar — Navigation with 6 groups",
    "EvidencePanel — Flag context display",
    "FilterPanel — Source + type + annotation filters",
], AMBER, LAMBER)

# GraphQL
box(d, 1100, 100, 400, 550, "GRAPHQL LAYER", [
    "queries.ts:",
    "  SEARCH (mode: SearchMode)",
    "  BROWSE_ELEMENTS (sortBy, sortOrder)",
    "  BROWSE_SCHEMAS (sortBy, sortOrder)",
    "  BROWSE_VALUES (sortBy, sortOrder)",
    "  BROWSE_VALUESETS (sortBy, sortOrder)",
    "  GET_ELEMENT / GET_SCHEMA / etc.",
    "  FLAGS_FOR_ENTITY",
    "  CURATION_QUEUE",
    "",
    "types.ts:",
    "  OntologyAnnotation + EvidenceChainData",
    "  ElementNode, SchemaNode, ValueNode",
    "  CurationFlagNode, SearchResult",
    "",
    "lib/apollo.ts:",
    "  paginationMerge (dedup by cursor)",
    "  keyArgs: [source, sortBy, sortOrder]",
    "  Removed 'first' from keyArgs",
    "",
    "lib/chat-api.ts:",
    "  streamChat(messages, entityContext)",
    "  SSE event parsing",
    "",
    "lib/source-colors.ts:",
    "  getEntityColor(source) → color",
], GREEN, LGREEN)

# Auth
box(d, 1540, 100, 320, 250, "AUTH (AuthProvider)", [
    "Keycloak OIDC integration",
    "useAuth() hook",
    "Role-based UI rendering",
    "Token injection in GraphQL",
    "",
    "Roles visible in UI:",
    "  Curator: resolve buttons",
    "  Admin: import/export/manage",
], PURPLE, LPURPLE)

# Tech stack
box(d, 1540, 380, 320, 270, "TECH STACK", [
    "Next.js 15 (App Router)",
    "Apollo Client 3 (React)",
    "TanStack Table v8",
    "Tailwind CSS",
    "TypeScript strict mode",
    "eslint + prettier",
    "",
    "0 non-test TS errors",
    "Responsive sidebar",
    "Dark mode not yet",
], ORANGE, LORANGE)

img.save(str(OUT / "04_frontend_2k.png"), quality=95)
print(f"  04_frontend_2k.png")


# ============================================================
# 5. Entity Model Detail
# ============================================================
img, d = new_diagram("Entity Model & Lifecycle (2,000ft)", "Content-addressed, provenance-rich, curation-gated")

# Element
box(d, 60, 100, 420, 500, "ELEMENT (rdf:Property)", [
    "SemanticIdentity:",
    "  data_type: DataType enum",
    "  unit: str | None (e.g., 'year')",
    "  unit_uri: str | None (QUDT URI)",
    "  pattern: str | None (regex)",
    "  response_options: [ResponseOption]",
    "  question_text: str | None",
    "  value_domain: str | None",
    "  min_value / max_value: float",
    "  type_ref: str | None (→ Schema)",
    "  description: str (fallback hash only)",
    "  ontology_annotations: [OntologyAnnotation]",
    "",
    "OntologyAnnotation:",
    "  term_uri, term_label, ontology",
    "  mapping_relation (SKOS)",
    "  match_level, score, model, primary",
    "  evidence: EvidenceChain | None",
    "",
    "ProvenanceEntry (W3C PROV-O):",
    "  source, class, name, description",
    "  generated_at, attributed_to",
    "  activity, derived_from, source_ref",
], TEAL, LTEAL)

# Schema
box(d, 520, 100, 350, 250, "SCHEMA (sh:NodeShape)", [
    "SchemaIdentity:",
    "  properties: [str] (element sha256s)",
    "  subclass_of: str | None",
    "  mixins: [str]",
    "  description: str",
    "  ontology_annotations: [...]",
    "",
    "Cross-references:",
    "  properties resolved at commit",
    "  (class, name) → sha256 lookup",
], AMBER, LAMBER)

# Value
box(d, 520, 380, 350, 220, "VALUE (enum_value)", [
    "ValueSemanticIdentity:",
    "  value_type: 'categorical'",
    "  label: str",
    "  description: str | None",
    "  ontology_annotations: [...]",
    "",
    "Used for: M/F, left/right,",
    "  MRI/fMRI/EEG, etc.",
], GREEN, LGREEN)

# ValueSet
box(d, 910, 100, 350, 250, "VALUESET (collection)", [
    "ValueSetIdentity:",
    "  name: str",
    "  members: [str] (value sha256s)",
    "  description: str | None",
    "  ontology_annotations: [...]",
    "",
    "Groups enum values:",
    "  handedness_options",
    "  modality_types",
], PURPLE, LPURPLE)

# Transform
box(d, 910, 380, 350, 220, "TRANSFORM", [
    "TransformRecord:",
    "  source_element: str (sha256)",
    "  target_element: str (sha256)",
    "  source_elements: [str] (many→one)",
    "  function: FunctionSpec",
    "    type, expression, params",
    "  confidence, sssom_predicate",
], ORANGE, LORANGE)

# EvidenceChain
box(d, 1300, 100, 520, 260, "EVIDENCE CHAIN", [
    "similarity_score: float (0.0–1.0)",
    "similarity_method: 'cosine_embedding' | 'exact_name' | 'llm_reasoning'",
    "source_text: str (element name + description)",
    "target_term_uri: str (ontology term URI)",
    "target_term_label: str",
    "target_term_definition: str | None",
    "uri_verified: bool (HTTP HEAD check)",
    "reasoning: str (step-by-step explanation)",
    "",
    "Embedded in: OntologyAnnotation.evidence, LLMEnrichmentProposal.evidence",
], RED, LRED)

# Lifecycle
box(d, 1300, 390, 520, 210, "ENTITY LIFECYCLE", [
    "staged → curated (through review)",
    "",
    "Curator actions:",
    "  approveAnnotation → curated_annotations[]",
    "  rejectAnnotation → removed + provenance entry",
    "  versionElement → new sha256, superseded_by link",
    "  resolveFlag → approved | rejected | deferred",
], GREEN, LGREEN)

# Hashing
box(d, 60, 640, 900, 180, "CONTENT-ADDRESSED HASHING", [
    "Mode 1 — Ontology-Anchored:   hash(data_type + unit + pattern + min/max + response_options + type_ref + primary_ontology_uri)",
    "Mode 2 — Structural Fallback:  hash(data_type + unit + pattern + min/max + response_options + type_ref + class + attribute + description)",
    "",
    "Fields NOT in hash: question_text, value_domain, ontology_annotations (enrichment metadata)",
    "Short key: first 12 hex chars of SHA-256 (sufficient for current 7K+ element scale)",
    "Cross-source merge: same hash → merge provenance arrays, not duplicate entities",
], TEAL, LTEAL)

# Audit
box(d, 1000, 640, 820, 180, "AUDIT LOG (PROV-O)", [
    "AuditLog:  activity, agent, agent_type, entity_type, entity_ref, generated_entity_ref, details{}, timestamp",
    "",
    "Activities: flag_approved, flag_rejected, approve_annotation, reject_annotation,",
    "  update, version, approve_ingestion, reject_ingestion, proposal_approved, import",
    "",
    "Queryable: by entity_type, entity_ref, agent, activity, time range",
    "14,984 flags  •  All mutations audited  •  PROV-O compliant",
], RED, LRED)

img.save(str(OUT / "05_entity_model_2k.png"), quality=95)
print(f"  05_entity_model_2k.png")

print(f"\nDone! Generated 5 diagrams in {OUT}")
