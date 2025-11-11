#!/usr/bin/env python3
# ==========================================================
# 🚀  70_start_tabby.py — Start Tabby Server in Docker
# ==========================================================
# Starts the Tabby server container with models prepared
# on the instance. Requires TABBY_WEBSERVER_JWT_TOKEN_SECRET
# and REMOTE_IP to be set.
#
# 💡 Usage:
#     export TABBY_WEBSERVER_JWT_TOKEN_SECRET="secret"
#     export REMOTE_IP="192.168.1.42"
#     python3 70_start_tabby.py
#
# Environment:
#   - TABBY_WEBSERVER_JWT_TOKEN_SECRET (required)
#   - REMOTE_IP (required)
#   - PORT, DATA_ROOT, MODEL_ROOT, CONTAINER_NAME (optional)
# ==========================================================

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import subprocess
from setup.config import (
    DATA_ROOT,
    MODEL_ROOT,
    PORT,
    CONTAINER_NAME,
    PROMPT_MODEL,
    CHAT_MODEL,
)


def log(msg: str):
    print(msg, flush=True)


def get_selected_image():
    """Read Docker image name from /tmp/tabby_image.txt."""
    try:
        with open("/tmp/tabby_image.txt") as f:
            return f.read().strip()
    except FileNotFoundError:
        log("⚠️  No saved image found, defaulting to tabbyml/tabby:latest")
        return "tabbyml/tabby:latest"


def stop_existing_container(container_name: str):
    log("==> Stopping any existing Tabby container")
    subprocess.run(["sudo", "docker", "rm", "-f", container_name],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("   🧹 Removed old container if present.")


def start_container(image: str, container_name: str, jwt_secret: str, remote_ip: str, port: int):
    log("==> Starting Tabby container")
    subprocess.run([
        "sudo", "docker", "run", "-d",
        "--name", container_name,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--gpus", "all",
        "-p", f"{port}:8080",
        "-v", f"{DATA_ROOT}:/data",
        "-e", "TABBY_MODEL_DIR=/data/models/TabbyML",
        "-e", "TABBY_DISABLE_USAGE_COLLECTION=true",
        "-e", f"TABBY_WEBSERVER_JWT_TOKEN_SECRET={jwt_secret}",
        "-e", f"TABBY_WEBSERVER_EXTERNAL_URL=http://{remote_ip}:{port}",
        "--restart", "unless-stopped",
        image, "serve",
        "--model", PROMPT_MODEL,
        "--chat-model", CHAT_MODEL,
    ], check=True)
    log(f"   ✅ Container '{container_name}' started.")


def show_logs(container_name: str):
    log("==> Checking container logs (last 50 lines)")
    subprocess.run(["sleep", "2"])
    subprocess.run(["sudo", "docker", "logs", "--tail", "50", container_name], check=False)


def print_summary(remote_ip: str, port: int, image: str):
    log("==> Done.\n")
    log(f"    Tabby API reachable at: http://{remote_ip}:{port}")
    log(f"    Models dir:             {MODEL_ROOT}")
    log(f"    Docker image used:      {image}")
    log("")
    log("NOTE:")
    log(" - Re-login or run 'newgrp docker' to apply group changes.")
    log(f" - Ensure model folders '{PROMPT_MODEL}' and '{CHAT_MODEL}' exist under {MODEL_ROOT}.")


def main():
    """CLI and run_all entry point."""
    jwt_secret = os.getenv("TABBY_WEBSERVER_JWT_TOKEN_SECRET")
    remote_ip = os.getenv("REMOTE_IP")

    if not jwt_secret:
        log("❌ TABBY_WEBSERVER_JWT_TOKEN_SECRET not set.")
        sys.exit(1)
    if not remote_ip:
        log("❌ REMOTE_IP not set (usually provided by deploy-seed.sh).")
        sys.exit(1)

    image = get_selected_image()
    stop_existing_container(CONTAINER_NAME)
    start_container(image, CONTAINER_NAME, jwt_secret, remote_ip, PORT)
    show_logs(CONTAINER_NAME)
    print_summary(remote_ip, PORT, image)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Error: {e}")
        sys.exit(1)

