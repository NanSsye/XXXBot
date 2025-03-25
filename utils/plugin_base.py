from abc import ABC

from loguru import logger

from .decorators import scheduler, add_job_safe, remove_job_safe


class PluginBase(ABC):
    """插件基类"""

    # 插件元数据
    description: str = "暂无描述"
    author: str = "未知"
    version: str = "1.0.0"

    def __init__(self):
        self.enabled = False
        self._scheduled_jobs = set()

    async def on_enable(self, bot=None):
        """插件启用时调用"""

        # 定时任务
        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, '_is_scheduled'):
                job_id = getattr(method, '_job_id')
                trigger = getattr(method, '_schedule_trigger')
                trigger_args = getattr(method, '_schedule_args')

                add_job_safe(scheduler, job_id, method, bot, trigger, **trigger_args)
                self._scheduled_jobs.add(job_id)
        if self._scheduled_jobs:
            logger.success("插件 {} 已加载定时任务: {}", self.__class__.__name__, self._scheduled_jobs)

    async def on_disable(self):
        """插件禁用时调用"""
        
        # 移除定时任务
        for job_id in self._scheduled_jobs:
            remove_job_safe(scheduler, job_id)
        logger.info("已卸载定时任务: {}", self._scheduled_jobs)
        self._scheduled_jobs.clear()

    async def async_init(self):
        """插件异步初始化"""
        return
