#!/usr/bin/env bash
# docker-entrypoint.sh
# Waits for Ollama to be reachable, pulls required models if absent, then
# hands off to the command passed as arguments (default: python3 agent/main.py).
set -euo pipefail

OLLAMA_HOST="${AGENT_OLLAMA_HOST:-ollama}"
OLLAMA_PORT="${AGENT_OLLAMA_PORT:-11434}"
OLLAMA_BASE="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
LLM_MODEL="${AGENT_LLM_MODEL:-codellama:7b-q4}"
EMBED_MODEL="nomic-embed-text"

echo "[entrypoint] Waiting for Ollama at ${OLLAMA_BASE}..."
until curl -sf "${OLLAMA_BASE}/api/tags" >/dev/null; do
    echo "[entrypoint] Ollama not ready — retrying in 3 s..."
    sleep 3
done
echo "[entrypoint] Ollama is ready."

_pull_model() {
    local model="$1"
    if curl -sf "${OLLAMA_BASE}/api/tags" | grep -q "\"name\":\"${model}\""; then
        echo "[entrypoint] Model already present: ${model}"
        return
    fi
    echo "[entrypoint] Pulling ${model} — this may take several minutes..."
    # stream:false blocks until the pull is complete and returns a single JSON line
    curl -sf -X POST "${OLLAMA_BASE}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${model}\",\"stream\":false}" \
        --max-time 1800 \
        >/dev/null
    echo "[entrypoint] Pull complete: ${model}"
}

_pull_model "${LLM_MODEL}"
_pull_model "${EMBED_MODEL}"

echo "[entrypoint] Starting: $*"
exec "$@"
