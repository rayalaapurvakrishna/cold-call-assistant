
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Annotated, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="CallGuide API",
    version="2.2.0",
    description="Evidence-led cold-call intelligence assistant"
)

origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "*").split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "apikey"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

memory_calls = {}

ShortText = Annotated[str, Field(max_length=500)]
NoteText = Annotated[str, Field(max_length=4000)]
ActionText = Annotated[str, Field(max_length=300)]
ActionList = Annotated[List[ActionText], Field(max_length=20)]
HistoryList = Annotated[List[Annotated[str, Field(max_length=1000)]], Field(max_length=30)]


class StartCall(BaseModel):
    prospect_name: ShortText = ""
    company_name: ShortText = ""
    role: ShortText = ""
    phone_note: NoteText = ""


class StageSave(BaseModel):
    stage_number: int = Field(ge=1, le=8)
    stage_reached: int = Field(ge=1, le=8)
    actions: ActionList = Field(default_factory=list)
    prospect_words: NoteText = ""
    caller_note: NoteText = ""


class CloseCall(BaseModel):
    outcome: str = Field(min_length=1, max_length=80)
    final_note: NoteText = ""
    prospect_words: NoteText = ""
    actions: ActionList = Field(default_factory=list)
    caller_note: NoteText = ""
    current_stage: int = Field(ge=1, le=8)
    stage_reached: int = Field(ge=1, le=8)


class AIRequest(BaseModel):
    stage_number: int = Field(ge=1, le=8)
    prospect_words: NoteText = ""
    caller_note: NoteText = ""
    company_name: ShortText = ""
    history: HistoryList = Field(default_factory=list)
    call_id: Optional[str] = None


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
    prefer: str = "return=representation"
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
                "Supabase request failed:",
                response.status_code,
                response.text[:500]
            )
            raise HTTPException(
                502,
                f"Database request failed ({response.status_code})."
            )

        if not response.content:
            return []

        try:
            return response.json()
        except ValueError:
            raise HTTPException(
                502,
                "The database returned an invalid response."
            )

    except httpx.TimeoutException:
        raise HTTPException(504, "Database request timed out.")

    except httpx.RequestError:
        raise HTTPException(502, "Could not connect to the database.")


