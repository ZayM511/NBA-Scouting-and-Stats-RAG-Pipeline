#!/usr/bin/env bash
# auto-format.sh — PostToolUse hook for Write/Edit.
#
# Runs `ruff format` on the file Claude Code just touched, if it's a Python
# file. Exit code is informational (PostToolUse hooks don't block); failures
# print a warning to stderr.

set -uo pipefail

PAYLOAD=$(cat)

# Try to extract the file path from the tool input JSON. Tool input shape:
#   {"tool_input": {"file_path": "..."}, ...}
# Use jq if available, otherwise fall back to a grep parse.
if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // .file_path // empty' 2>/dev/null)
else
  FILE_PATH=$(printf '%s' "$PAYLOAD" | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n1 | sed -E 's/.*"file_path"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
fi

if [ -z "${FILE_PATH:-}" ]; then
  exit 0
fi

# Only format Python files.
case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

if ! [ -f "$FILE_PATH" ]; then
  exit 0
fi

if ! command -v ruff >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv run ruff format "$FILE_PATH" 2>&1 || echo "auto-format: ruff format failed for $FILE_PATH" >&2
  else
    echo "auto-format: skipped (ruff and uv both missing)" >&2
  fi
  exit 0
fi

ruff format "$FILE_PATH" 2>&1 || echo "auto-format: ruff format failed for $FILE_PATH" >&2
exit 0
