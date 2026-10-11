# gpu-ai inference servers (PF11)

The AI proxy's second alias, `truebex-open`, is an open-weight model on the platform's own GPUs for heavy
generation and unattended runs (AI7). It stays **off** (`"enabled": false` in `server/app/ai/aliases.json`) until
GD3 names the `gpu-ai` class (planning: 1 × L4 24 GB, weight 0.85) and GD7 sets its credit rates.

| Piece | Where |
|---|---|
| the server | `serve.sh`: an OpenAI-compatible inference server (vLLM, Apache-2.0) with `--served-model-name truebex-open`, an API key, tool calling on |
| the model | an instruct model with tool calling whose licence allows commercial hosting (Apache-2.0 or MIT); weights cached under `/var/lib/truebex-models` |
| the adapter | `server/app/ai/adapters/selfhosted.py`: Messages turns to chat completions and back |
| warm or cold | `ai.servers.scale` (every 60 s) probes `GET <base>/v1/models`; a warm server answers turns, otherwise the alias's `fallback_alias` (`truebex-assist`) does |
| registration | Admin -> Render -> AI, or `POST /admin/ai/servers {"server_id", "alias": "truebex-open", "base_url"}` |

To switch it on: run `serve.sh` on a gpu-ai machine reachable from the API over a private network, put the same
key in the API's `SELFHOSTED_API_KEY`, register the server, set `"enabled": true` on `truebex-open` and its
`credits_per_mtok` from GD7 (the API re-reads the file; no restart). The machine holds no user credentials; prompts
reach it only inside the platform's network.
