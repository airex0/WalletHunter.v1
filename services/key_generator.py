import os
from loguru import logger
import random
from eth_account import Account
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
from config.app_config import WORDLISTS_DIR
from core.models import GeneratedWallet

class KeyGenerator:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self._reload_config()

    def _reload_config(self):
        """إعادة تحميل الإعدادات والمؤشرات من مدير الإعدادات."""
        self.strategies_config = self.settings_manager.get("strategies")
        self.sequential_counter = self.strategies_config.get("sequential", {}).get("current_pos", 1)
        self._setup_wordlist_iterators()

    def _setup_wordlist_iterators(self):
        """إعداد المؤشرات لجميع قوائم الكلمات المفعلة."""
        self.wordlist_iterators = []
        os.makedirs(WORDLISTS_DIR, exist_ok=True)
        wordlist_files = self.strategies_config.get("wordlist", {}).get("files", {})

        for filename, config in wordlist_files.items():
            if config.get("enabled"):
                path = os.path.join(WORDLISTS_DIR, filename)
                if os.path.exists(path):
                    try:
                        f = open(path, "r", encoding="utf-8", errors="ignore")
                        f.seek(config.get("current_pos", 0))
                        self.wordlist_iterators.append({"file": f, "name": filename})
                    except Exception as e:
                        logger.error(f"فشل فتح قائمة الكلمات {path}: {e}")

    def generate_batch(self, total_count: int) -> list[GeneratedWallet]:
        """إنشاء دفعة هجينة بناءً على النسب المحددة."""
        self._reload_config()

        wallets = []
        allocations = self.strategies_config.get("allocations", {})

        # التوليد من قوائم الكلمات
        wordlist_count = int(total_count * (allocations.get("wordlist", 0) / 100))
        if self.strategies_config.get("wordlist", {}).get("enabled") and self.wordlist_iterators:
            wallets.extend(self._generate_from_wordlists(wordlist_count))

        # التوليد المتسلسل
        seq_count = int(total_count * (allocations.get("sequential", 0) / 100))
        if self.strategies_config.get("sequential", {}).get("enabled"):
            for _ in range(seq_count):
                wallets.append(self._generate_from_sequential())
                self.sequential_counter += 1

        # إكمال الدفعة بالتوليد العشوائي
        random_count = total_count - len(wallets)
        wallets.extend([self._generate_random_eth() for _ in range(random_count)])

        random.shuffle(wallets) # خلط الدفعة النهائية
        return wallets

    def _generate_random_eth(self) -> GeneratedWallet:
        private_key = os.urandom(32)
        acct = Account.from_key(private_key)
        return GeneratedWallet(acct.address, private_key.hex(), "random")

    def _generate_from_sequential(self) -> GeneratedWallet:
        pk_bytes = self.sequential_counter.to_bytes(32, 'big')
        acct = Account.from_key(pk_bytes)
        return GeneratedWallet(acct.address, pk_bytes.hex(), "sequential", source=self.sequential_counter)

    def _generate_from_wordlists(self, count: int) -> list[GeneratedWallet]:
        generated = []
        if not self.wordlist_iterators: return []

        for _ in range(count):
            it = random.choice(self.wordlist_iterators) # اختيار ملف عشوائي
            line = it["file"].readline()
            if not line: # نهاية الملف، انتقل للتالي
                continue

            mnemonic = line.strip()
            try:
                seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
                bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
                bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(0).AddressIndex(0)

                address = bip44_acc.PublicKey().ToAddress()
                private_key = bip44_acc.PrivateKey().Raw().ToHex()
                generated.append(GeneratedWallet(address, private_key, "wordlist", source=mnemonic))
            except Exception:
                continue
        return generated

    def save_state(self):
        """حفظ الموضع الحالي للاستراتيجيات في ملف الإعدادات."""
        logger.info("حفظ تقدم البحث...")
        self.settings_manager.set("strategies.sequential.current_pos", self.sequential_counter)
        for it in self.wordlist_iterators:
            try:
                filename = it["name"]
                current_pos = it["file"].tell()
                self.settings_manager.set(f"strategies.wordlist.files.{filename}.current_pos", current_pos)
            except Exception as e:
                logger.warning(f"فشل في حفظ موضع الملف {it['name']}: {e}")
        self.settings_manager.save_settings()

    def close_files(self):
        """إغلاق جميع ملفات قوائم الكلمات المفتوحة."""
        for it in self.wordlist_iterators:
            it["file"].close()