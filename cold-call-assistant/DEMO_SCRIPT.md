# Six-minute product demonstration script

**Recording format:** screen recording with your camera visible in a small corner. Speak naturally; do not read every sentence word-for-word. Use a test database and fictional sample details only.

## 0:00–0:40 — The problem and product

“Hi, I’m going to walk through CallGuide, a cold-call assistant built for a caller at Meridian Growth Partners, a fictional company that sells growth analysis and growth work to Indian businesses. The problem is simple: on a cold call, the caller has to listen, remember the structure, capture what happened, and decide what to do next. CallGuide keeps the structure visible without forcing the caller to read a script.”

## 0:40–1:20 — Why this design

“The assignment included 100 call transcripts. I reviewed the outcome distribution and call lengths. The median recording is about 94 seconds, and 68 of the 100 calls are under two minutes. That influenced the interface: quick outcome taps, a short verbatim field, and the option to end at any stage. I also kept report acceptance separate from a meeting or a confirmed next step, because those are different outcomes in the data.”

Show the Research page and briefly point to the outcome breakdown and design decisions.

## 1:20–2:40 — Live call flow

“I’ll start a sample call. The caller enters the prospect and company details. The screen starts at Opening and shows what this stage is for, what prospects tend to say, and what the caller should listen for. The caller taps what happened rather than typing a long explanation.”

Start a call with fictional values. Demonstrate a quick action tap and enter a short exact quote. Click **Save & next** and show that the draft is retained when you move between stages.

## 2:40–3:35 — Prospect words and AI

“Stage 5 is deliberately different: it gives the prospect’s own words a dedicated field. The AI is not allowed to invent a need or turn a vague answer into buying intent. I can ask it to suggest the likely stage based on the notes, or structure the notes into a concise CRM summary. The caller remains responsible for checking the suggestion.”

Use one AI action if the API key is configured. If not, show the setup status and explain that the endpoint is deployed but the key is not configured in this demo environment. Do not pretend an AI response was generated.

## 3:35–4:25 — Ending early and outcomes

“Most calls do not reach the final stage. I can end a call from any point and select the actual outcome: a next step, a report request, a callback, not interested, do not call, wrong person, or another result. The current stage is saved with the call so the final notes are not lost.”

End the test call with a clear outcome. Choose a non-success outcome if that better demonstrates the product’s honesty.

## 4:25–5:20 — Call history and review

“Every saved call appears in Past calls with the furthest stage reached and the logged outcome. Opening a call shows the stage-by-stage record, the selected observations, the prospect’s exact words, and the caller’s notes. This makes the next conversation more informed.”

Open the call you just saved and review the stage record.

## 5:20–6:00 — Architecture and close

“The frontend is React and Vite on Vercel. The FastAPI backend runs on Render. Supabase stores calls and stage events, and its database functions make stage saves and call closing atomic. Gemini is called only from the backend, so the API key is not exposed in the browser. The goal is not to automate the salesperson; it is to help them listen better, record accurately, and agree a clear next step. Thank you.”

Show the deployed UI briefly, then the Render health endpoint or API docs if time allows.

## Before recording

- Use a stable internet connection and close unrelated tabs.
- Verify the frontend and backend are live.
- Test the exact flow once before recording.
- Use fictional names and company details.
- If Gemini is unavailable, be transparent; never simulate a live AI result.
- Keep your camera visible throughout and speak to the reviewer, not to the screen.
