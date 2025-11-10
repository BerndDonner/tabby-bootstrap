#!/usr/bin/env bash
set -euo pipefail

# ===============================================
# 🚀 deploy-seed.sh
# -----------------------------------------------
# Uploads and executes a seed/bootstrap script on
# a remote machine via SSH, injecting the REMOTE_IP.
#
# Usage:
#   ./deploy-seed.sh <REMOTE_IP> <SOURCE_SEED_PATH> [<REMOTE_PATH>]
#
# Example:
#   ./deploy-seed.sh 192.168.1.42 ./seed.sh /tmp/seed.sh
#
# Description:
#   - Copies the specified local seed script to the given remote host.
#   - Marks it executable.
#   - Executes it with REMOTE_IP exported, so the script and any
#     sub-scripts can use it.
# ===============================================

SSH_USER="${SSH_USER:-ubuntu}"
REMOTE_PATH_DEFAULT="/tmp/00_install_secrets.py"

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

echo "==> Deploying seed script to $REMOTE_IP"
echo "    Local file:  $SOURCE_SEED_PATH"
echo "    Remote path: $REMOTE_PATH"
echo "    SSH user:    $SSH_USER"

scp -C "$SOURCE_SEED_PATH" "$SSH_USER@$REMOTE_IP:$REMOTE_PATH"

# Export REMOTE_IP during remote execution
ssh "$SSH_USER@$REMOTE_IP" "export REMOTE_IP='$REMOTE_IP'; chmod +x '$REMOTE_PATH' && '$REMOTE_PATH'"
echo "✅ Deployment complete."

