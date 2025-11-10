#!/usr/bin/env bash
# =====================================================================
# 🧹 strip-secrets.sh  (fixed)
# ---------------------------------------------------------------------
#  • Detects and redacts secrets in seed scripts before commit.
#  • Handles indented and spaced KEY = "VALUE" syntax.
#  • Detects embedded OpenSSH/RSA keys even inside Python triple quotes.
# =====================================================================

set -euo pipefail

if [ -t 0 ]; then
  cat <<'EOF'

Usage: cat file | utils/strip-secrets.sh

Redacts:
  - SECRET ENV blocks (# BEGIN/END SECRET ENV)
  - Lines ending with  # @secret
  - Embedded OpenSSH / RSA private keys (even indented / inline)

EOF
  exit 0
fi

awk '
  BEGIN {
    in_env = 0
    in_key = 0
  }

  # ---------------------------------------------------------
  # Normalize: remove trailing CR to handle CRLF files
  # ---------------------------------------------------------
  {
    sub(/\r$/, "", $0)
  }

  # ---------------------------------------------------------
  # 1️⃣ Embedded OpenSSH / RSA private key (context-preserving)
  # ---------------------------------------------------------
  match($0, /[-]{5}BEGIN[[:space:]]+(OPENSSH|RSA)[[:space:]]+PRIVATE[[:space:]]+KEY[-]{5}/) {
    prefix = $0
    sub(/[-]{5}BEGIN[[:space:]]+(OPENSSH|RSA)[[:space:]]+PRIVATE[[:space:]]+KEY[-]{5}.*/, "", prefix)
    sub(/[[:space:]]+$/, "", prefix)

    # Remove any closing triple quotes before adding ours
    sub(/"{3}[[:space:]]*$/, "", prefix)

    if ($0 ~ /[-]{5}END[[:space:]]+(OPENSSH|RSA)[[:space:]]+PRIVATE[[:space:]]+KEY[-]{5}/) {
      print prefix " \"\"\"# 🔒 <PRIVATE SSH KEY REDACTED>\"\"\""
      next
    }

    in_key = 1
    print prefix " \"\"\"# 🔒 <PRIVATE SSH KEY REDACTED>\"\"\""
    next
  }

  in_key {
    if ($0 ~ /[-]{5}END[[:space:]]+(OPENSSH|RSA)[[:space:]]+PRIVATE[[:space:]]+KEY[-]{5}/) {
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

  # Inside SECRET ENV block: redact assignments (spaces allowed)
  in_env {
    # optional indent + optional export + VAR [spaces]*=*
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
  # 3️⃣ Inline @secret annotations (allow spaces around =)
  # ---------------------------------------------------------
  /# *@secret[[:space:]]*$/ {
    line = $0
    sub(/[[:space:]]+# *@secret[[:space:]]*$/, "", line)
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
  # Pass everything else unchanged
  # ---------------------------------------------------------
  { print }
'
