# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

class Orchestrator:
    def __init__(self, planner, executor, critic):
        self.planner = planner
        self.executor = executor
        self.critic = critic

    async def run(self, user_input, context):
        try:
            # 1. PLAN
            plan = await self.planner.create_plan(user_input, context)

            # fallback ako planner faila
            if not plan:
                return "Planner nije vratio plan."

            # 2. EXECUTE
            result = await self.executor.execute(plan, context)

            # 3. EVALUATE
            evaluation = await self.critic.evaluate(user_input, result)

            # 4. RETRY (1 pokušaj)
            if isinstance(evaluation, dict) and not evaluation.get("ok", True):
                result = await self.executor.execute(plan, context)

            return result

        except Exception as e:
            return f"[ORCHESTRATOR ERROR] {str(e)}"
