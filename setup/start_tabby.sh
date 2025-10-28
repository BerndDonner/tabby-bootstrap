#!/usr/bin/env bash
set -euo pipefail

# === Functions ===

detect_public_ip() {
  # Try several public IP services, silent unless all fail
  local ip=""
  local services=(
    "https://ifconfig.me"
    "https://api.ipify.org"
    "https://ipinfo.io/ip"
    "https://checkip.amazonaws.com"
  )

  for svc in "${services[@]}"; do
    ip="$(curl -fs --max-time 5 "$svc" 2>/dev/null || true)"
    if [[ -n "$ip" ]]; then
      echo "$ip"
      return 0
    fi
  done

  return 1
}

# ======== configurable bits ========
PORT="${PORT:-8080}"
DATA_ROOT="${DATA_ROOT:-/home/ubuntu/tabbyclassmodels}"          # your persistent NFS mount
MODEL_ROOT="${MODEL_ROOT:-${DATA_ROOT}/models/TabbyML}"          # where models live

if [[ -z "${TABBY_WEBSERVER_JWT_TOKEN_SECRET:-}" ]]; then
  echo "❌ Error: TABBY_WEBSERVER_JWT_TOKEN_SECRET must be set."
  exit 1
fi
JWT_SECRET="${TABBY_WEBSERVER_JWT_TOKEN_SECRET}"

# detect IPs early (silent)
PUBLIC_IP="$(detect_public_ip || true)"
LOCAL_IP="$(ip route get 1 | awk '{print $7; exit}')"

# models defined by your models.json (you already have these dirs)
declare -A PROMPT_MODELS=(
  [deepseek]="DeepSeekCoder-6.7B"
  [gemma]="CodeGemma-7B"
)

declare -A CHAT_MODELS=(
  [qwen]="Qwen2.5-Coder-7B-Instruct"
  [mistral]="Mistral-7B"
)

# Default selections
MODEL="${PROMPT_MODELS[deepseek]}"  # code completion model
CHAT_MODEL="${CHAT_MODELS[qwen]}"   # chat/instruct model

CONTAINER_NAME="${CONTAINER_NAME:-tabby}"

# === Steps ===

echo "==> [1/8] ensure docker group membership for $USER"
if ! getent group docker >/dev/null 2>&1; then
  sudo groupadd docker
fi
# add user to group; effective next login
if id -nG "$USER" | grep -qw docker; then
  echo "    $USER already in 'docker' group."
else
  sudo adduser "$USER" docker || sudo usermod -aG docker "$USER"
  echo "    added $USER to 'docker' group (will take effect on next login)."
fi

echo "==> [2/8] ensure model root exists"
mkdir -p "$DATA_ROOT"
ln -sfn "$DATA_ROOT" "$HOME/tabbyclassmodels"

echo "==> [3/8] ensure model root exists: $MODEL_ROOT"
mkdir -p "$MODEL_ROOT"

echo "==> [4/8] pick docker image"
IMAGE="tabbyml/tabby:local"
if ! sudo docker image inspect "$IMAGE" >/dev/null 2>&1; then
  IMAGE="tabbyml/tabby:latest"
  echo "    local build not found; pulling $IMAGE ..."
  sudo docker pull "$IMAGE" >/dev/null
else
  echo "    using locally built image: $IMAGE"
fi

echo "==> [5/8] stop any previous container"
sudo docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "==> [6/8] start Tabby"
sudo docker run -d \
  --name "$CONTAINER_NAME" \
  --user "$(id -u):$(id -g)" \
  --gpus all \
  -p "${PORT}:8080" \
  -v "${DATA_ROOT}:/data" \
  -e TABBY_MODEL_DIR="/data/models/TabbyML" \
  -e TABBY_DISABLE_USAGE_COLLECTION="true" \
  -e TABBY_WEBSERVER_JWT_TOKEN_SECRET="${JWT_SECRET}" \
  -e TABBY_WEBSERVER_EXTERNAL_URL="http://${PUBLIC_IP:-$LOCAL_IP}:${PORT}" \
  --restart unless-stopped \
  "$IMAGE" serve \
    --model "${MODEL}" \
    --chat-model "${CHAT_MODEL}"

echo "==> [7/8] quick health check"
sleep 2
sudo docker logs --tail 50 "$CONTAINER_NAME" || true

echo "==> [8/8] done."
echo
echo "    Tabby API (local):   http://${LOCAL_IP}:${PORT}"
if [[ -n "${PUBLIC_IP}" && "${PUBLIC_IP}" != "${LOCAL_IP}" ]]; then
  echo "    Tabby API (public):  http://${PUBLIC_IP}:${PORT}"
fi
echo "    Models dir:          ${MODEL_ROOT}"
echo "    Image used:          ${IMAGE}"
echo
echo "NOTE:"
echo " - Group change applied: 'docker'. For future sessions without sudo, re-login OR run:  newgrp docker"
echo " - If models '${MODEL}' and '${CHAT_MODEL}' aren't present under ${MODEL_ROOT},"
echo "   Tabby may start only the embedding server. Ensure those folders exist before starting."

