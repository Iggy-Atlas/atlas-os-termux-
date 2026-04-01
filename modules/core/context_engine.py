from modules.agents.memory_agent import recall

def build_context(msg: str) -> str:
    mem = recall()
    return f"{mem}\n\nUSER: {msg}"
