BLOCKED = ["hack", "exploit", "ddos"]

def is_allowed(msg: str) -> bool:
    return not any(b in msg.lower() for b in BLOCKED)
