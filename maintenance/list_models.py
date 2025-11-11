#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python list_models.py <path_to_models.js>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found → {path}")
        sys.exit(1)

    data = json.loads(path.read_text())

    print(f"{'Model Name':<28} | {'Template Type':<15} | {'Files / URLs'}")
    print("-" * 90)

    for m in data:
        name = m.get("name", "")
        if "prompt_template" in m:
            ttype = "prompt"
        elif "chat_template" in m:
            ttype = "chat"
        else:
            ttype = "other"

        urls = []
        if "urls" in m:
            urls.extend(m["urls"])
        if "partition_urls" in m:
            for p in m["partition_urls"]:
                urls.extend(p.get("urls", []))

        urls_str = ", ".join(urls[:2])
        if len(urls) > 2:
            urls_str += f" ... (+{len(urls)-2} more)"

        print(f"{name:<28} | {ttype:<15} | {urls_str}")

if __name__ == "__main__":
    main()

