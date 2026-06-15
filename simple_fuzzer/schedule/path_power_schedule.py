from typing import Dict, Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class PathPowerSchedule(PowerSchedule):
    """Assign fuzzing energy inversely to execution-path frequency.

    Paths that have been exercised many times receive lower energy, while
    seeds associated with rare paths are mutated more aggressively. Energy
    scales exponentially with the inverse of path frequency, matching the
    design described in greybox fuzzing literature (e.g. AFL-style power
    schedules).
    """

    def __init__(self, exponent: float = 2.0) -> None:
        super().__init__()
        self.exponent = exponent
        self.path_frequency: Dict[str, int] = {}

    def register_path(self, path_id: str) -> bool:
        """Record one execution of `path_id`. Returns True if this is a new path."""
        is_new = path_id not in self.path_frequency
        self.path_frequency[path_id] = self.path_frequency.get(path_id, 0) + 1
        return is_new

    def path_freq(self, path_id: str) -> int:
        """Return how often a path has been observed (minimum 1)."""
        return max(self.path_frequency.get(path_id, 0), 1)

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """Assign exponential energy inversely proportional to path frequency."""
        for seed in population:
            freq = self.path_freq(seed.path_id)
            seed.energy = 1.0 / (freq ** self.exponent)
