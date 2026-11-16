import sqlite3
from datetime import datetime

DB_NAME = "audit_history.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_name TEXT,
                cold_mops REAL,
                hot_mops REAL,
                drop_percent REAL,
                score INTEGER
            )
            """
        )


def save_test_result(diag: dict, bench: dict):
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            INSERT INTO test_history (timestamp, cpu_name, cold_mops, hot_mops, drop_percent, score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                diag["cpu_name"],
                bench["cold_mops"],
                bench["hot_mops"],
                bench["drop_percent"],
                diag["score"],
            ),
        )


def get_all_history() -> list:
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute(
            """
            SELECT timestamp, cpu_name, cold_mops, hot_mops, drop_percent, score
            FROM test_history
            ORDER BY id DESC
            LIMIT 20
            """
        )
        return cursor.fetchall()