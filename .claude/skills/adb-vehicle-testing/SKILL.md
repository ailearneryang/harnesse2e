---
name: adb-vehicle-testing
description: "基于 ADB 的 Android/车机实车测试技能。USE FOR: 根据需求文档和测试用例执行真机/实车测试，采集 adb shell、logcat、dumpsys、截图与录屏证据，输出结构化测试报告。关键词: adb、实车测试、车机测试、真机测试、Android Automotive、测试报告、requirements、test cases。"
globs:
  - "**/*.md"
  - "**/*.yaml"
  - "**/*.json"
---

# ADB 实车测试 Skill

本 Skill 用于把“需求文档 + 测试用例”转成一轮可执行的 ADB 实车测试流程，并最终产出一份结构化测试报告。

适用场景：
- Android 车机 / Android Automotive / 带 adb 能力的 Android 终端
- 输入已有需求文档和测试用例
- 需要边执行边采集系统证据，并沉淀为正式报告

不适用场景：
- 无 adb 连接能力
- 纯后端接口测试
- 需要 HIL 台架控制但当前环境没有相关控制链路

---

## 1. 输入与输出

### 输入
- `requirements_doc`: 需求文档路径
- `test_cases_doc`: 测试用例文档路径
- `target_package`: 待测应用包名，可选
- `target_activity`: 启动 Activity，可选
- `device_id`: adb 设备序列号，可选；多设备时必填
- `artifacts_dir`: 测试证据输出目录，可选，默认 `runs/adb-vehicle-test-<timestamp>/`

### 输出
- `TEST_REPORT.md`: 测试报告
- `summary.json`: 结构化测试结果摘要
- `artifacts/`:
  - `device_info.txt`
  - `logcat.txt`
  - `dumpsys_<service>.txt`
  - `screenshots/`
  - `screenrecords/`
  - `bugreports/`（如需要）

---

## 2. 执行原则

### 2.1 安全优先
- 涉及车辆行驶状态的测试，默认要求车辆静止、驻车并满足现场安全条件
- 涉及驾驶、安全、制动、转向、ADAS、OTA 等能力时，先在报告中明确测试边界
- 不具备安全前提时，不执行高风险动作，只输出阻塞原因与待确认项

### 2.2 证据先于结论
- 每个测试结论必须尽量绑定至少一种证据：logcat、截图、录屏、dumpsys、界面观察记录
- 无证据时，可记录“人工观察通过/失败”，但必须在报告里显式标记置信度较低

### 2.3 需求可追溯
- 每条测试结果都要回链到需求编号和测试用例编号
- 报告中必须包含“需求 -> 用例 -> 结果 -> 证据”矩阵

---

## 3. 标准流程

### Step 1: 解析输入
从需求文档中提取：
- 需求编号
- 功能点
- 前置条件
- 验收标准
- 非功能约束

从测试用例中提取：
- 用例编号
- 用例标题
- 前置条件
- 操作步骤
- 预期结果
- 优先级

如果文档缺字段，先在报告中生成“输入缺口”小节，不要自行编造。

### Step 2: 建立测试会话目录
建议目录结构：

```text
runs/adb-vehicle-test-<timestamp>/
  TEST_REPORT.md
  summary.json
  artifacts/
    device_info.txt
    logcat.txt
    screenshots/
    screenrecords/
    bugreports/
```

### Step 3: 检查 adb 与设备状态
优先执行：

```bash
adb devices -l
adb -s <device_id> get-state
adb -s <device_id> shell getprop ro.build.fingerprint
adb -s <device_id> shell getprop ro.product.model
adb -s <device_id> shell getprop ro.build.version.release
adb -s <device_id> shell settings get global device_name
```

记录：
- 设备 ID
- 型号
- Android 版本
- 构建指纹
- 当前连接状态

如存在多个设备且未指定 `device_id`，立即停止执行并提示用户指定目标设备。

### Step 4: 准备日志与证据采集
执行前建议：

```bash
adb -s <device_id> logcat -c
adb -s <device_id> shell date
adb -s <device_id> shell dumpsys activity activities
adb -s <device_id> shell dumpsys window windows
```

长日志采集建议异步：

```bash
adb -s <device_id> logcat -v threadtime
```

需要界面证据时：

```bash
adb -s <device_id> exec-out screencap -p > screenshot.png
adb -s <device_id> shell screenrecord /sdcard/test_case.mp4
adb -s <device_id> pull /sdcard/test_case.mp4 ./screenrecords/
```

