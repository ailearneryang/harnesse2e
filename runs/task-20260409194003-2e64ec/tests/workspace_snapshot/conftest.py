"""测试 fixtures —— 冒泡排序测试共享数据集。

来源：data_model.md 预定义测试数据集（10 组覆盖全部需求）。
"""

from __future__ import annotations

import pytest


# ---------- 基本场景 ----------

@pytest.fixture
def empty_list() -> list:
    """F003: 空列表。"""
    return []


@pytest.fixture
def single_element() -> list[int]:
    """F004: 单元素列表。"""
    return [42]


@pytest.fixture
def sorted_list() -> list[int]:
    """已排序列表（提前终止优化验证）。"""
    return [1, 2, 3, 4, 5]


@pytest.fixture
def reverse_list() -> list[int]:
    """F005: 逆序列表（最差情况）。"""
    return [5, 4, 3, 2, 1]


@pytest.fixture
def random_list() -> list[int]:
    """F001: 一般乱序列表。"""
    return [64, 34, 25, 12, 22, 11, 90]


# ---------- 边界场景 ----------

@pytest.fixture
def duplicates_list() -> list[int]:
    """F006: 包含重复元素的列表。"""
    return [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]


@pytest.fixture
def negative_list() -> list[int]:
    """F007: 包含负数与正数的列表。"""
    return [-3, 5, -1, 0, 4, -2, 3]


@pytest.fixture
def float_list() -> list[float]:
    """F008: 浮点数列表。"""
    return [3.14, 1.41, 2.72, 0.58, 1.73]


@pytest.fixture
def mixed_int_float() -> list[int | float]:
    """F008: 整数与浮点数混合列表。"""
    return [3, 1.5, 2, 0.5, 4]


# ---------- 大数据场景 ----------

@pytest.fixture
def large_list() -> list[int]:
    """NFR-001: 1000 元素列表，用于性能测试。"""
    import random
    rng = random.Random(42)  # 固定种子保证可复现
    return rng.sample(range(10000), 1000)
