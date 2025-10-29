import json
import os
from loguru import logger
from cryptography.fernet import Fernet
from .app_config import SETTINGS_FILE_PATH, APP_KEY_PATH, DEFAULT_NETWORKS, DEFAULT_STRATEGIES

class SettingsManager:
    def __init__(self):
        self._encryption_key = self._load_or_create_key()
        self._cipher = Fernet(self._encryption_key)
        self.settings = self._load_settings()

    def _load_or_create_key(self):
        if os.path.exists(APP_KEY_PATH):
            with open(APP_KEY_PATH, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(APP_KEY_PATH, "wb") as f:
                f.write(key)
            return key

    def _load_settings(self):
        if not os.path.exists(SETTINGS_FILE_PATH):
            return self._get_default_settings()

        try:
            with open(SETTINGS_FILE_PATH, "r") as f:
                encrypted_settings = json.load(f)

            decrypted_settings = self._get_default_settings()
            # فك تشفير مفاتيح API
            for key, value in encrypted_settings.get("api_keys", {}).items():
                if value:
                    decrypted_settings["api_keys"][key] = self._cipher.decrypt(value.encode()).decode()

            # دمج الإعدادات الأخرى
            decrypted_settings["networks"].update(encrypted_settings.get("networks", {}))
            decrypted_settings["scanner"].update(encrypted_settings.get("scanner", {}))
            decrypted_settings["strategies"].update(encrypted_settings.get("strategies", {}))

            return decrypted_settings
        except Exception as e:
            logger.error(f"فشل تحميل الإعدادات: {e}. سيتم استخدام الإعدادات الافتراضية.")
            return self._get_default_settings()

    def _get_default_settings(self):
        return {
            "api_keys": {"alchemy": "", "telegram_token": "", "telegram_chat_id": ""},
            "networks": DEFAULT_NETWORKS,
            "scanner": {"min_balance": 1.0, "concurrency": 5000, "delay": 1},
            "strategies": DEFAULT_STRATEGIES
        }

    def save_settings(self):
        encrypted_settings = {
            "api_keys": {},
            "networks": self.settings.get("networks", DEFAULT_NETWORKS),
            "scanner": self.settings.get("scanner", {}),
            "strategies": self.settings.get("strategies", DEFAULT_STRATEGIES)
        }
        for key, value in self.settings.get("api_keys", {}).items():
            if value:
                encrypted_settings["api_keys"][key] = self._cipher.encrypt(value.encode()).decode()
            else:
                encrypted_settings["api_keys"][key] = ""

        with open(SETTINGS_FILE_PATH, "w") as f:
            json.dump(encrypted_settings, f, indent=4)
        logger.info("تم حفظ الإعدادات بنجاح.")

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val

    def set(self, key, value):
        keys = key.split('.')
        d = self.settings
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value