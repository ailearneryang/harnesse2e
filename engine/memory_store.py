"""
Harness 记忆系统 - Memory Store
多层级记忆存储，支持跨任务学习和项目级知识积累

记忆层级：
1. Task History - 任务执行历史和结果
2. Project Memory - 项目级代码规范和模式
3. Agent Memory - Agent 专业知识积累
4. Lesson Learned - 从失败中学习的教训
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class TaskSummary:
    """任务摘要 - 蒸馏后的任务历史"""
    task_id: str
    title: str
    request_text: str
    status: str  # completed, failed
    duration_seconds: int
    total_tokens: int
    stages_passed: List[str]
    stages_failed: List[str]
    key_artifacts: List[str]  # 主要产物路径
    key_decisions: List[str]  # 关键决策
    lessons_learned: List[str]  # 经验教训
    tags: List[str]  # 分类标签
    created_at: str
    completed_at: str


@dataclass
class ProjectMemory:
    """项目级记忆 - 代码库特定的规范和模式"""
    memory_id: str
    category: str  # coding_style, architecture, testing, naming, etc.
    content: str
    source_task_id: Optional[str]
    confidence: float  # 0.0-1.0
    usage_count: int
    last_used_at: str
    created_at: str


@dataclass
class AgentMemory:
    """Agent 记忆 - 专业知识积累"""
    memory_id: str
    agent_id: str
    memory_type: str  # success_pattern, failure_lesson, best_practice
    content: str
    context: str  # 适用场景
    effectiveness_score: float  # 有效性评分
    source_task_id: Optional[str]
    usage_count: int
    created_at: str


@dataclass
class LessonLearned:
    """经验教训 - 从失败中学习"""
    lesson_id: str
    task_id: str
    stage: str
    failure_type: str  # retry_exhausted, review_rejected, test_failed, etc.
    failure_summary: str
    root_cause: str
    prevention_strategy: str
    created_at: str


class MemoryStore:
    """
    Harness 记忆存储
    
    基于 SQLite 的多层级记忆系统，支持：
    - 任务历史快速检索
    - 相似任务推荐
    - 项目规范积累
    - 失败教训学习
    """

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.db_path = os.path.join(harness_dir, "data", "harness_state.db")
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_memory_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_memory_tables(self) -> None:
        """初始化记忆相关的表"""
        with self._lock, self._connect() as conn:
            # 任务摘要表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_summaries (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    request_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    stages_passed TEXT DEFAULT '[]',
                    stages_failed TEXT DEFAULT '[]',
                    key_artifacts TEXT DEFAULT '[]',
                    key_decisions TEXT DEFAULT '[]',
                    lessons_learned TEXT DEFAULT '[]',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            
            # 项目记忆表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_memories (
                    memory_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_task_id TEXT,
                    confidence REAL DEFAULT 0.5,
                    usage_count INTEGER DEFAULT 0,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Agent 记忆表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memories (
                    memory_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    effectiveness_score REAL DEFAULT 0.5,
                    source_task_id TEXT,
                    usage_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 经验教训表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons_learned (
                    lesson_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    failure_summary TEXT NOT NULL,
                    root_cause TEXT DEFAULT '',
                    prevention_strategy TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_summaries_status ON task_summaries(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_summaries_created ON task_summaries(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project_memories_category ON project_memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_memories_agent ON agent_memories(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lessons_stage ON lessons_learned(stage)")
            
            conn.commit()

    # ==================== Task History ====================
    
    def save_task_summary(self, summary: TaskSummary) -> None:
        """保存任务摘要"""
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO task_summaries (
                    task_id, title, request_text, status, duration_seconds,
                    total_tokens, stages_passed, stages_failed, key_artifacts,
                    key_decisions, lessons_learned, tags, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.task_id,
                summary.title,
                summary.request_text,
                summary.status,
                summary.duration_seconds,
                summary.total_tokens,
                json.dumps(summary.stages_passed, ensure_ascii=False),
                json.dumps(summary.stages_failed, ensure_ascii=False),
                json.dumps(summary.key_artifacts, ensure_ascii=False),
                json.dumps(summary.key_decisions, ensure_ascii=False),
                json.dumps(summary.lessons_learned, ensure_ascii=False),
                json.dumps(summary.tags, ensure_ascii=False),
                summary.created_at,
                summary.completed_at,
            ))
            conn.commit()

    def get_task_history(
        self, 
        limit: int = 50, 
        status: Optional[str] = None,
        since: Optional[str] = None
    ) -> List[TaskSummary]:
        """获取任务历史"""
        with self._lock, self._connect() as conn:
            query = "SELECT * FROM task_summaries WHERE 1=1"
            params: List[Any] = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            if since:
                query += " AND created_at >= ?"
                params.append(since)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
        return [self._row_to_task_summary(row) for row in rows]

    def get_task_summary(self, task_id: str) -> Optional[TaskSummary]:
        """获取单个任务摘要"""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_summaries WHERE task_id = ?",
                (task_id,)
            ).fetchone()
        
        return self._row_to_task_summary(row) if row else None

    def find_similar_tasks(self, keywords: List[str], limit: int = 5) -> List[TaskSummary]:
        """查找相似任务"""
        with self._lock, self._connect() as conn:
            # 简单的关键词匹配
            conditions = " OR ".join(["request_text LIKE ?" for _ in keywords])
            params = [f"%{kw}%" for kw in keywords]
            params.append(limit)
            
            rows = conn.execute(
                f"SELECT * FROM task_summaries WHERE {conditions} ORDER BY created_at DESC LIMIT ?",
                params
            ).fetchall()
            
        return [self._row_to_task_summary(row) for row in rows]

    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计"""
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM task_summaries").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM task_summaries WHERE status = 'completed'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM task_summaries WHERE status = 'failed'").fetchone()[0]
            
            avg_duration = conn.execute(
                "SELECT AVG(duration_seconds) FROM task_summaries WHERE status = 'completed'"
            ).fetchone()[0] or 0
            
            avg_tokens = conn.execute(
                "SELECT AVG(total_tokens) FROM task_summaries WHERE status = 'completed'"
            ).fetchone()[0] or 0
            
            # 最近7天趋势
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            daily_stats = conn.execute("""
                SELECT DATE(created_at) as day, COUNT(*) as count, 
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM task_summaries 
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY day
            """, (week_ago,)).fetchall()
            
        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "avg_duration_seconds": round(avg_duration),
            "avg_tokens_per_task": round(avg_tokens),
            "daily_trend": [{"day": r[0], "count": r[1], "completed": r[2]} for r in daily_stats]
        }

    def _row_to_task_summary(self, row: sqlite3.Row) -> TaskSummary:
        return TaskSummary(
            task_id=row["task_id"],
            title=row["title"],
            request_text=row["request_text"],
            status=row["status"],
            duration_seconds=row["duration_seconds"],
            total_tokens=row["total_tokens"],
            stages_passed=json.loads(row["stages_passed"]),
            stages_failed=json.loads(row["stages_failed"]),
            key_artifacts=json.loads(row["key_artifacts"]),
            key_decisions=json.loads(row["key_decisions"]),
            lessons_learned=json.loads(row["lessons_learned"]),
            tags=json.loads(row["tags"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    # ==================== Project Memory ====================
    
    def save_project_memory(self, memory: ProjectMemory) -> None:
        """保存项目记忆"""
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO project_memories (
                    memory_id, category, content, source_task_id,
                    confidence, usage_count, last_used_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.memory_id,
                memory.category,
                memory.content,
                memory.source_task_id,
                memory.confidence,
                memory.usage_count,
                memory.last_used_at,
                memory.created_at,
            ))
            conn.commit()

    def get_project_memories(
        self, 
        category: Optional[str] = None, 
        limit: int = 20
    ) -> List[ProjectMemory]:
        """获取项目记忆"""
        with self._lock, self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM project_memories WHERE category = ? ORDER BY usage_count DESC, confidence DESC LIMIT ?",
                    (category, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM project_memories ORDER BY usage_count DESC, confidence DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        
        return [ProjectMemory(
            memory_id=r["memory_id"],
            category=r["category"],
            content=r["content"],
            source_task_id=r["source_task_id"],
            confidence=r["confidence"],
            usage_count=r["usage_count"],
            last_used_at=r["last_used_at"],
            created_at=r["created_at"],
        ) for r in rows]

    def increment_memory_usage(self, memory_id: str) -> None:
        """增加记忆使用计数"""
        with self._lock, self._connect() as conn:
            conn.execute("""
                UPDATE project_memories 
                SET usage_count = usage_count + 1, last_used_at = ?
                WHERE memory_id = ?
            """, (datetime.now().isoformat(), memory_id))
            conn.commit()

    # ==================== Agent Memory ====================
    
    def save_agent_memory(self, memory: AgentMemory) -> None:
        """保存 Agent 记忆"""
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO agent_memories (
                    memory_id, agent_id, memory_type, content, context,
                    effectiveness_score, source_task_id, usage_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.memory_id,
                memory.agent_id,
                memory.memory_type,
                memory.content,
                memory.context,
                memory.effectiveness_score,
                memory.source_task_id,
                memory.usage_count,
                memory.created_at,
            ))
            conn.commit()

    def get_agent_memories(
        self, 
        agent_id: str, 
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        """获取 Agent 记忆"""
        with self._lock, self._connect() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM agent_memories WHERE agent_id = ? AND memory_type = ? ORDER BY effectiveness_score DESC LIMIT ?",
                    (agent_id, memory_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_memories WHERE agent_id = ? ORDER BY effectiveness_score DESC LIMIT ?",
                    (agent_id, limit)
                ).fetchall()
        
        return [AgentMemory(
            memory_id=r["memory_id"],
            agent_id=r["agent_id"],
            memory_type=r["memory_type"],
            content=r["content"],
            context=r["context"],
            effectiveness_score=r["effectiveness_score"],
            source_task_id=r["source_task_id"],
            usage_count=r["usage_count"],
            created_at=r["created_at"],
        ) for r in rows]

    # ==================== Lessons Learned ====================
    
    def save_lesson(self, lesson: LessonLearned) -> None:
        """保存经验教训"""
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lessons_learned (
                    lesson_id, task_id, stage, failure_type,
                    failure_summary, root_cause, prevention_strategy, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lesson.lesson_id,
                lesson.task_id,
                lesson.stage,
                lesson.failure_type,
                lesson.failure_summary,
                lesson.root_cause,
                lesson.prevention_strategy,
                lesson.created_at,
            ))
            conn.commit()

    def get_lessons_for_stage(self, stage: str, limit: int = 5) -> List[LessonLearned]:
        """获取特定阶段的经验教训"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM lessons_learned WHERE stage = ? ORDER BY created_at DESC LIMIT ?",
                (stage, limit)
            ).fetchall()
        
        return [LessonLearned(
            lesson_id=r["lesson_id"],
            task_id=r["task_id"],
            stage=r["stage"],
            failure_type=r["failure_type"],
            failure_summary=r["failure_summary"],
            root_cause=r["root_cause"],
            prevention_strategy=r["prevention_strategy"],
            created_at=r["created_at"],
        ) for r in rows]

    def get_all_lessons(self, limit: int = 50) -> List[LessonLearned]:
        """获取所有经验教训"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM lessons_learned ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        
        return [LessonLearned(
            lesson_id=r["lesson_id"],
            task_id=r["task_id"],
            stage=r["stage"],
            failure_type=r["failure_type"],
            failure_summary=r["failure_summary"],
            root_cause=r["root_cause"],
            prevention_strategy=r["prevention_strategy"],
            created_at=r["created_at"],
        ) for r in rows]

    # ==================== Memory Retrieval for Prompts ====================
    
    def get_context_for_stage(self, stage: str, request_text: str) -> Dict[str, Any]:
        """
        为特定阶段获取相关的记忆上下文
        用于注入到 Agent 的 prompt 中
        """
        context = {
            "similar_tasks": [],
            "lessons": [],
            "best_practices": [],
        }
        
        # 提取关键词
        keywords = self._extract_keywords(request_text)
        
        # 查找相似任务
        if keywords:
            similar = self.find_similar_tasks(keywords, limit=3)
            context["similar_tasks"] = [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "status": t.status,
                    "key_decisions": t.key_decisions[:3] if t.key_decisions else [],
                }
                for t in similar
            ]
        
        # 获取该阶段的经验教训
        lessons = self.get_lessons_for_stage(stage, limit=3)
        context["lessons"] = [
            {
                "failure_type": l.failure_type,
                "prevention_strategy": l.prevention_strategy,
            }
            for l in lessons if l.prevention_strategy
        ]
        
        # 获取相关的项目记忆
        stage_category_map = {
            "requirements": "requirements",
            "design": "architecture",
            "development": "coding_style",
            "testing": "testing",
            "code_review": "coding_style",
        }
        category = stage_category_map.get(stage)
        if category:
            memories = self.get_project_memories(category, limit=3)
            context["best_practices"] = [m.content for m in memories]
        
        return context

    def _extract_keywords(self, text: str) -> List[str]:
        """简单的关键词提取"""
        import re
        # 移除标点，分词
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z_][a-zA-Z0-9_]*', text)
        # 过滤停用词和短词
        stopwords = {'的', '是', '在', '和', '了', '有', '我', '请', '把', '给', 'the', 'a', 'an', 'is', 'are'}
        keywords = [w for w in words if len(w) >= 2 and w.lower() not in stopwords]
        return keywords[:10]  # 最多10个关键词
