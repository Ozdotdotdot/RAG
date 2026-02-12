"""Ranking intent profiles for deterministic player scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RankingIntent = Literal[
    "strongest",
    "clutch",
    "underrated",
    "overrated",
    "consistent",
    "upset_heavy",
    "activity_monsters",
]


@dataclass(frozen=True)
class MetricWeight:
    metric: str
    weight: float
    direction: Literal["asc", "desc"] = "desc"


@dataclass(frozen=True)
class RankingProfile:
    intent: RankingIntent
    label: str
    description: str
    weights: tuple[MetricWeight, ...]


RANKING_PROFILES: dict[RankingIntent, RankingProfile] = {
    "strongest": RankingProfile(
        intent="strongest",
        label="Strongest Players",
        description="Overall strongest by weighted win rate and opponent strength.",
        weights=(
            MetricWeight("weighted_win_rate", 0.55, "desc"),
            MetricWeight("opponent_strength", 0.40, "desc"),
            MetricWeight("activity_score", 0.05, "desc"),
        ),
    ),
    "clutch": RankingProfile(
        intent="clutch",
        label="Most Clutch Players",
        description="Outperform seed and convert upsets against strong opponents.",
        weights=(
            MetricWeight("upset_rate", 0.40, "desc"),
            MetricWeight("avg_seed_delta", 0.35, "asc"),
            MetricWeight("opponent_strength", 0.15, "desc"),
            MetricWeight("weighted_win_rate", 0.10, "desc"),
        ),
    ),
    "underrated": RankingProfile(
        intent="underrated",
        label="Most Underrated Players",
        description="Players who consistently outperform seed expectations.",
        weights=(
            MetricWeight("avg_seed_delta", 0.70, "asc"),
            MetricWeight("upset_rate", 0.20, "desc"),
            MetricWeight("activity_score", 0.10, "desc"),
        ),
    ),
    "overrated": RankingProfile(
        intent="overrated",
        label="Most Overrated Players",
        description="Players who underperform seed expectations.",
        weights=(
            MetricWeight("avg_seed_delta", 0.75, "desc"),
            MetricWeight("upset_rate", 0.15, "asc"),
            MetricWeight("activity_score", 0.10, "desc"),
        ),
    ),
    "consistent": RankingProfile(
        intent="consistent",
        label="Most Consistent Players",
        description="Stable performance and reliability across events.",
        weights=(
            MetricWeight("weighted_win_rate", 0.45, "desc"),
            MetricWeight("avg_seed_delta", 0.30, "asc"),
            MetricWeight("activity_score", 0.25, "desc"),
        ),
    ),
    "upset_heavy": RankingProfile(
        intent="upset_heavy",
        label="Most Upset-Heavy Players",
        description="Players most associated with upset-driven results.",
        weights=(
            MetricWeight("upset_rate", 0.70, "desc"),
            MetricWeight("avg_seed_delta", 0.20, "asc"),
            MetricWeight("activity_score", 0.10, "desc"),
        ),
    ),
    "activity_monsters": RankingProfile(
        intent="activity_monsters",
        label="Most Active Players",
        description="High activity and strong event-volume participation.",
        weights=(
            MetricWeight("activity_score", 0.55, "desc"),
            MetricWeight("avg_event_entrants", 0.20, "desc"),
            MetricWeight("large_event_share", 0.15, "desc"),
            MetricWeight("weighted_win_rate", 0.10, "desc"),
        ),
    ),
}
