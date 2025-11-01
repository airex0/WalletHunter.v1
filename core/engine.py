# core/engine.py (v10.0 - Final)

import asyncio
from loguru import logger
import time
from concurrent.futures import ThreadPoolExecutor
import os
from web3 import Web3, HTTPProvider
import threading

from .state import AppState
from services.key_generator import KeyGenerator
from services.blockchain_checker import BlockchainChecker
from services.ai_classifier import AIClassifier
from services.analytics_service import AnalyticsService
from config.settings_manager import get_settings_manager
from core.models import FoundWallet

class ScannerEngine:
    """
    العقل المدبر للتطبيق. يطبق نمط المراقب (Observer) للاستجابة الفورية لتغييرات الإعدادات.
    يدير دورة حياة الفحص في خيط منفصل لضمان استجابة الواجهة.
    يستخدم ThreadPoolExecutor للمهام الحاسوبية لضمان التوافق والموثوقية.
    """
    def __init__(self, app_state: AppState):
        self.state = app_state
        self.settings_manager = get_settings_manager()
        self.settings_manager.register_observer(self)

        self.ai_classifier = AIClassifier()
        self.analytics_service = AnalyticsService()

        # استخدام ThreadPoolExecutor لأنه أكثر توافقًا وموثوقية في بيئات Flet و Replit
        self.thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() * 5)

        # تطبيق الإعدادات الأولية عند الإنشاء
        self.on_settings_updated(self.settings_manager.settings)

    def on_settings_updated(self, new_settings: dict):
        """
        دالة رد نداء (Callback) يتم استدعاؤها تلقائيًا من SettingsManager.
        تقوم بتحديث معلمات المحرك بشكل فوري.
        """
        logger.info("ScannerEngine received new settings. Applying them immediately.")
        self.scanner_settings = new_settings.get("scanner", {})
        self.concurrency = self.scanner_settings.get("concurrency", 5000)
        self.delay = self.scanner_settings.get("delay", 1)

        self.blockchain_checker = BlockchainChecker(self.settings_manager)
        self.key_generator = KeyGenerator(self.settings_manager)

        self.state.add_log("⚙️ تم تطبيق الإعدادات الجديدة بنجاح.")

    def start_scan_in_thread(self):
        """إنشاء وتشغيل حلقة الفحص في خيط منفصل لضمان عدم تجميد الواجهة."""
        if self.state.is_running: return

        thread = threading.Thread(target=lambda: asyncio.run(self.start_scan()), daemon=True)
        thread.start()

    async def verify_api_connection(self) -> bool:
        """التحقق من أن مفتاح Alchemy API يعمل بشكل صحيح."""
        try:
            api_key = self.settings_manager.get("api_keys.alchemy")
            if not api_key:
                self.state.post_event("api_status_update", "FAILED")
                return False

            rpc_url = self.settings_manager.get("networks.Ethereum.rpc_placeholder").format(api_key=api_key)
            w3 = Web3(HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
            await asyncio.to_thread(w3.eth.get_block_number)

            self.state.post_event("api_status_update", "OK")
            logger.info("API connection verification successful.")
            return True
        except Exception as e:
            logger.warning(f"API connection verification failed: {e}")
            self.state.post_event("api_status_update", "FAILED")
            return False

    async def start_scan(self):
        """الحلقة الرئيسية لعملية الفحص. تعمل بشكل غير متزامن في خيطها الخاص."""
        self.state.is_running = True
        self.state.post_event("status_change", "running")

        self.state.session_scanned = 0
        self.state.add_log("🚀 Scan process started...")
        loop = asyncio.get_running_loop()

        while self.state.is_running:
            if self.settings_manager.get("strategies.ai_managed"):
                self._self_tune_strategies()

            batch_start_time = time.time()

            # استدعاء دالة التوليد الموحدة والبسيطة في ThreadPoolExecutor
            wallets_to_check = await loop.run_in_executor(
                self.thread_pool, self.key_generator.generate_batch, self.concurrency
            )

            if not wallets_to_check:
                self.state.add_log("⚠️ لم يتم توليد أي محافظ. تحقق من إعدادات الاستراتيجيات وقوائم الكلمات.")
                await asyncio.sleep(self.delay)
                continue

            activity_hits = await self.blockchain_checker._filter_for_activity(wallets_to_check)

            for hit in activity_hits:
                self.state.db_queue.put(('activity_hits', hit.__dict__))

            if activity_hits:
                self.state.add_log(f"🔍 تم العثور على {len(activity_hits)} محفظة نشطة. بدء الفحص الكامل...")
                found_wallets_data = await self.blockchain_checker._check_balances_full(activity_hits)

                if found_wallets_data:
                    for data in found_wallets_data:
                        ai_score = self.ai_classifier.classify(data)
                        wallet = FoundWallet(**data, ai_score=ai_score)
                        self.state.db_queue.put(('found_wallets', wallet.__dict__))
                        self.state.total_found += 1
                        self.state.add_found_wallet(wallet)

            batch_duration = time.time() - batch_start_time
            self.state.scan_speed = self.concurrency / batch_duration if batch_duration > 0 else 0
            self.state.session_scanned += self.concurrency

            self.state.post_event("stats_update", {
                "session_scanned": self.state.session_scanned,
                "total_found": self.state.total_found,
                "scan_speed": self.state.scan_speed
            })

            await asyncio.sleep(self.delay)

        self.state.scan_speed = 0.0
        self.state.post_event("status_change", "stopped")

    def _self_tune_strategies(self):
        """يقوم بتعديل نسب توزيع الاستراتيجيات بناءً على أدائها التاريخي."""
        performance_ratios = self.analytics_service.get_strategy_performance()
        self.settings_manager.set("strategies.allocations", performance_ratios)
        self.state.post_event("strategy_update", performance_ratios)

    def stop_scan(self):
        """إيقاف حلقة الفحص بشكل آمن وحفظ التقدم."""
        if self.state.is_running:
            self.state.is_running = False
            self.key_generator.save_state()
            self.key_generator.close_files()
            logger.info("Scan stop requested. Exiting loop after current batch.")