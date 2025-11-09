#!/usr/bin/env python3
# ==========================================================
# 🔧  Shared S3 + Archiving Utilities for Tabby Backups
# ==========================================================
# Provides:
#   - S3 client setup for Hetzner Object Storage (via boto3 Session profile)
#   - Upload/Download helpers (simple logs, no external deps)
#   - .tar.zst create/extract using *system* tar+zstd only
#   - SHA256 checksum generation & verification
#
# Defaults assume:
#   - Endpoint: https://fsn1.your-objectstorage.com
#   - Region:   fsn1
#   - Profile:  hetzner  (reads ~/.aws/credentials)
#
# NOTE: Requires system binaries: tar, zstd, unzstd
# ==========================================================
import os, sys, hashlib, subprocess, shutil
from typing import Optional
import boto3, botocore

DEFAULT_ENDPOINT = "https://fsn1.your-objectstorage.com"
DEFAULT_BUCKET   = "tabby-models"
DEFAULT_REGION   = "fsn1"
DEFAULT_PROFILE  = "hetzner"

def log(msg: str) -> None:
    print(msg, flush=True)

def ensure_system_tar_zstd() -> None:
    missing = []
    if not shutil.which("tar"):
        missing.append("tar")
    if not shutil.which("zstd"):
        missing.append("zstd")
    if not shutil.which("unzstd"):
        missing.append("unzstd")
    if missing:
        raise RuntimeError(f"Missing required system tools: {', '.join(missing)}. Please install them.")

def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_sha256(filepath: str, checksum: str) -> bool:
    return calculate_sha256(filepath) == checksum

def create_archive_from_home_include_tabbyclassmodels(archive_path: str, include_models: bool) -> None:
    ensure_system_tar_zstd()
    home = os.path.expanduser("~")
    src_root = "tabbyclassmodels"
    cmd = ["tar", "-I", "zstd -T0 -19", "-cvhf", archive_path, "-C", home]
    if not include_models:
        cmd += ["--exclude", f"{src_root}/models"]
    cmd += [src_root]
    subprocess.run(cmd, check=True)

def extract_archive_to_home(archive_path: str) -> None:
    ensure_system_tar_zstd()
    home = os.path.expanduser("~")
    subprocess.run(["tar", "--use-compress-program=unzstd", "-xvf", archive_path, "-C", home], check=True)

def get_s3_client(profile: str = DEFAULT_PROFILE,
                  endpoint: str = DEFAULT_ENDPOINT,
                  region: str = DEFAULT_REGION):
    session = boto3.Session(profile_name=profile)
    return session.client("s3", endpoint_url=endpoint, region_name=region)

def upload_file(s3, bucket: str, key: str, local_path: str) -> None:
    s3.upload_file(local_path, bucket, key)
    log(f"✅ Uploaded s3://{bucket}/{key}")

def download_file(s3, bucket: str, key: str, local_path: str) -> None:
    s3.download_file(bucket, key, local_path)
    log(f"✅ Downloaded s3://{bucket}/{key}")

def find_latest_backup(s3, bucket: str, prefix: str) -> Optional[str]:
    paginator = s3.get_paginator("list_objects_v2")
    latest = None
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".tar.zst"):
                if latest is None or obj["LastModified"] > latest["LastModified"]:
                    latest = obj
    return latest["Key"] if latest else None
