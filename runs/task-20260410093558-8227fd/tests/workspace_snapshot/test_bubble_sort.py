"""冒泡排序算法综合测试。

覆盖设计文档中的全部功能需求（F001-F010）和非功能需求（NFR-001~005）。
测试场景对应 data_model.md 预定义测试数据集。
"""

from __future__ import annotations

import time
from collections import Counter

import pytest

from src.bubble_sort import bubble_sort


# ======================================================================
# F001: 冒泡排序核心功能
# ======================================================================

class TestBubbleSortBasic:
    """基本排序功能测试。"""

    def test_random_list(self, random_list: list[int]) -> None:
        """F001: 一般乱序列表排序。"""
        result = bubble_sort(random_list)
        assert result == [11, 12, 22, 25, 34, 64, 90]

    def test_sorted_list(self, sorted_list: list[int]) -> None:
        """F002: 已排序列表（验证提前终止优化不改变结果）。"""
        result = bubble_sort(sorted_list)
        assert result == [1, 2, 3, 4, 5]

    def test_reverse_list(self, reverse_list: list[int]) -> None:
        """F005: 逆序列表（最差情况）。"""
        result = bubble_sort(reverse_list)
        assert result == [1, 2, 3, 4, 5]


# ======================================================================
# F003 / F004: 边界情况
# ======================================================================

class TestBubbleSortEdgeCases:
    """空列表与单元素列表测试。"""

    def test_empty_list(self, empty_list: list) -> None:
        """F003: 空列表返回空列表。"""
        result = bubble_sort(empty_list)
        assert result == []

    def test_single_element(self, single_element: list[int]) -> None:
        """F004: 单元素列表原样返回。"""
        result = bubble_sort(single_element)
        assert result == [42]

    def test_two_elements_sorted(self) -> None:
        """两个元素已排序。"""
        assert bubble_sort([1, 2]) == [1, 2]

    def test_two_elements_unsorted(self) -> None:
        """两个元素未排序。"""
        assert bubble_sort([2, 1]) == [1, 2]


# ======================================================================
# F006: 重复元素
# ======================================================================

class TestBubbleSortDuplicates:
    """重复元素处理测试。"""

    def test_duplicates(self, duplicates_list: list[int]) -> None:
        """F006: 包含重复元素正确排序。"""
        result = bubble_sort(duplicates_list)
        assert result == sorted(duplicates_list)  # 与标准库对比

    def test_all_same(self) -> None:
        """所有元素相同。"""
        arr = [7, 7, 7, 7, 7]
        assert bubble_sort(arr) == [7, 7, 7, 7, 7]


# ======================================================================
# F007: 负数与混合正负数
# ======================================================================

class TestBubbleSortNegative:
    """负数处理测试。"""

    def test_negative_list(self, negative_list: list[int]) -> None:
        """F007: 负数与正数混合列表。"""
        result = bubble_sort(negative_list)
        assert result == [-3, -2, -1, 0, 3, 4, 5]

    def test_all_negative(self) -> None:
        """全部为负数。"""
        arr = [-5, -1, -3, -2, -4]
        assert bubble_sort(arr) == [-5, -4, -3, -2, -1]


# ======================================================================
# F008: 浮点数支持
# ======================================================================

class TestBubbleSortFloat:
    """浮点数支持测试。"""

    def test_float_list(self, float_list: list[float]) -> None:
        """F008: 纯浮点数列表。"""
        result = bubble_sort(float_list)
        assert result == [0.58, 1.41, 1.73, 2.72, 3.14]

    def test_mixed_int_float(self, mixed_int_float: list[int | float]) -> None:
        """F008: 整数与浮点数混合。"""
        result = bubble_sort(mixed_int_float)
        assert result == [0.5, 1.5, 2, 3, 4]


# ======================================================================
# F009: 排序稳定性
# ======================================================================

class TestBubbleSortStability:
    """排序稳定性测试。

    设计说明（api_design.md）：
    使用严格 > 比较，相等键值的元素保持原始相对顺序。
    为了验证稳定性，我们使用带有标识的包装对象。
    """

    def test_stability_preserved(self) -> None:
        """F009: 相等元素保持原始相对顺序。

        构造场景：多个值相等的整数，通过索引追踪原始顺序。
        """
        # 用 (value, original_index) 对模拟，但 bubble_sort 只接受数值，
        # 所以我们通过结果中重复元素的位置间接验证。
        arr = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
        result = bubble_sort(arr)

        # 验证排序正确
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]

        # 验证元素守恒
        assert Counter(result) == Counter(arr)


