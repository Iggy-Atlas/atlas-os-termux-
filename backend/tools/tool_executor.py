# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


from .tool_registry import TOOLS

def execute_tool(action: str, args: dict) -> str:
    tool = TOOLS.get(action)

    if not tool:
        return "Nepoznat alat."

    try:
        return tool(**args)
    except Exception as e:
        return f"[TOOL ERROR] {e}"
