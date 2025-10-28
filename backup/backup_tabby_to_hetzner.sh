#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# 🧠  Tabby Model Backup Script → Hetzner Object Storage
# ==========================================================
# Designed for ephemeral GPU instances (e.g. Lambda.ai, Hetzner, Scaleway).
#
# ----------------------------------------------------------
# 🪄 USAGE (on a freshly booted instance):
#
#   # 1️⃣ Export your Hetzner Object Storage credentials
#   export AWS_ACCESS_KEY_ID="your-access-key"
#   export AWS_SECRET_ACCESS_KEY="your-secret-key"
#
#   # 2️⃣ Run the script
#   ./backup_tabby_to_hetzner.sh
#
# The script will:
#   - install awscli and zstd if missing
#   - configure ~/.aws/credentials dynamically
#   - create a compressed archive of /lambda/nfs/tabbyclassmodels
#   - upload it (and its checksum) to s3://tabby-models
#   - verify upload integrity by comparing byte sizes
#
# Output example:
#   📦 Creating archive tabbyclassmodels_2025-10-26.tar.zst ...
#   ☁️ Uploading to s3://tabby-models ...
#   ✅ Verification successful: 29,075,631,747 bytes
#   🎉 Backup complete!
# ==========================================================

# --- User configuration (edit as needed) ---
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
PROFILE="hetzner"
ENDPOINT="https://fsn1.your-objectstorage.com"
REGION="fsn1"
BUCKET="tabby-models"
SRC_DIR="/lambda/nfs/tabbyclassmodels"
DATE=$(date +%Y-%m-%d)
ARCHIVE="tabbyclassmodels_${DATE}.tar.zst"
CHECKSUM="${ARCHIVE%.zst}.sha256"

# --- Sanity checks ---
if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
  echo "❌ Please export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running."
  exit 1
fi

# --- Ensure required tools are installed or available ---
echo "🔧 Checking dependencies..."

# Detect AWS CLI (Snap, system, or custom path)
if command -v aws >/dev/null 2>&1; then
  echo "✅ AWS CLI found: $(command -v aws)"
else
  echo "⚠️ AWS CLI not found in PATH."
  echo "   Please install it manually, e.g.:"
  echo "   snap install aws-cli --classic"
  exit 1
fi

# Check for zstd (compression)
if ! command -v zstd >/dev/null 2>&1; then
  echo "⚙️ Installing zstd (compression tool)..."
  sudo apt-get update -qq
  sudo apt-get install -y zstd
else
  echo "✅ zstd found: $(command -v zstd)"
fi

# --- Prepare AWS config directory ---
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

# --- Confirm configuration ---
echo "✅ AWS profile configured for Hetzner endpoint ($ENDPOINT)"

# --- Create compressed tar archive ---
echo "📦 Creating archive $ARCHIVE from $SRC_DIR ..."
tar -I 'zstd -T0 -19' -cvhf "$ARCHIVE" "$SRC_DIR"

# --- Compute checksum ---
echo "🔢 Calculating SHA256 checksum ..."
sha256sum "$ARCHIVE" > "$CHECKSUM"

# --- Upload to Hetzner S3 ---
echo "☁️ Uploading $ARCHIVE to s3://$BUCKET ..."
aws --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 cp "$ARCHIVE" "s3://$BUCKET/"

echo "☁️ Uploading checksum file ..."
aws --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3 cp "$CHECKSUM" "s3://$BUCKET/"

# --- Verify upload size ---
echo "🔍 Verifying upload ..."
LOCAL_SIZE=$(stat -c %s "$ARCHIVE")
REMOTE_SIZE=$(aws --profile "$PROFILE" --endpoint-url "$ENDPOINT" s3api head-object \
    --bucket "$BUCKET" --key "$ARCHIVE" --query 'ContentLength' --output text)

if [[ "$LOCAL_SIZE" -eq "$REMOTE_SIZE" ]]; then
    echo "✅ Verification successful: $LOCAL_SIZE bytes"
else
    echo "❌ Size mismatch! Local=$LOCAL_SIZE, Remote=$REMOTE_SIZE"
    exit 1
fi

echo "🎉 Backup complete: $ARCHIVE uploaded to s3://$BUCKET/"

