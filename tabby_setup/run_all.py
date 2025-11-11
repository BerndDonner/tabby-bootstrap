#!/usr/bin/env python3
# ==========================================================
# 🧩  run_all.py — Execute All Setup Steps Sequentially
# ==========================================================
# Automatically discovers and runs all numbered setup scripts
# (e.g. 10_restore_db.py, 20_restore_models.py, …).
#
# 💡 Usage:
#     python3 run_all.py
#
# Behavior:
#   - Sorts all scripts in this directory by numeric prefix.
#   - Imports each script as a module.
#   - Calls its `main()` function directly (no subprocess).
#   - Prints progress in the form (1/7), (2/7), etc.
#   - Stops immediately if any step raises an exception
#     or exits with a nonzero status.
#
# Environment:
#   Must have all required env vars set for the individual
#   scripts (e.g. AWS credentials, REMOTE_IP, secrets, etc.).
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
        # Match numbered prefix files only
        if name[:2].isdigit() and "_" in name:
            modules.append(name)
    return sorted(modules, key=lambda n: int(n.split("_")[0]))


def main():
    """Main orchestrator."""
    scripts = discover_scripts()
    total = len(scripts)

    if not scripts:
        log("❌ No numbered setup scripts found.")
        sys.exit(1)

    log(f"🧩 Found {total} setup steps to execute.\n")

    for i, name in enumerate(scripts, start=1):
        log(f"=== ({i}/{total}) Running {name} ===")
        try:
            mod = importlib.import_module(f"setup.{name}")
            if hasattr(mod, "main"):
                mod.main()
            else:
                log(f"⚠️  Module {name} has no main() function — skipped.")
        except SystemExit as e:
            # Propagate nonzero exit codes to stop the chain
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
