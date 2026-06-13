"""轻量后台任务管理器。

解决裸 asyncio.create_task() 的常见问题：
- 任务异常被静默吞掉
- 同一资源并发执行重复任务
- 组件生命周期内无法追踪运行中的任务
"""

import asyncio
import logging
from typing import Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """按 key 追踪后台任务，自动处理异常并防止同一 key 并发重复执行。"""

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}

    def start(self, key: str, coro: Coroutine, *, replace: bool = True) -> asyncio.Task:
        """启动一个后台任务并按 key 追踪。

        Args:
            key: 任务唯一标识，通常包含资源 ID，例如 "understanding:file_123"
            coro: 要执行的协程
            replace: 为 True 时取消同 key 的已有任务；为 False 时若 key 已存在则跳过

        Returns:
            新创建或已存在的 asyncio.Task
        """
        existing = self._tasks.get(key)
        if existing and not existing.done():
            if not replace:
                logger.debug("任务 %s 已在运行，跳过重复启动", key)
                return existing
            logger.info("取消已运行的同 key 任务: %s", key)
            existing.cancel()

        task = asyncio.create_task(coro)
        self._tasks[key] = task
        task.add_done_callback(lambda t: self._on_task_done(key, t))
        return task

    def _on_task_done(self, key: str, task: asyncio.Task) -> None:
        """任务完成回调：记录异常并清理。"""
        self._tasks.pop(key, None)
        exc = task.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            logger.exception("后台任务 %s 执行失败", key, exc_info=exc)

    def get(self, key: str) -> Optional[asyncio.Task]:
        """获取指定 key 的运行中任务。"""
        return self._tasks.get(key)

    def is_running(self, key: str) -> bool:
        """判断指定 key 是否有任务在运行。"""
        task = self._tasks.get(key)
        return task is not None and not task.done()

    def cancel(self, key: str) -> bool:
        """取消指定 key 的任务。返回是否成功取消。"""
        task = self._tasks.get(key)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def shutdown(self, timeout: Optional[float] = 5.0) -> None:
        """优雅关闭：取消所有运行中任务并等待超时。"""
        pending = [t for t in self._tasks.values() if not t.done()]
        if not pending:
            return
        for task in pending:
            task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("关闭 TaskManager 时部分任务未在 %.1fs 内完成", timeout)


# 全局默认任务管理器实例（适合单进程部署；多 worker 部署需自行管理）
task_manager = TaskManager()
