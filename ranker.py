"""Deterministic scoring engine for ranking intents."""

from __future__ import annotations

from typing import Any

from ranking_profiles import RankingProfile

_NEUTRAL_SCORE = 0.5
_MAX_CANDIDATES = 500
_OVERSIZE_THRESHOLD = 5000


def _format_num(value: Any, decimals: int = 3) -> str:
    if value is None:
        return "null"
    return f"{float(value):.{decimals}f}"


def _seed_delta_label(value: Any) -> str:
    if value is None:
        return "unknown"
    numeric = float(value)
    if numeric < 0:
        return "outperformed_seed"
    if numeric > 0:
        return "underperformed_seed"
    return "met_seed"


def _normalize(
    value: float | int | None,
    *,
    min_value: float,
    max_value: float,
    direction: str,
) -> float:
    if value is None:
        return _NEUTRAL_SCORE
    if max_value <= min_value:
        return _NEUTRAL_SCORE
    score = (float(value) - min_value) / (max_value - min_value)
    if direction == "asc":
        return 1.0 - score
    return score


def _metric_bounds(rows: list[dict[str, Any]], metric: str) -> tuple[float, float]:
    values = [float(row[metric]) for row in rows if row.get(metric) is not None]
    if not values:
        return (0.0, 1.0)
    return (min(values), max(values))


def _tiebreak_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row.get("opponent_strength") or 0.0),
        float(row.get("activity_score") or 0.0),
        float(row.get("weighted_win_rate") or 0.0),
    )


def _reduce_oversized_pool(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    if len(rows) <= _OVERSIZE_THRESHOLD:
        return rows, None
    ranked = sorted(rows, key=_tiebreak_key, reverse=True)
    return ranked[:_MAX_CANDIDATES], (
        f"Candidate pool reduced from {len(rows)} to {_MAX_CANDIDATES} "
        "for deterministic scoring stability."
    )


def _reason_lines(row: dict[str, Any], profile: RankingProfile) -> list[str]:
    reasons: list[str] = []
    for metric_weight in profile.weights[:3]:
        metric = metric_weight.metric
        value = row.get(metric)
        if metric == "avg_seed_delta":
            label = _seed_delta_label(value)
            reasons.append(
                "avg_seed_delta="
                f"{_format_num(value)} ({label}; negative is good, positive is bad)"
            )
            continue
        if metric == "upset_rate":
            reasons.append(f"upset_rate={_format_num(value)}")
            continue
        if value is not None:
            reasons.append(f"{metric}={_format_num(value)}")
    if not reasons:
        reasons.append("ranked with neutral handling for missing metrics")
    return reasons


def rank_players(
    rows: list[dict[str, Any]],
    *,
    profile: RankingProfile,
    top_n: int = 5,
) -> dict[str, Any]:
    candidates, reduction_note = _reduce_oversized_pool(rows)
    bounds = {weight.metric: _metric_bounds(candidates, weight.metric) for weight in profile.weights}

    scored_rows: list[dict[str, Any]] = []
    for row in candidates:
        score = 0.0
        contributions: dict[str, float] = {}
        for metric_weight in profile.weights:
            min_value, max_value = bounds[metric_weight.metric]
            normalized = _normalize(
                row.get(metric_weight.metric),
                min_value=min_value,
                max_value=max_value,
                direction=metric_weight.direction,
            )
            weighted = normalized * metric_weight.weight
            score += weighted
            contributions[metric_weight.metric] = round(weighted, 6)

        next_row = dict(row)
        next_row["ranking_score"] = round(score, 6)
        next_row["score_contributions"] = contributions
        scored_rows.append(next_row)

    scored_rows.sort(key=lambda row: (row["ranking_score"], *_tiebreak_key(row)), reverse=True)
    top_players = scored_rows[: max(1, top_n)]

    return {
        "intent": profile.intent,
        "intent_label": profile.label,
        "method": {
            "description": profile.description,
            "seed_delta_semantics": {
                "metric": "avg_seed_delta",
                "negative": "outperformed_seed (good)",
                "positive": "underperformed_seed (bad)",
                "zero": "met_seed",
            },
            "weights": [
                {
                    "metric": weight.metric,
                    "weight": weight.weight,
                    "direction": weight.direction,
                }
                for weight in profile.weights
            ],
            "missing_metric_handling": "neutral_0.5",
            "tie_break_order": ["opponent_strength", "activity_score", "weighted_win_rate"],
            "reduction_note": reduction_note,
        },
        "count_considered": len(candidates),
        "count_original": len(rows),
        "top_players": [
            {
                "rank": idx + 1,
                "gamer_tag": player.get("gamer_tag"),
                "player_id": player.get("player_id"),
                "ranking_score": player.get("ranking_score"),
                "why": _reason_lines(player, profile),
                "metrics": {
                    "weighted_win_rate": player.get("weighted_win_rate"),
                    "opponent_strength": player.get("opponent_strength"),
                    "avg_seed_delta": player.get("avg_seed_delta"),
                    "seed_delta_label": _seed_delta_label(player.get("avg_seed_delta")),
                    "upset_rate": player.get("upset_rate"),
                    "activity_score": player.get("activity_score"),
                    "avg_event_entrants": player.get("avg_event_entrants"),
                    "large_event_share": player.get("large_event_share"),
                },
            }
            for idx, player in enumerate(top_players)
        ],
    }
