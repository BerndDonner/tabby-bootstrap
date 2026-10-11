#!/usr/bin/env python3
"""Validate a bootstrap deployment and write its secret JSON only to SSH stdin."""

import argparse
import ipaddress
import json
import os
import sys
from pathlib import Path

from task_runner import load_manifest

TARGETS = {"ollama", "tabby"}


def create_payload(target, remote_ip, debug, commit, branch, environ=None, repo=None):
    env = os.environ if environ is None else environ
    root = Path(__file__).resolve().parent if repo is None else Path(repo)
    if target not in TARGETS:
        raise ValueError(f"Unsupported target: {target!r}")
    try:
        ipaddress.ip_address(remote_ip)
    except ValueError as exc:
        raise ValueError("REMOTE_IP must be an IP address") from exc
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("Invalid Git commit SHA")
    if not isinstance(branch, str) or not branch:
        raise ValueError("Missing local branch metadata")
    if target == "tabby" and not debug:
        raise ValueError("Tabby production setup is not configured. Use --debug only.")

    # Tabby has no live credentials or supported DAG yet; safe debug-only snapshot.
    tasks = load_manifest(root / "ollama_setup" / "tasks.json", root) if target == "ollama" else {}
    required = sorted({secret for task in tasks.values() for secret in task["secrets"]})
    missing = [name for name in required if not env.get(name) or env[name] == "<REDACTED>"]
    if missing:
        raise ValueError("Missing required secrets: " + ", ".join(missing) + ". Enter the target devShell.")

    return {"target": target, "remote_ip": remote_ip, "commit": commit,
            "branch": branch, "debug": bool(debug),
            "env": {name: env[name] for name in required}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--remote-ip", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = create_payload(args.target, args.remote_ip, args.debug,
                                 args.commit, args.branch)
    except (OSError, ValueError) as exc:
        print(f"Bootstrap preflight error: {exc}", file=sys.stderr)
        return 1
    if not args.validate_only:
        json.dump(payload, sys.stdout, ensure_ascii=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
