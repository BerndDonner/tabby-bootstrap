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
#   - Creates a .tar.zst archive of ~/tabbyclassmodels/ee
#   - Generates a SHA256 checksum
#   - Uploads both to s3://<bucket>/db-backups/
#   - Optionally deletes local archive via --cleanup
# ==========================================================
import os, argparse, datetime, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from include.s3_utils import *

def main():
    parser = argparse.ArgumentParser(description="Backup Tabby DB data → Hetzner S3")
    parser.add_argument("--src", default=os.path.expanduser("~/tabbyclassmodels/ee"),
                        help="Path to the DB data directory (default: ~/tabbyclassmodels/ee)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket name")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="S3 endpoint URL")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS profile name")
    parser.add_argument("--cleanup", action="store_true", help="Remove local archive after successful upload")
    args = parser.parse_args()

    date = datetime.date.today().isoformat()
    archive = f"db_{date}.tar.zst"
    checksum_file = f"{archive}.sha256"
    prefix = "db-backups/"

    s3 = get_s3_client(args.profile, args.endpoint)

    create_archive(args.src, archive)
    log("🔢 Calculating checksum ...")
    checksum = calculate_sha256(archive, progress=True)
    with open(checksum_file, "w") as f:
        f.write(f"{checksum}  {archive}\n")

    log("☁️ Uploading to S3 ...")
    upload_file(s3, args.bucket, prefix + archive, archive, progress=True)
    upload_file(s3, args.bucket, prefix + checksum_file, checksum_file)

    log("✅ Backup complete!")
    if args.cleanup:
        os.remove(archive)
        os.remove(checksum_file)
        log("🧹 Local archive removed.")

if __name__ == "__main__":
    main()
