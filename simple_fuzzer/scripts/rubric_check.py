"""Preliminary rubric check against PJ2 scoring criteria."""
import inspect
import os
import sys
import time
from typing import Callable, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fuzzer.path_grey_box_fuzzer import PathGreyBoxFuzzer
from runner.function_coverage_runner import FunctionCoverageRunner
from schedule.path_power_schedule import PathPowerSchedule
from samples.samples import sample1, sample2, sample3, sample4
from utils.coverage import Location
from utils.mutator import Mutator
from utils.object_utils import dump_object, load_object


SAMPLES = {
    1: (sample1, "corpus/corpus_1"),
    2: (sample2, "corpus/corpus_2"),
    3: (sample3, "corpus/corpus_3"),
    4: (sample4, "corpus/corpus_4"),
}


def sample_total_lines(func: Callable) -> int:
    lines, start = inspect.getsourcelines(func)
    return len(lines)


def sample_coverage_ratio(covered: Set[Location], func: Callable) -> Tuple[int, int, float]:
    name = func.__name__
    hit = sum(1 for fn, _ in covered if fn == name)
    total = sample_total_lines(func)
    ratio = hit / total if total else 0.0
    return hit, total, ratio


def check_basic_run() -> Tuple[bool, str]:
    try:
        func, corpus = SAMPLES[1]
        seeds = load_object(corpus)
        assert isinstance(seeds, list) and len(seeds) > 0
        runner = FunctionCoverageRunner(func)
        fuzzer = PathGreyBoxFuzzer(seeds, PathPowerSchedule(), is_print=False)
        fuzzer.runs(runner, run_time=3)
        return True, f"启动正常，读取 {len(seeds)} 个 seed，3 秒 fuzz 完成，execs={fuzzer.total_execs}"
    except Exception as exc:
        return False, str(exc)


def check_mutator() -> Tuple[bool, str]:
    mut = Mutator()
    base = "Hello123!"
    outputs = set()
    for _ in range(200):
        outputs.add(mut.mutate(base))
    kinds = len(mut.mutators)
    changed = sum(1 for o in outputs if o != base)
    ok = kinds >= 5 and changed >= 50
    return ok, f"{kinds} 种变异算子，200 次变异中 {changed} 次产生不同输入，{len(outputs)} 种 distinct 输出"


def check_path_scheduler() -> Tuple[bool, str]:
    schedule = PathPowerSchedule()
    schedule.register_path("p1")
    schedule.register_path("p1")
    schedule.register_path("p2")
    from utils.seed import Seed

    seeds = [Seed("a", set(), path_id="p1"), Seed("b", set(), path_id="p2")]
    schedule.assign_energy(seeds)
    ok = seeds[0].energy < seeds[1].energy and len(schedule.path_frequency) == 2
    return ok, f"path 频率={schedule.path_frequency}，energy p1={seeds[0].energy:.4f}, p2={seeds[1].energy:.4f}"


def check_extra_scheduler() -> Tuple[bool, str]:
    schedule_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schedule")
    files = [f for f in os.listdir(schedule_dir) if f.endswith(".py") and f not in ("power_schedule.py", "path_power_schedule.py")]
    classes = []
    for f in files:
        path = os.path.join(schedule_dir, f)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if "PowerSchedule" in text and "class " in text:
            classes.append(f)
    if classes:
        return True, f"发现额外调度: {', '.join(classes)}"
    return False, "schedule/ 下除 power_schedule / path_power_schedule 外无第三种调度"


def check_seed_persistence() -> Tuple[bool, str]:
    grey_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fuzzer", "grey_box_fuzzer.py")
    store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "seed_store.py")
    if not os.path.exists(store_path):
        return False, "缺少 utils/seed_store.py"
    with open(grey_path, encoding="utf-8") as fh:
        text = fh.read()
    if "SeedPersistence" in text and "_trim_memory_population" in text:
        return True, "GreyBoxFuzzer 已接入 SeedPersistence 与内存裁剪"
    return False, "seed 持久化尚未接入 fuzzer 主流程"


