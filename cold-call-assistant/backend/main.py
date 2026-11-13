import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="CallGuide API", version="1.1.0", description="Evidence-led cold-call companion")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=os.getenv("CORS_ORIGINS", "*") != "*",
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "apikey"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Demo/local fallback only. It is intentionally volatile; configure Supabase for persistence.
memory_calls = {}


class StartCall(BaseModel):
    prospect_name: str = ""
    company_name: str = ""
    role: str = ""
    phone_note: str = ""


class StageSave(BaseModel):
    stage_number: int = Field(ge=1, le=8)
    stage_reached: int = Field(ge=1, le=8)
    actions: List[str] = Field(default_factory=list)
    prospect_words: str = ""
    caller_note: str = ""


class CloseCall(BaseModel):
    outcome: str = Field(min_length=1, max_length=80)
    final_note: str = ""
    prospect_words: str = ""
    actions: List[str] = Field(default_factory=list)
    caller_note: str = ""
    current_stage: int = Field(ge=1, le=8)
    stage_reached: int = Field(ge=1, le=8)


class AIRequest(BaseModel):
    stage_number: int = Field(ge=1, le=8)
    prospect_words: str = ""
    caller_note: str = ""
    company_name: str = ""
    history: List[str] = Field(default_factory=list)


def using_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def db_headers(prefer: str = "return=representation"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


async def db_request(method: str, path: str, payload=None, prefer="return=representation"):
    async with httpx.AsyncClient(timeout=18) as client:
        response = await client.request(
            method,
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=db_headers(prefer),
            json=payload,
        )
        if response.is_error:
            detail = response.text[:500]
            raise HTTPException(502, f"Database request failed ({response.status_code}): {detail}")
        return response.json() if response.content else []


STAGES = {
    1: "Opening: reach the correct person and establish who is calling.",
    2: "Purpose: explain in one or two clear sentences why the call was made.",
    3: "Permission: establish whether the prospect is willing to talk now. A callback is not permission to continue now.",
    4: "Their business: understand the prospect's company and role before pitching.",
    5: "Their need, in their words: capture the prospect's goal or difficulty verbatim; do not rewrite it as a sales claim.",
    6: "Objection: understand the reason for hesitation or refusal without talking over it.",
    7: "Next step: agree one concrete action, channel, and/or time. A polite yes to a document is not automatically buying intent.",
    8: "Close: record the actual outcome and end the call clearly.",
}


@app.get("/")
def root():
    return {"service": "CallGuide API", "version": "1.1.0", "status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "supabase" if using_supabase() else "memory_only",
        "ai": "configured" if GEMINI_API_KEY else "not_configured",
        "model": GEMINI_MODEL if GEMINI_API_KEY else None,
    }


@app.post("/calls")
async def start_call(body: StartCall):
    row = {
        "prospect_name": body.prospect_name.strip(),
        "company_name": body.company_name.strip(),
        "role": body.role.strip(),
        "phone_note": body.phone_note.strip(),
        "stage_reached": 1,
        "outcome": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if using_supabase():
        data = await db_request("POST", "calls", row)
        return {"call": data[0]}
    row.update({"id": str(uuid.uuid4()), "stages": []})
    memory_calls[row["id"]] = row
    return {"call": row}


@app.get("/calls")
async def list_calls():
    if using_supabase():
        data = await db_request("GET", "calls?select=*&order=created_at.desc&limit=100")
    else:
        data = [c for c in memory_calls.values() if c.get("outcome") != "in_progress"]
        data.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return {"calls": data}


@app.get("/calls/{call_id}")
async def get_call(call_id: str):
    if using_supabase():
        calls = await db_request("GET", f"calls?id=eq.{call_id}&select=*&limit=1")
        if not calls:
            raise HTTPException(404, "Call not found")
        stages = await db_request("GET", f"call_stages?call_id=eq.{call_id}&select=*&order=stage_number.asc")
        return {"call": calls[0], "stages": stages}
    call = memory_calls.get(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return {"call": call, "stages": call.get("stages", [])}


@app.post("/calls/{call_id}/stage")
async def save_stage(call_id: str, body: StageSave):
    event = {
        "call_id": call_id,
        "stage_number": body.stage_number,
        "actions": body.actions,
        "prospect_words": body.prospect_words.strip(),
        "caller_note": body.caller_note.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if using_supabase():
        await db_request("POST", "rpc/save_call_stage_atomic", {
            "p_call_id": call_id,
            "p_stage_number": body.stage_number,
            "p_stage_reached": body.stage_reached,
            "p_actions": body.actions,
            "p_prospect_words": body.prospect_words.strip(),
            "p_caller_note": body.caller_note.strip(),
        })
        return {"saved": True, "stage_number": body.stage_number, "stage_reached": body.stage_reached}
    call = memory_calls.get(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    prior = next((i for i, x in enumerate(call["stages"]) if x["stage_number"] == body.stage_number), None)
    if prior is None:
        call["stages"].append(event)
    else:
        call["stages"][prior] = event
    call["stage_reached"] = max(call["stage_reached"], body.stage_reached)
    return {"saved": True, "stage_number": body.stage_number, "stage_reached": call["stage_reached"]}


@app.post("/calls/{call_id}/close")
async def close_call(call_id: str, body: CloseCall):
    # Save the current stage in the same close operation so ending early never drops the final notes.
    final_stage = {
        "call_id": call_id,
        "stage_number": body.current_stage,
        "actions": body.actions,
        "prospect_words": body.prospect_words.strip(),
        "caller_note": body.caller_note.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = {
        "outcome": body.outcome,
        "final_note": body.final_note.strip(),
        "stage_reached": max(body.stage_reached, body.current_stage),
        "last_prospect_words": body.prospect_words.strip(),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }
    if using_supabase():
        data = await db_request("POST", "rpc/close_call_atomic", {
            "p_call_id": call_id,
            "p_outcome": body.outcome,
            "p_final_note": body.final_note.strip(),
            "p_current_stage": body.current_stage,
            "p_stage_reached": body.stage_reached,
            "p_prospect_words": body.prospect_words.strip(),
            "p_actions": body.actions,
            "p_caller_note": body.caller_note.strip(),
        })
        saved_call = data[0] if isinstance(data, list) and data else data
        return {"saved": True, "call": saved_call}
    call = memory_calls.get(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    prior = next((i for i, x in enumerate(call["stages"]) if x["stage_number"] == body.current_stage), None)
    if prior is None:
        call["stages"].append(final_stage)
    else:
        call["stages"][prior] = final_stage
    call.update(payload)
    return {"saved": True, "call": call}


async def gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(503, "AI is not configured. Add GEMINI_API_KEY to the backend environment.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                json={
                    "system_instruction": {
                        "parts": [{"text": "You are CallGuide, a careful cold-call note assistant. Never invent prospect facts, never pressure a prospect, and always respect a clear refusal or do-not-call request. Distinguish a document request from genuine buying intent. Preserve multilingual wording and names exactly; do not silently translate or normalize Hindi, Hinglish, Marathi, Kannada, or other language fragments. Keep output concise and practical."}]
                    },
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
                },
            )
        if response.is_error:
            raise HTTPException(502, f"Gemini API returned {response.status_code}. Check model access, API key, and quota.")
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, "Gemini returned an unexpected response. Try again.")
    except httpx.TimeoutException:
        raise HTTPException(504, "Gemini took too long to respond. Try again.")


@app.post("/ai/suggest-stage")
async def suggest_stage(body: AIRequest):
    prompt = f"""Based only on the latest caller notes, identify the most likely current stage from this fixed eight-stage call structure and recommend one respectful next move. If evidence is insufficient, say 'uncertain' and ask one useful clarification. Do not infer interest from politeness. A callback request means pause and schedule; a clear refusal or do-not-call means stop and do not suggest another pitch. Return: Likely stage; Evidence from the prospect's words; Suggested next move; Confidence (low/medium/high). Keep under 100 words.

STAGES: {json_stages()}
Company context: {body.company_name or 'not provided'}
Current stage selected by caller: {body.stage_number} — {STAGES[body.stage_number]}
Prospect's exact words: {body.prospect_words or 'not captured'}
Caller note: {body.caller_note or 'none'}
What happened: {', '.join(body.history) if body.history else 'not selected'}"""
    return {"result": await gemini(prompt)}


@app.post("/ai/structure-notes")
async def structure_notes(body: AIRequest):
    prompt = f"""Turn the supplied notes into concise CRM fields. Preserve the prospect's wording in quotation marks and in its original language where possible. Do not silently translate multilingual fragments. Do not invent missing details. Do not interpret a polite document acceptance as buying intent. If the prospect declines or requests no more calls, make that explicit. Output these headings: Observed facts; Prospect's stated need; Objection or constraint; Agreed next step (include exact time/channel only if stated); One-line CRM summary.

Current stage: {body.stage_number} — {STAGES[body.stage_number]}
Company: {body.company_name or 'not provided'}
Prospect's exact words: {body.prospect_words or 'not captured'}
Caller note: {body.caller_note or 'none'}
Selected observations: {', '.join(body.history) if body.history else 'none'}"""
    return {"result": await gemini(prompt)}


def json_stages():
    return "\n".join(f"{n}. {label}" for n, label in STAGES.items())
