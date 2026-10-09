#!/usr/bin/env python3
"""Remote first-stage bootstrap for temporary Lambda GPU instances.

A small, non-secret Python script copied via SCP. It receives all secrets as
one JSON document on SSH stdin. It installs the temporary GitHub SSH key,
clones tabby-bootstrap, and runs the chosen target's setup sequence.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_URL = "git@github.com:BerndDonner/tabby-bootstrap.git"
TARGET_RUNNERS = {
    "ollama": "ollama_setup",
    "tabby": "tabby_setup",
}


def setup_ssh(private_key):
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    ssh_dir.chmod(0o700)
    private_path = ssh_dir / "id_tabby_bootstrap"
    # Exclusive creation with 0600; replacing an existing private key is fine
    # on the disposable VM, but permissions must be restrictive from the start.
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(private_key.rstrip("\n") + "\n")
    private_path.chmod(0o600)

    # Keep the original bootstrap's GitHub configuration. The VM is freshly
    # created, so it is safe to dedicate ~/.ssh/config to this purpose.
    config_path = ssh_dir / "config"
    config_path.write_text(
        "Host github.com\n"
        "    HostName github.com\n"
        "    User git\n"
        "    IdentityFile ~/.ssh/id_tabby_bootstrap\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking accept-new\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    # Keep the original host-key acquisition behavior for now.
    known_hosts = ssh_dir / "known_hosts"
    if not known_hosts.exists() or "github.com" not in known_hosts.read_text(encoding="utf-8"):
        with known_hosts.open("a", encoding="utf-8") as f:
            subprocess.run(["ssh-keyscan", "-t", "ed25519", "github.com"],
                           stdout=f, check=True)


def clone_repo(ref):
    target_dir = Path.home() / "tabby-bootstrap"
    if not target_dir.is_dir():
        subprocess.run(["git", "clone", REPO_URL, str(target_dir)], check=True)
    subprocess.run(["git", "-C", str(target_dir), "fetch", "origin", "--prune", "--tags"], check=True)
    # A remote feature branch is selected deterministically, including on
    # subsequent runs. Tags or commit SHA values run in detached HEAD.
    remote_ref = f"refs/remotes/origin/{ref}"
    is_remote_branch = subprocess.run(
        ["git", "-C", str(target_dir), "show-ref", "--verify", "--quiet", remote_ref],
        check=False,
    ).returncode == 0
    if is_remote_branch:
        subprocess.run(["git", "-C", str(target_dir), "checkout", "-B", ref,
                        f"origin/{ref}"], check=True)
    else:
        subprocess.run(["git", "-C", str(target_dir), "checkout", "--detach", ref], check=True)
    print(f"Repository ready: {target_dir} at {ref}", flush=True)


def run_setup(target):
    setup_path = Path.home() / "tabby-bootstrap" / TARGET_RUNNERS[target] / "run_all.py"
    if not setup_path.is_file():
        raise FileNotFoundError(setup_path)
    print(f"Running {target} setup ...", flush=True)
    subprocess.run(["python3", str(setup_path)], cwd=setup_path.parent, check=True)


def main():
    payload = json.load(sys.stdin)
    target = payload.get("target")
    if target not in TARGET_RUNNERS:
        raise ValueError(f"Unsupported target: {target!r}")
    env = payload.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                             for k, v in env.items()):
        raise ValueError("Invalid environment data")
    for name in env:
        if not name.isidentifier():
            raise ValueError(f"Invalid environment variable: {name!r}")

    ref = payload.get("ref", "master")
    os.environ.update(env)
    os.environ["REMOTE_IP"] = payload["remote_ip"]
    os.environ["CF_DNS_NAME"] = "ai.donner-lab.org"

    print(f"GPU bootstrap: {target} / ref {ref}", flush=True)
    setup_ssh(payload["git_ssh_key"])
    clone_repo(ref)

    if payload.get("debug", False):
        print("Debug mode: cloned repository, skipping setup.", flush=True)
    else:
        run_setup(target)
    print(f"Bootstrap finished: {target}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
