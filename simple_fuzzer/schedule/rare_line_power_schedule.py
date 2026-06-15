from typing import Dict, Sequence, Set

from schedule.power_schedule import PowerSchedule
from utils.coverage import Location
from utils.seed import Seed


class RareLinePowerSchedule(PowerSchedule):
    """Assign higher energy to seeds that touch rarely executed code lines.

    Each line's global hit count is tracked across all executions. Seeds whose
    coverage sets contain more unusual lines receive more fuzzing budget.
    """

    def __init__(self, exponent: float = 2.0) -> None:
        super().__init__()
        self.exponent = exponent
        self.line_frequency: Dict[Location, int] = {}

    def register_coverage(self, coverage: Set[Location]) -> None:
        """Record one execution that touched the given lines."""
        for location in coverage:
            self.line_frequency[location] = self.line_frequency.get(location, 0) + 1

    def line_freq(self, location: Location) -> int:
        return max(self.line_frequency.get(location, 0), 1)

    def seed_rarity_score(self, coverage: Set[Location]) -> float:
        if not coverage:
            return 1.0
        scores = [1.0 / (self.line_freq(loc) ** self.exponent) for loc in coverage]
        return sum(scores) / len(scores)

    def assign_energy(self, population: Sequence[Seed]) -> None:
        for seed in population:
            seed.energy = self.seed_rarity_score(seed.coverage)
