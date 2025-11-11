#!/usr/bin/env python3
# ==========================================================
# 🧠  20_restore_models.py — Restore Tabby Models from S3
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# Adds simple progress feedback during large S3 downloads.
# ==========================================================

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import tempfile
import time
from include.s3_utils import (
    get_s3_client,
    find_latest_backup,
    verify_sha256,
    extract_archive_to_home,
    DEFAULT_BUCKET,
    DEFAULT_ENDPOINT,
    DEFAULT_PROFILE,
    botocore,
    log,
)


def download_file_with_progress(s3, bucket, key, dest_path, chunk_size=8 * 1024 * 1024):
    """Download a file from S3 with basic progress feedback (no extra deps)."""
    log(f"🔽 Downloading {key} → {dest_path}")
    try:
        obj = s3.head_object(Bucket=bucket, Key=key)
        total = obj.get("ContentLength", 0)
    except Exception:
        total = 0

    start = time.time()
    bytes_done = 0
    with open(dest_path, "wb") as f:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_done += len(chunk)
            if total:
                pct = bytes_done * 100 // total
                print(f"\r   Progress: {pct:3d}% ({bytes_done/1e6:.1f}/{total/1e6:.1f} MB)", end="", flush=True)
            else:
                print(f"\r   Downloaded {bytes_done/1e6:.1f} MB", end="", flush=True)
    dur = time.time() - start
    print(f"\n✅ Download complete ({bytes_done/1e6:.1f} MB in {dur:.1f}s)")


def restore_models(bucket=DEFAULT_BUCKET, endpoint=DEFAULT_ENDPOINT, profile=DEFAULT_PROFILE):
    """Restore Tabby model data from Hetzner S3."""
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

    download_file_with_progress(s3, bucket, key, local_archive)

    have_checksum = True
    try:
        download_file_with_progress(s3, bucket, checksum_key, local_checksum)
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
