
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="CallGuide API",
    version="2.0.0",
    description="Evidence-led cold-call intelligence assistant"
)

origins = [
    x.strip()
    for x in os.getenv("CORS_ORIGINS", "*").split(",")
    if x.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "apikey"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Volatile fallback for local development and demos.
memory_calls = {}


# --------------------------------------------------
# DATA MODELS
# --------------------------------------------------

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

    # Optional so older frontend requests remain compatible.
    # The upgraded frontend will send this to retrieve saved stages.
    call_id: Optional[str] = None


# --------------------------------------------------
# SALES STAGE FRAMEWORK
# --------------------------------------------------

STAGES = {
    1: "Opening: reach the correct person and establish who is calling.",
    2: "Purpose: explain clearly why the call was made.",
    3: "Permission: establish whether the prospect is willing to talk now. A callback request means pause and schedule.",
    4: "Their business: understand the prospect's company, role and operating context.",
    5: "Their need: capture the prospect's actual goal, problem or requirement in their own words.",
    6: "Objection or evaluation: understand explicit hesitation, price concerns, vendor comparisons, approval requirements or other constraints without assuming they all mean the same thing.",
    7: "Next step: identify a concrete agreed action, owner, channel and time where available.",
    8: "Close: record the actual call outcome accurately and end respectfully."
}


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def using_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def db_headers(prefer: str = "return=representation"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


async def db_request(
    method: str,
    path: str,
    payload=None,
    prefer="return=representation"
):
    if not using_supabase():
        raise HTTPException(503, "Supabase is not configured.")

    try:
        async with httpx.AsyncClient(timeout=18) as client:
            response = await client.request(
                method,
                f"{SUPABASE_URL}/rest/v1/{path}",
                headers=db_headers(prefer),
                json=payload,
            )

        if response.is_error:
            print(
                "Supabase error:",
                response.status_code,
                response.text[:1000]
            )
            raise HTTPException(
                502,
                f"Database request failed ({response.status_code})."
            )

        return response.json() if response.content else []

    except httpx.TimeoutException:
        raise HTTPException(504, "Database request timed out.")

    except httpx.RequestError:
        raise HTTPException(502, "Could not connect to the database.")


def validate_call_id(call_id: str):
    try:
        return str(uuid.UUID(call_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Invalid call ID.")


async def load_call_stages(call_id: str):
    """
    Retrieve the actual saved stage history.
    This is the source of truth for AI conversation context.
    """

    call_id = validate_call_id(call_id)

    if using_supabase():
        calls = await db_request(
            "GET",
            f"calls?id=eq.{call_id}&select=id,company_name,prospect_name&limit=1"
        )

        if not calls:
            raise HTTPException(404, "Call not found.")

        stages = await db_request(
            "GET",
            f"call_stages?call_id=eq.{call_id}&select=*&order=stage_number.asc"
        )

        return stages, calls[0]

    call = memory_calls.get(call_id)

    if not call:
        raise HTTPException(404, "Call not found.")

    return (
        sorted(
            call.get("stages", []),
            key=lambda item: item["stage_number"]
        ),
        call
    )


def build_conversation_context(stages, extra_history):
    """
    Build a readable transcript from all saved stages.
    Preserve prospect wording and distinguish it from caller notes.
    """

    sections = []

    for stage in stages:
        number = stage.get("stage_number", "?")
        label = STAGES.get(number, "Unknown stage")

        actions = stage.get("actions") or []
        words = (stage.get("prospect_words") or "").strip()
        note = (stage.get("caller_note") or "").strip()

        section = [
            f"STAGE {number}: {label}",
        ]

        if actions:
            section.append(
                "Recorded actions: " + ", ".join(actions)
            )

        if words:
            section.append(
                "Prospect's exact words: " + words
            )

        if note:
            section.append(
                "Caller's observation: " + note
            )

        sections.append("\n".join(section))

    if extra_history:
        sections.append(
            "Additional current-stage observations:\n"
            + "\n".join(
                f"- {item}" for item in extra_history if item.strip()
            )
        )

    result = "\n\n".join(sections)

    # Prevent excessively long prompts.
    return result[-18000:] if result else "No saved conversation."


async def get_ai_context(body: AIRequest):
    """
    Combine saved stages with current unsaved input.
    Older frontend requests without call_id still work.
    """

    stages = []
    company = body.company_name

    if body.call_id:
        stages, call = await load_call_stages(body.call_id)

        if not company:
            company = call.get("company_name", "")

    context = build_conversation_context(
        stages,
        body.history
    )

    current_words = body.prospect_words.strip()
    current_note = body.caller_note.strip()

    current_section = []

    if current_words:
        current_section.append(
            "Current prospect wording: " + current_words
        )

    if current_note:
        current_section.append(
            "Current caller observation: " + current_note
        )

    if current_section:
        context += "\n\nCURRENT UNSAVED INPUT:\n"
        context += "\n".join(current_section)

    return context, company


# --------------------------------------------------
# API STATUS
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "CallGuide API",
        "version": "2.0.0",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "supabase" if using_supabase() else "memory_only",
        "ai": "configured" if GEMINI_API_KEY else "not_configured",
        "model": GEMINI_MODEL if GEMINI_API_KEY else None,
    }


# --------------------------------------------------
# CALL MANAGEMENT
# --------------------------------------------------

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

        if not data:
            raise HTTPException(502, "Could not create the call.")

        return {"call": data[0]}

    row.update({
        "id": str(uuid.uuid4()),
        "stages": []
    })

    memory_calls[row["id"]] = row

    return {"call": row}


@app.get("/calls")
async def list_calls():
    if using_supabase():
        data = await db_request(
            "GET",
            "calls?select=*&order=created_at.desc&limit=100"
        )
    else:
        data = [
            call
            for call in memory_calls.values()
            if call.get("outcome") != "in_progress"
        ]

        data.sort(
            key=lambda call: call.get("created_at", ""),
            reverse=True
        )

    return {"calls": data}


@app.get("/calls/{call_id}")
async def get_call(call_id: str):
    call_id = validate_call_id(call_id)

    if using_supabase():
        calls = await db_request(
            "GET",
            f"calls?id=eq.{call_id}&select=*&limit=1"
        )

        if not calls:
            raise HTTPException(404, "Call not found.")

        stages = await db_request(
            "GET",
            f"call_stages?call_id=eq.{call_id}&select=*&order=stage_number.asc"
        )

        return {
            "call": calls[0],
            "stages": stages
        }

    call = memory_calls.get(call_id)

    if not call:
        raise HTTPException(404, "Call not found.")

    return {
        "call": call,
        "stages": call.get("stages", [])
    }


# --------------------------------------------------
# SAVE STAGE
# --------------------------------------------------

@app.post("/calls/{call_id}/stage")
async def save_stage(call_id: str, body: StageSave):
    call_id = validate_call_id(call_id)

    event = {
        "call_id": call_id,
        "stage_number": body.stage_number,
        "actions": body.actions,
        "prospect_words": body.prospect_words.strip(),
        "caller_note": body.caller_note.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if using_supabase():
        await db_request(
            "POST",
            "rpc/save_call_stage_atomic",
            {
                "p_call_id": call_id,
                "p_stage_number": body.stage_number,
                "p_stage_reached": body.stage_reached,
                "p_actions": body.actions,
                "p_prospect_words": body.prospect_words.strip(),
                "p_caller_note": body.caller_note.strip(),
            }
        )

        return {
            "saved": True,
            "stage_number": body.stage_number,
            "stage_reached": body.stage_reached
        }

    call = memory_calls.get(call_id)

    if not call:
        raise HTTPException(404, "Call not found.")

    prior = next(
        (
            index
            for index, item in enumerate(call["stages"])
            if item["stage_number"] == body.stage_number
        ),
        None
    )

    if prior is None:
        call["stages"].append(event)
    else:
        call["stages"][prior] = event

    call["stage_reached"] = max(
        call["stage_reached"],
        body.stage_reached
    )

    return {
        "saved": True,
        "stage_number": body.stage_number,
        "stage_reached": call["stage_reached"]
    }


# --------------------------------------------------
# CLOSE CALL
# --------------------------------------------------

@app.post("/calls/{call_id}/close")
async def close_call(call_id: str, body: CloseCall):
    call_id = validate_call_id(call_id)

    now = datetime.now(timezone.utc).isoformat()

    final_stage = {
        "call_id": call_id,
        "stage_number": body.current_stage,
        "actions": body.actions,
        "prospect_words": body.prospect_words.strip(),
        "caller_note": body.caller_note.strip(),
        "created_at": now,
    }

    payload = {
        "outcome": body.outcome,
        "final_note": body.final_note.strip(),
        "stage_reached": max(
            body.stage_reached,
            body.current_stage
        ),
        "last_prospect_words": body.prospect_words.strip(),
        "closed_at": now,
    }

    if using_supabase():
        data = await db_request(
            "POST",
            "rpc/close_call_atomic",
            {
                "p_call_id": call_id,
                "p_outcome": body.outcome,
                "p_final_note": body.final_note.strip(),
                "p_current_stage": body.current_stage,
                "p_stage_reached": body.stage_reached,
                "p_prospect_words": body.prospect_words.strip(),
                "p_actions": body.actions,
                "p_caller_note": body.caller_note.strip(),
            }
        )

        saved_call = (
            data[0]
            if isinstance(data, list) and data
            else data
        )

        return {
            "saved": True,
            "call": saved_call
        }

    call = memory_calls.get(call_id)

    if not call:
        raise HTTPException(404, "Call not found.")

    prior = next(
        (
            index
            for index, item in enumerate(call["stages"])
            if item["stage_number"] == body.current_stage
        ),
        None
    )

    if prior is None:
        call["stages"].append(final_stage)
    else:
        call["stages"][prior] = final_stage

    call.update(payload)

    return {
        "saved": True,
        "call": call
    }


# --------------------------------------------------
# GEMINI AI
# --------------------------------------------------


SYSTEM_INSTRUCTION = """
You are CallGuide, an evidence-led sales-call intelligence assistant.

Your priority is factual accuracy, not making the conversation appear more advanced than it is.

CORE RULES:

1. Never invent facts, needs, budgets, decisions, approvals or commitments.
2. Clearly distinguish prospect statements from caller observations.
3. Preserve the prospect's exact wording and original language.
4. Politeness and permission to talk do not indicate buying intent.
5. A request for a report, brochure, email or quotation is not a purchase commitment.
6. Never assume a prospect's company is the caller's company or solution provider.
7. Never invent a product, service, feature or company offering.
8. A clear refusal or do-not-call request must be respected.
9. A callback request means pause and establish a callback arrangement.
10. Never describe a proposed next step as an agreed next step.

STAGE ACCURACY:

The stage selected by the caller is the CURRENT WORKING STAGE.

Do not change the current working stage simply because information
associated with a later stage appears in the conversation.

Report detected signals separately from the current stage.

Examples:
- Stage 4 may contain an early indication of a business problem.
- Stage 5 captures the prospect's actual need in greater detail.
- Stage 6 covers objections and evaluation constraints.
- Stage 7 records agreed next steps.
- Stage 8 records the actual closing outcome.

Do not claim a stage has been completed without supporting evidence.

CLASSIFICATION RULES:

BUDGET:
A stated budget, spending range or budget ceiling is qualification information.
It is not automatically a price objection.

PRICE OBJECTION:
Only classify as a price objection when the prospect explicitly expresses
price resistance, dissatisfaction, unaffordability or poor value.

VENDOR EVALUATION:
Comparing vendors, existing tools or competing solutions indicates evaluation.
It does not automatically indicate rejection.

APPROVAL REQUIRED:
Use this classification only when the prospect explicitly mentions
a manager, director, finance team, purchasing authority or another
decision-maker whose approval is needed.

Do not infer approval requirements from budget concerns.

NEED IDENTIFIED:
A need requires an actual stated problem, goal or requirement.
Preserve the prospect's own words as evidence.

BUYING SIGNAL:
A concrete indication of purchasing interest or commitment.
A general request for information alone is insufficient.

NEXT STEP:
Distinguish these carefully:
- Requested action: prospect asks the caller to do something.
- Proposed action: a possible future action is discussed.
- Agreed action: both parties explicitly accept an action.
- Scheduled meeting: date and time are actually agreed.
- Purchase commitment: explicit evidence of a purchase decision.

Never invent an owner, date, time or communication channel.

COMPANY CONTEXT:
The prospect's company is not necessarily the caller's company.
Do not attribute a solution, product or service to either company
unless the conversation explicitly establishes it.

CONFIDENCE:
HIGH: Direct, unambiguous evidence.
MEDIUM: Some supporting evidence, but important details are missing.
LOW: Ambiguous, contradictory or insufficient evidence.

When evidence is insufficient, say "Not established."

Be concise, practical and evidence-led.
"""


async def gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(
            503,
            "AI is not configured. Add GEMINI_API_KEY to the backend environment."
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(3):
                response = await client.post(url, json=payload)

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue

                if response.is_error:
                    print(
                        "Gemini error:",
                        response.status_code,
                        response.text[:1000]
                    )

                    raise HTTPException(
                        502,
                        f"Gemini API returned {response.status_code}. Check backend logs."
                    )

                data = response.json()

                candidates = data.get("candidates") or []

                if not candidates:
                    raise HTTPException(
                        502,
                        "Gemini returned no usable response. Try again."
                    )

                parts = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [])
                )

                answer = "\n".join(
                    part.get("text", "")
                    for part in parts
                    if part.get("text")
                ).strip()

                if not answer:
                    raise HTTPException(
                        502,
                        "Gemini returned an empty response. Try again."
                    )

                return answer

    except httpx.TimeoutException:
        raise HTTPException(
            504,
            "Gemini took too long to respond. Try again."
        )

    except httpx.RequestError:
        raise HTTPException(
            502,
            "Could not connect to Gemini. Try again."
        )

    raise HTTPException(
        503,
        "Gemini is temporarily unavailable. Please try again."
    )


# --------------------------------------------------
# AI CONTEXT AND PROMPTS
# --------------------------------------------------

def json_stages():
    return "\n".join(
        f"{number}. {label}"
        for number, label in STAGES.items()
    )


@app.post("/ai/suggest-stage")
async def suggest_stage(body: AIRequest):
    conversation, company = await get_ai_context(body)

    prompt = f"""
Analyze the complete sales conversation below.

Identify the most advanced stage that is ACTUALLY supported by evidence.

Do not assume that the caller has completed a stage just because it is selected
in the interface.

AVAILABLE STAGES:
{json_stages()}

CURRENT STAGE SELECTED BY CALLER:
{body.stage_number} — {STAGES[body.stage_number]}

COMPANY:
{company or "Not provided"}

COMPLETE CONVERSATION:
{conversation}

CLASSIFICATION CHECKLIST:

- Is this a budget qualification or an actual price objection?
- Is the prospect comparing vendors?
- Is a manager or director approval required?
- Has the prospect explicitly stated a need?
- Has the prospect agreed to a specific next step?
- Is there a clear refusal or do-not-call request?
- Is there evidence of an actual buying commitment?

Respond using these exact headings:

Likely stage:
Classification:
Evidence:
What is still unknown:
Suggested next move:
Confidence: LOW / MEDIUM / HIGH

For Classification, use the most relevant label:
Qualification, Need identified, Price objection, Vendor evaluation,
Approval required, Other objection, Information requested,
Next step agreed, Buying signal, Refusal, Do not call, or Uncertain.

Do not invent evidence. Quote the prospect's actual words when useful.
Keep the response under 180 words.
"""

    return {
        "result": await gemini(prompt)
    }


@app.post("/ai/structure-notes")
async def structure_notes(body: AIRequest):
    conversation, company = await get_ai_context(body)

    prompt = f"""
Convert this complete sales conversation into accurate CRM notes.

COMPANY:
{company or "Not provided"}

CURRENT STAGE:
{body.stage_number} — {STAGES[body.stage_number]}

COMPLETE CONVERSATION:
{conversation}

IMPORTANT:

- Separate verified facts from caller assumptions.
- Preserve important prospect quotes in their original language.
- Never silently translate multilingual wording.
- Do not invent a budget, requirement, deadline or decision.
- Distinguish budget qualification from a price objection.
- Distinguish vendor comparison from rejection.
- Distinguish approval requirements from refusal.
- A report or brochure request is not a purchase commitment.
- Record only next steps that were actually agreed.
- Explicitly highlight a refusal or do-not-call request.
- If information is missing, write "Not established."

OUTPUT THESE HEADINGS:

1. Observed facts
2. Prospect's stated need
3. Budget and commercial qualification
4. Objection, evaluation or approval constraint
5. Buying signals
6. Agreed next step
7. Important prospect quotes
8. One-line CRM summary

Keep the result concise, factual and useful to a salesperson.
"""

    return {
        "result": await gemini(prompt)
    }
