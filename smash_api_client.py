"""Thin client for the Smash Data Analytics API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

import requests
from requests import RequestException


class SmashAPIError(RuntimeError):
    """Raised when the Smash API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


LOGGER = logging.getLogger("smash_api.client")


@dataclass
class SmashAPIClient:
    base_url: str = "https://server.cetacean-tuna.ts.net"
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        self._session = requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        started = time.perf_counter()
        LOGGER.info("API request: GET %s params=%s", path, params or {})
        try:
            response = self._session.get(url, params=params, timeout=self.timeout_seconds)
        except RequestException as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            LOGGER.error("API network error: GET %s in %d ms error=%s", path, elapsed_ms, exc)
            raise SmashAPIError(f"Network error for GET {path}: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        LOGGER.info("API response: GET %s status=%d in %d ms", path, response.status_code, elapsed_ms)

        if not response.ok:
            message = f"HTTP {response.status_code} for GET {path}"
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                message = f"{message} (Retry-After: {retry_after}s)"
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise SmashAPIError(f"{message}. Body: {body}", status_code=response.status_code)

        try:
            return response.json()
        except ValueError as exc:
            raise SmashAPIError(f"Invalid JSON from GET {path}: {response.text}") from exc

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def get_precomputed(
        self,
        *,
        state: str,
        months_back: int = 3,
        videogame_id: int = 1386,
        limit: int = 0,
        filter_state: str | None = None,
        min_entrants: int | None = None,
    ) -> dict[str, Any]:
        params = {
            "state": state.upper(),
            "months_back": months_back,
            "videogame_id": videogame_id,
            "limit": limit,
        }
        if filter_state:
            params["filter_state"] = filter_state.upper()
        if min_entrants is not None:
            params["min_entrants"] = min_entrants
        return self._get("/precomputed", params=params)

    def get_precomputed_series(
        self,
        *,
        state: str,
        tournament_contains: str,
        months_back: int = 3,
        videogame_id: int = 1386,
        limit: int = 0,
        allow_multi: bool = True,
    ) -> dict[str, Any]:
        params = {
            "state": state.upper(),
            "tournament_contains": tournament_contains,
            "months_back": months_back,
            "videogame_id": videogame_id,
            "limit": limit,
            "allow_multi": str(allow_multi).lower(),
        }
        return self._get("/precomputed_series", params=params)

    def search_tournaments(
        self,
        *,
        state: str,
        tournament_contains: str,
        months_back: int = 3,
        videogame_id: int = 1386,
        limit: int = 0,
    ) -> dict[str, Any]:
        params = {
            "state": state.upper(),
            "tournament_contains": tournament_contains,
            "months_back": months_back,
            "videogame_id": videogame_id,
            "limit": limit,
        }
        return self._get("/tournaments", params=params)

    def lookup_tournament_by_slug(self, *, tournament_slug: str) -> dict[str, Any]:
        return self._get("/tournaments/by-slug", params={"tournament_slug": tournament_slug})

    def search_by_slug(
        self,
        *,
        tournament_slug: str,
        videogame_id: int = 1386,
        limit: int = 0,
    ) -> dict[str, Any]:
        params = {
            "tournament_slug": tournament_slug,
            "videogame_id": videogame_id,
            "limit": limit,
        }
        return self._get("/search/by-slug", params=params)
