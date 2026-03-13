#!/usr/bin/env zsh
# Consolidated prerequisite checking script (zsh)
#
# Equivalent to scripts/powershell/check-prerequisites.ps1
#
# Usage: ./check-prerequisites.sh [OPTIONS]
#
# OPTIONS:
#   --json              Output in JSON format
#   --require-tasks     Require tasks.md to exist (for implementation phase)
#   --include-tasks     Include tasks.md in AVAILABLE_DOCS list
#   --paths-only        Only output path variables (no validation)
#   -h, --help          Show help message

set -euo pipefail

JSON=false
REQUIRE_TASKS=false
INCLUDE_TASKS=false
PATHS_ONLY=false

usage() {
  cat <<EOF
Usage: check-prerequisites.sh [OPTIONS]

Consolidated prerequisite checking for Spec-Driven Development workflow.

OPTIONS:
  --json              Output in JSON format
  --require-tasks     Require tasks.md to exist (for implementation phase)
  --include-tasks     Include tasks.md in AVAILABLE_DOCS list
  --paths-only        Only output path variables (no prerequisite validation)
  -h, --help          Show this help message

EXAMPLES:
  # Check task prerequisites (plan.md required)
  ./check-prerequisites.sh --json

  # Check implementation prerequisites (plan.md + tasks.md required)
  ./check-prerequisites.sh --json --require-tasks --include-tasks

  # Get feature paths only (no validation)
  ./check-prerequisites.sh --paths-only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)         JSON=true ;;
    --require-tasks) REQUIRE_TASKS=true ;;
    --include-tasks) INCLUDE_TASKS=true ;;
    --paths-only)   PATHS_ONLY=true ;;
    -h|--help)      usage; exit 0 ;;
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
  # Fall back: pick highest-numbered specs/ directory
  CURRENT_BRANCH=$(ls -1 "$REPO_ROOT/specs" 2>/dev/null \
    | grep -E '^[0-9]{3}-' | sort | tail -1 || echo "main")
fi

FEATURE_DIR="$REPO_ROOT/specs/$CURRENT_BRANCH"
FEATURE_SPEC="$FEATURE_DIR/spec.md"
IMPL_PLAN="$FEATURE_DIR/plan.md"
TASKS="$FEATURE_DIR/tasks.md"
RESEARCH="$FEATURE_DIR/research.md"
DATA_MODEL="$FEATURE_DIR/data-model.md"
QUICKSTART="$FEATURE_DIR/quickstart.md"
CONTRACTS_DIR="$FEATURE_DIR/contracts"

# Validate feature branch naming (warn only for non-git)
if ! $HAS_GIT; then
  echo "[specify] Warning: Git repository not detected; skipped branch validation" >&2
elif [[ ! "$CURRENT_BRANCH" =~ ^[0-9]{3}- ]]; then
  echo "ERROR: Not on a feature branch. Current branch: $CURRENT_BRANCH"
  echo "Feature branches should be named like: 001-feature-name"
  exit 1
fi

# Paths-only mode
if $PATHS_ONLY; then
  if $JSON; then
    printf '{"REPO_ROOT":"%s","BRANCH":"%s","FEATURE_DIR":"%s","FEATURE_SPEC":"%s","IMPL_PLAN":"%s","TASKS":"%s"}\n' \
      "$REPO_ROOT" "$CURRENT_BRANCH" "$FEATURE_DIR" "$FEATURE_SPEC" "$IMPL_PLAN" "$TASKS"
  else
    echo "REPO_ROOT: $REPO_ROOT"
    echo "BRANCH: $CURRENT_BRANCH"
    echo "FEATURE_DIR: $FEATURE_DIR"
    echo "FEATURE_SPEC: $FEATURE_SPEC"
    echo "IMPL_PLAN: $IMPL_PLAN"
    echo "TASKS: $TASKS"
  fi
  exit 0
fi

# Validate required dirs/files
if [[ ! -d "$FEATURE_DIR" ]]; then
  echo "ERROR: Feature directory not found: $FEATURE_DIR"
  echo "Run /speckit.specify first to create the feature structure."
  exit 1
fi

if [[ ! -f "$IMPL_PLAN" ]]; then
  echo "ERROR: plan.md not found in $FEATURE_DIR"
  echo "Run /speckit.plan first to create the implementation plan."
  exit 1
fi

if $REQUIRE_TASKS && [[ ! -f "$TASKS" ]]; then
  echo "ERROR: tasks.md not found in $FEATURE_DIR"
  echo "Run /speckit.tasks first to create the task list."
  exit 1
fi

# Build AVAILABLE_DOCS list
DOCS=()
[[ -f "$RESEARCH"   ]] && DOCS+=("research.md")
[[ -f "$DATA_MODEL" ]] && DOCS+=("data-model.md")
if [[ -d "$CONTRACTS_DIR" ]] && [[ -n "$(ls -A "$CONTRACTS_DIR" 2>/dev/null)" ]]; then
  DOCS+=("contracts/")
fi
[[ -f "$QUICKSTART" ]] && DOCS+=("quickstart.md")
$INCLUDE_TASKS && [[ -f "$TASKS" ]] && DOCS+=("tasks.md")

# Output results
if $JSON; then
  # Build JSON array of docs
  docs_json=$(printf '"%s",' "${DOCS[@]}" | sed 's/,$//')
  printf '{"FEATURE_DIR":"%s","AVAILABLE_DOCS":[%s]}\n' "$FEATURE_DIR" "$docs_json"
else
  echo "FEATURE_DIR:$FEATURE_DIR"
  echo "AVAILABLE_DOCS:"
  check_file() { [[ -f "$1" ]] && echo "  ✓ $2" || echo "  ✗ $2"; }
  check_dir()  {
    [[ -d "$1" ]] && [[ -n "$(ls -A "$1" 2>/dev/null)" ]] \
      && echo "  ✓ $2" || echo "  ✗ $2"
  }
  check_file "$RESEARCH"    "research.md"
  check_file "$DATA_MODEL"  "data-model.md"
  check_dir  "$CONTRACTS_DIR" "contracts/"
  check_file "$QUICKSTART"  "quickstart.md"
  $INCLUDE_TASKS && check_file "$TASKS" "tasks.md"
fi
