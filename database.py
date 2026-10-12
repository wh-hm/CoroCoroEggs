import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "corocoro_eggs.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        # 音声認識結果の保存
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recognized_text TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'normal',
                received_at TEXT NOT NULL,
                delete_flag INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 既存のvoice_logsに不足カラムを追加
        voice_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(voice_logs)"
            ).fetchall()
        }

        if "category" not in voice_columns:
            conn.execute("""
                ALTER TABLE voice_logs
                ADD COLUMN category TEXT NOT NULL DEFAULT 'normal'
            """)
        
        if "delete_flag" not in voice_columns:
            conn.execute("""
                ALTER TABLE voice_logs
                ADD COLUMN delete_flag INTEGER NOT NULL DEFAULT 0
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
                message TEXT NOT NULL DEFAULT 'たまごを温めて育てよう！',

                rock_points INTEGER NOT NULL DEFAULT 0,
                cute_points INTEGER NOT NULL DEFAULT 0,
                narcissist_points INTEGER NOT NULL DEFAULT 0,
                neet_points INTEGER NOT NULL DEFAULT 0,
                normal_points INTEGER NOT NULL DEFAULT 0,

                insult_points INTEGER NOT NULL DEFAULT 0,
                heart INTEGER NOT NULL DEFAULT 100,
                personality TEXT NOT NULL DEFAULT 'normal',
                hatched_at TEXT
            )
        """)

        # 既存のpet_stateに不足カラムを追加
        pet_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(pet_state)"
            ).fetchall()
        }

        new_columns = {
            "rock_points": "INTEGER NOT NULL DEFAULT 0",
            "cute_points": "INTEGER NOT NULL DEFAULT 0",
            "narcissist_points": "INTEGER NOT NULL DEFAULT 0",
            "neet_points": "INTEGER NOT NULL DEFAULT 0",
            "normal_points": "INTEGER NOT NULL DEFAULT 0",
            "insult_points": "INTEGER NOT NULL DEFAULT 0",
            "heart": "INTEGER NOT NULL DEFAULT 100",
            "personality": "TEXT NOT NULL DEFAULT 'normal'",
            "hatched_at": "TEXT",
        }

        for column_name, column_type in new_columns.items():
            if column_name not in pet_columns:
                conn.execute(
                    f"ALTER TABLE pet_state ADD COLUMN "
                    f"{column_name} {column_type}"
                )

        # 発言ごとの分析結果を保存
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice_log_id INTEGER NOT NULL,
                word_category TEXT NOT NULL DEFAULT 'normal',
                ending_category TEXT NOT NULL DEFAULT 'normal',
                emotion_category TEXT NOT NULL DEFAULT 'neutral',
                insult_level INTEGER NOT NULL DEFAULT 0,
                kindness_score INTEGER NOT NULL DEFAULT 0,
                analyzed_at TEXT NOT NULL,
                FOREIGN KEY (voice_log_id)
                    REFERENCES voice_logs(id)
                    ON DELETE CASCADE
            )
        """)

        # ペットの初期レコードを1件だけ作る
        conn.execute("""
            INSERT OR IGNORE INTO pet_state (id)
            VALUES (1)
        """)


def save_voice_text(recognized_text: str, category: str = "normal") -> int:
    received_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO voice_logs (
                recognized_text,
                category,
                received_at,
                delete_flag
            )
            VALUES (?, ?, ?, ?)
            """,
            (recognized_text, category, received_at, 0),
        )

        return cursor.lastrowid


def get_voice_logs():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                id,
                recognized_text,
                category,
                received_at,
                delete_flag
            FROM voice_logs
            ORDER BY id ASC
        """).fetchall()

        return [dict(row) for row in rows]


def save_voice_analysis(
    voice_log_id: int,
    word_category: str = "normal",
    ending_category: str = "normal",
    emotion_category: str = "neutral",
    insult_level: int = 0,
    kindness_score: int = 0,
):
    analyzed_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO voice_analysis (
                voice_log_id,
                word_category,
                ending_category,
                emotion_category,
                insult_level,
                kindness_score,
                analyzed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                voice_log_id,
                word_category,
                ending_category,
                emotion_category,
                insult_level,
                kindness_score,
                analyzed_at,
            ),
        )


def get_voice_analysis():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                id,
                voice_log_id,
                word_category,
                ending_category,
                emotion_category,
                insult_level,
                kindness_score,
                analyzed_at
            FROM voice_analysis
            ORDER BY id ASC
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
                message = ?,
                rock_points = ?,
                cute_points = ?,
                narcissist_points = ?,
                neet_points = ?,
                normal_points = ?,
                insult_points = ?,
                heart = ?,
                personality = ?,
                hatched_at = ?
            WHERE id = 1
        """, (
            pet["stage"],
            pet["hunger"],
            pet["energy"],
            pet["affection"],
            pet["turns"],
            int(pet["isAlive"]),
            pet["message"],
            pet.get("rock_points", 0),
            pet.get("cute_points", 0),
            pet.get("narcissist_points", 0),
            pet.get("neet_points", 0),
            pet.get("normal_points", 0),
            pet.get("insult_points", 0),
            pet.get("heart", 100),
            pet.get("personality", "normal"),
            pet.get("hatched_at"),
        ))


def count_voice_logs() -> int:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS total
            FROM voice_logs
        """).fetchone()

        return row["total"]


def count_growth_words() -> int:
    # 指定したキーワードが含まれる発言を数える
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
                message = 'たまごを温めて育てよう！',
                rock_points = 0,
                cute_points = 0,
                narcissist_points = 0,
                neet_points = 0,
                normal_points = 0,
                insult_points = 0,
                heart = 100,
                personality = 'normal',
                hatched_at = NULL
            WHERE id = 1
        """)