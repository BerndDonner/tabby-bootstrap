#!/usr/bin/env python3
# =====================================================================
# 🧩 30_restore_models.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Restore Tabby model files from Hetzner S3 backup.
# ---------------------------------------------------------------------
# USAGE:
#   python3 setup/30_restore_models.py
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import subprocess
from pathlib import Path


def main():
    print("==> [4/7] Restoring model data...")
    script = Path.home() / "tabby-bootstrap" / "restore" / "restore-models.py"
    subprocess.run(["python3", str(script)], check=True)
    print("✅ Model restore complete.")


if __name__ == "__main__":
    main()

