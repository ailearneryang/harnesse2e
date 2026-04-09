"""
ADB Runner — 车机台架 ADB 核心工具
支持：设备连接检查、命令执行、日志采集、截图/录屏、产物拉取
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class ADBRunner:
    """通过 ADB 与车机台架交互的核心工具。"""

    DEFAULT_PORT = 5555

    def __init__(self, serial: Optional[str] = None, timeout: int = 30):
        """
        :param serial: 设备序列号或 IP:PORT（TCP 模式）。
                       为 None 时使用 adb 默认选中的唯一设备。
        :param timeout: 每条 adb 命令的超时秒数。
        """
        self.serial = serial
        self.timeout = timeout
        self._base_cmd = ["adb"]
        if serial:
            self._base_cmd += ["-s", serial]

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    @classmethod
    def connect_tcp(cls, host: str, port: int = DEFAULT_PORT, timeout: int = 10) -> "ADBRunner":
        """通过 TCP/IP 连接台架，返回已连接的 ADBRunner 实例。"""
        serial = f"{host}:{port}"
        result = subprocess.run(
            ["adb", "connect", serial],
            capture_output=True, text=True, timeout=timeout,
        )
        if "connected" not in result.stdout.lower() and "already" not in result.stdout.lower():
            raise ConnectionError(
                f"无法连接到 {serial}：{result.stdout.strip()} {result.stderr.strip()}"
            )
        return cls(serial=serial, timeout=timeout)

    def disconnect(self) -> None:
        if self.serial:
            subprocess.run(["adb", "disconnect", self.serial], capture_output=True)

    def is_connected(self) -> bool:
        """检查设备当前是否在线。"""
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True
        )
        return self.serial in result.stdout if self.serial else "device" in result.stdout

    # ------------------------------------------------------------------
    # 设备信息
    # ------------------------------------------------------------------

    def device_info(self) -> dict:
        """采集台架关键属性，用于报告头部。"""
        props = {
            "serialno": "ro.serialno",
            "build_fingerprint": "ro.build.fingerprint",
            "android_version": "ro.build.version.release",
            "sdk_version": "ro.build.version.sdk",
            "product_model": "ro.product.model",
            "product_name": "ro.product.name",
            "build_date": "ro.build.date",
        }
        info: dict = {"serial": self.serial, "timestamp": datetime.now().isoformat()}
        for key, prop in props.items():
            info[key] = self.getprop(prop)
        return info

    def getprop(self, prop: str) -> str:
        """读取系统属性。"""
        out, _ = self.shell(f"getprop {prop}")
        return out.strip()

    # ------------------------------------------------------------------
    # Shell 命令执行
    # ------------------------------------------------------------------

    def shell(self, cmd: str, timeout: Optional[int] = None) -> tuple[str, int]:
        """
        在设备上执行 shell 命令。
        返回 (stdout, returncode)。
        """
        full_cmd = self._base_cmd + ["shell", cmd]
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True,
            timeout=timeout or self.timeout,
        )
        combined = result.stdout
        if result.returncode != 0 and result.stderr:
            combined += result.stderr
        return combined, result.returncode

    def shell_stream(self, cmd: str, line_callback=None, timeout: int = 60) -> int:
        """流式执行 shell 命令，每行输出调用 line_callback(line)。"""
        full_cmd = self._base_cmd + ["shell", cmd]
        with subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        ) as proc:
            deadline = time.time() + timeout
            for line in proc.stdout:
                if line_callback:
                    line_callback(line.rstrip())
                if time.time() > deadline:
                    proc.terminate()
                    break
            proc.wait()
            return proc.returncode

    # ------------------------------------------------------------------
    # 应用操作
    # ------------------------------------------------------------------

    def install_apk(self, apk_path: str, replace: bool = True) -> bool:
        """安装 APK 到台架。"""
        flags = ["-r"] if replace else []
        result = subprocess.run(
            self._base_cmd + ["install"] + flags + [apk_path],
            capture_output=True, text=True, timeout=120,
        )
        return "Success" in result.stdout

    def launch_app(self, package: str, activity: str) -> dict:
        """
        冷启动应用，返回启动耗时信息。
        使用 am start -W 获取 WaitTime / TotalTime。
        """
        out, rc = self.shell(
            f"am start -W -n {package}/{activity}"
        )
        result = {"package": package, "activity": activity, "raw": out, "success": rc == 0}
        for line in out.splitlines():
            if "TotalTime:" in line:
                result["total_time_ms"] = int(line.split(":")[1].strip())
            elif "WaitTime:" in line:
                result["wait_time_ms"] = int(line.split(":")[1].strip())
        return result

    def force_stop(self, package: str) -> None:
        """强制停止应用。"""
        self.shell(f"am force-stop {package}")

    def clear_app_data(self, package: str) -> bool:
        """清除应用数据（用于冷启动测试）。"""
        _, rc = self.shell(f"pm clear {package}")
        return rc == 0

    # ------------------------------------------------------------------
    # 日志采集
    # ------------------------------------------------------------------

    def capture_logcat(
        self,
        output_path: str,
        duration_seconds: int = 30,
        tags: Optional[list[str]] = None,
        buffers: str = "main,system,crash",
    ) -> str:
        """
        采集 logcat 日志到文件，返回文件路径。
        :param tags: 过滤 tag 列表，如 ['ActivityManager:I', '*:E']
        """
        tag_args = " ".join(tags) if tags else "*:V"
        cmd = f"logcat -v threadtime -b {buffers} -t {duration_seconds * 100} {tag_args}"

        lines: list[str] = []
        self.shell_stream(cmd, line_callback=lines.append, timeout=duration_seconds + 5)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path

    def clear_logcat(self) -> None:
        self.shell("logcat -c")

    # ------------------------------------------------------------------
    # 截图 & 录屏
    # ------------------------------------------------------------------

    def screenshot(self, local_path: str) -> str:
        """截图并拉取到本地，返回本地文件路径。"""
        remote = "/sdcard/_ivi_test_screenshot.png"
        self.shell(f"screencap -p {remote}")
        self.pull(remote, local_path)
        self.shell(f"rm {remote}")
        return local_path

    def start_screenrecord(self, remote_path: str = "/sdcard/_ivi_record.mp4") -> subprocess.Popen:
        """在后台启动屏幕录制，返回 Popen 对象（调用方负责 terminate）。"""
        cmd = self._base_cmd + ["shell", f"screenrecord {remote_path}"]
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_screenrecord_and_pull(self, proc: subprocess.Popen, remote_path: str, local_path: str) -> str:
        proc.terminate()
        proc.wait(timeout=5)
        time.sleep(1)  # 等待视频写入完成
        self.pull(remote_path, local_path)
        self.shell(f"rm {remote_path}")
        return local_path

    # ------------------------------------------------------------------
    # 文件拉取
    # ------------------------------------------------------------------

    def pull(self, remote: str, local: str) -> bool:
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            self._base_cmd + ["pull", remote, local],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0

    # ------------------------------------------------------------------
    # CLI 入口
    # ------------------------------------------------------------------

    @staticmethod
    def _cli_check(args) -> int:
        """--check: 验证环境和设备连通性。"""
        print("=== IVI 台架连接检查 ===")
        if args.ip:
            try:
                runner = ADBRunner.connect_tcp(args.ip, args.port)
                print(f"[OK] TCP 连接成功: {args.ip}:{args.port}")
            except ConnectionError as e:
                print(f"[FAIL] {e}")
                return 1
        else:
            runner = ADBRunner()
            if not runner.is_connected():
                print("[FAIL] 未发现在线设备，请通过 USB 或 --ip 指定台架地址")
                return 1
            print("[OK] 发现在线设备")

        info = runner.device_info()
        for k, v in info.items():
            print(f"  {k}: {v}")
        return 0

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="IVI ADB Runner")
        parser.add_argument("--check", action="store_true", help="检查设备连通性")
        parser.add_argument("--ip", help="台架 IP 地址（TCP 模式）")
        parser.add_argument("--port", type=int, default=ADBRunner.DEFAULT_PORT)
        parser.add_argument("--serial", help="设备序列号（USB 模式多设备时使用）")
        args = parser.parse_args()

        if args.check:
            sys.exit(ADBRunner._cli_check(args))
        else:
            parser.print_help()


if __name__ == "__main__":
    ADBRunner.main()
