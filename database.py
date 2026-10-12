
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "corocoro_eggs.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        # 音声認識結果の保存
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recognized_text TEXT NOT NULL,
                received_at TEXT NOT NULL
            )
        """)

        # ペットの状態の保存
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pet_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                stage INTEGER NOT NULL DEFAULT 0,
                hunger INTEGER NOT NULL DEFAULT 50,
                energy INTEGER NOT NULL DEFAULT 50,
                affection INTEGER NOT NULL DEFAULT 50,
                turns INTEGER NOT NULL DEFAULT 0,
                is_alive INTEGER NOT NULL DEFAULT 1,
                message TEXT NOT NULL DEFAULT 'たまごを温めて育てよう！'
            )
        """)

        # ペットの初期レコードを1件だけ作る
        conn.execute("""
            INSERT OR IGNORE INTO pet_state (id)
            VALUES (1)
        """)


def save_voice_text(text: str) -> int:
    received_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO voice_logs (recognized_text, received_at)
            VALUES (?, ?)
            """,
            (text, received_at),
        )
        return cursor.lastrowid


def get_voice_logs():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, recognized_text, received_at
            FROM voice_logs
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def get_pet_state():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT *
            FROM pet_state
            WHERE id = 1
        """).fetchone()

        return dict(row)


def save_pet_state(pet: dict):
    with get_connection() as conn:
        conn.execute("""
            UPDATE pet_state
            SET stage = ?,
                hunger = ?,
                energy = ?,
                affection = ?,
                turns = ?,
                is_alive = ?,
                message = ?
            WHERE id = 1
        """, (
            pet["stage"],
            pet["hunger"],
            pet["energy"],
            pet["affection"],
            pet["turns"],
            int(pet["isAlive"]),
            pet["message"],
        ))


def count_voice_logs() -> int:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS total
            FROM voice_logs
        """).fetchone()

        return row["total"]


def count_growth_words() -> int:
    # 部分一致ではなく、指定したキーワードが含まれる文章を数える
    keywords = (
        "お腹がすいた",
        "おなかがすいた",
        "ごはん",
        "遊びたい",
        "遊ぼう",
        "眠い",
        "寝たい",
        "ねむい",
        "ねたい",
    )

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT recognized_text
            FROM voice_logs
        """).fetchall()

        total = 0
        for row in rows:
            text = row["recognized_text"]
            if any(keyword in text for keyword in keywords):
                total += 1

        return total


def reset_pet_state():
    with get_connection() as conn:
        conn.execute("""
            UPDATE pet_state
            SET stage = 0,
                hunger = 50,
                energy = 50,
                affection = 50,
                turns = 0,
                is_alive = 1,
                message = 'たまごを温めて育てよう！'
            WHERE id = 1
        """)
