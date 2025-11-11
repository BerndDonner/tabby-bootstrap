#!/usr/bin/env python3
# ==========================================================
# 🌐  40_fix_ipaddress.py — Update Tabby Server IP in DB
# ==========================================================
# Designed for ephemeral GPU instances (Lambda, Hetzner, Scaleway)
#
# 💡 Usage (CLI mode):
#     export REMOTE_IP=192.168.1.42
#     python3 40_fix_ipaddress.py
#
# 💡 Usage (Python module):
#     from setup.40_fix_ipaddress import main
#     main()
#
# What it does:
#   1. Reads $REMOTE_IP from the environment.
#   2. Opens ~/tabbyclassmodels/ee/db.sqlite.
#   3. Updates the table `server_setting` to set:
#        key='base_url', value='http://<REMOTE_IP>:8080'
#   4. Creates the entry if it does not exist.
#
# Environment:
#   REMOTE_IP – required, e.g. 192.168.1.42
# ==========================================================

import os
import sys
import sqlite3
from pathlib import Path


def log(msg: str):
    print(msg, flush=True)


def fix_ipaddress():
    """Update Tabby base_url in server_setting table."""
    remote_ip = os.getenv("REMOTE_IP")
    if not remote_ip:
        log("❌ REMOTE_IP environment variable not set.")
        return False

    db_path = Path.home() / "tabbyclassmodels" / "ee" / "db.sqlite"
    if not db_path.exists():
        log(f"❌ Database not found at {db_path}")
        return False

    new_url = f"http://{remote_ip}:8080"
    log(f"🌍 Setting Tabby base_url to {new_url}")

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM server_setting WHERE key='base_url'")
        exists = cur.fetchone()[0] > 0

        if exists:
            cur.execute(
                "UPDATE server_setting SET value=? WHERE key='base_url'",
                (new_url,),
            )
            log("🔁 Updated existing base_url entry.")
        else:
            cur.execute(
                "INSERT INTO server_setting (key, value) VALUES ('base_url', ?)",
                (new_url,),
            )
            log("🆕 Created new base_url entry.")

        conn.commit()
        conn.close()
        log("✅ IP address updated successfully.")
        return True

    except Exception as e:
        log(f"❌ Database update failed: {e}")
        return False


def main():
    """CLI and run_all entry point."""
    success = fix_ipaddress()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

