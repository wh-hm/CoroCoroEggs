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
        # 1. 親テーブル：音声認識結果の保存 (delete_flag を保持)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recognized_text TEXT NOT NULL,
                received_at TEXT NOT NULL,
                delete_flag INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 2. 子テーブル：複数のカテゴリーやポイント (親の削除状態や自身でも delete_flag を持つ)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice_log_id INTEGER NOT NULL,
                category_name TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 1,
                step INTEGER NOT NULL DEFAULT 1,
                delete_flag INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (voice_log_id)
                    REFERENCES voice_logs(id)
                    ON DELETE CASCADE
            )
        """)

        # 3. 子テーブル：詳細な分析結果 (同じく delete_flag を持ち、親と連動)
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
                delete_flag INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (voice_log_id)
                    REFERENCES voice_logs(id)
                    ON DELETE CASCADE
            )
        """)

        # 4. ペットの状態保存テーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pet_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                stage INTEGER NOT NULL DEFAULT 1,
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
                hatched_at TEXT,

                is_evolved INTEGER NOT NULL DEFAULT 0,
                evolved_category TEXT
            )
        """)

        # ペットの初期レコードを1件だけ作成
        conn.execute("""
            INSERT OR IGNORE INTO pet_state (id, stage, is_evolved)
            VALUES (1, 1, 0)
        """)


def save_voice_text(recognized_text: str, categories: list = None, current_step: int = 1) -> int:
    if categories is None:
        categories = [{'name': 'normal', 'score': 1}]

    received_at = datetime.now().astimezone().isoformat(timespec="seconds")
    analyzed_at = received_at

    with get_connection() as conn:
        # 1. 親ログの保存
        cursor = conn.execute(
            """
            INSERT INTO voice_logs (recognized_text, received_at, delete_flag)
            VALUES (?, ?, ?)
            """,
            (recognized_text, received_at, 0),
        )
        log_id = cursor.lastrowid

        # 2. カテゴリー情報の保存（delete_flag = 0 で初期化）
        for cat in categories:
            conn.execute(
                """
                INSERT INTO voice_categories (voice_log_id, category_name, score, step, delete_flag)
                VALUES (?, ?, ?, ?, ?)
                """,
                (log_id, cat.get('name', 'normal'), cat.get('score', 1), current_step, 0)
            )

        # 3. 分析結果の初期保存（リレーションに紐づけて delete_flag = 0 で初期化）
        conn.execute(
            """
            INSERT INTO voice_analysis (voice_log_id, word_category, ending_category, emotion_category, insult_level, kindness_score, analyzed_at, delete_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, 'normal', 'normal', 'neutral', 0, 0, analyzed_at, 0)
        )

    # 4. 受信したカテゴリーに基づいてペットの状態（ポイント等）を更新
    update_pet_points_by_categories(categories)

    return log_id


def update_pet_points_by_categories(categories: list):
    """
    受信したカテゴリーに応じて pet_state の各ポイントやゲームオーバー状態を更新する
    """
    pet = get_pet_state()
    
    # 既にゲームオーバー（死亡）している場合はポイント変動を無視
    if pet.get("is_alive", 1) == 0:
        return pet

    insult_points = pet.get("insult_points", 0)
    cute_points = pet.get("cute_points", 0)
    rock_points = pet.get("rock_points", 0)
    neet_points = pet.get("neet_points", 0)
    narcissist_points = pet.get("narcissist_points", 0)
    normal_points = pet.get("normal_points", 0)

    for cat in categories:
        name = cat.get("name")
        score = cat.get("score", 1)

        if name == "insult":
            # 悪口ポイント加算（1回につき5〜10ポイント想定、score倍）
            insult_points += score * 10
        elif name == "apology":
            # 【救済措置】謝罪されたら悪口ポイントを減少（0未満にはしない）
            insult_points -= 15
            if insult_points < 0:
                insult_points = 0
        elif name == "cute":
            cute_points += score
        elif name == "rock":
            rock_points += score
        elif name == "narcissist":
            narcissist_points += score
        elif name == "neet":
            neet_points += score
        elif name == "normal":
            normal_points += score

    # 100ポイントを超えたらゲームオーバー（is_alive = 0）とする判定
    if insult_points >= 100:
        pet["is_alive"] = 0
        pet["message"] = "悪口を言いすぎたせいで、たまごが完全に心を閉ざしてしまった……（ゲームオーバー）"
    else:
        if insult_points > 0:
            pet["message"] = f"たまごが不機嫌そうに揺れている……（悪口ポイント: {insult_points}）"
        else:
            pet["message"] = "たまごは機嫌よく温まっている。"

    # 更新された数値をペットの状態辞書に反映
    pet["insult_points"] = insult_points
    pet["cute_points"] = cute_points
    pet["rock_points"] = rock_points
    pet["narcissist_points"] = narcissist_points
    pet["neet_points"] = neet_points
    pet["normal_points"] = normal_points

    save_pet_state(pet)
    return pet


