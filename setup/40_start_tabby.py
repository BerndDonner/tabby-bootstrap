#!/usr/bin/env python3
# =====================================================================
# 🚀 40_start_tabby.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Launch Tabby after restoring data and models.
#
# ---------------------------------------------------------------------
# USAGE:
#   python3 setup/40_start_tabby.py
#
#   Requires TABBY_WEBSERVER_JWT_TOKEN_SECRET to be set.
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import os
import subprocess
from pathlib import Path


def main():
    print("==> [5/7] Starting Tabby service...")

    env = os.environ.copy()
    jwt_secret = env.get("TABBY_WEBSERVER_JWT_TOKEN_SECRET")

    if not jwt_secret:
        print("❌ TABBY_WEBSERVER_JWT_TOKEN_SECRET not found in environment.")
        exit(1)

    subprocess.run(["bash", "setup/start_tabby.sh"], check=True, cwd=str(Path.home() / "tabby-bootstrap"))
    print("✅ Tabby started successfully!")


if __name__ == "__main__":
    main()

