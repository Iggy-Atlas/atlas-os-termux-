from modules.tools.media_agent import process_image, extract_audio
import asyncio
from modules.agents.orchestrator import run_agent
from modules.news import handle_news

async def handle_modules(user_msg: str):
    if user_msg.lower().startswith("obradi sliku"):
        return {"message": "Spreman za obradu slike... Pošaljite file.", "model": "MEDIA", "tags": ["image"], "mode": "media"}
    """Optimizirani Atlas Router v18.3 - Brzi odziv."""
    low_msg = user_msg.lower()

    # 1. NEWS (Brza provjera bez dodatne logike)
    news = handle_news(user_msg)
    if news:
        return {"message": news, "model": "NEWS", "tags": ["web"], "mode": "search"}

    # 2. AGENT / AUTO
    if low_msg.startswith("auto ") or low_msg.startswith("napravi "):
        goal = user_msg[5:] if low_msg.startswith("auto ") else user_msg[8:]
        # Direktno proslijeđivanje agentu
        result = await run_agent(goal)
        return {"message": result, "model": "AGENT", "tags": ["auto"], "mode": "auto"}

    # 3. PASS-THROUGH
    # Ako nije ništa od navedenog, vraćamo None i puštamo main.py da odradi LLM poziv
    # To eliminira duplu inicijalizaciju varijabli u routeru!
    return None
