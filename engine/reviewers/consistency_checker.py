"""
一致性检测器 - Consistency Checker
解决跨阶段产物不一致问题

核心功能：
1. 需求-设计一致性检查
2. 设计-代码一致性检查
3. 需求-测试一致性检查
4. 生成追溯矩阵（Traceability Matrix）
5. 检测冲突并自动标记受影响产物
"""

import os
import re
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    check_name: str
    severity: str          # blocker / major / minor / info
    source_artifact: str
    target_artifact: str
    description: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class TraceabilityEntry:
    """追溯条目"""
    requirement_id: str
    design_element: Optional[str] = None
    code_module: Optional[str] = None
    test_case: Optional[str] = None
    coverage: str = "none"  # full / partial / none


class ConsistencyChecker:
    """
    一致性检测器

    在每个阶段完成后执行跨阶段检查，
    确保需求→设计→代码→测试的一致性链路完整。
    """

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.report_dir = os.path.join(harness_dir, "data", "consistency")
        os.makedirs(self.report_dir, exist_ok=True)

        # 各阶段产物路径
        self.requirements_file = os.path.join(
            harness_dir, "requirements", "requirements_spec.md"
        )
        self.design_files = {
            "architecture": os.path.join(
                harness_dir, "design", "architecture.md"
            ),
            "api": os.path.join(
                harness_dir, "design", "api_design.md"
            ),
            "data_model": os.path.join(
                harness_dir, "design", "data_model.md"
            ),
        }
        self.src_dir = os.path.join(harness_dir, "src")
        self.tests_dir = os.path.join(harness_dir, "tests")

    def run_all_checks(self) -> dict:
        """执行所有一致性检查"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": [],
            "traceability_matrix": [],
            "overall_status": "pass",  # pass / warning / fail
        }

        # 检查 1: 需求-设计一致性
        if self._file_exists(self.requirements_file):
            req_design = self.check_requirements_design_consistency()
            results["checks"]["req_design"] = req_design

        # 检查 2: 设计-代码一致性
        if os.path.exists(self.src_dir) and any(
            os.path.exists(f) for f in self.design_files.values()
        ):
            design_code = self.check_design_code_consistency()
            results["checks"]["design_code"] = design_code

        # 检查 3: 需求-测试一致性
        if os.path.exists(self.tests_dir) and self._file_exists(
            self.requirements_file
        ):
            req_test = self.check_requirements_test_consistency()
            results["checks"]["req_test"] = req_test

        # 生成追溯矩阵
        results["traceability_matrix"] = self.generate_traceability_matrix()

        # 汇总问题
        for check_result in results["checks"].values():
            for issue in check_result.get("issues", []):
                results["issues"].append(issue)
                if issue["severity"] == "blocker":
                    results["overall_status"] = "fail"
                elif issue["severity"] == "major" and results["overall_status"] != "fail":
                    results["overall_status"] = "warning"

        # 保存报告
        self._save_report(results)

        return results

    # --------------------------------------------------
    # 需求-设计一致性检查
    # --------------------------------------------------
    def check_requirements_design_consistency(self) -> dict:
        """检查需求规格与设计文档的一致性"""
        result = {
            "check_name": "需求-设计一致性",
            "status": "pass",
            "issues": [],
            "stats": {},
        }

        req_content = self._read_file(self.requirements_file)

        # 提取需求功能点编号
        req_ids = set(re.findall(r'(F\d{3})', req_content))

        # 检查设计文档中是否引用了所有需求编号
        design_ref_count = 0
        missing_in_design = []

        for req_id in req_ids:
            found = False
            for design_file in self.design_files.values():
                if self._file_exists(design_file):
                    content = self._read_file(design_file)
                    if req_id in content:
                        found = True
                        design_ref_count += 1
                        break
            if not found:
                missing_in_design.append(req_id)

        # 检查设计中是否有超出需求的功能
        extra_in_design = []
        for name, design_file in self.design_files.items():
            if self._file_exists(design_file):
                content = self._read_file(design_file)
                # 查找设计中可能的新功能
                design_refs = re.findall(r'(?:功能|模块|组件)\s*[:：]\s*(.+?)(?:\n|$)', content)
                for ref in design_refs:
                    # 简单启发：如果设计中有提到但需求中没有对应编号
                    if not any(rid in ref for rid in req_ids):
                        extra_in_design.append(f"{name}: {ref.strip()[:50]}")

        result["stats"] = {
            "total_requirements": len(req_ids),
            "referenced_in_design": design_ref_count,
            "missing_in_design": len(missing_in_design),
            "extra_in_design": len(extra_in_design),
        }

        if missing_in_design:
            result["status"] = "warning"
            result["issues"].append({
                "check_name": "需求-设计一致性",
                "severity": "major",
                "source_artifact": "requirements_spec.md",
                "target_artifact": "design/",
                "description": f"以下需求在设计文档中未被引用: {', '.join(missing_in_design)}",
                "suggestion": "确保设计文档中每个功能模块标注对应的需求编号（如 [REQ-F001]）",
                "auto_fixable": False,
            })

        if extra_in_design:
            result["status"] = "warning" if result["status"] == "pass" else result["status"]
            result["issues"].append({
                "check_name": "需求-设计一致性",
                "severity": "minor",
                "source_artifact": "design/",
                "target_artifact": "requirements_spec.md",
                "description": f"设计中可能存在超出需求范围的功能: {', '.join(extra_in_design[:5])}",
                "suggestion": "确认这些是需求遗漏还是设计自行添加",
                "auto_fixable": False,
            })

        return result

    # --------------------------------------------------
    # 设计-代码一致性检查
    # --------------------------------------------------
    def check_design_code_consistency(self) -> dict:
        """检查设计文档与代码实现的一致性"""
        result = {
            "check_name": "设计-代码一致性",
            "status": "pass",
            "issues": [],
            "stats": {},
        }

        api_design_path = self.design_files["api"]
        if not self._file_exists(api_design_path):
            result["stats"]["api_design_exists"] = False
            return result

        api_content = self._read_file(api_design_path)

        # 提取设计中定义的 API 路径
        design_apis = set(
            re.findall(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\)\"]+)', api_content)
        )

        # 在代码中搜索 API 路径
        code_apis = set()
        if os.path.exists(self.src_dir):
            for root, dirs, files in os.walk(self.src_dir):
                for f in files:
                    if self._is_code_file(f):
                        filepath = os.path.join(root, f)
                        content = self._read_file(filepath)
                        # 搜索路由定义
                        code_api_matches = re.findall(
                            r'(?:route|path|url|Mapping)\s*\(\s*["\'](/[^\s"\']+)',
                            content, re.IGNORECASE
                        )
                        code_apis.update(code_api_matches)

        # 比较
        only_in_design = design_apis - code_apis
        only_in_code = code_apis - design_apis

        result["stats"] = {
            "design_apis": len(design_apis),
            "code_apis": len(code_apis),
            "matched": len(design_apis & code_apis),
            "only_in_design": len(only_in_design),
            "only_in_code": len(only_in_code),
        }

        if only_in_design:
            result["status"] = "warning"
            result["issues"].append({
                "check_name": "设计-代码一致性",
                "severity": "major",
                "source_artifact": "api_design.md",
                "target_artifact": "src/",
                "description": f"设计中定义但代码未实现的 API: {', '.join(list(only_in_design)[:5])}",
                "suggestion": "确认这些 API 是否需要实现，或在设计文档中标记为未实现",
                "auto_fixable": False,
            })

        if only_in_code:
            result["status"] = "warning"
            result["issues"].append({
                "check_name": "设计-代码一致性",
                "severity": "minor",
                "source_artifact": "src/",
                "target_artifact": "api_design.md",
                "description": f"代码中实现但设计未定义的 API: {', '.join(list(only_in_code)[:5])}",
                "suggestion": "更新设计文档以包含这些 API，或移除未设计的代码",
                "auto_fixable": False,
            })

        return result

    # --------------------------------------------------
    # 需求-测试一致性检查
    # --------------------------------------------------
    def check_requirements_test_consistency(self) -> dict:
        """检查需求与测试用例的覆盖度"""
        result = {
            "check_name": "需求-测试一致性",
            "status": "pass",
            "issues": [],
            "stats": {},
        }

        req_content = self._read_file(self.requirements_file)
        req_ids = set(re.findall(r'(F\d{3})', req_content))

        # 搜索测试文件中的需求引用
        tested_ids = set()
        test_files = self._find_files(self.tests_dir, [".md", ".kt", ".java", ".py"])

        for test_file in test_files:
            content = self._read_file(test_file)
            found_ids = re.findall(r'(F\d{3})', content)
            tested_ids.update(found_ids)

        # 分析覆盖率
        covered = req_ids & tested_ids
        not_covered = req_ids - tested_ids

        result["stats"] = {
            "total_requirements": len(req_ids),
            "tested": len(tested_ids),
            "covered": len(covered),
            "not_covered": len(not_covered),
            "coverage_rate": round(len(covered) / len(req_ids) * 100, 1) if req_ids else 0,
        }

        if not_covered:
            result["status"] = "warning" if len(not_covered) <= len(req_ids) * 0.2 else "fail"
            result["issues"].append({
                "check_name": "需求-测试一致性",
                "severity": "major" if len(not_covered) > len(req_ids) * 0.2 else "minor",
                "source_artifact": "requirements_spec.md",
                "target_artifact": "tests/",
                "description": f"以下需求缺少测试覆盖: {', '.join(sorted(not_covered)[:10])}",
                "suggestion": "为未覆盖的需求功能点添加测试用例",
                "auto_fixable": False,
            })

        return result

    # --------------------------------------------------
    # 追溯矩阵
    # --------------------------------------------------
    def generate_traceability_matrix(self) -> list:
        """
        生成追溯矩阵

        每行代表一个需求功能点，列表示在各阶段的对应产物
        """
        matrix = []

        req_path = self.requirements_file
        if not self._file_exists(req_path):
            return matrix

        req_content = self._read_file(req_path)
        req_ids = re.findall(r'(F\d{3})', req_content)

        for req_id in req_ids:
            entry = TraceabilityEntry(requirement_id=req_id)

            # 检查设计引用
            for name, design_file in self.design_files.items():
                if self._file_exists(design_file):
                    content = self._read_file(design_file)
                    if req_id in content:
                        entry.design_element = f"design/{os.path.basename(design_file)}"
                        break

            # 检查代码引用
            if os.path.exists(self.src_dir):
                for root, dirs, files in os.walk(self.src_dir):
                    for f in files:
                        if self._is_code_file(f):
                            filepath = os.path.join(root, f)
                            content = self._read_file(filepath)
                            if req_id in content:
                                entry.code_module = filepath.replace(self.src_dir + "/", "")
                                break
                    if entry.code_module:
                        break

            # 检查测试引用
            if os.path.exists(self.tests_dir):
                test_files = self._find_files(self.tests_dir, [".md", ".kt", ".java", ".py"])
                for test_file in test_files:
                    content = self._read_file(test_file)
                    if req_id in content:
                        entry.test_case = test_file.replace(self.tests_dir + "/", "")
                        break

            # 判断覆盖度
            has = sum([
                entry.design_element is not None,
                entry.code_module is not None,
                entry.test_case is not None,
            ])
            if has == 3:
                entry.coverage = "full"
            elif has >= 1:
                entry.coverage = "partial"

            matrix.append({
                "requirement": entry.requirement_id,
                "design": entry.design_element,
                "code": entry.code_module,
                "test": entry.test_case,
                "coverage": entry.coverage,
            })

        return matrix

    # --------------------------------------------------
    # 工具方法
    # --------------------------------------------------
    def _file_exists(self, path: str) -> bool:
        return os.path.exists(path) and os.path.isfile(path)

    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _is_code_file(self, filename: str) -> bool:
        code_extensions = {".kt", ".java", ".py", ".js", ".ts", ".go", ".rs", ".swift"}
        return any(filename.endswith(ext) for ext in code_extensions)

    def _find_files(self, directory: str, extensions: list) -> list:
        """递归查找文件"""
        found = []
        if not os.path.exists(directory):
            return found
        for root, dirs, files in os.walk(directory):
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    found.append(os.path.join(root, f))
        return found

    def _save_report(self, report: dict):
        """保存一致性报告"""
        report_path = os.path.join(
            self.report_dir, f"consistency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 同时保存最新版本
        latest_path = os.path.join(self.report_dir, "latest.json")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
