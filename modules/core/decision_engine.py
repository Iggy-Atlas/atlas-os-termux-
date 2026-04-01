def decide(intent: str) -> list:
    if intent == "create":
        return ["plan", "generate_code", "execute"]
    if intent == "analyze":
        return ["analyze", "summarize"]
    if intent == "execute":
        return ["execute"]
    return ["chat"]
