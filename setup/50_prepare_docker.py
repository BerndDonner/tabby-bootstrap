#!/usr/bin/env python3
# ==========================================================
# 🧱  50_prepare_docker.py — Prepare Docker Environment
# ==========================================================
# Ensures docker group membership and creates required
# data directories for Tabby server.
#
# 💡 Usage:
#     python3 50_prepare_docker.py
#
# Environment:
#   Uses DATA_ROOT and MODEL_ROOT from config.py
# ==========================================================

import subprocess
from pathlib import Path
import os
import sys
from setup.config import DATA_ROOT, MODEL_ROOT
sys.path.append(str(Path(__file__).resolve().parent.parent))

def log(msg: str):
    print(msg, flush=True)


def ensure_docker_group():
    """Ensure docker group exists and user is in it."""
    user = os.getenv("USER", "ubuntu")
    log(f"==> Ensuring docker group membership for {user}")

    # Check or create docker group
    result = subprocess.run(["getent", "group", "docker"], capture_output=True, text=True)
    if not result.stdout.strip():
        subprocess.run(["sudo", "groupadd", "docker"], check=False)
        log("   ➕ Created 'docker' group.")

    # Check membership
    group_check = subprocess.run(["id", "-nG", user], capture_output=True, text=True)
    if "docker" in group_check.stdout:
        log(f"   ✅ {user} already in 'docker' group.")
    else:
        subprocess.run(["sudo", "adduser", user, "docker"], check=False)
        subprocess.run(["sudo", "usermod", "-aG", "docker", user], check=False)
        log(f"   ➕ Added {user} to 'docker' group (effective after re-login).")


def ensure_data_dirs():
    """Ensure data directories and symlink exist."""
    log("==> Ensuring data directories exist")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)

    symlink_target = Path.home() / "tabbyclassmodels"
    if not symlink_target.exists() or symlink_target.resolve() != DATA_ROOT.resolve():
        if symlink_target.exists():
            symlink_target.unlink()
        symlink_target.symlink_to(DATA_ROOT)
        log(f"   🔗 Created symlink {symlink_target} -> {DATA_ROOT}")
    else:
        log("   ✅ Symlink already correct.")


def main():
    """CLI and run_all entry point."""
    ensure_docker_group()
    ensure_data_dirs()
    log("✅ Docker environment prepared.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Error: {e}")
        sys.exit(1)

