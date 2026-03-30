from backend.tools.tool_bridge import handle_tool_request

def fallback_response(user_msg: str) -> dict:
    """
    Radi kada AI ne odgovara
    """

    # 1. pokušaj tool
    tool = handle_tool_request(user_msg)
    if tool:
        return {
            "type": "fallback_tool",
            "output": tool
        }

    # 2. basic heuristika
    m = user_msg.lower()

    if "fajl" in m:
        return {
            "type": "fallback",
            "output": "Mogu raditi sa fajlovima. Probaj: napravi fajl ime.txt sa sadržajem tekst"
        }

    if "folder" in m or "list" in m:
        return {
            "type": "fallback",
            "output": "Mogu prikazati fajlove. Probaj: listaj fajlove"
        }

    if "python" in m:
        return {
            "type": "fallback",
            "output": "Mogu pokrenuti Python kod. Probaj: pokreni python print('hello')"
        }

    return {
        "type": "fallback",
        "output": "AI trenutno nije dostupan. Pokušaj ponovo ili koristi komande (fajl, python, shell)."
    }
