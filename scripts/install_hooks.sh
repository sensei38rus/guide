#!/usr/bin/env bash
# install_hooks.sh — install Guide git hooks into a target repository
#
# Usage:
#   ./scripts/install_hooks.sh [REPO_PATH]
#
# REPO_PATH defaults to the current directory.
# The script is idempotent: safe to run multiple times.

set -euo pipefail

REPO_PATH="${1:-.}"
HOOKS_DIR="$REPO_PATH/.git/hooks"
PACKAGE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_HOOKS="$PACKAGE_ROOT/src/guide/hooks"

# Colour helpers (gracefully degraded when no tty)
_green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
_red() { printf '\033[0;31m%s\033[0m\n' "$*"; }

# ------------------------------------------------------------------ validate
if [ ! -d "$REPO_PATH/.git" ]; then
  _red "Error: '$REPO_PATH' is not a git repository (no .git directory found)."
  exit 1
fi

mkdir -p "$HOOKS_DIR"

# ------------------------------------------------------------------ helper
install_hook() {
  local hook_name="$1"      # e.g. commit-msg
  local python_module="$2"  # e.g. guide.hooks.commit_msg

  local target="$HOOKS_DIR/$hook_name"

  if [ -f "$target" ] && ! grep -q "# installed-by: guide" "$target" 2>/dev/null; then
    _yellow "  ⚠ $hook_name already exists and was not installed by Guide — skipping."
    _yellow "    To replace it, remove '$target' manually and re-run this script."
    return
  fi

  cat > "$target" << HOOK_SCRIPT
#!/usr/bin/env bash
# installed-by: guide
# Do not edit — regenerate with: make install

exec python3 -m $python_module "\$@"
HOOK_SCRIPT

  chmod +x "$target"
  _green "  ✓ Installed $hook_name"
}


echo "Installing Guide hooks into: $REPO_PATH"
echo ""

install_hook "commit-msg"  "guide.hooks.commit_msg"
install_hook "pre-commit"  "guide.hooks.pre_commit"
install_hook "pre-push"    "guide.hooks.pre_push"

echo ""
_green "Done. Guide hooks are active for this repository."
echo ""
echo "Verify with:  ls -la $HOOKS_DIR"
echo "Uninstall:    rm $HOOKS_DIR/commit-msg $HOOKS_DIR/pre-commit $HOOKS_DIR/pre-push"
