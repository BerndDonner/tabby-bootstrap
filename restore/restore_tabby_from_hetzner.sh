#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# 🧠  Tabby Model Restore Script ← Hetzner Object Storage
# ==========================================================
# Designed for ephemeral GPU instances (Lambda.ai, Hetzner, Scaleway, etc.)
#
# ----------------------------------------------------------
# 🪄 USAGE (on a freshly booted instance):
#
#   # 1️⃣ Export your Hetzner Object Storage credentials
#   export AWS_ACCESS_KEY_ID="your-access-key"
#   export AWS_SECRET_ACCESS_KEY="your-secret-key"
#
#   # 2️⃣ Run the script
#   ./restore_tabby_from_hetzner.sh
#
# The script will:
#   - detect or configure AWS CLI (works with Snap install)
#   - locate the most recent *.tar.zst* backup in s3://tabby-models
#   - download it and its checksum
#   - verify SHA256 integrity (if checksum exists)
#   - extract contents to ~/tabbyclassmodels
#
# Example output:
#   ☁️ Found latest archive: tabbyclassmodels_2025-10-26.tar.zst
#   🔽 Downloading from s3://tabby-models ...
#   🔢 Verifying checksum ...
#   📦 Extracting archive to ~/tabbyclassmodels ...
#   ✅ Restore complete!
# ==========================================================

# --- Configuration ---
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
PROFILE="hetzner"
ENDPOINT="https://fsn1.your-objectstorage.com"
REGION="fsn1"
BUCKET="tabby-models"
DEST_DIR="$HOME/tabbyclassmodels"

# --- Sanity checks ---
if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
  echo "❌ Please export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running."
  exit 1
fi

# --- Dependency check (detect Snap AWS CLI) ---
echo "🔧 Checking dependencies..."

# Detect AWS CLI binary (Snap or system)
AWS_BIN="${AWS_BIN:-$(command -v aws || true)}"
if [[ -z "$AWS_BIN" ]]; then
  echo "⚠️ AWS CLI not found. Please install it manually, e.g.:"
  echo "   snap install aws-cli --classic"
  exit 1
fi
echo "✅ Using AWS CLI: $AWS_BIN"

# Ensure zstd is available
if ! command -v zstd >/dev/null 2>&1; then
  echo "⚙️ Installing zstd ..."
  sudo apt-get update -qq
  sudo apt-get install -y zstd
else
  echo "✅ zstd found: $(command -v zstd)"
fi

# --- Prepare AWS configuration ---
mkdir -p ~/.aws
chmod 700 ~/.aws

cat > ~/.aws/credentials <<EOF
[$PROFILE]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF

cat > ~/.aws/config <<EOF
[profile $PROFILE]
region = $REGION
output = json
EOF

echo "✅ AWS profile configured for Hetzner endpoint ($ENDPOINT)"

# --- Find the most recent backup in the bucket ---
echo "☁️ Searching for latest archive in s3://$BUCKET ..."
LATEST_FILE=$($AWS_BIN --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 ls "s3://$BUCKET/" \
  | awk '/tabbyclassmodels_.*\.tar\.zst/ {print $4, $1, $2, $3}' \
  | sort -k2,3 -r | head -n1 | awk '{print $1}')

if [[ -z "$LATEST_FILE" ]]; then
  echo "❌ No backup archive found in s3://$BUCKET/"
  exit 1
fi
echo "✅ Found latest archive: $LATEST_FILE"

# --- Download archive and checksum ---
echo "🔽 Downloading archive and checksum ..."
$AWS_BIN --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 cp "s3://$BUCKET/$LATEST_FILE" .
CHECKSUM_FILE="${LATEST_FILE%.tar.zst}.sha256"

# Download checksum if available
if $AWS_BIN --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 ls "s3://$BUCKET/$CHECKSUM_FILE" >/dev/null 2>&1; then
  $AWS_BIN --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 cp "s3://$BUCKET/$CHECKSUM_FILE" .
else
  echo "⚠️ No checksum file found for $LATEST_FILE — skipping integrity check."
  CHECKSUM_FILE=""
fi

# --- Verify checksum if present ---
if [[ -n "$CHECKSUM_FILE" ]]; then
  echo "🔢 Verifying checksum ..."
  if sha256sum -c "$CHECKSUM_FILE"; then
    echo "✅ Checksum verification passed."
  else
    echo "❌ Checksum verification FAILED!"
    exit 1
  fi
fi

# --- Extract archive ---
echo "📦 Extracting $LATEST_FILE to $DEST_DIR ..."
mkdir -p "$DEST_DIR"
tar --use-compress-program=unzstd -xvf "$LATEST_FILE" \
  --strip-components=3 -C "$DEST_DIR"

# --- Cleanup (optional) ---
# rm "$LATEST_FILE" "$CHECKSUM_FILE"

echo "🎉 Restore complete! Data available at: $DEST_DIR"
