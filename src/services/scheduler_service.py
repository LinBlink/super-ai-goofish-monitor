"""
调度服务
负责管理定时任务的调度
"""
from datetime import datetime
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List

from src.core.cron_utils import build_cron_trigger
from src.domain.models.task import Task
from src.infrastructure.logging.logger import get_logger
from src.services.process_service import ProcessService

logger = get_logger(__name__)

# 触发时间错过多久之内仍然补跑一次；超过这个宽限期就跳过本次触发，等下一个
# cron 周期，避免任务堆积导致的连环错过。
DEFAULT_MISFIRE_GRACE_SECONDS = 60


class SchedulerService:
    """调度服务"""

    def __init__(self, process_service: ProcessService):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.process_service = process_service
        # 是否暂停全部定时触发；暂停后所有已加载任务的触发规则都不生效，
        # 但不影响手动触发（启动/全部开始）。
        self._paused = False
        self.scheduler.add_listener(
            self._on_job_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED
        )

    def _on_job_event(self, event: JobExecutionEvent) -> None:
        if event.code == EVENT_JOB_MISSED:
            logger.warning(f"任务 '{event.job_id}' 错过了预定触发时间: {event.scheduled_run_time}")
            return
        logger.error(f"任务 '{event.job_id}' 执行时抛出异常: {event.exception!r}")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("调度器已停止")

    def is_paused(self) -> bool:
        """是否处于「暂停全部定时触发」状态"""
        return self._paused

    def set_paused(self, paused: bool) -> None:
        """暂停/恢复全部定时触发。仅影响定时触发，不影响手动触发。"""
        self._paused = bool(paused)
        if not self.scheduler.running:
            return
        if self._paused:
            self.scheduler.pause()
            logger.info("已暂停全部定时触发（调度器仍在运行，手动触发不受影响）")
        else:
            self.scheduler.resume()
            logger.info("已恢复全部定时触发")

    def get_next_run_time(self, task_id: int):
        job = self.scheduler.get_job(f"task_{task_id}")
        if job is None:
            return None

        next_run_time = getattr(job, "next_run_time", None)
        if next_run_time is not None:
            return next_run_time

        trigger = getattr(job, "trigger", None)
        if trigger is None or not hasattr(trigger, "get_next_fire_time"):
            return None

        try:
            now = datetime.now(self.scheduler.timezone)
            return trigger.get_next_fire_time(None, now)
        except Exception:
            return None

    async def reload_jobs(self, tasks: List[Task]):
        """重新加载所有定时任务"""
        logger.info("正在重新加载定时任务...")
        self.scheduler.remove_all_jobs()

        for task in tasks:
            if task.enabled and task.cron:
                try:
                    trigger = build_cron_trigger(
                        task.cron,
                        timezone=self.scheduler.timezone,
                    )
                    self.scheduler.add_job(
                        self._run_task,
                        trigger=trigger,
                        args=[task.id, task.task_name],
                        id=f"task_{task.id}",
                        name=f"Scheduled: {task.task_name}",
                        replace_existing=True,
                        # 同一个任务不允许并发跑第二个触发实例；错过超过宽限期就跳过，
                        # 不要在恢复后一次性把错过的触发全部补跑一遍。
                        max_instances=1,
                        coalesce=True,
                        misfire_grace_time=DEFAULT_MISFIRE_GRACE_SECONDS,
                    )
                    logger.info(f"  -> 已为任务 '{task.task_name}' 添加定时规则: '{task.cron}'")
                except ValueError as e:
                    logger.warning(f"  -> [警告] 任务 '{task.task_name}' 的 Cron 表达式无效: {e}")

        logger.info("定时任务加载完成")

        # 重新加载后，若处于「暂停全部定时触发」状态，则让调度器保持暂停。
        # （pause 作用于整个调度器，而非单个 job，因此 remove_all_jobs + add_job
        # 之后定时触发依旧不会生效，直到 resume。）
        if self._paused and self.scheduler.running:
            self.scheduler.pause()

    async def _run_task(self, task_id: int, task_name: str):
        """执行定时任务：加入串行队列，由队列 worker 顺序执行"""
        logger.info(f"定时任务触发: 正在为任务 '{task_name}' 加入串行执行队列...")
        try:
            await self.process_service.enqueue_task(task_id, task_name)
        except Exception as exc:
            # APScheduler 会把这里抛出的异常记录进它自己的内部日志（并触发
            # EVENT_JOB_ERROR），但那部分日志容易被忽略；这里显式记录一份，
            # 确保失败在应用日志里也能看到。
            logger.error(f"任务 '{task_name}' (id={task_id}) 入队失败: {exc!r}")
            raise
