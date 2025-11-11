#!/usr/bin/env python3
# ==========================================================
# 🐳  60_select_image.py — Select Tabby Docker Image
# ==========================================================
# Chooses the Docker image for Tabby server startup.
# Prefers local image (tabbyml/tabby:local), otherwise
# pulls latest official version.
#
# 💡 Usage:
#     python3 60_select_image.py
#
# Writes the selected image name into:
#     /tmp/tabby_image.txt
# ==========================================================

import subprocess
import sys


def log(msg: str):
    print(msg, flush=True)


def select_docker_image():
    local_image = "tabbyml/tabby:local"
    latest_image = "tabbyml/tabby:latest"

    log("==> Selecting Docker image")

    result = subprocess.run(["sudo", "docker", "image", "inspect", local_image],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode == 0:
        image = local_image
        log(f"   ✅ Using locally built image: {image}")
    else:
        image = latest_image
        log(f"   ⚙️  Local image not found, pulling {image} ...")
        subprocess.run(["sudo", "docker", "pull", image], check=True)

    tmpfile = "/tmp/tabby_image.txt"
    with open(tmpfile, "w") as f:
        f.write(image)

    log(f"   💾 Saved image name to {tmpfile}")
    return image


def main():
    """CLI and run_all entry point."""
    image = select_docker_image()
    log(f"✅ Selected Docker image: {image}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Error: {e}")
        sys.exit(1)

