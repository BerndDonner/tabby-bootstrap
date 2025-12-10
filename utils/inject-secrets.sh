#!/usr/bin/env bash
# =====================================================================
# 💉 inject-secrets.sh  (context-aware, 2025-12-10)
# ---------------------------------------------------------------------
# PURPOSE:
#   Re-insert real secrets into a redacted seed template.
#   This is the exact inverse of utils/strip-secrets.sh.
#
#   Restores:
#     1️⃣ Environment variables inside a SECRET ENV block
#     2️⃣ The embedded OpenSSH or RSA private key placeholder
#
#   The script is intentionally stdout-first:
#     - Without an output argument, it prints the injected result to stdout.
#     - With an optional output argument, it writes safely and atomically.
#
# ---------------------------------------------------------------------
# WHY THIS DESIGN:
#   In repos that use "clean-only" secret filters, tracking a file that
#   contains real local secrets can cause:
#     - "phantom" modifications (index vs working tree mismatch)
#     - friction with stash/pull/rebase
#
#   To avoid that, the recommended pattern is:
#     ✅ Track/edit the redacted source of truth:
#          secrets/stripped-seed.py
#     ✅ Keep the injected local file untracked + gitignored:
#          secrets/seed.py
#
# ---------------------------------------------------------------------
# TYPICAL WORKFLOW (RECOMMENDED):
#
#   1. Repository contains the redacted template:
#        secrets/stripped-seed.py
#
#   2. Local folder secrets/ contains:
#        ├── seed.key              # KEY=VALUE pairs (unquoted or quoted)
#        └── id_tabby_bootstrap    # private SSH key
#
#   3. Generate the local injected file safely:
#
#        ./utils/inject-secrets.sh \
#            secrets/stripped-seed.py \
#            secrets/seed.key \
#            secrets/id_tabby_bootstrap \
#            secrets/seed.py
#
#      - Writes atomically (tempfile → move).
#      - Locks down permissions afterwards (chmod 600 + remove user write).
#      - Discourages accidental direct edits of secrets/seed.py.
#
#   4. Use secrets/seed.py locally for deployment/bootstrap.
#
# ---------------------------------------------------------------------
# EXPECTED FILE FORMATS:
#
#   A) secrets/seed.key
#      Simple KEY=VALUE pairs:
#
#         AWS_ACCESS_KEY_ID=AKIA...
#         AWS_SECRET_ACCESS_KEY=abcd...
#         TABBY_WEBSERVER_JWT_TOKEN_SECRET=1234...
#
#      - Lines beginning with # are ignored.
#      - Quotes around values are optional and will be stripped.
#      - Whitespace around keys/values is tolerated.
#
#   B) secrets/id_tabby_bootstrap
#      The raw OpenSSH or RSA private key file:
#
#         -----BEGIN OPENSSH PRIVATE KEY-----
#         ...
#         -----END OPENSSH PRIVATE KEY-----
#
# ---------------------------------------------------------------------
# REDACTED TEMPLATE FORMAT:
#
#   Environment block (markers are preserved):
#
#     # -----BEGIN SECRET ENV-----
#     AWS_ACCESS_KEY_ID = "<REDACTED>"
#     AWS_SECRET_ACCESS_KEY = "<REDACTED>"
#     TABBY_WEBSERVER_JWT_TOKEN_SECRET = "<REDACTED>"
#     # -----END SECRET ENV-----
#
#   SSH key placeholder (two supported forms):
#
#     private_key = """# 🔒 <PRIVATE SSH KEY REDACTED>"""
#
#     # or legacy plain placeholder line containing:
#     # 🔒 <PRIVATE SSH KEY REDACTED>
#
# ---------------------------------------------------------------------
# SAFETY & DESIGN PRINCIPLES:
#
#   ✅ Pure textual substitution — no eval, no execution.
#   ✅ Handles both quoted and unquoted key placeholders.
#   ✅ Only touches clearly marked secret sections.
#   ✅ Keeps logic, comments, and formatting intact.
#   ✅ Idempotent and predictable.
#   ✅ Optional safe output mode prevents destructive self-redirect bugs.
#
# ---------------------------------------------------------------------
# USAGE EXAMPLES:
#
#   🔹 Dry run (print to stdout):
#       ./utils/inject-secrets.sh \
#           secrets/stripped-seed.py \
#           secrets/seed.key \
#           secrets/id_tabby_bootstrap
#
#   🔹 Safe write to generated local file:
#       ./utils/inject-secrets.sh \
#           secrets/stripped-seed.py \
#           secrets/seed.key \
#           secrets/id_tabby_bootstrap \
#           secrets/seed.py
#
#   🔹 Advanced: write elsewhere:
#       ./utils/inject-secrets.sh \
#           secrets/stripped-seed.py \
#           secrets/seed.key \
#           secrets/id_tabby_bootstrap \
#           /tmp/seed_filled.py
#
# ---------------------------------------------------------------------
# EXIT CODES:
#   0  success
#   1  missing or unreadable input file / wrong args
#   2  syntax or substitution error / unsafe usage pattern
#
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

set -euo pipefail

