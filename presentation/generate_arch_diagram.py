"""Generate architecture diagram for undata presentation using PIL."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1200
BG = (255, 255, 255)
TEXT = (30, 41, 59)
TEAL = (14, 116, 144)
AMBER = (180, 83, 9)
MUTED = (100, 116, 139)
CARD_BG = (241, 245, 249)
GREEN = (21, 128, 61)
ORANGE = (194, 65, 12)
PURPLE = (126, 34, 206)
LIGHT_TEAL = (207, 250, 254)
LIGHT_AMBER = (254, 243, 199)
LIGHT_GREEN = (220, 252, 231)
LIGHT_PURPLE = (243, 232, 255)

def _font(size, bold=False):
    for name in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size, index=1 if bold and name.endswith(".ttc") else 0)
        except (OSError, IndexError):
            pass
    return ImageFont.load_default(size=size)

TITLE = _font(36, True)
HEADING = _font(22, True)
BODY = _font(17)
SMALL = _font(14)
TINY = _font(12)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Title
d.text((W//2 - 250, 20), "undata Architecture", fill=TEAL, font=TITLE)
d.rectangle([W//2 - 250, 65, W//2 + 250, 68], fill=TEAL)

# --- Layer 1: Frontend ---
d.rounded_rectangle([60, 100, 620, 380], radius=16, fill=LIGHT_TEAL, outline=TEAL, width=2)
d.text((80, 110), "FRONTEND", fill=TEAL, font=HEADING)
d.text((80, 140), "Next.js + Apollo Client + Tailwind", fill=MUTED, font=SMALL)
components = ["Entity Browser", "Search (lexical/semantic)", "Curation Queue",
              "LLM Chat Assistant", "Detail Pages (ER nav)", "Downloads Page",
              "Ontology Admin", "Infinite Scroll + Sort"]
for i, c in enumerate(components):
    col, row = i % 2, i // 2
    x, y = 80 + col * 270, 175 + row * 45
    d.rounded_rectangle([x, y, x+255, y+38], radius=6, fill=BG, outline=TEAL, width=1)
    d.text((x+10, y+8), c, fill=TEXT, font=SMALL)

# Arrow: Frontend → Backend
d.text((640, 220), "GraphQL", fill=TEAL, font=SMALL)
d.line([(620, 240), (700, 240)], fill=TEAL, width=2)
d.polygon([(700, 235), (710, 240), (700, 245)], fill=TEAL)

# --- Layer 2: Backend ---
d.rounded_rectangle([720, 100, 1280, 380], radius=16, fill=LIGHT_AMBER, outline=AMBER, width=2)
d.text((740, 110), "BACKEND", fill=AMBER, font=HEADING)
d.text((740, 140), "FastAPI + Strawberry GraphQL", fill=MUTED, font=SMALL)
services = ["GraphQL Schema", "Audit Service", "Chat Service",
            "Export Service", "Version Service", "Import Service",
            "Enrichment Service", "Discovery Service"]
for i, s in enumerate(services):
    col, row = i % 2, i // 2
    x, y = 740 + col * 270, 175 + row * 45
    d.rounded_rectangle([x, y, x+255, y+38], radius=6, fill=BG, outline=AMBER, width=1)
    d.text((x+10, y+8), s, fill=TEXT, font=SMALL)

# Arrow: Backend → Library
d.text((1300, 220), "StorageBackend", fill=AMBER, font=SMALL)
d.text((1300, 238), "Protocol", fill=AMBER, font=SMALL)
d.line([(1280, 255), (1360, 255)], fill=AMBER, width=2)
d.polygon([(1360, 250), (1370, 255), (1360, 260)], fill=AMBER)

# --- Layer 3: Library ---
d.rounded_rectangle([1380, 100, 1860, 380], radius=16, fill=LIGHT_GREEN, outline=GREEN, width=2)
d.text((1400, 110), "LIBRARY", fill=GREEN, font=HEADING)
d.text((1400, 140), "Pure Python • 436 tests • CLI", fill=MUTED, font=SMALL)
modules = ["Extract (adapters)", "Enrich (embeddings+LLM)",
           "Align (aliases)", "Commit (content-addr)",
           "Transform (3 strategies)", "Curation flags",
           "Ontology Store", "Version Check"]
for i, m in enumerate(modules):
    col, row = i % 2, i // 2
    x, y = 1400 + col * 230, 175 + row * 45
    d.rounded_rectangle([x, y, x+215, y+38], radius=6, fill=BG, outline=GREEN, width=1)
    d.text((x+10, y+8), m, fill=TEXT, font=SMALL)

# --- Data Layer ---
d.rounded_rectangle([60, 420, 1860, 620], radius=16, fill=CARD_BG, outline=MUTED, width=2)
d.text((80, 430), "DATA LAYER", fill=MUTED, font=HEADING)

stores = [
    ("PostgreSQL 16", "JSONB entities\ntsvector search\nAudit log", TEAL, 80),
    ("pgvector", "384-dim embeddings\nNearest-neighbor\nSemantic search", AMBER, 380),
    ("pyoxigraph", "RDF ontology store\nSPARQL queries\n2.99M terms", GREEN, 680),
    ("File Backend", "YAML entities\nParquet vectors\nJSON LLM cache", PURPLE, 980),
    ("Keycloak", "OIDC auth\n3 roles\nJWT tokens", ORANGE, 1280),
    ("Static Files", "Export archives\nNightly builds\n/api/downloads/", MUTED, 1560),
]
for name, desc, color, x in stores:
    light = (*[min(255, c + 180) for c in color], )
    d.rounded_rectangle([x, 465, x+260, 600], radius=10, fill=light, outline=color, width=2)
    d.text((x+15, 475), name, fill=color, font=HEADING)
    for j, line in enumerate(desc.split("\n")):
        d.text((x+15, 505 + j * 22), line, fill=TEXT, font=SMALL)

# --- Pipeline Flow ---
d.rounded_rectangle([60, 660, 1860, 860], radius=16, fill=(255, 255, 255), outline=TEAL, width=2)
d.text((80, 670), "PIPELINE", fill=TEAL, font=HEADING)
d.text((220, 675), "extract → enrich → align → commit → transform", fill=MUTED, font=SMALL)

pipeline_stages = [
    ("Extract", "8 adapters\nBIDS, NWB, DANDI\nopenMINDS, AIND\nOpenNeuro, ReproSchema\nNDA", TEAL),
    ("Enrich", "Embedding similarity\nLLM verification\nOntology hierarchy\nEvidence chains\nSKOS mapping", GREEN),
    ("Align", "Cross-source aliases\nAnnotation transfer\nAlias groups\nGap detection", AMBER),
    ("Commit", "SHA-256 hashing\nTwo-mode identity\nDedup + merge\nProvenance accum", PURPLE),
    ("Transform", "Shared URI\nName matching\nEmbedding sim\nMany-to-one\nType detection", ORANGE),
]
for i, (name, desc, color) in enumerate(pipeline_stages):
    x = 80 + i * 360
    d.rounded_rectangle([x, 710, x+320, 845], radius=10, fill=BG, outline=color, width=2)
    d.text((x+15, 718), name, fill=color, font=HEADING)
    for j, line in enumerate(desc.split("\n")):
        d.text((x+15, 748 + j * 18), line, fill=TEXT, font=TINY)
    if i < 4:
        ax = x + 330
        d.line([(ax, 775), (ax + 25, 775)], fill=MUTED, width=2)
        d.polygon([(ax+25, 770), (ax+35, 775), (ax+25, 780)], fill=MUTED)

# --- Sources Row ---
d.rounded_rectangle([60, 900, 1860, 1060], radius=16, fill=CARD_BG, outline=MUTED, width=2)
d.text((80, 910), "SOURCES & KNOWLEDGE", fill=MUTED, font=HEADING)
sources = [
    ("BIDS", "JSON Schema\n585 elements"),
    ("NWB", "Python/hdmf\n179 elements"),
    ("DANDI", "Pydantic\n398 elements"),
    ("openMINDS", "JSON-LD\n473 elements"),
    ("AIND", "JSON Schema\n556 elements"),
    ("OpenNeuro", "datalad/TSV\n28 elements"),
    ("ReproSchema", "JSON-LD\n4,836 elements"),
    ("NDA", "REST API"),
]
for i, (name, desc) in enumerate(sources):
    x = 80 + i * 220
    d.rounded_rectangle([x, 945, x+200, 1040], radius=8, fill=BG, outline=TEAL, width=1)
    d.text((x+10, 950), name, fill=TEAL, font=BODY)
    for j, line in enumerate(desc.split("\n")):
        d.text((x+10, 975 + j * 18), line, fill=MUTED, font=TINY)

# --- Ontologies at bottom ---
d.text((80, 1070), "Ontologies: NCIT (209K) • PATO (2.8K) • NCBITaxon (filtered 20 spp) • UBERON • HP • DICOM (5K) • RadLex (46K) • NIDM • HoMBA • EDAM", fill=MUTED, font=SMALL)
d.text((80, 1095), "Knowledge: Cognitive Atlas • InterLex • NIH CDE • CDISC • FHIR • schema.org • QUDT units", fill=MUTED, font=SMALL)

# Arrows from sources up to pipeline
d.line([(960, 900), (960, 860)], fill=MUTED, width=2)
d.polygon([(955, 862), (960, 852), (965, 862)], fill=MUTED)

# Arrows from pipeline up to data layer
d.line([(960, 660), (960, 620)], fill=MUTED, width=2)
d.polygon([(955, 622), (960, 612), (965, 622)], fill=MUTED)

# Arrows from data layer up to backend
d.line([(960, 420), (960, 380)], fill=MUTED, width=2)
d.polygon([(955, 382), (960, 372), (965, 382)], fill=MUTED)

out = Path(__file__).parent / "diagrams" / "architecture.png"
out.parent.mkdir(exist_ok=True)
img.save(str(out), quality=95)
print(f"Created: {out} ({out.stat().st_size // 1024} KB)")
