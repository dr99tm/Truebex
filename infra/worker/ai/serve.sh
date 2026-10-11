#!/usr/bin/env bash
# A gpu-ai inference server for the self-hosted alias `truebex-open` (PF11).
#
# An OpenAI-compatible server (vLLM, Apache-2.0) serving an open-weight
# instruct model whose licence allows commercial hosting (Apache-2.0 or MIT;
# GD3 names the GPU class, GD7 the credit rates). The API reaches it over the
# platform's private network only: bind it to a private address, never to the
# internet, and register it with Admin -> Render -> AI (POST /admin/ai/servers).
#
#   MODEL_ID=<org/model> SELFHOSTED_API_KEY=<key> ./serve.sh
#
# Confirm at writing time: the vLLM image tag, the model and its tool-call
# parser (hermes for most current instruct models), the context length.
set -euo pipefail
MODEL_ID="${MODEL_ID:?set MODEL_ID to an Apache-2.0 or MIT licensed instruct model with tool calling}"
SELFHOSTED_API_KEY="${SELFHOSTED_API_KEY:?set SELFHOSTED_API_KEY (the same value as the API's server/.env)}"
BIND="${BIND:-127.0.0.1}"
PORT="${PORT:-8001}"
IMAGE="${IMAGE:-vllm/vllm-openai:v0.8.5}"
PARSER="${TOOL_CALL_PARSER:-hermes}"
MAX_LEN="${MAX_MODEL_LEN:-131072}"
CACHE="${MODEL_CACHE:-/var/lib/truebex-models}"
mkdir -p "$CACHE"
exec docker run --rm --gpus all --name truebex-open \
  -p "${BIND}:${PORT}:8000" \
  -v "${CACHE}:/root/.cache/huggingface" \
  "$IMAGE" \
  --model "$MODEL_ID" --served-model-name truebex-open --api-key "$SELFHOSTED_API_KEY" \
  --enable-auto-tool-choice --tool-call-parser "$PARSER" --max-model-len "$MAX_LEN"
