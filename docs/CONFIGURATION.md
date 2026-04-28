# Configuration

## Environment

Copy the template:

```bash
cp .env.example .env
```

Common variables:

| Variable | Description |
| --- | --- |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_MODEL` | Model name |
| `LLM_API_KEY` | API key, can be empty for local providers |
| `LLM_TEMPERATURE` | Generation temperature |
| `LLM_TIMEOUT_SECONDS` | Request timeout |
| `CRAWLER_DELAY_SECONDS` | Metadata crawler delay |
| `CRAWLER_USER_AGENT` | User agent for metadata requests |

## UI Model Profiles

The UI supports multiple profiles in `data/config/model_profiles.json`:

- OpenAI-compatible HTTP API
- Ollama local API
- LM Studio local API
- Claude CLI bridge

This file may contain credentials and is ignored by Git.

## Electron

```bash
bash scripts/run_electron.sh
```

Electron starts the local Streamlit server and opens it in a desktop window.
