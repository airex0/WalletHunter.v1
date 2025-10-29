# core/state.py (v3.2)

import flet as ft
from queue import Queue
from core.models import FoundWallet
import threading
from database import db_writer

class AppState:
    """
    مدير الحالة المركزي. يحتوي على الحالة المشتركة لجميع أجزاء التطبيق.
    """
    def __init__(self, page: ft.Page):
        self.page = page
        self.engine = None
        self.sys_monitor = None
        self.is_running_app = True

        # --- الإصلاح الجذري: إعادة is_running إلى هنا ---
        self.is_running = False # هذه هي الحالة التي يتحقق منها الجميع

        self.event_queue = Queue()
        self.db_queue = Queue()
        self.db_writer_thread = threading.Thread(target=db_writer, args=(self.db_queue,), daemon=True)
        self.db_writer_thread.start()

        # البيانات الخام
        self.session_scanned = 0
        self.total_found = 0
        self.scan_speed = 0.0
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.api_status = "UNKNOWN"
        self.found_wallets = []
        self.strategy_allocations = {}

    def post_event(self, event_type: str, data: any = None):
        """يستخدمه الباك إند لإرسال تحديثات إلى الواجهة عبر طابور آمن."""
        self.event_queue.put({"type": event_type, "data": data})

    def add_log(self, message: str):
        self.post_event("log", message)

    def add_found_wallet(self, wallet: FoundWallet):
        self.found_wallets.insert(0, wallet)
        self.post_event("new_wallet", wallet)