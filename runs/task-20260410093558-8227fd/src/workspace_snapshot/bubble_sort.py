"""冒泡排序模块。

提供经典冒泡排序算法的纯函数实现，支持整数和浮点数列表的升序排序。

设计要点（来自 architecture.md / api_design.md）：
  - 纯函数语义：返回新列表，不修改输入
  - 提前终止优化：通过 swapped 标志位，已排序列表 O(n)
  - 排序稳定性：使用严格 > 比较，相等元素保持原始顺序
  - 异常处理：非列表输入或包含非数值元素时抛出 TypeError
  - 禁止使用内置 sorted() / list.sort()
"""

from __future__ import annotations


def bubble_sort(arr: list[int | float]) -> list[int | float]:
    """对数值列表进行升序冒泡排序，返回排序后的新列表。

    算法逻辑：
      1. 复制输入列表（纯函数保证）
      2. 外层循环控制趟数（最多 n-1 趟）
      3. 内层循环执行相邻元素比较与交换
      4. swapped 标志位实现提前终止优化
      5. 使用严格 > 比较确保排序稳定性

    Args:
        arr: 包含整数或浮点数的列表。

    Returns:
        升序排列的新列表，原列表不被修改。

    Raises:
        TypeError: 当 arr 不是 list 类型时。
        TypeError: 当 arr 中包含非数值（int/float）元素时。

    Examples:
        >>> bubble_sort([3, 1, 2])
        [1, 2, 3]
        >>> bubble_sort([])
        []
        >>> bubble_sort([1])
        [1]
        >>> original = [5, 3, 1]
        >>> sorted_list = bubble_sort(original)
        >>> original  # 原列表未被修改
        [5, 3, 1]
    """
    # --- 输入校验 ---
    if not isinstance(arr, list):
        raise TypeError(
            f"bubble_sort() 参数必须是 list 类型，"
            f"收到 {type(arr).__name__}"
        )

    # EAFP 策略：遍历检查每个元素是否为数值类型
    for i, item in enumerate(arr):
        if not isinstance(item, (int, float)):
            raise TypeError(
                f"列表元素必须是 int 或 float 类型，"
                f"索引 {i} 处收到 {type(item).__name__}: {item!r}"
            )

    # --- 边界情况：空列表或单元素列表直接返回副本 ---
    n = len(arr)
    if n <= 1:
        return arr[:]

    # --- 核心冒泡排序算法 ---
    # 步骤 1：复制输入列表，保证纯函数语义
    result = arr[:]

    # 步骤 2：外层循环，最多执行 n-1 趟
    for i in range(n - 1):
        # 步骤 4：swapped 标志位，实现提前终止优化
        swapped = False

        # 步骤 3：内层循环，每趟将当前未排序部分的最大值"冒泡"到末尾
        # 每完成一趟，末尾的 i 个元素已排好，无需再比较
        for j in range(n - 1 - i):
            # 步骤 5：严格 > 比较，保证排序稳定性
            # （相等元素不交换，从而保持原始相对顺序）
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
                swapped = True

        # 如果本趟未发生交换，说明列表已有序，提前终止
        if not swapped:
            break

    return result
