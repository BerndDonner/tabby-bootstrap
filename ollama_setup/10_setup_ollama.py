#!/usr/bin/env python3
# =====================================================================
# 🧠  10_setup_ollama.py — Install and Configure Ollama for Tabby
# =====================================================================
# PURPOSE:
#   Bootstraps a fresh GPU instance with Ollama and the required models
#   for Tabby / Continue integration.
#
# ACTIONS:
#   1. Install Ollama if missing.
#   2. Configure Ollama to listen on all interfaces (0.0.0.0).
#   3. Ensure Ollama service (systemd or manual) is running.
#   4. Pull required models:
#        - deepseek-coder:6.7b  (autocomplete)
#        - qwen2.5-coder:7b     (chat & reasoning)
#   5. Remove any unused models.
#
# CAN BE RUN:
#   - Standalone:  python3 ollama_setup/10_setup_ollama.py
#   - From code:   from ollama_setup import 10_setup_ollama; 10_setup_ollama.main()
# =====================================================================

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
        if check:
            sys.exit(1)
        return ""


def sudo_write(path: Path, content: str):
    """Create parent dir and write file as root using sudo."""
    run(["sudo", "mkdir", "-p", str(path.parent)])
    tmp = Path("/tmp") / (path.name + ".tmp")
    tmp.write_text(content)
    run(["sudo", "mv", str(tmp), str(path)])


# ==========================================================
# 🧱 Install Ollama (if missing)
# ==========================================================
def ensure_ollama_installed():
    if shutil.which("ollama"):
        log("✅ Ollama binary already present.")
        return

    log("⬇️  Ollama not found — installing now ...")
    run(["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])

    if not shutil.which("ollama"):
        log("❌ Installation failed: Ollama binary still missing.")
        sys.exit(1)

    log("✅ Ollama successfully installed.")


# ==========================================================
# ⚙️  Configure remote access (systemd override)
# ==========================================================
def configure_remote_access():
    log("⚙  Configuring Ollama to listen on all interfaces ...")
    if not shutil.which("systemctl"):
        log("ℹ️ systemd not present; skipping override (manual start mode).")
        return

    override_dir = Path("/etc/systemd/system/ollama.service.d")
    override_file = override_dir / "override.conf"
    desired = '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n'

    current = run(["sudo", "cat", str(override_file)], check=False, capture_output=True)
    if current == desired:
        log("✅ systemd override already in place.")
        return

    sudo_write(override_file, desired)
    run(["sudo", "systemctl", "daemon-reload"])
    run(["sudo", "systemctl", "restart", "ollama"])
    log("✅ systemd override applied and service restarted.")


# ==========================================================
# ⚙️  Ensure Ollama service or process is running
# ==========================================================
def ensure_ollama_running():
    if shutil.which("systemctl"):
        status = run(["systemctl", "is-active", "ollama"], check=False, capture_output=True)
        if status.strip() != "active":
            log("⚙️  Ollama service not active — attempting to start...")
            run(["sudo", "systemctl", "start", "ollama"], check=False)
        else:
            log("✅ Ollama systemd service is active.")
        return

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
    configure_remote_access()
    ensure_ollama_running()
    ensure_models_installed()
    cleanup_unused_models()

    log("\n🎉 Ollama setup complete! Models ready:")
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
