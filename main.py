import json
import os
from collections import Counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

QUESTIONS_FILE = "./questions.json"


def load_questions() -> dict:
    if not os.path.exists(QUESTIONS_FILE):
        return {}
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def save_questions(questions: dict) -> None:
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)


@app.get("/")
def read_root():
    return {"Hello": "World"}


LOGGED_FIELDS = [
    "questionId",
    "prompt",
    "choiceA",
    "choiceB",
    "choiceC",
    "choiceD",
    "correctChoice",
]


@app.post("/log")
def log(question: dict):
    question_id = question.get("questionId")
    questions = load_questions()

    if question_id in questions:
        return {"status": "exists", "questionId": question_id}

    questions[question_id] = {field: question.get(field) for field in LOGGED_FIELDS}
    save_questions(questions)
    return {"status": "logged", "questionId": question_id}


def most_common_choice(questions: dict) -> str | None:
    choices = [q["correctChoice"] for q in questions.values() if q.get("correctChoice")]
    if not choices:
        return None
    return Counter(choices).most_common(1)[0][0]


@app.get("/answer/{question_id}")
def answer(question_id: str):
    questions = load_questions()
    question = questions.get(question_id)
    correct_choice = question["correctChoice"] if question else None
    return {"answer": correct_choice or most_common_choice(questions)}



