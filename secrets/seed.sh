#!/usr/bin/env bash
set -euo pipefail

# ===============================================
# 🌱 seed — first-stage bootstrap
#  - Installs SSH key
#  - Configures Git to use that key
#  - Clones BerndDonner/tabby-bootstrap
#  - Exports AWS + Tabby secrets
#  - Restores data from Hetzner
#  - Starts Tabby
#  - Self-deletes on completion (optionally removes SSH key)
# ===============================================

# ---------- CONFIGURABLE VALUES ----------
# ⚠ These should be filled or templated by automation.

# -----BEGIN SECRET ENV-----
AWS_ACCESS_KEY_ID="<REDACTED>"
AWS_SECRET_ACCESS_KEY="<REDACTED>"
TABBY_WEBSERVER_JWT_TOKEN_SECRET="<REDACTED>"
# -----END SECRET ENV-----

GITHUB_REPO="git@github.com:BerndDonner/tabby-bootstrap.git"
GITHUB_DIR="$HOME/tabby-bootstrap"
# -----------------------------------------

SEED_PATH="$(readlink -f "$0")"
REMOVE_SSH_KEY_ON_EXIT="${REMOVE_SSH_KEY_ON_EXIT:-false}"

cleanup() {
  echo "==> Cleaning up temporary seed files..."
  if [[ "$REMOVE_SSH_KEY_ON_EXIT" == "true" ]]; then
    rm -f ~/.ssh/id_tabby_bootstrap ~/.ssh/id_tabby_bootstrap.pub
  fi
  if command -v shred >/dev/null 2>&1; then
    shred -u -n 3 -- "$SEED_PATH" || rm -f -- "$SEED_PATH"
  else
    rm -f -- "$SEED_PATH"
  fi
}
trap cleanup EXIT

echo "==> [1/7] Install SSH key for GitHub access"

for cmd in git ssh ssh-keyscan; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "❌ Missing command: $cmd"; exit 1; }
done

mkdir -p ~/.ssh
chmod 700 ~/.ssh

# --- Add your private key here (temporary classroom use only!) ---
cat > ~/.ssh/id_tabby_bootstrap <<'EOF'
# 🔒 <PRIVATE SSH KEY REDACTED>
EOF
chmod 600 ~/.ssh/id_tabby_bootstrap

# --- Public key (optional, just for clarity) ---
cat > ~/.ssh/id_tabby_bootstrap.pub <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICXiHT+jg/VjuPl3/wLs/AYNhfYIlCItbsECJbfoJKNl tabby-bootstrap deploy key
EOF
chmod 644 ~/.ssh/id_tabby_bootstrap.pub

# --- Known hosts (avoid first-time prompt) ---
grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null || \
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts

# --- Git config to use this key specifically for GitHub ---
cat > ~/.ssh/config <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_tabby_bootstrap
    IdentitiesOnly yes
    StrictHostKeyChecking no
EOF
chmod 600 ~/.ssh/config

echo "==> [2/7] Export AWS credentials for restore"
export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
echo "    AWS_ACCESS_KEY_ID exported (secret hidden)"

echo "==> [3/7] Clone tabby-bootstrap repo"
if [[ -d "$GITHUB_DIR" ]]; then
  echo "    Repo already exists; pulling latest changes..."
  git -C "$GITHUB_DIR" pull --rebase
else
  git clone "$GITHUB_REPO" "$GITHUB_DIR"
fi

cd "$GITHUB_DIR"
git -C "$GITHUB_DIR" config user.name "Bernd Donner"
git -C "$GITHUB_DIR" config user.email "bernd.donner@sabel.com"

echo "==> [4/7] Run restore script"
if [[ -x restore/restore_tabby_from_hetzner.sh ]]; then
  restore/restore_tabby_from_hetzner.sh
else
  echo "❌ restore/restore_tabby_from_hetzner.sh not found or not executable"
  exit 1
fi

echo "==> [5/7] Export Tabby JWT secret"
export TABBY_WEBSERVER_JWT_TOKEN_SECRET="$TABBY_WEBSERVER_JWT_TOKEN_SECRET"
echo "    TABBY_WEBSERVER_JWT_TOKEN_SECRET exported (secret hidden)"

echo "==> [6/7] Start Tabby setup"
if [[ -x setup/start_tabby.sh ]]; then
  setup/start_tabby.sh
else
  echo "❌ setup/start_tabby.sh not found or not executable"
  exit 1
fi

echo "==> [7/7] Done!"
echo "✅ Tabby bootstrap completed successfully!"


