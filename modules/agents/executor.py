
import re
from modules.tools.python_runner import run_python_code
import httpx
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

async def execute(step: str, goal: str) -> str:
    prompt = f"""
Ti si Executor agent unutar ATLAS OS.

Zadatak:
{goal}

Trenutni korak:
{step}

Pravila:
- konkretan output
- bez objašnjenja
- ako je kod → samo kod
"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 800
                }
            )

        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]

        return f"[ERROR {r.status_code}]"

    except Exception as e:
        return f"[EXEC ERROR] {e}"
