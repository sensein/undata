#!/usr/bin/env zsh
# Create a new feature branch and spec directory scaffold
#
# Usage: ./create-new-feature.sh [OPTIONS] <feature description>
#
# OPTIONS:
#   --json              Output result in JSON format
#   --short-name NAME   Custom short name (2-4 words) for the branch slug
#   --number N          Specify branch number manually (overrides auto-detection)
#   -h, --help          Show this help message

set -euo pipefail

JSON=false
SHORT_NAME=""
NUMBER=0
DESCRIPTION=""

usage() {
  cat <<EOF
Usage: create-new-feature.sh [OPTIONS] <feature description>

Creates a new numbered feature branch and scaffolds the spec directory.

OPTIONS:
  --json              Output result in JSON format
  --short-name NAME   Custom short name for the branch slug (e.g. user-auth)
  --number N          Specify branch number manually (default: auto-detect)
  -h, --help          Show this help message

EXAMPLES:
  ./create-new-feature.sh 'Add user authentication system' --short-name user-auth
  ./create-new-feature.sh --number 5 'Implement OAuth2 integration'
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=true ;;
    --short-name) SHORT_NAME="$2"; shift ;;
    --number) NUMBER="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; DESCRIPTION="$*"; break ;;
    -*) echo "Unknown option: $1"; usage; exit 1 ;;
    *) DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1" ;;
  esac
  shift
done

if [[ -z "$DESCRIPTION" ]]; then
  echo "Error: Feature description is required." >&2
  usage; exit 1
fi

# Resolve repo root
REPO_ROOT=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
  if [[ -d "$DIR/.specify" ]] || [[ -d "$DIR/.git" ]]; then
    REPO_ROOT="$DIR"; break
  fi
  DIR="$(dirname "$DIR")"
done
if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: Could not find repo root (.git or .specify directory)." >&2
  exit 1
fi

HAS_GIT=false
git -C "$REPO_ROOT" rev-parse --show-toplevel &>/dev/null && HAS_GIT=true || true

SPECS_DIR="$REPO_ROOT/specs"

# Auto-detect next number
if [[ $NUMBER -eq 0 ]]; then
  HIGHEST=0
  if [[ -d "$SPECS_DIR" ]]; then
    setopt nullglob 2>/dev/null || true
    for d in "$SPECS_DIR"/[0-9][0-9][0-9]-*; do
      [[ -d "$d" ]] || continue
      n="${d##*/}"; n="${n%%-*}"; n="${n#0}"; n="${n#0}"
      [[ $n -gt $HIGHEST ]] && HIGHEST=$n
    done
    setopt nonullglob 2>/dev/null || true
  fi
  NUMBER=$((HIGHEST + 1))
fi

PADDED=$(printf "%03d" "$NUMBER")

# Derive slug from short name or description
if [[ -z "$SHORT_NAME" ]]; then
  SHORT_NAME=$(echo "$DESCRIPTION" \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9 ]//g' \
    | tr -s ' ' '-' \
    | cut -c1-50 \
    | sed 's/-$//')
fi

BRANCH="${PADDED}-${SHORT_NAME}"
FEATURE_DIR="$SPECS_DIR/$BRANCH"

# Create directory scaffold
mkdir -p "$FEATURE_DIR/contracts"
mkdir -p "$FEATURE_DIR/checklists"

TEMPLATE_DIR="$REPO_ROOT/.specify/templates"

for tmpl in spec-template.md plan-template.md; do
  target_name="${tmpl/-template/}"
  src="$TEMPLATE_DIR/$tmpl"
  dst="$FEATURE_DIR/$target_name"
  if [[ -f "$src" ]]; then
    cp "$src" "$dst"
  else
    touch "$dst"
  fi
done

# Create git branch if in a git repo
if $HAS_GIT; then
  git -C "$REPO_ROOT" checkout -b "$BRANCH" 2>/dev/null || \
    echo "Warning: Branch '$BRANCH' already exists or could not be created." >&2
fi

if $JSON; then
  printf '{"BRANCH":"%s","FEATURE_DIR":"%s","NUMBER":%d}\n' \
    "$BRANCH" "$FEATURE_DIR" "$NUMBER"
else
  echo "Created feature: $BRANCH"
  echo "Feature dir:     $FEATURE_DIR"
  echo "Next step:       Edit $FEATURE_DIR/spec.md then run /speckit.plan"
fi
