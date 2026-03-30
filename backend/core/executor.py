class Executor:
    def __init__(self, ai_call):
        self.ai_call = ai_call

    async def execute(self, plan, context):
        try:
            goal = plan.get("goal", "")
            steps = plan.get("steps", [])

            # fallback ako plan nije validan
            if not goal:
                return "Executor: nema goal."

            steps_text = "\n".join(f"- {s}" for s in steps)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ti si execution engine AI sistema.\n"
                        "Dobijaš PLAN i moraš ga izvršiti.\n\n"
                        "PRAVILA:\n"
                        "- prati korake\n"
                        "- budi konkretan\n"
                        "- ne opisuj plan, nego GA IZVRSI\n"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"CILJ:\n{goal}\n\n"
                        f"KORACI:\n{steps_text}\n\n"
                        "Izvrši zadatak."
                    )
                }
            ]

            result, _ = await self.ai_call(messages, mode="analysis")
            return result

        except Exception as e:
            return f"[EXECUTOR ERROR] {str(e)}"
