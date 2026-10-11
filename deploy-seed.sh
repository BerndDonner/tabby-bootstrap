#!/usr/bin/env bash
set -euo pipefail
DEPLOY_STARTED=$SECONDS

# Usage: ./deploy-seed.sh <IP> [--debug]
# Target and SOPS secrets come from 'nix develop' / 'nix develop .#tabby'.
# All code comes from the clean local HEAD, not from GitHub on the GPU.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_tabby_bootstrap}"
DEBUG_MODE=0

usage() { echo "Usage: $0 <IP> [--debug]" >&2; }
[[ $# -ge 1 ]] || { usage; exit 2; }
REMOTE_IP="$1"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug) DEBUG_MODE=1; shift ;;
    *) usage; echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "${BOOTSTRAP_TARGET:-}" in
  ollama|tabby) ;;
  *) echo 'No bootstrap target selected. Run nix develop or nix develop .#tabby first.' >&2; exit 1 ;;
esac
for cmd in ssh scp python3 git sha256sum; do
  command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }
done
[[ -r "$SSH_KEY_PATH" ]] || { echo "Missing SSH key: $SSH_KEY_PATH" >&2; exit 1; }

# Reject tracked, staged and non-ignored untracked modifications; no implicit stash.
[[ -z "$(git -C "$SCRIPT_DIR" status --porcelain --untracked-files=all)" ]] || {
  echo 'Local checkout is not clean. Commit or stash all changes (git stash push -u).' >&2
  exit 1
}
COMMIT="$(git -C "$SCRIPT_DIR" rev-parse --verify HEAD)"
BRANCH="$(git -C "$SCRIPT_DIR" symbolic-ref --quiet --short HEAD || printf '(detached)')"

payload_args=(--target "$BOOTSTRAP_TARGET" --remote-ip "$REMOTE_IP" \
              --commit "$COMMIT" --branch "$BRANCH")
[[ "$DEBUG_MODE" -eq 0 ]] || payload_args+=(--debug)
# Validate IP, manifest, declared secrets and Tabby safety before touching GPU.
python3 "$SCRIPT_DIR/bootstrap_payload.py" "${payload_args[@]}" --validate-only

umask 077
ARCHIVE="$(mktemp "${TMPDIR:-/tmp}/tabby-bootstrap.XXXXXXXX.tar")"
trap 'rm -f -- "$ARCHIVE"' EXIT
# git archive always captures the committed files at HEAD, including manifest + scheduler.
git -C "$SCRIPT_DIR" archive --format=tar HEAD > "$ARCHIVE"
[[ "$(git -C "$SCRIPT_DIR" rev-parse HEAD)" == "$COMMIT" ]] || {
  echo 'HEAD moved while preparing the archive. Retry deployment.' >&2; exit 1;
}
[[ -z "$(git -C "$SCRIPT_DIR" status --porcelain --untracked-files=all)" ]] || {
  echo 'Local checkout changed while preparing the archive. Retry deployment.' >&2; exit 1;
}
ARCHIVE_SHA256="$(sha256sum "$ARCHIVE" | cut -d' ' -f1)"

# Keep the established ephemeral-VM SSH behavior. Revisit fingerprint checks separately.
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          -o LogLevel=ERROR -o IdentitiesOnly=yes -i "$SSH_KEY_PATH")
REMOTE="$SSH_USER@$REMOTE_IP"
echo "Target: $BOOTSTRAP_TARGET | Local branch: $BRANCH | Commit: $COMMIT | Debug: $DEBUG_MODE"
echo 'Transferring committed snapshot (no GitHub credentials or local secrets in archive)...'
scp -C "${SSH_OPTS[@]}" -- "$ARCHIVE" "$REMOTE:tabby-bootstrap-source.tar"

# Verify the exact tar bytes, unpack, and replace previous checkout safely.
# The original archive is kept on the GPU in debug mode for offline restoration.
ssh -T "${SSH_OPTS[@]}" "$REMOTE" bash -s -- "$ARCHIVE_SHA256" <<'REMOTE_SETUP'
set -euo pipefail
expected="$1"
archive="$HOME/tabby-bootstrap-source.tar"
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status || {
  echo 'Remote snapshot checksum mismatch' >&2; exit 1;
}
stage="$(mktemp -d "$HOME/.tabby-bootstrap-stage.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
tar -xf "$archive" -C "$stage"
test -f "$stage/seed.py" && test -f "$stage/task_runner.py" || {
  echo 'Incomplete snapshot: seed.py/task_runner.py missing' >&2; exit 1;
}
dest="$HOME/tabby-bootstrap"
previous="$HOME/tabby-bootstrap.previous"
if test -e "$dest"; then
  rm -rf -- "$previous"
  mv -- "$dest" "$previous"
fi
if ! mv -- "$stage" "$dest"; then
  if test -e "$previous"; then mv -- "$previous" "$dest"; fi
  exit 1
fi
trap - EXIT
echo 'Verified snapshot installed at ~/tabby-bootstrap'
REMOTE_SETUP

# Secrets are transmitted only on SSH stdin (never via command line or SCP).
python3 "$SCRIPT_DIR/bootstrap_payload.py" "${payload_args[@]}" |
  ssh -T "${SSH_OPTS[@]}" "$REMOTE" 'python3 -u "$HOME/tabby-bootstrap/seed.py"'

echo "Bootstrap complete: $BOOTSTRAP_TARGET ($COMMIT)"
echo "Total deployment time: $((SECONDS - DEPLOY_STARTED))s (including preflight, transfer and remote tasks)"
