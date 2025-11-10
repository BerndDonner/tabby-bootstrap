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
#   all secrets, SSH keys, and cloned repository.
#   By default, seed.py will continue to execute
#   the full setup sequence automatically.
#
# 🧩 DEBUG MODE:
#   To stop after secrets and repository setup:
#     DEBUG=1 ./deploy-seed.sh <IP> secrets/seed.py
#
# 🪟 Windows (Git Bash) compatible:
#   - Starts ssh-agent if needed
#   - Adds your SSH key once per session
#   - Runs scp + ssh commands
#
# -----------------------------------------------
# Usage:
#   ./deploy-seed.sh <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>]
#
# Example:
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py
#   ./deploy-seed.sh 150.136.93.240 secrets/seed.py /tmp/seed.py
# ===============================================

SSH_USER="${SSH_USER:-ubuntu}"
REMOTE_PATH_DEFAULT="/tmp/seed.py"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/bernds-desktop}"  # change if you use another key
DEBUG_MODE="${DEBUG:-0}"  # Set to 1 to skip auto-run on remote

# --- Argument check -----------------------------------------------------------
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>]" >&2
  exit 1
fi

REMOTE_IP="$1"
SOURCE_SEED_PATH="$2"
REMOTE_PATH="${3:-$REMOTE_PATH_DEFAULT}"

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
echo "    Local file:  $SOURCE_SEED_PATH"
echo "    Remote path: $REMOTE_PATH"
echo "    SSH user:    $SSH_USER"
echo "    Debug mode:  $DEBUG_MODE"
echo

scp -C "$SOURCE_SEED_PATH" "$SSH_USER@$REMOTE_IP:$REMOTE_PATH"

if [[ "$DEBUG_MODE" == "1" ]]; then
  echo "🧩 Running seed.py in DEBUG mode (no auto-run)..."
  ssh "$SSH_USER@$REMOTE_IP" "export DEBUG=1 REMOTE_IP='$REMOTE_IP'; chmod +x '$REMOTE_PATH' && '$REMOTE_PATH'"
else
  echo "🚀 Running seed.py in AUTO mode..."
  ssh "$SSH_USER@$REMOTE_IP" "export REMOTE_IP='$REMOTE_IP'; chmod +x '$REMOTE_PATH' && '$REMOTE_PATH'"
fi

echo "✅ Deployment complete."
