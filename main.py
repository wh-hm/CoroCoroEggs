from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import random

from database import (
    init_db,
    save_voice_text,
    get_voice_logs,
    get_pet_state,
    save_pet_state,
    count_voice_logs,
    count_growth_words,
    soft_delete_all_data,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ColoColoEggs API",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (BASE_DIR / "images").is_dir():
    app.mount(
        "/images",
        StaticFiles(directory=BASE_DIR / "images"),
        name="images",
    )


class CategoryScore(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    score: int = Field(default=1, ge=1)


class VoiceData(BaseModel):
    recognized_text: str = Field(min_length=1, max_length=5000)
    categories: list[CategoryScore] = Field(default_factory=list)


class PetState(BaseModel):
    stage: int = 1
    hunger: int = 50
    energy: int = 50
    affection: int = 50
    turns: int = 0
    isAlive: bool = True
    message: str = "たまごを温めて育てよう！"
    is_evolved: int = 0
    evolved_category: str | None = None


@app.get("/")
def read_root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/pet/init")
def init_pet():
    soft_delete_all_data()
    return get_pet_state_for_api()


@app.get("/list")
def read_list():
    return FileResponse(BASE_DIR / "list.html")


def get_pet_state_for_api():
    pet = get_pet_state()
    pet["isAlive"] = bool(pet.pop("is_alive", 1))
    return pet


def process_turn(pet: dict, manual: bool = False) -> dict:
    if not pet["isAlive"]:
        return pet

    pet["turns"] += 1
    pet["hunger"] = max(0, pet["hunger"] - 10)

    if manual:
        pet["message"] = "時間を過ごしました。"

    if pet["hunger"] <= 0:
        pet["energy"] = max(0, pet["energy"] - 20)

    if pet["energy"] <= 0:
        pet["isAlive"] = False
        pet["message"] = "力尽きてしまいました…"

    return pet


@app.post("/api/pet/feed")
def feed_pet(pet: PetState):
    state = pet.model_dump()
    if not state["isAlive"]:
        return state

    state["hunger"] = min(100, state["hunger"] + 30)
    state["energy"] = min(100, state["energy"] + 5)
    state["message"] = "ごはんを食べてお腹がいっぱい！"

    state = process_turn(state)
    save_pet_state(state)
    return state


@app.post("/api/pet/play")
def play_pet(pet: PetState):
    state = pet.model_dump()
    if not state["isAlive"]:
        return state

    if state["energy"] < 20:
        state["message"] = "疲れていて遊べそうにありません…"
        return state

    state["affection"] = min(100, state["affection"] + 15)
    state["hunger"] = max(0, state["hunger"] - 15)
    state["energy"] = max(0, state["energy"] - 20)
    state["message"] = "元気に遊んで満足そうです！"

    state = process_turn(state)
    save_pet_state(state)
    return state


@app.post("/api/pet/sleep")
def sleep_pet(pet: PetState):
    state = pet.model_dump()
    if not state["isAlive"]:
        return state

    state["energy"] = min(100, state["energy"] + 40)
    state["hunger"] = max(0, state["hunger"] - 10)
    state["message"] = "ぐっすり眠って体力が回復しました！"

    state = process_turn(state)
    save_pet_state(state)
    return state


@app.post("/api/pet/pass_time")
def pass_time_api(pet: PetState):
    state = pet.model_dump()
    if not state["isAlive"]:
        return state

    state = process_turn(state, manual=True)
    save_pet_state(state)
    return state


@app.post("/api/voice")
def receive_voice(data: VoiceData):
    recognized_text = data.recognized_text.strip()
    if not recognized_text:
        raise HTTPException(
            status_code=400,
            detail="音声認識結果が空です。",
        )

    current_pet = get_pet_state()

    # 死亡フラグ確認
    if int(current_pet.get("is_alive", 1)) == 0:
        pet_api = get_pet_state_for_api()
        return {
            "message": "たまごはすでに心を閉ざしています…。",
            "pet": pet_api,
        }

    current_stage = int(current_pet.get("stage", 1))

    categories_data = []
    for c in data.categories:
        categories_data.append({"name": c.name.strip(), "score": int(c.score)})

    # 1. ログをDBに保存
    log_id = save_voice_text(recognized_text, categories_data, current_step=current_stage)

    # 2. 悪口・謝罪ポイント計算
    insult_points = int(current_pet.get("insult_points", 0))
    point_message_addon = ""

    for c in categories_data:
        c_name = c["name"].lower()
        c_score = c["score"]
        if c_name == "insult":
            insult_points += c_score * 5
            point_message_addon = "（悪口を言われて怯えている…）"
        elif c_name == "apology":
            insult_points -= 15
            if insult_points < 0:
                insult_points = 0
            point_message_addon = "（素直に謝罪を受け入れたようだ）"

    current_pet["insult_points"] = insult_points

    # 3. 集計処理（現在のステップでの累積スコア計算）
    total_logs = count_voice_logs()
    growth_words = count_growth_words()

    main_category = (current_pet.get("evolved_category") or "").lower().strip()

    updated_logs = get_voice_logs()
    counts = {
        "cute": 0,
        "normal": 0,
        "rock": 0,
        "narcissist": 0,
        "neet": 0,
    }

    for log in updated_logs:
        # 論理削除されているログは除外
        if int(log.get("delete_flag", 0)) == 1 or int(log.get("is_deleted", 0)) == 1:
            continue

        log_step = int(log.get("current_step") or log.get("step") or 1)

        for cat in log.get("categories", []):
            cat_step = int(cat.get("step") or log_step)

            # 現在のステップのログのみ集計
            if cat_step == current_stage:
                c_name = cat.get("category_name", "").lower().strip()
                raw_score = int(cat.get("score", 1))

                multiplier = 2 if (current_stage >= 2 and main_category and c_name == main_category) else 1
                effective_score = raw_score * multiplier

                if c_name in counts:
                    counts[c_name] += effective_score

    # 100ポイント判定
    exceeded = {k: v for k, v in counts.items() if v >= 100}
    evolved_this_turn = False

    if exceeded:
        if current_stage >= 6:
            current_pet["message"] = "最高ステップ（ステージ6）に到達しています！"
        else:
            max_val = max(exceeded.values())
            top_categories = [k for k, v in exceeded.items() if v == max_val]
            chosen_category = random.choice(top_categories)

            current_pet["stage"] = current_stage + 1
            current_pet["evolved_category"] = chosen_category
            current_pet["is_evolved"] = 1
            evolved_this_turn = True
            current_pet["message"] = f"おめでとう！{chosen_category}の力が極まり、ステップ {current_pet['stage']} に進化したよ！"
    else:
        if point_message_addon:
            current_pet["message"] = f"音声を記録したよ！ {point_message_addon} (悪口P: {insult_points}/100)"
        else:
            current_pet["message"] = f"音声を記録したよ！（保存件数：{total_logs}件）"

    # 4. 悪口100pt以上でゲームオーバー判定
    if insult_points >= 100:
        current_pet["is_alive"] = 0
        current_pet["message"] = "悪口を言いすぎたせいで、たまごが完全に心を閉ざしてしまった……（ゲームオーバー）"

        # ステップ1→2への進化とゲームオーバーが同じ音声処理で発生した場合、
        # カテゴリーを空にしてDBへ保存する。フロント側はこれを見て other_gameover.png を表示する。
        # これによりページ再読み込み後も同じ画像判定を維持できる。
        if evolved_this_turn and current_stage == 1 and int(current_pet.get("stage", 1)) == 2:
            current_pet["evolved_category"] = None

    # DBに状態保存
    save_pet_state(current_pet)
    updated_pet_api = get_pet_state_for_api()

    return {
        "message": current_pet["message"],
        "id": log_id,
        "recognized_text": recognized_text,
        "categories": categories_data,
        "total_logs": total_logs,
        "growth_words": growth_words,
        "stage": updated_pet_api["stage"],
        "pet": updated_pet_api,
    }


@app.get("/api/voice/logs")
def read_voice_logs():
    return get_voice_logs()


@app.get("/api/pet/state")
def read_pet_state():
    pet = get_pet_state_for_api()
    pet["total_logs"] = count_voice_logs()
    pet["growth_words"] = count_growth_words()
    return pet
