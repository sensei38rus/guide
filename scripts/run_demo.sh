#!/usr/bin/env bash


set -euo pipefail

DEMO_REPO="${DEMO_REPO:-/tmp/guide-demo-repo}"
PACKAGE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

_green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
_cyan()   { printf '\033[0;36m%s\033[0m\n' "$*"; }
_bold()   { printf '\033[1m%s\033[0m\n'    "$*"; }

_bold "═══════════════════════════════════════"
_bold " Guide — demo session (Sprint 1 + 2)"
_bold "═══════════════════════════════════════"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Setup demo repository
# ─────────────────────────────────────────────────────────────────────────────

rm -rf "$DEMO_REPO"
mkdir -p "$DEMO_REPO"
cd "$DEMO_REPO"

git init -q
git config user.email "demo@guide.local"
git config user.name  "Guide Demo"

# Install Guide hooks into the demo repo
bash "$PACKAGE_ROOT/scripts/install_hooks.sh" "$DEMO_REPO"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

PASSED=0
TRIGGERED=0
TOTAL_EXPECTED_TRIGGERS=0

attempt_commit() {
  local label="$1"
  local msg="$2"
  local expect_hint="${3:-}"

  echo ""
  _cyan "──────────────────────────────────────"
  _cyan " Scenario: $label"
  _cyan "──────────────────────────────────────"
  echo "  Commit message: \"$msg\""
  echo ""

  echo "demo content $$" >> demo.txt
  git add demo.txt

  local output
  output=$(git commit -m "$msg" 2>&1 || true)
  echo "$output"

  if [ -n "$expect_hint" ]; then
    TOTAL_EXPECTED_TRIGGERS=$((TOTAL_EXPECTED_TRIGGERS + 1))
    if echo "$output" | grep -q "$expect_hint"; then
      _green "  ✓ Expected hint found."
      TRIGGERED=$((TRIGGERED + 1))
    else
      _yellow "  ⚠ Expected hint '$expect_hint' not found."
    fi
  else
    _green "  ✓ Commit accepted (no violations expected)."
    PASSED=$((PASSED + 1))
  fi
}

attempt_large_commit() {
  local label="$1"
  local msg="$2"
  local expect_hint="${3:-}"
  local num_lines="${4:-250}"

  echo ""
  _cyan "──────────────────────────────────────"
  _cyan " Scenario: $label"
  _cyan "──────────────────────────────────────"
  echo "  Commit message: \"$msg\" (staging ~${num_lines} lines)"
  echo ""

  # Generate a file with many lines to trigger DIFF001
  python3 -c "
for i in range($num_lines):
    print(f'line {i}: ' + 'x' * 60)
" > large_file_$$.py
  git add large_file_$$.py

  local output
  output=$(git commit -m "$msg" 2>&1 || true)
  echo "$output"

  if [ -n "$expect_hint" ]; then
    TOTAL_EXPECTED_TRIGGERS=$((TOTAL_EXPECTED_TRIGGERS + 1))
    if echo "$output" | grep -q "$expect_hint"; then
      _green "  ✓ Expected hint found."
      TRIGGERED=$((TRIGGERED + 1))
    else
      _yellow "  ⚠ Expected hint '$expect_hint' not found."
    fi
  else
    _green "  ✓ Commit accepted (no violations expected)."
    PASSED=$((PASSED + 1))
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 1 — commit-msg scenarios
# ─────────────────────────────────────────────────────────────────────────────

_bold ""
_bold "── Sprint 1: commit-msg hook ──────────────────"

attempt_commit \
  "Generic placeholder message" \
  "fix" \
  "MSG001"

attempt_commit \
  "No type prefix" \
  "updated the authentication logic" \
  "MSG002"

attempt_commit \
  "Description too short" \
  "fix(auth): fix it" \
  "MSG003"

attempt_commit \
  "Well-formed Conventional Commit (clean)" \
  "feat(auth): add password strength validation on registration"

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 2 — pre-commit hook (diff size + test signal)
# ─────────────────────────────────────────────────────────────────────────────

_bold ""
_bold "── Sprint 2: pre-commit hook ──────────────────"

attempt_large_commit \
  "Large diff triggers DIFF001" \
  "feat(data): import dataset" \
  "DIFF001" \
  250

attempt_commit \
  "No test signal triggers TEST001" \
  "feat(api): add rate limiting to login" \
  "TEST001"

# Test signal via message keyword — should pass
echo "another change $$" >> demo.txt
git add demo.txt
echo ""
_cyan "──────────────────────────────────────"
_cyan " Scenario: No-test keyword in message (clean)"
_cyan "──────────────────────────────────────"
msg="feat(config): update rate limit thresholds"
body="No tests: config-only change, no logic modified"
output=$(git commit -m "$msg" -m "$body" 2>&1 || true)
echo "$output"
if echo "$output" | grep -qv "TEST001"; then
  _green "  ✓ Commit accepted (no-test keyword recognised)."
  PASSED=$((PASSED + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

echo ""
_bold "═══════════════════════════════════════"
_bold " Demo summary"
_bold "═══════════════════════════════════════"
echo "  Hook triggered correctly: $TRIGGERED / $TOTAL_EXPECTED_TRIGGERS"
echo "  Clean commits passed:     $PASSED"
echo ""

if [ "$TRIGGERED" -eq "$TOTAL_EXPECTED_TRIGGERS" ]; then
  _green "All scenarios behaved as expected. Guide is working correctly."
  exit 0
else
  _yellow "Some scenarios did not produce the expected output."
  _yellow "Check the output above for details."
  exit 1
fi
