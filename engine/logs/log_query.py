"""
日志查询器与导出器 - Log Query & Export
提供多维过滤、全文搜索、时间范围查询、CSV/JSON 导出

查询语法：
- 按类别: category=activity,error,alert
- 按级别: level=error,critical
- 按阶段: stage=requirements,design
- 按时间: from=2026-04-08T00:00:00&to=2026-04-08T23:59:59
- 关键词搜索: q=评审未通过
- 分页: page=1&size=50
- 排序: sort=timestamp&order=desc
"""

import os
import re
import csv
import io
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from .log_storage import LogStorage


class LogQuery:
    """日志查询条件"""

    def __init__(self):
        self.categories: List[str] = None     # None = 全部
        self.levels: List[str] = None          # None = 全部
        self.stage: str = None
        self.spec: str = None
        self.iteration: int = None
        self.from_time: str = None             # ISO8601
        self.to_time: str = None               # ISO8601
        self.keyword: str = None               # 全文搜索关键词
        self.regex: str = None                 # 正则表达式
        self.page: int = 1
        self.page_size: int = 50
        self.sort_by: str = "timestamp"        # timestamp / level / category / stage
        self.sort_order: str = "desc"          # asc / desc

    @classmethod
    def from_request(cls, args: dict) -> "LogQuery":
        """从 HTTP 请求参数构建查询"""
        q = cls()

        if args.get("category"):
            q.categories = [c.strip() for c in args["category"].split(",")]
        if args.get("level"):
            q.levels = [l.strip() for l in args["level"].split(",")]
        q.stage = args.get("stage")
        q.spec = args.get("spec")
        if args.get("iteration"):
            try:
                q.iteration = int(args["iteration"])
            except ValueError:
                pass
        q.from_time = args.get("from")
        q.to_time = args.get("to")
        q.keyword = args.get("q")
        q.regex = args.get("regex")
        if args.get("page"):
            try:
                q.page = max(1, int(args["page"]))
            except ValueError:
                pass
        if args.get("size"):
            try:
                q.page_size = min(200, max(1, int(args["size"])))
            except ValueError:
                pass
        q.sort_by = args.get("sort", "timestamp")
        q.sort_order = args.get("order", "desc")

        return q

    def matches(self, entry: dict) -> bool:
        """检查日志条目是否匹配查询条件"""
        if self.categories:
            if entry.get("category") not in self.categories:
                return False

        if self.levels:
            if entry.get("level") not in self.levels:
                return False

        if self.stage and entry.get("stage") != self.stage:
            return False

        if self.spec and entry.get("spec") != self.spec:
            return False

        if self.iteration is not None and entry.get("iteration") != self.iteration:
            return False

        ts = entry.get("timestamp", "")
        if self.from_time and ts < self.from_time:
            return False
        if self.to_time and ts > self.to_time:
            return False

        if self.keyword:
            # 全文搜索：在所有字段中搜索
            full_text = json.dumps(entry, ensure_ascii=False).lower()
            if self.keyword.lower() not in full_text:
                return False

        if self.regex:
            try:
                pattern = re.compile(self.regex)
                full_text = json.dumps(entry, ensure_ascii=False)
                if not pattern.search(full_text):
                    return False
            except re.error:
                pass

        return True


