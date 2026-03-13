#!/usr/bin/env bash
# fetch-schemas.sh — Download full schema fixtures for the undata ingestion pipeline.
#
# Usage: bash scripts/fetch-schemas.sh [--force]
#   --force: re-download even if files already exist (overrides idempotency check)
#
# Downloads:
#   1. NWB core YAML files (13 files) → schemas/nwb/
#   2. openMINDS schemas (sparse-checkout) → schemas/openminds-repo/
#   3. Extended AIND JSON Schema files (4 modules) → schemas/aind/
#   4. DANDI release files (v0.7.0, 5 files) → schemas/dandi/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INGESTION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCHEMAS_DIR="${INGESTION_DIR}/schemas"

FORCE="${1:-}"

info() { echo "[INFO] $*"; }
skip() { echo "[SKIP] $*"; }

# ── 1. NWB core YAML files ────────────────────────────────────────────────────

NWB_DIR="${SCHEMAS_DIR}/nwb"
NWB_BASE="https://raw.githubusercontent.com/NeurodataWithoutBorders/nwb-schema/dev/core"
NWB_FILES=(
    "nwb.namespace.yaml"
    "nwb.base.yaml"
    "nwb.icephys.yaml"
    "nwb.ecephys.yaml"
    "nwb.ophys.yaml"
    "nwb.behavior.yaml"
    "nwb.image.yaml"
    "nwb.misc.yaml"
    "nwb.file.yaml"
    "nwb.epoch.yaml"
    "nwb.device.yaml"
    "nwb.ogen.yaml"
    "nwb.retinotopy.yaml"
)

info "Downloading NWB core YAML files to ${NWB_DIR}/"
mkdir -p "${NWB_DIR}"

for filename in "${NWB_FILES[@]}"; do
    dest="${NWB_DIR}/${filename}"
    if [[ -f "${dest}" && -z "${FORCE}" ]]; then
        skip "NWB ${filename} already exists"
        continue
    fi
    info "Downloading NWB ${filename}..."
    curl -fsSL "${NWB_BASE}/${filename}" -o "${dest}"
done

info "NWB: $(ls "${NWB_DIR}"/*.yaml 2>/dev/null | wc -l | tr -d ' ') YAML files in ${NWB_DIR}/"

# ── 2. openMINDS sparse-checkout ─────────────────────────────────────────────

OPENMINDS_REPO="${SCHEMAS_DIR}/openminds-repo"
OPENMINDS_SCHEMAS="${SCHEMAS_DIR}/openminds"

if [[ -d "${OPENMINDS_REPO}" && -z "${FORCE}" ]]; then
    skip "openMINDS repo already exists at ${OPENMINDS_REPO}"
else
    info "Sparse-checking out openMINDS schemas to ${OPENMINDS_REPO}/"
    rm -rf "${OPENMINDS_REPO}"
    git clone \
        --depth 1 \
        --filter=blob:none \
        --sparse \
        https://github.com/openMetadataInitiative/openMINDS.git \
        "${OPENMINDS_REPO}" 2>&1 | grep -v "^Cloning\|^remote\|^Receiving\|^Resolving\|^Updating" || true
    (
        cd "${OPENMINDS_REPO}"
        git sparse-checkout set schemas/latest/ 2>/dev/null || true
    )
fi

# Create flat schemas/openminds/ symlink directory with .schema.omi.json files
if [[ ! -d "${OPENMINDS_SCHEMAS}" || -n "${FORCE}" ]]; then
    info "Collecting .schema.omi.json files to ${OPENMINDS_SCHEMAS}/"
    mkdir -p "${OPENMINDS_SCHEMAS}"
    if [[ -d "${OPENMINDS_REPO}/schemas/latest" ]]; then
        find "${OPENMINDS_REPO}/schemas/latest" -name "*.schema.omi.json" \
            -exec cp {} "${OPENMINDS_SCHEMAS}/" \; 2>/dev/null || true
        info "openMINDS: $(ls "${OPENMINDS_SCHEMAS}"/*.json 2>/dev/null | wc -l | tr -d ' ') schema files"
    fi
fi

# ── 3. Extended AIND JSON Schema files ───────────────────────────────────────
#
# aind-data-schema does not publish pre-generated JSON Schema files as release
# assets. We generate them using a temporary Python 3.12 venv (aind-data-schema
# 2.x requires Python 3.12; it does not compile on Python 3.14 due to Rust
# extensions). The venv is created in /tmp and reused across runs.

AIND_DIR="${SCHEMAS_DIR}/aind"
AIND_VENV="/tmp/undata-aind-venv"

# Check if all 4 AIND files already exist
AIND_MODULES=("metadata" "model" "processing" "quality_control")
AIND_MISSING=0
for module in "${AIND_MODULES[@]}"; do
    [[ ! -f "${AIND_DIR}/${module}.json" ]] && AIND_MISSING=1
done

if [[ "${AIND_MISSING}" -eq 0 && -z "${FORCE}" ]]; then
    skip "All AIND JSON Schema files already exist in ${AIND_DIR}/"
