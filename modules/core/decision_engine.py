# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


def decide(intent: str) -> list:
    if intent == "create":
        return ["plan", "generate_code", "execute"]
    if intent == "analyze":
        return ["analyze", "summarize"]
    if intent == "execute":
        return ["execute"]
    return ["chat"]
