"""Smoke test: verify at least one API call and optional tool/agent path."""

from __future__ import annotations

import argparse
import logging
import time

from policy import ToolPolicy
from smash_api_client import SmashAPIClient, SmashAPIError


def run_direct_api_check(client: SmashAPIClient, state: str) -> None:
    last_error: SmashAPIError | None = None
    for months_back in (3, 1):
        start = time.perf_counter()
        try:
            data = client.get_precomputed(
                state=state,
                months_back=months_back,
                limit=0,
                filter_state=state,
                min_entrants=32,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            print(
                f"[PASS] Direct API call /precomputed in {elapsed_ms} ms, "
                f"months_back={months_back}, count={data.get('count')}"
            )
            return
        except SmashAPIError as err:
            last_error = err
    if last_error is not None:
        raise last_error


def run_tool_check(client: SmashAPIClient, state: str) -> None:
    from tools import build_tools

    policy = ToolPolicy()
    tools = build_tools(client, policy, include_high_intensity=True)
    tool_map = {tool.name: tool for tool in tools}
    start = time.perf_counter()
    output = tool_map["rank_statewide_players"].invoke(
        {"state": state, "intent": "clutch", "months_back": 3, "top_n": 5}
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    print(f"[PASS] Tool call rank_statewide_players in {elapsed_ms} ms")
    print(output[:500])


def run_agent_check(model: str, ollama_base_url: str, api_base_url: str, query: str) -> None:
    from agent import build_agent, run_query

    agent = build_agent(
        model=model,
        base_url=ollama_base_url,
        api_base_url=api_base_url,
        include_high_intensity=True,
    )
    result = run_query(agent, query)
    print("[PASS] Agent invocation complete")
    print(result["messages"][-1].content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smash agent smoke checks.")
    parser.add_argument("--state", default="GA", help="State code for smoke checks.")
    parser.add_argument("--api-base-url", default="https://server.cetacean-tuna.ts.net")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument(
        "--run-agent",
        action="store_true",
        help="Also run a full local model + tool call check.",
    )
    parser.add_argument(
        "--query",
        default="Who are the top players in GA in the last 3 months?",
        help="Prompt for --run-agent.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = SmashAPIClient(base_url=args.api_base_url)

    try:
        run_direct_api_check(client, args.state)
        try:
            run_tool_check(client, args.state)
        except ModuleNotFoundError as err:
            print(f"[SKIP] Tool check skipped because dependency is missing: {err}")
        if args.run_agent:
            run_agent_check(args.model, args.ollama_base_url, args.api_base_url, args.query)
    except SmashAPIError as err:
        print(f"[FAIL] Smash API error: {err}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