else
    info "Generating extended AIND JSON Schema files to ${AIND_DIR}/"
    mkdir -p "${AIND_DIR}"

    # Create or reuse isolated Python 3.12 venv for aind-data-schema
    if [[ ! -d "${AIND_VENV}" || -n "${FORCE}" ]]; then
        info "Creating Python 3.12 venv at ${AIND_VENV}..."
        uv venv "${AIND_VENV}" --python 3.12 --clear 2>/dev/null \
            || uv venv "${AIND_VENV}" --python python3.12 --clear
        info "Installing aind-data-schema into venv..."
        uv pip install --python "${AIND_VENV}/bin/python" aind-data-schema 2>&1 \
            | grep -E "^(Installed|error)" || true
    else
        info "Reusing existing AIND venv at ${AIND_VENV}"
    fi

    AIND_PYTHON="${AIND_VENV}/bin/python"

    # Verify install
    AIND_VER=$("${AIND_PYTHON}" -c "import aind_data_schema; print(aind_data_schema.__version__)" 2>/dev/null || echo "")
    if [[ -z "${AIND_VER}" ]]; then
        echo "[ERROR] aind-data-schema not importable in ${AIND_VENV}. Cannot generate AIND schemas." >&2
        exit 1
    fi
    info "aind-data-schema version: ${AIND_VER}"

    # Generate JSON Schema files from Pydantic models (export AIND_DIR for Python)
    export AIND_DIR
    "${AIND_PYTHON}" - <<'PYEOF'
import json, os, sys

try:
    from aind_data_schema.core import metadata, model, processing, quality_control
except ImportError as exc:
    print(f"[ERROR] Cannot import aind_data_schema: {exc}", file=sys.stderr)
    sys.exit(1)

aind_dir = os.environ["AIND_DIR"]
configs = [
    ("metadata",        metadata,        "Metadata"),
    ("model",           model,           "Model"),
    ("processing",      processing,      "Processing"),
    ("quality_control", quality_control, "QualityControl"),
]

for fname, mod, cls_name in configs:
    cls = getattr(mod, cls_name, None)
    if cls is None or not hasattr(cls, "model_json_schema"):
        print(f"[WARN] {cls_name} not found in aind_data_schema.core.{fname}", file=sys.stderr)
        continue
    schema = cls.model_json_schema()
    dest = os.path.join(aind_dir, f"{fname}.json")
    with open(dest, "w") as fh:
        json.dump(schema, fh, indent=2)
    print(f"[INFO] Wrote {fname}.json ({len(schema.get('properties', {}))} top-level props, "
          f"{len(schema.get('$defs', {}))} defs)")
PYEOF

fi

AIND_COUNT=$(ls "${AIND_DIR}"/*.json 2>/dev/null | wc -l | tr -d ' ')
info "AIND: ${AIND_COUNT} JSON Schema files in ${AIND_DIR}/"

# ── 4. DANDI release files (v0.7.0) ──────────────────────────────────────────

DANDI_DIR="${SCHEMAS_DIR}/dandi"
DANDI_VERSION="${DANDI_VERSION:-0.7.0}"
DANDI_BASE="https://raw.githubusercontent.com/dandi/dandischema/master/dandischema/data/dandischema"
DANDI_FILES=(
    "asset.json"
    "dandiset.json"
    "published-asset.json"
    "published-dandiset.json"
    "context.json"
)

info "Downloading DANDI schema release files (v${DANDI_VERSION}) to ${DANDI_DIR}/"
mkdir -p "${DANDI_DIR}"

for filename in "${DANDI_FILES[@]}"; do
    dest="${DANDI_DIR}/${filename}"
    if [[ -f "${dest}" && -z "${FORCE}" ]]; then
        skip "DANDI ${filename} already exists"
        continue
    fi
    info "Downloading DANDI ${filename}..."
    url="${DANDI_BASE}/${DANDI_VERSION}/${filename}"
    if curl -fsSL "${url}" -o "${dest}" 2>/dev/null; then
        info "Downloaded DANDI ${filename}"
    else
        info "WARN: Could not download DANDI ${filename} from ${url}"
        rm -f "${dest}"
    fi
done

DANDI_COUNT=$(ls "${DANDI_DIR}"/*.json 2>/dev/null | wc -l | tr -d ' ')
info "DANDI: ${DANDI_COUNT} JSON files in ${DANDI_DIR}/"

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "=== fetch-schemas.sh complete ==="
echo "  NWB:      $(ls "${SCHEMAS_DIR}/nwb"/*.yaml 2>/dev/null | wc -l | tr -d ' ') YAML files"
echo "  openMINDS: $(ls "${SCHEMAS_DIR}/openminds"/*.json 2>/dev/null | wc -l | tr -d ' ') schema files"
echo "  AIND:     $(ls "${SCHEMAS_DIR}/aind"/*.json 2>/dev/null | wc -l | tr -d ' ') JSON Schema files"
echo "  DANDI:    $(ls "${SCHEMAS_DIR}/dandi"/*.json 2>/dev/null | wc -l | tr -d ' ') JSON files"
