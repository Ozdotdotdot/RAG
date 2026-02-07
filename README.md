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
- `agent.py`: Ollama + LangChain + LangGraph agent entrypoint.
- `eval_smoke.py`: Smoke checks for direct API call, tool call, and optional full agent run.

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
