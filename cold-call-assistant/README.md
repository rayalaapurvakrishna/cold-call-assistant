# CallGuide — Cold-call field assistant

A focused web app for a caller at **Meridian Growth Partners**, a fictional company selling growth analysis and growth work to Indian businesses. CallGuide keeps a salesperson oriented through the eight stages of a first call, captures what actually happened, and saves the stage reached and call outcome.

> The product is a call companion, not an auto-dialler or a script. The caller stays in control. AI suggestions are advisory and must be checked against what the prospect actually said.

## Product walkthrough

### Live call
- Eight fixed stages from the supplied brief: Opening, Purpose, Permission, Their business, Their need (in the prospect's words), Objection, Next step, Close.
- A one-line purpose and stage-specific listening guidance.
- Four quick outcome taps per stage.
- A dedicated verbatim field for the prospect's words and a separate caller note.
- Drafts remain in place when the caller navigates between stages.
- A call can end at any stage; the current stage is saved as part of the close operation.

### Past calls
- Saved prospect and company details, outcome, and furthest stage reached.
- Open a call to review the stage-by-stage observations, verbatim words, and caller notes.

### Research
- Aggregate findings from the provided 100-call sample.
- Outcome distribution and explicit product decisions tied to the evidence.
- Raw transcript files, names, and company names are not shipped in the public app.

### AI assistance
- **AI stage coach:** suggests a likely stage, evidence, and one respectful next move.
- **Structure notes:** formats caller notes into CRM fields while preserving prospect wording.
- Guardrails distinguish a document request from a meeting, avoid inventing needs, and prohibit suggesting another pitch after a clear refusal or do-not-call request.
- Uses Gemini through the backend. The API key is never sent to the browser.

## Evidence from the supplied research sample

The sample contains 100 fictionalised transcripts. Median recording length is 93.5 seconds; 68 of 100 recordings are under two minutes. The ten caller-logged outcomes are:

| Outcome | Calls |
|---|---:|
| Not interested | 14 |
| Agreed to receive report | 14 |
| Follow-up | 14 |
| Not logged | 13 |
| Next step agreed | 11 |
| Do not call | 10 |
| Wrong person | 8 |
| Interested | 7 |
| Moved company | 5 |
| Call again | 4 |

These are caller-logged labels, not an independent judgment of call quality. The source notes that some speaker labels may be swapped and logged outcomes do not always match the spoken conversation. The product therefore keeps observations, prospect words, and final outcomes distinct. No individual transcript or identity is included in this repository.

## Architecture

```text
React + Vite (Vercel)
        |
        | HTTPS JSON
        v
FastAPI (Render) -------- Gemini API
        |
        | Supabase REST / RPC
        v
Supabase Postgres
  - calls
  - call_stages
```

- Frontend: React 18, Vite, Lucide icons.
- Backend: Python, FastAPI, Pydantic, HTTPX.
- Database: Supabase Postgres.
- AI: Gemini API (`gemini-3.8-flash` by default; configurable with `GEMINI_MODEL`).
- Hosting: Vercel (frontend), Render (backend), Supabase (database).

## Run locally

### 1. Database
1. Create a Supabase project.
2. Open **SQL Editor**.
3. Run `supabase/schema.sql` (includes tables, indexes, RLS, and atomic write functions).
4. Copy the Project URL and service-role key. The service-role key belongs only in the backend environment.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and fill in:

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_SIDE_SERVICE_ROLE_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.8-flash
CORS_ORIGINS=http://localhost:5173
```

Start the API:

```bash
uvicorn main:app --reload --port 8000
```

Check `http://localhost:8000/health`. It should report `status: ok`, `database: supabase`, and `ai: configured` after the environment variables are correct.

Without Supabase credentials, the backend uses a temporary in-memory fallback for local UI testing. Those records disappear when the server restarts. Without a Gemini key, normal call capture still works but AI endpoints return a clear configuration message.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. For local development, the frontend defaults to `http://localhost:8000`. If the API runs elsewhere, create `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

## Deploy

### Render — backend
1. Push this repository to GitHub.
2. In Render, create a **New Web Service** connected to the repository.
3. Root directory: `backend`.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
6. Health check path: `/health`.
7. Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, and `CORS_ORIGINS` as Render environment variables. Set `CORS_ORIGINS` to the exact Vercel deployment origin (and localhost only if needed).

### Vercel — frontend
1. Import the same GitHub repository.
2. Root directory: `frontend`.
3. Framework preset: Vite.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add `VITE_API_URL` with the deployed Render base URL, without a trailing slash.
7. Deploy, then add the exact Vercel origin to Render's `CORS_ORIGINS` and redeploy the backend if changed.

After deployment, open the Vercel app, start a test call, save two stages, end early, refresh the page, and verify the call and stage notes still appear in Past calls. Check the Render `/health` endpoint separately.

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Service, database and AI configuration status |
| POST | `/calls` | Start a call |
| GET | `/calls` | List saved calls |
| GET | `/calls/{id}` | Retrieve a call and its stage history |
| POST | `/calls/{id}/stage` | Save or update a stage |
| POST | `/calls/{id}/close` | Save the current stage and close atomically |
| POST | `/ai/suggest-stage` | AI stage coach |
| POST | `/ai/structure-notes` | Structure notes for CRM |

Interactive API docs are available at `/docs` on the running backend.

## Reliability and security choices

- Stage writes and call closing use Postgres RPC functions so stage capture and call progress commit in a single database transaction.
- A unique `(call_id, stage_number)` constraint prevents duplicate stage rows when a caller revisits a stage.
- Row-level security is enabled on both tables. The backend service-role key bypasses RLS and is never included in frontend variables.
- The caller's exact words are stored separately from the AI-generated summary.
- The UI retains unsaved drafts when moving between stages. The final stage is saved when ending early.
- The in-memory fallback is for local preview only, not production persistence.

## Tests

From `backend/`:

```bash
pip install -r requirements.txt
pip install pytest
pytest -q
```

The tests cover health, early close, exact-word retention, stage revisit behavior, history retrieval, 404 handling, and graceful AI configuration failure.

## Submission checklist

- [ ] Run the SQL in Supabase.
- [ ] Deploy the API on Render and verify `/health`.
- [ ] Deploy the frontend on Vercel and verify `VITE_API_URL`.
- [ ] Confirm a saved call survives a browser refresh and backend restart.
- [ ] Test a callback, a wrong-person result, a clear no, and a report request.
- [ ] Test both AI actions with the Gemini key configured.
- [ ] Add the real Vercel and Render URLs below.
- [ ] Record the six-minute walkthrough with camera visible.

## Live URLs

- Frontend: _add after deployment_
- Backend: _add after deployment_
- API docs: _add after deployment_

## Free-tier behavior and privacy note

This stack can be demonstrated on free tiers, but “free” does not mean always-on:

- **Render Free:** a web service spins down after 15 minutes without inbound traffic and may take about a minute to wake on the next request. Its filesystem is ephemeral, which is why calls are stored in Supabase rather than local files. See [Render free services](https://render.com/docs/free).
- **Supabase Free:** includes a 500 MB database and projects can pause after one week of inactivity. Reopen the project in the dashboard if it has paused. See [Supabase pricing](https://supabase.com/pricing).
- **Vercel Hobby:** free for personal, non-commercial use; review the plan terms before using it for a commercial deployment. See [Vercel Hobby](https://vercel.com/docs/plans/hobby).
- **Gemini API:** Gemini 3.8 Flash lists a free tier. Google notes that free-tier content may be used to improve products. Use fictional/demo information only in this assignment; do not submit real prospect contact details, confidential business information, or sensitive call notes through the free tier. See [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing/).

These are provider policies and quotas, which can change. Check the linked official pages before deployment.

### Prototype access boundary

This assignment build does not yet include user sign-in or per-caller authorization. Keep the deployment limited to reviewer/demo use and synthetic contact data. RLS protects direct anonymous table access, but the public API routes themselves are not an identity system. Before using real prospect records or opening this to a sales team, add Supabase Auth, caller ownership columns, per-user RLS policies, and authenticated API checks.
