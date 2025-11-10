#!/usr/bin/env bash
set -euo pipefail

# ===============================================
# 🚀 deploy-seed.sh
# -----------------------------------------------
# Uploads and executes a seed/bootstrap script on
# a remote machine via SSH, injecting the REMOTE_IP.
#
# 🪟 Windows (Git Bash) version:
#   - Starts ssh-agent if needed
#   - Adds your SSH key once per session
#   - Then runs scp + ssh commands
#
# Usage:
#   ./deploy-seed.sh <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>]
#
# Example:
#   ./deploy-seed.sh 192.168.1.42 ./seed.sh /tmp/seed.sh
# ===============================================

SSH_USER="${SSH_USER:-ubuntu}"
REMOTE_PATH_DEFAULT="/tmp/00_install_secrets.py"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"  # change if you use another key

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
echo

scp -C "$SOURCE_SEED_PATH" "$SSH_USER@$REMOTE_IP:$REMOTE_PATH"

ssh "$SSH_USER@$REMOTE_IP" "export REMOTE_IP='$REMOTE_IP'; chmod +x '$REMOTE_PATH' && '$REMOTE_PATH'"

echo "✅ Deployment complete."
