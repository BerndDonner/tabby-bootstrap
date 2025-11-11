#!/usr/bin/env python3
# =====================================================================
# 🚀 seed.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Bootstrap a fresh instance for Tabby and/or Ollama deployment.
#
#   This script unifies and replaces the previous stages:
#     • 00_install_secrets.py
#     • 10_clone_repo.py
#
#   It prepares a new instance for full deployment by performing:
#     1. Installing the deploy SSH key into ~/.ssh
#     2. Exporting AWS credentials (optional)
#     3. Exporting TABBY_WEBSERVER_JWT_TOKEN_SECRET (optional)
#     4. Cloning or updating the tabby-bootstrap repository
#     5. Automatically running one of the setup sequences:
#          - ~/tabby-bootstrap/ollama_setup/run_all.py   (default)
#          - ~/tabby-bootstrap/tabby_setup/run_all.py    (if adapted)
#     6. Removing itself on completion for a clean environment
#
# ---------------------------------------------------------------------
# USAGE:
#   python3 /tmp/seed.py
#
#   To run in debug mode (skip automatic run_all.py execution):
#     DEBUG=1 python3 /tmp/seed.py
#
# ---------------------------------------------------------------------
# SECRET BLOCK (redacted for Git safety):
#   These values are injected automatically by:
#     utils/inject-secrets.sh
#   and sanitized before commit by:
#     utils/strip-secrets.sh
#
# ---------------------------------------------------------------------
# NOTES:
#   - AWS and JWT secrets are optional if handled elsewhere.
#   - Uses "StrictHostKeyChecking accept-new" for first-time SSH safety.
#   - Supports automatic cleanup and self-deletion.
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import os
import shutil
import subprocess
import atexit
from pathlib import Path


# ---------- CONFIGURABLE VALUES ----------
# ⚠ These should be filled or templated by automation.

# -----BEGIN SECRET ENV-----
AWS_ACCESS_KEY_ID = "<REDACTED>"
AWS_SECRET_ACCESS_KEY = "<REDACTED>"
TABBY_WEBSERVER_JWT_TOKEN_SECRET = "<REDACTED>"
# -----END SECRET ENV-----

SEED_PATH = Path(__file__).resolve()
REMOVE_SSH_KEY_ON_EXIT = os.environ.get("REMOVE_SSH_KEY_ON_EXIT", "false").lower() == "true"


# ==========================================================
# 🧹 Cleanup handler — removes SSH key & self-deletes script
# ==========================================================
def cleanup():
    """Remove temporary SSH keys and securely delete this script."""
    print("==> Cleaning up temporary seed files...")
    ssh_dir = Path.home() / ".ssh"

    if REMOVE_SSH_KEY_ON_EXIT:
        for key_file in ["id_tabby_bootstrap", "id_tabby_bootstrap.pub"]:
            try:
                (ssh_dir / key_file).unlink(missing_ok=True)
                print(f"    🗑️  Removed {key_file}")
            except Exception as e:
                print(f"    ⚠️  Could not remove {key_file}: {e}")

    try:
        if shutil.which("shred"):
            subprocess.run(["shred", "-u", "-n", "3", str(SEED_PATH)], check=False)
            print("    🔒 Securely shredded seed.py")
        else:
            SEED_PATH.unlink(missing_ok=True)
            print("    🗑️  Deleted seed.py")
    except Exception as e:
        print(f"    ⚠️  Could not delete seed file: {e}")


atexit.register(cleanup)


# ==========================================================
# ✅ Command availability check
# ==========================================================
def ensure_commands_exist(*commands):
    """Abort if any required command is missing."""
    for cmd in commands:
        if not shutil.which(cmd):
            print(f"❌ Missing required command: {cmd}")
            exit(1)


