#!/usr/bin/env python3
# ==========================================================
# 🧠  Tabby Models Restore ← Hetzner Object Storage (S3)
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# 🪄 USAGE (CLI mode):
#   export AWS_ACCESS_KEY_ID="your-access-key"
#   export AWS_SECRET_ACCESS_KEY="your-secret-key"
#   python3 restore-models.py
#
# 🧩 USAGE (Python module):
#   from restore_models import restore_models
#   restore_models()
#
# What it does:
#   - Finds the latest models_YYYY-MM-DD.tar.zst in s3://<bucket>/model-backups/
#   - Downloads archive (+ .sha256 if present)
#   - Verifies SHA256
#   - Extracts into HOME (so 'tabbyclassmodels/models' ends under ~)
# ==========================================================
import os
import tempfile
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from include.s3_utils import *


def restore_models(bucket=DEFAULT_BUCKET, endpoint=DEFAULT_ENDPOINT, profile=DEFAULT_PROFILE):
    """Restore Tabby model data from Hetzner S3."""
    s3 = get_s3_client(profile, endpoint)
    key = find_latest_backup(s3, bucket, "model-backups/")
    if not key:
        log("❌ No model backup found.")
        return

    log(f"☁️ Found latest model backup: {key}")
    archive = os.path.basename(key)
    checksum_key = key.replace(".tar.zst", ".tar.zst.sha256")
    tmpdir = tempfile.gettempdir()
    local_archive = os.path.join(tmpdir, archive)
    local_checksum = local_archive + ".sha256"

    download_file(s3, bucket, key, local_archive)

    have_checksum = True
    try:
        download_file(s3, bucket, checksum_key, local_checksum)
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
    log("🎉 Restore complete under ~/tabbyclassmodels/models")


if __name__ == "__main__":
    restore_models()
