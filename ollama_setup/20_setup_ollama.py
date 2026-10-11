#!/usr/bin/env python3
"""Legacy standalone entrypoint; normal deployment uses the parallel task DAG.

Kept as a convenience for manual troubleshooting. The one source of truth for
individual Ollama steps is common.py and the individual task scripts.
"""

from common import install_ollama, configure_and_start, pull_model, check_models


def main():
    install_ollama()
    configure_and_start()
    pull_model("qwen2.5-coder:7b")
    pull_model("deepseek-coder:6.7b")
    check_models()


if __name__ == "__main__":
    main()
