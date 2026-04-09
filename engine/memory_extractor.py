"""
记忆提取器 - Memory Extractor
从任务执行结果中自动提取和保存记忆

功能：
1. 任务完成后提取摘要
2. 失败任务提取经验教训
3. 成功模式识别
4. 项目规范学习
"""

from __future__ import annotations

import re
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

from memory_store import (
    MemoryStore,
    TaskSummary,
    ProjectMemory,
    AgentMemory,
    LessonLearned,
)


class MemoryExtractor:
    """
    记忆提取器
    
    在任务完成或失败后自动提取有价值的信息，
    并保存到记忆存储中供后续任务参考。
    """

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def extract_from_completed_task(self, task: Dict[str, Any]) -> TaskSummary:
        """
        从已完成的任务中提取摘要
        """
        stages = task.get("stages", {})
        
        # 计算持续时间
        duration = self._calculate_duration(task)
        
        # 计算 token 消耗
        total_tokens = self._calculate_tokens(task)
        
        # 提取阶段状态
        stages_passed = []
        stages_failed = []
        for stage_name, stage_data in stages.items():
            status = stage_data.get("status", "")
            if status in ["passed", "completed", "done"]:
                stages_passed.append(stage_name)
            elif status == "failed":
                stages_failed.append(stage_name)
        
        # 提取关键产物
        key_artifacts = self._extract_artifacts(task)
        
        # 提取关键决策
        key_decisions = self._extract_decisions(task)
        
        # 自动生成标签
        tags = self._generate_tags(task)
        
        summary = TaskSummary(
            task_id=task.get("id", ""),
            title=task.get("title", "Untitled"),
            request_text=task.get("request_text", ""),
            status=task.get("status", "unknown"),
            duration_seconds=duration,
            total_tokens=total_tokens,
            stages_passed=stages_passed,
            stages_failed=stages_failed,
            key_artifacts=key_artifacts,
            key_decisions=key_decisions,
            lessons_learned=[],
            tags=tags,
            created_at=task.get("created_at", datetime.now().isoformat()),
            completed_at=task.get("completed_at", datetime.now().isoformat()),
        )
        
        # 保存到存储
        self.memory_store.save_task_summary(summary)
        
        return summary

    def extract_from_failed_task(self, task: Dict[str, Any], failed_stage: str, failure_summary: str) -> LessonLearned:
        """
        从失败的任务中提取经验教训
        """
        # 分析失败类型
        failure_type = self._classify_failure(failure_summary)
        
        # 尝试提取根因
        root_cause = self._extract_root_cause(failure_summary)
        
        # 生成预防策略
        prevention = self._generate_prevention_strategy(failure_type, failure_summary)
        
        lesson = LessonLearned(
            lesson_id=f"lesson-{uuid.uuid4().hex[:8]}",
            task_id=task.get("id", ""),
            stage=failed_stage,
            failure_type=failure_type,
            failure_summary=failure_summary[:500],  # 限制长度
            root_cause=root_cause,
            prevention_strategy=prevention,
            created_at=datetime.now().isoformat(),
        )
        
        # 保存到存储
        self.memory_store.save_lesson(lesson)
        
        # 同时更新任务摘要
        self.extract_from_completed_task(task)
        
        return lesson

    def extract_project_memory(
        self, 
        category: str, 
        content: str, 
        source_task_id: Optional[str] = None,
        confidence: float = 0.7
    ) -> ProjectMemory:
        """
        提取并保存项目记忆
        """
        # 生成唯一 ID（基于内容哈希，避免重复）
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        memory_id = f"pm-{category}-{content_hash}"
        
        memory = ProjectMemory(
            memory_id=memory_id,
            category=category,
            content=content,
            source_task_id=source_task_id,
            confidence=confidence,
            usage_count=0,
            last_used_at=None,
            created_at=datetime.now().isoformat(),
        )
        
        self.memory_store.save_project_memory(memory)
        return memory

    def extract_agent_memory(
        self,
        agent_id: str,
        memory_type: str,  # success_pattern, failure_lesson, best_practice
        content: str,
        context: str = "",
        source_task_id: Optional[str] = None,
        effectiveness: float = 0.5
    ) -> AgentMemory:
        """
        提取并保存 Agent 记忆
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        memory_id = f"am-{agent_id}-{content_hash}"
        
        memory = AgentMemory(
            memory_id=memory_id,
            agent_id=agent_id,
            memory_type=memory_type,
            content=content,
            context=context,
            effectiveness_score=effectiveness,
            source_task_id=source_task_id,
            usage_count=0,
            created_at=datetime.now().isoformat(),
        )
        
        self.memory_store.save_agent_memory(memory)
        return memory

    def _calculate_duration(self, task: Dict) -> int:
        """计算任务持续时间（秒）"""
        created = task.get("created_at") or task.get("started_at")
        completed = task.get("completed_at") or task.get("updated_at")
        
        if not created:
            return 0
        
        try:
            start = datetime.fromisoformat(created.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed.replace("Z", "+00:00")) if completed else datetime.now()
            return int((end - start).total_seconds())
        except (ValueError, AttributeError):
            return 0

    def _calculate_tokens(self, task: Dict) -> int:
        """计算 token 消耗"""
        stages = task.get("stages", {})
        total = 0
        for stage_data in stages.values():
            total += stage_data.get("tokens_used", 0)
        return total

    def _extract_artifacts(self, task: Dict) -> List[str]:
        """提取关键产物路径"""
        artifacts = task.get("artifacts", {})
        key_artifacts = []
        
        for stage, paths in artifacts.items():
            if isinstance(paths, list):
                # 只保留关键文件
                for p in paths[:2]:  # 每阶段最多2个
                    if isinstance(p, str):
                        key_artifacts.append(p)
        
        return key_artifacts[:10]  # 最多10个

    def _extract_decisions(self, task: Dict) -> List[str]:
        """提取关键决策"""
        decisions = []
        context = task.get("context", {})
        
        for stage, stage_ctx in context.items():
            if isinstance(stage_ctx, dict):
                summary = stage_ctx.get("summary", "")
                # 提取决策相关的句子
                if summary:
                    lines = summary.split("\n")
                    for line in lines:
                        if any(kw in line.lower() for kw in ["决定", "选择", "采用", "使用", "决策", "choose", "decide", "select", "use"]):
                            decisions.append(line.strip()[:200])
        
        return decisions[:5]  # 最多5个

    def _generate_tags(self, task: Dict) -> List[str]:
        """自动生成标签"""
        tags = []
        request = task.get("request_text", "").lower()
        
        # 基于请求内容的标签
        tag_keywords = {
            "前端": ["前端", "ui", "界面", "页面", "html", "css", "react", "vue"],
            "后端": ["后端", "api", "服务", "接口", "backend", "server"],
            "数据库": ["数据库", "sql", "mongodb", "redis", "database"],
            "测试": ["测试", "test", "单元测试", "集成测试"],
            "重构": ["重构", "优化", "refactor", "restructure"],
            "新功能": ["新增", "添加", "新功能", "feature", "add"],
            "修复": ["修复", "fix", "bug", "错误", "问题"],
            "游戏": ["游戏", "game", "snake", "chess", "棋"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in request for kw in keywords):
                tags.append(tag)
        
        # 基于状态的标签
        if task.get("status") == "completed":
            tags.append("成功")
        elif task.get("status") == "failed":
            tags.append("失败")
        
        return tags

    def _classify_failure(self, summary: str) -> str:
        """分类失败类型"""
        summary_lower = summary.lower()
        
        if "retry" in summary_lower or "重试" in summary_lower:
            return "retry_exhausted"
        elif "review" in summary_lower or "审查" in summary_lower:
            return "review_rejected"
        elif "test" in summary_lower or "测试" in summary_lower:
            return "test_failed"
        elif "timeout" in summary_lower or "超时" in summary_lower:
            return "timeout"
        elif "permission" in summary_lower or "权限" in summary_lower:
            return "permission_error"
        elif "syntax" in summary_lower or "语法" in summary_lower:
            return "syntax_error"
        elif "option" in summary_lower or "参数" in summary_lower:
            return "invalid_option"
        else:
            return "unknown"

    def _extract_root_cause(self, summary: str) -> str:
        """尝试提取根因"""
        # 查找常见的错误模式
        patterns = [
            r"error[:\s]+(.+?)(?:\n|$)",
            r"错误[：:\s]+(.+?)(?:\n|$)",
            r"failed[:\s]+(.+?)(?:\n|$)",
            r"失败[：:\s]+(.+?)(?:\n|$)",
            r"unknown option[:\s]+(.+?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, summary, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        
        return summary[:200] if summary else ""

    def _generate_prevention_strategy(self, failure_type: str, summary: str) -> str:
        """生成预防策略"""
        strategies = {
            "retry_exhausted": "增加重试次数或检查 agent 配置是否正确",
            "review_rejected": "在提交前增加本地审查步骤，确保代码质量",
            "test_failed": "增强测试覆盖，在开发阶段运行单元测试",
            "timeout": "优化任务粒度，将大任务拆分为小任务",
            "permission_error": "检查文件权限和访问控制配置",
            "syntax_error": "启用语法检查和 linting 工具",
            "invalid_option": "检查 CLI 版本和参数兼容性",
        }
        
        return strategies.get(failure_type, "分析失败日志，定位具体问题")


class MemoryInjector:
    """
    记忆注入器
    
    在构建 prompt 时注入相关的记忆上下文
    """

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def build_memory_context(self, stage: str, request_text: str, agent_id: str) -> str:
        """
        构建记忆上下文片段，用于注入 prompt
        """
        sections = []
        
        # 获取相关记忆
        context = self.memory_store.get_context_for_stage(stage, request_text)
        
        # 相似任务参考
        if context.get("similar_tasks"):
            sections.append("## 相似任务参考")
            for t in context["similar_tasks"]:
                status_icon = "✅" if t["status"] == "completed" else "❌"
                sections.append(f"- {status_icon} {t['title']}")
                if t.get("key_decisions"):
                    for d in t["key_decisions"][:2]:
                        sections.append(f"  - 决策: {d}")
        
        # 经验教训
        if context.get("lessons"):
            sections.append("\n## 历史教训 (避免重复)")
            for l in context["lessons"]:
                if l.get("prevention_strategy"):
                    sections.append(f"- ⚠️ {l['prevention_strategy']}")
        
        # 最佳实践
        if context.get("best_practices"):
            sections.append("\n## 项目最佳实践")
            for bp in context["best_practices"][:3]:
                sections.append(f"- {bp}")
        
        # Agent 专属记忆
        agent_memories = self.memory_store.get_agent_memories(agent_id, "success_pattern", limit=3)
        if agent_memories:
            sections.append(f"\n## {agent_id} 成功模式")
            for m in agent_memories:
                sections.append(f"- {m.content}")
        
        if sections:
            return "\n".join(sections)
        return ""

    def format_for_prompt(self, memory_context: str) -> str:
        """
        格式化记忆上下文，用于 prompt 注入
        """
        if not memory_context:
            return ""
        
        return f"""
---
# 🧠 Memory Context (历史经验参考)

{memory_context}

---
""".strip()
