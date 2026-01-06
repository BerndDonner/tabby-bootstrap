#!/usr/bin/env bash
set -euo pipefail

# ===============================================
# 🚀 deploy-seed.sh
# -----------------------------------------------
# Uploads and executes the Tabby bootstrap script
# (secrets/seed.py) on a remote machine via SSH.
#
# 🧠 PURPOSE:
#   Used to provision a fresh cloud instance with
#   all secrets, SSH keys, and the tabby-bootstrap
#   repository.
#
#   By default, seed.py will continue to execute
#   the full setup sequence automatically using
#   its built-in defaults (typically master).
#
# 🧩 DEBUG MODE (remote):
#   To stop after secrets and repository setup:
#     ./deploy-seed.sh <IP> secrets/seed.py --debug
#
#   This runs seed.py with:
#     DEBUG=1
#
# 🌿 TESTING A SPECIFIC BRANCH / REF (remote):
#   To let seed.py clone/check out a specific
#   branch/tag/commit of tabby-bootstrap:
#     ./deploy-seed.sh <IP> secrets/seed.py --branch test-bootstrap
#
#   This runs seed.py with:
#     TABBY_BOOTSTRAP_REF=test-bootstrap
#
# 🪟 Windows (Git Bash) compatible:
#   - Starts ssh-agent if needed
#   - Adds your SSH key once per session
#   - Runs scp + ssh commands
#
# -----------------------------------------------
# Usage:
#   ./deploy-seed.sh <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>] [--debug] [--branch <ref>]
#
# Examples:
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py /tmp/seed.py
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py --debug
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py --branch test-bootstrap
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py /tmp/seed.py --debug --branch a118443
# ===============================================

SSH_USER="${SSH_USER:-ubuntu}"
REMOTE_PATH_DEFAULT="/tmp/seed.py"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/bernds-desktop}"  # change if you use another key

# Behaviour flags (local defaults; changed via CLI flags)
DEBUG_MODE="0"          # 1 → run seed.py with DEBUG=1 on remote
BOOTSTRAP_BRANCH=""     # non-empty → export TABBY_BOOTSTRAP_REF on remote

# --- Argument check -----------------------------------------------------------
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>] [--debug] [--branch <ref>]" >&2
  exit 1
fi

REMOTE_IP="$1"
SOURCE_SEED_PATH="$2"
shift 2

# Optional 3rd positional arg for REMOTE_PATH (if present and not an option)
REMOTE_PATH="$REMOTE_PATH_DEFAULT"
if [[ $# -gt 0 && "${1:-}" != --* ]]; then
  REMOTE_PATH="$1"
  shift 1
fi

# --- Option parsing -----------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      DEBUG_MODE="1"
      shift
      ;;
    --branch)
      BOOTSTRAP_BRANCH="${2:-}"
      if [[ -z "$BOOTSTRAP_BRANCH" ]]; then
        echo "❌ --branch requires a value (branch/tag/SHA)" >&2
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "❌ Unknown option: $1" >&2
      echo "Usage: $0 <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>] [--debug] [--branch <ref>]" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$SOURCE_SEED_PATH" ]]; then
  echo "❌ Source file not found: $SOURCE_SEED_PATH" >&2
  exit 1
fi

# --- SSH agent setup ----------------------------------------------------------
echo "🔐 Checking ssh-agent..."

if ! ssh-add -l >/dev/null 2>&1; then
  echo "→ Starting ssh-agent and adding key..."
  eval "$(ssh-agent -s)" >/dev/null
  ssh-add "$SSH_KEY_PATH"
else
  echo "✅ SSH key already loaded in agent."
fi

# --- Deploy -------------------------------------------------------------------
echo "==> Deploying seed script to $REMOTE_IP"
echo "    Local file:     $SOURCE_SEED_PATH"
echo "    Remote path:    $REMOTE_PATH"
echo "    SSH user:       $SSH_USER"
echo "    Debug mode:     $DEBUG_MODE"
echo "    Bootstrap ref:  ${BOOTSTRAP_BRANCH:-<seed default>}"
echo

scp -C "$SOURCE_SEED_PATH" "$SSH_USER@$REMOTE_IP:$REMOTE_PATH"

# Build remote exports:
# - REMOTE_IP is always set (used by seed.py and follow-up scripts)
# - DEBUG (optional) controls seed.py debug mode
# - TABBY_BOOTSTRAP_REF (optional) controls which ref to check out
REMOTE_EXPORTS="export REMOTE_IP='$REMOTE_IP';"

if [[ "$DEBUG_MODE" == "1" ]]; then
  REMOTE_EXPORTS="export DEBUG=1 REMOTE_IP='$REMOTE_IP';"
fi

if [[ -n "$BOOTSTRAP_BRANCH" ]]; then
  REMOTE_EXPORTS="${REMOTE_EXPORTS} export TABBY_BOOTSTRAP_REF='$BOOTSTRAP_BRANCH';"
fi

if [[ "$DEBUG_MODE" == "1" ]]; then
  echo "🧩 Running seed.py in DEBUG mode (no auto-run)..."
else
  echo "🚀 Running seed.py in AUTO mode..."
fi

ssh "$SSH_USER@$REMOTE_IP" \
  "$REMOTE_EXPORTS chmod +x '$REMOTE_PATH' && '$REMOTE_PATH'"

echo "✅ Deployment complete."