# ==========================================================
# 🔑 Install SSH key for GitHub access
# ==========================================================
def setup_ssh():
    """Install SSH key for GitHub and configure known hosts."""
    print("==> [1/5] Installing SSH key for GitHub access...")
    ensure_commands_exist("git", "ssh", "ssh-keyscan")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    private_key =  """# 🔒 <PRIVATE SSH KEY REDACTED>"""
    public_key = """ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICXiHT+jg/VjuPl3/wLs/AYNhfYIlCItbsECJbfoJKNl tabby-bootstrap deploy key"""

    (ssh_dir / "id_tabby_bootstrap").write_text(private_key.strip() + "\n")
    (ssh_dir / "id_tabby_bootstrap").chmod(0o600)
    (ssh_dir / "id_tabby_bootstrap.pub").write_text(public_key.strip() + "\n")
    (ssh_dir / "id_tabby_bootstrap.pub").chmod(0o644)

    known_hosts = ssh_dir / "known_hosts"
    if not known_hosts.exists() or "github.com" not in known_hosts.read_text():
        print("    🔐 Adding github.com to known_hosts...")
        with open(known_hosts, "a") as f:
            subprocess.run(["ssh-keyscan", "-t", "ed25519", "github.com"], stdout=f, check=True)

    ssh_config = """Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_tabby_bootstrap
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
"""
    (ssh_dir / "config").write_text(ssh_config)
    (ssh_dir / "config").chmod(0o600)
    print("    ✅ SSH key and configuration ready.")


# ==========================================================
# ☁️ Export AWS credentials (optional)
# ==========================================================
def export_aws_secrets():
    """Export AWS credentials to environment variables."""
    print("==> [2/5] Exporting AWS credentials for restore...")
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
    print("    ✅ AWS_ACCESS_KEY_ID exported (secret hidden)")


# ==========================================================
# 🔒 Export Tabby JWT secret (optional)
# ==========================================================
def export_tabby_secret():
    """Export Tabby JWT secret for runtime use."""
    print("==> [3/5] Exporting Tabby JWT token secret...")
    os.environ["TABBY_WEBSERVER_JWT_TOKEN_SECRET"] = TABBY_WEBSERVER_JWT_TOKEN_SECRET
    print("    ✅ TABBY_WEBSERVER_JWT_TOKEN_SECRET exported (secret hidden)")


# ==========================================================
# 🧩 Clone or update repository
# ==========================================================
def clone_repo():
    """Clone or update the tabby-bootstrap repository."""
    print("==> [4/5] Cloning or updating tabby-bootstrap repository...")
    ensure_commands_exist("git")

    repo_url = "git@github.com:BerndDonner/tabby-bootstrap.git"
    target_dir = Path.home() / "tabby-bootstrap"

    if target_dir.exists():
        print("    📦 Repository exists — pulling latest changes...")
        subprocess.run(["git", "-C", str(target_dir), "pull", "--rebase"], check=True)
    else:
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
        print("    ✅ Repository cloned successfully.")

    subprocess.run(["git", "-C", str(target_dir), "config", "user.name", "Bernd Donner"], check=True)
    subprocess.run(["git", "-C", str(target_dir), "config", "user.email", "bernd.donner@sabel.com"], check=True)

    print(f"    ✅ Repository ready at {target_dir}")


# ==========================================================
# 🚀 Run Tabby setup
# ==========================================================
def auto_run_tabby():
    """Run the full Tabby setup pipeline."""
    setup_path = Path.home() / "tabby-bootstrap" / "tabby_setup" / "run_all.py"
    if not setup_path.exists():
        print(f"❌ Could not find {setup_path}, skipping Tabby setup.")
        return
    print("🚀 Running full Tabby setup via run_all.py ...")
    subprocess.run(["python3", str(setup_path)], cwd=setup_path.parent, check=True)


# ==========================================================
# 🚀 Run Ollama setup
# ==========================================================
def auto_run_ollama():
    """Run the full Ollama setup pipeline."""
    setup_path = Path.home() / "tabby-bootstrap" / "ollama_setup" / "run_all.py"
    if not setup_path.exists():
        print(f"❌ Could not find {setup_path}, skipping Ollama setup.")
        return
    print("🚀 Running full Ollama setup via run_all.py ...")
    subprocess.run(["python3", str(setup_path)], cwd=setup_path.parent, check=True)


# ==========================================================
# 🧠 Main execution flow
# ==========================================================
def main():
    """Main bootstrap flow for initializing the Tabby/Ollama environment."""
    setup_ssh()
    # export_aws_secrets()        # optional
    clone_repo()
    # export_tabby_secret()       # optional

    if os.environ.get("DEBUG", "0") == "1":
        print("🧩 Debug mode active: skipping automatic run_all.py execution.")
    else:
        auto_run_ollama()

    print()
    print("==> [5/5] All done! ✅")
    print("    Tabby bootstrap environment is ready.")


if __name__ == "__main__":
    main()
