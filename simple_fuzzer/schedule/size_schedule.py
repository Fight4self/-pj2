from typing import List

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class SizeSchedule(PowerSchedule):
    """Assign energy inversely proportional to input length.

    Shorter inputs receive higher energy because they:
    - Execute faster, allowing more iterations
    - Are more likely to hit core logic without noise
    - More easily expose boundary conditions
    """

    def assign_energy(self, population: List[Seed]) -> None:
        for seed in population:
            length = len(seed.data)
            if length == 0:
                seed.energy = 10.0
            else:
                seed.energy = 1.0 / length
