import json
import os
import time
from collections import Counter

import httpx

BASE_URL = "https://camp.sitcon.party"
QUESTIONS_FILE = "./questions.json"
POLL_INTERVAL_SECONDS = 0.5
DEFAULT_RETRY_AFTER_SECONDS = 3.0

LOGGED_FIELDS = [
    "questionId",
    "prompt",
    "choiceA",
    "choiceB",
    "choiceC",
    "choiceD",
    "correctChoice",
]


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


def log_question_result(questions: dict, result: dict) -> None:
    question_id = result.get("questionId")
    if question_id is None or question_id in questions:
        return
    questions[question_id] = {field: result.get(field) for field in LOGGED_FIELDS}
    save_questions(questions)
    print(f"[log] learned answer for question {question_id}: {result.get('correctChoice')}")


def most_common_choice(questions: dict) -> str | None:
    choices = [q["correctChoice"] for q in questions.values() if q.get("correctChoice")]
    if not choices:
        return None
    return Counter(choices).most_common(1)[0][0]


def best_choice(questions: dict, question_id: str) -> str:
    known = questions.get(question_id)
    if known and known.get("correctChoice"):
        return known["correctChoice"]
    return most_common_choice(questions) or "A"


def format_answer(result: dict, answer: dict | None) -> str:
    if not answer:
        return "no answer"
    choice = answer.get("choice")
    choice_text = result.get(f"choice{choice}", "") if choice else "?"
    mark = "correct" if answer.get("correct") else "wrong"
    gained = answer.get("baseScore", 0) + answer.get("bonusScore", 0)
    return f"{choice} \"{choice_text}\" [{mark}, +{gained}]"


def report_result(host_player_id: str, result: dict) -> None:
    answers = result.get("answers", [])
    by_id = {a["playerId"]: a for a in answers}
    me = by_id.get(host_player_id)
    opponent = next((a for a in answers if a["playerId"] != host_player_id), None)

    print(f"[result] Q{result['questionId']} \"{result['prompt']}\" -> correct answer: {result.get('correctChoice')}")
    print(f"[result]   you: {format_answer(result, me)} | computer: {format_answer(result, opponent)}")
    if result.get("explanation"):
        print(f"[result]   explanation: {result['explanation']}")


def report_match_completed(host_player_id: str, match: dict) -> None:
    print(f"[match] completed {match['matchId']}")
    for player in match.get("players", []):
        label = "you" if player["playerId"] == host_player_id else player.get("nickname", player["playerId"])
        reward = player.get("openPowerReward", 0)
        drop = player.get("materialDrop")
        drop_text = "none"
        if drop and drop.get("dropped"):
            drop_text = f"{drop.get('sitoneName')} x{drop.get('quantity')}"
        print(f"[match]   {label}: score {player.get('score')} | reward {reward} | sitone drop: {drop_text}")


def request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    while True:
        response = client.request(method, url, **kwargs)
        if response.status_code == 429:
            wait_seconds = float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS))
            print(f"[429] rate limited on {method} {url}, retrying in {wait_seconds:.1f}s")
            time.sleep(wait_seconds)
            continue
        response.raise_for_status()
        return response


def play_match(client: httpx.Client, questions: dict) -> None:
    match = request_with_retry(client, "POST", f"{BASE_URL}/api/matches/computer").json()
    match_id = match["matchId"]
    host_player_id = match["hostPlayerId"]
    print(f"[match] created {match_id}")

    request_with_retry(client, "POST", f"{BASE_URL}/api/matches/{match_id}/ready")

    answered_question_id = None
    reported_result_id = None
    while True:
        match = request_with_retry(client, "GET", f"{BASE_URL}/api/matches/{match_id}").json()

        result = match.get("currentQuestionResult")
        if result and result.get("questionId") != reported_result_id:
            report_result(host_player_id, result)
            log_question_result(questions, result)
            reported_result_id = result["questionId"]

        if match["status"] == "completed":
            report_match_completed(host_player_id, match)
            return

        question = match.get("currentQuestion")
        if question and question["questionId"] != answered_question_id:
            choice = best_choice(questions, question["questionId"])
            print(f"[answer] question {question['questionId']} -> {choice}")
            request_with_retry(
                client,
                "POST",
                f"{BASE_URL}/api/matches/{match_id}/answers",
                json={"questionId": question["questionId"], "choice": choice},
            )
            answered_question_id = question["questionId"]

        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    auth_cookie = os.environ.get("CAMP_AUTH_COOKIE")
    if not auth_cookie:
        raise SystemExit(
            "Set CAMP_AUTH_COOKIE to the value of the camp2026_auth cookie "
            "(copy it from your browser's DevTools after logging in)."
        )

    questions = load_questions()
    headers = {
        "Accept": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/battle",
    }
    cookies = {"camp2026_auth": auth_cookie}

    with httpx.Client(headers=headers, cookies=cookies, timeout=10.0) as client:
        while True:
            try:
                play_match(client, questions)
            except httpx.HTTPStatusError as error:
                print(f"[error] {error}")
                time.sleep(DEFAULT_RETRY_AFTER_SECONDS)
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
