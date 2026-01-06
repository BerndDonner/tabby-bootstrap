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
#   Mandatory steps performed:
#     1. Installing the deploy SSH key into ~/.ssh
#     2. Exporting Cloudflare DNS config for ai.donner-lab.org
#     3. Cloning or updating the tabby-bootstrap repository
#     4. Automatically running one of the setup sequences:
#          - ~/tabby-bootstrap/ollama_setup/run_all.py   (default)
#          - ~/tabby-bootstrap/tabby_setup/run_all.py    (if adapted)
#     5. Finalizing and leaving a clean bootstrap environment
#
#   Optional extras (not counted in the [1/5..5/5] progress):
#     - Exporting AWS credentials
#     - Exporting TABBY_WEBSERVER_JWT_TOKEN_SECRET
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
#   - Cloudflare secrets are required for automatic DNS updates
#     via downstream scripts in ollama_setup/tabby_setup.
#   - AWS and JWT secrets are optional if handled elsewhere.
#   - Uses "StrictHostKeyChecking accept-new" for first-time SSH safety.
#   - Supports automatic cleanup and self-deletion via atexit.
#   - Only sets environment variables; all real work happens in
#     tabby-bootstrap/{ollama_setup,tabby_setup}.
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
CF_API_TOKEN = "<REDACTED>"
CF_ZONE_ID = "<REDACTED>"
# -----END SECRET ENV-----

CF_DNS_NAME = "ai.donner-lab.org"
SEED_PATH = Path(__file__).resolve()
REMOVE_SSH_KEY_ON_EXIT = os.environ.get("REMOVE_SSH_KEY_ON_EXIT", "false").lower() == "true"


# ==========================================================
# 🧹 Cleanup handler — removes SSH key & self-deletes script
# ==========================================================
def cleanup():
    """Remove temporary SSH keys and (best-effort) delete this script."""
    print("==> Cleaning up temporary seed files...")
    ssh_dir = Path.home() / ".ssh"

    # Optionally remove the temporary deploy key from ~/.ssh
    if REMOVE_SSH_KEY_ON_EXIT:
        for key_file in ["id_tabby_bootstrap", "id_tabby_bootstrap.pub"]:
            try:
                (ssh_dir / key_file).unlink(missing_ok=True)
                print(f"    🗑️  Removed {key_file}")
            except Exception as e:
                print(f"    ⚠️  Could not remove {key_file}: {e}")

    # Best-effort removal of the seed script itself
    try:
        # Make sure the file is owner-writable so shred/unlink can work,
        # even if it was uploaded as read-only from the local machine.
        try:
            SEED_PATH.chmod(0o700)
        except Exception as e:
            print(f"    ⚠️  Could not chmod seed.py before delete: {e}")

        if shutil.which("shred"):
            # Try secure delete; check exit code explicitly
            result = subprocess.run(
                ["shred", "-u", "-n", "3", str(SEED_PATH)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                print("    🔒 Securely shredded seed.py")
                return
            else:
                print(
                    f"    ⚠️  shred failed (exit code {result.returncode}), "
                    "falling back to plain delete..."
                )

        # Either shred is not available or it failed → plain delete
        SEED_PATH.unlink(missing_ok=True)
        print("    🗑️  Deleted seed.py (no secure shred)")

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
    print("==> Exporting AWS credentials for restore (optional)...")
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
    print("    ✅ AWS_ACCESS_KEY_ID exported (secret hidden)")


# ==========================================================
# 🔒 Export Tabby JWT secret (optional)
# ==========================================================
def export_tabby_secret():
    """Export Tabby JWT secret for runtime use."""
    print("==> Exporting Tabby JWT token secret (optional)...")
    os.environ["TABBY_WEBSERVER_JWT_TOKEN_SECRET"] = TABBY_WEBSERVER_JWT_TOKEN_SECRET
    print("    ✅ TABBY_WEBSERVER_JWT_TOKEN_SECRET exported (secret hidden)")


# ==========================================================
# 🌐 Export Cloudflare DNS config
# ==========================================================
def export_cloudflare_secrets():
    """
    Export Cloudflare-related configuration to environment variables.

    These are later used by scripts in ollama_setup/tabby_setup to
    update ai.donner-lab.org → REMOTE_IP via Cloudflare API.
    """
    print("==> [2/5] Exporting Cloudflare DNS configuration...")
    if CF_API_TOKEN and CF_ZONE_ID:
        os.environ["CF_API_TOKEN"] = CF_API_TOKEN
        os.environ["CF_ZONE_ID"] = CF_ZONE_ID
        os.environ["CF_DNS_NAME"] = CF_DNS_NAME
        print("    ✅ CF_API_TOKEN / CF_ZONE_ID / CF_DNS_NAME exported (secrets hidden)")
    else:
        print("    ⚠️  CF_API_TOKEN / CF_ZONE_ID not set — Cloudflare DNS updates will not work.")


# ==========================================================
# 🧩 Clone or update repository
# ==========================================================
def clone_repo():
    """Clone or update the tabby-bootstrap repository.

    The seed script clones this repository by default.
    For low-noise testing, an optional ref can be provided via:
      TABBY_BOOTSTRAP_REF=<branch|tag|sha>
    """
    print("==> [3/5] Cloning or updating tabby-bootstrap repository...")
    ensure_commands_exist("git")

    repo_url = "git@github.com:BerndDonner/tabby-bootstrap.git"
    target_dir = Path.home() / "tabby-bootstrap"

    ref = os.environ.get("TABBY_BOOTSTRAP_REF", "master")

    if target_dir.exists():
        print("    📦 Repository exists — fetching latest changes...")
        subprocess.run(["git", "-C", str(target_dir), "fetch", "--all", "--tags"], check=True)
    else:
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
        print("    ✅ Repository cloned successfully.")

    print(f"    🔎 Checking out ref: {ref}")
    subprocess.run(["git", "-C", str(target_dir), "checkout", ref], check=True)

    # Best effort update if ref is a branch
    try:
        subprocess.run(["git", "-C", str(target_dir), "pull", "--rebase"], check=True)
    except subprocess.CalledProcessError:
        print("    ℹ️  Detached ref (tag/SHA). Skipping pull --rebase.")

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
    print("==> [4/5] Running full Tabby setup via run_all.py ...")
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
    print("==> [4/5] Running full Ollama setup via run_all.py ...")
    subprocess.run(["python3", str(setup_path)], cwd=setup_path.parent, check=True)


# ==========================================================
# 🧠 Main execution flow
# ==========================================================
def main():
    """Main bootstrap flow for initializing the Tabby/Ollama environment."""
    setup_ssh()
    export_cloudflare_secrets()
    # export_aws_secrets()        # optional
    # export_tabby_secret()       # optional
    clone_repo()

    if os.environ.get("DEBUG", "0") == "1":
        print("🧩 Debug mode active: skipping automatic run_all.py execution.")
    else:
        auto_run_ollama()

    print()
    print("==> [5/5] All done! ✅")
    print("    Tabby bootstrap environment is ready.")


if __name__ == "__main__":
    main()
