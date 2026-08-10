"""Biological memory graph layer (Nacre-inspired, Epic #99)."""

from .config import memory_graph_enabled
from .decay import (
    DEFAULT_DECAY_RATE,
    DEFAULT_REINFORCEMENT_BOOST,
    MemoryEdgeState,
    calculate_decayed_weight,
    calculate_stability,
    compute_decayed_weight_from_dates,
    days_between,
    half_life_days,
)
from .recall import RecallBundle, recall_from_existing_retrieval

__all__ = [
    "DEFAULT_DECAY_RATE",
    "DEFAULT_REINFORCEMENT_BOOST",
    "MemoryEdgeState",
    "calculate_decayed_weight",
    "calculate_stability",
    "compute_decayed_weight_from_dates",
    "days_between",
    "half_life_days",
    "memory_graph_enabled",
    "RecallBundle",
    "recall_from_existing_retrieval",
]
