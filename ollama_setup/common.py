"""Shared, non-secret helpers for independently executable Ollama setup tasks."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

MODELS = {
    "deepseek-coder:6.7b": "autocomplete",
    "qwen2.5-coder:7b": "chat",
}


def log(message):
    print(message, flush=True)


def run(args, *, capture=False, check=True, env=None):
    result = subprocess.run(args, check=check, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, env=env)
    return result.stdout.strip() if capture else ""


def install_ollama():
    if shutil.which("ollama"):
        log("Ollama binary already installed")
        return
    log("Installing Ollama...")
    # Preserve official installer, but propagate curl failure (pipefail).
    run(["bash", "-o", "pipefail", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
    if not shutil.which("ollama"):
        raise RuntimeError("Ollama installer returned success but binary is missing")


def configure_and_start():
    if shutil.which("systemctl"):
        # A running systemd manager is required; merely finding the binary is not enough.
        state = subprocess.run(["systemctl", "show-environment"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if state.returncode == 0:
            override = Path("/etc/systemd/system/ollama.service.d/override.conf")
            desired = '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n'
            current = subprocess.run(["sudo", "cat", str(override)],
                                     capture_output=True, text=True)
            if current.returncode != 0 or current.stdout != desired:
                log("Configuring Ollama systemd override (0.0.0.0:11434)")
                run(["sudo", "mkdir", "-p", str(override.parent)])
                # Write override via root stdin, not through world-readable /tmp.
                subprocess.run(["sudo", "tee", str(override)], input=desired,
                               text=True, stdout=subprocess.DEVNULL, check=True)
                run(["sudo", "systemctl", "daemon-reload"])
            run(["sudo", "systemctl", "restart", "ollama"])
            wait_for_ollama()
            return
    # Best-effort non-systemd fallback. Container port mapping remains hoster-specific.
    log("No running systemd manager: starting Ollama as detached process")
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "0.0.0.0:11434"
    logpath = Path.home() / "ollama-serve.log"
    with logpath.open("ab") as outfile:
        subprocess.Popen(["ollama", "serve"], env=env, start_new_session=True,
                         stdout=outfile, stderr=subprocess.STDOUT)
    wait_for_ollama()


def wait_for_ollama(timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
                if response.status == 200:
                    log("Ollama API is responding")
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError("Ollama API did not become ready")


def pull_model(model):
    """Pull through Ollama's newline-delimited JSON API, not its animated CLI.

    The CLI redraws multiple terminal lines and produces hundreds of duplicate
    messages when two downloads run under our line-oriented scheduler logger.
    Ollama's API exposes the same underlying download as structured updates.
    """
    found = run(["ollama", "list"], capture=True).splitlines()
    if any(line.split() and line.split()[0] == model for line in found[1:]):
        log(f"Already installed: {model}")
        return

    log(f"Pulling {model} ...")
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/pull",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    current_phase = None
    last_percent = None
    last_report = 0.0
    successful = False
    with urllib.request.urlopen(request, timeout=180) as response:
        for line in response:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError(f"Ollama pull failed for {model}: {event['error']}")
            phase = event.get("status")
            if phase == "success":
                successful = True
                break
            if not phase:
                continue

            now = time.monotonic()
            if phase != current_phase:
                current_phase = phase
                last_percent = None
                last_report = 0.0

            total = event.get("total")
            completed = event.get("completed")
            if isinstance(total, (int, float)) and total > 0 and isinstance(completed, (int, float)):
                percent = min(100, max(0, int(100 * completed / total)))
                # Always report first/last progress, but sample intermediate updates.
                if (last_percent is None or now - last_report >= 2.0
                        or percent == 100 and last_percent != 100):
                    log(f"{phase}: {percent}% ({completed / 1e9:.2f}/{total / 1e9:.2f} GB)")
                    last_percent = percent
                    last_report = now
            elif last_percent is None:
                log(phase)
                last_percent = -1  # Suppress repeated spinner/status updates.

    if not successful:
        raise RuntimeError(f"Ollama pull ended without success: {model}")
    log(f"Pulled {model}")


def check_models():
    found = run(["ollama", "list"], capture=True).splitlines()
    installed = {line.split()[0] for line in found[1:] if line.split()}
    missing = set(MODELS) - installed
    if missing:
        raise RuntimeError("Missing Ollama models: " + ", ".join(sorted(missing)))
    log("Both models installed; local API responding")


def cleanup_unused_models():
    found = run(["ollama", "list"], capture=True).splitlines()
    for line in found[1:]:
        parts = line.split()
        if parts and parts[0] not in MODELS:
            log(f"Removing unused model {parts[0]}")
            run(["ollama", "rm", parts[0]])
