
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database import (
    init_db,
    save_voice_text,
    get_voice_logs,
    get_pet_state,
    save_pet_state,
    count_voice_logs,
    count_growth_words,
    reset_pet_state,
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

# 画像フォルダを配信する
# images フォルダが存在する場合に利用する
if (BASE_DIR / "images").is_dir():
    app.mount(
        "/images",
        StaticFiles(directory=BASE_DIR / "images"),
        name="images",
    )


class VoiceData(BaseModel):
    recognized_text: str = Field(min_length=1, max_length=5000)
    category: str = Field(min_length=1, max_length=50)


class PetState(BaseModel):
    stage: int = 0
    hunger: int = 50
    energy: int = 50
    affection: int = 50
    turns: int = 0
    isAlive: bool = True
    message: str = "たまごを温めて育てよう！"


@app.get("/")
def read_root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/pet/init")
def init_pet():
    # ペットを初期状態に戻す
    reset_pet_state()
    return get_pet_state_for_api()


@app.get("/list")
def read_list():
    return FileResponse(BASE_DIR / "list.html")


def get_pet_state_for_api():
    pet = get_pet_state()
    pet["isAlive"] = bool(pet.pop("is_alive"))
    return pet


def process_turn(pet: dict, manual: bool = False) -> dict:
    if not pet["isAlive"]:
        return pet

    pet["turns"] += 1
    pet["hunger"] = max(0, pet["hunger"] - 10)

    if pet["stage"] == 0 and pet["turns"] >= 2:
        pet["stage"] = 1
        pet["message"] = "たまごから赤ちゃんが生まれました！"
    elif pet["stage"] == 1 and pet["turns"] >= 8:
        pet["stage"] = 2
        pet["message"] = "ペットが大人の姿に進化しました！"
    elif manual:
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
    category = data.category.strip()

    if not recognized_text:
        raise HTTPException(
            status_code=400,
            detail="音声認識結果が空です。",
        )

    if not category:
        raise HTTPException(
            status_code=400,
            detail="音声認識カテゴリー結果が空です。",
        )

    # ① 音声認識結果をDBへ保存
    log_id = save_voice_text(recognized_text, category)

    # ② 保存後に成長条件を判定
    total_logs = count_voice_logs()
    growth_words = count_growth_words()

    pet = get_pet_state_for_api()
    old_stage = pet["stage"]

    # ③ 件数と文章内容の両方を満たしたら成長
    if total_logs >= 5 and growth_words >= 1:
        pet["stage"] = max(pet["stage"], 1)

    if total_logs >= 15 and growth_words >= 3:
        pet["stage"] = max(pet["stage"], 2)

    if pet["stage"] > old_stage:
        if pet["stage"] == 1:
            pet["message"] = "音声の記録がたまって、赤ちゃんに成長したよ！"
        elif pet["stage"] == 2:
            pet["message"] = "たくさん記録したね！大人に成長したよ！"
    else:
        pet["message"] = (
            f"音声を記録したよ！（保存件数：{total_logs}件）"
        )

    # ④ 成長後の状態をDBへ保存
    save_pet_state(pet)

    return {
        "message": pet["message"],
        "id": log_id,
        "recognized_text": recognized_text,
        "category": category,
        "total_logs": total_logs,
        "growth_words": growth_words,
        "stage": pet["stage"],
        "pet": pet,
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
