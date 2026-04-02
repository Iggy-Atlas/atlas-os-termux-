# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


from modules.agents.retry_agent import should_retry
from modules.agents.self_improve import improve

async def run_loop(execute_fn, code: str):
    attempts = 0
    output = ""

    while attempts < 3:
        output = await execute_fn(code)

        if not should_retry(output):
            return output

        code = improve(code, output)
        attempts += 1

    return output
