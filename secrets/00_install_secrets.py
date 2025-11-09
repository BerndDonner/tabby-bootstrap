#!/usr/bin/env python3
# =====================================================================
# 🔐 00_install_secrets.py
# ---------------------------------------------------------------------
# PURPOSE:
#   Install all runtime secrets and SSH keys needed for Tabby bootstrap.
#   This replaces the secret-handling portion of seed.sh.
#
#   - Writes AWS credentials into ~/.aws
#   - Installs the deploy SSH key into ~/.ssh
#   - Exports TABBY_WEBSERVER_JWT_TOKEN_SECRET
#   - Removes itself on success
#
# ---------------------------------------------------------------------
# USAGE:
#   python3 secrets/00_install_secrets.py
#
# ---------------------------------------------------------------------
# SECRET BLOCK (redacted for Git safety):
#   These values will be injected automatically by
#   utils/inject-secrets.sh and sanitized by strip-secrets.sh.
# ---------------------------------------------------------------------

# -----BEGIN SECRET ENV-----
# <redacted line inside SECRET ENV block>
# <redacted line inside SECRET ENV block>
# <redacted line inside SECRET ENV block>
# -----END SECRET ENV-----

# 🔒 <PRIVATE SSH KEY REDACTED>

# ---------------------------------------------------------------------
# SAFETY NOTES:
#   - Purely local: no secrets are logged or transmitted.
#   - Compatible with Git clean/smudge filters.
#   - Self-deletes (os.remove()) after successful installation.
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

import os
from pathlib import Path


def main():
    print("==> [1/1] Installing secrets and SSH configuration...")

    home = Path.home()
    ssh_dir = home / ".ssh"
    aws_dir = home / ".aws"

    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    aws_dir.mkdir(mode=0o700, exist_ok=True)

    # --- Validate secrets ---
    if "<REDACTED>" in (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        TABBY_WEBSERVER_JWT_TOKEN_SECRET,
    ):
        print("❌ This file still contains redacted secrets. Run utils/inject-secrets.sh first.")
        exit(1)

    # --- AWS credentials ---
    (aws_dir / "credentials").write_text(
        f"[hetzner]\n"
        f"aws_access_key_id = {AWS_ACCESS_KEY_ID}\n"
        f"aws_secret_access_key = {AWS_SECRET_ACCESS_KEY}\n"
    )
    (aws_dir / "config").write_text("[profile hetzner]\nregion = fsn1\noutput = json\n")
    print("✅ AWS credentials written to ~/.aws")

    # --- SSH key ---
    ssh_key_path = ssh_dir / "id_tabby_bootstrap"
    private_key = """-----BEGIN OPENSSH PRIVATE KEY-----
<REDACTED>
-----END OPENSSH PRIVATE KEY-----
"""
    if "<REDACTED>" in private_key:
        print("❌ Private SSH key missing. Run inject-secrets.sh first.")
        exit(1)

    ssh_key_path.write_text(private_key)
    os.chmod(ssh_key_path, 0o600)

    (ssh_dir / "config").write_text(
        "Host github.com\n"
        "    HostName github.com\n"
        "    User git\n"
        "    IdentityFile ~/.ssh/id_tabby_bootstrap\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking no\n"
    )
    print("✅ SSH configuration ready for GitHub access")

    # --- Export JWT secret ---
    os.environ["TABBY_WEBSERVER_JWT_TOKEN_SECRET"] = TABBY_WEBSERVER_JWT_TOKEN_SECRET
    print("✅ Tabby JWT secret exported")

    # --- Self-delete ---
    this_file = Path(__file__)
    try:
        os.remove(this_file)
        print(f"🧹 Removed {this_file}")
    except Exception as e:
        print(f"⚠️ Could not delete {this_file}: {e}")

    print("🎉 Secrets installation complete!")


if __name__ == "__main__":
    main()

