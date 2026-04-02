# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------



async def plan(goal: str) -> list:
    # minimalni planner (kasnije LLM)
    steps = []

    if "napravi" in goal or "build" in goal:
        steps = [
            "Analiziraj zahtjev",
            "Generiraj rješenje",
            "Testiraj i optimiziraj"
        ]
    else:
        steps = [
            "Analiza",
            "Rješenje"
        ]

    return steps
