"""Build and run a local Ollama tool-calling agent."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

try:
    from langchain_ollama import ChatOllama
except ImportError:  # Fallback for older setups.
    from langchain_community.chat_models import ChatOllama

from policy import ToolPolicy
from smash_api_client import SmashAPIClient
from tools import build_tools

LOGGER = logging.getLogger("smash_agent")

SYSTEM_PROMPT = """You are a Smash Data assistant.
Rules:
1) Prefer low-intensity endpoints: precomputed, precomputed_series, tournaments, tournaments/by-slug.
2) If user gives tournament name (not slug), call search_tournaments first. Never guess slug.
3) If search_tournaments is ambiguous, ask user to clarify.
4) Use high-intensity analytics only when user explicitly asks for player stats/analytics at specific tournament.
5) For statewide ranking questions, call rank_statewide_players with the closest intent:
   strongest, clutch, underrated, overrated, consistent, upset_heavy, activity_monsters.
6) Return top 5 and include short why bullets.
7) Videogame must be Super Smash Bros Ultimate (videogame_id=1386).
8) Be concise and cite what tool result and intent/method you used.
"""


def build_agent(
    *,
    model: str = "qwen3:14b",
    base_url: str = "http://localhost:11434",
    api_base_url: str = "https://server.cetacean-tuna.ts.net",
    include_high_intensity: bool = True,
) -> Any:
    client = SmashAPIClient(base_url=api_base_url)
    policy = ToolPolicy()
    tools = build_tools(client, policy, include_high_intensity=include_high_intensity)

    llm = ChatOllama(model=model, base_url=base_url, temperature=0.1)
    llm_with_tools = llm.bind_tools(tools)
    return create_react_agent(llm_with_tools, tools, prompt=SYSTEM_PROMPT)


def run_query(agent: Any, query: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    LOGGER.info("Agent completed in %d ms", elapsed_ms)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Smash agent with Ollama.")
    parser.add_argument("--query", required=True, help="User question to ask the agent.")
    parser.add_argument("--model", default="qwen3:14b", help="Ollama model tag.")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument(
        "--api-base-url",
        default="https://server.cetacean-tuna.ts.net",
        help="Smash API base URL.",
    )
    parser.add_argument(
        "--disable-high-intensity",
        action="store_true",
        help="Disable /search/by-slug tool exposure.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    agent = build_agent(
        model=args.model,
        base_url=args.base_url,
        api_base_url=args.api_base_url,
        include_high_intensity=not args.disable_high_intensity,
    )
    result = run_query(agent, args.query)
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
