# core/engine.py (v3.2)

import asyncio
from loguru import logger
import time
from concurrent.futures import ProcessPoolExecutor
import os
from web3 import Web3, HTTPProvider
import threading

from .state import AppState
from services.key_generator import KeyGenerator
from services.blockchain_checker import BlockchainChecker
from services.ai_classifier import AIClassifier
from services.analytics_service import AnalyticsService
from config.settings_manager import SettingsManager
from core.models import FoundWallet

class ScannerEngine:
    def __init__(self, app_state: AppState):
        self.state = app_state
        self.settings_manager = SettingsManager()
        self.key_generator = KeyGenerator(self.settings_manager)
        self.blockchain_checker = BlockchainChecker(self.settings_manager)
        self.ai_classifier = AIClassifier()
        self.analytics_service = AnalyticsService()

        self.process_pool = ProcessPoolExecutor(max_workers=os.cpu_count())

    def start_scan_in_thread(self):
        if self.state.is_running: return

        # --- الإصلاح: تحديث الحالة المركزية ---
        self.state.is_running = True
        self.state.post_event("status_change", "running")

        thread = threading.Thread(target=lambda: asyncio.run(self.start_scan()), daemon=True)
        thread.start()

    async def verify_api_connection(self) -> bool:
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
        self.state.session_scanned = 0
        self.state.add_log("🚀 Scan process started...")
        loop = asyncio.get_running_loop()

        while self.state.is_running:
            self.settings_manager.settings = self.settings_manager._load_settings()
            scanner_settings = self.settings_manager.get("scanner", {})
            concurrency = scanner_settings.get("concurrency", 5000)
            delay = scanner_settings.get("delay", 1)

            if self.settings_manager.get("strategies.ai_managed"):
                self._self_tune_strategies()

            batch_start_time = time.time()

            wallets_to_check = await loop.run_in_executor(
                self.process_pool, self.key_generator.generate_batch, concurrency
            )

            activity_hits = await self.blockchain_checker._filter_for_activity(wallets_to_check)

            for hit in activity_hits:
                self.state.db_queue.put(('activity_hits', hit.__dict__))

            if activity_hits:
                self.state.add_log(f"🔍 Found {len(activity_hits)} active wallets. Starting full balance check...")
                found_wallets_data = await self.blockchain_checker._check_balances_full(activity_hits)

                if found_wallets_data:
                    for data in found_wallets_data:
                        ai_score = self.ai_classifier.classify(data)
                        wallet = FoundWallet(**data, ai_score=ai_score)
                        self.state.db_queue.put(('found_wallets', wallet.__dict__))
                        self.state.total_found += 1
                        self.state.add_found_wallet(wallet)

            batch_duration = time.time() - batch_start_time
            self.state.scan_speed = concurrency / batch_duration if batch_duration > 0 else 0
            self.state.session_scanned += concurrency

            self.state.post_event("stats_update", {
                "session_scanned": self.state.session_scanned,
                "total_found": self.state.total_found,
                "scan_speed": self.state.scan_speed
            })

            await asyncio.sleep(delay)

        self.state.scan_speed = 0.0
        self.state.post_event("status_change", "stopped")

    def _self_tune_strategies(self):
        performance_ratios = self.analytics_service.get_strategy_performance()
        self.settings_manager.set("strategies.allocations", performance_ratios)
        self.state.post_event("strategy_update", {k: f'{v:.1f}%' for k,v in performance_ratios.items()})

    def stop_scan(self):
        # --- الإصلاح: تحديث الحالة المركزية ---
        if self.state.is_running:
            self.state.is_running = False
            self.key_generator.save_state()
            self.key_generator.close_files()
            logger.info("Scan stop requested. Exiting loop after current batch.")