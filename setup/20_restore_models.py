#!/usr/bin/env python3
# ==========================================================
# 🧠  20_restore_models.py — Restore Tabby Models from S3
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# 💡 Usage (CLI mode):
#     export AWS_ACCESS_KEY_ID="your-access-key"
#     export AWS_SECRET_ACCESS_KEY="your-secret-key"
#     python3 20_restore_models.py
#
# 💡 Usage (Python module):
#     from setup.20_restore_models import main
#     main()
#
# What it does:
#   1. Finds the latest `models_YYYY-MM-DD.tar.zst` in `s3://<bucket>/model-backups/`
#   2. Downloads archive (+ optional .sha256 file)
#   3. Verifies SHA256 checksum (if present)
#   4. Extracts archive into $HOME (→ ~/tabbyclassmodels/models)
#
# Environment:
#   AWS_ACCESS_KEY_ID       – required
#   AWS_SECRET_ACCESS_KEY   – required
#   AWS_DEFAULT_REGION      – optional
#   AWS_PROFILE             – optional, overrides credentials
#   TABBY_S3_BUCKET         – optional, overrides default bucket
#   TABBY_S3_ENDPOINT       – optional, overrides default endpoint
# ==========================================================

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import tempfile
from include.s3_utils import (
    get_s3_client,
    find_latest_backup,
    download_file,
    verify_sha256,
    extract_archive_to_home,
    DEFAULT_BUCKET,
    DEFAULT_ENDPOINT,
    DEFAULT_PROFILE,
    botocore,
    log,
)


def restore_models(bucket=DEFAULT_BUCKET, endpoint=DEFAULT_ENDPOINT, profile=DEFAULT_PROFILE):
    """
    Restore Tabby model data from Hetzner S3.

    Args:
        bucket (str): S3 bucket name to use.
        endpoint (str): S3 endpoint URL.
        profile (str): Optional AWS profile for authentication.

    Returns:
        bool: True if restore succeeded, False otherwise.
    """
    s3 = get_s3_client(profile, endpoint)
    key = find_latest_backup(s3, bucket, "model-backups/")
    if not key:
        log("❌ No model backup found.")
        return False

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
            return False

    extract_archive_to_home(local_archive)
    log("🎉 Restore complete under ~/tabbyclassmodels/models")
    return True


def main():
    """CLI and run_all entry point."""
    bucket = os.getenv("TABBY_S3_BUCKET", DEFAULT_BUCKET)
    endpoint = os.getenv("TABBY_S3_ENDPOINT", DEFAULT_ENDPOINT)
    profile = os.getenv("AWS_PROFILE", DEFAULT_PROFILE)

    success = restore_models(bucket, endpoint, profile)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
