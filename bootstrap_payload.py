#!/usr/bin/env python3
"""Build the in-memory JSON payload for the remote, target-agnostic seed.py.

The JSON is written to stdout *only* so it can be piped directly into SSH.
Never print it in a terminal, log it, or store it in a file.
"""

import argparse
import ipaddress
import json
import os
import sys
from pathlib import Path


TARGET_VARIABLES = {
    "ollama": ("CF_API_TOKEN", "CF_ZONE_ID"),
    "tabby": (),  # Historical S3/JWT secrets no longer valid; not configured.
}


def create_payload(target, remote_ip, ref, debug, key_path, environ=None):
    env = os.environ if environ is None else environ
    if target not in TARGET_VARIABLES:
        raise ValueError(f"Unknown BOOTSTRAP_TARGET: {target!r}")

    try:
        ipaddress.ip_address(remote_ip)
    except ValueError as exc:
        raise ValueError("REMOTE_IP must be an IP address") from exc

    if target == "tabby" and not debug:
        raise ValueError(
            "Tabby is not configured yet (old AWS/Hetzner credentials expired). "
            "For a safe clone-only test, run with --debug."
        )

    required = TARGET_VARIABLES[target]
    missing = [name for name in required if not env.get(name) or env[name] == "<REDACTED>"]
    if missing:
        raise ValueError("Missing required Ollama secrets: " + ", ".join(missing) +
                         ". Enter 'nix develop' after migrating cloudflare.sops.env.")

    private_key = Path(key_path).expanduser().read_text(encoding="utf-8")
    if not private_key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----") and \
       not private_key.startswith("-----BEGIN RSA PRIVATE KEY-----"):
        raise ValueError("GitHub deploy key does not look like a private SSH key")

    return {
        "target": target,
        "remote_ip": remote_ip,
        "ref": ref,
        "debug": debug,
        "env": {name: env[name] for name in required},
        "git_ssh_key": private_key,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=tuple(TARGET_VARIABLES))
    parser.add_argument("--remote-ip", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--key-path", required=True)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    try:
        payload = create_payload(args.target, args.remote_ip, args.ref, args.debug, args.key_path)
    except (OSError, ValueError) as exc:
        print(f"Bootstrap preflight error: {exc}", file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
