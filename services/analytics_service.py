import sqlite3
from loguru import logger
from typing import Dict
from config.app_config import DB_PATH

class AnalyticsService:
    @staticmethod
    def get_strategy_performance() -> Dict[str, float]:
        """
        تحليل أداء كل استراتيجية بناءً على عدد النتائج النشطة التي حققتها.
        ترجع قاموسًا يحتوي على نسب مئوية لكل استراتيجية.
        """
        performance = {"random": 1, "sequential": 1, "wordlist": 1}
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT strategy, COUNT(*) FROM activity_hits GROUP BY strategy')
                rows = cursor.fetchall()
                for strategy, count in rows:
                    if strategy in performance:
                        performance[strategy] += count
                total_points = sum(performance.values())
                if total_points > 3:
                    for strategy in performance:
                        performance[strategy] = (performance[strategy] / total_points) * 100
                    logger.info(f"تم حساب أداء الاستراتيجيات: {performance}")
                    return performance
        except sqlite3.Error as e:
            logger.error(f"فشل تحليل أداء الاستراتيجيات: {e}")
        
        return {"random": 34, "sequential": 33, "wordlist": 33}
