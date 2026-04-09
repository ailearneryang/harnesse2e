"""
Harness 核心引擎 - 状态机与循环驱动
Pipeline State Machine & Loop Driver

定义流水线状态转移、无限循环机制、重试逻辑、人工介入处理
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
import os


# ============================================================
# 状态定义
# ============================================================
class PipelineState(Enum):
    """流水线状态枚举"""
    IDLE = "idle"                 # 等待新功能规范
    REQUIREMENTS = "requirements"  # 需求分析中
    DESIGN = "design"             # 系统设计中
    DEVELOPMENT = "development"    # 代码开发中
    TESTING = "testing"           # 质量测试中
    REVIEWING = "reviewing"       # 产物评审中
    HUMAN_INTERVENTION = "human_intervention"  # 等待人工介入
    DONE = "done"                 # 本轮完成


class ReviewResult(Enum):
    """评审结果"""
    PASS = "pass"
    FAIL = "fail"
    NEED_HUMAN = "need_human"     # 需要人工介入


class FeedbackAction(Enum):
    """反馈回流动作"""
    CONTINUE = "continue"          # 进入下一阶段
    RETRY_CURRENT = "retry"        # 重试当前阶段
    REWORK_PREVIOUS = "rework"     # 退回上一阶段
    PAUSE_FOR_HUMAN = "pause"      # 暂停等人工
    SKIP_TO_DONE = "done"          # 跳到完成（所有测试通过）


# ============================================================
# 状态转移表
# ============================================================
TRANSITIONS = {
    PipelineState.IDLE: {
        "new_spec": PipelineState.REQUIREMENTS,
    },
    PipelineState.REQUIREMENTS: {
        "review_pass": PipelineState.DESIGN,
        "review_fail": PipelineState.REQUIREMENTS,  # 重试
        "human_needed": PipelineState.HUMAN_INTERVENTION,
    },
    PipelineState.DESIGN: {
        "review_pass": PipelineState.DEVELOPMENT,
        "review_fail": PipelineState.DESIGN,
        "inconsistent_with_req": PipelineState.REQUIREMENTS,  # 回流到需求
        "human_needed": PipelineState.HUMAN_INTERVENTION,
    },
    PipelineState.DEVELOPMENT: {
        "review_pass": PipelineState.TESTING,
        "review_fail": PipelineState.DEVELOPMENT,
        "inconsistent_with_design": PipelineState.DESIGN,  # 回流到设计
        "human_needed": PipelineState.HUMAN_INTERVENTION,
    },
    PipelineState.TESTING: {
        "all_pass": PipelineState.DONE,
        "has_bugs": PipelineState.DEVELOPMENT,  # Bug 退回开发
        "req_issue": PipelineState.REQUIREMENTS,  # 需求问题退回
        "human_needed": PipelineState.HUMAN_INTERVENTION,
    },
    PipelineState.DONE: {
        "next_spec": PipelineState.IDLE,  # 回到等待
        "shutdown": PipelineState.IDLE,
    },
    PipelineState.HUMAN_INTERVENTION: {
        "resume": PipelineState.REQUIREMENTS,  # 人工处理后重新开始
        "skip": PipelineState.IDLE,
    },
}


# ============================================================
# 数据类
# ============================================================
@dataclass
class StageMetrics:
    """阶段执行指标"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    token_usage: int = 0
    retry_count: int = 0
    review_score: Optional[float] = None
    review_passed: bool = False
    status: str = "pending"  # pending / running / review / passed / failed


@dataclass
class ArtifactVersion:
    """产物版本"""
    version: int
    path: str
    created_at: str
    size_bytes: int
    review_score: Optional[float] = None
    changelog: str = ""


@dataclass
class ChangeRequest:
    """变更请求"""
    change_id: str
    description: str
    affected_requirements: list = field(default_factory=list)
    affected_designs: list = field(default_factory=list)
    affected_code_modules: list = field(default_factory=list)
    affected_test_cases: list = field(default_factory=list)
    status: str = "pending"  # pending / analyzed / applied


@dataclass
class Alert:
    """告警"""
    timestamp: str
    level: str        # info / warning / error / critical
    stage: str
    message: str
    action_required: bool = False
    resolved: bool = False


