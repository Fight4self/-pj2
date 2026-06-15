# Part A — 变异策略完善（`mutator.py`）

## 一、任务目标

完善 `utils/mutator.py` 中的输入变异策略，确保多种不同类型的变异算子能够正常工作。

## 二、变异策略在模糊测试中的作用

在框架的数据流中（参见 README 架构图），变异器处于 fuzzing 循环的第 2 步：

```
调度器选种子 → 变异器生成新输入 → 执行器喂给目标程序 → 覆盖率反馈
```

具体作用体现在三个层面：

### 2.1 从已知探索未知

种子只是少数几个已知的输入。变异器通过对种子进行随机扰动（翻转 bit、增删字节、替换片段等），生成大量"看起来像但又不完全一样"的新输入，试图触达种子未曾覆盖的代码分支。没有变异器，fuzzer 只是在不断重复执行相同的种子，不可能发现新路径或崩溃。

### 2.2 多维度互补覆盖

单一变异类型容易陷入盲区。例如：

- 只有插入没有删除 → 输入越来越长，无法测试短输入路径
- 只有字节替换没有 bit 翻转 → 难以触发 `if (x & 0x80)` 这类位运算边界
- 只有随机操作没有边界值 → 难以命中 `if (x == 0)` 或 `if (x == 255)` 这类精确比较

9 种变异类型覆盖了 **长度变化**（插入、删除）、**值变化**（翻转、算术、边界值替换）、**结构重排**（复制、块交换、随机替换）三个维度，互补探索更广的输入空间。

### 2.3 模拟破坏性攻击

很多漏洞（缓冲区溢出、格式化字符串、除零异常、越界访问）只有在输入"不符合预期"时才会暴露。变异器的随机性和多样性正是在模拟攻击者构造畸形输入的过程——它不关心输入"应该"是什么，只关心输入"还能"是什么。

### 2.4 与其他模块的关系

| 上游/下游模块 | 关系 |
|---------------|------|
| `schedule`（调度器） | 调度器决定"变异谁"，提供被选中的种子 |
| `runner`（执行器） | 变异结果通过执行器喂给目标，间接影响覆盖率反馈 |
| `grey_box_fuzzer`（Fuzzer） | Fuzzer 调用变异器生成候选输入，新覆盖的变异结果被加入种群 |

简而言之：**调度器决定"变异谁"，变异器决定"怎么变"，覆盖率决定"变异有没有价值"**。

## 三、现有基础

原始文件已有 7 种变异算子，参考了 AFL 的 bitflip、arithmetic、interesting values 和 random havoc 等策略：

| 算子 | 类型 | 说明 |
|------|------|------|
| `insert_random_character` | 插入 | 在随机位置插入一个可打印 ASCII 字符 |
| `flip_random_bits` | 位翻转 | 相邻 N 位翻转（N=1,2,4） |
| `arithmetic_random_bytes` | 算术 | 相邻 N 字节加减随机偏移 |
| `interesting_random_bytes` | 替换 | 用 interesting values 替换 N 字节 |
| `havoc_random_insert` | 插入 | 随机插入一段内容（75%来自原文，25%随机） |
| `havoc_random_replace` | 替换 | 随机替换一段内容（75%来自原文，25%随机） |
| `random_block_swap` | 重排 | 交换相邻两个字节块 |

## 四、问题分析

1. **缺失删除类操作** — 现有算子只有插入、替换、重排，没有删除字节的能力。AFL 的策略中删除是重要的变异类型。
2. **缺失复制/重复操作** — 将一段内容复制到另一位置，有助于触发缓冲区溢出或格式字符串漏洞。
3. **UTF-8 编解码风险** — 字节级变异使用 `s.encode('utf-8')` 和 `data.decode('utf-8', errors='ignore')`，当变异产生非法 UTF-8 序列时，`errors='ignore'` 会丢弃字节，导致数据丢失。
4. **缺少边界值** — `interesting_values` 只包含可打印字符，缺少 `0x00`、`0xFF`、`0x7F` 等常见边界值。
5. **无异常保护** — 任意一个变异器抛异常都会导致整个 fuzzing 流程中断。

## 五、改动内容

### 5.1 新增编解码辅助函数

```python
def _to_bytes(s: str) -> bytearray:
    return bytearray(s.encode('latin-1'))

def _from_bytes(data: bytearray) -> str:
    return data.decode('latin-1')
```

**选择 latin-1 的原因**：Latin-1 编码将字节 0–255 一一映射到对应字符，不存在非法序列，因此编解码完全可逆，不会丢失任何字节数据。对于 fuzzing 这种需要精确控制字节内容的场景，latin-1 是比 UTF-8 更合适的内部编码。

### 5.2 新增 `delete_random_bytes`

- 随机选取起始位置和删除长度（1~16 字节）
- 删除该段内容，返回缩短后的输入
- 空输入直接返回原值

### 5.3 新增 `duplicate_random_bytes`

- 随机选取一段长度 L（1~8 字节）的内容
- 随机选取一个插入位置
- 将该段内容复制并插入到目标位置
- 模拟"重复写入"场景，有助于触发缓冲区相关漏洞

### 5.4 统一编码方式

将 `flip_random_bits`、`arithmetic_random_bytes`、`interesting_random_bytes`、`havoc_random_insert`、`havoc_random_replace`、`random_block_swap` 中的 `s.encode('utf-8')` / `data.decode('utf-8', errors='ignore')` 全部替换为 `_to_bytes(s)` / `_from_bytes(data)`。

### 5.5 扩充 interesting values

在单字节档增加边界值 `0`、`127`、`255`、`0x7F`、`0xFF`，覆盖：
- 整数溢出边界（-128, 127, 255）
- 符号位边界（0x7F → 0x80）
- 空字节（用于触发字符串终止）

### 5.6 变异器权重机制

```python
self.weights = [10, 5, 10, 10, 10, 15, 15, 10, 10]
```

删除类操作（`delete_random_bytes`）权重较低（5），避免输入过快缩小导致信息丢失；随机类操作（`havoc_*`）权重较高（15），因为随机扰动是探索新路径的主要动力。

### 5.7 异常保护

```python
def mutate(self, inp: Any) -> Any:
    mutator = random.choices(self.mutators, weights=self.weights)[0]
    try:
        return mutator(inp)
    except Exception:
        return inp
```

任何变异器抛出异常时，返回原输入，保证 fuzzing 循环不中断。

## 六、最终变异类型总览

| 序号 | 算子 | 类型 | 权重 |
|------|------|------|------|
| 1 | `insert_random_character` | 单字符插入 | 10 |
| 2 | `delete_random_bytes` | 删除 ★新增 | 5 |
| 3 | `flip_random_bits` | 位翻转 | 10 |
| 4 | `arithmetic_random_bytes` | 算术增减 | 10 |
| 5 | `interesting_random_bytes` | 边界值替换 | 10 |
| 6 | `havoc_random_insert` | 随机段插入 | 15 |
| 7 | `havoc_random_replace` | 随机段替换 | 15 |
| 8 | `duplicate_random_bytes` | 复制重复 ★新增 | 10 |
| 9 | `random_block_swap` | 块交换 | 10 |

## 七、测试验证

在空串、短串、长串、含空字节的二进制数据上分别执行所有变异器，确认：

- 所有变异器对合法输入不抛异常
- 空串由各变异器自行处理（插入类可生成新内容，删除/翻转类返回空串）
- `Mutator.mutate()` 在任何输入上均不崩溃
- latin-1 编解码可无损传输字节 0–255
