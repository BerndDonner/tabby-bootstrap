#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy-seed.sh <IP> [--debug] [--branch <git-ref>]
# Run inside 'nix develop' (Ollama) or 'nix develop .#tabby'.
# No remote secret file is created. The payload travels over SSH stdin.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_tabby_bootstrap}"
REMOTE_PATH="/tmp/tabby-bootstrap-seed.py"
DEBUG_MODE=0
BOOTSTRAP_BRANCH=""

usage() {
  echo "Usage: $0 <IP> [--debug] [--branch <git-ref>]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi
REMOTE_IP="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      DEBUG_MODE=1
      shift ;;
    --branch)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo 'Missing argument to --branch' >&2
        exit 2
      fi
      BOOTSTRAP_BRANCH="$2"
      shift 2 ;;
    *)
      usage
      echo "Unknown argument: $1" >&2
      exit 2 ;;
  esac
done

case "${BOOTSTRAP_TARGET:-}" in
  ollama|tabby) ;;
  *)
    echo 'No bootstrap target selected. Run nix develop or nix develop .#tabby first.' >&2
    exit 1 ;;
esac

for command in ssh scp python3 git; do
  command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
[[ -r "$SSH_KEY_PATH" ]] || { echo "Missing SSH key: $SSH_KEY_PATH" >&2; exit 1; }
[[ -f "$SCRIPT_DIR/seed.py" ]] || { echo 'Missing seed.py' >&2; exit 1; }

# Critical for feature-branch testing: remote always checks out the local
# current branch unless explicitly overridden. It never silently uses master.
if [[ -z "$BOOTSTRAP_BRANCH" ]]; then
  BOOTSTRAP_BRANCH="$(git -C "$SCRIPT_DIR" symbolic-ref --quiet --short HEAD)" || {
    echo 'Detached HEAD: specify --branch <ref> explicitly.' >&2
    exit 1
  }
fi

# Avoid uploading an unpushed branch and then accidentally running old code.
# Tags and commit hashes are supported by --branch as in the old bootstrap.
if [[ "$BOOTSTRAP_BRANCH" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
  if ! git -C "$SCRIPT_DIR" cat-file -e "${BOOTSTRAP_BRANCH}^{commit}"; then
    echo "Unknown local commit: $BOOTSTRAP_BRANCH" >&2
    exit 1
  fi
else
  if ! git -C "$SCRIPT_DIR" ls-remote --exit-code origin \
      "refs/heads/$BOOTSTRAP_BRANCH" "refs/tags/$BOOTSTRAP_BRANCH" >/dev/null; then
    echo "Git ref '$BOOTSTRAP_BRANCH' is not published on origin; push it first." >&2
    exit 1
  fi
fi

# Ephemeral Lambda instances: preserve the SSH connectivity behavior of the
# previous deploy-seed.sh. Host-key verification can be hardened separately.
SSH_OPTS=(
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o LogLevel=ERROR
  -o IdentitiesOnly=yes
  -i "$SSH_KEY_PATH"
)

echo "Target:       $BOOTSTRAP_TARGET"
echo "Remote:       $SSH_USER@$REMOTE_IP"
echo "Git ref:      $BOOTSTRAP_BRANCH"
echo "Debug:        $DEBUG_MODE"
echo 'Preparing and deploying bootstrap (secrets are not printed)...'

# Preflight *before* touching the server, with output discarded.
# Transfer code via SCP and the payload via SSH stdin, never a secret file.
preflight_args=(
  --target "$BOOTSTRAP_TARGET"
  --remote-ip "$REMOTE_IP"
  --ref "$BOOTSTRAP_BRANCH"
  --key-path "$SSH_KEY_PATH"
)
if [[ "$DEBUG_MODE" -eq 1 ]]; then
  preflight_args+=(--debug)
fi

# Preflight verifies inputs before remote work. Output is discarded.
python3 "$SCRIPT_DIR/bootstrap_payload.py" "${preflight_args[@]}" >/dev/null

scp -C "${SSH_OPTS[@]}" -- "$SCRIPT_DIR/seed.py" "$SSH_USER@$REMOTE_IP:$REMOTE_PATH"

python3 "$SCRIPT_DIR/bootstrap_payload.py" "${preflight_args[@]}" |
  ssh -T "${SSH_OPTS[@]}" "$SSH_USER@$REMOTE_IP" \
    "python3 -u '$REMOTE_PATH'"

echo "Bootstrap complete: $BOOTSTRAP_TARGET ($BOOTSTRAP_BRANCH)"
