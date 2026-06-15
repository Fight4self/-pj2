import argparse
import os
import time

from fuzzer.path_grey_box_fuzzer import PathGreyBoxFuzzer
from runner.function_coverage_runner import FunctionCoverageRunner
from schedule.path_power_schedule import PathPowerSchedule
from samples.samples import sample1, sample2, sample3, sample4
from utils.object_utils import dump_object, load_object


class Result:
    def __init__(self, coverage, crashes, start_time, end_time):
        self.covered_line = coverage
        self.crashes = crashes
        self.start_time = start_time
        self.end_time = end_time

    def __str__(self):
        return "Covered Lines: " + str(self.covered_line) + ", Crashes Num: " + str(self.crashes) + ", Start Time: " + str(self.start_time) + ", End Time: " + str(self.end_time)


def build_sample(sample_id: int):
    sample_map = {
        1: (sample1, "corpus/corpus_1"),
        2: (sample2, "corpus/corpus_2"),
        3: (sample3, "corpus/corpus_3"),
        4: (sample4, "corpus/corpus_4"),
    }
    return sample_map[sample_id]


def parse_args():
    parser = argparse.ArgumentParser(description="Run the simple grey-box fuzzer demo.")
    parser.add_argument("--sample", type=int, default=4, choices=(1, 2, 3, 4),
                        help="Target sample program to fuzz")
    parser.add_argument("--run-time", type=int, default=300,
                        help="Fuzzing duration in seconds")
    parser.add_argument("--output-dir", default="_result",
                        help="Directory used to persist the run result")
    parser.add_argument("--quiet", action="store_true",
                        help="Disable the status table output")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_function, corpus_path = build_sample(args.sample)

    f_runner = FunctionCoverageRunner(target_function)
    seeds = load_object(corpus_path)

    grey_fuzzer = PathGreyBoxFuzzer(seeds=seeds, schedule=PathPowerSchedule(), is_print=not args.quiet)
    start_time = time.time()
    grey_fuzzer.runs(f_runner, run_time=args.run_time)

    res = Result(grey_fuzzer.covered_line, set(grey_fuzzer.crash_map.values()), start_time, time.time())
    output_path = os.path.join(args.output_dir, f"Sample-{args.sample}.pkl")
    dump_object(output_path, res)
    print(load_object(output_path))
