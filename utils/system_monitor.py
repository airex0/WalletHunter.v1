# utils/system_monitor.py (v5.0 - Final)

import psutil
from loguru import logger
import threading
import time

class SystemMonitor:
    """
    مراقب موارد النظام. يعمل في خيط منفصل لضمان عدم تأثره بضغط التطبيق.
    يرسل تحديثات عادية وإنذارات ذكية عبر طابور الأحداث.
    """
    def __init__(self, app_state):
        self.app_state = app_state
        self.thread = None
        self.warning_thresholds = {'cpu': 90.0, 'ram': 90.0}

    def start(self):
        """بدء مراقبة موارد النظام في خيط خلفي."""
        if self.app_state.sys_monitor_running: return
        self.app_state.sys_monitor_running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        logger.info("System monitor thread started.")

    def stop(self):
        """إيقاف مهمة المراقبة."""
        self.app_state.sys_monitor_running = False
        logger.info("System monitor thread stopped.")

    def monitor_loop(self):
        """الحلقة التي تعمل في الخلفية لجمع بيانات الموارد."""
        while self.app_state.sys_monitor_running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent

                # إرسال حدث تحديث عادي إلى الواجهة
                self.app_state.post_event("system_update", {"cpu": cpu, "ram": ram})

                # إرسال حدث إنذار إذا تجاوز الاستهلاك الحد الخطر
                if cpu > self.warning_thresholds['cpu']:
                    self.app_state.post_event("system_warning", f"High CPU usage: {cpu:.1f}%")
                if ram > self.warning_thresholds['ram']:
                    self.app_state.post_event("system_warning", f"High RAM usage: {ram:.1f}%")

            except Exception as e:
                logger.error(f"Error in system monitor loop: {e}")

            time.sleep(2) # تحديث كل ثانيتين