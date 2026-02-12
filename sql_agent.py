"""Build and run a local Ollama text-to-SQL agent for the Smash database."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent as create_react_agent

try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

LOGGER = logging.getLogger("smash_sql_agent")

SQL_SYSTEM_PROMPT = """You are an agent designed to interact with a SQL database containing \
Super Smash Bros. Ultimate tournament and player data.

Given an input question, create a syntactically correct SQLite query to run, \
then look at the results of the query and return the answer.

Unless the user specifies a specific number of results, always LIMIT your query to at most {top_k} results.

You can order the results by a relevant column to return the most interesting examples in the database. \
Never query for all the columns from a specific table — only ask for the relevant columns given the question.

You MUST double check your query before executing it. If you get an error while \
executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

To start you should ALWAYS look at the tables in the database to see what you can query. \
Do NOT skip this step. Then you should query the schema of the most relevant tables.

=== DATABASE GUIDE ===

Lightweight tables (prefer these):
- tournaments: id, slug, name, city, state, country, start_at (unix timestamp), num_attendees, videogame_id
- events: id, tournament_id, slug, name, start_at, num_entrants, videogame_id
  (FK: tournament_id -> tournaments.id)
- player_metrics: precomputed stats per player/state/month window.
  Columns: state, videogame_id, months_back, target_character, player_id, gamer_tag,
  weighted_win_rate, opponent_strength, avg_seed_delta, upset_rate, activity_score,
  home_state, avg_event_entrants, max_event_entrants, large_event_share, latest_event_start
- player_series_metrics: same as player_metrics but per tournament series.
  Extra columns: series_key, series_name_term, series_slug_term, window_offset, window_size

Heavy tables (use only when needed):
- event_payloads: event_id (FK -> events.id), seeds_json, standings_json, sets_json — large JSON blobs.
  Use json_extract() / json_each() to query these.
  standings_json: [{{"placement": N, "entrant": {{"id": N, "name": "Tag"}}}}]
  sets_json: [{{"fullRoundText": "Grand Final", "winnerId": N, "slots": [{{"entrant": {{"id": N, "name": "Tag", \
"participants": [{{"gamerTag": "...", "player": {{"id": N}}}}]}}, "standing": {{"placement": N, "stats": \
{{"score": {{"value": N}}}}}}}}]}}]

Tips:
- Dates are Unix timestamps. Use datetime(start_at, 'unixepoch') for human-readable dates.
- All data is videogame_id = 1386 (Super Smash Bros. Ultimate).
- player_metrics.state is the query region; home_state is the player's actual home state.
- Negative avg_seed_delta = outperformed seed (good). Positive = underperformed seed (bad).
- For JSON array queries: SELECT value FROM event_payloads, json_each(event_payloads.standings_json) ...
"""

DEFAULT_TOP_K = 10
DEFAULT_DB_PATH = "/home/ozdotdotdot/code-repos/smashDA/.cache/startgg/smash.db"


def build_sql_agent(
    *,
    model: str = "qwen3:14b",
    base_url: str = "http://localhost:11434",
    db_path: str = DEFAULT_DB_PATH,
    top_k: int = DEFAULT_TOP_K,
) -> Any:
    # Read-only connection via SQLite URI
    db_uri = f"sqlite:///file:{db_path}?mode=ro&uri=true"
    db = SQLDatabase.from_uri(db_uri)

    llm = ChatOllama(model=model, base_url=base_url, temperature=0.1)

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    llm_with_tools = llm.bind_tools(tools)
    prompt = SQL_SYSTEM_PROMPT.format(top_k=top_k)

    return create_react_agent(llm_with_tools, tools, system_prompt=prompt)


def run_query(agent: Any, query: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    LOGGER.info("SQL agent completed in %d ms", elapsed_ms)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Smash SQL agent with Ollama.")
    parser.add_argument("--query", required=True, help="Natural language question to ask.")
    parser.add_argument("--model", default="qwen3:14b", help="Ollama model tag.")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to smash.db SQLite database.",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Default LIMIT for queries.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    agent = build_sql_agent(
        model=args.model,
        base_url=args.base_url,
        db_path=args.db_path,
        top_k=args.top_k,
    )
    result = run_query(agent, args.query)
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
