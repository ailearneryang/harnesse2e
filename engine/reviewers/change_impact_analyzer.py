"""
变更影响分析器 - Change Impact Analyzer
分析需求变更对其他产物的影响范围

核心功能：
1. 变更登记：记录需求变更描述
2. 影响分析：自动识别受影响的设计/代码/测试
3. 影响范围报告：列出所有需要修改的产物
4. 局部重跑建议：建议需要重跑的流水线阶段
"""

import os
import re
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ChangeImpact:
    """变更影响"""
    change_description: str
    affected_requirements: list = field(default_factory=list)
    affected_designs: list = field(default_factory=list)
    affected_code_modules: list = field(default_factory=list)
    affected_test_cases: list = field(default_factory=list)
    stages_to_rerun: list = field(default_factory=list)
    impact_level: str = "low"  # low / medium / high / critical
    analysis_details: str = ""


class ChangeImpactAnalyzer:
    """
    变更影响分析器

    当需求发生变更时，分析变更会影响哪些已有产物，
    并建议需要重跑哪些流水线阶段。
    """

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.changes_dir = os.path.join(harness_dir, "data", "changes")
        os.makedirs(self.changes_dir, exist_ok=True)

        self.requirements_file = os.path.join(
            harness_dir, "requirements", "requirements_spec.md"
        )
        self.design_dir = os.path.join(harness_dir, "design")
        self.src_dir = os.path.join(harness_dir, "src")
        self.tests_dir = os.path.join(harness_dir, "tests")

    def analyze_change(self, change_description: str,
                       changed_requirements: list = None) -> ChangeImpact:
        """
        分析变更影响

        Args:
            change_description: 变更描述（自然语言）
            changed_requirements: 明确修改的需求编号列表（如 ["F001", "F003"]）
        """
        impact = ChangeImpact(
            change_description=change_description
        )

        # 1. 识别受影响的需求
        if changed_requirements:
            impact.affected_requirements = changed_requirements
        else:
            impact.affected_requirements = self._guess_affected_requirements(
                change_description
            )

        # 2. 分析对设计的影响
        impact.affected_designs = self._analyze_design_impact(
            impact.affected_requirements
        )

        # 3. 分析对代码的影响
        impact.affected_code_modules = self._analyze_code_impact(
            impact.affected_requirements
        )

        # 4. 分析对测试的影响
        impact.affected_test_cases = self._analyze_test_impact(
            impact.affected_requirements
        )

        # 5. 确定影响级别
        impact.impact_level = self._determine_impact_level(impact)

        # 6. 建议需要重跑的阶段
        impact.stages_to_rerun = self._suggest_rerun_stages(impact)

        # 7. 生成分析详情
        impact.analysis_details = self._generate_analysis_text(impact)

        # 保存变更记录
        self._save_change(impact)

        return impact

    def _guess_affected_requirements(self, description: str) -> list:
        """
        根据变更描述猜测受影响的需求编号

        启发式匹配：
        1. 直接提到编号（如 "修改 F001"）
        2. 提到功能关键词（与需求文档匹配）
        """
        affected = []

        # 直接匹配编号
        direct_refs = re.findall(r'(F\d{3})', description, re.IGNORECASE)
        affected.extend(direct_refs)

        # 关键词匹配
        if not affected and os.path.exists(self.requirements_file):
            req_content = self._read_file(self.requirements_file)
            # 提取变更描述中的关键词
            keywords = self._extract_keywords(description)
            # 在需求文档中搜索包含这些关键词的功能点
            func_blocks = re.split(r'\n(?=###\s*F\d{3})', req_content)
            for block in func_blocks:
                func_id = re.search(r'(F\d{3})', block)
                if func_id and any(kw in block for kw in keywords):
                    affected.append(func_id.group(1))

        return list(set(affected))

    def _analyze_design_impact(self, req_ids: list) -> list:
        """分析对设计文档的影响"""
        affected = []

        if not os.path.exists(self.design_dir):
            return affected

        for filename in os.listdir(self.design_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(self.design_dir, filename)
            content = self._read_file(filepath)

            for req_id in req_ids:
                if req_id in content:
                    affected.append(f"design/{filename}")
                    break

        return affected

    def _analyze_code_impact(self, req_ids: list) -> list:
        """分析对代码模块的影响"""
        affected = []

        if not os.path.exists(self.src_dir):
            return affected

        for root, dirs, files in os.walk(self.src_dir):
            for f in files:
                filepath = os.path.join(root, f)
                content = self._read_file(filepath)
                for req_id in req_ids:
                    if req_id in content:
                        affected.append(filepath.replace(self.src_dir + "/", ""))
                        break

        return affected

    def _analyze_test_impact(self, req_ids: list) -> list:
        """分析对测试用例的影响"""
        affected = []

        if not os.path.exists(self.tests_dir):
            return affected

        for root, dirs, files in os.walk(self.tests_dir):
            for f in files:
                filepath = os.path.join(root, f)
                content = self._read_file(filepath)
                for req_id in req_ids:
                    if req_id in content:
                        affected.append(filepath.replace(self.tests_dir + "/", ""))
                        break

        return affected

    def _determine_impact_level(self, impact: ChangeImpact) -> str:
        """确定影响级别"""
        score = 0

        if len(impact.affected_requirements) > 3:
            score += 3
        elif len(impact.affected_requirements) > 1:
            score += 2
        elif len(impact.affected_requirements) == 1:
            score += 1

        if impact.affected_designs:
            score += 1

        if len(impact.affected_code_modules) > 5:
            score += 3
        elif impact.affected_code_modules:
            score += 1

        if impact.affected_test_cases:
            score += 1

        # 判断是否涉及架构变更
        arch_keywords = ["架构", "分层", "模块", "整体", "重构"]
        if any(kw in impact.change_description for kw in arch_keywords):
            score += 2

        if score >= 6:
            return "critical"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        return "low"

    def _suggest_rerun_stages(self, impact: ChangeImpact) -> list:
        """建议需要重跑的流水线阶段"""
        stages = []

        if impact.affected_designs:
            stages.append("design")

        if impact.affected_code_modules:
            stages.append("development")

        if impact.affected_test_cases:
            stages.append("testing")

        # 如果影响级别高，建议全量重跑
        if impact.impact_level in ("critical", "high"):
            stages = ["design", "development", "testing"]
        elif not stages:
            # 至少需要重新评审需求
            stages = ["requirements"]

        return stages

    def _generate_analysis_text(self, impact: ChangeImpact) -> str:
        """生成可读的分析报告"""
        level_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        lines = [
            f"# 变更影响分析报告",
            f"",
            f"## 变更描述",
            f"{impact.change_description}",
            f"",
            f"## 影响级别: {level_emoji.get(impact.impact_level, '')} {impact.impact_level.upper()}",
            f"",
            f"## 受影响产物",
            f"",
        ]

        if impact.affected_requirements:
            lines.append(f"### 需求 ({len(impact.affected_requirements)})")
            for req in impact.affected_requirements:
                lines.append(f"- {req}")
            lines.append("")

        if impact.affected_designs:
            lines.append(f"### 设计文档 ({len(impact.affected_designs)})")
            for d in impact.affected_designs:
                lines.append(f"- {d}")
            lines.append("")

        if impact.affected_code_modules:
            lines.append(f"### 代码模块 ({len(impact.affected_code_modules)})")
            for m in impact.affected_code_modules[:20]:
                lines.append(f"- {m}")
            if len(impact.affected_code_modules) > 20:
                lines.append(f"- ... 及其他 {len(impact.affected_code_modules) - 20} 个文件")
            lines.append("")

        if impact.affected_test_cases:
            lines.append(f"### 测试用例 ({len(impact.affected_test_cases)})")
            for t in impact.affected_test_cases[:20]:
                lines.append(f"- {t}")
            lines.append("")

        lines.append(f"## 建议重跑阶段")
        for stage in impact.stages_to_rerun:
            lines.append(f"- {stage}")

        return "\n".join(lines)

    # --------------------------------------------------
    # 工具方法
    # --------------------------------------------------
    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _extract_keywords(self, text: str) -> list:
        """提取关键词"""
        # 移除常见停用词
        stopwords = {"的", "了", "和", "是", "在", "对", "修改", "变更", "调整", "更新"}
        words = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]+', text)
        return [w for w in words if w not in stopwords and len(w) >= 2]

    def _save_change(self, impact: ChangeImpact):
        """保存变更记录"""
        change_id = f"CHG-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        record = {
            "change_id": change_id,
            "timestamp": datetime.now().isoformat(),
            "change_description": impact.change_description,
            "affected_requirements": impact.affected_requirements,
            "affected_designs": impact.affected_designs,
            "affected_code_modules": impact.affected_code_modules,
            "affected_test_cases": impact.affected_test_cases,
            "stages_to_rerun": impact.stages_to_rerun,
            "impact_level": impact.impact_level,
        }

        # 保存变更记录
        change_path = os.path.join(self.changes_dir, f"{change_id}.json")
        with open(change_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        # 保存分析详情
        detail_path = os.path.join(self.changes_dir, f"{change_id}.md")
        with open(detail_path, "w", encoding="utf-8") as f:
            f.write(impact.analysis_details)
