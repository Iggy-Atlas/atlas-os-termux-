from modules.agents.intent_agent import detect_intent
from modules.agents.memory_agent import remember
import asyncio

def process_input(msg: str):
    """Analizira poruku i sprema je u memoriju."""
    intent = detect_intent(msg)
    # Pokrećemo remember u pozadini ako je sinkron, 
    # ili ga ostavljamo ovako ako je obična funkcija.
    try:
        remember(msg)
    except Exception:
        pass
    return intent
