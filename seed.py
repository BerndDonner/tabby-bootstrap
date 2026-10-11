#!/usr/bin/env python3
"""Remote entrypoint for a *locally archived*, checksum-verified code snapshot.

The SSH stdin JSON carries secrets only; no GitHub login or remote Git clone.
Normal mode keeps secrets in memory. Debug mode saves a protected context for
manual task execution and leaves all application tasks untouched.
"""

import json
import os
from pathlib import Path
import sys

import task_runner


def write_debug_context(payload, path=task_runner.DEBUG_CONTEXT):
    path = Path(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.parent.chmod(0o700)
    # Atomic replacement; never expose an existing world-readable file.
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix=".debug-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
            stream.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(stdin=None, root=None):
    stream = sys.stdin if stdin is None else stdin
    root = Path(__file__).resolve().parent if root is None else Path(root)
    payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")
    target = payload.get("target")
    if target not in ("ollama", "tabby"):
        raise ValueError("Unsupported target")
    env = payload.get("env")
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("Invalid secret payload")
    remote_ip = payload.get("remote_ip")
    import ipaddress
    ipaddress.ip_address(remote_ip)
    context = {key: payload[key] for key in ("target", "remote_ip", "commit", "branch", "env", "debug")}
    print(f"GPU bootstrap: {target}, local commit {context['commit']} ({context['branch']})", flush=True)
    if context["debug"]:
        write_debug_context(context)
        print("Debug ready. No DNS, installation or model downloads started.", flush=True)
        print("SSH login → cd ~/tabby-bootstrap → python3 task_runner.py --list", flush=True)
        return 0
    # An earlier debug deployment on the same VM must not leave credentials on disk.
    task_runner.DEBUG_CONTEXT.unlink(missing_ok=True)
    if target != "ollama":
        raise ValueError("Tabby production setup is disabled. Use --debug.")
    success = task_runner.execute(target, env, context, root)
    if not success:
        raise RuntimeError("One or more bootstrap tasks failed")
    # Snapshot archive is useful in debug only; normal deployment can discard it.
    (Path.home() / "tabby-bootstrap-source.tar").unlink(missing_ok=True)
    print(f"Bootstrap ready: {target}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
