"""Policy checks for endpoint/tool usage intensity."""

from __future__ import annotations

from dataclasses import dataclass
import re


ANALYTICS_INTENT_RE = re.compile(
    r"\b(stats?|analytics|performance|performed|who\s+did\s+best|player\s+metrics?)\b",
    flags=re.IGNORECASE,
)


@dataclass
class ToolPolicy:
    """Small policy layer to keep high-intensity calls intentional."""

    def should_allow_high_intensity(self, user_request: str) -> bool:
        return bool(ANALYTICS_INTENT_RE.search(user_request))

    def summarize_tournament_resolution(self, count: int) -> str | None:
        if count == 0:
            return "No tournaments matched. Ask the user for a different tournament name."
        if count > 1:
            return "Multiple tournaments matched. Ask the user which exact tournament they mean."
        return None
