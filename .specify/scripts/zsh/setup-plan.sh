#!/usr/bin/env zsh
# Setup implementation plan for a feature
#
# Usage: ./setup-plan.sh [--json] [-h]
#
# OPTIONS:
#   --json    Output results in JSON format
#   -h        Show this help message

set -euo pipefail

JSON=false

usage() {
  echo "Usage: setup-plan.sh [--json] [-h]"
  echo "  --json    Output results in JSON format"
  echo "  -h        Show this help message"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
  shift
done

# Resolve repo root
if git rev-parse --show-toplevel &>/dev/null; then
  REPO_ROOT=$(git rev-parse --show-toplevel)
  HAS_GIT=true
else
  REPO_ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
  HAS_GIT=false
fi

# Resolve current branch / feature name
if [[ -n "${SPECIFY_FEATURE:-}" ]]; then
  CURRENT_BRANCH="$SPECIFY_FEATURE"
elif $HAS_GIT; then
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
else
  CURRENT_BRANCH=$(ls -1 "$REPO_ROOT/specs" 2>/dev/null \
    | grep -E '^[0-9]{3}-' | sort | tail -1 || echo "main")
fi

FEATURE_DIR="$REPO_ROOT/specs/$CURRENT_BRANCH"
FEATURE_SPEC="$FEATURE_DIR/spec.md"
IMPL_PLAN="$FEATURE_DIR/plan.md"

# Validate branch naming
if ! $HAS_GIT; then
  echo "[specify] Warning: Git repository not detected; skipped branch validation" >&2
elif [[ ! "$CURRENT_BRANCH" =~ ^[0-9]{3}- ]]; then
  echo "ERROR: Not on a feature branch. Current branch: $CURRENT_BRANCH"
  echo "Feature branches should be named like: 001-feature-name"
  exit 1
fi

# Ensure feature directory exists
mkdir -p "$FEATURE_DIR"

# Copy plan template only if plan.md does not already exist
TEMPLATE="$REPO_ROOT/.specify/templates/plan-template.md"
if [[ -f "$IMPL_PLAN" ]]; then
  echo "plan.md already exists at $IMPL_PLAN — not overwriting"
elif [[ -f "$TEMPLATE" ]]; then
  cp "$TEMPLATE" "$IMPL_PLAN"
  echo "Copied plan template to $IMPL_PLAN"
else
  echo "Warning: Plan template not found at $TEMPLATE" >&2
  touch "$IMPL_PLAN"
fi

# Output results
if $JSON; then
  printf '{"FEATURE_SPEC":"%s","IMPL_PLAN":"%s","SPECS_DIR":"%s","BRANCH":"%s","HAS_GIT":%s}\n' \
    "$FEATURE_SPEC" "$IMPL_PLAN" "$FEATURE_DIR" "$CURRENT_BRANCH" "$HAS_GIT"
else
  echo "FEATURE_SPEC: $FEATURE_SPEC"
  echo "IMPL_PLAN: $IMPL_PLAN"
  echo "SPECS_DIR: $FEATURE_DIR"
  echo "BRANCH: $CURRENT_BRANCH"
  echo "HAS_GIT: $HAS_GIT"
fi
