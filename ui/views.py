# ui/views.py (v6.0 - Final)

import flet as ft
import asyncio
import time
from loguru import logger
import os
import shutil
import threading

from core.state import AppState
from core.engine import ScannerEngine
from .components import KPI, SystemMonitorGauge
from utils.system_monitor import SystemMonitor
from config.settings_manager import get_settings_manager
from config.app_config import WORDLISTS_DIR
from core.models import FoundWallet

class MainView(ft.View):
    """
    العرض الرئيسي للتطبيق (لوحة المعلومات).
    هذا الكلاس مسؤول فقط عن عرض البيانات واستقبال أوامر المستخدم.
    لا يحتوي على أي منطق عمل، بل يتفاعل مع الباك إند عبر طابور الأحداث.
    """
    def __init__(self, app_state: AppState, go_func):
        super().__init__(route="/", scroll=ft.ScrollMode.ADAPTIVE)
        self.app_state = app_state
        self.go = go_func

        # التأكد من وجود نسخة واحدة فقط من الخدمات الأساسية
        if not app_state.engine: 
            app_state.engine = ScannerEngine(app_state)
        self.engine = app_state.engine

        if not app_state.sys_monitor: 
            app_state.sys_monitor = SystemMonitor(app_state)
        self.sys_monitor = app_state.sys_monitor

        self.build_components()

    def build_components(self):
        # --- مكونات الواجهة ---
        self.kpi_session = ft.Text("0", size=28, weight=ft.FontWeight.BOLD)
        self.kpi_found = ft.Text("0", size=28, weight=ft.FontWeight.BOLD, color="green400")
        self.kpi_speed = ft.Text("0.00", size=28, weight=ft.FontWeight.BOLD)

        self.cpu_progress = ft.ProgressBar(width=100, color="orange", bgcolor="#444444")
        self.cpu_text = ft.Text("0.0%")
        self.ram_progress = ft.ProgressBar(width=100, color="lightblue", bgcolor="#444444")
        self.ram_text = ft.Text("0.0%")

        self.start_stop_button = ft.ElevatedButton(
            text="🚀 ابدأ الفحص", on_click=self.toggle_scan, icon="play_arrow", height=50, width=250,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
        )

        self.results_table = ft.DataTable(columns=[
            ft.DataColumn(ft.Text("العنوان")), ft.DataColumn(ft.Text("الشبكة")),
            ft.DataColumn(ft.Text("الرصيد"), numeric=True), ft.DataColumn(ft.Text("تصنيف AI")),
            ft.DataColumn(ft.Text("الاستراتيجية")),
        ], rows=[])
        self.log_view = ft.ListView(expand=True, auto_scroll=True, spacing=5)

        self.api_status_indicator = ft.Row([
            ft.CircleAvatar(radius=5, color="orange"), ft.Text("API Status: Checking...")
        ], alignment=ft.MainAxisAlignment.CENTER)

        self.appbar = ft.AppBar(
            title=ft.Text("WalletHunter Elite"), center_title=True,
            actions=[ft.IconButton(icon="settings", on_click=lambda _: self.go("/settings"), tooltip="الإعدادات")]
        )

        self.controls = [
            ft.Column(
                [
                    ft.Row([KPI("الجلسة الحالية", self.kpi_session), KPI("إجمالي المكتشف", self.kpi_found), KPI("السرعة (محفظة/ث)", self.kpi_speed)]),
                    ft.Divider(),
                    ft.Row([SystemMonitorGauge("CPU", self.cpu_progress, self.cpu_text), SystemMonitorGauge("RAM", self.ram_progress, self.ram_text), self.start_stop_button],
                           alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(),
                    ft.Row([
                        ft.Row([ft.Column([ft.Text("📊 النتائج المكتشفة", weight=ft.FontWeight.BOLD), self.results_table], expand=3)], scroll=ft.ScrollMode.ADAPTIVE, expand=3),
                        ft.Column([ft.Text("📜 سجل الأحداث", weight=ft.FontWeight.BOLD), self.log_view], expand=2),
                    ], expand=True)
                ],
                expand=True
            ),
            ft.Container(content=self.api_status_indicator, padding=ft.padding.only(left=10, bottom=5))
        ]

    def handle_event(self, event):
        """المعالج المركزي للأحداث. هذا هو المكان الوحيد الذي يتم فيه تحديث الواجهة."""
        event_type, data = event["type"], event["data"]

        if event_type == "stats_update":
            self.kpi_session.value = f"{data['session_scanned']:,}"
            self.kpi_found.value = f"{data['total_found']:,}"
            self.kpi_speed.value = f"{data['scan_speed']:.2f}"
        elif event_type == "status_change":
            is_running = (data == "running")
            self.start_stop_button.text = "🛑 إيقاف الفحص" if is_running else "🚀 ابدأ الفحص"
            self.start_stop_button.icon = "stop" if is_running else "play_arrow"
            self.start_stop_button.disabled = False
        elif event_type == "log":
            self.log_view.controls.insert(0, ft.Text(f"[{time.strftime('%H:%M:%S')}] {data}", size=12))
            if len(self.log_view.controls) > 100: self.log_view.controls.pop()
        elif event_type == "new_wallet":
            wallet: FoundWallet = data
            self.results_table.rows.insert(0, ft.DataRow(cells=[
                ft.DataCell(ft.Text(wallet.address, font_family="monospace")), ft.DataCell(ft.Text(wallet.chain)),
                ft.DataCell(ft.Text(f"${wallet.total_usdt:,.2f}")), ft.DataCell(ft.Text(wallet.ai_score)),
                ft.DataCell(ft.Text(wallet.strategy)),
            ]))
        elif event_type == "system_update":
            self.cpu_progress.color = "orange"
            self.ram_progress.color = "lightblue"
            self.cpu_progress.value, self.cpu_text.value = data["cpu"] / 100, f"{data['cpu']:.1f}%"
            self.ram_progress.value, self.ram_text.value = data["ram"] / 100, f"{data['ram']:.1f}%"
        elif event_type == "system_warning":
            if "CPU" in data: self.cpu_progress.color = "red"
            if "RAM" in data: self.ram_progress.color = "red"
            self.page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ {data}", color="yellow"), open=True)
        elif event_type == "api_status_update":
            is_ok = (data == "OK")
            self.api_status_indicator.controls[0].color = "green" if is_ok else "red"
            self.api_status_indicator.controls[1].value = "API Status: CONNECTED" if is_ok else "API Status: FAILED"
        elif event_type == "strategy_update":
            if self.page and self.page.views and isinstance(self.page.views[-1], SettingsView):
                self.page.views[-1].update_strategy_allocations_display(data)

        self.page.update()

    def toggle_scan(self, e):
        if self.app_state.is_running:
            self.start_stop_button.text, self.start_stop_button.disabled = "⏳ جاري الإيقاف...", True
            self.page.update()
            self.engine.stop_scan()
        else:
            if not self.engine.settings_manager.get("api_keys.alchemy"):
                self.page.snack_bar = ft.SnackBar(ft.Text("❌ خطأ: يرجى إدخال مفتاح Alchemy API أولاً."), open=True)
                self.page.update()
                return

            self.start_stop_button.text, self.start_stop_button.disabled = "⏳ جاري البدء...", True
            self.page.update()
            self.engine.start_scan_in_thread()

    async def did_mount_async(self):
        self.sys_monitor.start()
        threading.Thread(target=lambda: asyncio.run(self.engine.verify_api_connection()), daemon=True).start()

    async def will_unmount_async(self):
        self.sys_monitor.stop()


class SettingsView(ft.View):
    """
    العرض الخاص بصفحة الإعدادات.
    يتيح للمستخدم التحكم في جميع جوانب التطبيق.
    """
    def __init__(self, app_state: AppState, go_func):
        super().__init__(route="/settings", scroll=ft.ScrollMode.ADAPTIVE)
        self.app_state = app_state
        self.go = go_func
        self.settings_manager = get_settings_manager()

        self.build_components()

        self.appbar = ft.AppBar(title=ft.Text("الإعدادات"), leading=ft.IconButton(icon="arrow_back", on_click=lambda _: self.go("/")))
        self.controls = [self.layout]

    def build_components(self):
        self.file_picker = ft.FilePicker(on_result=self.on_file_picker_result)
        if self.file_picker not in self.app_state.page.overlay:
            self.app_state.page.overlay.append(self.file_picker)

        api_keys = self.settings_manager.get("api_keys")
        self.alchemy_key_field = ft.TextField(label="Alchemy API Key", value=api_keys.get("alchemy"), password=True, can_reveal_password=True)
        self.telegram_token_field = ft.TextField(label="Telegram Bot Token", value=api_keys.get("telegram_token"), password=True, can_reveal_password=True)
        self.telegram_chat_id_field = ft.TextField(label="Telegram Chat ID", value=api_keys.get("telegram_chat_id"))

        scanner_settings = self.settings_manager.get("scanner")
        self.min_balance_field = ft.TextField(label="الحد الأدنى للرصيد (USDT)", value=str(scanner_settings.get("min_balance")))
        self.concurrency_field = ft.TextField(label="عدد المحافظ / دورة", value=str(scanner_settings.get("concurrency")), tooltip="عدد المحافظ التي يتم فحصها في كل دفعة.")
        self.delay_field = ft.TextField(label="فترة الراحة (ثانية)", value=str(scanner_settings.get("delay")))

        self.network_switches = []
        for name, config in self.settings_manager.get("networks").items():
            self.network_switches.append(ft.Switch(label=name, value=config.get("enabled", False)))

        strategies = self.settings_manager.get("strategies", {})
        allocations = strategies.get("allocations", {})
        self.ai_switch = ft.Switch(label="إدارة تلقائية بواسطة AI", value=strategies.get("ai_managed", True), on_change=self.toggle_ai_management)

        self.strategy_allocations_view = ft.Column()
        self.update_strategy_allocations_display(allocations)

        self.wordlist_manager_view = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, height=150)
        self.update_wordlist_display()

        self.save_button = ft.ElevatedButton("حفظ الإعدادات", on_click=self.save_settings, icon="save")

        column_content = ft.Column(
            [
                ft.Text("مفاتيح الخدمات (API Keys)", size=20, weight=ft.FontWeight.BOLD),
                self.alchemy_key_field, self.telegram_token_field, self.telegram_chat_id_field,
                ft.Divider(),
                ft.Text("إعدادات الفحص", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([self.min_balance_field, self.concurrency_field, self.delay_field], scroll=ft.ScrollMode.ADAPTIVE),
                ft.Divider(),
                ft.Text("الشبكات المفعلة", size=20, weight=ft.FontWeight.BOLD),
                ft.Column(controls=self.network_switches),
                ft.Divider(),
                ft.Text("توزيع الاستراتيجيات", size=20, weight=ft.FontWeight.BOLD),
                self.ai_switch,
                self.strategy_allocations_view,
                ft.Divider(),
                ft.Text("مدير قوائم الكلمات", size=20, weight=ft.FontWeight.BOLD),
                self.wordlist_manager_view,
                ft.ElevatedButton("إضافة قائمة كلمات جديدة", icon="upload_file", on_click=lambda _: self.file_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["txt"])),
                ft.Divider(),
                self.save_button,
            ],
            spacing=15,
        )

        self.layout = ft.Container(content=column_content, padding=20)

    def toggle_ai_management(self, e=None):
        self.update_strategy_allocations_display(self.settings_manager.get("strategies.allocations"))

    def update_strategy_allocations_display(self, allocations: dict):
        self.strategy_allocations_view.controls.clear()
        is_ai_managed = self.ai_switch.value

        if is_ai_managed:
            total = sum(allocations.values())
            if total == 0: total = 1
            for name, value in allocations.items():
                percentage = (value / total) * 100
                self.strategy_allocations_view.controls.append(
                    ft.Row([
                        ft.Text(name.capitalize(), width=100),
                        ft.ProgressBar(value=percentage/100, width=300, color="cyan"),
                        ft.Text(f"{percentage:.1f}%")
                    ])
                )
        else:
            self.random_slider = ft.Slider(min=0, max=100, divisions=100, value=allocations.get("random", 80), label="{value}%")
            self.sequential_slider = ft.Slider(min=0, max=100, divisions=100, value=allocations.get("sequential", 10), label="{value}%")
            self.wordlist_slider = ft.Slider(min=0, max=100, divisions=100, value=allocations.get("wordlist", 10), label="{value}%")
            self.sliders = [self.random_slider, self.sequential_slider, self.wordlist_slider]
            self.strategy_allocations_view.controls.extend([
                ft.Row([ft.Text("Random", width=100), self.random_slider]),
                ft.Row([ft.Text("Sequential", width=100), self.sequential_slider]),
                ft.Row([ft.Text("Wordlist", width=100), self.wordlist_slider]),
            ])

        if self.page:
            self.page.update()

    def update_wordlist_display(self):
        self.wordlist_manager_view.controls.clear()
        wordlist_files = self.settings_manager.get("strategies.wordlist.files", {})
        if not wordlist_files:
            self.wordlist_manager_view.controls.append(ft.Text("لا توجد قوائم كلمات مضافة."))
        for filename, config in wordlist_files.items():
            self.wordlist_manager_view.controls.append(
                ft.Row(
                    [
                        ft.Switch(label=filename, value=config.get("enabled", False), data=filename),
                        ft.Text(f"التقدم: {config.get('current_pos', 0):,}"),
                        ft.IconButton(icon="delete", on_click=self.delete_wordlist, data=filename, tooltip="حذف الملف"),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )

    async def on_file_picker_result(self, e: ft.FilePickerResultEvent):
        if e.files:
            for file in e.files:
                try:
                    dest_path = os.path.join(WORDLISTS_DIR, file.name)
                    shutil.copy(file.path, dest_path)
                    self.settings_manager.set(f"strategies.wordlist.files.{file.name}", {"enabled": True, "current_pos": 0})
                    logger.info(f"تمت إضافة قائمة الكلمات: {file.name}")
                except Exception as ex:
                    logger.error(f"فشل إضافة قائمة الكلمات {file.name}: {ex}")

            self.update_wordlist_display()
            self.page.update()

    async def delete_wordlist(self, e):
        filename = e.control.data
        try:
            os.remove(os.path.join(WORDLISTS_DIR, filename))
            wordlist_files = self.settings_manager.get("strategies.wordlist.files")
            if filename in wordlist_files:
                del wordlist_files[filename]
            self.settings_manager.set("strategies.wordlist.files", wordlist_files)
            logger.info(f"تم حذف قائمة الكلمات: {filename}")
        except Exception as ex:
            logger.error(f"فشل حذف قائمة الكلمات {filename}: {ex}")

        self.update_wordlist_display()
        self.page.update()

    async def save_settings(self, e):
        try:
            self.settings_manager.set("api_keys.alchemy", self.alchemy_key_field.value)
            self.settings_manager.set("api_keys.telegram_token", self.telegram_token_field.value)
            self.settings_manager.set("api_keys.telegram_chat_id", self.telegram_chat_id_field.value)

            self.settings_manager.set("scanner.min_balance", float(self.min_balance_field.value))
            self.settings_manager.set("scanner.concurrency", int(self.concurrency_field.value))
            self.settings_manager.set("scanner.delay", int(self.delay_field.value))

            for switch in self.network_switches:
                self.settings_manager.set(f"networks.{switch.label}.enabled", switch.value)

            self.settings_manager.set("strategies.ai_managed", self.ai_switch.value)
            if not self.ai_switch.value:
                total = self.random_slider.value + self.sequential_slider.value + self.wordlist_slider.value
                if total == 0: total = 1
                self.settings_manager.set("strategies.allocations.random", (self.random_slider.value / total) * 100)
                self.settings_manager.set("strategies.allocations.sequential", (self.sequential_slider.value / total) * 100)
                self.settings_manager.set("strategies.allocations.wordlist", (self.wordlist_slider.value / total) * 100)

            for row in self.wordlist_manager_view.controls:
                if isinstance(row, ft.Row) and row.controls:
                    switch = row.controls[0]
                    if isinstance(switch, ft.Switch):
                        filename = switch.data
                        self.settings_manager.set(f"strategies.wordlist.files.{filename}.enabled", switch.value)

            self.settings_manager.save_settings()

            self.page.snack_bar = ft.SnackBar(ft.Text("✅ تم حفظ الإعدادات بنجاح! سيتم تطبيقها فورًا."), open=True)
        except Exception as ex:
            logger.error(f"فشل حفظ الإعدادات: {ex}")
            self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ خطأ: {ex}"), open=True)

        self.page.update()