### Step 5: 执行用例
逐条执行测试用例，并按以下粒度记录：
- `PASS`: 实际结果符合预期
- `FAIL`: 实际结果不符合预期
- `BLOCKED`: 环境、权限、依赖、硬件条件不满足
- `NOT_RUN`: 本轮未执行

每条用例至少记录：
- 需求编号
- 用例编号
- 前置条件是否满足
- 实际步骤摘要
- 实际结果
- 结论
- 证据路径

### Step 6: 采集故障信息
失败用例建议追加：

```bash
adb -s <device_id> shell dumpsys activity top
adb -s <device_id> shell dumpsys package <target_package>
adb -s <device_id> shell pidof <target_package>
adb -s <device_id> bugreport
```

若关注性能，可补充：

```bash
adb -s <device_id> shell dumpsys meminfo <target_package>
adb -s <device_id> shell dumpsys gfxinfo <target_package>
adb -s <device_id> shell top -n 1
```

### Step 7: 输出报告
报告必须包含：
- 测试范围
- 设备与环境
- 用例执行结果汇总
- 逐条用例明细
- 缺陷与风险
- 需求覆盖情况
- 结论与建议

优先使用本 Skill 附带模板：
- `templates/TEST_REPORT_TEMPLATE.md`
- `templates/CASE_RESULT_TEMPLATE.md`

---

## 4. 推荐命令清单

### 4.1 连接与设备识别
```bash
adb devices -l
adb -s <device_id> get-state
adb -s <device_id> shell getprop
```

### 4.2 应用生命周期
```bash
adb -s <device_id> shell am start -n <package>/<activity>
adb -s <device_id> shell am force-stop <package>
adb -s <device_id> shell monkey -p <package> -c android.intent.category.LAUNCHER 1
```

### 4.3 输入注入
```bash
adb -s <device_id> shell input tap <x> <y>
adb -s <device_id> shell input swipe <x1> <y1> <x2> <y2> <duration_ms>
adb -s <device_id> shell input text '<text>'
adb -s <device_id> shell input keyevent <keycode>
```

### 4.4 系统状态采集
```bash
adb -s <device_id> shell dumpsys activity
adb -s <device_id> shell dumpsys window
adb -s <device_id> shell dumpsys package <package>
adb -s <device_id> shell dumpsys meminfo <package>
adb -s <device_id> shell dumpsys gfxinfo <package>
```

### 4.5 日志与证据
```bash
adb -s <device_id> logcat -c
adb -s <device_id> logcat -d
adb -s <device_id> exec-out screencap -p
adb -s <device_id> shell screenrecord /sdcard/<name>.mp4
adb -s <device_id> pull /sdcard/<name>.mp4 <local_path>
```

---

## 5. 报告生成要求

生成 `TEST_REPORT.md` 时，遵守以下规则：
- 先给执行摘要，再给逐条明细
- 所有失败项必须有“现象 + 预期 + 初步定位 + 证据”
- 所有阻塞项必须写清楚阻塞原因和解阻条件
- 不确定的结论使用“待确认”，不要伪造 PASS
- 结论必须显式区分：功能结果、稳定性结果、风险结果

`summary.json` 至少包含：

```json
{
  "session_id": "adb-vehicle-test-20260411-120000",
  "device_id": "emulator-5554",
  "package": "com.example.app",
  "total_cases": 10,
  "passed": 8,
  "failed": 1,
  "blocked": 1,
  "not_run": 0,
  "report_path": "runs/adb-vehicle-test-20260411-120000/TEST_REPORT.md"
}
```

---

## 6. 使用方式

当用户请求“基于需求文档和测试用例做 adb 实车测试并输出测试报告”时：

1. 读取需求文档和测试用例
2. 建立需求与用例映射
3. 检查 adb 连接与目标设备
4. 建立证据采集目录
5. 逐条执行或半自动辅助执行用例
6. 生成 `TEST_REPORT.md` 和 `summary.json`

如果当前环境没有真实设备或不能执行 adb：
- 仍可先生成“测试执行计划 + 报告骨架”
- 明确标记为 `Dry Run` 或 `Pending Device Execution`

---

## 7. 最终输出格式

最终对用户回复时，优先包含：
- 本轮测试范围
- 设备信息
- 执行结果统计
- 关键失败/阻塞项
- 报告路径

不要只给口头结论，必须落地生成报告文件。