class LogExporter:
    """日志导出器"""

    # CSV 导出字段
    CSV_FIELDS = [
        "id", "timestamp", "level", "category",
        "stage", "iteration", "spec", "message"
    ]

    def __init__(self, storage: LogStorage):
        self.storage = storage

    def to_json(self, entries: List[dict]) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(entries, indent=2, ensure_ascii=False)

    def to_jsonl(self, entries: List[dict]) -> str:
        """导出为 JSONL 字符串（每行一个 JSON）"""
        return "\n".join(
            json.dumps(e, ensure_ascii=False) for e in entries
        ) + "\n"

    def to_csv(self, entries: List[dict]) -> str:
        """导出为 CSV 字符串"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.CSV_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            # 展平嵌套字段
            flat = {
                k: entry.get(k, "")
                for k in self.CSV_FIELDS
            }
            writer.writerow(flat)
        return output.getvalue()

    def to_markdown(self, entries: List[dict], max_entries: int = 100) -> str:
        """导出为 Markdown 表格"""
        lines = [
            "# 日志回溯报告",
            f"",
            f"**导出时间**: {datetime.now().isoformat()}",
            f"**日志条数**: {len(entries)}",
            f"",
            f"| ID | 时间 | 级别 | 类别 | 阶段 | 消息 |",
            f"|-----|------|------|------|------|------|",
        ]

        for entry in entries[:max_entries]:
            log_id = entry.get("id", "")
            ts = entry.get("timestamp", "")
            # 简化时间显示
            if len(ts) > 19:
                ts = ts[:19]
            level = entry.get("level", "")
            category = entry.get("category", "")
            stage = entry.get("stage", "-")
            message = entry.get("message", "")
            # 截断长消息
            if len(message) > 80:
                message = message[:77] + "..."

            lines.append(
                f"| {log_id} | {ts} | {level} | {category} "
                f"| {stage} | {message} |"
            )

        if len(entries) > max_entries:
            lines.append(f"")
            lines.append(
                f"> 仅显示前 {max_entries} 条，共 {len(entries)} 条。"
                f"请使用 JSON/CSV 格式导出完整数据。"
            )

        return "\n".join(lines)

    def save_to_file(self, entries: List[dict], filepath: str,
                     format: str = "json"):
        """
        保存到文件

        Args:
            entries: 日志条目列表
            filepath: 输出文件路径
            format: 导出格式 (json / jsonl / csv / markdown)
        """
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        exporters = {
            "json": self.to_json,
            "jsonl": self.to_jsonl,
            "csv": self.to_csv,
            "markdown": self.to_markdown,
        }

        exporter = exporters.get(format, self.to_json)
        content = exporter(entries)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath


class LogQuerier:
    """
    日志查询器

    组合 LogStorage + LogQuery，提供完整的查询接口
    """

    def __init__(self, storage: LogStorage):
        self.storage = storage
        self.exporter = LogExporter(storage)

    def query(self, query: LogQuery) -> dict:
        """
        执行查询

        Returns:
            {
                "total": 总匹配条数,
                "page": 当前页,
                "page_size": 每页大小,
                "total_pages": 总页数,
                "entries": 当前页日志,
                "aggregations": {
                    "by_level": {error: 5, warning: 12, ...},
                    "by_category": {activity: 50, error: 5, ...},
                    "by_stage": {requirements: 20, design: 15, ...}
                }
            }
        """
        # 获取时间范围内的所有日志
        all_entries = self.storage.read_all_categories(
            start_time=query.from_time,
            end_time=query.to_time,
        )

        # 应用过滤
        filtered = [e for e in all_entries if query.matches(e)]

        # 排序
        sort_key = query.sort_by
        reverse = query.sort_order == "desc"

        filtered.sort(
            key=lambda x: x.get(sort_key, ""),
            reverse=reverse,
        )

        # 统计聚合
        aggregations = self._aggregate(filtered)

        # 分页
        total = len(filtered)
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        page_entries = filtered[start:end]

        return {
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
            "total_pages": max(1, (total + query.page_size - 1) // query.page_size),
            "entries": page_entries,
            "aggregations": aggregations,
        }

    def search(self, keyword: str, limit: int = 50) -> List[dict]:
        """快速关键词搜索（最近 7 天）"""
        from_time = (
            datetime.now() - __import__("datetime").timedelta(days=7)
        ).isoformat()

        all_entries = self.storage.read_all_categories(start_time=from_time)
        results = []
        kw = keyword.lower()

        for entry in all_entries:
            full_text = json.dumps(entry, ensure_ascii=False).lower()
            if kw in full_text:
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def get_timeline(self, category: str = None,
                     granularity: str = "hour") -> List[dict]:
        """
        获取时间线统计（用于图表展示）

        Args:
            category: 日志类别（None=全部）
            granularity: 统计粒度 (hour / day)

        Returns:
            [{ "time": "2026-04-08T09:00", "count": 15, "errors": 2 }, ...]
        """
        entries = self.storage.read_all_categories() if not category \
            else self.storage.read_range(category)

        # 按时间桶聚合
        buckets: Dict[str, dict] = {}

        for entry in entries:
            ts = entry.get("timestamp", "")
            if not ts:
                continue

            if granularity == "hour":
                bucket_key = ts[:13] + ":00:00"
            else:
                bucket_key = ts[:10]

            if bucket_key not in buckets:
                buckets[bucket_key] = {
                    "time": bucket_key,
                    "count": 0,
                    "errors": 0,
                    "warnings": 0,
                    "critical": 0,
                }

            buckets[bucket_key]["count"] += 1
            level = entry.get("level", "")
            if level == "error":
                buckets[bucket_key]["errors"] += 1
            elif level == "warning":
                buckets[bucket_key]["warnings"] += 1
            elif level == "critical":
                buckets[bucket_key]["critical"] += 1

        # 排序
        return sorted(buckets.values(), key=lambda x: x["time"])

    def export(self, query: LogQuery, format: str = "json") -> str:
        """
        导出查询结果

        Args:
            query: 查询条件
            format: 导出格式 (json / jsonl / csv / markdown)

        Returns:
            导出内容的字符串
        """
        # 获取全部匹配结果（不分页）
        all_entries = self.storage.read_all_categories(
            start_time=query.from_time,
            end_time=query.to_time,
        )
        filtered = [e for e in all_entries if query.matches(query)]
        filtered.sort(
            key=lambda x: x.get(query.sort_by, ""),
            reverse=(query.sort_order == "desc"),
        )

        exporters = {
            "json": self.exporter.to_json,
            "jsonl": self.exporter.to_jsonl,
            "csv": self.exporter.to_csv,
            "markdown": self.exporter.to_markdown,
        }

        exporter = exporters.get(format, self.exporter.to_json)
        return exporter(filtered)

    def _aggregate(self, entries: List[dict]) -> dict:
        """计算聚合统计"""
        by_level = {}
        by_category = {}
        by_stage = {}

        for entry in entries:
            # 按级别
            level = entry.get("level", "unknown")
            by_level[level] = by_level.get(level, 0) + 1

            # 按类别
            category = entry.get("category", "unknown")
            by_category[category] = by_category.get(category, 0) + 1

            # 按阶段
            stage = entry.get("stage")
            if stage:
                by_stage[stage] = by_stage.get(stage, 0) + 1

        return {
            "by_level": by_level,
            "by_category": by_category,
            "by_stage": by_stage,
        }