def run_sample_coverage(sample_id: int, run_time: int = 60) -> Tuple[int, int, float, int, int]:
    func, corpus = SAMPLES[sample_id]
    seeds = load_object(corpus)
    runner = FunctionCoverageRunner(func)
    fuzzer = PathGreyBoxFuzzer(seeds, PathPowerSchedule(), is_print=False)
    fuzzer.runs(runner, run_time=run_time)
    hit, total, ratio = sample_coverage_ratio(fuzzer.covered_line, func)
    return hit, total, ratio, fuzzer.total_execs, len(set(fuzzer.crash_map.values()))


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    run_time = int(os.environ.get("RUBRIC_RUN_TIME", "30"))

    print("=" * 60)
    print("PJ2 初步评分自检（运行时间每 sample {}s）".format(run_time))
    print("=" * 60)

    scores = []

    ok, msg = check_basic_run()
    scores.append(("基础运行", 4 if ok else 0, 4, msg))
    print(f"[{'PASS' if ok else 'FAIL'}] 基础运行 (4分): {msg}")

    ok, msg = check_mutator()
    scores.append(("代码实现-变异", 4 if ok else 0, 4, msg))
    print(f"[{'PASS' if ok else 'FAIL'}] 变异器 (代码实现子项): {msg}")

    ok, msg = check_path_scheduler()
    part = 4 if ok else 0
    scores.append(("代码实现-路径调度", part, 4, msg))
    print(f"[{'PASS' if ok else 'FAIL'}] 路径频率调度 (代码实现子项): {msg}")

    ok_extra, msg_extra = check_extra_scheduler()
    print(f"[{'PASS' if ok_extra else 'FAIL'}] 第三种调度 (代码实现子项): {msg_extra}")

    ok_persist, msg_persist = check_seed_persistence()
    scores.append(("框架完善", 4 if ok_persist else 0, 4, msg_persist))
    print(f"[{'PASS' if ok_persist else 'FAIL'}] 框架完善/seed 持久化 (4分): {msg_persist}")

    print("\n--- Fuzzer 可用性：各 sample 覆盖率 (目标 >=50%) ---")
    coverage_pass = 0
    for sid in (1, 2, 3, 4):
        hit, total, ratio, execs, crashes = run_sample_coverage(sid, run_time)
        ok_cov = ratio >= 0.5
        if ok_cov:
            coverage_pass += 1
        print(
            f"  Sample {sid}: {hit}/{total} lines = {ratio*100:.1f}%  "
            f"(execs={execs}, crashes={crashes})  {'OK' if ok_cov else 'LOW'}"
        )

    cov_score = 5 if coverage_pass == 4 else int(5 * coverage_pass / 4)
    scores.append(("Fuzzer 可用性", cov_score, 5, f"{coverage_pass}/4 sample 达 50%"))

    # Code implementation: need mutator + path + extra scheduler
    impl_ok = scores[1][1] == 4 and scores[2][1] == 4 and ok_extra
    impl_score = 4 if impl_ok else (3 if scores[1][1] == 4 and scores[2][1] == 4 else 2)
    scores[1] = ("代码实现", impl_score, 4, f"变异+路径调度{'+第三种' if ok_extra else '(缺第三种)'}")

    report_score = 0
    scores.append(("测试报告 PDF", report_score, 3, "需人工提交，代码无法检测"))

    total = sum(s[1] for s in scores)
    max_total = sum(s[2] for s in scores)

    print("\n" + "=" * 60)
    print("预估得分汇总")
    print("=" * 60)
    for name, got, mx, detail in scores:
        print(f"  {name}: {got}/{mx}  ({detail})")
    print(f"\n  当前代码可拿约: {total}/{max_total} 分")
    print(f"  完成测试报告 PDF 后最多还可 +3 分 → 上限 {total + 3}/{max_total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
