# DriftGuard

DriftGuard is a Python SDK and FastAPI backend for monitoring LLM calls with prompt-injection heuristics, semantic drift scoring, lightweight trust scoring, and a local trace dashboard. It is honest-by-design: the MVP estimates risk and suspicious patterns, but it does not prove that a response is safe, truthful, or hallucination-free.

## Installation

```bash
pip install driftguard
```

## Local Setup

Create a local `.env` from the checked-in template before running the chatbot:

```bash
copy .env.example .env
```

Then set `OPENAI_API_KEY` inside `.env`.

Important:

- `.env` is ignored by Git and should never be committed.
- `.env.example` is safe to commit because it contains placeholders only.

## Quickstart

```python
import asyncio
from openai import AsyncOpenAI
import driftguard

client = AsyncOpenAI()

@driftguard.monitor(model="gpt-4o-mini")
async def call_llm(prompt: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""

asyncio.run(call_llm("Summarize why runtime LLM monitoring matters."))
```

Start the dashboard:

```bash
driftguard-server
```

Visit `http://localhost:8000`.

- `http://localhost:8000/` opens the project hub with two options: live chatbot demo and DriftGuard reports.
- `http://localhost:8000/chat` opens the browser chatbot.
- `http://localhost:8000/reports` opens the monitoring report dashboard.

## GitHub Push Checklist

- Keep your real API key only in local `.env`.
- Do not commit SQLite databases, logs, or `__pycache__` files.
- Commit `.env.example` so other developers know which variables are required.

## Config Reference

| Env Var | Default | Purpose |
| --- | --- | --- |
| `DRIFTGUARD_REDIS_URL` | `redis://localhost:6379` | Redis Stream endpoint for async processing. |
| `DRIFTGUARD_DB_PATH` | `./driftguard.db` | SQLite database file for traces and feedback. |
| `DRIFTGUARD_LLM_JUDGE_MODEL` | `gpt-4o-mini` | Out-of-band judge model used for asynchronous injection review. |
| `DRIFTGUARD_LLM_JUDGE_API_KEY` | unset | API key for the async LLM judge. |
| `DRIFTGUARD_INJECTION_THRESHOLD` | `0.7` | Flag threshold for prompt injection scoring. |
| `DRIFTGUARD_DRIFT_THRESHOLD` | `0.35` | Alert threshold for semantic drift. |
| `DRIFTGUARD_TRUST_THRESHOLD` | `0.5` | Final trace trust-score threshold. |
| `DRIFTGUARD_EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | Sentence-transformers embedding model used for drift detection. |
| `DRIFTGUARD_LOG_LEVEL` | `INFO` | Structlog log verbosity. |

## Dashboard Screenshot Placeholder

![Dashboard screenshot placeholder](https://via.placeholder.com/1200x700?text=DriftGuard+Dashboard)

## Architecture

See the [7-Layer Architecture](#7-layer-architecture) section for the runtime flow.

## 7-Layer Architecture

1. SDK wrapper captures prompt, response, model, latency, and metadata with minimal hot-path work.
2. Queue layer pushes the trace into Redis Streams or an in-memory fallback queue.
3. Worker layer pulls events and runs injection and drift detectors concurrently.
4. Injection layer applies regex and heuristic checks immediately, then schedules an out-of-band LLM judge when configured.
5. Drift layer embeds prompts, compares them to a rolling centroid baseline, and periodically computes prompt-length PSI.
6. Trust layer aggregates injection, drift, and hallucination-risk heuristics into a single trust score.
7. Storage and API layer persists traces to SQLite and serves the dashboard, trace APIs, and feedback ingestion.

## Known Limitations

- Hallucination risk is only a heuristic score. It is not a hallucination detector and should not be treated as factual verification.
- Prompt injection recall is strongest on known attack shapes and weaker on novel or obfuscated attacks. Expect roughly 85% recall on familiar patterns, not comprehensive coverage.
- The async LLM judge is advisory and optional. If no judge API key is configured, DriftGuard still works, but that third layer is skipped.
- The default drift baseline is prompt-centric. If your application shifts topics intentionally, you should reset or segment baselines by workflow.
