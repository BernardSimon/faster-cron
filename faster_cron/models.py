"""
FasterCron v2.0 - 核心数据模型

提供 TaskInfo, TaskState, ExecutionRecord 等数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, List, Dict, Any


class TaskState(Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 待调度
    RUNNING = "running"       # 正在运行
    PAUSED = "paused"         # 已暂停
    DISABLED = "disabled"     # 已禁用（不调度但保留配置）
    COMPLETED = "completed"   # 已完成
    
    def __str__(self):
        return self.value


@dataclass
class TaskInfo:
    """
    任务信息对象
    
    包含任务的完整元数据和运行时状态
    """
    name: str
    expression: str
    func: Callable[..., Any]
    allow_overlap: bool
    state: TaskState
    priority: int = 0           # 优先级（越高越优先）
    retry_count: int = 0        # 当前重试次数
    last_execution: Optional[datetime] = None    # 上次执行时间
    last_result: Optional[str] = None            # 上次执行结果
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "expression": self.expression,
            "func_name": self.func.__name__,
            "allow_overlap": self.allow_overlap,
            "state": str(self.state),
            "priority": self.priority,
            "retry_count": self.retry_count,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "last_result": self.last_result,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionRecord:
    """
    单次执行记录
    
    记录每次任务执行的详细信息
    """
    task_name: str
    scheduled_at: datetime
    started_at: datetime
    finished_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0
    duration_seconds: Optional[float] = None
    
    @property
    def elapsed_ms(self) -> Optional[float]:
        """获取执行耗时（毫秒）"""
        if self.duration_seconds is not None:
            return self.duration_seconds * 1000
        if self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            return delta.total_seconds() * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_name": self.task_name,
            "scheduled_at": self.scheduled_at.isoformat(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "success": self.success,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "duration_seconds": self.duration_seconds,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class SchedulerStats:
    """
    调度器统计信息
    
    用于监控和分析调度器运行情况
    """
    total_tasks: int = 0
    active_tasks: int = 0
    paused_tasks: int = 0
    disabled_tasks: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    error_history_size: int = 0
    
    @property
    def success_rate(self) -> float:
        """获取成功率百分比"""
        if self.total_executions == 0:
            return 100.0
        return (self.successful_executions / self.total_executions) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_tasks": self.total_tasks,
            "active_tasks": self.active_tasks,
            "paused_tasks": self.paused_tasks,
            "disabled_tasks": self.disabled_tasks,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "error_history_size": self.error_history_size,
            "success_rate": round(self.success_rate, 2),
        }
