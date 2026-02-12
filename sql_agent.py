"""Build and run a local Ollama text-to-SQL agent for the Smash database."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from typing import Any

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain.agents import create_agent as create_react_agent

try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

from ranker import rank_players as run_ranking
from ranking_profiles import RANKING_PROFILES

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

=== CRITICAL FILTERING RULES ===
When querying player_metrics or player_series_metrics:
- ALWAYS filter by home_state to match the requested state (e.g., WHERE home_state = 'GA').
  The 'state' column is the query region, NOT the player's home state. Players from other states
  compete in GA tournaments and appear in state='GA' rows. Use home_state to get actual residents.
- For RANKING queries (top players, best, etc.), filter by avg_event_entrants >= 32 to exclude
  players from tiny locals whose stats are unreliable.
- For SPECIFIC PLAYER lookups (e.g., "tell me about player X"), do NOT apply the min_entrants
  filter — the user wants info on that specific player regardless of event size.
  You MUST run an actual query with a WHERE clause, e.g.:
  SELECT gamer_tag, player_id, weighted_win_rate, opponent_strength, avg_seed_delta,
         upset_rate, activity_score, home_state, avg_event_entrants, months_back
  FROM player_metrics WHERE gamer_tag LIKE '%name%' COLLATE NOCASE
  Do NOT just look at the schema sample rows — those are only 3 random rows and will almost
  never contain the player you are looking for.
- Default to months_back = 3 for recent data unless the user specifies otherwise.

For ranking-style questions (best, strongest, underrated, clutch, overrated, consistent,
upset_heavy, most active, etc.), use the rank_players_by_intent tool instead of raw SQL.
It applies proper population-normalized weighted scoring that SQL cannot replicate.

=== DATABASE GUIDE ===

Lightweight tables (prefer these):
- tournaments: id, slug, name, city, state, country, start_at (unix timestamp), num_attendees, videogame_id
- events: id, tournament_id, slug, name, start_at, num_entrants, videogame_id
  (FK: tournament_id -> tournaments.id)
- player_metrics: precomputed stats per player/state/month window.
  Columns: state, videogame_id, months_back, target_character, player_id, gamer_tag,
  weighted_win_rate, opponent_strength, avg_seed_delta, upset_rate, activity_score,
  home_state, home_state_inferred, avg_event_entrants, max_event_entrants,
  large_event_share, latest_event_start
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
- Negative avg_seed_delta = outperformed seed (good). Positive = underperformed seed (bad).
- For JSON array queries: SELECT value FROM event_payloads, json_each(event_payloads.standings_json) ...
"""

DEFAULT_TOP_K = 10
DEFAULT_DB_PATH = "/home/ozdotdotdot/code-repos/smashDA/.cache/startgg/smash.db"


def _build_rank_tool(db_path: str):
    """Create the rank_players_by_intent tool with a closure over db_path."""

    @tool
    def rank_players_by_intent(
        state: str,
        intent: str = "strongest",
        months_back: int = 3,
        top_n: int = 5,
        min_entrants: int = 32,
    ) -> str:
        """Rank players by intent using weighted scoring. Use this for questions like
        'best players', 'most underrated', 'most clutch', etc. Intents: strongest,
        clutch, underrated, overrated, consistent, upset_heavy, activity_monsters.
        Returns ranked players with method transparency in JSON."""
        if intent not in RANKING_PROFILES:
            return (
                f"Unsupported intent '{intent}'. "
                f"Supported intents: {', '.join(sorted(RANKING_PROFILES.keys()))}."
            )

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT player_id, gamer_tag, weighted_win_rate, opponent_strength,
                       avg_seed_delta, upset_rate, activity_score, home_state,
                       avg_event_entrants, max_event_entrants, large_event_share,
                       latest_event_start
                FROM player_metrics
                WHERE state = ?
                  AND videogame_id = 1386
                  AND months_back = ?
                  AND home_state = ?
                  AND avg_event_entrants >= ?
            """
            LOGGER.info("rank_players_by_intent SQL:\n%s", query)
            LOGGER.info("  params: state=%s, months_back=%d, home_state=%s, min_entrants=%d",
                        state.upper(), months_back, state.upper(), min_entrants)
            rows = conn.execute(query, (state.upper(), months_back, state.upper(), min_entrants)).fetchall()
        finally:
            conn.close()

        if not rows:
            return json.dumps({"error": f"No players found for state={state.upper()} with min_entrants>={min_entrants}."})

        row_dicts = [dict(row) for row in rows]
        ranked = run_ranking(row_dicts, profile=RANKING_PROFILES[intent], top_n=top_n)
        ranked["query"] = {
            "state": state.upper(),
            "intent": intent,
            "months_back": months_back,
            "videogame_id": 1386,
            "top_n": top_n,
            "min_entrants": min_entrants,
        }
        return json.dumps(ranked, ensure_ascii=True)

    return rank_players_by_intent


def build_sql_agent(
    *,
    model: str = "qwen3:14b",
    base_url: str = "http://localhost:11434",
    db_path: str = DEFAULT_DB_PATH,
    top_k: int = DEFAULT_TOP_K,
) -> Any:
    # Read-only connection via SQLite URI; echo=True logs all SQL via sqlalchemy.engine
    db_uri = f"sqlite:///file:{db_path}?mode=ro&uri=true"
    db = SQLDatabase.from_uri(db_uri, engine_args={"echo": True})

    llm = ChatOllama(model=model, base_url=base_url, temperature=0.1)

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    toolkit_tools = toolkit.get_tools()

    rank_tool = _build_rank_tool(db_path)
    all_tools = toolkit_tools + [rank_tool]

    llm_with_tools = llm.bind_tools(all_tools)
    prompt = SQL_SYSTEM_PROMPT.format(top_k=top_k)

    return create_react_agent(llm_with_tools, all_tools, system_prompt=prompt)


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
    # SQLAlchemy echo=True logs queries through sqlalchemy.engine at INFO level

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
