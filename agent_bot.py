import asyncio
import json
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from openai import AsyncOpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WORK_DIR = os.getenv("WORK_DIR", "/root/workspace")
OPENCODE_CMD = os.getenv("OPENCODE_CMD", "opencode")
MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))
ALLOWED_USER = int(os.getenv("ALLOWED_USER", "0"))

dialog_history: list[dict] = []
agent_task: asyncio.Task | None = None
is_running = False

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = f"""Ты — автономный AI-агент разработчика. Работаешь с репозиторием в {WORK_DIR}.

У тебя есть инструмент: OpenCode CLI — выполняет задачи в репозитории (чинит код, пишет тесты, рефакторит).

Когда пользователь даёт задачу — планируй шаги, вызывай OpenCode, анализируй результат, продолжай пока не готово.
Когда пользователь просто общается — отвечай как ассистент, помни контекст.

Отвечай ТОЛЬКО JSON, один из трёх форматов:

Вызов OpenCode:
{{"action": "opencode", "command": "задача для OpenCode", "reasoning": "почему этот шаг"}}

Обычный ответ:
{{"action": "reply", "message": "твой ответ пользователю"}}

Задача выполнена:
{{"action": "done", "message": "что было сделано"}}

ТОЛЬКО JSON. Никакого текста вне JSON."""


async def run_opencode(command: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            OPENCODE_CMD, "run", command,
            cwd=WORK_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="replace").strip()
        return output if output else "Done."
    except asyncio.TimeoutError:
        return "TIMEOUT: OpenCode timed out"
    except FileNotFoundError:
        return f"ERROR: OpenCode not found: {OPENCODE_CMD}"
    except Exception as e:
        return f"ERROR: {e}"


async def call_gpt() -> dict:
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + dialog_history,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(response.choices[0].message.content)


async def process_message(chat_id: int, user_text: str):
    global is_running

    dialog_history.append({"role": "user", "content": user_text})
    is_running = True
    step = 0

    try:
        while is_running and step < MAX_STEPS:
            try:
                decision = await call_gpt()
            except Exception as e:
                await bot.send_message(chat_id, f"GPT error: {e}")
                break

            action = decision.get("action", "reply")

            if action == "reply":
                await bot.send_message(chat_id, decision.get("message", "..."))
                dialog_history.append({"role": "assistant", "content": json.dumps(decision)})
                break

            elif action == "opencode":
                step += 1
                command = decision.get("command", "")
                reasoning = decision.get("reasoning", "")

                await bot.send_message(
                    chat_id,
                    f"Step {step}: {reasoning}\n{command}",
                    parse_mode="Markdown"
                )

                result = await run_opencode(command)
                result_short = result[:600] + ("..." if len(result) > 600 else "")

                await bot.send_message(
                    chat_id,
                    f"```\n{result_short}\n```",
                    parse_mode="Markdown"
                )

                dialog_history.append({"role": "assistant", "content": json.dumps(decision)})
                dialog_history.append({"role": "user", "content": f"OpenCode result:\n{result[:1000]}"})

            elif action == "done":
                await bot.send_message(chat_id, f"Done: {decision.get('message', 'Done!')}")
                dialog_history.append({"role": "assistant", "content": json.dumps(decision)})
                break

            else:
                await bot.send_message(chat_id, f"Unknown action: {action}")
                break

        if step >= MAX_STEPS:
            await bot.send_message(chat_id, f"Limit {MAX_STEPS} steps. Write 'continue' to proceed.")

    finally:
        is_running = False


def is_allowed(message: Message) -> bool:
    if ALLOWED_USER == 0:
        return True
    return message.from_user.id == ALLOWED_USER


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        return
    await message.answer(
        "Codex Agent v2\n\n"
        "Just write a task - I'll do it.\n"
        "Remembers conversation context.\n\n"
        "/stop - stop agent\n"
        "/clear - reset history\n"
        "/status - status",
        parse_mode="Markdown"
    )


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    global is_running
    if not is_allowed(message):
        return
    is_running = False
    await message.answer("Stopping after current step.")


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    global dialog_history
    if not is_allowed(message):
        return
    dialog_history = []
    await message.answer("History cleared.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_allowed(message):
        return
    status = "Running" if is_running else "Idle"
    msgs = len([m for m in dialog_history if m["role"] == "user"])
    await message.answer(f"{status}\nContext messages: {msgs}")


@dp.message()
async def handle_message(message: Message):
    if not is_allowed(message):
        await message.answer("Access denied.")
        return

    if is_running:
        await message.answer("Busy. /stop to cancel.")
        return

    thinking = await message.answer("Thinking...")

    await process_message(message.chat.id, message.text)

    try:
        await bot.delete_message(message.chat.id, thinking.message_id)
    except Exception:
        pass


async def main():
    print(f"Codex Agent Bot v2")
    print(f"WORK_DIR: {WORK_DIR}")
    print(f"ALLOWED_USER: {ALLOWED_USER or 'all'}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())