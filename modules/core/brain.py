from modules.agents.intent_agent import detect_intent
from modules.agents.memory_agent import remember

def process_input(msg: str):
    intent = detect_intent(msg)
    remember(msg)
    return intent
