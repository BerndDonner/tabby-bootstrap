#!/usr/bin/env python3
# ==========================================================
# 🔧  Shared S3 + Archiving Utilities for Tabby Backups
# ==========================================================
# Provides:
#   - S3 client setup for Hetzner Object Storage (via boto3 Session profile)
#   - Upload/Download with progress bars (tqdm)
#   - .tar.zst create/extract (prefers system tar+zstd, falls back to Python)
#   - SHA256 checksum generation & verification
#
# Defaults assume:
#   - Endpoint: https://fsn1.your-objectstorage.com
#   - Region:   fsn1
#   - Profile:  hetzner  (reads ~/.aws/credentials)
#
# ==========================================================
import os, sys, hashlib, tarfile, subprocess, shutil
from typing import Optional
import boto3, botocore
from tqdm import tqdm

DEFAULT_ENDPOINT = "https://fsn1.your-objectstorage.com"
DEFAULT_BUCKET   = "tabby-models"
DEFAULT_REGION   = "fsn1"
DEFAULT_PROFILE  = "hetzner"

# ---------- Console helpers ----------
def log(msg: str) -> None:
    print(msg, flush=True)

def is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False

# ---------- Checksum helpers ----------
def calculate_sha256(filepath: str, progress: bool = False) -> str:
    h = hashlib.sha256()
    total = os.path.getsize(filepath)
    with open(filepath, "rb") as f, tqdm(
        total=total, unit="B", unit_scale=True, disable=not progress or not is_tty(),
        desc=f"SHA256 {os.path.basename(filepath)}"
    ) as bar:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            bar.update(len(chunk))
    return h.hexdigest()

def verify_sha256(filepath: str, checksum: str) -> bool:
    return calculate_sha256(filepath) == checksum

# ---------- Archive helpers ----------
def has_system_tar_zstd() -> bool:
    return bool(shutil.which("tar")) and bool(shutil.which("zstd"))

def create_archive(src_dir: str, archive_path: str) -> None:
    # Create .tar.zst archive containing the basename of src_dir at the archive root.
    src_dir = os.path.abspath(os.path.expanduser(src_dir))
    parent  = os.path.dirname(src_dir)
    base    = os.path.basename(src_dir)

    if has_system_tar_zstd():
        log("📦 Creating archive using system tar+zstd ...")
        subprocess.run(
            ["tar", "-I", "zstd -T0 -19", "-cvhf", archive_path, "-C", parent, base],
            check=True,
        )
    else:
        log("📦 Creating archive using Python tarfile+zstandard ...")
        try:
            import zstandard as zstd
        except ImportError as e:
            raise RuntimeError("zstandard module not installed and system zstd not available") from e
        with open(archive_path, "wb") as f:
            cctx = zstd.ZstdCompressor(level=19)
            with cctx.stream_writer(f) as compressor:
                with tarfile.open(mode="w|", fileobj=compressor) as tar:
                    tar.add(src_dir, arcname=base)

def extract_archive(archive_path: str, dest_dir: str) -> None:
    dest_dir = os.path.abspath(os.path.expanduser(dest_dir))
    os.makedirs(dest_dir, exist_ok=True)

    if has_system_tar_zstd():
        log("📦 Extracting archive using system tar+zstd ...")
        subprocess.run(
            ["tar", "--use-compress-program=unzstd", "-xvf", archive_path, "-C", dest_dir],
            check=True,
        )
    else:
        log("📦 Extracting archive using Python tarfile+zstandard ...")
        try:
            import zstandard as zstd
        except ImportError as e:
            raise RuntimeError("zstandard module not installed and system zstd not available") from e
        with open(archive_path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as tar:
                    tar.extractall(path=dest_dir)

# ---------- AWS / S3 helpers ----------
def get_s3_client(profile: str = DEFAULT_PROFILE,
                  endpoint: str = DEFAULT_ENDPOINT,
                  region: str = DEFAULT_REGION):
    # Return a boto3 S3 client using the given profile, endpoint, and region.
    session = boto3.Session(profile_name=profile)
    return session.client("s3", endpoint_url=endpoint, region_name=region)

def upload_file(s3, bucket: str, key: str, local_path: str, progress: bool = False) -> None:
    total = os.path.getsize(local_path)
    with open(local_path, "rb") as f, tqdm(
        total=total, unit="B", unit_scale=True, disable=not progress or not is_tty(),
        desc=f"Uploading {os.path.basename(local_path)}"
    ) as bar:
        s3.upload_fileobj(f, bucket, key, Callback=lambda n: bar.update(n))
    log(f"✅ Uploaded s3://{bucket}/{key}")

def download_file(s3, bucket: str, key: str, local_path: str, progress: bool = False) -> None:
    meta = s3.head_object(Bucket=bucket, Key=key)
    total = meta["ContentLength"]
    with open(local_path, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, disable=not progress or not is_tty(),
        desc=f"Downloading {os.path.basename(local_path)}"
    ) as bar:
        s3.download_fileobj(bucket, key, f, Callback=lambda n: bar.update(n))
    log(f"✅ Downloaded s3://{bucket}/{key}")

def find_latest_backup(s3, bucket: str, prefix: str) -> Optional[str]:
    # Return the key of the most recently modified .tar.zst object under prefix.
    paginator = s3.get_paginator("list_objects_v2")
    latest = None
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".tar.zst"):
                if latest is None or obj["LastModified"] > latest["LastModified"]:
                    latest = obj
    return latest["Key"] if latest else None
