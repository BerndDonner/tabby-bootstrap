#!/usr/bin/env bash
# =====================================================================
# 🧹 strip-secrets.sh
# ---------------------------------------------------------------------
# PURPOSE:
#   This script sanitizes sensitive data before a file (e.g. seed.sh)
#   is committed to Git. It’s designed to be used as a “clean filter”
#   in .gitattributes:
#
#       seed.sh filter=stripsecrets
#
#   and registered in .git/config:
#
#       [filter "stripsecrets"]
#           clean = "../utils/strip-secrets.sh"
#           smudge = "cat"
#
#   When you run `git add seed.sh`, Git sends the file’s content
#   through this script, and only the sanitized version is stored
#   in the commit. The working copy (your real file) remains untouched.
#
# ---------------------------------------------------------------------
# DESIGN PRINCIPLES:
#   ✅  Explicit markers only – no guessing.
#   ✅  Works non-interactively (for Git filters) and interactively (manual test).
#   ✅  Keeps logic, formatting, and readability intact.
#   ✅  Fully symmetric with inject-secrets.sh.
#
# ---------------------------------------------------------------------
# SUPPORTED MARKERS:
#
#   1️⃣  SECRET ENV BLOCK
#       Redacts everything between the following lines:
#
#           # -----BEGIN SECRET ENV-----
#           AWS_ACCESS_KEY_ID="ABC..."
#           AWS_SECRET_ACCESS_KEY="DEF..."
#           # -----END SECRET ENV-----
#
#       → becomes:
#           AWS_ACCESS_KEY_ID="<REDACTED>"
#           AWS_SECRET_ACCESS_KEY="<REDACTED>"
#
#   2️⃣  INLINE SECRET TAG
#       Redacts any assignment line ending with  # @secret
#           TABBY_WEBSERVER_JWT_TOKEN_SECRET="xyz"   # @secret
#       →   TABBY_WEBSERVER_JWT_TOKEN_SECRET="<REDACTED>"
#
#   3️⃣  EMBEDDED OPENSSH PRIVATE KEY
#       Replaces any block between
#           -----BEGIN OPENSSH PRIVATE KEY-----
#           ...
#           -----END OPENSSH PRIVATE KEY-----
#       with a one-line placeholder comment.
#
# ---------------------------------------------------------------------
# USAGE (manual test):
#       cat secrets/seed.sh | ../utils/strip-secrets.sh
#
#   or simply:
#       ../utils/strip-secrets.sh   → shows usage help (interactive mode)
#
# ---------------------------------------------------------------------
# SAFETY:
#   - When Git calls this script, stdin is *not* a terminal → help is suppressed.
#   - Only explicit markers are redacted; logic stays readable.
#
# ---------------------------------------------------------------------
# AUTHOR:  Bernd Donner (with GPT-5 assistant)
# LICENSE: MIT
# =====================================================================

set -euo pipefail

# -------------------------------------------------------------
# 🧭 Optional interactive help (only shown without piped input)
# -------------------------------------------------------------
if [ -t 0 ]; then
  echo
  echo "Usage: cat file | $(basename "$0")"
  echo
  echo "This script redacts secrets from seed.sh before committing."
  echo
  echo "Typical workflow:"
  echo "  - Git automatically calls this script as a clean filter"
  echo "    to sanitize secrets before committing."
  echo "  - Run manually with a pipe for testing:"
  echo
  echo "      cat secrets/seed.sh | ../utils/strip-secrets.sh"
  echo
  echo "Markers recognized:"
  echo "  - # -----BEGIN SECRET ENV----- / # -----END SECRET ENV-----"
  echo "  - lines ending with  # @secret"
  echo "  - embedded OpenSSH private keys"
  echo
  exit 0
fi

# -------------------------------------------------------------
# 🔍 Main redaction logic
# -------------------------------------------------------------
awk '
  BEGIN {
    in_env = 0;
    in_key = 0;
  }

  # ---------------------------------------------------------
  # 1️⃣  Redact embedded OpenSSH private key
  # ---------------------------------------------------------
  /^-----BEGIN OPENSSH PRIVATE KEY-----$/ {
    in_key = 1;
    print "# 🔒 <PRIVATE SSH KEY REDACTED>";
    next;
  }
  in_key {
    if ($0 ~ /^-----END OPENSSH PRIVATE KEY-----$/) {
      in_key = 0;
    }
    next;
  }

  # ---------------------------------------------------------
  # 2️⃣  Secret ENV block markers
  # ---------------------------------------------------------
  /^# *-----BEGIN SECRET ENV----- *$/ {
    in_env = 1;
    print;
    next;
  }
  /^# *-----END SECRET ENV----- *$/ {
    in_env = 0;
    print;
    next;
  }

  # Inside SECRET ENV block: redact all VAR assignments
  in_env {
    if (match($0, /^[[:space:]]*(export[[:space:]]+)?([A-Z0-9_]+)=/, m)) {
      varname = m[2];
      indent = "";
      if (match($0, /^[[:space:]]+/, sp)) { indent = sp[0]; }
      print indent varname "=\"<REDACTED>\"";
    } else {
      print "# <redacted line inside SECRET ENV block>";
    }
    next;
  }

  # ---------------------------------------------------------
  # 3️⃣  Inline @secret annotations
  # ---------------------------------------------------------
  /# *@secret[[:space:]]*$/ {
    line = $0;
    sub(/[[:space:]]+# *@secret[[:space:]]*$/, "", line);
    n = index(line, "=");
    if (n > 0) {
      head = substr(line, 1, n);
      print head "\"<REDACTED>\"";
    } else {
      print "# <redacted inline secret>";
    }
    next;
  }

  # ---------------------------------------------------------
  # 4️⃣  Default: pass everything else unchanged
  # ---------------------------------------------------------
  { print; }
'
