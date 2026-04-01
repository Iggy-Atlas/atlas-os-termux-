
from modules.agents.orchestrator import run_agent

from modules.news import handle_news

async def handle_modules(user_msg: str):
    # NEWS
    news = handle_news(user_msg)
    if news:
        return {
            "message": news,
            "model": "NEWS",
            "tags": ["web"],
            "mode": "search"
        }

    
    # AGENT TRIGGER
    if user_msg.lower().startswith("auto "):
        result = await run_agent(user_msg[5:])
        return {
            "message": result,
            "model": "AGENT",
            "tags": ["auto"],
            "mode": "auto"
        }

    return None