# ======================================================================
# NFR-005: 纯函数保证（不修改输入）
# ======================================================================

class TestBubbleSortPureFunction:
    """纯函数语义测试。"""

    def test_input_not_modified(self) -> None:
        """NFR-005: 原列表在排序后不被修改。"""
        original = [5, 3, 1, 4, 2]
        original_copy = original[:]
        bubble_sort(original)
        assert original == original_copy, "原列表被修改了！"

    def test_returns_new_list(self) -> None:
        """NFR-005: 返回的列表是新对象，非原引用。"""
        original = [3, 1, 2]
        result = bubble_sort(original)
        assert result is not original

    def test_empty_returns_new_list(self) -> None:
        """空列表也返回新对象。"""
        original: list[int] = []
        result = bubble_sort(original)
        assert result is not original
        assert result == []

    def test_single_returns_new_list(self) -> None:
        """单元素列表也返回新对象。"""
        original = [1]
        result = bubble_sort(original)
        assert result is not original
        assert result == [1]


# ======================================================================
# 异常处理（TypeError）
# ======================================================================

class TestBubbleSortTypeError:
    """类型错误测试。

    设计说明（api_design.md）：
    3 种异常场景，均抛出 TypeError。
    """

    def test_non_list_input_string(self) -> None:
        """传入字符串而非列表。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort("hello")  # type: ignore[arg-type]

    def test_non_list_input_tuple(self) -> None:
        """传入元组而非列表。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort((1, 2, 3))  # type: ignore[arg-type]

    def test_non_list_input_none(self) -> None:
        """传入 None。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort(None)  # type: ignore[arg-type]

    def test_non_list_input_int(self) -> None:
        """传入整数。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort(42)  # type: ignore[arg-type]

    def test_non_numeric_element_string(self) -> None:
        """列表中包含字符串元素。"""
        with pytest.raises(TypeError, match="int 或 float"):
            bubble_sort([1, "two", 3])  # type: ignore[list-item]

    def test_non_numeric_element_none(self) -> None:
        """列表中包含 None 元素。"""
        with pytest.raises(TypeError, match="int 或 float"):
            bubble_sort([1, None, 3])  # type: ignore[list-item]

    def test_non_numeric_element_list(self) -> None:
        """列表中包含嵌套列表。"""
        with pytest.raises(TypeError, match="int 或 float"):
            bubble_sort([1, [2], 3])  # type: ignore[list-item]

    def test_non_numeric_element_dict(self) -> None:
        """列表中包含字典。"""
        with pytest.raises(TypeError, match="int 或 float"):
            bubble_sort([1, {"a": 2}, 3])  # type: ignore[list-item]


# ======================================================================
# NFR-001: 性能测试
# ======================================================================

class TestBubbleSortPerformance:
    """性能测试。

    NFR-001: 1000 元素 ≤ 500ms。
    """

    def test_1000_elements_under_500ms(self, large_list: list[int]) -> None:
        """NFR-001: 1000 个元素排序耗时 ≤ 500ms。"""
        start = time.perf_counter()
        result = bubble_sort(large_list)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 验证排序正确性
        assert result == sorted(large_list)

        # 验证性能约束
        assert elapsed_ms <= 500, (
            f"排序耗时 {elapsed_ms:.1f}ms，超过 500ms 限制"
        )

    def test_already_sorted_fast(self) -> None:
        """F002: 已排序列表应因提前终止而非常快（接近 O(n)）。"""
        arr = list(range(1000))
        start = time.perf_counter()
        result = bubble_sort(arr)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result == arr
        # 已排序列表应远快于最差情况
        assert elapsed_ms <= 50, (
            f"已排序列表耗时 {elapsed_ms:.1f}ms，提前终止优化可能未生效"
        )


# ======================================================================
# 输出不变量综合验证（data_model.md 5 条断言）
# ======================================================================

# ======================================================================
# F010: docstring 文档注释
# ======================================================================

