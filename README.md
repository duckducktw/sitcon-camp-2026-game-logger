# sitcon-2026-questions

A standalone bot for the SITCON 2026 "battle" live quiz. It talks to the
quiz API directly over HTTP — no browser required — playing matches,
answering with the best-known choice, and learning correct answers as they
are revealed.

## How it works

**[main.py](main.py)** drives the whole game loop against
`https://camp.sitcon.party`:

1. Creates a match against the computer opponent
   (`POST /api/matches/computer`) and marks itself ready
   (`POST /api/matches/{id}/ready`).
2. Polls the match (`GET /api/matches/{id}`) once a second.
   - When a `currentQuestion` appears that hasn't been answered yet, it picks
     the best-known choice from `questions.json` (falling back to the most
     common correct choice seen so far) and submits it
     (`POST /api/matches/{id}/answers`).
   - When a `currentQuestionResult` reveals the correct answer for a
     question not yet recorded, it's saved to `questions.json` for next
     time.
3. When the match's `status` becomes `completed`, it immediately starts a
   new match and repeats, forever (stop it with Ctrl+C).

Any request that gets rate-limited (HTTP 429) is retried automatically,
honoring the `Retry-After` header when present.

## Requirements

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) (dependency management, per `pyproject.toml` / `uv.lock`)

## Setup

```bash
uv sync
```

## Running the bot

You need the value of the `camp2026_auth` cookie from a logged-in browser
session (DevTools → Application/Storage → Cookies).

```bash
CAMP_AUTH_COOKIE=<your camp2026_auth cookie value> uv run main.py
```

The bot will keep playing matches until you stop it.

## Legacy browser script

**[log.js](log.js)** is an older approach: paste it into the browser
DevTools console while the quiz app is open to observe/auto-play via the UI
instead of `main.py`. It's kept for reference but is no longer required.

## Utilities

- **[len.sh](len.sh)** — quick script to print how many questions have been
  logged in `questions.json`.

## Data

`questions.json` accumulates logged questions locally and is git-ignored —
it's treated as local cache/state, not project source.
