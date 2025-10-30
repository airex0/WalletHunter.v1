import psutil
from loguru import logger
import threading
import time

class SystemMonitor:
    def __init__(self, app_state):
        self.app_state = app_state
        self.thread = None

    def start(self):
        if self.app_state.sys_monitor_running: return
        self.app_state.sys_monitor_running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        logger.info("System monitor thread started.")

    def stop(self):
        self.app_state.sys_monitor_running = False
        logger.info("System monitor thread stopped.")

    def monitor_loop(self):
        while self.app_state.sys_monitor_running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent

                self.app_state.post_event("system_update", {"cpu": cpu, "ram": ram})

                if cpu > 90.0:
                    self.app_state.post_event("system_warning", f"High CPU usage: {cpu:.1f}%")
                if ram > 90.0:
                    self.app_state.post_event("system_warning", f"High RAM usage: {ram:.1f}%")

            except Exception as e:
                logger.error(f"Error in system monitor loop: {e}")

            time.sleep(2)