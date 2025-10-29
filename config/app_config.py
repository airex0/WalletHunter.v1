APP_NAME = "WalletHunter Elite"
APP_VERSION = "1.0.0"

# مسارات الملفات والبيانات
DATA_DIR = "data"
DB_PATH = f"{DATA_DIR}/hunter.db"
SETTINGS_FILE_PATH = f"{DATA_DIR}/settings.json"
MODEL_FILE_PATH = f"{DATA_DIR}/ai_model.joblib"
LOG_FILE_PATH = "logs/app.log"
APP_KEY_PATH = f"{DATA_DIR}/app.key"
WORDLISTS_DIR = f"{DATA_DIR}/wordlists"

# إعدادات الشبكات الافتراضية
DEFAULT_NETWORKS = {
    "Ethereum": {"enabled": True, "rpc_placeholder": "https://eth-mainnet.g.alchemy.com/v2/{api_key}"},
    "Polygon": {"enabled": True, "rpc_placeholder": "https://polygon-mainnet.g.alchemy.com/v2/{api_key}"},
    "Arbitrum": {"enabled": False, "rpc_placeholder": "https://arb-mainnet.g.alchemy.com/v2/{api_key}"},
    "Optimism": {"enabled": False, "rpc_placeholder": "https://opt-mainnet.g.alchemy.com/v2/{api_key}"},
    "BSC": {"enabled": False, "rpc_placeholder": "https://bsc-dataseed.binance.org/"}
}

# إعدادات الاستراتيجيات الافتراضية
DEFAULT_STRATEGIES = {
    "allocations": {"random": 80, "sequential": 10, "wordlist": 10},
    "sequential": {"enabled": True, "current_pos": 1},
    "wordlist": {"enabled": True, "files": {}}
}