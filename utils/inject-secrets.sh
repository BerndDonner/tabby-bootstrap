#!/usr/bin/env bash
# =====================================================================
# 🧹 strip-secrets.sh
# ---------------------------------------------------------------------
# PURPOSE:
#   Redact all sensitive information from a seed or bootstrap script
#   before committing to Git. Designed as the inverse of
#   inject-secrets.sh.
#
#   Redacts:
#     1️⃣ Embedded OpenSSH or RSA private key blocks
#     2️⃣ Environment variables within SECRET ENV blocks
#     3️⃣ Inline secrets marked with  # @secret
#
#   Intended for use as a Git "clean" filter:
#
#       [filter "stripsecrets"]
#           clean  = "utils/strip-secrets.sh"
#           smudge = "cat"
#
# ---------------------------------------------------------------------
# TYPICAL WORKFLOW:
#
#   1. The working copy contains the full seed.sh with real secrets.
#   2. Git calls this script when committing to produce a sanitized
#      version for storage in the repository.
#   3. inject-secrets.sh later restores secrets locally when needed.
#
# ---------------------------------------------------------------------
# SUPPORTED MARKERS:
#
#   1️⃣ SECRET ENV BLOCK
#
#       # -----BEGIN SECRET ENV-----
#       AWS_ACCESS_KEY_ID = "ABC..."
#       AWS_SECRET_ACCESS_KEY="DEF..."
#       # -----END SECRET ENV-----
#
#     → becomes:
#
#       AWS_ACCESS_KEY_ID = "<REDACTED>"
#       AWS_SECRET_ACCESS_KEY = "<REDACTED>"
#
#   2️⃣ INLINE SECRET TAG
#
#       TABBY_WEBSERVER_JWT_TOKEN_SECRET="xyz"   # @secret
#     → TABBY_WEBSERVER_JWT_TOKEN_SECRET = "<REDACTED>"
#
#   3️⃣ EMBEDDED PRIVATE KEY BLOCKS
#
#       -----BEGIN OPENSSH PRIVATE KEY-----
#       ...
#       -----END OPENSSH PRIVATE KEY-----
#
#     → replaced by:
#       # 🔒 <PRIVATE SSH KEY REDACTED>
#
# ---------------------------------------------------------------------
# SAFETY & DESIGN PRINCIPLES:
#
#   ✅ Explicit markers only — no guessing.
#   ✅ Symmetric with inject-secrets.sh.
#   ✅ Robust to indentation and spacing.
#   ✅ Keeps logic, comments, and readability intact.
#   ✅ Works both interactively (manual pipe) and via Git filters.
#
# ---------------------------------------------------------------------
# MANUAL TEST:
#
#   cat secrets/seed.sh | utils/strip-secrets.sh
#
# ---------------------------------------------------------------------
# EXIT CODES:
#   0  success
#   1  usage (no input)
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner
# LICENSE: MIT
# =====================================================================

set -euo pipefail

# --------------------------------------------------------------
# 🧭 Optional interactive help (only shown without piped input)
# --------------------------------------------------------------
if [ -t 0 ]; then
  echo
  echo "Usage: cat file | $(basename "$0")"
  echo
  echo "Redacts all known secret sections from the input file."
  echo "Recognized markers:"
  echo "  - # -----BEGIN SECRET ENV----- / # -----END SECRET ENV-----"
  echo "  - embedded OpenSSH / RSA private keys"
  echo "  - lines ending with  # @secret"
  echo
  exit 0
fi

# --------------------------------------------------------------
# 🔍 Main redaction logic
# --------------------------------------------------------------
awk '
  BEGIN {
    in_env = 0
    in_key = 0
  }

  # ---------------------------------------------------------
  # 1️⃣ Embedded OpenSSH / RSA private key
  # ---------------------------------------------------------
  /^[[:space:]]*[-]{5}BEGIN (OPENSSH|RSA) PRIVATE KEY[-]{5}/ {
    in_key = 1
    print "# 🔒 <PRIVATE SSH KEY REDACTED>"
    next
  }

  in_key {
    if ($0 ~ /[-]{5}END (OPENSSH|RSA) PRIVATE KEY[-]{5}/) {
      in_key = 0
    }
    next
  }

  # ---------------------------------------------------------
  # 2️⃣ Secret ENV block markers
  # ---------------------------------------------------------
  /^# *[-]{5}BEGIN SECRET ENV[-]{5}/ {
    in_env = 1
    print
    next
  }

  /^# *[-]{5}END SECRET ENV[-]{5}/ {
    in_env = 0
    print
    next
  }

  # Inside SECRET ENV block → redact variable assignments
  in_env {
    # Match: optional indent + optional "export" + VAR [spaces] = [spaces]
    if (match($0, /^[[:space:]]*(export[[:space:]]+)?([A-Za-z0-9_]+)[[:space:]]*=/, m)) {
      varname = m[2]
      indent = ""
      if (match($0, /^[[:space:]]+/, sp)) { indent = sp[0] }
      print indent varname " = \"<REDACTED>\""
    } else {
      print "# <redacted line inside SECRET ENV block>"
    }
    next
  }

  # ---------------------------------------------------------
  # 3️⃣ Inline @secret annotations
  # ---------------------------------------------------------
  /# *@secret[[:space:]]*$/ {
    line = $0
    sub(/[[:space:]]+# *@secret[[:space:]]*$/, "", line)
    # Allow spaces around '='
    n = match(line, /=/)
    if (n > 0) {
      pre = substr(line, 1, RSTART - 1)
      sub(/[[:space:]]+$/, "", pre)
      print pre " = \"<REDACTED>\""
    } else {
      print "# <redacted inline secret>"
    }
    next
  }

  # ---------------------------------------------------------
  # 4️⃣ Default: pass everything else unchanged
  # ---------------------------------------------------------
  { print }
'
