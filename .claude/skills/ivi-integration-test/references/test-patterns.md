# IVI 集成测试常用模式

## Pattern 1：应用冷启动验证

**场景**：验证目标应用能在 5s 内完成冷启动并到达可交互状态。

**步骤**：
1. `pm clear <package>` — 清除数据
2. `am start -W -n <package>/<activity>` — 冷启动并计时
3. 断言 `TotalTime ≤ 5000ms`
4. `uiautomator dump` 确认主页面元素已渲染

**关键日志 tag**：`ActivityManager`, `ActivityTaskManager`

---

## Pattern 2：HMI 核心流程测试

**场景**：验证主要用户路径（如：主页 → 导航 → 目的地输入 → 开始导航）。

**步骤**：
1. `go_home()` — 确保从 Launcher 出发
2. `tap_element(id/nav_button)` — 点击导航入口
3. `assert_activity("NavigationActivity")` — 确认跳转
4. `tap_element(id/search_box)` — 点击搜索框
5. `input_text("北京")` — 输入目的地
6. `assert_text(id/first_result, "北京")` — 确认搜索结果
7. 截图留存

**缺陷判定**：任何步骤超时 5s 或 assertion 失败 → FAIL

---

## Pattern 3：蓝牙连接性测试

**场景**：验证蓝牙配对和音频切换流程。

**步骤**：
1. 进入蓝牙设置：`am start -n com.android.settings/.bluetooth.BluetoothSettings`
2. dump UI，确认"搜索设备"按钮可见
3. 点击配对按钮（如果使用测试手机，自动接受配对）
4. `logcat -s BluetoothAdapter` 监听 20s
5. 断言日志中出现 `STATE_CONNECTED`

**注意**：如台架不支持 ADB 触发配对，改用预配对设备 + 仅验证连接状态。

---

## Pattern 4：性能基准回归

**场景**：跨版本对比性能指标，防止性能劣化。

**报告字段**：

| 指标 | 采集方式 | P1 门限 | P2 门限 |
|------|---------|---------|---------|
| 冷启动时间 | `am start -W` | > 5000ms | > 3000ms |
| 热启动时间 | `am start -W`（不清数据）| > 2000ms | > 1200ms |
| 帧率（P50） | `dumpsys gfxinfo` | < 30fps | < 45fps |
| 卡顿率 | `dumpsys gfxinfo` | > 10% | > 5% |
| 内存 PSS | `dumpsys meminfo` | > 512MB | > 256MB |
| CPU 均值 | `/proc/<pid>/stat` | > 50% | > 30% |

---

## Pattern 5：稳定性 Soak 测试

**场景**：长时间运行（30min+）检测内存泄漏和 ANR。

**步骤**：
1. 启动应用，记录初始内存基线
2. 每 5 分钟执行一轮 HMI 操作（模拟用户操作）
3. 每轮结束后采集内存 + logcat crash 检查
4. 60 分钟后对比内存增长量（> 100MB 为疑似泄漏）
5. 全程 logcat 过滤 `ANR|FATAL|Force finishing`

**退出条件**：ANR > 0 次 / Crash > 0 次 / 内存净增 > 200MB

---

## Pattern 6：OTA 升级验证

**场景**：升级后验证核心功能无回退。

**步骤**：
1. 记录升级前版本 `getprop ro.build.version.release`
2. 触发 OTA（如通过 adb 推送包）
3. 等待重启完成（轮询 `adb wait-for-device`）
4. 验证新版本号
5. 执行"冷启动 + HMI 核心流程 + 蓝牙连接"三合一冒烟

---

## 缺陷分级示例

| 现象 | 级别 | 处置 |
|------|------|------|
| 设备无法 ADB 连接 | P0 阻塞 | 立即报告，停止测试 |
| 应用启动崩溃 | P0 阻塞 | 提交缺陷，附 logcat |
| 冷启动 > 5s | P1 严重 | 提交缺陷，附性能数据 |
| HMI 核心路径断链 | P1 严重 | 提交缺陷，附截图/录屏 |
| 帧率 < 30fps | P1 严重 | 提交缺陷，附 gfxinfo |
| 非核心功能异常 | P2 一般 | 提交缺陷 |
| UI 细节偏差 | P3 优化 | 记录，视版本决定是否修 |
