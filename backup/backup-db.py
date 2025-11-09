#!/usr/bin/env python3
# ==========================================================
# 🗄️  Tabby DB Backup → Hetzner Object Storage (S3)
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# 🪄 USAGE:
#   export AWS_ACCESS_KEY_ID="your-access-key"
#   export AWS_SECRET_ACCESS_KEY="your-secret-key"
#   ./backup-db.py --cleanup
#
# What it does:
#   - Creates a .tar.zst archive with root 'tabbyclassmodels/' under HOME
#   - Excludes 'tabbyclassmodels/models' (models are backed up separately)
#   - Generates a SHA256 checksum file (.sha256)
#   - Uploads both to s3://<bucket>/db-backups/
#   - Optionally deletes local archive via --cleanup
# ==========================================================
import os, argparse, datetime, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from include.s3_utils import *

def main():
    parser = argparse.ArgumentParser(description="Backup Tabby DB/runtime data → Hetzner S3")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket name")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="S3 endpoint URL")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS profile name")
    parser.add_argument("--cleanup", action="store_true", help="Remove local archive after successful upload")
    args = parser.parse_args()

    date = datetime.date.today().isoformat()
    archive = f"db_{date}.tar.zst"
    checksum_file = f"{archive}.sha256"
    prefix = "db-backups/"

    log("📦 Creating archive with root '~/tabbyclassmodels' (excluding models/) ...")
    create_archive_from_home_include_tabbyclassmodels(archive_path=archive, include_models=False)

    log("🔢 Calculating checksum ...")
    checksum = calculate_sha256(archive)
    with open(checksum_file, "w") as f:
        f.write(f"{checksum}  {archive}\n")

    s3 = get_s3_client(args.profile, args.endpoint)

    log("☁️ Uploading to S3 ...")
    upload_file(s3, args.bucket, prefix + archive, archive)
    upload_file(s3, args.bucket, prefix + checksum_file, checksum_file)

    log("✅ Backup complete!")
    if args.cleanup:
        os.remove(archive)
        os.remove(checksum_file)
        log("🧹 Local archive removed.")

if __name__ == "__main__":
    main()