# ============================================================
# 流水线状态快照（持久化用）
# ============================================================
@dataclass
class PipelineSnapshot:
    """完整的流水线状态快照"""
    current_state: str = PipelineState.IDLE.value
    current_spec: Optional[str] = None
    iteration: int = 0
    total_iterations: int = 0

    # 各阶段指标
    stage_metrics: dict = field(default_factory=dict)

    # 产物版本历史
    artifact_versions: dict = field(default_factory=dict)

    # 变更记录
    change_requests: list = field(default_factory=list)

    # 告警记录
    alerts: list = field(default_factory=list)

    # 预算追踪
    total_tokens_used: int = 0
    budget_limit: int = 500000
    total_time_seconds: float = 0

    # 活动日志（最近 100 条）
    activity_log: list = field(default_factory=list)

    # 错误追踪
    errors: list = field(default_factory=list)

    # 评审历史
    review_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "current_state": self.current_state,
            "current_spec": self.current_spec,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
            "stage_metrics": {
                k: {
                    "start_time": v.start_time.isoformat() if v.start_time else None,
                    "end_time": v.end_time.isoformat() if v.end_time else None,
                    "token_usage": v.token_usage,
                    "retry_count": v.retry_count,
                    "review_score": v.review_score,
                    "review_passed": v.review_passed,
                    "status": v.status,
                }
                for k, v in self.stage_metrics.items()
            },
            "artifact_versions": self.artifact_versions,
            "alerts": [
                {"timestamp": a.timestamp, "level": a.level,
                 "stage": a.stage, "message": a.message,
                 "action_required": a.action_required,
                 "resolved": a.resolved}
                for a in self.alerts
            ],
            "total_tokens_used": self.total_tokens_used,
            "budget_limit": self.budget_limit,
            "total_time_seconds": self.total_time_seconds,
            "activity_log": self.activity_log[-100:],
            "review_history": self.review_history[-50:],
            "errors": self.errors[-50:],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineSnapshot":
        """从字典反序列化"""
        snap = cls()
        snap.current_state = data.get("current_state", PipelineState.IDLE.value)
        snap.current_spec = data.get("current_spec")
        snap.iteration = data.get("iteration", 0)
        snap.total_iterations = data.get("total_iterations", 0)
        snap.total_tokens_used = data.get("total_tokens_used", 0)
        snap.budget_limit = data.get("budget_limit", 500000)
        snap.total_time_seconds = data.get("total_time_seconds", 0)
        snap.alerts = [Alert(**a) for a in data.get("alerts", [])]
        snap.activity_log = data.get("activity_log", [])
        snap.review_history = data.get("review_history", [])
        snap.errors = data.get("errors", [])

        for k, v in data.get("stage_metrics", {}).items():
            m = StageMetrics()
            m.start_time = datetime.fromisoformat(v["start_time"]) if v.get("start_time") else None
            m.end_time = datetime.fromisoformat(v["end_time"]) if v.get("end_time") else None
            m.token_usage = v.get("token_usage", 0)
            m.retry_count = v.get("retry_count", 0)
            m.review_score = v.get("review_score")
            m.review_passed = v.get("review_passed", False)
            m.status = v.get("status", "pending")
            snap.stage_metrics[k] = m

        snap.artifact_versions = data.get("artifact_versions", {})
        return snap


