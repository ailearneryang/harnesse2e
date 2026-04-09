"""
日志存储引擎 - Log Storage Engine
解决日志截断、丢失问题，提供 append-only 持久化存储

设计原则：
1. Append-only：日志只追加，不修改、不删除
2. 按日轮转：每天一个日志文件，便于管理和归档
3. 结构化：每条日志是 JSON 对象，支持字段级查询
4. 多流分离：activity/error/alert/review 四种日志流独立存储
5. 索引加速：维护内存索引，支持快速范围查询

日志格式：
{
    "id": "LOG-20260408-00001",        // 唯一ID
    "timestamp": "2026-04-08T09:40:00", // ISO8601 时间戳
    "level": "info",                     // info / warning / error / critical / success
    "category": "activity",              // activity / error / alert / review / stage / budget
    "stage": "requirements",             // 所属阶段（可选）
    "iteration": 1,                      // 迭代轮次（可选）
    "spec": "user_login.md",            // 关联的功能规范（可选）
    "message": "需求分析阶段完成",        // 日志消息
    "metadata": {}                       // 附加元数据（可选）
}
"""

import os
import json
import gzip
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from threading import Lock


@dataclass
class LogEntry:
    """结构化日志条目"""
    id: str
    timestamp: str
    level: str           # info / warning / error / critical / success
    category: str        # activity / error / alert / review / stage / budget
    message: str
    stage: Optional[str] = None
    iteration: Optional[int] = None
    spec: Optional[str] = None
    metadata: Optional[dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # 过滤掉 None 值和空 dict
        return {k: v for k, v in d.items() if v is not None and v != {}}

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False) + "\n"


