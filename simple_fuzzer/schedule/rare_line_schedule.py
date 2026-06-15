from typing import Dict, List, Set

from schedule.power_schedule import PowerSchedule
from utils.coverage import Location
from utils.seed import Seed


class RareLineSchedule(PowerSchedule):
    """Assign energy based on the rarity of lines covered by a seed.

    Tracks how often each code line has been triggered across the fuzzing
    campaign. Seeds that cover lines with low global hit counts receive
    exponentially higher energy, directing the fuzzer toward under-explored
    program logic.
    """

    def __init__(self) -> None:
        super().__init__()
        self.line_frequency: Dict[Location, int] = {}

    def assign_energy(self, population: List[Seed]) -> None:
        seen: Set[Location] = set()

        for seed in population:
            for loc in seed.coverage:
                if loc not in seen:
                    self.line_frequency[loc] = self.line_frequency.get(loc, 0) + 1
                    seen.add(loc)

        for seed in population:
            if not seed.coverage:
                seed.energy = 1.0
                continue

            rarity_sum = 0.0
            for loc in seed.coverage:
                freq = self.line_frequency.get(loc, 1)
                rarity_sum += 1.0 / (freq ** 0.5)

            seed.energy = rarity_sum / len(seed.coverage)
