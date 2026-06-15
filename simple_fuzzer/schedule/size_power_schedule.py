from typing import List

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class SizeBasedPowerSchedule(PowerSchedule):
    """Prefer shorter seeds because they execute faster and mutate more efficiently."""

    def __init__(self, exponent: float = 1.0) -> None:
        super().__init__()
        self.exponent = exponent

    def assign_energy(self, population: List[Seed]) -> None:
        for seed in population:
            length = max(len(seed.data), 1)
            seed.energy = 1.0 / (length ** self.exponent)
