# IVI 集成测试报告

## 基本信息

| 字段 | 值 |
|------|----|
| 报告时间 | <!-- TIMESTAMP --> |
| 台架设备 | <!-- DEVICE_SERIAL --> |
| Build | <!-- BUILD_FINGERPRINT --> |
| Android 版本 | <!-- ANDROID_VERSION --> |
| 产品型号 | <!-- PRODUCT_MODEL --> |
| 测试套件 | <!-- SUITE_ID --> |
| 执行工程师 | <!-- ENGINEER --> |

---

## 执行摘要

| 统计项 | 数量 |
|--------|------|
| 总用例数 | <!-- TOTAL --> |
| ✅ 通过 | <!-- PASSED --> |
| ❌ 失败 | <!-- FAILED --> |
| ⏭️ 跳过 | <!-- SKIPPED --> |
| **通过率** | **<!-- PASS_RATE -->%** |

**整体结论**：<!-- OVERALL_VERDICT: PASS / FAIL / BLOCKED -->

---

## 性能指标汇总

| 指标 | 测量值 | 门限 | 结论 |
|------|--------|------|------|
| 冷启动时间（均值） | <!-- COLD_START_MS --> ms | ≤ 5000 ms | <!-- COLD_START_VERDICT --> |
| 热启动时间（均值） | <!-- WARM_START_MS --> ms | ≤ 2000 ms | <!-- WARM_START_VERDICT --> |
| P90 冷启动 | <!-- COLD_P90_MS --> ms | — | — |
| 估算 FPS | <!-- FPS --> | ≥ 30 | <!-- FPS_VERDICT --> |
| 卡顿率 | <!-- JANK_RATE -->% | ≤ 5% | <!-- JANK_VERDICT --> |
| 内存 PSS | <!-- MEMORY_MB --> MB | ≤ 512 MB | <!-- MEMORY_VERDICT --> |
| CPU 均值 | <!-- CPU_PCT -->% | ≤ 50% | <!-- CPU_VERDICT --> |

---

## 用例详情

### P0 用例

| TC ID | 用例名称 | 需求 | 结果 | 耗时(ms) | 截图 |
|-------|---------|------|------|----------|------|
| <!-- TC_P0_ROWS --> | | | | | |

### P1 用例

| TC ID | 用例名称 | 需求 | 结果 | 耗时(ms) | 截图 |
|-------|---------|------|------|----------|------|
| <!-- TC_P1_ROWS --> | | | | | |

### P2/P3 用例

| TC ID | 用例名称 | 需求 | 结果 | 耗时(ms) |
|-------|---------|------|------|----------|
| <!-- TC_P2P3_ROWS --> | | | | |

---

## 缺陷清单

| 缺陷ID | 级别 | 用例 | 现象描述 | Logcat 摘录 |
|--------|------|------|---------|------------|
| <!-- BUG_ROWS --> | | | | |

---

## 需求覆盖矩阵

| 需求编号 | 需求描述 | 覆盖用例 | 覆盖状态 |
|---------|---------|---------|---------|
| <!-- REQ_ROWS --> | | | |

---

## 风险与建议

<!-- RISKS_AND_SUGGESTIONS -->

---

## 附件

- 截图目录：`tests/reports/screenshots/`
- 录屏：`tests/reports/recordings/`
- Logcat：`tests/reports/logcat/`
- 原始性能数据：`tests/reports/perf_raw.json`
