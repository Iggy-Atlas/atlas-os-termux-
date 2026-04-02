# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------



from modules.agents.planner import plan
from modules.agents.executor import execute

async def run_agent(goal: str) -> str:
    steps = await plan(goal)

    final_result = None

    for s in steps:
        r = await execute(s, goal)

        # uzmi samo NAJBITNIJI rezultat
        if any(k in s.lower() for k in ["generiraj", "rješenje", "napravi"]):
            final_result = r

    return final_result or "Nema rezultata."
