#!/usr/bin/env zsh
# Update agent context files (CLAUDE.md etc.) with technology info from plan.md
#
# Usage: ./update-agent-context.sh [--agent-type <type>] [-h]
#
# OPTIONS:
#   --agent-type TYPE   Agent to update: claude (default), gemini, copilot, etc.
#                       Omit to update all existing agent files.
#   -h, --help          Show this help message

set -euo pipefail

AGENT_TYPE=""

usage() {
  cat <<EOF
Usage: update-agent-context.sh [--agent-type TYPE] [-h]

Update agent context files with technology stack info extracted from plan.md.

OPTIONS:
  --agent-type TYPE   Target agent (claude, gemini, copilot, ...).
                      If omitted, updates all existing agent files.
  -h, --help          Show this help message

EXAMPLES:
  ./update-agent-context.sh --agent-type claude
  ./update-agent-context.sh   # update all existing agent files
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-type) AGENT_TYPE="$2"; shift ;;
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

# Resolve current branch
if [[ -n "${SPECIFY_FEATURE:-}" ]]; then
  CURRENT_BRANCH="$SPECIFY_FEATURE"
elif $HAS_GIT; then
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
else
  CURRENT_BRANCH=$(ls -1 "$REPO_ROOT/specs" 2>/dev/null \
    | grep -E '^[0-9]{3}-' | sort | tail -1 || echo "main")
fi

FEATURE_DIR="$REPO_ROOT/specs/$CURRENT_BRANCH"
IMPL_PLAN="$FEATURE_DIR/plan.md"
TEMPLATE_FILE="$REPO_ROOT/.specify/templates/agent-file-template.md"
TODAY=$(date +%Y-%m-%d)

if [[ ! -f "$IMPL_PLAN" ]]; then
  echo "ERROR: plan.md not found at $IMPL_PLAN" >&2
  echo "Run /speckit.plan first." >&2
  exit 1
fi

# Extract a rough "tech stack" line from plan.md for the Recent Changes entry
TECH_LINE=$(grep -E '^\|.*\|' "$IMPL_PLAN" 2>/dev/null | head -5 \
  | awk -F'|' '{print $3}' | tr '\n' '+' | sed 's/+$//' | tr -s ' ' || echo "")

# Map agent type → file path
agent_file() {
  local agent="$1"
  case "$agent" in
    claude)       echo "$REPO_ROOT/CLAUDE.md" ;;
    gemini)       echo "$REPO_ROOT/GEMINI.md" ;;
    copilot)      echo "$REPO_ROOT/.github/agents/copilot-instructions.md" ;;
    cursor-agent) echo "$REPO_ROOT/.cursor/rules/specify-rules.mdc" ;;
    qwen)         echo "$REPO_ROOT/QWEN.md" ;;
    codex|amp|kiro-cli|bob) echo "$REPO_ROOT/AGENTS.md" ;;
    windsurf)     echo "$REPO_ROOT/.windsurf/rules/specify-rules.md" ;;
    kilocode)     echo "$REPO_ROOT/.kilocode/rules/specify-rules.md" ;;
    auggie)       echo "$REPO_ROOT/.augment/rules/specify-rules.md" ;;
    roo)          echo "$REPO_ROOT/.roo/rules/specify-rules.md" ;;
    codebuddy)    echo "$REPO_ROOT/CODEBUDDY.md" ;;
    shai)         echo "$REPO_ROOT/SHAI.md" ;;
    agy)          echo "$REPO_ROOT/.agent/rules/specify-rules.md" ;;
    *)            echo "$REPO_ROOT/CLAUDE.md" ;;
  esac
}

update_agent() {
  local agent="$1"
  local target
  target=$(agent_file "$agent")

  # Create from template if missing
  if [[ ! -f "$target" ]]; then
    if [[ -f "$TEMPLATE_FILE" ]]; then
      mkdir -p "$(dirname "$target")"
      cp "$TEMPLATE_FILE" "$target"
      echo "Created $target from template"
    else
      echo "Warning: $target does not exist and no template found; skipping." >&2
      return
    fi
  fi

  # Append a Recent Changes entry between markers if they exist
  local marker_start="<!-- MANUAL ADDITIONS START -->"
  local marker_end="<!-- MANUAL ADDITIONS END -->"

  if grep -q "$marker_start" "$target" 2>/dev/null; then
    # Insert a "Last updated" line just before the end marker
    local updated_line="<!-- Last updated: $TODAY by update-agent-context.sh (branch: $CURRENT_BRANCH) -->"
    # Replace the end marker line, prepending our note
    sed -i '' "s|$marker_end|$updated_line\n$marker_end|" "$target" 2>/dev/null || true
  fi

  echo "✓ Updated $target"
}

# Determine which agents to update
if [[ -n "$AGENT_TYPE" ]]; then
  update_agent "$AGENT_TYPE"
else
  # Update all existing agent files (default: claude if none exist)
  KNOWN_AGENTS=(claude gemini copilot cursor-agent qwen windsurf kilocode auggie roo codebuddy shai agy)
  UPDATED=0
  for agent in "${KNOWN_AGENTS[@]}"; do
    target=$(agent_file "$agent")
    if [[ -f "$target" ]]; then
      update_agent "$agent"
      UPDATED=$((UPDATED + 1))
    fi
  done
  if [[ $UPDATED -eq 0 ]]; then
    echo "No existing agent files found; creating default CLAUDE.md"
    update_agent claude
  fi
fi
