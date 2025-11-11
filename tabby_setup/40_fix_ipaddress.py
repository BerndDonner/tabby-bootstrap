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
#   3. Updates the column `network_external_url`
#      in the table `server_setting` with:
#        http://<REMOTE_IP>:8080
# ==========================================================

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import sqlite3


def log(msg: str):
    print(msg, flush=True)


def fix_ipaddress():
    """Update Tabby network_external_url in server_setting table."""
    remote_ip = os.getenv("REMOTE_IP")
    if not remote_ip:
        log("❌ REMOTE_IP environment variable not set.")
        return False

    db_path = Path.home() / "tabbyclassmodels" / "ee" / "db.sqlite"
    if not db_path.exists():
        log(f"❌ Database not found at {db_path}")
        return False

    new_url = f"http://{remote_ip}:8080"
    log(f"🌍 Setting Tabby network_external_url to {new_url}")

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Update the single-row table
        cur.execute("UPDATE server_setting SET network_external_url = ? WHERE id = 1", (new_url,))
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
