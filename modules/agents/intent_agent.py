def detect_intent(msg: str) -> str:
    m = msg.lower()
    if "napravi" in m or "create" in m:
        return "create"
    if "analiziraj" in m:
        return "analyze"
    if "pokreni" in m:
        return "execute"
    return "chat"
