# services/key_generator.py (v10.0 - Final)

import os
from loguru import logger
import random
from eth_account import Account
from bip_utils import Bip39SeedGenerator, Bip39Mnemonic, Bip44, Bip44Coins
from config.app_config import WORDLISTS_DIR
from core.models import GeneratedWallet

class KeyGenerator:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.wordlist_iterators = []
        self.on_settings_updated(self.settings_manager.settings)

    def on_settings_updated(self, new_settings: dict):
        self.strategies_config = new_settings.get("strategies", {})
        self.sequential_counter = self.strategies_config.get("sequential", {}).get("current_pos", 1)
        self._setup_wordlist_iterators()

    def _setup_wordlist_iterators(self):
        self.close_files()
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
                        logger.info(f"Wordlist '{filename}' opened successfully.")
                    except Exception as e:
                        logger.error(f"Failed to open wordlist {path}: {e}")

    def generate_batch(self, total_count: int) -> list[GeneratedWallet]:
        """
        إنشاء دفعة هجينة بناءً على النسب المحددة.
        هذه هي الدالة الوحيدة التي يتم استدعاؤها من الخارج.
        """
        wallets = []
        allocations = self.strategies_config.get("allocations", {})

        # حساب عدد المحافظ لكل استراتيجية
        wordlist_count = int(total_count * (allocations.get("wordlist", 0) / 100))
        seq_count = int(total_count * (allocations.get("sequential", 0) / 100))

        # التوليد من قوائم الكلمات
        if self.strategies_config.get("wordlist", {}).get("enabled") and self.wordlist_iterators:
             wallets.extend(self._generate_from_wordlists_local(wordlist_count))

        # التوليد المتسلسل
        if self.strategies_config.get("sequential", {}).get("enabled"):
            for _ in range(seq_count):
                wallets.append(self._generate_from_sequential())
                self.sequential_counter += 1

        # إكمال الدفعة بالتوليد العشوائي
        random_count = total_count - len(wallets)
        if random_count > 0:
            wallets.extend([self._generate_random_eth() for _ in range(random_count)])

        random.shuffle(wallets)
        return wallets[:total_count]

    def _generate_random_eth(self) -> GeneratedWallet:
        private_key = os.urandom(32)
        acct = Account.from_key(private_key)
        return GeneratedWallet(acct.address, private_key.hex(), "random")

    def _generate_from_sequential(self) -> GeneratedWallet:
        pk_bytes = self.sequential_counter.to_bytes(32, 'big')
        acct = Account.from_key(pk_bytes)
        return GeneratedWallet(acct.address, pk_bytes.hex(), "sequential", source=self.sequential_counter)

    def _generate_from_wordlists_local(self, count: int) -> list[GeneratedWallet]:
        generated = []
        if not self.wordlist_iterators: return []

        for _ in range(count):
            if not self.wordlist_iterators: break
            it_choice = random.choice(self.wordlist_iterators)
            line = it_choice["file"].readline()

            if not line:
                logger.info(f"Reached end of wordlist: {it_choice['name']}")
                it_choice["file"].close()
                self.wordlist_iterators.remove(it_choice)
                continue

            mnemonic = line.strip()
            wallet = self._generate_from_mnemonic(mnemonic)
            if wallet:
                generated.append(wallet)
        return generated

    def _generate_from_mnemonic(self, mnemonic: str) -> GeneratedWallet | None:
        try:
            if not Bip39Mnemonic.IsValid(mnemonic): return None
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
            bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
            bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(0).AddressIndex(0)

            address = bip44_acc.PublicKey().ToAddress()
            private_key = bip44_acc.PrivateKey().Raw().ToHex()
            return GeneratedWallet(address, private_key, "wordlist", source=mnemonic)
        except Exception:
            return None

    def save_state(self):
        logger.info("Saving search progress...")
        self.settings_manager.set("strategies.sequential.current_pos", self.sequential_counter)
        for it in self.wordlist_iterators:
            try:
                filename = it["name"]
                current_pos = it["file"].tell()
                self.settings_manager.set(f"strategies.wordlist.files.{filename}.current_pos", current_pos)
            except Exception as e:
                logger.warning(f"Failed to save position for file {it['name']}: {e}")
        self.settings_manager.save_settings()

    def close_files(self):
        logger.info("Closing all wordlist files.")
        for it in self.wordlist_iterators:
            it["file"].close()
        self.wordlist_iterators = []