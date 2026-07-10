import json
import os
import time
from collections import Counter

import httpx

BASE_URL = "https://camp.sitcon.party"
QUESTIONS_FILE = "./questions.json"
POLL_INTERVAL_SECONDS = 0.3 
DEFAULT_RETRY_AFTER_SECONDS = 3.0
DEFAULT_COMPUTER_PLAYERS = 3
ROOM_PLAYER_LIMIT = 4

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
    opponents = [a for a in answers if a["playerId"] != host_player_id]
    opponent_text = " | ".join(format_answer(result, answer) for answer in opponents) or "no answer"

    print(f"[result] Q{result['questionId']} \"{result['prompt']}\" -> correct answer: {result.get('correctChoice')}")
    print(f"[result]   you: {format_answer(result, me)} | computers: {opponent_text}")
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


RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_RETRY_WAIT_SECONDS = 30.0


def request_with_retry(
    client: httpx.Client, method: str, url: str, allow_statuses: set[int] = frozenset(), **kwargs
) -> httpx.Response:
    attempt = 0
    while True:
        attempt += 1
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TransportError as error:
            wait_seconds = min(DEFAULT_RETRY_AFTER_SECONDS * attempt, MAX_RETRY_WAIT_SECONDS)
            print(f"[retry] {method} {url} failed ({error}), retrying in {wait_seconds:.1f}s")
            time.sleep(wait_seconds)
            continue

        if response.status_code == 429:
            wait_seconds = float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS))
            print(f"[429] rate limited on {method} {url}, retrying in {wait_seconds:.1f}s")
            time.sleep(wait_seconds)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            wait_seconds = min(DEFAULT_RETRY_AFTER_SECONDS * attempt, MAX_RETRY_WAIT_SECONDS)
            print(f"[{response.status_code}] server error on {method} {url}, retrying in {wait_seconds:.1f}s")
            time.sleep(wait_seconds)
            continue

        if response.status_code in allow_statuses:
            return response

        response.raise_for_status()
        return response


def find_open_match(client: httpx.Client) -> dict:
    return request_with_retry(client, "GET", f"{BASE_URL}/api/matches/open").json()


def load_desired_computer_players() -> int:
    value = os.environ.get("CAMP_COMPUTER_PLAYERS")
    if value is None:
        return DEFAULT_COMPUTER_PLAYERS

    try:
        count = int(value)
    except ValueError as error:
        raise SystemExit("CAMP_COMPUTER_PLAYERS must be an integer.") from error

    max_computer_players = ROOM_PLAYER_LIMIT - 1
    if count < 0 or count > max_computer_players:
        raise SystemExit(f"CAMP_COMPUTER_PLAYERS must be between 0 and {max_computer_players}.")
    return count


def create_room_match(client: httpx.Client) -> dict:
    response = request_with_retry(
        client, "POST", f"{BASE_URL}/api/matches/multiplayer/pairings", allow_statuses={409}
    )
    if response.status_code == 409:
        match = find_open_match(client)
        print(f"[match] resuming open match {match['matchId']} (status={match.get('status')})")
        return match

    data = response.json()
    match = data["match"]
    print(f"[match] created room {match['matchId']}")
    return match


def computer_player_count(match: dict) -> int:
    return sum(1 for player in match.get("players", []) if player.get("kind") == "computer")


def add_computer_players(client: httpx.Client, match: dict, desired_computer_players: int) -> dict:
    match_id = match["matchId"]
    while (
        match.get("status") == "waiting"
        and computer_player_count(match) < desired_computer_players
        and len(match.get("players", [])) < ROOM_PLAYER_LIMIT
    ):
        response = request_with_retry(
            client,
            "POST",
            f"{BASE_URL}/api/matches/{match_id}/computer-players",
            allow_statuses={400, 409},
        )
        if response.status_code in {400, 409}:
            print(f"[match] cannot add more computer players: {response.text.strip()}")
            return match

        match = response.json()
        print(
            f"[match] added computer player "
            f"({computer_player_count(match)}/{desired_computer_players})"
        )

    return match


def mark_host_ready(client: httpx.Client, match: dict) -> dict:
    if match.get("status") != "waiting":
        return match

    host_player_id = match["hostPlayerId"]
    host_player = next((p for p in match.get("players", []) if p["playerId"] == host_player_id), None)
    if host_player and host_player.get("ready"):
        return match

    match = request_with_retry(client, "POST", f"{BASE_URL}/api/matches/{match['matchId']}/ready").json()
    print(f"[match] host ready (status={match.get('status')})")
    return match


def play_match(client: httpx.Client, questions: dict, desired_computer_players: int) -> None:
    match = create_room_match(client)
    match = add_computer_players(client, match, desired_computer_players)
    match = mark_host_ready(client, match)

    match_id = match["matchId"]
    host_player_id = match["hostPlayerId"]

    match_started = match.get("status") not in (None, "waiting")
    answered_question_id = None
    reported_result_id = None
    while True:
        match = request_with_retry(client, "GET", f"{BASE_URL}/api/matches/{match_id}").json()

        if not match_started and match["status"] != "waiting":
            match_started = True
            print(f"[match] {match_id} started")

        result = match.get("currentQuestionResult")
        if result and result.get("questionId") != reported_result_id:
            report_result(host_player_id, result)
            log_question_result(questions, result)
            reported_result_id = result["questionId"]

        if match["status"] == "completed":
            report_match_completed(host_player_id, match)
            return

        if match_started:
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
    desired_computer_players = load_desired_computer_players()
    headers = {
        "Accept": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/battle/room",
    }
    cookies = {"camp2026_auth": auth_cookie}

    with httpx.Client(headers=headers, cookies=cookies, timeout=10.0) as client:
        while True:
            try:
                play_match(client, questions, desired_computer_players)
            except httpx.HTTPError as error:
                print(f"[error] {error}")
                time.sleep(DEFAULT_RETRY_AFTER_SECONDS)
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
