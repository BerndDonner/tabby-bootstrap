#!/usr/bin/env python3
from common import check_models, wait_for_ollama

if __name__ == "__main__":
    wait_for_ollama(timeout=10)
    check_models()
