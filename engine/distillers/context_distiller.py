"""
上下文蒸馏器 - Context Distiller
解决长流水线上下文爆炸问题

核心功能：
1. 产物摘要提取：将长文档蒸馏为结构化摘要
2. 关键决策提取：提取设计决策列表
3. 接口契约提取：提取 API 签名摘要
4. 变更 Diff 提取：只传递新增/修改部分
5. 跨阶段上下文打包：为下一阶段准备精简上下文包
"""

import os
import re
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class DistilledContext:
    """蒸馏后的上下文"""
    stage: str = ""
    original_size: int = 0
    distilled_size: int = 0
    compression_ratio: float = 0.0
    key_decisions: list = field(default_factory=list)
    api_summary: list = field(default_factory=list)
    data_entities: list = field(default_factory=list)
    unresolved_issues: list = field(default_factory=list)
    quality_score: Optional[float] = None
    handoff_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ContextDistiller:
    """
    上下文蒸馏器

    在多 Agent 协作中，每个阶段的产物可能很长，
    直接传递给下一阶段会消耗大量 Token 且容易丢失关键信息。
    蒸馏器提取"决策精华"传递，而非原始文档。
    """

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.distill_dir = os.path.join(harness_dir, "data", "distilled")
        os.makedirs(self.distill_dir, exist_ok=True)
        self.distill_threshold_chars = 10000
        self.summary_retention_ratio = 0.3
        self.protected_section_markers = [
            "安全约束",
            "接口定义",
            "数据模型",
            "api",
            "schema",
            "iso 26262",
            "autosar",
        ]
        self._load_budget_config()

    def _load_budget_config(self) -> None:
        if yaml is None:
            return
        budget_path = os.path.join(self.harness_dir, "budget.yaml")
        if not os.path.exists(budget_path):
            return
        with open(budget_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        context_cfg = loaded.get("context_management", {})
        self.distill_threshold_chars = int(context_cfg.get("distill_threshold_chars", self.distill_threshold_chars))
        self.summary_retention_ratio = float(context_cfg.get("summary_retention_ratio", self.summary_retention_ratio))
        extra_markers = context_cfg.get("protected_section_markers", [])
        if isinstance(extra_markers, list):
            self.protected_section_markers.extend(str(item).lower() for item in extra_markers)

    def should_distill(self, content: str) -> bool:
        """判断是否需要蒸馏"""
        return len(content) > self.distill_threshold_chars

    def distill(self, stage: str, content: str, filename: str) -> DistilledContext:
        """
        蒸馏文档内容

        根据阶段类型采用不同的蒸馏策略
        """
        original_size = len(content)

        if stage == "requirements":
            distilled = self._distill_requirements(content)
        elif stage == "design":
            distilled = self._distill_design(content)
        elif stage == "development":
            distilled = self._distill_code(content)
        elif stage == "testing":
            distilled = self._distill_test_report(content)
        else:
            distilled = self._distill_generic(content)

        distilled.stage = stage
        distilled.original_size = original_size
        distilled.distilled_size = len(json.dumps(
            self._to_dict(distilled), ensure_ascii=False
        ))
        distilled.compression_ratio = round(
            1 - distilled.distilled_size / original_size, 2
        ) if original_size > 0 else 0

        # 保存蒸馏结果
        self._save_distilled(stage, filename, distilled)

        return distilled

    def create_handoff_package(self, stages_completed: list,
                                current_stage: str) -> str:
        """
        创建跨阶段交接包

        将前面所有阶段的蒸馏结果打包为精简上下文，
        供当前阶段的 Agent 使用
        """
        package = {
            "purpose": f"为 {current_stage} 阶段准备的上下文交接包",
            "timestamp": datetime.now().isoformat(),
            "completed_stages": stages_completed,
            "context": {},
        }

        for stage in stages_completed:
            distilled_path = os.path.join(
                self.distill_dir, stage, "latest.json"
            )
            if os.path.exists(distilled_path):
                with open(distilled_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    package["context"][stage] = data

        # 生成可读的交接摘要
        summary_lines = [
            f"# 上下文交接包 - {current_stage} 阶段",
            f"**前置阶段**: {' → '.join(stages_completed)}",
            "",
        ]

        for stage in stages_completed:
            ctx = package["context"].get(stage, {})
            summary_lines.append(f"## 来自 {stage} 阶段")

            if ctx.get("key_decisions"):
                summary_lines.append("### 关键决策")
                for d in ctx["key_decisions"]:
                    summary_lines.append(
                        f"- **{d.get('id', '?')}**: {d.get('description', '')}"
                    )

            if ctx.get("api_summary"):
                summary_lines.append("### 接口契约")
                for api in ctx["api_summary"]:
                    summary_lines.append(
                        f"- `{api.get('method', '?')} {api.get('path', '?')}` "
                        f"- {api.get('description', '')}"
                    )

            if ctx.get("unresolved_issues"):
                summary_lines.append("### 未解决问题")
                for issue in ctx["unresolved_issues"]:
                    summary_lines.append(f"- ⚠️ {issue}")
            summary_lines.append("")

        handoff_text = "\n".join(summary_lines)

        # 保存交接包
        handoff_path = os.path.join(
            self.distill_dir, "handoff", f"{current_stage}.md"
        )
        os.makedirs(os.path.dirname(handoff_path), exist_ok=True)
        with open(handoff_path, "w", encoding="utf-8") as f:
            f.write(handoff_text)

        return handoff_text

    # --------------------------------------------------
    # 各阶段蒸馏策略
    # --------------------------------------------------
    def _distill_requirements(self, content: str) -> DistilledContext:
        """蒸馏需求文档"""
        ctx = DistilledContext()

        # 提取功能点列表
        func_pattern = r'(?:F\d{3}|功能\d+)[：:]\s*(.+?)(?=\n(?:F\d{3}|功能\d+|##|\Z))'
        functions = re.findall(func_pattern, content, re.DOTALL)

        # 提取验收标准
        ac_pattern = r'(?:AC|验收标准)[：:]?\s*(.+?)(?=\n(?:AC|验收标准|##|\Z))'
        acs = re.findall(ac_pattern, content, re.DOTALL)

        # 提取非功能需求中的数值指标
        metric_pattern = r'(\d+)\s*(?:ms|MB|KB|%|秒|毫秒|并发|用户|请求)'
        metrics = re.findall(metric_pattern, content)

        # 提取优先级
        priority_pattern = r'(?:P[0-3]|高|中|低)'
        priorities = re.findall(priority_pattern, content)

        # 智能提取关键决策和未解决问题
        ctx.key_decisions = self._extract_decisions(content)
        ctx.unresolved_issues = self._extract_issues(content)
        ctx.handoff_summary = (
            f"功能点数量: {len(functions)}\n"
            f"验收标准数量: {len(acs)}\n"
            f"性能指标: {', '.join(metrics[:10])}\n"
        )
        self._append_protected_sections(ctx, content)

        return ctx

    def _distill_design(self, content: str) -> DistilledContext:
        """蒸馏设计文档"""
        ctx = DistilledContext()

        # 提取 API 路径
        api_pattern = r'((?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\)]+))'
        apis = re.findall(api_pattern, content)

        ctx.api_summary = [
            {"method": a[0], "path": a[1]} for a in apis
        ]

        # 提取数据实体
        entity_pattern = r'(?:class|entity|表)\s+(\w+)'
        entities = re.findall(entity_pattern, content, re.IGNORECASE)
        ctx.data_entities = entities

        # 提取设计决策
        ctx.key_decisions = self._extract_decisions(content)
        ctx.unresolved_issues = self._extract_issues(content)

        # 提取需求追溯编号
        req_refs = re.findall(r'(?:REQ-|F\d{3})[\w-]*', content)
        ctx.handoff_summary = (
            f"API 接口数: {len(ctx.api_summary)}\n"
            f"数据实体: {', '.join(ctx.data_entities[:10])}\n"
            f"需求追溯点: {len(req_refs)}个\n"
        )
        self._append_protected_sections(ctx, content)

        return ctx

    def _distill_code(self, content: str) -> DistilledContext:
        """蒸馏代码摘要"""
        ctx = DistilledContext()

        # 提取类/函数签名
        class_pattern = r'(?:class|interface|object)\s+(\w+)'
        func_pattern = r'(?:def|fun|func)\s+(\w+)\s*\(([^)]*)\)'

        classes = re.findall(class_pattern, content)
        functions = [
            {"name": f[0], "params": f[1].strip()}
            for f in re.findall(func_pattern, content)
        ]

        ctx.key_decisions = [
            {"id": f"CLS-{c}", "description": f"类: {c}"}
            for c in classes[:20]
        ] + [
            {"id": f"FUN-{f['name']}", "description": f"函数: {f['name']}({f['params']})"}
            for f in functions[:30]
        ]

        # 提取 TODO/FIXME
        ctx.unresolved_issues = re.findall(
            r'(?:TODO|FIXME|HACK|XXX)[：:]\s*(.+)', content
        )

        ctx.handoff_summary = (
            f"类数量: {len(classes)}\n"
            f"函数数量: {len(functions)}\n"
            f"未解决问题: {len(ctx.unresolved_issues)}\n"
        )
        self._append_protected_sections(ctx, content)

        return ctx

    def _distill_test_report(self, content: str) -> DistilledContext:
        """蒸馏测试报告"""
        ctx = DistilledContext()

        # 提取通过率
        pass_pattern = r'(?:通过率|pass rate)[：:]?\s*(\d+)\s*%?'
        passes = re.findall(pass_pattern, content, re.IGNORECASE)

        # 提取失败用例
        fail_pattern = r'(?:失败|fail|bug|缺陷)[：:]?\s*(.+?)(?:\n|$)'
        failures = re.findall(fail_pattern, content, re.IGNORECASE)

        ctx.handoff_summary = (
            f"通过率: {passes[0] + '%' if passes else '未知'}\n"
            f"失败项: {len(failures)}\n"
        )

        if failures:
            ctx.unresolved_issues = failures[:10]

        self._append_protected_sections(ctx, content)

        return ctx

    def _distill_generic(self, content: str) -> DistilledContext:
        """通用蒸馏"""
        ctx = DistilledContext()
        ctx.key_decisions = self._extract_decisions(content)
        ctx.unresolved_issues = self._extract_issues(content)
        ctx.handoff_summary = f"文档大小: {len(content)} 字符"
        self._append_protected_sections(ctx, content)
        return ctx

    # --------------------------------------------------
    # 辅助提取方法
    # --------------------------------------------------
    def _extract_decisions(self, content: str) -> list:
        """提取决策信息"""
        decisions = []
        # 匹配"决定"、"选择"、"采用"等关键词
        patterns = [
            r'(?:决定|选择|采用|确定)[：:]\s*(.+?)(?:\n|$)',
            r'(?:技术选型|架构决策)[：:]?\s*(.+?)(?:\n\n|\Z)',
            r'(?:\[REQ-[\w-]+\])\s*(.+?)(?:\n|$)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for m in matches:
                if len(m.strip()) > 5:  # 过滤太短的匹配
                    decisions.append({
                        "id": f"DEC-{len(decisions)+1:03d}",
                        "description": m.strip()[:200]
                    })

        return decisions[:20]  # 最多保留 20 条

    def _extract_issues(self, content: str) -> list:
        """提取未解决问题"""
        issues = []
        patterns = [
            r'(?:TODO|FIXME|TBD|待定|待确认)[：:]\s*(.+?)(?:\n|$)',
            r'(?:问题|风险|未知)[：:]?\s*(.+?)(?:\n\n|\Z)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                if len(m.strip()) > 3:
                    issues.append(m.strip()[:200])

        return issues[:15]

    def _append_protected_sections(self, ctx: DistilledContext, content: str) -> None:
        snippets = []
        for block in re.split(r"\n\s*\n", content):
            lowered = block.lower()
            if any(marker in lowered for marker in self.protected_section_markers):
                snippets.append(block.strip()[:800])
        if not snippets:
            return
        ctx.key_decisions.append({
            "id": f"DEC-{len(ctx.key_decisions) + 1:03d}",
            "description": "保留不可压缩安全/接口/数据模型段落",
        })
        protected_text = "\n\n".join(snippets[:3])
        ctx.handoff_summary = f"{ctx.handoff_summary}\n\n## Protected Sections\n{protected_text}".strip()

    # --------------------------------------------------
    # 持久化
    # --------------------------------------------------
    def _save_distilled(self, stage: str, filename: str,
                        ctx: DistilledContext):
        """保存蒸馏结果"""
        data = self._to_dict(ctx)

        latest_path = os.path.join(
            self.distill_dir, stage, "latest.json"
        )
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)

        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _to_dict(self, ctx: DistilledContext) -> dict:
        return {
            "stage": ctx.stage,
            "original_size": ctx.original_size,
            "distilled_size": ctx.distilled_size,
            "compression_ratio": ctx.compression_ratio,
            "key_decisions": ctx.key_decisions,
            "api_summary": ctx.api_summary,
            "data_entities": ctx.data_entities,
            "unresolved_issues": ctx.unresolved_issues,
            "quality_score": ctx.quality_score,
            "handoff_summary": ctx.handoff_summary,
            "created_at": ctx.created_at,
        }
