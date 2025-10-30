# services/key_generator.py (v4.2 - إصلاح ImportError)

import os
from loguru import logger
import random
from eth_account import Account
# --- التصحيح هنا ---
from bip_utils import Bip39SeedGenerator, Bip39Mnemonic, Bip44, Bip44Coins
from config.app_config import WORDLISTS_DIR
from core.models import GeneratedWallet

# --- الدوال النقالة (Picklable Functions) للتشغيل في عمليات منفصلة ---

def _generate_random_eth() -> GeneratedWallet:
    private_key = os.urandom(32)
    acct = Account.from_key(private_key)
    return GeneratedWallet(acct.address, private_key.hex(), "random")

def _generate_from_sequential(counter: int) -> GeneratedWallet:
    pk_bytes = counter.to_bytes(32, 'big')
    acct = Account.from_key(pk_bytes)
    return GeneratedWallet(acct.address, pk_bytes.hex(), "sequential", source=counter)

def _generate_from_wordlist_mnemonic(mnemonic: str) -> GeneratedWallet | None:
    """يأخذ عبارة استعادة ويحولها إلى محفظة."""
    try:
        # التحقق من صحة العبارة أولاً
        if not Bip39Mnemonic.IsValid(mnemonic):
            return None

        seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
        bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(0).AddressIndex(0)

        address = bip44_acc.PublicKey().ToAddress()
        private_key = bip44_acc.PrivateKey().Raw().ToHex()
        return GeneratedWallet(address, private_key, "wordlist", source=mnemonic)
    except Exception:
        return None

def generate_batch_pure(config: dict, total_count: int) -> list[GeneratedWallet]:
    """
    دالة نقية ومستقلة تمامًا لتوليد دفعة. يمكن إرسالها بأمان إلى ProcessPoolExecutor.
    ملاحظة: هذه الدالة لا تتعامل مع قوائم الكلمات لأنها تتطلب الوصول للملفات.
    """
    wallets = []
    allocations = config.get("allocations", {})

    # التوليد المتسلسل
    seq_count = int(total_count * (allocations.get("sequential", 0) / 100))
    if config.get("sequential", {}).get("enabled"):
        counter = config.get("sequential", {}).get("current_pos", 1)
        for i in range(seq_count):
            wallets.append(_generate_from_sequential(counter + i))

    # إكمال الدفعة بالتوليد العشوائي
    random_count = total_count - len(wallets)
    wallets.extend([_generate_random_eth() for _ in range(random_count)])

    random.shuffle(wallets)
    return wallets[:total_count]


class KeyGenerator:
    """
    مدير توليد المفاتيح. يدير الاستراتيجيات المختلفة ويحافظ على حالة التقدم.
    """
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.wordlist_iterators = []
        self.on_settings_updated(self.settings_manager.settings)

    def on_settings_updated(self, new_settings: dict):
        self.strategies_config = new_settings.get("strategies", {})
        self.sequential_counter = self.strategies_config.get("sequential", {}).get("current_pos", 1)
        self._setup_wordlist_iterators()

    def _setup_wordlist_iterators(self):
        """إعداد المؤشرات لجميع قوائم الكلمات المفعلة."""
        self.close_files() # إغلاق الملفات القديمة قبل فتح الجديدة
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
        هذه الدالة الآن هي غلاف يجمع بين التوليد من الملفات (في الخيط الرئيسي)
        والتوليد النقي (الذي سيتم إرساله إلى عمليات أخرى).
        """
        wallets = []
        allocations = self.strategies_config.get("allocations", {})

        # 1. التوليد من قوائم الكلمات (يحدث هنا لأنه يتطلب الوصول للملفات)
        wordlist_count = int(total_count * (allocations.get("wordlist", 0) / 100))
        if self.strategies_config.get("wordlist", {}).get("enabled") and self.wordlist_iterators:
             wallets.extend(self._generate_from_wordlists_local(wordlist_count))

        # 2. حساب العدد المتبقي للاستراتيجيات الأخرى
        remaining_count = total_count - len(wallets)

        # 3. توليد بقية الدفعة باستخدام الدالة النقية (سيتم استدعاؤها في Engine)
        # هنا سنقوم فقط بمحاكاة التوليد المتبقي
        config_copy = self.strategies_config.copy()
        # تعديل النسب لتصبح 100% من العدد المتبقي
        sub_allocations = {
            "random": allocations.get("random", 0),
            "sequential": allocations.get("sequential", 0)
        }
        total_sub = sum(sub_allocations.values())
        if total_sub > 0:
            config_copy["allocations"] = {k: (v / total_sub) * 100 for k, v in sub_allocations.items()}

        # استدعاء الدالة النقية لمحاكاة ما سيحدث في المحرك
        remaining_wallets = generate_batch_pure(config_copy, remaining_count)
        wallets.extend(remaining_wallets)

        random.shuffle(wallets)
        return wallets

    def _generate_from_wordlists_local(self, count: int) -> list[GeneratedWallet]:
        """يقرأ من ملفات قوائم الكلمات ويولد محافظ."""
        generated = []
        if not self.wordlist_iterators: return []

        for _ in range(count):
            if not self.wordlist_iterators: break
            it_choice = random.choice(self.wordlist_iterators)
            line = it_choice["file"].readline()

            if not line: # نهاية الملف، أغلقه وأزله من القائمة
                logger.info(f"Reached end of wordlist: {it_choice['name']}")
                it_choice["file"].close()
                self.wordlist_iterators.remove(it_choice)
                continue

            mnemonic = line.strip()
            wallet = _generate_from_wordlist_mnemonic(mnemonic)
            if wallet:
                generated.append(wallet)
        return generated

    def save_state(self):
        """حفظ الموضع الحالي للاستراتيجيات في ملف الإعدادات."""
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
        """إغلاق جميع ملفات قوائم الكلمات المفتوحة."""
        logger.info("Closing all wordlist files.")
        for it in self.wordlist_iterators:
            it["file"].close()
        self.wordlist_iterators = []