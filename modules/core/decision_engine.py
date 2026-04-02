# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

def decide(intent: str) -> list:
    if intent == "create":
        return ["plan", "generate_code", "execute"]
    if intent == "analyze":
        return ["analyze", "summarize"]
    if intent == "execute":
        return ["execute"]
    return ["chat"]
