#!/usr/bin/env python3
# =====================================================================
# 🧩 10_clone_repo.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Clone or update the tabby-bootstrap repository on the instance.
#
# ---------------------------------------------------------------------
# USAGE:
#   python3 setup/10_clone_repo.py
#
#   Expects a working SSH key in ~/.ssh/id_tabby_bootstrap.
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import subprocess
from pathlib import Path


def main():
    print("==> [2/7] Clone or update tabby-bootstrap repository")

    repo_url = "git@github.com:BerndDonner/tabby-bootstrap.git"
    target_dir = Path.home() / "tabby-bootstrap"

    if target_dir.exists():
        print("    Repository exists — pulling latest changes...")
        subprocess.run(["git", "-C", str(target_dir), "pull", "--rebase"], check=True)
    else:
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)

    subprocess.run(["git", "-C", str(target_dir), "config", "user.name", "Bernd Donner"], check=True)
    subprocess.run(["git", "-C", str(target_dir), "config", "user.email", "bernd.donner@sabel.com"], check=True)

    print("✅ Repository ready at", target_dir)


if __name__ == "__main__":
    main()

