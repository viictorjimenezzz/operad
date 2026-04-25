from __future__ import annotations

from operad.core.agent import Agent

POPULATION_SIZE = 8
GENERATIONS = 5


def diversity(population: list[Agent]) -> int:  # type: ignore[type-arg]
    """Count unique hash_content values across the population."""
    return len({a.hash_content for a in population})
