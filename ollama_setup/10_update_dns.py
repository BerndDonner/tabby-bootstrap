#!/usr/bin/env python3
"""Update Cloudflare A record early in parallel with installing Ollama.

Receives only CF_API_TOKEN and CF_ZONE_ID, plus REMOTE_IP and CF_DNS_NAME,
from the task executor. TTL is 60 seconds; proxied is false.
"""

import json
import os
import sys
import urllib.parse
import urllib.request


# ==========================================================
# 🧩 Utility helpers
# ==========================================================
def log(msg: str) -> None:
    print(msg, flush=True)


def api_request(method: str, url: str, api_token: str, body: dict | None = None) -> dict:
    """
    Minimal Cloudflare API wrapper using only the standard library.

    Raises SystemExit(1) on HTTP or Cloudflare-level errors, with
    human-readable log output.
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        log(f"❌ HTTP request to Cloudflare failed: {e}")
        sys.exit(1)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        log("❌ Could not decode JSON response from Cloudflare.")
        log(f"   Raw response: {raw!r}")
        sys.exit(1)

    if not isinstance(result, dict):
        log("❌ Unexpected JSON structure from Cloudflare.")
        log(f"   Raw response: {result!r}")
        sys.exit(1)

    return result


# ==========================================================
# 🌐  Cloudflare DNS logic
# ==========================================================
def upsert_a_record(
    api_token: str,
    zone_id: str,
    fqdn: str,
    ip: str,
    ttl: int = 60,
    proxied: bool = False,
) -> dict:
    """
    Create or update an A record for `fqdn` in the given Cloudflare zone.

    - If a matching A record already exists, it is updated.
    - If none exists, a new record is created.

    Returns the final record object as returned by Cloudflare.
    """
    base = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

    # 1) Look for an existing A record for this name
    query_name = urllib.parse.quote(fqdn)
    list_url = f"{base}?type=A&name={query_name}"

    log(f"🔍 Looking up existing A record for {fqdn} ...")
    listing = api_request("GET", list_url, api_token)

    if not listing.get("success", False):
        log("❌ Cloudflare DNS list request failed.")
        log(json.dumps(listing, indent=2))
        sys.exit(1)

    records = listing.get("result", []) or []

    payload = {
        "type": "A",
        "name": fqdn,
        "content": ip,
        "ttl": ttl,
        "proxied": proxied,
    }

    # 2) Update existing record or create new one
    if records:
        record_id = records[0]["id"]
        update_url = f"{base}/{record_id}"
        log(f"✏️  Updating existing A record ({record_id}) to {ip} ...")
        result = api_request("PUT", update_url, api_token, payload)
    else:
        log(f"➕ Creating new A record for {fqdn} → {ip} ...")
        result = api_request("POST", base, api_token, payload)

    if not result.get("success", False):
        log("❌ Cloudflare DNS upsert request failed.")
        log(json.dumps(result, indent=2))
        sys.exit(1)

    record = result.get("result", {})
    return record


# ==========================================================
# 🧭  Main entry point
# ==========================================================
def main() -> None:
    log("🌐 Starting Cloudflare DNS update for AI endpoint ...")

    api_token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    fqdn = os.environ.get("CF_DNS_NAME", "ai.donner-lab.org")
    remote_ip = os.environ.get("REMOTE_IP")

    # --- Basic validation ------------------------------------------------------
    missing = []
    if not api_token:
        missing.append("CF_API_TOKEN")
    if not zone_id:
        missing.append("CF_ZONE_ID")
    if not remote_ip:
        missing.append("REMOTE_IP")

    if missing:
        log("❌ Missing required environment variables:")
        for name in missing:
            log(f"   - {name}")
        log("\nℹ️  Expected environment to be prepared by:")
        log("   - deploy-seed.sh  → REMOTE_IP")
        log("   - seed.py         → CF_API_TOKEN / CF_ZONE_ID / CF_DNS_NAME")
        sys.exit(1)

    log(f"   CF_DNS_NAME: {fqdn}")
    log(f"   REMOTE_IP : {remote_ip}")

    # --- Upsert A record ------------------------------------------------------
    record = upsert_a_record(
        api_token=api_token,
        zone_id=zone_id,
        fqdn=fqdn,
        ip=remote_ip,
        ttl=60,
        proxied=False,
    )

    log("\n✅ Cloudflare DNS update complete:")
    log(f"   Name : {record.get('name')}")
    log(f"   Type : {record.get('type')}")
    log(f"   IP   : {record.get('content')}")
    log(f"   TTL  : {record.get('ttl')}s")
    log(f"   Proxy: {record.get('proxied')}")

    log("\n🧩 Reminder:")
    log(f"   - Continue / Tabby clients should use apiBase: http://{fqdn}:11434")
    log("   - With TTL=60s, switching GPU instances should propagate quickly.")


if __name__ == "__main__":
    main()