def get_voice_logs():
    """
    音声ログと、それに紐付くすべてのカテゴリーをまとめて取得する（すべてのテーブルで delete_flag = 0 のものだけ）
    """
    with get_connection() as conn:
        logs_rows = conn.execute("""
            SELECT id, recognized_text, received_at, delete_flag
            FROM voice_logs
            WHERE delete_flag = 0
            ORDER BY id ASC
        """).fetchall()

        logs = []
        for row in logs_rows:
            log_dict = dict(row)
            
            cat_rows = conn.execute("""
                SELECT category_name, score, step
                FROM voice_categories
                WHERE voice_log_id = ? AND delete_flag = 0
            """, (log_dict['id'],)).fetchall()
            
            log_dict['categories'] = [dict(c) for c in cat_rows]
            logs.append(log_dict)

        return logs


def get_pet_state():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM pet_state WHERE id = 1").fetchone()
        return dict(row)


def save_pet_state(pet: dict):
    with get_connection() as conn:
        conn.execute("""
            UPDATE pet_state
            SET stage = ?, hunger = ?, energy = ?, affection = ?, turns = ?,
                is_alive = ?, message = ?, rock_points = ?, cute_points = ?,
                narcissist_points = ?, neet_points = ?, normal_points = ?,
                insult_points = ?, heart = ?, personality = ?, hatched_at = ?,
                is_evolved = ?, evolved_category = ?
            WHERE id = 1
        """, (
            pet["stage"], pet["hunger"], pet["energy"], pet["affection"],
            pet["turns"], int(pet["is_alive"]), pet["message"],
            pet.get("rock_points", 0), pet.get("cute_points", 0),
            pet.get("narcissist_points", 0), pet.get("neet_points", 0),
            pet.get("normal_points", 0), pet.get("insult_points", 0),
            pet.get("heart", 100), pet.get("personality", "normal"),
            pet.get("hatched_at"),
            pet.get("is_evolved", 0), pet.get("evolved_category"),
        ))


def count_voice_logs() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM voice_logs WHERE delete_flag = 0").fetchone()
        return row["total"]


def count_growth_words() -> int:
    keywords = ("お腹がすいた", "おなかがすいた", "ごはん", "遊びたい", "遊ぼう", "眠い", "寝たい", "ねむい", "ねたい")
    with get_connection() as conn:
        rows = conn.execute("SELECT recognized_text FROM voice_logs WHERE delete_flag = 0").fetchall()
        total = 0
        for row in rows:
            if any(keyword in row["recognized_text"] for keyword in keywords):
                total += 1
        return total


def soft_delete_all_data():
    """ 
    リレーションを考慮し、すべての関連テーブル（voice_logs, voice_categories, voice_analysis）
    の delete_flag を一斉に 1 に更新（論理削除）し、ペットの状態を初期状態にリセットする 
    """
    with get_connection() as conn:
        # 親テーブルの論理削除
        conn.execute("UPDATE voice_logs SET delete_flag = 1")
        
        # 紐づく子テーブル（voice_categories）の論理削除（親のIDやリレーションに連動）
        conn.execute("UPDATE voice_categories SET delete_flag = 1")
        
        # 紐づく子テーブル（voice_analysis）の論理削除
        conn.execute("UPDATE voice_analysis SET delete_flag = 1")

        # ペットの状態初期化
        conn.execute("""
            UPDATE pet_state
            SET stage = 1, hunger = 50, energy = 50, affection = 50, turns = 0,
                is_alive = 1, message = 'たまごを温めて育てよう！',
                rock_points = 0, cute_points = 0, narcissist_points = 0,
                neet_points = 0, normal_points = 0, insult_points = 0,
                heart = 100, personality = 'normal', hatched_at = NULL,
                is_evolved = 0, evolved_category = NULL
            WHERE id = 1
        """)


def reset_pet_state():
    soft_delete_all_data()