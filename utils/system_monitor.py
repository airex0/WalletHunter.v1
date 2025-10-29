import psutil
import asyncio
from loguru import logger

class SystemMonitor:
    def __init__(self, app_state):
        self.app_state = app_state
        self._task = None

    def start(self):
        """بدء مراقبة موارد النظام في مهمة خلفية."""
        if self._task is None:
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("تم بدء مراقبة النظام.")

    def stop(self):
        """إيقاف مهمة المراقبة."""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("تم إيقاف مراقبة النظام.")

    async def _monitor_loop(self):
        while True:
            try:
                self.app_state.cpu_usage = psutil.cpu_percent(interval=None)
                self.app_state.ram_usage = psutil.virtual_memory().percent
                await asyncio.sleep(2) # تحديث كل ثانيتين
            except asyncio.CancelledError:
                logger.info("تم إلغاء مهمة مراقبة النظام.")
                break
            except Exception as e:
                logger.error(f"خطأ في مراقبة النظام: {e}")
                await asyncio.sleep(5)