# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


def detect_tool(code: str) -> str:
    if "import matplotlib" in code:
        return "plot"
    if "requests" in code:
        return "web"
    return "python"
