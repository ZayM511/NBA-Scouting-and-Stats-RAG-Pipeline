#!/usr/bin/env bash
# block-secrets.sh — PreToolUse hook for Write/Edit.
#
# Reads the tool input JSON from stdin and scans the proposed file content for
# patterns matching API keys, tokens, and other credentials. Exits non-zero
# (which Claude Code treats as a block) if anything matches.
#
# Patterns covered:
#   - AWS access keys: AKIA followed by 16 uppercase alphanumeric
#   - Anthropic/OpenAI-style: sk- followed by 20+ alphanumeric
#   - GitHub personal access tokens: github_pat_
#   - GitHub classic tokens: ghp_, gho_, ghs_, ghr_, ghu_
#   - HuggingFace tokens: hf_
#   - Voyage AI tokens: voy-
#   - Slack bot tokens: xoxb-
#   - Google API keys: AIza followed by 35 alphanumeric/_/-
#   - Stripe live keys: sk_live_, pk_live_, rk_live_
#   - Generic high-entropy: bearer <token>, password=<value>, api_key=<value>

set -uo pipefail

# Read the entire stdin payload (the tool's input as JSON).
PAYLOAD=$(cat)

# Extract the content field. The exact field depends on whether this is a
# Write (writes 'content') or an Edit (writes 'new_string'). Grep both.
TARGET=$(printf '%s' "$PAYLOAD" | tr -d '\r')

# Patterns. Each is checked separately so the error message can name it.
declare -a PATTERNS=(
  'AKIA[0-9A-Z]{16}'
  'sk-[a-zA-Z0-9]{20,}'
  'sk_live_[a-zA-Z0-9]{20,}'
  'pk_live_[a-zA-Z0-9]{20,}'
  'rk_live_[a-zA-Z0-9]{20,}'
  'github_pat_[a-zA-Z0-9_]{20,}'
  'ghp_[a-zA-Z0-9]{30,}'
  'gho_[a-zA-Z0-9]{30,}'
  'ghs_[a-zA-Z0-9]{30,}'
  'ghr_[a-zA-Z0-9]{30,}'
  'ghu_[a-zA-Z0-9]{30,}'
  'hf_[a-zA-Z0-9]{30,}'
  'voy-[a-zA-Z0-9]{30,}'
  'xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{20,}'
  'AIza[0-9A-Za-z_-]{35}'
)

declare -a NAMES=(
  'AWS access key'
  'Anthropic/OpenAI-style secret key'
  'Stripe live secret key'
  'Stripe live publishable key'
  'Stripe live restricted key'
  'GitHub fine-grained PAT'
  'GitHub classic PAT (ghp_)'
  'GitHub OAuth (gho_)'
  'GitHub app server-to-server (ghs_)'
  'GitHub refresh (ghr_)'
  'GitHub app user-to-server (ghu_)'
  'HuggingFace token'
  'Voyage AI key'
  'Slack bot token'
  'Google API key'
)

FOUND=0
for i in "${!PATTERNS[@]}"; do
  if printf '%s' "$TARGET" | grep -Eq -- "${PATTERNS[$i]}"; then
    echo "block-secrets: matched ${NAMES[$i]} (pattern: ${PATTERNS[$i]})" >&2
    FOUND=1
  fi
done

# Soft heuristics: flag explicit assignment of obviously sensitive names.
SOFT_PATTERNS=(
  '(API_KEY|SECRET_KEY|ACCESS_KEY|PRIVATE_KEY)\s*=\s*["\047][^"\047${}]{16,}["\047]'
  'Bearer\s+[A-Za-z0-9_\-\.=]{30,}'
)
SOFT_NAMES=(
  'hardcoded *_KEY assignment'
  'inline Bearer token'
)
for i in "${!SOFT_PATTERNS[@]}"; do
  if printf '%s' "$TARGET" | grep -Eiq -- "${SOFT_PATTERNS[$i]}"; then
    # Allow placeholders like YOUR_KEY_HERE, changeme, xxx, <...>.
    if printf '%s' "$TARGET" | grep -Eiq -- "${SOFT_PATTERNS[$i]}" \
       && ! printf '%s' "$TARGET" | grep -Eiq -- '(YOUR[_-]?(KEY|TOKEN|SECRET)|changeme|placeholder|example|xxx{3,}|<[A-Z_]+>)'; then
      echo "block-secrets: matched ${SOFT_NAMES[$i]}" >&2
      FOUND=1
    fi
  fi
done

if [ "$FOUND" -ne 0 ]; then
  echo "block-secrets: WRITE BLOCKED. Move the value to an environment variable and reference it via the central config module." >&2
  exit 2
fi

exit 0
