# TradeEase — Desktop GUI (PySide6)

A 4-screen desktop app: **Home → Classify HS Code → Generate Invoice → Guidance & Mentor**,
wired to the live Gemini API. Layout inspired by the reference image
(icon sidebar, light main panel, card grid, chat-style input bar),
colored with TradeEase's Ocean Gradient palette.

## Setup (5 minutes)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your real Gemini key (free, from aistudio.google.com)
python main.py
```

No key yet? The app still opens — every AI action just shows a clear
"add your key" message instead of crashing. Good for UI demos before the
backend is wired up.

## How it's organized

```
main.py                 → app window, screen routing, loads the API key
theme.py                → all colors/fonts/styles in ONE place
gemini_client.py         → the only file that talks to Gemini
widgets.py               → reusable pieces: sidebar, cards, mascot, worker thread
landing_screen.py        → Home screen
classification_screen.py → HS code classification flow
invoice_screen.py        → Invoice generation flow
mentor_screen.py         → Guidance & Mentor chat screen
```

Each screen is a self-contained `QWidget`. `main.py` just places them in a
`QStackedWidget` and connects their signals — e.g. clicking "Use this code"
on the classification result carries the product description + HS code
into the invoice form automatically.

## Suggested file ownership (matches how you've split the PRD)

| File | Owner |
|---|---|
| `gemini_client.py`, `main.py` | Tech Lead |
| `landing_screen.py`, `widgets.py` | Frontend Dev |
| `classification_screen.py`, `invoice_screen.py`, `mentor_screen.py` | Frontend Dev + Tech Lead |
| `theme.py`, copy/wording, demo flow | PM/UX Lead (you) |
| Prompt testing in `gemini_client.py`, edge cases | Data & Testing Engineer |

## Two concepts worth understanding (not just copying)

**1. Why API calls run on a `QThread` (see `GeminiWorker` in `widgets.py`)**
Calling Gemini directly inside a button's `clicked` handler freezes the
whole window until the response arrives — the #1 beginner mistake with
desktop apps + APIs. `GeminiWorker` runs the call on a background thread
and emits a signal back to the UI when it's done, so the window stays
responsive.

**2. Why every AI response is forced into JSON with a "caution" field**
Compliance is a domain where a confident-sounding wrong answer causes real
harm. `gemini_client.py` always asks for a structured response that
includes a human-in-the-loop caution line, and the UI always renders it —
this is your hallucination-prevention guardrail, built into the prompt
itself rather than bolted on later.

## Known limitations (MVP scope, by design)

- Classification gives one reasoning snippet, not a full action plan (matches your MVP scope decision).
- Guidance & Mentor is a simple Q&A chat, not the full "action-plan generation" feature — same scope-discipline logic, applied to chat instead of a one-shot report.
- Invoice export is plain `.txt`, not PDF — fastest path for the demo; swap in `reportlab` (also free) post-hackathon if you want a polished PDF.
- "Compliance Tracker" card is a visible stub — shows judges you know what's MVP vs. roadmap.
- Free-tier Gemini rate limits (~10-15 requests/min) — `gemini_client.py` retries with backoff automatically; if you still hit a 429 during a live demo, wait ~60 seconds.

## Next steps

- Swap in your real exact Ocean Gradient hex codes in `theme.py` if they differ from the placeholders here.
- Replace the `🤖` mascot with your actual mascot illustration (just swap the emoji `QLabel` for a `QPixmap` in `widgets.py`).
- Add a simple local history list (the "Coming Soon" card) once MVP demo is locked.