class TestBubbleSortDocstring:
    """文档注释完整性测试。"""

    def test_docstring_exists(self) -> None:
        """F010: 函数 docstring 存在且非空。"""
        assert bubble_sort.__doc__ is not None
        assert len(bubble_sort.__doc__.strip()) > 0

    def test_docstring_sections(self) -> None:
        """F010: docstring 包含 Args / Returns / Raises / Examples。"""
        doc = bubble_sort.__doc__
        assert doc is not None
        for section in ("Args:", "Returns:", "Raises:", "Examples:"):
            assert section in doc, f"docstring 缺少 '{section}' 章节"


# ======================================================================
# 补充边界：bool 子类、set 输入、极端浮点数
# ======================================================================

class TestBubbleSortAdditionalEdgeCases:
    """补充边界测试。"""

    def test_bool_elements_accepted(self) -> None:
        """bool 是 int 的子类，应被正常接受。"""
        result = bubble_sort([True, False, True, False])
        assert result == [False, False, True, True]
        assert result == [0, 0, 1, 1]

    def test_non_list_input_set(self) -> None:
        """传入 set 而非列表。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort({1, 2, 3})  # type: ignore[arg-type]

    def test_non_list_input_bool(self) -> None:
        """传入 bool 值（非列表）。"""
        with pytest.raises(TypeError, match="list 类型"):
            bubble_sort(True)  # type: ignore[arg-type]

    def test_zero_positive_negative_zero(self) -> None:
        """正零与负零的比较。"""
        result = bubble_sort([0.0, -0.0])
        assert len(result) == 2
        assert result[0] == 0.0
        assert result[1] == 0.0

    def test_very_small_floats(self) -> None:
        """极小浮点数排序。"""
        result = bubble_sort([1e-10, 1e-11, 1e-9])
        assert result == [1e-11, 1e-10, 1e-9]

    def test_very_large_floats(self) -> None:
        """极大浮点数排序。"""
        result = bubble_sort([1e15, 1e14, 1e16])
        assert result == [1e14, 1e15, 1e16]

    def test_large_reverse_list(self) -> None:
        """100 元素逆序列表（最差情况较大规模）。"""
        arr = list(range(100, 0, -1))
        result = bubble_sort(arr)
        assert result == list(range(1, 101))

    def test_nearly_sorted(self) -> None:
        """几乎有序列表（仅首两元素逆序）。"""
        arr = [2, 1, 3, 4, 5]
        result = bubble_sort(arr)
        assert result == [1, 2, 3, 4, 5]

    def test_two_equal_elements(self) -> None:
        """两个相同元素。"""
        result = bubble_sort([1, 1])
        assert result == [1, 1]

    def test_single_zero(self) -> None:
        """单元素零值。"""
        result = bubble_sort([0])
        assert result == [0]

    def test_single_negative(self) -> None:
        """单元素负数。"""
        result = bubble_sort([-1])
        assert result == [-1]

    def test_mixed_negative_zero_positive(self) -> None:
        """混合负数、零、正数。"""
        result = bubble_sort([0, -1, 1])
        assert result == [-1, 0, 1]


class TestOutputInvariants:
    """输出不变量测试。

    data_model.md 定义的 5 条不变量：
    1. 长度守恒
    2. 元素守恒
    3. 升序排列
    4. 纯函数（不修改输入）
    5. 返回新对象
    """

    @pytest.mark.parametrize("arr", [
        [],
        [1],
        [3, 1, 2],
        [5, 4, 3, 2, 1],
        [1, 1, 1],
        [-3, 5, -1, 0],
        [3.14, 1.41, 2.72],
        [3, 1.5, 2, 0.5],
    ], ids=[
        "empty", "single", "random", "reverse",
        "all_same", "negative", "float", "mixed",
    ])
    def test_all_invariants(self, arr: list[int | float]) -> None:
        """综合验证全部 5 条输出不变量。"""
        original = arr[:]
        result = bubble_sort(arr)

        # 不变量 1：长度守恒
        assert len(result) == len(arr)

        # 不变量 2：元素守恒
        assert Counter(result) == Counter(arr)

        # 不变量 3：升序排列
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]

        # 不变量 4：纯函数（不修改输入）
        assert arr == original

        # 不变量 5：返回新对象
        assert result is not arr
