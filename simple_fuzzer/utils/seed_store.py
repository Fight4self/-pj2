import os
import random
from typing import List, Optional, Set, Tuple

from utils.object_utils import dump_object, get_md5_of_object, load_object
from utils.seed import Seed


class SeedPersistence:
    """Persist discovered seeds and crashes to disk to cap in-memory population size."""

    def __init__(self, root_dir: str, memory_limit: int = 200) -> None:
        self.root_dir = root_dir
        self.crash_dir = os.path.join(root_dir, "crashes")
        self.memory_limit = memory_limit
        self.known_seed_hashes: Set[str] = set()
        self.known_crash_hashes: Set[str] = set()
        self.seed_hashes: List[str] = []
        os.makedirs(self.root_dir, exist_ok=True)
        os.makedirs(self.crash_dir, exist_ok=True)

    def _seed_path(self, seed_hash: str) -> str:
        return os.path.join(self.root_dir, f"{seed_hash}.pkl")

    def seed_fingerprint(self, seed: Seed) -> str:
        payload = (seed.data, tuple(sorted(seed.coverage)))
        return get_md5_of_object(payload)

    def persist_seed(self, seed: Seed) -> Optional[str]:
        """Write a new seed to disk. Returns hash when stored, None if duplicate."""
        seed_hash = self.seed_fingerprint(seed)
        if seed_hash in self.known_seed_hashes:
            return None

        dump_object(self._seed_path(seed_hash), seed)
        self.known_seed_hashes.add(seed_hash)
        self.seed_hashes.append(seed_hash)
        return seed_hash

    def load_seed(self, seed_hash: str) -> Seed:
        return load_object(self._seed_path(seed_hash))

    def sample_seed(self) -> Optional[Seed]:
        if not self.seed_hashes:
            return None
        return self.load_seed(random.choice(self.seed_hashes))

    def persist_crash(self, inp: str, crash_id) -> Optional[str]:
        crash_hash = get_md5_of_object((inp, crash_id))
        if crash_hash in self.known_crash_hashes:
            return None

        dump_object(os.path.join(self.crash_dir, f"{crash_hash}.pkl"), (inp, crash_id))
        self.known_crash_hashes.add(crash_hash)
        return crash_hash

    def persist_manifest(self) -> None:
        manifest = {
            "seed_hashes": self.seed_hashes,
            "crash_hashes": sorted(self.known_crash_hashes),
            "total_seeds": len(self.seed_hashes),
            "total_crashes": len(self.known_crash_hashes),
        }
        dump_object(os.path.join(self.root_dir, "manifest.pkl"), manifest)

    def stats(self) -> Tuple[int, int]:
        return len(self.seed_hashes), len(self.known_crash_hashes)
