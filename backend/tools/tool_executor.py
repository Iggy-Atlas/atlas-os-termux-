from .tool_registry import TOOLS

def execute_tool(action: str, args: dict) -> str:
    tool = TOOLS.get(action)

    if not tool:
        return "Nepoznat alat."

    try:
        return tool(**args)
    except Exception as e:
        return f"[TOOL ERROR] {e}"
