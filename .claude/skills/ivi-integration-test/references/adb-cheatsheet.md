# ADB 车机测试速查表

## 连接台架

```bash
# USB 连接（直接）
adb devices

# TCP 连接（通过网络）
adb connect <HU_IP>:5555
adb -s <HU_IP>:5555 shell getprop ro.product.model

# 断开
adb disconnect <HU_IP>:5555
```

## 设备信息采集

```bash
# 基础信息
adb shell getprop ro.build.fingerprint
adb shell getprop ro.build.version.release   # Android 版本
adb shell getprop ro.product.model
adb shell getprop ro.serialno

# 分辨率
adb shell wm size

# 当前前台应用
adb shell dumpsys window windows | grep mCurrentFocus

# 已安装包列表
adb shell pm list packages | grep <keyword>
```

## 应用操作

```bash
# 安装
adb install -r <app.apk>

# 冷启动并计时（返回 TotalTime / WaitTime）
adb shell am start -W -n <package>/<activity>

# 强制停止
adb shell am force-stop <package>

# 清除数据（模拟冷启动）
adb shell pm clear <package>

# 查看应用信息
adb shell dumpsys package <package> | grep -E "versionName|firstInstallTime"
```

## HMI 输入

```bash
# 点击坐标
adb shell input tap <x> <y>

# 滑动（从 x1,y1 到 x2,y2，duration 毫秒）
adb shell input swipe <x1> <y1> <x2> <y2> <duration>

# 长按
adb shell input swipe <x> <y> <x> <y> 1000

# 键值事件
adb shell input keyevent 3     # HOME
adb shell input keyevent 4     # BACK
adb shell input keyevent 82    # MENU
adb shell input keyevent 24    # VOLUME_UP
adb shell input keyevent 25    # VOLUME_DOWN

# 输入文字
adb shell input text "hello"

# 导出 UI hierarchy（用于元素查找）
adb shell uiautomator dump --compressed /sdcard/ui_dump.xml
adb pull /sdcard/ui_dump.xml .
```

## 日志采集

```bash
# 全量 logcat（带线程时间戳）
adb logcat -v threadtime > logcat.txt

# 指定 buffer（main+system+crash）
adb logcat -v threadtime -b main,system,crash

# 按 Tag 过滤（只看 Error 及以上）
adb logcat ActivityManager:I *:E

# 清空 logcat 缓冲区
adb logcat -c

# 获取最近 N 条
adb logcat -v time -t 500

# 过滤 ANR / Crash
adb logcat | grep -E "ANR|FATAL|Force finishing"
```

## 性能采集

```bash
# 帧率统计（先 reset，交互一段时间后再读）
adb shell dumpsys gfxinfo <package> reset
# ... 操作应用 ...
adb shell dumpsys gfxinfo <package>

# 内存
adb shell dumpsys meminfo <package>

# CPU（实时 top，5 次采样）
adb shell top -n 5 -d 1 | grep <package>

# 电量信息
adb shell dumpsys battery

# 磁盘 I/O
adb shell iostat 1 5
```

## 截图 & 录屏

```bash
# 截图
adb shell screencap -p /sdcard/screenshot.png
adb pull /sdcard/screenshot.png .

# 录屏（最长 3 分钟，180s）
adb shell screenrecord --time-limit 30 /sdcard/record.mp4
adb pull /sdcard/record.mp4 .
```

## 文件操作

```bash
# 推送文件到台架
adb push <local_file> /sdcard/

# 从台架拉取文件
adb pull /sdcard/<file> .

# 台架上查看文件
adb shell ls /sdcard/
```

## 常见 IVI 包名参考

| 应用 | 典型包名 |
|------|--------|
| 导航 | `com.xxx.navigation` |
| 蓝牙电话 | `com.android.phone` |
| 媒体播放 | `com.xxx.media` |
| 系统设置 | `com.android.settings` |
| CarPlay | `com.apple.carplay` / OEM 适配层 |
| Android Auto | `com.google.android.projection.gearhead` |
| Launcher | `com.xxx.launcher` |

## 蓝牙 / 连接性排查

```bash
# 蓝牙 dump
adb shell dumpsys bluetooth_manager

# Wi-Fi 状态
adb shell dumpsys wifi | grep -E "mWifiState|SSID"

# USB 连接状态
adb shell dumpsys usb

# CarPlay/AA 日志 tag（参考）
adb logcat -s CarPlay:V AndroidAuto:V Projection:V
```
