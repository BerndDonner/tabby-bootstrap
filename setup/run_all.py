#!/usr/bin/env python3
# =====================================================================
# 🧭 run_all.py
# ---------------------------------------------------------------------
# purpose:
#   run all setup scripts (10–40) in numerical order.
#   skips missing ones and stops on first failure.
#
# ---------------------------------------------------------------------
# usage:
#   python3 setup/run_all.py
# ---------------------------------------------------------------------
# author:  bernd donner
# license: mit
# =====================================================================

import subprocess
from pathlib import path


def main():
    setup_dir = path(__file__).resolve().parent
    steps = sorted(setup_dir.glob("[0-9][0-9]_*.py"))

    print("==> executing setup sequence...")
    for step in steps:
        print(f"\n➡️  running {step.name}")
        result = subprocess.run(["python3", str(step)])
        if result.returncode != 0:
            print(f"❌ step {step.name} failed (exit {result.returncode}). stopping.")
            exit(result.returncode)

    print("\n🎉 all setup steps completed successfully.")


if __name__ == "__main__":
    main()

