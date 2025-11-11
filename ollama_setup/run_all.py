#!/usr/bin/env python3
# ==========================================================
# 🧩  run_all.py — Execute All Setup Steps Sequentially
# ==========================================================
# Automatically discovers and runs all numbered setup scripts
# in *this* directory (works from any directory name).
# ==========================================================

import importlib
import pkgutil
import sys
from pathlib import Path


def log(msg: str):
    print(msg, flush=True)


def discover_scripts():
    """Return sorted list of setup modules like ['10_restore_db', ...]."""
    setup_dir = Path(__file__).parent
    modules = []
    for module_info in pkgutil.iter_modules([str(setup_dir)]):
        name = module_info.name
        if name[:2].isdigit() and "_" in name:
            modules.append(name)
    return sorted(modules, key=lambda n: int(n.split("_")[0]))


def main():
    """Main orchestrator."""
    setup_dir = Path(__file__).parent
    package_name = setup_dir.name  # ← derive dynamically (e.g. "ollama_setup")
    scripts = discover_scripts()
    total = len(scripts)

    if not scripts:
        log("❌ No numbered setup scripts found.")
        sys.exit(1)

    log(f"🧩 Found {total} setup steps to execute.\n")

    for i, name in enumerate(scripts, start=1):
        log(f"=== ({i}/{total}) Running {name} ===")
        try:
            mod = importlib.import_module(f"{package_name}.{name}")
            if hasattr(mod, "main"):
                mod.main()
            else:
                log(f"⚠️  Module {name} has no main() function — skipped.")
        except SystemExit as e:
            if e.code != 0:
                log(f"❌ {name} exited with code {e.code}. Stopping.")
                sys.exit(e.code)
        except Exception as e:
            log(f"❌ {name} failed: {e}")
            sys.exit(1)

    log("\n🎉 All setup steps completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n🛑 Aborted by user.")
        sys.exit(130)
