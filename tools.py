"""LangChain tools backed by SmashAPIClient."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from policy import ToolPolicy
from ranker import rank_players as run_ranking
from ranking_profiles import RANKING_PROFILES, RankingIntent
from smash_api_client import SmashAPIClient, SmashAPIError

ULTIMATE_VIDEOGAME_ID = 1386


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True)


def build_tools(
    client: SmashAPIClient,
    policy: ToolPolicy,
    *,
    include_high_intensity: bool = False,
) -> list[Any]:
    @tool
    def rank_statewide_players(
        state: str,
        intent: RankingIntent = "strongest",
        months_back: int = 3,
        top_n: int = 5,
        limit: int = 0,
        min_entrants: int = 32,
    ) -> str:
        """Rank statewide players by intent using weighted scoring. Intents: strongest, clutch, underrated, overrated, consistent, upset_heavy, activity_monsters. Returns top players with method transparency in JSON."""
        if intent not in RANKING_PROFILES:
            return (
                f"Unsupported intent '{intent}'. "
                f"Supported intents: {', '.join(sorted(RANKING_PROFILES.keys()))}."
            )
        try:
            data = client.get_precomputed(
                state=state,
                months_back=months_back,
                videogame_id=ULTIMATE_VIDEOGAME_ID,
                limit=limit,
                filter_state=state,
                min_entrants=min_entrants,
            )
            rows = data.get("results", [])
            if not isinstance(rows, list):
                return "Error: /precomputed response missing list field 'results'."

            ranked = run_ranking(rows, profile=RANKING_PROFILES[intent], top_n=top_n)
            ranked["query"] = {
                "state": state.upper(),
                "intent": intent,
                "months_back": months_back,
                "videogame_id": ULTIMATE_VIDEOGAME_ID,
                "top_n": top_n,
                "limit": limit,
                "filter_state": state.upper(),
                "min_entrants": min_entrants,
            }
            return _json(ranked)
        except SmashAPIError as err:
            return f"Error calling /precomputed: {err}"

    @tool
    def get_series_rankings(
        state: str,
        tournament_contains: str,
        months_back: int = 3,
        limit: int = 25,
    ) -> str:
        """Get precomputed rankings for a tournament series name. Fast cached endpoint; returns JSON."""
        try:
            data = client.get_precomputed_series(
                state=state,
                tournament_contains=tournament_contains,
                months_back=months_back,
                videogame_id=ULTIMATE_VIDEOGAME_ID,
                limit=limit,
            )
            return _json(data)
        except SmashAPIError as err:
            return f"Error calling /precomputed_series: {err}"

    @tool
    def search_tournaments(
        state: str,
        tournament_contains: str,
        months_back: int = 3,
        limit: int = 25,
    ) -> str:
        """Find tournaments by name substring to discover exact slugs. Use this before slug lookups; returns JSON."""
        try:
            data = client.search_tournaments(
                state=state,
                tournament_contains=tournament_contains,
                months_back=months_back,
                videogame_id=ULTIMATE_VIDEOGAME_ID,
                limit=limit,
            )
            count = int(data.get("count", 0))
            resolution = policy.summarize_tournament_resolution(count)
            if resolution:
                data["agent_guidance"] = resolution
            return _json(data)
        except SmashAPIError as err:
            return f"Error calling /tournaments: {err}"

    @tool
    def lookup_tournament(tournament_slug: str) -> str:
        """Get tournament metadata by exact slug or start.gg URL. Low-intensity lookup; returns JSON."""
        try:
            data = client.lookup_tournament_by_slug(tournament_slug=tournament_slug)
            return _json(data)
        except SmashAPIError as err:
            return f"Error calling /tournaments/by-slug: {err}"

    tools = [rank_statewide_players, get_series_rankings, search_tournaments, lookup_tournament]

    if include_high_intensity:

        @tool
        def get_tournament_player_analytics(
            tournament_slug: str,
            user_request: str,
            limit: int = 25,
        ) -> str:
            """Compute player analytics for a specific tournament slug. High-intensity; only use when user explicitly asks for player stats."""
            if not policy.should_allow_high_intensity(user_request):
                return (
                    "Policy blocked high-intensity /search/by-slug call. "
                    "Use low-intensity tournament endpoints unless user explicitly asks for player analytics."
                )
            try:
                data = client.search_by_slug(
                    tournament_slug=tournament_slug,
                    videogame_id=ULTIMATE_VIDEOGAME_ID,
                    limit=limit,
                )
                return _json(data)
            except SmashAPIError as err:
                return f"Error calling /search/by-slug: {err}"

        tools.append(get_tournament_player_analytics)

    return tools
