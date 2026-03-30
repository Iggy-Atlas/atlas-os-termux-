def detect_action(message: str) -> dict:
    m = message.lower()

    if "napravi fajl" in m or "create file" in m:
        return {"action": "file_write"}

    if "procitaj fajl" in m or "read file" in m:
        return {"action": "file_read"}

    if "pokreni python" in m or "run python" in m:
        return {"action": "run_python"}

    if "pokreni komandu" in m or "run command" in m:
        return {"action": "run_shell"}

    if "listaj fajlove" in m or "list files" in m:
        return {"action": "list_files"}

    return {"action": None}
