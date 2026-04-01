BLOCKED = ["os.remove", "rm -rf", "subprocess", "sys.exit"]

def is_safe(code: str) -> bool:
    return not any(b in code for b in BLOCKED)
