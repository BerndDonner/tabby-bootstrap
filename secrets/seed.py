#!/usr/bin/env python3
# =====================================================================
# 🚀 seed.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Bootstrap a fresh instance for Tabby server deployment.
#   Installs secrets, SSH keys, clones the tabby-bootstrap repository,
#   and (by default) executes the full setup sequence.
#
#   This script replaces the previous 00_install_secrets.py
#   and 10_clone_repo.py stages.
#
#   Actions performed:
#     - Export AWS credentials for runtime restore
#     - Install the deploy SSH key into ~/.ssh
#     - Export TABBY_WEBSERVER_JWT_TOKEN_SECRET
#     - Clone or update the tabby-bootstrap repository
#     - Run ~/tabby-bootstrap/setup/run_all.py  (default)
#     - Remove itself on completion
#
# ---------------------------------------------------------------------
# USAGE:
#   python3 /tmp/seed.py
#
#   To run in debug mode (stop before auto-run):
#     DEBUG=1 python3 /tmp/seed.py
#
# ---------------------------------------------------------------------
# SECRET BLOCK (redacted for Git safety):
#   These values are injected automatically by
#   utils/inject-secrets.sh and sanitized by strip-secrets.sh.
# ---------------------------------------------------------------------

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
    print("==> Cleaning up temporary seed files...")
    ssh_dir = Path.home() / ".ssh"

    if REMOVE_SSH_KEY_ON_EXIT:
        for key_file in ["id_tabby_bootstrap", "id_tabby_bootstrap.pub"]:
            try:
                (ssh_dir / key_file).unlink(missing_ok=True)
            except Exception as e:
                print(f"    ⚠ Could not remove {key_file}: {e}")

    try:
        # Try secure deletion if available
        if shutil.which("shred"):
            subprocess.run(["shred", "-u", "-n", "3", str(SEED_PATH)], check=False)
        else:
            SEED_PATH.unlink(missing_ok=True)
    except Exception as e:
        print(f"    ⚠ Could not delete seed file: {e}")


atexit.register(cleanup)


# ==========================================================
# ✅ Check required commands
# ==========================================================
def ensure_commands_exist(*commands):
    for cmd in commands:
        if not shutil.which(cmd):
            print(f"❌ Missing command: {cmd}")
            exit(1)


# ==========================================================
# 🔑 Install SSH key for GitHub access
# ==========================================================
def setup_ssh():
    print("==> [1/5] Install SSH key for GitHub access")
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
    if "github.com" not in known_hosts.read_text() if known_hosts.exists() else "":
        subprocess.run(["ssh-keyscan", "-t", "ed25519", "github.com"], stdout=open(known_hosts, "a"), check=True)

    ssh_config = """Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_tabby_bootstrap
    IdentitiesOnly yes
    StrictHostKeyChecking no
"""
    (ssh_dir / "config").write_text(ssh_config)
    (ssh_dir / "config").chmod(0o600)


# ==========================================================
# ☁️ Export AWS credentials
# ==========================================================
def export_aws_secrets():
    print("==> [2/5] Export AWS credentials for restore")
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
    print("    AWS_ACCESS_KEY_ID exported (secret hidden)")


# ==========================================================
# 🧩 Clone or update repository
# ==========================================================
def clone_repo():
    print("==> [3/5] Clone or update tabby-bootstrap repository")

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


# ==========================================================
# 🔒 Export Tabby JWT secret
# ==========================================================
def export_tabby_secret():
    print("==> [4/5] Export Tabby JWT secret")
    os.environ["TABBY_WEBSERVER_JWT_TOKEN_SECRET"] = TABBY_WEBSERVER_JWT_TOKEN_SECRET
    print("    TABBY_WEBSERVER_JWT_TOKEN_SECRET exported (secret hidden)")


# ==========================================================
# 🚀 Auto-run Tabby setup
# ==========================================================
def auto_run_tabby():
    """Run the full bootstrap sequence from the cloned repository."""
    setup_path = Path.home() / "tabby-bootstrap" / "setup" / "run_all.py"
    if not setup_path.exists():
        print(f"❌ Could not find {setup_path}, aborting auto-run.")
        return
    print("🚀 Running full Tabby setup via run_all.py ...")
    subprocess.run(["python3", str(setup_path)], cwd=setup_path.parent, check=True)


# ==========================================================
# 🧠 Main execution flow
# ==========================================================
def main():
    setup_ssh()
    export_aws_secrets()
    clone_repo()
    export_tabby_secret()

    if os.environ.get("DEBUG", "0") == "1":
        print("🧩 Debug mode: skipping automatic run_all.py execution.")
    else:
        auto_run_tabby()

    print()
    print("==> [5/5] All done! ✅")
    print("    Tabby bootstrap environment ready.")


if __name__ == "__main__":
    main()
