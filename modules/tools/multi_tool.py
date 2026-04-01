def detect_tool(code: str) -> str:
    if "import matplotlib" in code:
        return "plot"
    if "requests" in code:
        return "web"
    return "python"
