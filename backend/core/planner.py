# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import json

class Planner:
    def __init__(self, ai_call):
        self.ai_call = ai_call

    async def create_plan(self, user_input, context):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ti si planner za AI sistem.\n"
                        "Tvoj zadatak je pretvoriti korisnikov zahtjev u jasan plan.\n\n"
                        "VRATI ISKLJUCIVO JSON u formatu:\n"
                        "{\n"
                        '  "goal": "string",\n'
                        '  "steps": ["korak1", "korak2", "..."]\n'
                        "}\n\n"
                        "Bez objasnjenja. Bez teksta van JSON-a."
                    )
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ]

            result, _ = await self.ai_call(messages, mode="analysis")

            # pokušaj parsiranja
            cleaned = result.strip().replace("```json", "").replace("```", "").strip()

            try:
                plan = json.loads(cleaned)
                return plan
            except:
                # fallback plan ako LLM zabrlja
                return {
                    "goal": user_input,
                    "steps": ["razmisli", "odgovori"]
                }

        except Exception as e:
            return {
                "goal": user_input,
                "steps": ["error fallback"]
            }
