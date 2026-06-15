# Part C — 新增调度策略（任务三）

## 一、任务目标

在 `schedule/` 包中增加**至少一种**不同于路径频率的调度策略，并与现有 `PowerSchedule`、`PathPowerSchedule` 形成对比。

本实现新增两种策略：

| 调度器 | 文件 | 核心思想 |
|--------|------|----------|
| **RareLinePowerSchedule** | `rare_line_power_schedule.py` | 触发罕见代码行的 seed 获得更高能量 |
| **SizeBasedPowerSchedule** | `size_power_schedule.py` | 更短的 seed 获得更高能量 |

## 二、RareLinePowerSchedule（罕见代码行调度）

### 2.1 动机

路径频率调度关注「走了哪条执行路径」，而罕见行调度关注「触达了哪些代码行」。一个 seed 即使路径常见，若它覆盖了全局很少被触发的行，仍可能通向深层逻辑，值得优先变异。

### 2.2 行频率统计

每次执行后，Fuzzer 将本次 coverage 交给调度器：

```python
def register_coverage(self, coverage: Set[Location]) -> None:
    for location in coverage:
        self.line_frequency[location] = self.line_frequency.get(location, 0) + 1
```

`GreyBoxFuzzer.run()` 中通过 duck typing 调用：

```python
if hasattr(self.schedule, "register_coverage"):
    coverage = runner.coverage()
    if coverage:
        self.schedule.register_coverage(coverage)
```

### 2.3 能量公式

对 seed 覆盖集中的每一行，计算稀有度：

\[
\text{rarity}(line) = \frac{1}{\text{freq}(line)^{\text{exponent}}}
\]

seed 的能量为其覆盖行稀有度的**平均值**（默认 `exponent = 2.0`）：

\[
\text{energy}(seed) = \frac{1}{|C|} \sum_{line \in C} \text{rarity}(line)
\]

| 行频率 | 单行 rarity（exp=2） |
|--------|------------------------|
| 1 | 1.0 |
| 5 | 0.04 |
| 100 | 0.0001 |

### 2.4 与路径调度的区别

| 维度 | PathPowerSchedule | RareLinePowerSchedule |
|------|-------------------|------------------------|
| 统计粒度 | 执行 trace 的边序列 | 单行 `(函数, 行号)` |
| 反馈时机 | `PathGreyBoxFuzzer.run()` | `GreyBoxFuzzer.run()` hook |
| 适用 Fuzzer | `PathGreyBoxFuzzer` | `GreyBoxFuzzer` |
| 偏好 | 罕见**路径** | 罕见**代码行** |

## 三、SizeBasedPowerSchedule（输入长度调度）

### 3.1 动机

短输入执行更快、变异开销更低，且更少无关字节干扰分支判断。AFL 类 fuzzer 也常对短 corpus 条目给予更多执行机会。

### 3.2 能量公式

\[
\text{energy}(seed) = \frac{1}{\max(len(seed.data), 1)^{\text{exponent}}}
\]

默认 `exponent = 1.0`（反比于长度）。长度为 10 的 seed 能量是长度为 100 的 seed 的 10 倍。

### 3.3 特点

- **无需运行时反馈**：只读 seed 自身属性，不依赖 `register_coverage`
- **实现简单**：适合作为基线对比
- **潜在局限**：过度偏好短输入可能忽略需要长格式的样本（如 Sample 4 HTML）

## 四、入口与切换方式

`main.py` 新增 `--schedule` 参数：

```bash
# 默认：路径频率调度
uv run main.py --sample 2 --run-time 60

# 罕见行调度
uv run main.py --sample 3 --schedule rare-line --run-time 60

# 输入长度调度
uv run main.py --sample 1 --schedule size --run-time 60

# 均匀调度（基线）
uv run main.py --sample 4 --schedule uniform --run-time 60
```

| `--schedule` | Fuzzer 类 | Schedule 类 |
|--------------|-----------|-------------|
| `path`（默认） | `PathGreyBoxFuzzer` | `PathPowerSchedule` |
| `rare-line` | `GreyBoxFuzzer` | `RareLinePowerSchedule` |
| `size` | `GreyBoxFuzzer` | `SizeBasedPowerSchedule` |
| `uniform` | `GreyBoxFuzzer` | `PowerSchedule` |

结果文件命名：`Sample-{N}-{schedule}.pkl`，便于对比实验。

## 五、三种调度策略对比总结

| 策略 | 能量依据 | 优点 | 缺点 |
|------|----------|------|------|
| **Uniform** | 恒定 1 | 简单、无偏 | 不利用反馈，效率低 |
| **Path** | 路径频率反比 | 探索未充分走到的路径 | 需 trace，与 PathGreyBoxFuzzer 耦合 |
| **Rare-Line** | 罕见行反比 | 直达「少被触发的代码行」 | 需每次更新行频率表 |
| **Size** | 输入长度反比 | 执行快、实现轻 | 可能忽略长输入才能触达的分支 |

## 六、测试验证

### 6.1 RareLine 单元测试

```python
schedule = RareLinePowerSchedule(exponent=2.0)
schedule.register_coverage({("sample3", 36)})
schedule.register_coverage({("sample3", 36)})
schedule.register_coverage({("sample3", 42)})

seeds = [
    Seed("a", {("sample3", 36)}),
    Seed("b", {("sample3", 42)}),
]
schedule.assign_energy(seeds)
# seeds[0].energy < seeds[1].energy  （行 36 频率更高，更常见）
```

### 6.2 集成测试

```bash
python scripts/rubric_check.py
```

确认「第三种调度」检测项通过。

### 6.3 对比实验建议（报告用）

固定 `--sample` 与 `--run-time`，分别运行四种 `--schedule`，记录：

- 覆盖行数
- 崩溃数
- 总 exec 次数

分析哪种策略在该 sample 上更合适，避免只写「效果很好」。

## 七、报告撰写要点

1. 说明为何选择 Rare-Line / Size 两种策略及其与 Path 的差异  
2. 给出 energy 公式与频率更新时机  
3. 展示 `--schedule` 切换与对比实验数据  
4. 分析各策略在不同 sample 上的优劣（如 Size 对 Sample 4 长 HTML 可能不利）
