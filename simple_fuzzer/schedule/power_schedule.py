import random
from typing import List

from utils.seed import Seed

MAX_SEEDS = 1000


class PowerSchedule:

    def register_path(self, path_id: str) -> bool:
        """Optional hook called by PathGreyBoxFuzzer each run. Override in subclasses."""
        return False

    def assign_energy(self, population: List[Seed]) -> None:
        """Assigns each seed the same energy"""
        for seed in population:
            seed.energy = 1

    def normalized_energy(self, population: List[Seed]) -> List[float]:
        """Normalize energy"""
        energy = list(map(lambda seed: seed.energy, population))
        sum_energy = sum(energy)  # Add up all values in energy
        assert sum_energy != 0
        norm_energy = list(map(lambda nrg: nrg / sum_energy, energy))
        return norm_energy

    def choose(self, population: List[Seed]) -> Seed:
        """Choose weighted by normalized energy."""
        self.assign_energy(population)
        norm_energy = self.normalized_energy(population)
        if len(population) > MAX_SEEDS:
            min_index = norm_energy.index(min(norm_energy))
            del norm_energy[min_index]
            del population[min_index]
        seed: Seed = random.choices(population, weights=norm_energy)[0]
        return seed
