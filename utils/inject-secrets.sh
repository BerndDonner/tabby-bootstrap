#!/usr/bin/env bash
# =====================================================================
# 💉 inject-secrets.sh
# ---------------------------------------------------------------------
# PURPOSE:
#   This script performs the inverse operation of strip-secrets.sh.
#   It *injects* (re-inserts) real secrets into a redacted seed.sh
#   template — typically after cloning or checking out the repository.
#
#   The script restores two kinds of secrets:
#     1️⃣ Environment variables within a SECRET ENV block
#     2️⃣ The embedded OpenSSH private key placeholder
#
#   It does NOT modify your git-tracked file unless you redirect the
#   output to overwrite it.
#
# ---------------------------------------------------------------------
# TYPICAL WORKFLOW:
#
#   1. Repo contains sanitized seed.sh (no real secrets)
#   2. Local folder secrets/ contains:
#        ├── seed.env              # key=value pairs
#        └── id_tabby_bootstrap    # private SSH key
#   3. Run:
#        ./scripts/inject-secrets.sh secrets/seed.sh secrets/seed.env \
#            secrets/id_tabby_bootstrap > seed_filled.sh
#   4. The resulting seed_filled.sh is ready for local use or bootstrap.
#
# ---------------------------------------------------------------------
# EXPECTED FILE FORMATS:
#
#   A) secrets/seed.env
#      Simple key-value pairs:
#
#         AWS_ACCESS_KEY_ID="AKIA..."
#         AWS_SECRET_ACCESS_KEY="abcd..."
#         TABBY_WEBSERVER_JWT_TOKEN_SECRET="1234..."
#
#      - Lines beginning with # are ignored.
#      - Quotes around values are optional.
#
#   B) secrets/id_tabby_bootstrap
#      The raw OpenSSH private key file:
#
#         -----BEGIN OPENSSH PRIVATE KEY-----
#         ...
#         -----END OPENSSH PRIVATE KEY-----
#
# ---------------------------------------------------------------------
# REDACTED TEMPLATE FORMAT:
#
#   The template (seed.sh) must include two placeholders:
#
#     1️⃣ SECRET ENV BLOCK
#         # -----BEGIN SECRET ENV-----
#         AWS_ACCESS_KEY_ID="<REDACTED>"
#         AWS_SECRET_ACCESS_KEY="<REDACTED>"
#         TABBY_WEBSERVER_JWT_TOKEN_SECRET="<REDACTED>"
#         # -----END SECRET ENV-----
#
#     2️⃣ SSH KEY PLACEHOLDER
#         # 🔒 <PRIVATE SSH KEY REDACTED>
#
#   The injector replaces these placeholders with real data.
#
# ---------------------------------------------------------------------
# SAFETY & DESIGN PRINCIPLES:
#
#   ✅  Works purely textually — no eval, no command execution.
#   ✅  Modifies only clearly marked secret sections.
#   ✅  Keeps logic, comments, and formatting intact.
#   ✅  Safe to run multiple times (idempotent).
#
# ---------------------------------------------------------------------
# USAGE EXAMPLES:
#
#   🔹 Dry run (print to stdout):
#       ./scripts/inject-secrets.sh secrets/seed.sh secrets/seed.env
#
#   🔹 Overwrite file in-place:
#       ./scripts/inject-secrets.sh secrets/seed.sh secrets/seed.env \
#           > secrets/seed.sh
#
#   🔹 With explicit key path:
#       ./scripts/inject-secrets.sh secrets/seed.sh secrets/seed.env \
#           secrets/my_custom_key > seed.sh
#
# ---------------------------------------------------------------------
# EXIT CODES:
#   0  success
#   1  missing or unreadable input file
#   2  syntax or substitution error
#
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

set -euo pipefail

# --------------------------------------------------------------
# 🧭  Argument parsing and validation
# --------------------------------------------------------------
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <redacted-seed.sh> <secrets.env> [private_key_file]" >&2
  exit 1
fi

REDACTED_SEED="$1"
SECRETS_FILE="$2"
KEY_FILE="${3:-secrets/id_tabby_bootstrap}"

[[ -f "$REDACTED_SEED" ]] || { echo "❌ Template seed file not found: $REDACTED_SEED" >&2; exit 1; }
[[ -f "$SECRETS_FILE" ]] || { echo "❌ Secrets file not found: $SECRETS_FILE" >&2; exit 1; }
[[ -f "$KEY_FILE" ]] || { echo "❌ Private key file not found: $KEY_FILE" >&2; exit 1; }

# --------------------------------------------------------------
# 🔐  Load environment secrets into an associative array
# --------------------------------------------------------------
declare -A SECRETS
while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ -z "${key// }" || "$key" =~ ^[[:space:]]*# ]] && continue

  # Normalize key and value
  key="$(echo "$key" | xargs)"
  value="$(echo "$value" | sed -E 's/^[[:space:]]*"?(.*?)"?[[:space:]]*$/\1/')"

  SECRETS["$key"]="$value"
done <"$SECRETS_FILE"

# --------------------------------------------------------------
# 🔑  Read private SSH key into memory
# --------------------------------------------------------------
PRIVATE_KEY_CONTENT="$(cat "$KEY_FILE")"

# --------------------------------------------------------------
# 🧩  Injection loop — stream redacted seed.sh → restored output
# --------------------------------------------------------------
in_env=0

while IFS= read -r line || [[ -n "$line" ]]; do
  # ----- BEGIN / END SECRET ENV markers -----
  if [[ "$line" =~ ^#.*BEGIN[[:space:]]+SECRET[[:space:]]+ENV ]]; then
    in_env=1
    echo "$line"
    continue
  fi
  if [[ "$line" =~ ^#.*END[[:space:]]+SECRET[[:space:]]+ENV ]]; then
    in_env=0
    echo "$line"
    continue
  fi

  # Inside SECRET ENV block → replace each VAR="<REDACTED>"
  if (( in_env )); then
    if [[ "$line" =~ ^[[:space:]]*([A-Z0-9_]+)= ]]; then
      var="${BASH_REMATCH[1]}"
      if [[ -n "${SECRETS[$var]+_}" ]]; then
        printf '%s="%s"\n' "$var" "${SECRETS[$var]}"
      else
        echo "# ⚠️ No secret found for $var — left redacted" >&2
        echo "$line"
      fi
    else
      echo "$line"
    fi
    continue
  fi

  # Replace SSH key placeholder with real key content
  if [[ "$line" == "# 🔒 <PRIVATE SSH KEY REDACTED>" ]]; then
    printf '%s\n' "$PRIVATE_KEY_CONTENT"
    continue
  fi

  # Default: pass through unchanged
  echo "$line"
done <"$REDACTED_SEED"

# --------------------------------------------------------------
# ✅  End of script
# --------------------------------------------------------------
# Example log message for visibility:
# echo "==> 💉 Injected ${#SECRETS[@]} secrets and one SSH key from ${SECRETS_FILE}" >&2
