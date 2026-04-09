"""
Performance Capture — 车机性能指标采集
涵盖：应用冷/热启动时间、帧率(FPS)、内存基线、CPU 占用
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Optional

from adb_runner import ADBRunner


@dataclass
class StartupMetrics:
    package: str
    activity: str
    cold_start_times_ms: list[int] = field(default_factory=list)
    warm_start_times_ms: list[int] = field(default_factory=list)

    @property
    def cold_mean_ms(self) -> float:
        return statistics.mean(self.cold_start_times_ms) if self.cold_start_times_ms else 0

    @property
    def cold_p90_ms(self) -> float:
        if not self.cold_start_times_ms:
            return 0
        return sorted(self.cold_start_times_ms)[int(len(self.cold_start_times_ms) * 0.9)]

    @property
    def warm_mean_ms(self) -> float:
        return statistics.mean(self.warm_start_times_ms) if self.warm_start_times_ms else 0


@dataclass
class FrameMetrics:
    package: str
    total_frames: int = 0
    janky_frames: int = 0
    percentile_50_ms: float = 0
    percentile_90_ms: float = 0
    percentile_95_ms: float = 0
    percentile_99_ms: float = 0

    @property
    def jank_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return round(self.janky_frames / self.total_frames * 100, 2)

    @property
    def estimated_fps(self) -> float:
        if self.percentile_50_ms == 0:
            return 0.0
        return round(1000 / self.percentile_50_ms, 1)


@dataclass
class MemoryMetrics:
    package: str
    total_pss_kb: int = 0
    java_heap_kb: int = 0
    native_heap_kb: int = 0
    code_kb: int = 0
    stack_kb: int = 0
    graphics_kb: int = 0


@dataclass
class CPUMetrics:
    package: str
    cpu_percent: float = 0.0
    sample_duration_s: int = 5


@dataclass
class PerformanceReport:
    device_serial: Optional[str]
    timestamp: str
    startup: Optional[StartupMetrics] = None
    frame: Optional[FrameMetrics] = None
    memory: Optional[MemoryMetrics] = None
    cpu: Optional[CPUMetrics] = None
    thresholds_passed: dict[str, bool] = field(default_factory=dict)

    # 默认门限值（可被测试用例覆盖）
    COLD_START_THRESHOLD_MS = 5000
    JANK_RATE_THRESHOLD_PCT = 5.0
    MEMORY_THRESHOLD_KB = 512 * 1024  # 512 MB


class PerfCapture:
    """
    车机应用性能指标采集器。

    使用方式::

        runner = ADBRunner.connect_tcp("192.168.1.100")
        perf = PerfCapture(runner)
        report = perf.full_profile("com.example.navi", ".MainActivity", iterations=3)
        print(perf.to_markdown(report))
    """

    def __init__(self, runner: ADBRunner):
        self.runner = runner

    # ------------------------------------------------------------------
    # 启动时间
    # ------------------------------------------------------------------

    def measure_cold_start(
        self, package: str, activity: str, iterations: int = 3
    ) -> StartupMetrics:
        """
        多次冷启动测量，每次先清除应用数据确保冷启动条件。
        """
        metrics = StartupMetrics(package=package, activity=activity)
        for i in range(iterations):
            self.runner.force_stop(package)
            self.runner.clear_app_data(package)
            time.sleep(1)

            result = self.runner.launch_app(package, activity)
            if "total_time_ms" in result:
                metrics.cold_start_times_ms.append(result["total_time_ms"])
            time.sleep(2)
            self.runner.force_stop(package)

        return metrics

    def measure_warm_start(
        self, package: str, activity: str, iterations: int = 3
    ) -> StartupMetrics:
        """
        多次热启动测量（不清除数据，只 force-stop 再重启）。
        """
        metrics = StartupMetrics(package=package, activity=activity)
        # 先做一次冷启动让数据缓存到内存
        self.runner.launch_app(package, activity)
        time.sleep(2)

        for _ in range(iterations):
            self.runner.force_stop(package)
            time.sleep(0.5)
            result = self.runner.launch_app(package, activity)
            if "total_time_ms" in result:
                metrics.warm_start_times_ms.append(result["total_time_ms"])
            time.sleep(2)
            self.runner.force_stop(package)

        return metrics

    # ------------------------------------------------------------------
    # 帧率 / 流畅度
    # ------------------------------------------------------------------

    def measure_frame_stats(self, package: str, duration_s: int = 10) -> FrameMetrics:
        """
        使用 gfxinfo 采集渲染帧统计。
        需要应用正在前台运行。
        """
        self.runner.shell(f"dumpsys gfxinfo {package} reset")
        time.sleep(duration_s)
        out, _ = self.runner.shell(f"dumpsys gfxinfo {package}")
        return self._parse_gfxinfo(package, out)

    def _parse_gfxinfo(self, package: str, output: str) -> FrameMetrics:
        metrics = FrameMetrics(package=package)
        for line in output.splitlines():
            line = line.strip()
            if "Total frames rendered:" in line:
                try:
                    metrics.total_frames = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            elif "Janky frames:" in line:
                try:
                    # "Janky frames: 12 (8.33%)"
                    val = line.split(":")[1].strip().split()[0]
                    metrics.janky_frames = int(val)
                except (ValueError, IndexError):
                    pass
            elif "50th percentile:" in line:
                metrics.percentile_50_ms = self._parse_ms(line)
            elif "90th percentile:" in line:
                metrics.percentile_90_ms = self._parse_ms(line)
            elif "95th percentile:" in line:
                metrics.percentile_95_ms = self._parse_ms(line)
            elif "99th percentile:" in line:
                metrics.percentile_99_ms = self._parse_ms(line)
        return metrics

    # ------------------------------------------------------------------
    # 内存
    # ------------------------------------------------------------------

    def measure_memory(self, package: str) -> MemoryMetrics:
        """通过 dumpsys meminfo 采集当前内存使用。"""
        out, _ = self.runner.shell(f"dumpsys meminfo {package}")
        return self._parse_meminfo(package, out)

    def _parse_meminfo(self, package: str, output: str) -> MemoryMetrics:
        metrics = MemoryMetrics(package=package)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("TOTAL PSS:") or line.startswith("TOTAL:"):
                parts = line.split()
                try:
                    metrics.total_pss_kb = int(parts[2]) if len(parts) > 2 else int(parts[1])
                except (ValueError, IndexError):
                    pass
            elif "Java Heap:" in line:
                metrics.java_heap_kb = self._parse_first_int(line)
            elif "Native Heap:" in line:
                metrics.native_heap_kb = self._parse_first_int(line)
            elif "Code:" in line:
                metrics.code_kb = self._parse_first_int(line)
            elif "Stack:" in line:
                metrics.stack_kb = self._parse_first_int(line)
            elif "Graphics:" in line:
                metrics.graphics_kb = self._parse_first_int(line)
        return metrics

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------

    def measure_cpu(self, package: str, duration_s: int = 5) -> CPUMetrics:
        """采样一段时间内应用的 CPU 占用率。"""
        # 获取 PID
        pid_out, _ = self.runner.shell(f"pidof {package}")
        pid = pid_out.strip().split()[0] if pid_out.strip() else None

        if not pid:
            return CPUMetrics(package=package, cpu_percent=0.0)

        samples: list[float] = []
        end = time.time() + duration_s
        while time.time() < end:
            out, _ = self.runner.shell(f"cat /proc/{pid}/stat")
            parts = out.split()
            if len(parts) >= 15:
                try:
                    utime = int(parts[13])
                    stime = int(parts[14])
                    samples.append(utime + stime)
                except ValueError:
                    pass
            time.sleep(1)

        cpu_pct = 0.0
        if len(samples) >= 2:
            tick_diff = samples[-1] - samples[0]
            hz_out, _ = self.runner.shell("getconf CLK_TCK")
            try:
                hz = int(hz_out.strip())
            except ValueError:
                hz = 100
            cpu_pct = round((tick_diff / hz) / (len(samples) - 1) * 100, 2)

        return CPUMetrics(package=package, cpu_percent=cpu_pct, sample_duration_s=duration_s)

    # ------------------------------------------------------------------
    # 综合分析
    # ------------------------------------------------------------------

    def full_profile(
        self,
        package: str,
        activity: str,
        iterations: int = 3,
        frame_duration_s: int = 10,
        thresholds: Optional[dict] = None,
    ) -> PerformanceReport:
        """
        执行完整的性能剖析：冷启动 → 热启动 → 帧率 → 内存 → CPU。
        返回带门限判定的 PerformanceReport。
        """
        from datetime import datetime

        report = PerformanceReport(
            device_serial=self.runner.serial,
            timestamp=datetime.now().isoformat(),
        )

        th = {
            "cold_start_ms": PerformanceReport.COLD_START_THRESHOLD_MS,
            "jank_rate_pct": PerformanceReport.JANK_RATE_THRESHOLD_PCT,
            "memory_kb": PerformanceReport.MEMORY_THRESHOLD_KB,
        }
        if thresholds:
            th.update(thresholds)

        # 1. 启动时间
        report.startup = self.measure_cold_start(package, activity, iterations)
        warm = self.measure_warm_start(package, activity, iterations)
        report.startup.warm_start_times_ms = warm.warm_start_times_ms

        # 2. 帧率（需应用处于前台）
        self.runner.launch_app(package, activity)
        time.sleep(1)
        report.frame = self.measure_frame_stats(package, frame_duration_s)

        # 3. 内存
        report.memory = self.measure_memory(package)

        # 4. CPU
        report.cpu = self.measure_cpu(package, duration_s=5)

        # 门限判定
        report.thresholds_passed = {
            "cold_start": report.startup.cold_mean_ms <= th["cold_start_ms"],
            "jank_rate": report.frame.jank_rate <= th["jank_rate_pct"],
            "memory": report.memory.total_pss_kb <= th["memory_kb"],
        }

        self.runner.force_stop(package)
        return report

    def to_markdown(self, report: PerformanceReport) -> str:
        """将性能报告渲染为 Markdown 表格。"""
        lines = [
            "## 性能测试报告",
            f"- **设备**: {report.device_serial}",
            f"- **时间**: {report.timestamp}",
            "",
        ]
        if report.startup:
            s = report.startup
            lines += [
                "### 启动时间",
                "| 指标 | 数值 | 门限 |",
                "|------|------|------|",
                f"| 冷启动均值 | {s.cold_mean_ms:.0f} ms | ≤ {PerformanceReport.COLD_START_THRESHOLD_MS} ms |",
                f"| 冷启动 P90 | {s.cold_p90_ms:.0f} ms | — |",
                f"| 热启动均值 | {s.warm_mean_ms:.0f} ms | — |",
                "",
            ]
        if report.frame:
            f = report.frame
            lines += [
                "### 渲染流畅度",
                "| 指标 | 数值 |",
                "|------|------|",
                f"| 总帧数 | {f.total_frames} |",
                f"| 卡顿帧 | {f.janky_frames} ({f.jank_rate}%) |",
                f"| 估算 FPS | {f.estimated_fps} |",
                f"| P50 帧时间 | {f.percentile_50_ms} ms |",
                f"| P90 帧时间 | {f.percentile_90_ms} ms |",
                f"| P99 帧时间 | {f.percentile_99_ms} ms |",
                "",
            ]
        if report.memory:
            m = report.memory
            lines += [
                "### 内存",
                "| 指标 | 数值 |",
                "|------|------|",
                f"| Total PSS | {m.total_pss_kb // 1024} MB |",
                f"| Java Heap | {m.java_heap_kb // 1024} MB |",
                f"| Native Heap | {m.native_heap_kb // 1024} MB |",
                f"| Graphics | {m.graphics_kb // 1024} MB |",
                "",
            ]
        if report.cpu:
            lines += [
                "### CPU",
                f"- 占用率（{report.cpu.sample_duration_s}s 均值）: **{report.cpu.cpu_percent}%**",
                "",
            ]
        lines.append("### 门限判定")
        for key, passed in report.thresholds_passed.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            lines.append(f"- {key}: {status}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ms(line: str) -> float:
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*ms", line)
        return float(m.group(1)) if m else 0.0

    @staticmethod
    def _parse_first_int(line: str) -> int:
        import re
        m = re.search(r"\d+", line.split(":")[-1])
        return int(m.group(0)) if m else 0
