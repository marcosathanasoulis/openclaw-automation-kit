#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE_NAME="openclaw-chat-demo:local"
CONTAINER_NAME="openclaw-chat-demo"
PORT="${PORT:-8090}"

cd "$ROOT_DIR"

echo "[1/4] Building image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" -f demo/chat-demo/Dockerfile .

echo "[2/4] Replacing existing container (if any): $CONTAINER_NAME"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[3/4] Starting container on http://127.0.0.1:${PORT}"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:8080" \
  "$IMAGE_NAME" >/dev/null

echo "[4/4] Health check"
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null; then
    echo "Demo is ready: http://127.0.0.1:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "Demo failed to become healthy. Logs:"
docker logs "$CONTAINER_NAME" --tail 120 || true
exit 1