# --------------------------------------------------------------
# 🧭  Argument parsing and validation
# --------------------------------------------------------------
if [[ $# -ne 3 && $# -ne 4 ]]; then
  echo "Usage: $0 <redacted-seed-template> <secrets.key> <private_key_file> [output_file]" >&2
  exit 1
fi

REDACTED_SEED="$1"
SECRETS_FILE="$2"
KEY_FILE="$3"
OUTPUT_FILE="${4:-}"

[[ -f "$REDACTED_SEED" ]] || { echo "❌ Template seed file not found: $REDACTED_SEED" >&2; exit 1; }
[[ -f "$SECRETS_FILE" ]] || { echo "❌ Secrets file not found: $SECRETS_FILE" >&2; exit 1; }
[[ -f "$KEY_FILE"    ]] || { echo "❌ Private key file not found: $KEY_FILE" >&2; exit 1; }

# --------------------------------------------------------------
# 🧯  Guard against unsafe self-overwrite patterns
# --------------------------------------------------------------
# If a caller does:
#   ./inject-secrets.sh secrets/stripped-seed.py ... > secrets/stripped-seed.py
# the shell truncates the file before we can read it.
#
# With an explicit output_file argument, we can avoid this footgun by
# refusing identical input/output paths.
if [[ -n "$OUTPUT_FILE" && "$OUTPUT_FILE" == "$REDACTED_SEED" ]]; then
  echo "❌ Refusing to write output to the same path as the input template." >&2
  echo "   Use a distinct output path or omit output_file to print to stdout." >&2
  exit 2
fi

# --------------------------------------------------------------
# 🔐  Load environment secrets into an associative array
# --------------------------------------------------------------
declare -A SECRETS
while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ -z "${key// }" || "$key" =~ ^[[:space:]]*# ]] && continue

  # Normalize key and value
  key="$(echo "$key" | xargs)"
  value="$(echo "$value" | xargs)"

  # Remove optional surrounding quotes
  value="${value%\"}"
  value="${value#\"}"

  SECRETS["$key"]="$value"
done <"$SECRETS_FILE"

# --------------------------------------------------------------
# 🔑  Read private SSH key into memory
# --------------------------------------------------------------
PRIVATE_KEY_CONTENT="$(cat "$KEY_FILE")"

# --------------------------------------------------------------
# 🧩  Injection loop — stream redacted template → restored output
# --------------------------------------------------------------
inject_stream() {
  local in_env=0

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
      if [[ "$line" =~ ^[[:space:]]*([A-Z0-9_]+)[[:space:]]*= ]]; then
        local var="${BASH_REMATCH[1]}"
        if [[ -n "${SECRETS[$var]+_}" ]]; then
          # Preserve the "VAR = " style used in the canonical stripped template.
          printf '%s = "%s"\n' "$var" "${SECRETS[$var]}"
        else
          echo "# ⚠️ No secret found for $var — left redacted" >&2
          echo "$line"
        fi
      else
        echo "$line"
      fi
      continue
    fi

    # ----------------------------------------------------------
    # Replace SSH key placeholder (quoted or unquoted)
    # ----------------------------------------------------------
    if [[ "$line" == *"# 🔒 <PRIVATE SSH KEY REDACTED>"* ]]; then
      if [[ "$line" =~ \"\"\"# ]]; then
        # Triple-quoted form:
        #   private_key = """# 🔒 <PRIVATE SSH KEY REDACTED>"""
        # Keep everything before the placeholder's triple quote prefix and
        # replace the placeholder body with the full private key content.
        local prefix="${line%%\"\"\"#*}"
        printf '%s"""%s"""\n' "$prefix" "$PRIVATE_KEY_CONTENT"
      else
        # Plain unquoted placeholder (legacy):
        # Replace the line with the raw key content.
        printf '%s\n' "$PRIVATE_KEY_CONTENT"
      fi
      continue
    fi

    # Default: pass through unchanged
    echo "$line"
  done
}

# --------------------------------------------------------------
# 🧾  Output handling
# --------------------------------------------------------------
# Default behavior: print to stdout.
#
# If OUTPUT_FILE is provided:
#   - Write atomically via a temporary file.
#   - Attempt to relax write permission on the target first (if it exists).
#   - Lock down permissions afterwards to discourage direct editing.
if [[ -z "$OUTPUT_FILE" ]]; then
  inject_stream <"$REDACTED_SEED"
else
  # Ensure target directory exists
  out_dir="$(dirname "$OUTPUT_FILE")"
  mkdir -p "$out_dir"

  # Make the target temporarily writable if it already exists and is protected
  if [[ -f "$OUTPUT_FILE" ]]; then
    chmod u+w "$OUTPUT_FILE" || true
  fi

  tmp="$(mktemp "${OUTPUT_FILE}.XXXXXX")"
  inject_stream <"$REDACTED_SEED" >"$tmp"

  # Lock down the temporary file before moving it into place
  chmod 600 "$tmp"

  # Atomic replace
  mv -f "$tmp" "$OUTPUT_FILE"

  # Final permissions:
  #   600 ensures only the user can read/write;
  #   removing user write bit creates an intentional "edit barrier".
  chmod 600 "$OUTPUT_FILE"
  chmod u-w "$OUTPUT_FILE"
fi

# --------------------------------------------------------------
# ✅  End of script
# --------------------------------------------------------------
# echo "==> 💉 Injected ${#SECRETS[@]} secrets and one SSH key from ${SECRETS_FILE}" >&2
