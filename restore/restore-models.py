#!/usr/bin/env python3
# ==========================================================
# 🧠  Tabby Models Restore ← Hetzner Object Storage (S3)
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# 🪄 USAGE:
#   export AWS_ACCESS_KEY_ID="your-access-key"
#   export AWS_SECRET_ACCESS_KEY="your-secret-key"
#   ./restore-models.py
#
# What it does:
#   - Finds the latest models_YYYY-MM-DD.tar.zst in s3://<bucket>/model-backups/
#   - Downloads archive (+ .sha256 if present)
#   - Verifies SHA256
#   - Extracts into HOME (so 'tabbyclassmodels/models' ends under ~)
# ==========================================================
import os, argparse, tempfile, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from include.s3_utils import *

def main():
    parser = argparse.ArgumentParser(description="Restore Tabby models ← Hetzner S3")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket name")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="S3 endpoint URL")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS profile name")
    args = parser.parse_args()

    s3 = get_s3_client(args.profile, args.endpoint)
    key = find_latest_backup(s3, args.bucket, "model-backups/")
    if not key:
        log("❌ No model backup found.")
        return

    log(f"☁️ Found latest model backup: {key}")
    archive = os.path.basename(key)
    checksum_key = key.replace(".tar.zst", ".tar.zst.sha256")
    tmpdir = tempfile.gettempdir()
    local_archive = os.path.join(tmpdir, archive)
    local_checksum = local_archive + ".sha256"

    download_file(s3, args.bucket, key, local_archive)
    have_checksum = True
    try:
        download_file(s3, args.bucket, checksum_key, local_checksum)
    except botocore.exceptions.ClientError:
        log("⚠️ No checksum file found, skipping verification.")
        have_checksum = False

    if have_checksum:
        with open(local_checksum) as f:
            expected = f.read().split()[0]
        log("🔢 Verifying checksum ...")
        if verify_sha256(local_archive, expected):
            log("✅ Checksum OK.")
        else:
            log("❌ Checksum mismatch! Aborting.")
            return

    extract_archive_to_home(local_archive)
    log(f"🎉 Restore complete under ~/tabbyclassmodels/models")

if __name__ == "__main__":
    main()
