# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

def detect_intent(msg: str) -> str:
    m = msg.lower()
    if "napravi" in m or "create" in m:
        return "create"
    if "analiziraj" in m:
        return "analyze"
    if "pokreni" in m:
        return "execute"
    return "chat"
