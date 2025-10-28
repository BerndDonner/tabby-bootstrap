#!/usr/bin/env bash
set -euo pipefail

# ===============================================
# 🚀 start_tabby.sh
# -----------------------------------------------
# Starts a Tabby server in Docker using the models
# prepared on the instance. The external server URL
# is derived from the injected $REMOTE_IP variable
# provided by deploy-seed.sh.
#
# Required environment variables:
#   - TABBY_WEBSERVER_JWT_TOKEN_SECRET
#   - REMOTE_IP   (exported by deploy-seed.sh)
#
# Optional environment variables:
#   - PORT (default: 8080)
#   - DATA_ROOT (default: /home/ubuntu/tabbyclassmodels)
#   - MODEL_ROOT (default: ${DATA_ROOT}/models/TabbyML)
#   - CONTAINER_NAME (default: tabby)
#
# Example:
#   REMOTE_IP=192.168.1.42 ./setup/start_tabby.sh
# ===============================================

# === Configurable parameters ===
PORT="${PORT:-8080}"
DATA_ROOT="${DATA_ROOT:-/home/ubuntu/tabbyclassmodels}"
MODEL_ROOT="${MODEL_ROOT:-${DATA_ROOT}/models/TabbyML}"
CONTAINER_NAME="${CONTAINER_NAME:-tabby}"

# === Required secrets and variables ===
if [[ -z "${TABBY_WEBSERVER_JWT_TOKEN_SECRET:-}" ]]; then
  echo "❌ Error: TABBY_WEBSERVER_JWT_TOKEN_SECRET must be set."
  exit 1
fi
if [[ -z "${REMOTE_IP:-}" ]]; then
  echo "❌ Error: REMOTE_IP must be provided (set by deploy-seed.sh)."
  exit 1
fi

# === Model selections ===
declare -A PROMPT_MODELS=(
  [deepseek]="DeepSeekCoder-6.7B"
  [gemma]="CodeGemma-7B"
)

declare -A CHAT_MODELS=(
  [qwen]="Qwen2.5-Coder-7B-Instruct"
  [mistral]="Mistral-7B"
)

MODEL="${PROMPT_MODELS[deepseek]}"   # Code completion model
CHAT_MODEL="${CHAT_MODELS[qwen]}"    # Chat/instruct model

# === Step 1: Ensure docker group ===
echo "==> [1/7] Ensuring docker group membership for $USER"
if ! getent group docker >/dev/null 2>&1; then
  sudo groupadd docker
fi
if id -nG "$USER" | grep -qw docker; then
  echo "    $USER already in 'docker' group."
else
  sudo adduser "$USER" docker || sudo usermod -aG docker "$USER"
  echo "    Added $USER to 'docker' group (will take effect next login)."
fi

# === Step 2: Ensure model root exists ===
echo "==> [2/7] Ensuring data directories exist"
mkdir -p "$DATA_ROOT" "$MODEL_ROOT"
ln -sfn "$DATA_ROOT" "$HOME/tabbyclassmodels"

# === Step 3: Select docker image ===
echo "==> [3/7] Selecting Docker image"
IMAGE="tabbyml/tabby:local"
if ! sudo docker image inspect "$IMAGE" >/dev/null 2>&1; then
  IMAGE="tabbyml/tabby:latest"
  echo "    Local build not found; pulling $IMAGE ..."
  sudo docker pull "$IMAGE" >/dev/null
else
  echo "    Using locally built image: $IMAGE"
fi

# === Step 4: Stop any existing container ===
echo "==> [4/7] Stopping any existing Tabby container"
sudo docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

# === Step 5: Start container ===
echo "==> [5/7] Starting Tabby container"
sudo docker run -d \
  --name "$CONTAINER_NAME" \
  --user "$(id -u):$(id -g)" \
  --gpus all \
  -p "${PORT}:8080" \
  -v "${DATA_ROOT}:/data" \
  -e TABBY_MODEL_DIR="/data/models/TabbyML" \
  -e TABBY_DISABLE_USAGE_COLLECTION="true" \
  -e TABBY_WEBSERVER_JWT_TOKEN_SECRET="${TABBY_WEBSERVER_JWT_TOKEN_SECRET}" \
  -e TABBY_WEBSERVER_EXTERNAL_URL="http://${REMOTE_IP}:${PORT}" \
  --restart unless-stopped \
  "$IMAGE" serve \
    --model "${MODEL}" \
    --chat-model "${CHAT_MODEL}"

# === Step 6: Quick health check ===
echo "==> [6/7] Checking container logs"
sleep 2
sudo docker logs --tail 50 "$CONTAINER_NAME" || true

# === Step 7: Summary ===
echo "==> [7/7] Done."
echo
echo "    Tabby API reachable at: http://${REMOTE_IP}:${PORT}"
echo "    Models dir:             ${MODEL_ROOT}"
echo "    Docker image used:      ${IMAGE}"
echo
echo "NOTE:"
echo " - Group change 'docker' applied. Re-login or run 'newgrp docker' to apply immediately."
echo " - Ensure model folders '${MODEL}' and '${CHAT_MODEL}' exist under ${MODEL_ROOT}."
echo "   If not, Tabby may start only the embedding server."