def validate_call_id(call_id: str) -> str:
    try:
        return str(uuid.UUID(call_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Invalid call ID.")


async def load_call_stages(call_id: str):
    call_id = validate_call_id(call_id)

    if using_supabase():
        calls = await db_request(
            "GET",
            f"calls?id=eq.{call_id}&select=id,company_name,prospect_name,role,phone_note&limit=1"
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
    sections = []

    for stage in stages:
        number = stage.get("stage_number", "?")
        label = STAGES.get(number, "Unknown stage")

        actions = stage.get("actions") or []
        words = (stage.get("prospect_words") or "").strip()
        note = (stage.get("caller_note") or "").strip()

        section = [f"STAGE {number}: {label}"]

        if actions:
            section.append("Recorded actions: " + ", ".join(actions))

        if words:
            section.append("Prospect's exact words: " + words)

        if note:
            section.append("Caller's observation: " + note)

        sections.append("\n".join(section))

    if extra_history:
        sections.append(
            "Additional current-stage observations:\n"
            + "\n".join(
                f"- {item}" for item in extra_history if item.strip()
            )
        )

    result = "\n\n".join(sections)
    return result[-18000:] if result else "No saved conversation."


async def get_ai_context(body: AIRequest):
    stages = []
    company = body.company_name
    caller_context = ""

    if body.call_id:
        stages, call = await load_call_stages(body.call_id)

        if not company:
            company = call.get("company_name", "")

        caller_context = (call.get("phone_note") or "").strip()

    context = build_conversation_context(stages, body.history)

    if caller_context:
        context += (
            "\n\nCALLER-PROVIDED SETUP CONTEXT "
            "(not prospect statements):\n"
            + caller_context
        )

    current_words = body.prospect_words.strip()
    current_note = body.caller_note.strip()

    current_section = []

    if current_words:
        current_section.append("Current prospect wording: " + current_words)

    if current_note:
        current_section.append("Current caller observation: " + current_note)

    if current_section:
        context += "\n\nCURRENT UNSAVED INPUT:\n"
        context += "\n".join(current_section)

    return context, company


@app.get("/")
def root():
    return {
        "service": "CallGuide API",
        "version": "2.2.0",
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
        data = list(memory_calls.values())
        data.sort(
            key=lambda call: call.get("created_at", ""),
            reverse=True
        )
        data = data[:100]

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

    call.update({
        "outcome": body.outcome,
        "final_note": body.final_note.strip(),
        "stage_reached": max(
            call.get("stage_reached", 1),
            body.stage_reached,
            body.current_stage
        ),
        "last_prospect_words": body.prospect_words.strip(),
        "closed_at": now,
    })

    return {
        "saved": True,
        "call": call
    }


SYSTEM_INSTRUCTION = """
You are CallGuide, an evidence-led sales-call intelligence assistant.

Your priority is factual accuracy, not making the conversation appear
more advanced than it is.

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
        f"models/{GEMINI_MODEL}:generateContent"
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
            "maxOutputTokens": 1200
        }
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(3):
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue

                if response.is_error:
                    print(
                        "Gemini request failed:",
                        response.status_code,
                        response.text[:500]
                    )
                    raise HTTPException(
                        502,
                        f"Gemini API returned {response.status_code}. Check backend logs."
                    )

                try:
                    data = response.json()
                except ValueError:
                    raise HTTPException(
                        502,
                        "Gemini returned an invalid response."
                    )

                candidates = data.get("candidates") or []

                if not candidates:
                    block_reason = (
                        data.get("promptFeedback", {}).get("blockReason")
                    )
                    message = (
                        f"Gemini could not process this request ({block_reason})."
                        if block_reason
                        else "Gemini returned no usable response. Try again."
                    )
                    raise HTTPException(502, message)

                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])

                answer = "\n".join(
                    part.get("text", "")
                    for part in parts
                    if part.get("text")
                ).strip()

                if not answer:
                    finish_reason = candidate.get("finishReason", "unknown")
                    raise HTTPException(
                        502,
                        f"Gemini returned no text response ({finish_reason})."
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


@app.post("/ai/suggest-stage")
async def suggest_stage(body: AIRequest):
    conversation, company = await get_ai_context(body)

    prompt = f"""
Analyze this complete sales conversation using evidence only.

PROSPECT COMPANY:
{company or "Not provided"}

SELECTED CURRENT WORKING STAGE:
{body.stage_number} — {STAGES[body.stage_number]}

COMPLETE CONVERSATION:
{conversation}

IMPORTANT:
The selected current working stage is determined by the caller.
Do not change it based on the prospect's buying signals.

Your analysis MUST independently assess THREE different dimensions:

DIMENSION 1 — CONVERSATION PROGRESS

Report:
- Selected working stage.
- What the caller and prospect have actually covered.
- Whether the selected stage has supporting evidence.
- Any earlier or later stage signals worth noting.

Do not confuse reaching Stage 8 (Close) with making a sale.

DIMENSION 2 — SALES QUALIFICATION

Assess these areas separately:

1. Business need:
   Is there an explicit business problem or goal?
   Include the prospect's evidence.

2. Existing solution:
   What tool or process does the prospect currently use?
   What limitation did they actually mention?

3. Budget:
   Is a budget amount or spending range known?
   Is there a budget concern?
   Do not invent an amount.

4. Decision-making authority:
   Is the prospect the decision-maker?
   Is another person's approval explicitly required?
   If unknown, say "Not established."

5. Buying interest:
   Is there general interest, active evaluation, or an explicit
   purchase commitment?
   Do not exaggerate conditional interest.

Give an overall qualification assessment:
- Qualified: meaningful need and sufficient supporting qualification evidence.
- Partially qualified: meaningful need, but important commercial details remain unknown.
- Not qualified: no supported need or clear disqualifying evidence.
- Insufficient information: too little evidence to assess.

Do not automatically call a prospect qualified merely because they
identified a problem or requested information.

DIMENSION 3 — ACTUAL CALL OUTCOME

Identify separately:

- Prospect's requested action.
- Caller action required.
- Action explicitly agreed by both parties.
- Proposed but conditional future action.
- Scheduled meeting: only if an actual date and time were agreed.
- Purchase commitment: only if explicit purchase evidence exists.
- Final call outcome.

Never turn a request for information into a scheduled meeting.
Never turn a conditional demo into an agreed meeting.
Never turn a polite response into buying intent.

EVIDENCE RULES:

- Use exact prospect quotes whenever possible.
- Label caller observations separately.
- If something is unknown, write "Not established."
- Do not invent dates, budgets, approval processes or decision-makers.
- Distinguish a price objection from a general budget concern.
- Distinguish vendor evaluation from rejection.
- Distinguish requested, proposed and agreed actions.

OUTPUT USING THESE EXACT HEADINGS:

1. Conversation progress
   Selected stage:
   Progress assessment:
   Other detected signals:

2. Sales qualification
   Business need:
   Existing solution:
   Budget:
   Decision-making authority:
   Buying interest:
   Overall qualification:

3. Actual call outcome
   Prospect request:
   Caller action:
   Agreed action:
   Conditional next step:
   Scheduled meeting:
   Purchase commitment:
   Final outcome:

4. Evidence and unknowns

5. Recommended next move

6. Confidence
   Conversation progress:
   Sales qualification:
   Call outcome:

Confidence levels:
HIGH = direct and unambiguous evidence.
MEDIUM = supporting evidence, but important details are missing.
LOW = ambiguous or insufficient evidence.

Keep the analysis under 350 words.
Be factual, concise and useful to a salesperson.
"""

    return {"result": await gemini(prompt)}


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

    return {"result": await gemini(prompt)}
