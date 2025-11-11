#!/usr/bin/env python3
# =====================================================================
# 🧠  10_setup_ollama.py — Prepare Ollama Models for Continue/Tabby
# =====================================================================
# PURPOSE:
#   Installs and verifies required Ollama models on a GPU instance.
#   Intended for Hetzner / Lambda / Scaleway ephemeral deployments.
#
# ACTIONS:
#   1. Ensure Ollama is installed and running.
#   2. Pull required models if missing:
#        - deepseek-coder:6.7b  (autocomplete)
#        - qwen2.5-coder:7b     (chat & reasoning)
#   3. Remove any unused or legacy models (optional cleanup).
#   4. Print next-step instructions for VS Code Continue setup.
#
# USAGE:
#   python3 ollama/10_setup_ollama.py
#
# ---------------------------------------------------------------------
# DEPENDENCIES:
#   - ollama must already be installed and active (systemd or manual)
#   - firewall ports already open (done on Lambda panel)
# ---------------------------------------------------------------------

import subprocess
import shutil
import sys
from pathlib import Path

# ==========================================================
# 🔧 Configuration
# ==========================================================
REQUIRED_MODELS = {
    "deepseek-coder:6.7b": "autocomplete",
    "qwen2.5-coder:7b": "chat",
}

# ==========================================================
# 🧩 Utility helpers
# ==========================================================
def log(msg: str):
    print(msg, flush=True)


def run(cmd: list[str], check=True, capture_output=False):
    """Run a shell command with clean error output."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
        )
        return result.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        log(f"❌ Command failed: {' '.join(cmd)}")
        if e.stdout:
            log(e.stdout)
        if e.stderr:
            log(e.stderr)
        sys.exit(1)


# ==========================================================
# ⚙️  Check Ollama installation
# ==========================================================
def ensure_ollama_running():
    if not shutil.which("ollama"):
        log("❌ Ollama binary not found in PATH.")
        log("   Install via: curl -fsSL https://ollama.com/install.sh | sh")
        sys.exit(1)

    status = run(["systemctl", "is-active", "ollama"], check=False, capture_output=True)
    if status.strip() != "active":
        log("⚠️ Ollama service not active — attempting to start...")
        run(["sudo", "systemctl", "start", "ollama"], check=False)
    log("✅ Ollama service is running.")


# ==========================================================
# 📦  Ensure required models exist
# ==========================================================
def ensure_models_installed():
    existing = run(["ollama", "list"], capture_output=True).splitlines()
    existing_models = {line.split()[0] for line in existing if line.strip()}

    for model, role in REQUIRED_MODELS.items():
        if model in existing_models:
            log(f"✅ {model} ({role}) already installed.")
        else:
            log(f"⬇️ Pulling {model} for {role} ... this may take several minutes.")
            run(["ollama", "pull", model])
            log(f"✅ {model} installed.")


# ==========================================================
# 🧹  Remove unused models
# ==========================================================
def cleanup_unused_models():
    log("🧹 Checking for unused models ...")
    existing = run(["ollama", "list"], capture_output=True).splitlines()
    for line in existing:
        if not line.strip() or line.startswith("NAME"):
            continue
        name = line.split()[0]
        if name not in REQUIRED_MODELS:
            log(f"   Removing unused model: {name}")
            run(["ollama", "rm", name])
    log("✅ Cleanup complete.")


# ==========================================================
# 🧭  Main entry point
# ==========================================================
def main():
    log("🚀 Starting Ollama setup ...")
    ensure_ollama_running()
    ensure_models_installed()
    cleanup_unused_models()

    log("\n🎉 Ollama models ready!")
    log("   ➤ deepseek-coder:6.7b  — autocomplete")
    log("   ➤ qwen2.5-coder:7b     — chat")
    log("\n🧩 Next step:")
    log("   1. On your local machine, open VS Code.")
    log("   2. Install the Continue extension (if not yet installed).")
    log("   3. Edit ~/.continue/config.yaml to use provider: ollama")
    log("   4. Restart VS Code to connect to this host.")
    log("\n🌍 Ensure firewall port 11434/tcp is open for your IP (done on Lambda).")


if __name__ == "__main__":
    main()

