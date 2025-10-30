# config/settings_manager.py (v5.1 - Final)

import json
import os
from loguru import logger
from cryptography.fernet import Fernet
from .app_config import SETTINGS_FILE_PATH, APP_KEY_PATH, DEFAULT_NETWORKS, DEFAULT_STRATEGIES

# --- تطبيق نمط Singleton لضمان وجود نسخة واحدة فقط ---
_instance = None

def get_settings_manager():
    """
    هذه الدالة تضمن أننا دائمًا نحصل على نفس النسخة (instance) من SettingsManager.
    هذا يحل مشكلة عدم تزامن الإعدادات بين الواجهة والمحرك.
    """
    global _instance
    if _instance is None:
        _instance = SettingsManager()
    return _instance
# ----------------------------------------------------

class SettingsManager:
    """
    مدير الإعدادات المركزي.
    مسؤول عن تحميل، حفظ، تشفير، وفك تشفير إعدادات التطبيق.
    يطبق نمط المراقب (Observer Pattern) لإبلاغ المكونات الأخرى بالتغييرات فورًا.
    """
    def __init__(self):
        if _instance is not None:
            raise Exception("This class is a singleton! Use get_settings_manager() instead.")

        self._observers = []
        self._encryption_key = self._load_or_create_key()
        self._cipher = Fernet(self._encryption_key)
        self.settings = self._load_settings()

    def register_observer(self, observer):
        """تسجيل مكون جديد (مثل ScannerEngine) ليتلقى تحديثات الإعدادات."""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.info(f"Observer registered: {observer.__class__.__name__}")

    def _notify_observers(self):
        """إبلاغ جميع المراقبين المسجلين بوجود تحديث في الإعدادات."""
        logger.info(f"Notifying {len(self._observers)} observers of settings update.")
        for observer in self._observers:
            if hasattr(observer, 'on_settings_updated'):
                try:
                    observer.on_settings_updated(self.settings)
                except Exception as e:
                    logger.error(f"Error notifying observer {observer.__class__.__name__}: {e}")

    def _load_or_create_key(self):
        """تحميل مفتاح التشفير أو إنشاء واحد جديد إذا لم يكن موجودًا."""
        if os.path.exists(APP_KEY_PATH):
            with open(APP_KEY_PATH, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(APP_KEY_PATH), exist_ok=True)
            with open(APP_KEY_PATH, "wb") as f:
                f.write(key)
            logger.info("New encryption key generated.")
            return key

    def _load_settings(self):
        """تحميل الإعدادات من ملف JSON وفك تشفير البيانات الحساسة."""
        if not os.path.exists(SETTINGS_FILE_PATH):
            logger.warning("Settings file not found. Loading default settings.")
            return self._get_default_settings()

        try:
            with open(SETTINGS_FILE_PATH, "r") as f:
                encrypted_settings = json.load(f)

            decrypted_settings = self._get_default_settings()

            for key, value in encrypted_settings.get("api_keys", {}).items():
                if value:
                    decrypted_settings["api_keys"][key] = self._cipher.decrypt(value.encode()).decode()

            decrypted_settings["networks"].update(encrypted_settings.get("networks", {}))
            decrypted_settings["scanner"].update(encrypted_settings.get("scanner", {}))
            decrypted_settings["strategies"].update(encrypted_settings.get("strategies", {}))

            logger.info("Settings loaded successfully.")
            return decrypted_settings
        except Exception as e:
            logger.error(f"Failed to load settings: {e}. Loading default settings.")
            return self._get_default_settings()

    def _get_default_settings(self):
        """إرجاع قاموس بالإعدادات الافتراضية."""
        return {
            "api_keys": {"alchemy": "", "telegram_token": "", "telegram_chat_id": ""},
            "networks": DEFAULT_NETWORKS,
            "scanner": {"min_balance": 1.0, "concurrency": 5000, "delay": 1},
            "strategies": DEFAULT_STRATEGIES
        }

    def save_settings(self):
        """تشفير وحفظ الإعدادات الحالية في ملف JSON، ثم إبلاغ المراقبين."""
        encrypted_settings = {
            "api_keys": {},
            "networks": self.settings.get("networks", DEFAULT_NETWORKS),
            "scanner": self.settings.get("scanner", {}),
            "strategies": self.settings.get("strategies", DEFAULT_STRATEGIES)
        }
        for key, value in self.settings.get("api_keys", {}).items():
            encrypted_settings["api_keys"][key] = self._cipher.encrypt(value.encode()).decode() if value else ""

        with open(SETTINGS_FILE_PATH, "w") as f:
            json.dump(encrypted_settings, f, indent=4)

        logger.info("Settings saved successfully to file.")
        self._notify_observers()

    def get(self, key, default=None):
        """الحصول على قيمة من الإعدادات باستخدام مفتاح متداخل (e.g., 'scanner.concurrency')."""
        try:
            keys = key.split('.')
            val = self.settings
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

    def set(self, key, value):
        """تعيين قيمة في الإعدادات باستخدام مفتاح متداخل."""
        keys = key.split('.')
        d = self.settings
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value