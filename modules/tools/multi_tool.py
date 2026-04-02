# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

def detect_tool(code: str) -> str:
    if "import matplotlib" in code:
        return "plot"
    if "requests" in code:
        return "web"
    return "python"
