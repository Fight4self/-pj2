from typing import List

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class CoverageSizeSchedule(PowerSchedule):
    """Assign energy proportional to the number of lines covered by a seed.

    Seeds that cover more code lines in a single execution contain richer
    execution preconditions — they have crossed more branches and carry
    more internal state, making them promising candidates for deeper
    exploration.
    """

    def assign_energy(self, population: List[Seed]) -> None:
        for seed in population:
            seed.energy = len(seed.coverage)
