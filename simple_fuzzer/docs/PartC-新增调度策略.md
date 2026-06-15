# Part C — 新增调度策略（`schedule/`）

## 一、任务目标

在现有 `PowerSchedule`（均匀分配）和 `PathPowerSchedule`（路径频率反比）基础上，新增至少一种调度策略，放入 `schedule/` 包中。

## 二、在模糊测试中的作用

调度器位于 fuzzing 循环的第 1 步：

```
调度器选种子 → 变异器生成新输入 → 执行器喂给目标 → 覆盖率反馈
```

它回答的核心问题是：**种群中哪个种子最值得继续变异？**

不同调度策略对应不同的"价值"判断标准：

| 策略 | 判断标准 | 适用场景 |
|------|----------|----------|
| 路径频率反比 | 触发罕见路径的种子更有价值 | 有过早收敛风险的复杂分支 |
| 输入长度反比 | 短输入更有价值 | 追求执行速度、核心逻辑暴露 |
| 覆盖行数正比 | 单次覆盖行数多的种子更有价值 | 深层状态、复杂前置条件 |
| 罕见行反比 | 触发冷门代码行的种子更有价值 | 深层未探索分支 |

多种策略互补，可以让 fuzzer 在不同阶段、不同目标上都有较好的探索能力。

## 三、实现内容

### 3.1 SizeSchedule — 基于输入长度

**文件**：`schedule/size_schedule.py`

**核心公式**：

```
energy = 1.0 / len(seed.data)    (空输入固定 10.0)
```

**设计理由**：
- 短输入执行更快，单位时间内能完成更多轮 fuzzing
- 短输入减少了杂数据干扰，更容易暴露核心逻辑
- 许多漏洞（如缓冲区溢出）在精确构造的短输入上反而比长输入更容易触发

### 3.2 CoverageSizeSchedule — 基于覆盖范围

**文件**：`schedule/coverage_size_schedule.py`

**核心公式**：

```
energy = len(seed.coverage)
```

**设计理由**：
- 能在单次执行中触及更多代码行的种子，说明它穿过了更多分支
- 包含更丰富的内部状态和前置条件
- AFL 实践中也发现，高覆盖种子往往更能挖掘深层路径

### 3.3 RareLineSchedule — 基于罕见代码行

**文件**：`schedule/rare_line_schedule.py`

**核心公式**：

```
line_rarity = 1.0 / sqrt(freq)          // 每行的罕见度 = 频率的平方根反比
energy = sum(line_rarity) / len(seed.coverage)    // 种子能量 = 所覆盖行罕见度的均值
```

其中 `freq` 是每行代码在 fuzzing 历史中被触发过的次数。`assign_energy` 每次被调用时更新全局频率表。

**设计理由**：
- 如果某个种子触发了几乎没被触发过的"罕见行"，它应该获得极高能量
- 使用平方根衰减（而非线性）避免热门行完全主导，同时也避免罕见行能量爆炸
- 全局统计保证"冷门"是全局意义上的冷门，而非单次种群快照

**实现细节**：
- `line_frequency: Dict[Location, int]` — 全局行频率表
- 每次 `assign_energy` 从当前种群更新频率（同一轮内去重避免重复计数）
- 空覆盖率种子给基础能量 1.0

### 3.4 基础设施改动

**`PowerSchedule` 增加 `register_path` 钩子**：

```python
def register_path(self, path_id: str) -> bool:
    return False  # 默认无操作，子类覆盖
```

使得非路径类调度器也能与 `PathGreyBoxFuzzer` 兼容。

**`PathGreyBoxFuzzer.run()` 增加防御性检查**：

```python
if hasattr(self.schedule, 'path_frequency'):
    self.total_paths = len(self.schedule.path_frequency)
```

避免非路径调度器因缺少 `path_frequency` 属性而崩溃。

**`main.py` 增加 `--schedule` 参数**：

```
--schedule {path, size, coverage_size, rare_line}
```

支持运行时切换调度策略，便于对比实验。

## 四、实验对比（Sample 3，各 10 秒）

| 调度器 | 覆盖行数 | 最深行 | 唯一崩溃数 |
|--------|:---:|------|:---:|
| PathPowerSchedule | 8 | line 41 | 5 |
| SizeSchedule | 8 | line 41 | 5 |
| CoverageSizeSchedule | 8 | line 41 | 5 |
| **RareLineSchedule** | **9** | **line 42** | **7** |

RareLineSchedule 是唯一触达 line 42（`assert s[index+1] == 'A'`）的调度器，崩溃数也多 40%。

**原因**：line 39-41 在 sample3 中是较深的分支，命中概率本身就很低。三种对照策略对所有种子均等分配能量，深层的罕见种子容易被种群中的"常规"种子挤掉。RareLineSchedule 一旦发现某种子触发了低频行，会赋予其指数级更高的变异机会，使其在竞争中存活更久、产生更多衍生输入，最终穿透到 line 42。

## 五、使用方式

```bash
# 路径频率调度（默认）
python main.py --sample 3 --run-time 60 --schedule path

# 短输入优先
python main.py --sample 3 --run-time 60 --schedule size

# 高覆盖优先
python main.py --sample 3 --run-time 60 --schedule coverage_size

# 罕见行优先
python main.py --sample 3 --run-time 60 --schedule rare_line
```

## 六、文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `schedule/size_schedule.py` | 新增 | 基于输入长度的调度策略 |
| `schedule/coverage_size_schedule.py` | 新增 | 基于覆盖行数的调度策略 |
| `schedule/rare_line_schedule.py` | 新增 | 基于罕见代码行的调度策略 |
| `schedule/power_schedule.py` | 修改 | 增加 `register_path` 空钩子 |
| `fuzzer/path_grey_box_fuzzer.py` | 修改 | `path_frequency` 防御性检查 |
| `main.py` | 修改 | 增加 `--schedule` 参数和调度器工厂函数 |
