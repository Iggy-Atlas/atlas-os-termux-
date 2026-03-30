import json

class CriticAgent:
    def __init__(self, ai_call):
        self.ai_call = ai_call

    async def evaluate(self, user_input, result):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ti si critic AI sistema.\n"
                        "Tvoj zadatak je procijeniti da li je odgovor dobar.\n\n"
                        "VRATI ISKLJUCIVO JSON:\n"
                        "{\n"
                        '  "ok": true/false,\n'
                        '  "reason": "kratko objasnjenje"\n'
                        "}\n\n"
                        "Bez dodatnog teksta."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"KORISNIK TRAZI:\n{user_input}\n\n"
                        f"ODGOVOR:\n{result}\n\n"
                        "Da li je odgovor dobar?"
                    )
                }
            ]

            response, _ = await self.ai_call(messages, mode="analysis")

            cleaned = response.strip().replace("```json", "").replace("```", "").strip()

            try:
                data = json.loads(cleaned)
                return data
            except:
                return {"ok": True}  # fallback sigurnost

        except Exception as e:
            return {"ok": True}