# ============================================================
# 流水线引擎
# ============================================================
class PipelineEngine:
    """
    流水线状态机引擎

    核心职责：
    1. 管理状态转移
    2. 驱动无限主循环
    3. 管理阶段重试
    4. 处理反馈回流
    5. 持久化状态快照
    6. 管理告警和人工介入
    """

    def __init__(self, harness_dir: str, budget_limit: int = 500000,
                 log_storage=None):
        self.harness_dir = harness_dir
        self.state_file = os.path.join(harness_dir, "data", "pipeline_state.json")
        self.specs_pending_dir = os.path.join(harness_dir, "specs", "pending")
        self.specs_processed_dir = os.path.join(harness_dir, "specs", "processed")

        # 初始化或恢复状态
        self.snapshot = self._load_state()
        self.snapshot.budget_limit = budget_limit

        # 日志存储（外部注入，可选）
        self.log_storage = log_storage

        # 循环控制参数
        self.poll_interval = 10        # 秒
        self.max_retries_per_stage = 3
        self.max_iterations_per_spec = 5

    # --------------------------------------------------
    # 状态持久化
    # --------------------------------------------------
    def _load_state(self) -> PipelineSnapshot:
        """从文件加载状态"""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return PipelineSnapshot.from_dict(data)
        return PipelineSnapshot()

    def _save_state(self):
        """保存状态到文件"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(self.snapshot.to_json())

    # --------------------------------------------------
    # 状态转移
    # --------------------------------------------------
    def transition(self, trigger: str) -> Optional[PipelineState]:
        """执行状态转移"""
        current = PipelineState(self.snapshot.current_state)
        transitions = TRANSITIONS.get(current, {})

        if trigger in transitions:
            new_state = transitions[trigger]
            old_state_name = current.value
            new_state_name = new_state.value

            self._log_activity(
                f"状态转移: {old_state_name} → {new_state_name} (触发: {trigger})"
            )

            self.snapshot.current_state = new_state.value
            self._save_state()
            return new_state

        self._log_error(f"无效的状态转移: {current.value} + {trigger}")
        return None

    # --------------------------------------------------
    # 日志与告警
    # --------------------------------------------------
    def _log_activity(self, message: str, stage: str = None):
        """记录活动日志（同时写入内存和文件存储）"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        self.snapshot.activity_log.append(entry)

        # 写入 append-only 日志存储
        if self.log_storage:
            try:
                level = "info"
                if "❌" in message or "失败" in message:
                    level = "error"
                elif "✅" in message or "通过" in message or "完成" in message:
                    level = "success"
                elif "⚠️" in message or "警告" in message:
                    level = "warning"
                self.log_storage.append_log(
                    level=level,
                    category="activity",
                    message=message,
                    stage=stage,
                    iteration=self.snapshot.iteration,
                    spec=self.snapshot.current_spec,
                )
            except Exception:
                pass  # 日志写入失败不影响主流程

        self._save_state()

    def _log_error(self, message: str, stage: str = None):
        """记录错误（同时写入内存和文件存储）"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        self.snapshot.errors.append(entry)

        # 写入 append-only 日志存储
        if self.log_storage:
            try:
                self.log_storage.append_log(
                    level="error",
                    category="error",
                    message=message,
                    stage=stage,
                    iteration=self.snapshot.iteration,
                    spec=self.snapshot.current_spec,
                )
            except Exception:
                pass

        self._log_activity(f"❌ {message}")

    def add_alert(self, level: str, stage: str, message: str,
                  action_required: bool = False):
        """添加告警（同时写入内存和文件存储）"""
        alert = Alert(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            message=message,
            action_required=action_required,
        )
        self.snapshot.alerts.append(alert)

        # 写入 append-only 日志存储
        if self.log_storage:
            try:
                self.log_storage.append_log(
                    level=level,
                    category="alert",
                    message=f"[{stage}] {message}",
                    stage=stage,
                    iteration=self.snapshot.iteration,
                    spec=self.snapshot.current_spec,
                    metadata={"action_required": action_required},
                )
            except Exception:
                pass

        self._save_state()
        self._log_activity(
            f"{'🔴' if level == 'critical' else '⚠️' if level == 'warning' else 'ℹ️'} "
            f"[{stage}] {message}"
        )

    # --------------------------------------------------
    # 预算检查
    # --------------------------------------------------
    def check_budget(self) -> dict:
        """检查预算使用情况"""
        used = self.snapshot.total_tokens_used
        limit = self.snapshot.budget_limit
        percent = (used / limit * 100) if limit > 0 else 0

        status = "ok"
        if percent >= 95:
            status = "exceeded"
            self.add_alert("critical", "budget",
                          f"预算即将耗尽: {percent:.1f}% ({used}/{limit} tokens)",
                          action_required=True)
        elif percent >= 80:
            status = "warning"
            self.add_alert("warning", "budget",
                          f"预算使用超过 80%: {percent:.1f}% ({used}/{limit} tokens)")

        return {
            "used": used,
            "limit": limit,
            "percent": round(percent, 1),
            "status": status,
        }

    # --------------------------------------------------
    # 规范文件检测
    # --------------------------------------------------
    def check_pending_specs(self) -> list:
        """检查待处理的功能规范"""
        if not os.path.exists(self.specs_pending_dir):
            return []
        return [
            f for f in os.listdir(self.specs_pending_dir)
            if f.endswith(".md")
        ]

    # --------------------------------------------------
    # 主循环接口（由 pipeline_runner 调用）
    # --------------------------------------------------
    def get_current_state(self) -> PipelineState:
        """获取当前状态"""
        return PipelineState(self.snapshot.current_state)

    def start_stage(self, stage_name: str):
        """标记阶段开始"""
        if stage_name not in self.snapshot.stage_metrics:
            self.snapshot.stage_metrics[stage_name] = StageMetrics()
        metrics = self.snapshot.stage_metrics[stage_name]
        metrics.start_time = datetime.now()
        metrics.status = "running"
        self._log_activity(f"🚀 开始执行阶段: {stage_name}")
        self._save_state()

    def complete_stage(self, stage_name: str, token_usage: int = 0,
                       success: bool = True):
        """标记阶段完成"""
        if stage_name in self.snapshot.stage_metrics:
            metrics = self.snapshot.stage_metrics[stage_name]
            metrics.end_time = datetime.now()
            metrics.token_usage += token_usage
            metrics.status = "passed" if success else "failed"
            self.snapshot.total_tokens_used += token_usage

        status_icon = "✅" if success else "❌"
        self._log_activity(
            f"{status_icon} 阶段完成: {stage_name} "
            f"(tokens: {token_usage})"
        )
        self._save_state()

    def record_review(self, stage_name: str, score: float,
                      passed: bool, feedback: dict):
        """记录评审结果"""
        if stage_name in self.snapshot.stage_metrics:
            metrics = self.snapshot.stage_metrics[stage_name]
            metrics.review_score = score
            metrics.review_passed = passed
            metrics.status = "review"

        review_entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage_name,
            "score": score,
            "passed": passed,
            "feedback": feedback,
        }
        self.snapshot.review_history.append(review_entry)

        status_icon = "✅" if passed else "❌"
        self._log_activity(
            f"{status_icon} 评审结果: {stage_name} "
            f"(分数: {score}/100, 通过: {passed})"
        )
        self._save_state()

    def get_status_summary(self) -> dict:
        """获取状态摘要（供 Dashboard 使用）"""
        stages_order = ["requirements", "design", "development", "testing"]
        stage_status = {}

        for stage in stages_order:
            metrics = self.snapshot.stage_metrics.get(stage)
            if metrics:
                stage_status[stage] = {
                    "status": metrics.status,
                    "score": metrics.review_score,
                    "retries": metrics.retry_count,
                    "tokens": metrics.token_usage,
                    "start_time": metrics.start_time.isoformat() if metrics.start_time else None,
                    "end_time": metrics.end_time.isoformat() if metrics.end_time else None,
                }
            else:
                stage_status[stage] = {
                    "status": "pending",
                    "score": None,
                    "retries": 0,
                    "tokens": 0,
                    "start_time": None,
                    "end_time": None,
                }

        budget = self.check_budget()

        return {
            "current_state": self.snapshot.current_state,
            "current_spec": self.snapshot.current_spec,
            "iteration": self.snapshot.iteration,
            "total_iterations": self.snapshot.total_iterations,
            "stages": stage_status,
            "budget": budget,
            "recent_alerts": [
                a for a in self.snapshot.alerts[-10:]
                if not a.resolved
            ],
            "recent_activities": self.snapshot.activity_log[-20:],
            "pending_specs": self.check_pending_specs(),
        }

    def reset_for_new_iteration(self):
        """重置为新一轮迭代"""
        self.snapshot.iteration += 1
        self.snapshot.total_iterations += 1
        # 不清除历史指标，只更新状态
        self._save_state()
