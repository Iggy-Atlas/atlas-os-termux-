# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

def improve(code: str, error: str) -> str:
    # jednostavan početak (Claude kasnije može upgrade)
    if "syntax" in error.lower():
        return code.replace("print ", "print(") + ")"
    return code
