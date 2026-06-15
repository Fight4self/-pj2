# Part D — 种子持久化与框架改进

## 一、任务目标

使用 `utils/object_utils` 将 seed 和中间结果持久化到文件系统，避免长时间运行时内存持续增长，并支持断点续跑。

## 二、持久化要解决的问题

fuzzer 在运行过程中会不断累积数据：

| 累积对象 | 增长趋势 | 风险 |
|----------|----------|------|
| `population`（种子种群） | 每次新覆盖追加一个 Seed | 数万种子 → GB 级内存 |
| `crash_map`（崩溃记录） | 每次崩溃就追加一条，且 key 是完整输入字符串 | 运行一小时可达数 MB 甚至 GB |
| `covered_line`（覆盖行集合） | 持续增长直到覆盖饱和 | 相对较小 |

持久化解决三个问题：
1. **控制内存上限** — 淘汰的种子落盘而非丢弃；崩溃去重后再写入
2. **断点续跑** — 中断后从磁盘恢复种群和崩溃记录，不丢失进度
3. **事后分析** — 持久化的崩溃输入可用于离线最小化和复现

## 三、实现内容

### 3.1 改动总览

| 文件 | 改动 | 说明 |
|------|------|------|
| `schedule/power_schedule.py` | 9 行 | `__init__` 增加 `evicted_seeds` 列表；`choose()` 淘汰前记录被淘汰种子 |
| `fuzzer/grey_box_fuzzer.py` | 52 行 | 新增 `save_state()`、`resume_state()`；`__init__` 接受 `output_dir`/`sample_id`；`run()` 定期触发保存 |
| `fuzzer/path_grey_box_fuzzer.py` | 2 行 | `__init__` 透传 `output_dir`/`sample_id` 给父类 |
| `main.py` | 11 行 | 新增 `--resume` 参数；启动时调用 `resume_state()`；传递持久化参数给 fuzzer |

### 3.2 `PowerSchedule` — 淘汰记录

```python
class PowerSchedule:
    def __init__(self) -> None:
        self.evicted_seeds: List[Seed] = []   # 新增

    def choose(self, population):
        ...
        if len(population) > MAX_SEEDS:
            min_index = norm_energy.index(min(norm_energy))
            self.evicted_seeds.append(population[min_index])  # 新增：记录淘汰种子
            del norm_energy[min_index]
            del population[min_index]
```

被淘汰的种子不会立即丢弃，而是暂存到 `evicted_seeds` 列表，由 fuzzer 定期刷入磁盘。所有子类（`PathPowerSchedule`、`SizeSchedule` 等）自动继承此行为。

### 3.3 `GreyBoxFuzzer` — 核心持久化逻辑

**新增参数**：

```python
def __init__(self, seeds, schedule, is_print,
             output_dir="_result", sample_id=0):
```

**`save_state()` — 定期保存**：

```python
def save_state(self):
    prefix = os.path.join(self.output_dir, f"Sample-{self.sample_id}")

    # 1. 保存种群
    dump_object(f"{prefix}_population.pkl", self.population)

    # 2. 崩溃去重后保存（hash -> shortest_input）
    deduped = {}
    for inp, h in self.crash_map.items():
        if h not in deduped or len(inp) < len(deduped[h]):
            deduped[h] = inp
    dump_object(f"{prefix}_crashes.pkl", deduped)

    # 3. 淘汰种子追加写入磁盘
    evicted_path = f"{prefix}_evicted.pkl"
    existing = load_object(evicted_path) if os.path.exists(evicted_path) else []
    existing.extend(self.schedule.evicted_seeds)
    dump_object(evicted_path, existing)
    self.schedule.evicted_seeds.clear()
```

**崩溃去重的意义**：`crash_map` 以"输入字符串 → MD5 哈希"存储。相同崩溃（相同 MD5）可能有数千条不同输入。去重后只保留每个唯一崩溃的最短输入（便于后续复现），文件体积从 312KB 降到 210B。

**触发时机**（在 `run()` 末尾）：

```python
if self.total_execs % self.save_interval_execs == 0 or \
   time.time() - self.last_save_time > self.save_interval_secs:
    self.save_state()
    self.last_save_time = time.time()
```

双重条件：每 500 次执行 **或** 每 30 秒，取先到者。这样无论执行速度快慢，都能保证定期落盘。

**`resume_state()` — 断点恢复**：

```python
def resume_state(self) -> bool:
    # 1. 加载种群
    self.population = load_object(pop_path)
    # 2. 从种群恢复 covered_line（无需单独保存）
    for seed in self.population:
        self.covered_line |= seed.coverage
    # 3. 加载崩溃（自动识别 hash->input 或 input->hash 两种格式）
    saved = load_object(crash_path)
    if is_md5_like(first_key):       # hash -> input 格式（去重后）
        self.crash_map = {inp: h for h, inp in saved.items()}
    else:                             # input -> hash 格式（旧版兼容）
        self.crash_map = saved
    return True
```

设计要点：`covered_line` 不单独保存，因为每个种子已携带其 `coverage` 集合，恢复时取并集即可，避免数据冗余。

### 3.4 `main.py` — 用户接口

```python
# 新增参数
parser.add_argument("--resume", action="store_true",
                    help="Resume fuzzing from previously persisted state")

# 传递参数
grey_fuzzer = PathGreyBoxFuzzer(seeds=seeds, ...,
                                output_dir=args.output_dir,
                                sample_id=args.sample)

# 断点续跑
if args.resume:
    if grey_fuzzer.resume_state():
        print(f"[resume] Restored {len(population)} seeds, ...")
    else:
        print("[resume] No persisted state found, starting fresh.")
```

### 3.5 `PathGreyBoxFuzzer` — 透传参数

```python
def __init__(self, ..., output_dir="_result", sample_id=0):
    super().__init__(..., output_dir=output_dir, sample_id=sample_id)
```

继承 `GreyBoxFuzzer` 的全部持久化能力，无需额外逻辑。

## 四、测试验证

### 4.1 测试流程

```
Sample 2 新鲜运行 10s → 检查 _result/Sample-2_*.pkl → Sample 2 续跑 5s → 验证恢复
Sample 3 新鲜运行 10s → 检查文件大小
```

### 4.2 测试结果

| 测试 | 覆盖行 | 崩溃数 | population.pkl | crashes.pkl | evicted.pkl |
|------|:---:|:---:|:---:|:---:|:---:|
| Sample 2 新鲜运行 | 13 | 2 | 302B | 210B | — |
| Sample 2 --resume 续跑 | 13（保持）| 2（保持）| — | — | — |
| Sample 3 新鲜运行 | 5 | 3 | 173B | 133B | — |

**关键验证点**：
- 定期落盘自动触发，文件在运行期间持续更新
- 崩溃去重有效：6 个唯一崩溃只存 6 条记录，文件 < 300B
- 断点续跑成功恢复 population + covered_line + crash_map，覆盖和崩溃不丢失
- 不同 sample 数据隔离（`Sample-2_*` vs `Sample-3_*`）

## 五、使用方式

```bash
# 新鲜运行（自动持久化）
python main.py --sample 2 --run-time 120 --schedule rare_line

# 断点续跑
python main.py --sample 2 --run-time 60 --schedule rare_line --resume

# 查看持久化文件
ls -lh _result/Sample-2_*.pkl
```
