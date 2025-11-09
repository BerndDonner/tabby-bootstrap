#!/usr/bin/env python3
# =====================================================================
# 🧠 20_restore_db.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Restore Tabby SQLite database and runtime data from Hetzner S3.
# ---------------------------------------------------------------------
# USAGE:
#   python3 setup/20_restore_db.py
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import subprocess
from pathlib import Path


def main():
    print("==> [3/7] Restoring database and runtime data...")
    script = Path.home() / "tabby-bootstrap" / "restore" / "restore-db.py"
    subprocess.run(["python3", str(script)], check=True)
    print("✅ Database restore complete.")


if __name__ == "__main__":
    main()

