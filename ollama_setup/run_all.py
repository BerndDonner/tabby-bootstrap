#!/usr/bin/env python3
"""Compatibility entrypoint for manual debug: use the DAG in task_runner.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import task_runner

if __name__ == "__main__":
    sys.exit(task_runner.main(["--all"]))