class LogStorage:
    """
    Append-only 日志存储引擎

    核心设计：
    - 每种日志类别（activity/error/alert/review）独立存储
    - 按日期轮转：logs/{category}/{date}.jsonl（每天一个文件）
    - 支持自动压缩：超过 30 天的日志自动 gzip 压缩
    - 维护内存索引：加速时间范围查询
    """

    # 压缩阈值（天数）
    COMPRESS_AFTER_DAYS = 30
    # 索引保留天数
    INDEX_RETENTION_DAYS = 90

    def __init__(self, logs_dir: str):
        self.logs_dir = logs_dir
        self._lock = Lock()

        # 类别目录
        self.categories = {
            "activity", "error", "alert", "review", "stage", "budget"
        }

        # 内存索引：category → [(timestamp_str, line_offset), ...]
        self._index: Dict[str, List[tuple]] = {}
        self._counters: Dict[str, int] = {}  # 每个类别的日志计数

        # 确保目录存在
        os.makedirs(logs_dir, exist_ok=True)
        for cat in self.categories:
            os.makedirs(os.path.join(logs_dir, cat), exist_ok=True)

        # 加载索引
        self._build_index()

    # --------------------------------------------------
    # 写入
    # --------------------------------------------------
    def append(self, entry: LogEntry) -> str:
        """
        追加一条日志

        Returns:
            日志 ID
        """
        with self._lock:
            # 确定日期文件
            date_str = entry.timestamp[:10]  # "2026-04-08"
            file_path = os.path.join(
                self.logs_dir, entry.category, f"{date_str}.jsonl"
            )

            # 追加写入
            with open(file_path, "a", encoding="utf-8") as f:
                offset = f.tell()
                f.write(entry.to_json_line())

            # 更新索引
            if entry.category not in self._index:
                self._index[entry.category] = []
            self._index[entry.category].append((entry.timestamp, offset))

            # 更新计数
            self._counters[entry.category] = self._counters.get(
                entry.category, 0
            ) + 1

            return entry.id

    def append_log(self, level: str, category: str, message: str,
                   stage: str = None, iteration: int = None,
                   spec: str = None, metadata: dict = None) -> str:
        """
        便捷写入方法（自动生成 ID 和时间戳）

        Args:
            level: 日志级别 (info/warning/error/critical/success)
            category: 日志类别 (activity/error/alert/review/stage/budget)
            message: 日志消息
            stage: 所属阶段
            iteration: 迭代轮次
            spec: 关联功能规范
            metadata: 附加元数据

        Returns:
            日志 ID
        """
        now = datetime.now()
        # 生成唯一 ID: LOG-{YYYYMMDD}-{序号}
        date_part = now.strftime("%Y%m%d")
        count = self._counters.get(category, 0) + 1
        log_id = f"LOG-{date_part}-{count:05d}"

        entry = LogEntry(
            id=log_id,
            timestamp=now.isoformat(),
            level=level,
            category=category,
            message=message,
            stage=stage,
            iteration=iteration,
            spec=spec,
            metadata=metadata or {},
        )

        return self.append(entry)

    # --------------------------------------------------
    # 读取
    # --------------------------------------------------
    def read_file(self, category: str, date_str: str) -> List[dict]:
        """读取指定类别和日期的所有日志"""
        file_path = os.path.join(
            self.logs_dir, category, f"{date_str}.jsonl"
        )

        # 尝试压缩文件
        if not os.path.exists(file_path):
            gz_path = file_path + ".gz"
            if os.path.exists(gz_path):
                with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
            return []

        entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def read_range(self, category: str,
                   start_time: str = None,
                   end_time: str = None) -> List[dict]:
        """
        读取指定时间范围的日志

        Args:
            category: 日志类别
            start_time: 起始时间 (ISO8601, 如 "2026-04-08T09:00:00")
            end_time: 结束时间 (ISO8601)
        """
        # 确定日期范围
        start_date = start_time[:10] if start_time else None
        end_date = end_time[:10] if end_time else datetime.now().strftime("%Y-%m-%d")

        if start_date is None:
            # 默认最近 7 天
            start_dt = datetime.now() - timedelta(days=7)
            start_date = start_dt.strftime("%Y-%m-%d")

        # 收集日期范围内的文件
        cat_dir = os.path.join(self.logs_dir, category)
        if not os.path.exists(cat_dir):
            return []

        all_entries = []
        for filename in sorted(os.listdir(cat_dir)):
            if filename.startswith("."):
                continue

            # 解析日期
            date_str = filename.replace(".jsonl", "").replace(".gz", "")
            if not (start_date <= date_str <= end_date):
                continue

            entries = self.read_file(category, date_str)

            # 时间过滤
            for entry in entries:
                ts = entry.get("timestamp", "")
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                all_entries.append(entry)

        return all_entries

    def read_all_categories(self,
                            start_time: str = None,
                            end_time: str = None) -> List[dict]:
        """读取所有类别在指定时间范围内的日志"""
        all_entries = []
        for category in self.categories:
            entries = self.read_range(category, start_time, end_time)
            all_entries.extend(entries)

        # 按时间排序
        all_entries.sort(key=lambda x: x.get("timestamp", ""))
        return all_entries

    # --------------------------------------------------
    # 统计
    # --------------------------------------------------
    def get_stats(self) -> dict:
        """获取日志统计信息"""
        stats = {}
        for category in self.categories:
            cat_dir = os.path.join(self.logs_dir, category)
            if not os.path.exists(cat_dir):
                stats[category] = {"total_entries": 0, "files": 0, "size_bytes": 0}
                continue

            total = 0
            files = 0
            size = 0
            for filename in os.listdir(cat_dir):
                if filename.startswith("."):
                    continue
                filepath = os.path.join(cat_dir, filename)
                files += 1
                size += os.path.getsize(filepath)

                if filename.endswith(".jsonl"):
                    with open(filepath, "r", encoding="utf-8") as f:
                        total += sum(1 for line in f if line.strip())
                elif filename.endswith(".gz"):
                    with gzip.open(filepath, "rt", encoding="utf-8") as f:
                        total += sum(1 for line in f if line.strip())

            stats[category] = {
                "total_entries": total,
                "files": files,
                "size_bytes": size,
                "size_human": self._human_size(size),
            }

        return stats

    def get_date_range(self) -> dict:
        """获取日志的日期范围"""
        all_dates = set()
        for category in self.categories:
            cat_dir = os.path.join(self.logs_dir, category)
            if not os.path.exists(cat_dir):
                continue
            for filename in os.listdir(cat_dir):
                if filename.startswith("."):
                    continue
                date_str = filename.replace(".jsonl", "").replace(".gz", "")
                if len(date_str) == 10:  # YYYY-MM-DD
                    all_dates.add(date_str)

        if not all_dates:
            return {"earliest": None, "latest": None, "days": 0}

        sorted_dates = sorted(all_dates)
        return {
            "earliest": sorted_dates[0],
            "latest": sorted_dates[-1],
            "days": len(sorted_dates),
        }

    # --------------------------------------------------
    # 维护
    # --------------------------------------------------
    def compress_old_logs(self, days: int = None):
        """压缩旧的日志文件"""
        days = days or self.COMPRESS_AFTER_DAYS
        threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        for category in self.categories:
            cat_dir = os.path.join(self.logs_dir, category)
            if not os.path.exists(cat_dir):
                continue

            for filename in os.listdir(cat_dir):
                if not filename.endswith(".jsonl"):
                    continue

                date_str = filename.replace(".jsonl", "")
                if date_str >= threshold:
                    continue

                # 压缩
                src_path = os.path.join(cat_dir, filename)
                dst_path = src_path + ".gz"

                if os.path.exists(dst_path):
                    continue

                try:
                    with open(src_path, "rb") as f_in:
                        with gzip.open(dst_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # 删除原文件
                    os.remove(src_path)
                except Exception:
                    pass

    def cleanup_index(self, days: int = None):
        """清理内存索引"""
        days = days or self.INDEX_RETENTION_DAYS
        threshold = (datetime.now() - timedelta(days=days)).isoformat()

        for category in self._index:
            self._index[category] = [
                (ts, offset) for ts, offset in self._index[category]
                if ts >= threshold
            ]

    # --------------------------------------------------
    # 内部
    # --------------------------------------------------
    def _build_index(self):
        """构建内存索引"""
        for category in self.categories:
            cat_dir = os.path.join(self.logs_dir, category)
            if not os.path.exists(cat_dir):
                continue

            self._index[category] = []
            count = 0

            for filename in sorted(os.listdir(cat_dir)):
                if filename.startswith("."):
                    continue

                if filename.endswith(".jsonl"):
                    filepath = os.path.join(cat_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line in f:
                                if not line.strip():
                                    continue
                                try:
                                    entry = json.loads(line)
                                    ts = entry.get("timestamp", "")
                                    if ts:
                                        self._index[category].append(
                                            (ts, 0)  # offset 暂不精确记录
                                        )
                                    count += 1
                                except json.JSONDecodeError:
                                    continue
                    except Exception:
                        pass
                elif filename.endswith(".gz"):
                    filepath = os.path.join(cat_dir, filename)
                    try:
                        with gzip.open(filepath, "rt", encoding="utf-8") as f:
                            for line in f:
                                if not line.strip():
                                    continue
                                count += 1
                    except Exception:
                        pass

            self._counters[category] = count

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
