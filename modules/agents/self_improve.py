def improve(code: str, error: str) -> str:
    # jednostavan početak (Claude kasnije može upgrade)
    if "syntax" in error.lower():
        return code.replace("print ", "print(") + ")"
    return code
