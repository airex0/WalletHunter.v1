import sqlite3
import logging
from typing import List, Dict, Any
from config.app_config import DB_PATH
import os
import asyncio

def initialize_database():
    """إنشاء الجداول اللازمة في قاعدة البيانات إذا لم تكن موجودة."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # جدول لتخزين النتائج الإيجابية (محافظ لها رصيد)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS found_wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    private_key TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    total_usdt REAL NOT NULL,
                    ai_score TEXT,
                    strategy TEXT,
                    discovery_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # جدول لتخزين المحافظ التي أظهرت نشاطًا (حتى لو فارغة)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    tx_count INTEGER NOT NULL,
                    strategy TEXT NOT NULL,
                    source TEXT, -- الكلمة أو الرقم الذي أدى للنتيجة
                    discovery_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logging.info("تم تهيئة قاعدة البيانات بنجاح.")
    except sqlite3.Error as e:
        logging.critical(f"خطأ فادح في تهيئة قاعدة البيانات: {e}")
        raise

def db_writer(queue: asyncio.Queue):
    """دالة تعمل في خيط منفصل لكتابة البيانات في قاعدة البيانات بشكل غير متزامن."""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cursor = conn.cursor()

            # انتظار وصول البيانات إلى الطابور
            table, data = queue.get()

            if table == 'found_wallets':
                cursor.execute('''
                    INSERT OR IGNORE INTO found_wallets (address, private_key, chain, total_usdt, ai_score, strategy)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data['address'], data['private_key'], data['chain'], data['total_usdt'], data['ai_score'], data['strategy']))

            elif table == 'activity_hits':
                cursor.execute('''
                    INSERT OR IGNORE INTO activity_hits (address, tx_count, strategy, source)
                    VALUES (?, ?, ?, ?)
                ''', (data['address'], data['tx_count'], data['strategy'], data.get('source')))

            conn.commit()
            queue.task_done()
        except sqlite3.Error as e:
            logging.error(f"فشل في كتابة البيانات إلى قاعدة البيانات: {e}")
        except Exception as e:
            logging.error(f"خطأ غير متوقع في كاتب قاعدة البيانات: {e}")
        finally:
            if conn:
                conn.close()