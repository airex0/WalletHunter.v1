import flet as ft
from queue import Queue
from core.models import FoundWallet
import threading
from database import db_writer

class AppState:
    def __init__(self, page: ft.Page):
        self.page = page
        self.engine = None
        self.sys_monitor = None
        self.is_running_app = True
        self.is_running = False
        self.sys_monitor_running = False

        self.event_queue = Queue()

        self.db_queue = Queue()
        self.db_writer_thread = threading.Thread(target=db_writer, args=(self.db_queue,), daemon=True)
        self.db_writer_thread.start()

        self.session_scanned = 0
        self.total_found = 0
        self.scan_speed = 0.0
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.api_status = "UNKNOWN"
        self.found_wallets = []
        self.strategy_allocations = {}

    def post_event(self, event_type: str, data: any = None):
        self.event_queue.put({"type": event_type, "data": data})

    def add_log(self, message: str):
        self.post_event("log", message)

    def add_found_wallet(self, wallet: FoundWallet):
        self.found_wallets.insert(0, wallet)
        self.post_event("new_wallet", wallet)