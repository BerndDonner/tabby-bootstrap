#!/usr/bin/env python3
# ==========================================================
# ☁️  00_aws_env.py — Initialize AWS Credentials for Hetzner
# ==========================================================
# Creates ~/.aws/credentials and ~/.aws/config from environment
# variables. Ensures zstd is installed. This prepares the GPU
# instance for S3-based restore scripts that use boto3.
#
# 💡 Usage (CLI or via run_all):
#     export AWS_ACCESS_KEY_ID="your-access-key"
#     export AWS_SECRET_ACCESS_KEY="your-secret-key"
#     python3 setup/00_aws_env.py
#
# Environment:
#   AWS_ACCESS_KEY_ID        – required
#   AWS_SECRET_ACCESS_KEY    – required
#   TABBY_S3_ENDPOINT        – optional (default Hetzner)
#   AWS_PROFILE              – optional (default hetzner)
#   AWS_REGION               – optional (default fsn1)
# ==========================================================

import os
import sys
import shutil
import subprocess
from pathlib import Path


def log(msg: str):
    print(msg, flush=True)


def ensure_aws_env():
    """Create AWS credential/config files if not present."""
    profile = os.getenv("AWS_PROFILE", "hetzner")
    region = os.getenv("AWS_REGION", "fsn1")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        log("❌ Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY.")
        log("   Please export them before running this script.")
        sys.exit(1)

    aws_dir = Path.home() / ".aws"
    aws_dir.mkdir(mode=0o700, exist_ok=True)

    cred_file = aws_dir / "credentials"
    config_file = aws_dir / "config"

    cred_content = f"[{profile}]\naws_access_key_id = {access_key}\naws_secret_access_key = {secret_key}\n"
    config_content = f"[profile {profile}]\nregion = {region}\noutput = json\n"

    cred_file.write_text(cred_content, encoding="utf-8")
    config_file.write_text(config_content, encoding="utf-8")

    log(f"✅ AWS profile '{profile}' configured (region={region}) at {aws_dir}")


def ensure_zstd():
    """Ensure zstd is installed."""
    if shutil.which("zstd") is None:
        log("⚙️  Installing zstd (missing)...")
        subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
        subprocess.run(["sudo", "apt-get", "install", "-y", "zstd"], check=True)
    else:
        log(f"✅ zstd found at {shutil.which('zstd')}")


def main():
    ensure_aws_env()
    ensure_zstd()
    log("🎉 AWS environment ready for S3 restore scripts.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Error: {e}")
        sys.exit(1)

