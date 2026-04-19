import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENCODE_CMD   = os.getenv("OPENCODE_CMD", "opencode")
MAX_STEPS    = int(os.getenv("MAX_STEPS", "10"))
WORK_DIR    = os.getenv("WORK_DIR", "/root/workspace")

app = FastAPI(title="Codex Controller", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

sessions: dict[str, dict] = {}

class RunRequest(BaseModel):
    goal: str
    repo_path: str = WORK_DIR

class StepEvent(BaseModel):
    step: int
    type: str
    content: str

SYSTEM_PROMPT = """Ти — автономний планувальник завдань для розробника.
Тобі дають ЦІЛЬ та ІСТОРІЮ виконаних кроків.
Твоє завдання: повернути НАСТУПНИЙ конкретний крок для OpenCode CLI.

Формат відповіді (строго JSON):
{
  "command": "конкретна інструкція для OpenCode одним рядком",
  "reasoning": "чому цей крок наступний",
  "is_done": false
}

Якщо ціль досягнута — поверни is_done: true.
Команди мають бути конкретними: "fix failing tests in auth.py", "add error handling to api.py" тощо.
НЕ використовуй розпливчасті команди. Бути точним."""

async def plan_next_step(goal: str, history: list[dict]) -> dict:
    history_text = ""
    for i, h in enumerate(history):
        history_text += f"\nШАГ {i+1}: {h['command']}\nРЕЗУЛЬТАТ: {h['result'][:500]}\n"
    
    user_msg = f"ЦІЛЬ: {goal}\n\nІСТОРІЯ:\n{history_text or 'Початок — історія порожня.'}"
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg}
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    
    return json.loads(response.choices[0].message.content)

async def run_opencode(command: str, repo_path: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            OPENCODE_CMD, "run", command,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="replace")
        
        return output.strip() if output.strip() else "Команду виконано без виводу."
        
    except asyncio.TimeoutError:
        return "TIMEOUT: OpenCode не відповів за 120 секунд."
    except FileNotFoundError:
        return f"ERROR: OpenCode CLI не знайдено за шляхом '{OPENCODE_CMD}'. Перевір OPENCODE_CMD."
    except Exception as e:
        return f"ERROR: {str(e)}"

async def autonomous_loop(session_id: str, goal: str, repo_path: str):
    session = sessions[session_id]
    session["status"] = "running"
    session["events"].append(StepEvent(
        step=0, type="plan",
        content=f"🎯 Ціль: {goal}\n📁 Репо: {repo_path}"
    ))
    
    history = []
    
    for step in range(1, MAX_STEPS + 1):
        
        if session.get("cancelled"):
            session["events"].append(StepEvent(step=step, type="done", content="⛔ Зупинено користувачем."))
            session["status"] = "cancelled"
            return
        
        session["events"].append(StepEvent(step=step, type="plan", content="🧠 Планую наступний крок..."))
        
        try:
            plan = await plan_next_step(goal, history)
        except Exception as e:
            session["events"].append(StepEvent(step=step, type="error", content=f"LLM error: {e}"))
            session["status"] = "error"
            return
        
        session["events"].append(StepEvent(
            step=step, type="plan",
            content=f"📋 Крок {step}: {plan['command']}\n💭 {plan['reasoning']}"
        ))
        
        if plan.get("is_done"):
            session["events"].append(StepEvent(step=step, type="done", content=f"✅ Ціль досягнута за {step-1} кроків!"))
            session["status"] = "done"
            return
        
        session["events"].append(StepEvent(step=step, type="execute", content=f"⚙️ Виконую: {plan['command']}"))
        
        result = await run_opencode(plan["command"], repo_path)
        
        session["events"].append(StepEvent(
            step=step, type="result",
            content=f"📤 Результат:\n{result[:1000]}"
        ))
        
        history.append({"command": plan["command"], "result": result})
    
    session["events"].append(StepEvent(
        step=MAX_STEPS, type="done",
        content=f"⚠️ Досягнуто ліміт {MAX_STEPS} кроків. Зупини вручну або збільш MAX_STEPS."
    ))
    session["status"] = "limit_reached"

@app.post("/run")
async def run_loop(req: RunRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(400, "OPENAI_API_KEY не задан в env")
    
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "goal": req.goal,
        "repo_path": req.repo_path,
        "status": "pending",
        "events": [],
        "created_at": datetime.now().isoformat(),
        "cancelled": False,
    }
    
    asyncio.create_task(autonomous_loop(session_id, req.goal, req.repo_path))
    
    return {"session_id": session_id, "stream_url": f"/stream/{session_id}"}

@app.get("/stream/{session_id}")
async def stream_events(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Сессия не найдена")
    
    async def generate() -> AsyncGenerator:
        sent = 0
        while True:
            session = sessions[session_id]
            events = session["events"]
            
            while sent < len(events):
                evt = events[sent]
                yield {"data": evt.model_dump_json()}
                sent += 1
            
            if session["status"] in ("done", "error", "cancelled", "limit_reached"):
                yield {"data": json.dumps({"type": "stream_end", "status": session["status"]})}
                break
            
            await asyncio.sleep(0.5)
    
    return EventSourceResponse(generate())

@app.post("/stop/{session_id}")
async def stop_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Сессия не найдена")
    sessions[session_id]["cancelled"] = True
    return {"ok": True}

@app.get("/status/{session_id}")
async def get_status(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Сессия не найдена")
    s = sessions[session_id]
    return {
        "session_id": session_id,
        "status": s["status"],
        "goal": s["goal"],
        "steps_done": len([e for e in s["events"] if e.type == "result"]),
    }

@app.get("/health")
async def health():
    return {"ok": True, "sessions": len(sessions)}