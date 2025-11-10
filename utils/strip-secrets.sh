#!/usr/bin/env bash
# =====================================================================
# 🧹 strip-secrets.sh  (improved 2025-11-10)
# ---------------------------------------------------------------------
#  • Detects and redacts secrets in seed scripts before commit.
#  • Handles indented and spaced KEY = "VALUE" syntax.
#  • Detects embedded OpenSSH or RSA private keys even inside
#    triple-quoted or indented Python strings.
# =====================================================================

set -euo pipefail

if [ -t 0 ]; then
  cat <<'EOF'

Usage: cat file | utils/strip-secrets.sh

Redacts:
  - SECRET ENV blocks (# BEGIN/END SECRET ENV)
  - Lines ending with  # @secret
  - Embedded OpenSSH / RSA private keys (even indented)

EOF
  exit 0
fi

awk '
  BEGIN {
    in_env = 0
    in_key = 0
  }

  # ---------------------------------------------------------
  # 🔑 Embedded OpenSSH or RSA private key blocks
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
  # 🧱 Secret ENV block markers
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

  # Inside SECRET ENV block: redact all variable assignments
  in_env {
    # Match: optional indent + optional "export" + VAR = "value"
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
  # 🧷 Inline @secret annotations
  # ---------------------------------------------------------
  /# *@secret[[:space:]]*$/ {
    line = $0
    sub(/[[:space:]]+# *@secret[[:space:]]*$/, "", line)
    # Support optional spaces around '='
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
