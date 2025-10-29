# services/ai_classifier.py (v2.3)

import os
from loguru import logger
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from config.app_config import MODEL_FILE_PATH
import sys

class AIClassifier:
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        if not os.path.exists(MODEL_FILE_PATH):
            logger.warning(f"Model file {MODEL_FILE_PATH} not found. Training a basic model.")
            self.train_and_save_basic_model()

        try:
            self.model = joblib.load(MODEL_FILE_PATH)
            logger.info("AI model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load AI model: {e}")

    def train_and_save_basic_model(self):
        try:
            X_train = np.random.rand(100, 4) * 1000
            y_train = np.random.randint(0, 3, 100)

            model = RandomForestClassifier(n_estimators=10, random_state=42)
            model.fit(X_train, y_train)

            joblib.dump(model, MODEL_FILE_PATH)
            self.model = model
            logger.info(f"Trained and saved a basic AI model to {MODEL_FILE_PATH}.")
        except Exception as e:
            logger.critical(f"Failed to train basic AI model: {e}")

    def classify(self, wallet_data: dict) -> str:
        if not self.model:
            return "AI Error"

        try:
            features_raw = [
                wallet_data.get("total_usdt", 0.0),
                wallet_data.get("num_tokens", 0.0),
                wallet_data.get("avg_token_value", 0.0),
                wallet_data.get("max_token_value", 0.0),
            ]

            sanitized_features = []
            for val in features_raw:
                if val is None or not np.isfinite(val) or val > np.finfo(np.float32).max:
                    sanitized_features.append(0.0)
                else:
                    sanitized_features.append(float(val))

            features = np.array(sanitized_features, dtype=np.float32).reshape(1, -1)

            prediction = self.model.predict(features)
            categories = ["Low Value", "Active", "VIP"]
            return categories[prediction[0]]
        except Exception as e:
            logger.error(f"Error during wallet classification for address {wallet_data.get('address')}: {e}")
            return "Classification Error"