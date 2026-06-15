import time
from typing import List, Tuple, Any

from fuzzer.grey_box_fuzzer import GreyBoxFuzzer
from schedule.path_power_schedule import PathPowerSchedule
from runner.function_coverage_runner import FunctionCoverageRunner
from utils.coverage import path_id_from_trace


class PathGreyBoxFuzzer(GreyBoxFuzzer):
    """Grey-box fuzzer that feeds path-frequency feedback into the scheduler."""

    schedule: PathPowerSchedule

    def __init__(
        self,
        seeds: List[str],
        schedule: PathPowerSchedule,
        is_print: bool,
        seed_dir: str = "",
        memory_limit: int = 200,
    ):
        super().__init__(seeds, schedule, False, seed_dir=seed_dir, memory_limit=memory_limit)

        self.last_new_path_time = self.start_time
        self.total_paths = 0
        self.is_print = is_print

        if is_print:
            print("""
┌───────────────────────┬───────────────────────┬───────────────────────┬───────────────────┬───────────────────┬────────────────┬───────────────────┐
│        Run Time       │     Last New Path     │    Last Uniq Crash    │    Total Execs    │    Total Paths    │  Uniq Crashes  │   Covered Lines   │
├───────────────────────┼───────────────────────┼───────────────────────┼───────────────────┼───────────────────┼────────────────┼───────────────────┤""")

    def print_stats(self):
        if not self.is_print:
            return

        def format_seconds(seconds):
            hours = int(seconds) // 3600
            minutes = int(seconds % 3600) // 60
            remaining_seconds = int(seconds) % 60
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

        template = """│{runtime}│{path_time}│{crash_time}│{total_exec}│{total_path}│{uniq_crash}│{covered_line}│
├───────────────────────┼───────────────────────┼───────────────────────┼───────────────────┼───────────────────┼────────────────┼───────────────────┤"""
        template = template.format(
            runtime=format_seconds(time.time() - self.start_time).center(23),
            path_time=format_seconds(self.last_new_path_time - self.start_time).center(23),
            crash_time=format_seconds(self.last_crash_time - self.start_time).center(23),
            total_exec=str(self.total_execs).center(19),
            total_path=str(self.total_paths).center(19),
            uniq_crash=str(len(set(self.crash_map.values()))).center(16),
            covered_line=str(len(self.covered_line)).center(19),
        )
        print(template)

    def run(self, runner: FunctionCoverageRunner) -> Tuple[Any, str]:  # type: ignore
        """Run input, update population, and inform scheduler about path frequency."""
        population_size_before = len(self.population)
        result, outcome = super().run(runner)

        path_id = path_id_from_trace(runner.trace())
        is_new_path = self.schedule.register_path(path_id)
        if is_new_path:
            self.last_new_path_time = time.time()
        self.total_paths = len(self.schedule.path_frequency)

        if len(self.population) > population_size_before:
            self.population[-1].path_id = path_id

        return result, outcome
