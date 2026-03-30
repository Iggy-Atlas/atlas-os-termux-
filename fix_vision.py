import re

path = "main.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_func = '''
async def call_vision(image_data: str, prompt: str) -> tuple:
    b64 = image_data.split(",")[-1] if "," in image_data else image_data
    model = "meta-llama/llama-4-maverick-17b-128e-instruct"

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": 800,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt or "Detaljno opisi sliku."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64}"
                                    }
                                }
                            ]
                        }
                    ]
                }
            )

            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], "VISION"

            return f"[VISION ERROR {r.status_code}]", "ERROR"

    except Exception as e:
        return f"[VISION EXCEPTION] {e}", "ERROR"
'''

pattern = r'async def call_vision.*?return .*?\n'
new_content = re.sub(pattern, new_func + "\n", content, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("VISION PATCH DONE")
