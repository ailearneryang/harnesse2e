---
name: ivi-integration-test
description: "车机集成测试技能。Use when: 通过 ADB 连接车机台架执行集成测试、HMI 自动化测试、连接性测试（蓝牙/CarPlay/Android Auto）、性能基准测试（冷启动/帧率/内存）、稳定性测试。关键词: 车机, IVI, head unit, 台架, ADB, 集成测试, HMI, 车载。"
argument-hint: "可选: 设备IP或测试场景名称 (如: 192.168.1.100 或 hmi/connectivity/performance)"
---

# 车机集成测试 (IVI Integration Test)

## 适用场景

- 通过 ADB 连接车机台架，执行端到端集成测试
- HMI 功能验证（界面响应、跳转、输入）
- 连接性测试（蓝牙配对、CarPlay、Android Auto、Wi-Fi）
- 性能基准：冷启动时间、TTI（首屏可交互时间）、内存基线、帧率
- 稳定性验证：长时运行、ANR/Crash 检测、内存泄漏

---

## 工作流程

### Step 1 — 环境准备

1. 确认 ADB 可用：运行 [`./scripts/adb_runner.py --check`](./scripts/adb_runner.py)
2. 连接台架：
   - USB 直连：`adb devices`
   - TCP 网络：`adb connect <HEAD_UNIT_IP>:5555`
3. 验证设备信息（build, Android 版本, HU 型号）

### Step 2 — 加载测试上下文

- 读取 [`./assets/templates/test_case.yaml`](./assets/templates/test_case.yaml) 获取标准用例结构
- 确认测试范围：功能回归 / 专项（HMI/connectivity/performance）
- 加载需求追溯：将 F-编号映射到测试用例

### Step 3 — 执行集成测试

参照 [`./references/test-patterns.md`](./references/test-patterns.md) 选择对应模式：

| 场景 | 工具/方法 | 脚本 |
|------|----------|------|
| HMI 交互 | UIAutomator2 / adb input | [`./scripts/hmi_helper.py`](./scripts/hmi_helper.py) |
| 应用启动性能 | `adb shell am start -W` | [`./scripts/perf_capture.py`](./scripts/perf_capture.py) |
| 帧率/内存 | `dumpsys gfxinfo` / `dumpsys meminfo` | [`./scripts/perf_capture.py`](./scripts/perf_capture.py) |
| Logcat 日志采集 | `adb logcat` | [`./scripts/adb_runner.py`](./scripts/adb_runner.py) |
| 截图/录屏 | `adb shell screencap / screenrecord` | [`./scripts/adb_runner.py`](./scripts/adb_runner.py) |

### Step 4 — 缺陷判定规则

- **P0 阻塞**：设备无法连接 / 目标应用无法启动 / ANR 或系统级 Crash
- **P1 严重**：冷启动 > 5s / 帧率 < 30fps / 核心 HMI 流程失败
- **P2 一般**：非核心功能异常 / 性能轻微劣化（≤20%）
- **P3 优化**：UI 细节偏差 / 日志噪声

### Step 5 — 产出测试报告

按 [`./assets/templates/report_template.md`](./assets/templates/report_template.md) 格式生成报告，输出到 `tests/reports/ivi_test_report.md`。

报告必须包含：
- 设备信息快照（型号/build/Android 版本）
- 每条用例：TC 编号 / 结果 / 耗时 / 截图路径
- 性能指标汇总表
- 缺陷清单（含 logcat 摘录）
- 需求覆盖矩阵（Fxxx → TC-xxx）

---

## ADB 快速参考

详见 [`./references/adb-cheatsheet.md`](./references/adb-cheatsheet.md)

```bash
# 连接
adb connect <IP>:5555
adb -s <SERIAL> shell getprop ro.build.fingerprint

# 应用操作
adb shell am start -W -n <package>/<activity>
adb shell am force-stop <package>

# 性能
adb shell dumpsys gfxinfo <package> reset
adb shell dumpsys meminfo <package>

# 日志
adb logcat -v threadtime -b main,system,crash > logcat.txt
```

---

## 与 Harness 流水线集成

该 Skill 由 `ivi-test-engineer` agent 调用，嵌入在流水线的 `ivi_testing` 阶段（在标准 `testing` 之后）：

```
requirements → design → development → testing → ivi_testing → delivery
```

`ivi-test-engineer` agent 定义见 `.claude/agents/ivi-test-engineer.md`。
