# sitcon-2026-questions

Helper tooling for the SITCON 2026 "battle" live quiz: a browser-side script
that intercepts the quiz app's network traffic, and a small FastAPI service
that records questions/answers and serves back the best-known answer.

## How it works

1. **[log.js](log.js)** is pasted into the browser DevTools console while the
   quiz app is open. It monkey-patches `window.fetch` to observe the app's
   API calls:
   - When a `currentQuestionResult` comes back (the correct answer for a
     question that already closed), it POSTs the question + correct choice to
     the local API (`/log`) so it's saved for next time.
   - When a `currentQuestion` is active, it asks the local API
     (`/answer/{questionId}`) for the best-known answer and automatically
     clicks the matching choice button.
   - When the round `status` is `completed`, it automatically navigates back
     to `/battle/` and clicks through the "play again" buttons.
2. **[main.py](main.py)** is a FastAPI app that persists logged questions to
   `questions.json`:
   - `POST /log` — stores a question's prompt/choices/correct answer, keyed
     by `questionId` (no-op if already recorded).
   - `GET /answer/{questionId}` — returns the correct choice if the question
     is already known; otherwise falls back to the most common correct
     choice seen so far (a reasonable guess for unseen questions).

## Requirements

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) (dependency management, per `pyproject.toml` / `uv.lock`)

## Setup

```bash
uv sync
```

## Running the API

```bash
uv run fastapi dev main.py
```

This starts the API on `http://localhost:8000`.

## Using the browser script

1. Start the API (above).
2. Open the quiz app in your browser and open DevTools → Console.
3. Paste the contents of [log.js](log.js) and press Enter.
4. Play as normal — answers get logged automatically, and known questions
   are auto-answered.

## Utilities

- **[len.sh](len.sh)** — quick script to print how many questions have been
  logged in `questions.json`.

## Data

`questions.json` accumulates logged questions locally and is git-ignored —
it's treated as local cache/state, not project source.
