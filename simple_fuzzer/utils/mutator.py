import random
from typing import Any, List


def _to_bytes(s: str) -> bytearray:
    """Encode string to bytearray using latin-1 to preserve all byte values."""
    return bytearray(s.encode('latin-1'))


def _from_bytes(data: bytearray) -> str:
    """Decode bytearray back to string using latin-1."""
    return data.decode('latin-1')


def insert_random_character(s: str) -> str:
    """
    向 s 中下标为 pos 的位置插入一个随机 byte
    pos 为随机生成，范围为 [0, len(s)]
    插入的 byte 为随机生成，范围为 [32, 127]
    """
    pos = random.randint(0, len(s))
    random_char = chr(random.randint(32, 126))
    return s[:pos] + random_char + s[pos:]


def delete_random_bytes(s: str) -> str:
    """
    随机删除一段连续字节
    随机选取起始位置和长度，删除该段内容
    """
    if not s:
        return s
    data = _to_bytes(s)
    length = len(data)
    pos = random.randint(0, length - 1)
    max_del = min(length - pos, 16)
    del_len = random.randint(1, max_del)
    return _from_bytes(data[:pos] + data[pos + del_len:])


def flip_random_bits(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 bitflip 与 random havoc 实现相邻 N 位翻转（N = 1, 2, 4），其中 N 为随机生成
    从 s 中随机挑选一个 bit，将其与其后面 N - 1 位翻转（翻转即 0 -> 1; 1 -> 0）
    注意：不要越界
    """
    if not s:
        return s

    data = _to_bytes(s)
    total_bits = len(data) * 8

    N = random.choice([1, 2, 4])
    if total_bits < N:
        return s

    bit_index = random.randint(0, total_bits - N)

    for i in range(N):
        current_bit = bit_index + i
        byte_index = current_bit // 8
        bit_offset = current_bit % 8
        data[byte_index] ^= (1 << (7 - bit_offset))

    return _from_bytes(data)

def arithmetic_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 arithmetic inc/dec 与 random havoc 实现相邻 N 字节随机增减（N = 1, 2, 4），其中 N 为随机生成
    字节随机增减：
        1. 取其中一个 byte，将其转换为数字 num1；
        2. 将 num1 加上一个 [-35, 35] 的随机数，得到 num2；
        3. 用 num2 所表示的 byte 替换该 byte
    从 s 中随机挑选一个 byte，将其与其后面 N - 1 个 bytes 进行字节随机增减
    注意：不要越界；如果出现单个字节在添加随机数之后，可以通过取模操作使该字节落在 [0, 255] 之间
    """
    if not s:
        return s

    data = _to_bytes(s)
    N = random.choice([1, 2, 4])

    if len(data) < N:
        return s

    pos = random.randint(0, len(data) - N)

    for i in range(N):
        original = data[pos + i]
        delta = random.randint(-35, 35)
        modified = (original + delta) % 256
        data[pos + i] = modified

    return _from_bytes(data)


def interesting_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 interesting values 与 random havoc 实现相邻 N 字节随机替换为 interesting_value（N = 1, 2, 4），其中 N 为随机生成
    interesting_value 替换：
        1. 构建分别针对于 1, 2, 4 bytes 的 interesting_value 数组；
        2. 随机挑选 s 中相邻连续的 1, 2, 4 bytes，将其替换为相应 interesting_value 数组中的随机元素；
    注意：不要越界
    """
    if not s:
        return s

    interesting_values = {
        1: [ord(c) for c in ['A', 'B', 'C', 'Z', '0', '9', '!', '?']],
        2: [int.from_bytes(b, 'big') for b in [b'OK', b'Hi', b'42', b'Go']],
        4: [int.from_bytes(b, 'big') for b in [b'TEST', b'DEAD', b'BEEF', b'GOOD']],
    }

    # 添加边界值：0, 127, 255 等
    interesting_values[1].extend([0, 127, 255, 0x7F, 0xFF])

    data = _to_bytes(s)
    N = random.choice([1, 2, 4])

    if len(data) < N:
        return s

    pos = random.randint(0, len(data) - N)

    value = random.choice(interesting_values[N])
    value_bytes = value.to_bytes(N, byteorder='big')

    for i in range(N):
        data[pos + i] = value_bytes[i]

    return _from_bytes(data)


def havoc_random_insert(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机插入
    随机选取一个位置，插入一段的内容，其中 75% 的概率是插入原文中的任意一段随机长度的内容，25% 的概率是插入一段随机长度的 bytes
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)
    insert_pos = random.randint(0, length)

    max_len = min(16, length) if length > 0 else 16
    insert_len = random.randint(1, max_len if max_len > 0 else 1)

    if random.random() < 0.75:
        if length == 0:
            insert_bytes = bytearray()
        else:
            start_pos = random.randint(0, max(0, length - insert_len))
            insert_bytes = data[start_pos:start_pos + insert_len]
    else:
        insert_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(insert_len))

    new_data = data[:insert_pos] + insert_bytes + data[insert_pos:]
    return _from_bytes(new_data)


def havoc_random_replace(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机替换
    随机选取一个位置，替换随后一段随机长度的内容，其中 75% 的概率是替换为原文中的任意一段随机长度的内容，25% 的概率是替换为一段随机长度的 bytes
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)

    pos = random.randint(0, length - 1)

    max_len = min(16, length - pos)
    replace_len = random.randint(1, max_len)

    if random.random() < 0.75:
        if length - replace_len <= 0:
            replace_bytes = bytearray()
        else:
            start = random.randint(0, length - replace_len)
            replace_bytes = data[start:start + replace_len]
    else:
        replace_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(replace_len))

    new_data = data[:pos] + replace_bytes + data[pos + replace_len:]
    return _from_bytes(new_data)


def duplicate_random_bytes(s: str) -> str:
    """
    随机选取一段字节并将其复制插入到另一个随机位置
    1. 随机选取一段长度 L (1~8) 的内容
    2. 随机选取一个插入位置
    3. 将该段内容复制并插入到该位置
    """
    if not s:
        return s
    data = _to_bytes(s)
    length = len(data)
    L = random.randint(1, min(8, length))
    src_pos = random.randint(0, length - L)
    segment = data[src_pos:src_pos + L]
    insert_pos = random.randint(0, length)
    new_data = data[:insert_pos] + segment + data[insert_pos:]
    return _from_bytes(new_data)

def random_block_swap(s: str) -> str:
    """
    随机选取两个相邻的字节块并交换顺序
    1. 随机选定整个字符串长度内，选取一段长度 L1 (1~8) 和紧随其后的另一段长度 L2 (1~8)
    2. 交换这两段字节块的顺序
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)
    if length < 2:
        return s

    max_block_size = 8
    L1 = random.randint(1, min(max_block_size, length // 2))
    L2 = random.randint(1, min(max_block_size, length - L1))

    start_pos = random.randint(0, length - (L1 + L2))

    block1 = data[start_pos:start_pos + L1]
    block2 = data[start_pos + L1:start_pos + L1 + L2]

    new_data = data[:start_pos] + block2 + block1 + data[start_pos + L1 + L2:]
    return _from_bytes(new_data)


class Mutator:

    def __init__(self) -> None:
        self.mutators: List = [
            insert_random_character,
            delete_random_bytes,
            flip_random_bits,
            arithmetic_random_bytes,
            interesting_random_bytes,
            havoc_random_insert,
            havoc_random_replace,
            duplicate_random_bytes,
            random_block_swap,
        ]
        # 为不同变异类型分配权重，删除类操作概率较低避免输入过快缩小
        self.weights = [10, 5, 10, 10, 10, 15, 15, 10, 10]

    def mutate(self, inp: Any) -> Any:
        mutator = random.choices(self.mutators, weights=self.weights)[0]
        try:
            return mutator(inp)
        except Exception:
            return inp