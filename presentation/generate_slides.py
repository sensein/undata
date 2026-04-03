"""Generate undata presentation slides using PIL.

Creates a 40-slide deck telling the complete undata story.
Style: Dark navy background, white text, teal/gold accents.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap

W, H = 1920, 1080
BG = (15, 23, 42)           # Dark navy
TEXT = (255, 255, 255)       # White
ACCENT = (56, 189, 248)     # Teal/cyan
ACCENT2 = (250, 204, 21)    # Gold
MUTED = (148, 163, 184)     # Slate gray
DARK_CARD = (30, 41, 59)    # Card background
SUCCESS = (34, 197, 94)     # Green
WARN = (251, 146, 60)       # Orange

SLIDES_DIR = Path(__file__).parent / "slides"
SLIDES_DIR.mkdir(exist_ok=True)

# Try to load fonts
def _font(size, bold=False):
    for name in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]:
        try:
            return ImageFont.truetype(name, size, index=1 if bold and name.endswith(".ttc") else 0)
        except (OSError, IndexError):
            pass
    return ImageFont.load_default(size=size)

FONT_TITLE = _font(54, bold=True)
FONT_SUBTITLE = _font(36)
FONT_BODY = _font(28)
FONT_SMALL = _font(22)
FONT_TINY = _font(18)
FONT_BIG = _font(72, bold=True)
FONT_HUGE = _font(96, bold=True)
FONT_LABEL = _font(24, bold=True)

def new_slide():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Bottom accent bar
    draw.rectangle([0, H-4, W, H], fill=ACCENT)
    return img, draw

def draw_title(draw, text, y=60, color=TEXT, font=None):
    font = font or FONT_TITLE
    draw.text((100, y), text, fill=color, font=font)
    # Underline
    bbox = draw.textbbox((100, y), text, font=font)
    draw.rectangle([100, bbox[3]+8, bbox[2], bbox[3]+12], fill=ACCENT)
    return bbox[3] + 30

def draw_bullets(draw, items, x=120, y=200, color=TEXT, font=None, spacing=50, bullet_color=None):
    font = font or FONT_BODY
    bullet_color = bullet_color or ACCENT
    for item in items:
        draw.ellipse([x, y+10, x+10, y+20], fill=bullet_color)
        lines = textwrap.wrap(item, width=70)
        for i, line in enumerate(lines):
            draw.text((x + 30, y + i * (font.size + 6)), line, fill=color, font=font)
        y += len(lines) * (font.size + 6) + spacing - (font.size + 6)
    return y

def draw_card(draw, x, y, w, h, title, items, accent=ACCENT):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=12, fill=DARK_CARD, outline=accent, width=2)
    draw.text((x+20, y+15), title, fill=accent, font=FONT_LABEL)
    cy = y + 55
    for item in items:
        lines = textwrap.wrap(item, width=int(w/14))
        for line in lines:
            draw.text((x+20, cy), line, fill=MUTED, font=FONT_SMALL)
            cy += 28
        cy += 4
    return cy

def draw_stat(draw, x, y, number, label, color=ACCENT):
    draw.text((x, y), str(number), fill=color, font=FONT_BIG)
    bbox = draw.textbbox((x, y), str(number), font=FONT_BIG)
    draw.text((x, bbox[3]+5), label, fill=MUTED, font=FONT_SMALL)

def save(img, num, name):
    path = SLIDES_DIR / f"{num:02d}_{name}.png"
    img.save(str(path), quality=95)
    print(f"  {path.name}")

# ============================================================
# SLIDE GENERATION
# ============================================================

print("Generating slides...")

# --- SECTION 1: OPENING ---

# Slide 1: Title
img, d = new_slide()
d.text((100, 250), "undata", fill=ACCENT, font=FONT_HUGE)
d.text((100, 370), "A Universal Data Element Registry", fill=TEXT, font=FONT_TITLE)
d.text((100, 440), "for Neuroscience", fill=TEXT, font=FONT_TITLE)
d.rectangle([100, 520, 500, 524], fill=ACCENT2)
d.text((100, 560), "Building a shared language for neuroscience data schemas", fill=MUTED, font=FONT_SUBTITLE)
d.text((100, 680), "Satrajit Ghosh", fill=TEXT, font=FONT_BODY)
d.text((100, 720), "MIT  |  2026", fill=MUTED, font=FONT_SMALL)
save(img, 1, "title")

# Slide 2: The Problem — Opening Hook
img, d = new_slide()
d.text((W//2 - 400, 200), "Neuroscience has", fill=MUTED, font=FONT_TITLE)
d.text((W//2 - 400, 280), "no shared language", fill=ACCENT2, font=FONT_HUGE)
d.text((W//2 - 400, 410), "for data elements.", fill=MUTED, font=FONT_TITLE)
d.text((100, 600), "5 major ecosystems  ×  5 different formats  ×  0 interoperability", fill=TEXT, font=FONT_SUBTITLE)
d.text((100, 700), "BIDS  •  NWB  •  DANDI  •  openMINDS  •  AIND", fill=ACCENT, font=FONT_BODY)
save(img, 2, "problem_hook")

# Slide 3: Three Core Problems
img, d = new_slide()
y = draw_title(d, "Three Problems Nobody Has Solved")
draw_card(d, 80, y, 540, 260, "1  SCHEMA FRAGMENTATION", [
    "Same concept, different formats",
    "JSON Schema, YAML, LinkML, Python, JSON-LD",
    'No way to ask: "What does BIDS call',
    'the thing NWB calls ElectrodeArray?"',
], ACCENT)
draw_card(d, 680, y, 540, 260, "2  IDENTITY CONFLATION", [
    "What something IS ≠ where it came from",
    "'age' in BIDS and 'age' in AIND are",
    "treated as different things despite",
    "being semantically identical",
], ACCENT2)
draw_card(d, 1280, y, 540, 260, "3  INVISIBLE TRANSFORMS", [
    "Silent data transformations",
    "Unit conversions, type coercions",
    "happen in ad-hoc scripts",
    "Breaking reproducibility",
], WARN)
d.text((100, y+310), "These problems scale with every new dataset, standard, and ecosystem.", fill=MUTED, font=FONT_BODY)
save(img, 3, "three_problems")

# Slide 4: Impact
img, d = new_slide()
y = draw_title(d, "Why This Matters")
draw_bullets(d, [
    "Researchers waste weeks mapping between formats manually",
    "Cross-ecosystem analyses require heroic bespoke engineering",
    "Transformations are undocumented → results not reproducible",
    "New standards fragment the landscape further",
    "No machine-readable crosswalk between any two ecosystems",
], y=y+20)
d.text((100, 700), "The cost compounds with every dataset, every study, every collaboration.", fill=ACCENT2, font=FONT_SMALL)
save(img, 4, "impact")

# Slide 5: Three Innovations
img, d = new_slide()
y = draw_title(d, "Three Core Innovations")
draw_card(d, 80, y, 540, 300, "CONTENT-ADDRESSED IDENTITY", [
    "SHA-256 hash from semantic properties",
    "(data type, unit, pattern, constraints,",
    "ontology grounding)",
    "",
    "Two elements from different sources",
    "describing the same concept →",
    "same hash automatically",
], SUCCESS)
draw_card(d, 680, y, 540, 300, "IDENTITY ≠ PROVENANCE", [
    "An element's identity (what it IS)",
    "is separate from provenance",
    "(where it came FROM)",
    "",
    "A single element accumulates",
    "provenance from multiple sources",
    "instead of duplicating",
], ACCENT)
draw_card(d, 1280, y, 540, 300, "EXPLICIT TRANSFORMS", [
    "Every conversion documented:",
    "• Unit conversion (years → months)",
    "• Type coercion (float → string)",
    "• Value mapping (M/F → male/female)",
    "",
    "Content-addressed with their own",
    "provenance chains",
], ACCENT2)
save(img, 5, "three_innovations")

# --- SECTION 2: ARCHITECTURE ---

# Slide 6: Pipeline Overview
img, d = new_slide()
y = draw_title(d, "The undata Pipeline")
# Draw pipeline stages as connected boxes
stages = [
    ("Extract", "Source adapters\n→ LinkML → entities", ACCENT),
    ("Enrich", "Embedding similarity\n+ LLM verification", SUCCESS),
    ("Align", "Cross-source\nalias detection", ACCENT2),
    ("Commit", "Content addressing\n+ dedup + merge", WARN),
    ("Transform", "Conversion logic\ngeneration", (168, 85, 247)),
]
bx = 80
for i, (name, desc, color) in enumerate(stages):
    w = 320
    d.rounded_rectangle([bx, 200, bx+w, 380], radius=12, fill=DARK_CARD, outline=color, width=3)
    d.text((bx+20, 215), name, fill=color, font=FONT_LABEL)
    for j, line in enumerate(desc.split("\n")):
        d.text((bx+20, 260+j*30), line, fill=MUTED, font=FONT_SMALL)
    if i < len(stages) - 1:
        d.text((bx+w+10, 270), "→", fill=MUTED, font=FONT_TITLE)
    bx += w + 40

# Source schemas at left
d.text((80, 420), "Sources:", fill=MUTED, font=FONT_LABEL)
sources = ["BIDS (JSON Schema)", "NWB (Python/hdmf)", "DANDI (Pydantic)", "openMINDS (JSON-LD)", "AIND (JSON Schema)", "OpenNeuro (TSV/BIDS)", "ReproSchema (JSON-LD)", "NDA (REST API)"]
for i, s in enumerate(sources):
    col = i % 4
    row = i // 4
    d.text((80 + col*440, 460 + row*35), f"• {s}", fill=TEXT, font=FONT_SMALL)

# Knowledge service
d.text((80, 560), "Knowledge Service:", fill=MUTED, font=FONT_LABEL)
ontos = "NCIT (209K) • PATO (2.8K) • NCBITaxon (2.7M) • UBERON • HP • DICOM (5K) • RadLex (46K) • NIDM • EDAM"
d.text((80, 600), ontos, fill=ACCENT, font=FONT_SMALL)
d.text((80, 640), "13 ontologies  •  2.99M terms  •  268K embedded  •  pyoxigraph RDF store", fill=MUTED, font=FONT_SMALL)
save(img, 6, "pipeline")

# Slide 7: Three-Layer Architecture
img, d = new_slide()
y = draw_title(d, "Three-Layer Architecture")
# Frontend
draw_card(d, 80, y, 540, 220, "FRONTEND — Next.js", [
    "Apollo Client + Tailwind CSS",
    "Browse, search, curation, chat",
    "Entity navigator (ER diagram)",
    "Infinite scroll + server-side sort",
    "Real-time LLM curation assistant",
], ACCENT)
# Backend
draw_card(d, 680, y, 540, 220, "BACKEND — FastAPI", [
    "Strawberry GraphQL + PostgreSQL 16",
    "pgvector for embeddings",
    "JSONB for flexible entity storage",
    "Keycloak OIDC authentication",
    "PROV-O audit trail for all mutations",
], ACCENT2)
# Library
draw_card(d, 1280, y, 540, 220, "LIBRARY — Pure Python", [
    "No DB dependencies, standalone CLI",
    "All pipeline logic: extract → transform",
    "StorageBackend protocol (file or DB)",
    "436 tests, Python 3.14",
    "uv for dependency management",
], SUCCESS)
# Protocol
d.text((100, y+260), "StorageBackend Protocol:", fill=ACCENT, font=FONT_LABEL)
d.text((100, y+300), "read() • write() • list() • exists() • delete() • merge_provenance() • count()", fill=TEXT, font=FONT_BODY)
d.text((100, y+350), "Two implementations: FileBackend (YAML + Parquet + pyoxigraph)  |  DatabaseBackend (PostgreSQL + pgvector)", fill=MUTED, font=FONT_SMALL)
save(img, 7, "architecture")

# Slide 8: Entity Model
img, d = new_slide()
y = draw_title(d, "Content-Addressed Entity Model")
# Draw entity types
types = [
    ("Element", "Field-level definition\nage, weight, diagnosis\ntype, unit, constraints", ACCENT, ["sha256", "semantic{}", "provenance[]", "annotations[]"]),
    ("Schema", "Class-level definition\nSubject, Session, Electrode\nproperties, inheritance", ACCENT2, ["sha256", "properties[]", "subclass_of", "provenance[]"]),
    ("Value", "Categorical concept\nmale, right-handed, MRI\nontology grounding", SUCCESS, ["sha256", "label", "value_type", "provenance[]"]),
    ("ValueSet", "Named collection\nhandedness_options\nmodality_types", WARN, ["sha256", "name", "members[]", "provenance[]"]),
]
bx = 80
for name, desc, color, fields in types:
    w = 420
    d.rounded_rectangle([bx, y, bx+w, y+350], radius=12, fill=DARK_CARD, outline=color, width=2)
    d.text((bx+15, y+10), name, fill=color, font=FONT_LABEL)
    for j, line in enumerate(desc.split("\n")):
        d.text((bx+15, y+45+j*25), line, fill=MUTED, font=FONT_TINY)
    d.rectangle([bx+10, y+120, bx+w-10, y+122], fill=color)
    for j, f in enumerate(fields):
        d.text((bx+15, y+130+j*30), f"• {f}", fill=TEXT, font=FONT_SMALL)
    bx += w + 30
# Transform below
d.text((100, y+380), "+ Transform  (conversion between elements)  + CurationFlag  (quality review)  + AuditLog  (provenance trail)", fill=ACCENT, font=FONT_BODY)
d.text((100, y+430), "All entities: staged → curated through curator review. No automated changes without evidence-based review.", fill=MUTED, font=FONT_SMALL)
save(img, 8, "entity_model")

# Slide 9: Enrichment Deep Dive
img, d = new_slide()
y = draw_title(d, "Multi-Precision Enrichment")
draw_bullets(d, [
    "Embedding similarity: all-MiniLM-L6-v2 → cosine similarity to 268K ontology terms",
    "SKOS mapping relations: exactMatch (≥0.95) • closeMatch (≥0.85) • broadMatch • relatedMatch",
    "LLM verification for borderline matches (0.5–0.7 score) via litellm",
    "Ontology hierarchy traversal: ancestors added as broadMatch (multi-precision)",
    "Evidence Chain for every annotation: similarity score + URI verification + reasoning",
    "Curated annotations protected from re-enrichment",
], y=y+20, spacing=60)
d.text((100, 700), "NCBITaxon filtered to 20 neuroscience-relevant species (from 2.7M terms)", fill=ACCENT2, font=FONT_SMALL)
save(img, 9, "enrichment")

# --- SECTION 3: PROCESS ---

# Slide 10: Development Process — Speckit
img, d = new_slide()
y = draw_title(d, "Engineering Process: Speckit Lifecycle")
stages = [
    ("/speckit.specify", "User stories\nAcceptance criteria\nEdge cases"),
    ("/speckit.clarify", "Ambiguity detection\nUp to 5 questions\nSpec updates"),
    ("/speckit.plan", "Architecture\nData model\nContracts"),
    ("/speckit.tasks", "Dependency-ordered\ntask breakdown\nParallel markers"),
    ("/speckit.analyze", "Cross-artifact\nconsistency check\nCoverage gaps"),
    ("/speckit.implement", "Phase-by-phase\nexecution\nCheckpoint validation"),
]
bx = 60
for i, (name, desc) in enumerate(stages):
    w = 270
    color = ACCENT if i % 2 == 0 else ACCENT2
    d.rounded_rectangle([bx, y, bx+w, y+200], radius=10, fill=DARK_CARD, outline=color, width=2)
    d.text((bx+10, y+10), name, fill=color, font=FONT_SMALL)
    for j, line in enumerate(desc.split("\n")):
        d.text((bx+10, y+45+j*28), line, fill=MUTED, font=FONT_TINY)
    if i < len(stages) - 1:
        d.text((bx+w+5, y+80), "→", fill=MUTED, font=FONT_BODY)
    bx += w + 30

d.text((100, y+240), "38 features specified and implemented through this lifecycle", fill=TEXT, font=FONT_BODY)
d.text((100, y+290), "Project constitution (v2.1.0) with 7 core principles enforced at every stage", fill=MUTED, font=FONT_SMALL)
save(img, 10, "speckit_process")

# Slide 11: Constitution Principles
img, d = new_slide()
y = draw_title(d, "Project Constitution: 7 Core Principles")
principles = [
    ("I. Simplicity First", "YAGNI at all levels — complexity must be justified"),
    ("II. Test-Driven Development", "Red-Green-Refactor, non-negotiable"),
    ("III. API-First Design", "Contracts before implementation"),
    ("IV. Observability", "Structured JSON logs, no silent failures"),
    ("V. No Deprecation", "System has no consumers — rewrite freely"),
    ("VI. Environment Isolation", "uv + venvs, bridge venv exception for adapters"),
    ("VII. Developer Experience", "docker compose up → everything works"),
]
for i, (title, desc) in enumerate(principles):
    cy = y + 10 + i * 85
    color = ACCENT if i % 2 == 0 else ACCENT2
    d.text((120, cy), title, fill=color, font=FONT_LABEL)
    d.text((120, cy+30), desc, fill=MUTED, font=FONT_BODY)
d.text((100, y + 620), "Version 2.1.0  •  Ratified 2026-03-07  •  Enforced on every PR", fill=MUTED, font=FONT_SMALL)
save(img, 11, "constitution")

# Slide 12: Feature Evolution (38 features)
img, d = new_slide()
y = draw_title(d, "38 Features: From Brainstorm to Production")
# Timeline
phases = [
    ("Iteration 1: Exploration (001-027)", [
        "001-010: Schema integration, backend, explorer, migration, enrichment",
        "011-020: Metamodel, provenance, fullstack, ingestion overhaul, extraction",
        "021-027: Source acquisition, repo restructure, ontology, staged enrichment",
    ], MUTED),
    ("Iteration 2: Production (028-038)", [
        "028-029: Storage abstraction, backend service layer",
        "030-032: Frontend integration, CivicDB-inspired UI, authentication",
        "033-034: Unit standardization, curation interface",
        "035-037: UX overhaul, knowledge service, data export",
        "038: System hardening — 47 tasks, 9 user stories",
    ], ACCENT),
]
cy = y + 10
for title, items, color in phases:
    d.text((120, cy), title, fill=color, font=FONT_LABEL)
    cy += 35
    for item in items:
        d.text((140, cy), f"• {item}", fill=MUTED if color == MUTED else TEXT, font=FONT_SMALL)
        cy += 30
    cy += 20
save(img, 12, "feature_evolution")

# --- SECTION 4: WHAT WAS BUILT ---

# Slide 13: Registry Scale
img, d = new_slide()
y = draw_title(d, "The Registry: Scale & Coverage")
draw_stat(d, 120, y+20, "7,055", "Elements", ACCENT)
draw_stat(d, 450, y+20, "1,005", "Schemas", ACCENT2)
draw_stat(d, 780, y+20, "15,881", "Values", SUCCESS)
draw_stat(d, 1110, y+20, "2,426", "Value Sets", WARN)
draw_stat(d, 1440, y+20, "15", "Transforms", (168, 85, 247))

d.rectangle([100, y+180, W-100, y+182], fill=DARK_CARD)
d.text((120, y+200), "7 Sources:", fill=TEXT, font=FONT_LABEL)
sources_detail = [
    ("BIDS", "585 elements", "JSON Schema"),
    ("NWB", "179 elements", "Python/hdmf"),
    ("DANDI", "398 elements", "Pydantic"),
    ("openMINDS", "473 elements", "JSON-LD"),
    ("AIND", "556 elements", "JSON Schema"),
    ("OpenNeuro", "28 elements", "TSV/datalad"),
    ("ReproSchema", "4,836 elements", "JSON-LD"),
]
for i, (name, count, fmt) in enumerate(sources_detail):
    col = i % 4
    row = i // 4
    cx = 120 + col * 430
    cy = y + 250 + row * 80
    d.text((cx, cy), name, fill=ACCENT, font=FONT_LABEL)
    d.text((cx, cy+30), f"{count}  •  {fmt}", fill=MUTED, font=FONT_SMALL)
save(img, 13, "registry_scale")

# Slide 14: Enrichment Results
img, d = new_slide()
y = draw_title(d, "Enrichment Coverage")
# Bar-like visualization
sources_enrich = [
    ("openMINDS", 70, SUCCESS),
    ("AIND", 34.4, ACCENT),
    ("DANDI", 25.9, ACCENT),
    ("BIDS", 10.3, ACCENT2),
    ("NWB", 1.1, WARN),
]
cy = y + 20
for name, pct, color in sources_enrich:
    d.text((120, cy), f"{name}", fill=TEXT, font=FONT_BODY)
    bar_w = int(pct * 12)
    d.rounded_rectangle([350, cy+5, 350+bar_w, cy+30], radius=5, fill=color)
    d.text((360+bar_w, cy+3), f"{pct}%", fill=color, font=FONT_BODY)
    cy += 55

d.rectangle([100, cy+10, W-100, cy+12], fill=DARK_CARD)
d.text((120, cy+30), "13 Ontologies  •  2.99M total terms  •  268K embedded", fill=ACCENT, font=FONT_BODY)
draw_bullets(d, [
    "Evidence Chain: similarity score + URI verification + reasoning chain",
    "LLM verification (gpt-5.4-nano: 0.06s/pair, ollama/qwen3.5: 0.5s/pair)",
    "NCBITaxon filtered to 20 neuroscience species (from 2.7M terms)",
    "Curated annotations protected from re-enrichment",
], y=cy+80, spacing=45)
save(img, 14, "enrichment")

# Slide 15: Knowledge Service
img, d = new_slide()
y = draw_title(d, "Knowledge Service: Expanding the Semantic Universe")
draw_card(d, 80, y, 540, 300, "ONTOLOGIES", [
    "Core: NCIT, PATO, UBERON, HP, OBI",
    "Neuro: NIDM, CogPO, NIF-std, ReproNim",
    "Imaging: DICOM, RadLex, NeuroNames",
    "New: HoMBA (brain anatomy)",
    "",
    "pyoxigraph RDF store with SPARQL",
    "Checksum-based dedup per source",
], ACCENT)
draw_card(d, 680, y, 540, 300, "DATA REPOSITORIES", [
    "OpenNeuro (BIDS + metadata, datalad)",
    "DANDI (NWB + schema.org)",
    "openMINDS instances (4,390 entries)",
    "NDA data dictionary API",
    "ReproSchema library (JSON-LD)",
    "",
    "Adapter pattern: BaseAdapter + registry",
], ACCENT2)
draw_card(d, 1280, y, 540, 300, "KNOWLEDGE BASES", [
    "Cognitive Atlas (concepts → tasks)",
    "InterLex (NIF registry)",
    "NITRC (tools + capabilities)",
    "NIH CDE Repository",
    "CDISC, FHIR, schema.org",
    "",
    "Discovery service polls APIs daily",
], SUCCESS)
save(img, 15, "knowledge_service")

# Slide 16: Adapter Architecture
img, d = new_slide()
y = draw_title(d, "Adapter Architecture: 8 Source Adapters")
adapters = [
    ("BIDS", "LinkML-first, raw JSON Schema descriptors"),
    ("NWB", "Python/hdmf introspection via bridge venv (Python 3.12)"),
    ("DANDI", "Pydantic model introspection, inheritance handling"),
    ("openMINDS", "JSON-LD → LinkML, 4,390 instance values"),
    ("AIND", "JSON Schema with $ref resolution, enum extraction"),
    ("OpenNeuro", "datalad Python API, TSV/CSV + JSON sidecar scanning"),
    ("ReproSchema", "JSON-LD with relative path ref resolution"),
    ("NDA", "REST API, data dictionary extraction with value ranges"),
]
cy = y + 10
for name, desc in adapters:
    d.text((120, cy), name, fill=ACCENT, font=FONT_LABEL)
    d.text((350, cy), desc, fill=TEXT, font=FONT_SMALL)
    cy += 42
d.text((100, cy+20), "All adapters: BaseAdapter protocol → extract() → list[ClassifiedEntity]", fill=MUTED, font=FONT_BODY)
d.text((100, cy+60), "Entity types: CLASS, ATTRIBUTE, ENUM_VALUE, VALUESET", fill=ACCENT2, font=FONT_SMALL)
save(img, 16, "adapters")

# Slide 17: Content Addressing
img, d = new_slide()
y = draw_title(d, "Content-Addressed Identity: How It Works")
draw_card(d, 80, y, 840, 350, "TWO-MODE HASHING", [
    "Mode 1 — Ontology-Anchored:",
    "  hash(data_type + unit + pattern + constraints",
    "       + primary_ontology_uri)",
    "  → Same concept across sources gets same hash",
    "",
    "Mode 2 — Structural Fallback:",
    "  hash(data_type + unit + pattern + constraints",
    "       + class + attribute + description)",
    "  → Unique within context when no ontology match",
    "",
    "Short key: 12 hex chars from SHA-256",
    "Sufficient for current scale (7K+ elements)",
], ACCENT)
draw_card(d, 980, y, 840, 350, "PROVENANCE ACCUMULATION", [
    "Element: age (sha256: 240539a4c71f...)",
    "",
    "Provenance[0]: source=bids, class=participants",
    "Provenance[1]: source=nwb, class=Subject",
    "Provenance[2]: source=aind, class=Subject",
    "Provenance[3]: source=openneuro/ds000228",
    "",
    "One entity, many origins",
    "Cross-referenced automatically",
    "Browsable ER-diagram navigator",
], ACCENT2)
save(img, 17, "content_addressing")

# Slide 18: Transform Pipeline
img, d = new_slide()
y = draw_title(d, "Transform Generation: Three Strategies")
draw_card(d, 80, y, 560, 300, "1. SHARED ONTOLOGY URI", [
    "Elements with same primary annotation",
    "e.g., both mapped to NCIT:C25150 (Age)",
    "Original method: 15 transforms generated",
    "",
    "Detects: identity, unit_conversion,",
    "type_conversion, value_mapping,",
    "structural, unknown",
], ACCENT)
draw_card(d, 680, y, 560, 300, "2. NAME-BASED MATCHING", [
    "Group by provenance name (case-insensitive)",
    "Cross-source only (BIDS age ↔ NWB age)",
    "Type compatibility check",
    "",
    "Dramatically increases coverage:",
    "100+ transforms (up from 15)",
], ACCENT2)
draw_card(d, 1280, y, 540, 300, "3. EMBEDDING SIMILARITY", [
    "Cosine similarity between element",
    "description embeddings",
    "Threshold: 0.8 (cross-source only)",
    "",
    "Catches semantic matches missed by",
    "exact name or ontology matching",
    "Capped at 500 pairs for efficiency",
], SUCCESS)
d.text((100, y+330), "Many-to-one support: source_elements[] field for composite transforms (age + age_unit → age_in_years)", fill=MUTED, font=FONT_SMALL)
save(img, 18, "transforms")

# --- SECTION 5: CURATION & UI ---

# Slide 19: Curation Workflow
img, d = new_slide()
y = draw_title(d, "Evidence-Based Curation Workflow")
draw_card(d, 80, y, 560, 380, "EVIDENCE CHAIN (Every Proposal)", [
    "similarity_score: 0.85",
    "similarity_method: cosine_embedding",
    "source_text: 'Age of participant in years'",
    "target_term_uri: NCIT:C25150",
    "target_term_label: 'Age'",
    "target_term_definition: '...'",
    "uri_verified: true ✓",
    "reasoning: 'Cosine similarity 0.85...'",
    "",
    "No hallucinated confidence.",
    "Every claim backed by verifiable evidence.",
], ACCENT)
draw_card(d, 700, y, 540, 380, "CURATION ROLES", [
    "Contributor (default):",
    "  • Suggest annotations, flag issues",
    "",
    "Curator (reviews):",
    "  • Approve/reject proposals",
    "  • Resolve curation flags",
    "  • LLM-assisted chat curation",
    "",
    "Admin (manages):",
    "  • Import registries, manage ontologies",
    "  • Version dependency management",
], ACCENT2)
draw_card(d, 1300, y, 520, 380, "AUDIT TRAIL", [
    "PROV-O style for every mutation:",
    "  • agent (who)",
    "  • activity (what)",
    "  • entity (on what)",
    "  • generated_entity (new version)",
    "  • timestamp",
    "",
    "Queryable by entity, user, time",
    "14,984 curation flags tracked",
    "All mutation types recorded",
], SUCCESS)
save(img, 19, "curation")

# Slide 20: LLM Curation Chat
img, d = new_slide()
y = draw_title(d, "LLM-Powered Curation Assistant")
draw_bullets(d, [
    "Real-time chat connected to configurable LLM backend (litellm: OpenAI, ollama, Anthropic)",
    "Entity context injected into every conversation (all fields, provenance, annotations)",
    "Auto-suggest improvements on entity load (missing annotations, unit inference, description quality)",
    "Tool execution: lookup_ontology_term, propose_entity_change, fetch_entity, trigger_ingestion",
    "Proposals appear as reviewable diffs with evidence chains in right panel",
    "Borderline candidates (0.5-0.7 score) batch-verified via LLM with cache",
], y=y+20, spacing=55)
d.text((100, 700), "SSE streaming  •  Tool execution  •  Evidence chain display  •  Diff review", fill=ACCENT, font=FONT_SMALL)
save(img, 20, "llm_chat")

# Slide 21: Search Modes
img, d = new_slide()
y = draw_title(d, "Search: Lexical, Semantic, and Combined")
draw_card(d, 80, y, 540, 280, "LEXICAL SEARCH", [
    "PostgreSQL tsvector full-text search",
    "ILIKE fallback for simple queries",
    "Cross-entity: elements, schemas,",
    "values, valuesets",
    "Exact keyword matching",
], ACCENT)
draw_card(d, 680, y, 540, 280, "SEMANTIC SEARCH", [
    "pgvector nearest-neighbor search",
    "Query → embedding → cosine distance",
    "Finds conceptually related terms:",
    "\"brain area\" → brain_region,",
    "cortical_area, anatomical_region",
], ACCENT2)
draw_card(d, 1280, y, 540, 280, "COMBINED MODE", [
    "Default: both lexical + semantic",
    "Lexical matches first (exact)",
    "Semantic matches after (related)",
    "Similarity scores displayed",
    "Mode toggle in search page UI",
], SUCCESS)
save(img, 21, "search")

# Slide 22: UI — Browse Experience
img, d = new_slide()
y = draw_title(d, "UI: Entity Navigator — ER Diagram in a Browser")
draw_bullets(d, [
    "Every entity links to related entities — schemas ↔ elements ↔ values ↔ transforms",
    "Server-side sorting on all columns (not client-side re-sort of loaded page)",
    "Infinite scroll with IntersectionObserver (sentinel 200px before end)",
    "Source filtering on every browse page (BIDS, NWB, DANDI, openMINDS, AIND, ...)",
    "Cross-entity search with results grouped by type",
    "Annotation chips with expandable evidence chains",
    "Provenance badge strips showing all source attestations",
    "Compact property tables resolving sha256 → EntityTag chips",
], y=y+10, spacing=48)
save(img, 22, "ui_browse")

# Slide 23: UI — Detail Pages
img, d = new_slide()
y = draw_title(d, "UI: Entity Detail — Full Semantic Context")
draw_bullets(d, [
    "Identity block: sha256, data type, unit, unit URI, pattern, min/max, value domain",
    "Semantic fields: description, question text, response options",
    "Ontology annotations with SKOS relation, score, evidence chain",
    "Provenance entries with W3C PROV-O metadata (source, class, activity, timestamp)",
    "Cross-references: schemas containing this element, transforms involving it",
    "Curation flags with context, LLM verification, resolve buttons",
    "Versioning: superseded_by link chain, curation_update transforms",
], y=y+10, spacing=55)
save(img, 23, "ui_detail")

# --- SECTION 6: SYSTEM HARDENING ---

# Slide 24: Feature 038 Overview
img, d = new_slide()
y = draw_title(d, "Feature 038: System Hardening")
d.text((120, y+10), "47 tasks  •  9 user stories  •  12 phases  •  47/47 complete", fill=ACCENT2, font=FONT_SUBTITLE)
stories = [
    ("US1 P1", "LLM Curation Chat", "Auto-suggest, evidence chains, tool execution"),
    ("US2 P1", "Name-Based Transforms", "100+ transforms (up from 15), many-to-one"),
    ("US3 P1", "Additional Sources", "OpenNeuro, ReproSchema, NDA adapters"),
    ("US4 P2", "Search Modes", "Lexical/semantic/both with pgvector"),
    ("US5 P2", "Ontology Admin", "pyoxigraph store info, NCBITaxon filter"),
    ("US6 P2", "Server-Side Sorting", "All browse pages, infinite scroll"),
    ("US7 P3", "Audit + Downloads", "PROV-O audit, nightly exports"),
    ("US8 P3", "CI + Pipeline", "Action v6, index auto-rebuild, LLM enrichment"),
    ("US9 P1", "Versioned Dependencies", "Checksum detection, auto re-enrich"),
]
cy = y + 70
for us, title, desc in stories:
    color = ACCENT2 if "P1" in us else ACCENT if "P2" in us else MUTED
    d.text((120, cy), us, fill=color, font=FONT_LABEL)
    d.text((280, cy), title, fill=TEXT, font=FONT_BODY)
    d.text((650, cy), desc, fill=MUTED, font=FONT_SMALL)
    cy += 44
save(img, 24, "feature_038")

# Slide 25: Evidence Chain Detail
img, d = new_slide()
y = draw_title(d, "Evidence Chain: No Hallucinated Confidence")
d.text((120, y+10), "Every automated proposal carries verifiable evidence:", fill=TEXT, font=FONT_BODY)
draw_card(d, 80, y+60, 840, 400, "EVIDENCE CHAIN STRUCTURE", [
    "┌─────────────────────────────────────┐",
    "│  Similarity Score: 0.85  [85%]      │",
    "│  Method: cosine_embedding            │",
    "│                                      │",
    "│  Source: 'Age of participant (years)' │",
    "│  Target: NCIT:C25150 'Age'           │",
    "│  Def: 'How long something existed'   │",
    "│                                      │",
    "│  URI Verified: ✓ (HTTP 200)          │",
    "│                                      │",
    "│  Reasoning: Cosine similarity 0.85   │",
    "│  between element description and     │",
    "│  term label+definition. Relation:    │",
    "│  skos:closeMatch                     │",
    "└─────────────────────────────────────┘",
], ACCENT)
draw_card(d, 980, y+60, 840, 400, "THREE VERIFICATION LAYERS", [
    "1. SEMANTIC SIMILARITY",
    "   Embedding cosine score (0.0-1.0)",
    "   Threshold: 0.7 for annotation",
    "   0.95+ for auto-assign",
    "",
    "2. LINK VERIFICATION",
    "   HTTP HEAD check on proposed URI",
    "   Detects stale/broken ontology refs",
    "",
    "3. REASONING CHAIN",
    "   Step-by-step explanation",
    "   LLM-generated for borderline matches",
    "   Template-generated for embedding matches",
], ACCENT2)
save(img, 25, "evidence_chain")

# Slide 26: Version Management
img, d = new_slide()
y = draw_title(d, "Versioned Dependency Management")
draw_bullets(d, [
    "Scheduled checksum comparison for all registered ontologies and sources",
    "When change detected → automatic re-enrichment of affected entities",
    "Curator-approved annotations preserved (curated_annotations field)",
    "Only automated annotations from old version are re-evaluated",
    "VersionTransition recorded in provenance: old checksum → new checksum → timestamp",
    "checkDependencyVersions GraphQL mutation for manual trigger",
    "HoMBA ontology loaded from brain-bican GitHub releases with OWL→TTL fallback",
], y=y+10, spacing=55)
save(img, 26, "version_management")

# --- SECTION 7: TECHNICAL DEPTH ---

# Slide 27: Polyglot Storage
img, d = new_slide()
y = draw_title(d, "Polyglot Storage: Right Tool for Each Data Type")
headers = ["Data", "Pattern", "File Backend", "DB Backend"]
rows = [
    ["Entities", "CRUD, filter, paginate", "YAML", "PostgreSQL JSONB"],
    ["Ontology terms", "Graph traversal, SPARQL", "pyoxigraph", "RDF store"],
    ["Embeddings", "Nearest-neighbor, cosine", "Parquet + numpy", "pgvector"],
    ["Full-text search", "Keyword, faceted", "grep/memory", "tsvector"],
    ["LLM cache", "Key-value lookup", "JSON file", "PostgreSQL"],
    ["Curation flags", "CRUD, status filter", "YAML", "PostgreSQL"],
    ["Audit log", "Append-only, time-range", "YAML", "PostgreSQL"],
]
# Draw table
cy = y + 10
for i, h in enumerate(headers):
    d.text((120 + i * 430, cy), h, fill=ACCENT, font=FONT_LABEL)
cy += 40
d.rectangle([100, cy, W-100, cy+2], fill=DARK_CARD)
cy += 10
for row in rows:
    for i, cell in enumerate(row):
        color = TEXT if i == 0 else MUTED
        d.text((120 + i * 430, cy), cell, fill=color, font=FONT_SMALL)
    cy += 38
save(img, 27, "polyglot_storage")

# Slide 28: GraphQL API
img, d = new_slide()
y = draw_title(d, "GraphQL API: Single Unified Interface")
draw_card(d, 80, y, 560, 400, "QUERIES", [
    "element(sha256) → Element",
    "browseElements(source, sort, search)",
    "browseSchemas / browseValues / browseValuesets",
    "search(query, mode) → SearchResult[]",
    "curationQueue(flagType, status)",
    "flagsForEntity(entityType, entityRef)",
    "schemasUsingElement(sha256)",
    "transformsForElement(sha256)",
    "ontologyStoreInfo → OntologyStoreEntry[]",
    "auditLog(entity, agent, activity)",
    "enrichmentProposals(entity, status)",
    "releases(releaseType)",
], ACCENT)
draw_card(d, 700, y, 560, 400, "MUTATIONS", [
    "resolveFlag / batchResolveFlags",
    "updateElement / updateSchema / updateValue",
    "approveAnnotation / rejectAnnotation",
    "versionElement(sha256, changes)",
    "approveIngestion / rejectIngestion",
    "reviewProposal(id, decision)",
    "requestEnrichment(entity)",
    "importRegistry(path)",
    "exportRegistry(version)",
    "checkDependencyVersions",
    "tagRelease(version)",
], ACCENT2)
d.text((1320, y+10), "Features:", fill=SUCCESS, font=FONT_LABEL)
features = ["Relay-style cursor pagination", "Keycloak OIDC auth (3 roles)",
    "PROV-O audit on every mutation", "SearchMode enum (lexical/semantic/both)",
    "Server-side sort (sortBy/sortOrder)", "Apollo paginationMerge (dedup)"]
for i, f in enumerate(features):
    d.text((1320, y+50+i*35), f"• {f}", fill=MUTED, font=FONT_SMALL)
save(img, 28, "graphql_api")

# Slide 29: Testing
img, d = new_slide()
y = draw_title(d, "Testing: 436 Library Tests + Full Stack CI")
draw_stat(d, 120, y+20, "436", "Library Tests", SUCCESS)
draw_stat(d, 450, y+20, "16", "Transform Tests", ACCENT)
draw_stat(d, 780, y+20, "9", "CI Workflows", ACCENT2)
draw_stat(d, 1110, y+20, "0", "TS Errors", SUCCESS)

cy = y + 190
draw_bullets(d, [
    "pytest + pytest-asyncio for all Python tests",
    "TypeScript strict mode with zero non-test errors",
    "GitHub Actions: library, backend, frontend, e2e, lint, build-images",
    "Actions updated to v5/v6 (Node.js 24 compatible)",
    "Docker compose for integration testing",
    "Property-based tests for content addressing",
], y=cy, spacing=50)
save(img, 29, "testing")

# --- SECTION 8: PRIOR WORK & RESOURCES ---

# Slide 30: Prior Research Efforts
img, d = new_slide()
y = draw_title(d, "Standing on the Shoulders of Giants")
draw_card(d, 80, y, 560, 400, "NEUROSCIENCE STANDARDS", [
    "BIDS (Brain Imaging Data Structure)",
    "  Gorgolewski et al., 2016",
    "NWB (Neurodata Without Borders)",
    "  Teeters et al., 2015",
    "DANDI (Distributed Archives for Neuro)",
    "  Halchenko et al., 2024",
    "openMINDS (EBRAINS metadata)",
    "  Zehl et al., 2023",
    "AIND (Allen Institute)",
    "  Allen Institute, 2023",
], ACCENT)
draw_card(d, 700, y, 540, 400, "KNOWLEDGE RESOURCES", [
    "NCIT — NCI Thesaurus (209K terms)",
    "UBERON — Anatomy ontology",
    "PATO — Phenotype/trait ontology",
    "RadLex — Radiology lexicon (46K)",
    "DICOM — Medical imaging (5K)",
    "NIDM — Neuroimaging data model",
    "HoMBA — Brain anatomy (brain-bican)",
    "Cognitive Atlas — Poldrack et al.",
    "ReproSchema — ReproNim project",
    "NDA — NIMH Data Archive",
], ACCENT2)
draw_card(d, 1300, y, 520, 400, "TECHNOLOGIES", [
    "LinkML — Moxon et al., 2021",
    "SKOS — W3C vocabulary mapping",
    "W3C PROV-O — provenance model",
    "sentence-transformers (all-MiniLM-L6-v2)",
    "pyoxigraph — RDF store",
    "pgvector — PostgreSQL embeddings",
    "litellm — LLM abstraction",
    "datalad — distributed data mgmt",
    "CivicDB — community curation model",
    "QUDT — unit vocabulary",
], SUCCESS)
save(img, 30, "prior_work")

# Slide 31: Community Model (CivicDB inspiration)
img, d = new_slide()
y = draw_title(d, "Community Curation Model (Inspired by CivicDB)")
draw_bullets(d, [
    "Three-tier graduated engagement: Contributor → Curator → Admin",
    "Revision-based workflow: suggestions with evidence, curator approves/rejects",
    "Polymorphic concerns: any entity type can be commented, flagged, subscribed to",
    "Evidence panels: automated match candidates + scores, LLM verification, related entities",
    "Activity feed filterable by action, user, source",
    "Organization-level attribution and contribution statistics",
    "Notification system for subscribed entities and flags",
], y=y+20, spacing=55)
d.text((100, 700), "Every change goes through curation — no automated change applied without review.", fill=ACCENT2, font=FONT_SMALL)
save(img, 31, "community_model")

# Slide 32: Downloads & Export
img, d = new_slide()
y = draw_title(d, "Data Export & Downloads")
draw_bullets(d, [
    "Nightly export scheduler: asyncio background task, daily archive production",
    "Export format: YAML entities + Parquet embeddings + manifest",
    "Release records: version, file size, entity counts, download count",
    "Static file serving at /api/downloads/",
    "Downloads page in UI with version, date, size, entity counts",
    "Versioned releases: tag any nightly export with a version string",
], y=y+20, spacing=55)
save(img, 32, "exports")

# --- SECTION 9: BROADER VISION ---

# Slide 33: Cross-Ecosystem Impact
img, d = new_slide()
y = draw_title(d, "Cross-Ecosystem Impact")
d.text((120, y+10), "Before undata:", fill=WARN, font=FONT_LABEL)
draw_bullets(d, [
    "Each ecosystem defines its own 'age' field independently",
    "Converting between BIDS and NWB requires custom scripts per field",
    "No machine-readable way to discover equivalent concepts",
    "Transformation provenance lost in pipeline scripts",
], y=y+50, spacing=40, bullet_color=WARN)

d.text((120, 440), "After undata:", fill=SUCCESS, font=FONT_LABEL)
draw_bullets(d, [
    "One 'age' element (sha256: 240539a4c71f...) with provenance from 5+ sources",
    "Transforms auto-generated with documented conversion logic",
    "Semantic search finds related concepts across all ecosystems",
    "Every annotation backed by evidence chain and curation review",
], y=480, spacing=40, bullet_color=SUCCESS)
save(img, 33, "cross_ecosystem")

# Slide 34: Reproducibility
img, d = new_slide()
y = draw_title(d, "Reproducibility Through Provenance")
draw_bullets(d, [
    "Content-addressed identity: same semantic content → same hash, deterministic",
    "W3C PROV-O audit trail: who changed what, when, why, and what was generated",
    "Version transitions recorded: old ontology → new ontology → affected entities",
    "Transform provenance: explicit conversion logic, not hidden scripts",
    "Curation flags: machine-generated quality concerns requiring human review",
    "Nightly exports: timestamped, versioned snapshots of the complete registry",
], y=y+20, spacing=60)
save(img, 34, "reproducibility")

# Slide 35: Scalability
img, d = new_slide()
y = draw_title(d, "Scalability & Performance")
draw_stat(d, 120, y+20, "<5s", "Chat response", ACCENT)
draw_stat(d, 450, y+20, "<1s", "Search latency", ACCENT2)
draw_stat(d, 780, y+20, "<10m", "Pipeline run", SUCCESS)
draw_stat(d, 1110, y+20, "7K+", "Elements indexed", WARN)

cy = y + 190
draw_bullets(d, [
    "PostgreSQL 16 JSONB for flexible entity storage at scale",
    "pgvector for embedding nearest-neighbor in milliseconds",
    "Cursor-based pagination (not offset) for consistent performance",
    "Ontology store handles 2.99M terms in pyoxigraph without issues",
    "Embedding index: 268K terms, NCBITaxon filtered to avoid bloat",
    "Apollo cache with paginationMerge for frontend efficiency",
], y=cy, spacing=48)
save(img, 35, "scalability")

# Slide 36: Developer Experience
img, d = new_slide()
y = draw_title(d, "Developer Experience: One Command to Everything")
d.text((120, y+10), "$ docker compose up -d", fill=ACCENT, font=FONT_SUBTITLE)
d.text((120, y+60), "→ Database seeded  •  Backend running  •  Frontend live  •  Auth configured", fill=MUTED, font=FONT_BODY)

cy = y + 130
draw_bullets(d, [
    "Library standalone: uv run undata-library pipeline --source bids (no Docker needed)",
    "Hot reload for backend and frontend development",
    "docker-compose.override.yml for full registry mounting (not committed)",
    "Curated seed subset (70 elements, 7 sources) committed for quick start",
    "Full registry at ~/.cache/undata/registry/ for comprehensive testing",
    "Ontology store mounted from host for pyoxigraph access",
], y=cy, spacing=50)
save(img, 36, "developer_experience")

# Slide 37: What's Next
img, d = new_slide()
y = draw_title(d, "What's Next")
draw_card(d, 80, y, 560, 350, "NEAR TERM", [
    "Run full enrichment with all 7 sources",
    "Generate 100+ transforms with all 3 strategies",
    "Deploy to staging environment",
    "Community beta with initial curators",
    "Load HoMBA and additional ontologies",
    "OpenNeuro batch ingestion (100+ datasets)",
], ACCENT)
draw_card(d, 700, y, 560, 350, "MEDIUM TERM", [
    "Custom LLM fine-tuning for domain",
    "Real-time collaborative curation",
    "Cross-registry federation",
    "API consumers and integrations",
    "Automated pipeline scheduling",
    "Stats/mapping repository ingestion",
], ACCENT2)
draw_card(d, 1320, y, 500, 350, "LONG TERM", [
    "Community-driven ontology creation",
    "Federated registry network",
    "Standard adoption by ecosystems",
    "Training data for neuroscience NLP",
    "Integration with analysis pipelines",
], SUCCESS)
save(img, 37, "whats_next")

# Slide 38: Key Takeaways
img, d = new_slide()
d.text((W//2 - 300, 100), "Key Takeaways", fill=ACCENT, font=FONT_HUGE)
draw_bullets(d, [
    "Content-addressed identity solves schema fragmentation across 7+ neuroscience ecosystems",
    "Evidence-based curation prevents hallucinated confidence — every claim verifiable",
    "38 features, 436 tests, 7,055 elements from a rigorous speckit-driven process",
    "Three enrichment strategies: embedding similarity + LLM verification + ontology hierarchy",
    "Three transform strategies: shared URI + name matching + embedding similarity",
    "Full audit trail with PROV-O provenance for every mutation",
    "Library + backend + frontend — all open, all tested, all documented",
], y=220, spacing=60, font=FONT_BODY)
save(img, 38, "takeaways")

# Slide 39: The Scale of the Effort
img, d = new_slide()
y = draw_title(d, "By The Numbers")
stats = [
    ("38", "Features specified", ACCENT),
    ("47", "Tasks in hardening", ACCENT2),
    ("436", "Library tests", SUCCESS),
    ("7,055", "Elements", ACCENT),
    ("15,881", "Values", ACCENT2),
    ("1,005", "Schemas", SUCCESS),
    ("2,426", "Value Sets", WARN),
    ("9", "Ontologies loaded", ACCENT),
    ("268K", "Terms embedded", ACCENT2),
    ("8", "Source adapters", SUCCESS),
    ("7", "Constitution principles", WARN),
    ("3", "Architecture layers", ACCENT),
]
for i, (num, label, color) in enumerate(stats):
    col = i % 4
    row = i // 4
    cx = 120 + col * 440
    cy = y + 20 + row * 180
    d.text((cx, cy), num, fill=color, font=FONT_BIG)
    bbox = d.textbbox((cx, cy), num, font=FONT_BIG)
    d.text((cx, bbox[3]+5), label, fill=MUTED, font=FONT_BODY)
save(img, 39, "by_the_numbers")

# Slide 40: Thank You / Closing
img, d = new_slide()
d.text((W//2 - 200, 200), "Thank You", fill=ACCENT, font=FONT_HUGE)
d.rectangle([W//2 - 100, 310, W//2 + 100, 314], fill=ACCENT2)
d.text((W//2 - 350, 380), "undata: A Universal Data Element Registry", fill=TEXT, font=FONT_SUBTITLE)
d.text((W//2 - 200, 440), "for Neuroscience", fill=TEXT, font=FONT_SUBTITLE)
d.text((W//2 - 300, 550), "github.com/sensein/undata", fill=ACCENT, font=FONT_BODY)
d.text((W//2 - 300, 600), "satra@mit.edu", fill=MUTED, font=FONT_BODY)
d.text((W//2 - 300, 700), "Built with: Python 3.14  •  FastAPI  •  Next.js  •  PostgreSQL  •  pyoxigraph", fill=MUTED, font=FONT_SMALL)
d.text((W//2 - 300, 740), "Powered by: speckit lifecycle  •  litellm  •  sentence-transformers  •  datalad", fill=MUTED, font=FONT_SMALL)
save(img, 40, "thank_you")

print(f"\nDone! Generated {40} slides in {SLIDES_DIR}")
