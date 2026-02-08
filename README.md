# Smash Data Tool-Calling Agent (LangChain + Ollama)

This project connects a local Ollama model (`qwen3:14b`) to the Smash Data Analytics API so the model can answer user questions by making real API tool calls.

## What this does

- Wraps Smash API endpoints as LangChain `@tool` functions.
- Uses a LangGraph ReAct agent (`create_react_agent`) so the model can reason, call tools, observe results, and answer.
- Applies API usage policy rules so low-intensity endpoints are preferred, with high-intensity analytics available when needed.
- Logs API requests/responses (endpoint, params, status, latency) for debugging model behavior.

## Core files

- `smash_api_client.py`: Thin HTTP client for Smash endpoints.
- `tools.py`: LangChain tool definitions.
- `policy.py`: Endpoint-intensity and query-resolution guardrails.
- `ranking_profiles.py`: Intent-to-metric weight profiles (easy API port target).
- `ranker.py`: Deterministic weighted scoring engine used by tools.
- `agent.py`: Ollama + LangChain + LangGraph agent entrypoint.
- `eval_smoke.py`: Smoke checks for direct API call, tool call, and optional full agent run.

## Ranking intents

Statewide ranking questions use one generic tool with intent-based scoring:

- `strongest`
- `clutch`
- `underrated`
- `overrated`
- `consistent`
- `upset_heavy`
- `activity_monsters`

## Customization guide

### Change metric weights or ranking behavior

Edit `ranking_profiles.py`.

- Each intent has a profile in `RANKING_PROFILES`.
- Update metric `weight` and `direction` (`asc` or `desc`) per intent.
- Example: if `activity_score` is overvalued for `strongest`, reduce its weight in the `strongest` profile.

If you want deeper scoring logic changes (normalization, tie-breakers, top-N shaping), edit `ranker.py`.

### Change AI output style

Edit `agent.py`, specifically `SYSTEM_PROMPT`.

- This controls how the assistant presents answers (concise style, top 5 format, method transparency, etc.).
- If you want stricter formatting (for example always bullet lists with metric lines), enforce it in `SYSTEM_PROMPT`.

### Change tool-level defaults for API calls

Edit `tools.py`.

- `rank_statewide_players(...)` controls default behavior for statewide ranking calls.
- This is where defaults like `top_n`, `limit`, and `min_entrants` are defined before API calls happen.
- `ULTIMATE_VIDEOGAME_ID = 1386` is the hard guardrail used by all tools.

## Install

```bash
pip install requests langchain langchain-core langgraph langchain-ollama
```

## Run

Smoke check (API + tools):

```bash
python eval_smoke.py --state GA
```

Full agent run (model + tools):

```bash
python eval_smoke.py --state GA --run-agent --model qwen3:14b
```

Direct query run:

```bash
python agent.py --query "Who are the top players in GA in the last 3 months?" --model qwen3:14b
```

## Example commands

Smoke + agent run:

```bash
python eval_smoke.py --state GA --run-agent --model qwen3:14b
```

Direct agent query:

```bash
python agent.py --query "Top 5 most clutch players in GA in the last 3 months and why" --model qwen3:14b
```

Another direct query:

```bash
python agent.py --query "Top 5 most underrated players in GA for 3 months and explain the method used" --model qwen3:14b
```
