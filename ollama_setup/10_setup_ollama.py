#!/usr/bin/env python3
# =====================================================================
# 🧠  10_setup_ollama.py — Install Ollama and Required Models
# =====================================================================
# PURPOSE:
#   Bootstraps Ollama on a fresh GPU instance and ensures that
#   required models for Tabby/Continue are downloaded.
#
# ACTIONS:
#   1. Install Ollama if missing.
#   2. Ensure Ollama service (systemd or manual) is running.
#   3. Pull required models:
#        - deepseek-coder:6.7b  (autocomplete)
#        - qwen2.5-coder:7b     (chat & reasoning)
#   4. Optionally remove unused or legacy models.
#   5. Print next-step instructions for Continue/VS Code setup.
#
# CLI:
#   python3 ollama_setup/10_setup_ollama.py
#
# FUNCTIONAL USE:
#   from ollama_setup import 10_setup_ollama
#   10_setup_ollama.main()
# =====================================================================

import subprocess
import shutil
import sys
import os
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
        if check:
            sys.exit(1)
        return ""


# ==========================================================
# 🧱 Install Ollama (if missing)
# ==========================================================
def ensure_ollama_installed():
    if shutil.which("ollama"):
        log("✅ Ollama binary already present.")
        return

    log("⬇️  Ollama not found — installing now ...")
    run(
        ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
        check=True,
    )

    if not shutil.which("ollama"):
        log("❌ Installation failed: Ollama binary not found after install.")
        sys.exit(1)

    log("✅ Ollama successfully installed.")


# ==========================================================
# ⚙️  Ensure Ollama service or process is running
# ==========================================================
def ensure_ollama_running():
    # try systemd first
    if shutil.which("systemctl"):
        status = run(["systemctl", "is-active", "ollama"], check=False, capture_output=True)
        if status.strip() != "active":
            log("⚙️  Ollama service not active — attempting to start...")
            run(["sudo", "systemctl", "start", "ollama"], check=False)
        else:
            log("✅ Ollama systemd service is active.")
        return

    # fallback: check if process is running
    ps = run(["ps", "-A"], capture_output=True)
    if "ollama" not in ps:
        log("⚙️  Starting Ollama manually in background ...")
        subprocess.Popen(["ollama", "serve"])
    else:
        log("✅ Ollama process already running.")


# ==========================================================
# 📦  Ensure required models exist
# ==========================================================
def ensure_models_installed():
    existing = run(["ollama", "list"], capture_output=True).splitlines()
    existing_models = {line.split()[0] for line in existing if line.strip() and not line.startswith("NAME")}

    for model, role in REQUIRED_MODELS.items():
        if model in existing_models:
            log(f"✅ {model} ({role}) already installed.")
        else:
            log(f"⬇️  Pulling {model} for {role} — this may take several minutes ...")
            run(["ollama", "pull", model])
            log(f"✅ {model} installed.")


# ==========================================================
# 🧹  Remove unused models (optional)
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
    ensure_ollama_installed()
    ensure_ollama_running()
    ensure_models_installed()
    cleanup_unused_models()

    log("\n🎉 Ollama models ready!")
    for model, role in REQUIRED_MODELS.items():
        log(f"   ➤ {model:<20} — {role}")

    log("\n🧩 Next step:")
    log("   1. On your local machine, open VS Code.")
    log("   2. Install the Continue extension (if not yet installed).")
    log("   3. Edit ~/.continue/config.yaml to use provider: ollama")
    log("   4. Restart VS Code to connect to this host.")
    log("\n🌍 Ensure firewall port 11434/tcp is open for your IP (done on Lambda).")


if __name__ == "__main__":
    main()
