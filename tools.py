"""LangChain tools backed by SmashAPIClient."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from policy import ToolPolicy
from smash_api_client import SmashAPIClient, SmashAPIError


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True)


def build_tools(
    client: SmashAPIClient,
    policy: ToolPolicy,
    *,
    include_high_intensity: bool = False,
) -> list[Any]:
    @tool
    def get_player_rankings(
        state: str,
        months_back: int = 6,
        videogame_id: int = 1386,
        limit: int = 25,
        character: str = "Marth",
    ) -> str:
        """Get precomputed player rankings for a state. Fast cached endpoint; returns JSON."""
        try:
            data = client.get_precomputed(
                state=state,
                months_back=months_back,
                videogame_id=videogame_id,
                limit=limit,
                character=character,
            )
            return _json(data)
        except SmashAPIError as err:
            return f"Error calling /precomputed: {err}"

    @tool
    def get_series_rankings(
        state: str,
        tournament_contains: str,
        months_back: int = 6,
        videogame_id: int = 1386,
        limit: int = 25,
    ) -> str:
        """Get precomputed rankings for a tournament series name. Fast cached endpoint; returns JSON."""
        try:
            data = client.get_precomputed_series(
                state=state,
                tournament_contains=tournament_contains,
                months_back=months_back,
                videogame_id=videogame_id,
                limit=limit,
            )
            return _json(data)
        except SmashAPIError as err:
            return f"Error calling /precomputed_series: {err}"

    @tool
    def search_tournaments(
        state: str,
        tournament_contains: str,
        months_back: int = 6,
        videogame_id: int = 1386,
        limit: int = 25,
    ) -> str:
        """Find tournaments by name substring to discover exact slugs. Use this before slug lookups; returns JSON."""
        try:
            data = client.search_tournaments(
                state=state,
                tournament_contains=tournament_contains,
                months_back=months_back,
                videogame_id=videogame_id,
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

    tools = [get_player_rankings, get_series_rankings, search_tournaments, lookup_tournament]

    if include_high_intensity:

        @tool
        def get_tournament_player_analytics(
            tournament_slug: str,
            user_request: str,
            character: str = "Marth",
            videogame_id: int = 1386,
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
                    character=character,
                    videogame_id=videogame_id,
                    limit=limit,
                )
                return _json(data)
            except SmashAPIError as err:
                return f"Error calling /search/by-slug: {err}"

        tools.append(get_tournament_player_analytics)

    return tools
