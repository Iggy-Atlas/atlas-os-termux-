import re

path = "main.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# nova funkcija (čista)
new_func = """async def call_vision(image_data: str, prompt: str) -> tuple:
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
"""

# 🔥 NAĐI početak funkcije
start = re.search(r'async def call_vision\(', content)
if not start:
    print("❌ call_vision nije pronađen")
    exit()

start_idx = start.start()

# 🔥 NAĐI kraj funkcije (sljedeći async def ili EOF)
end = re.search(r'\nasync def ', content[start_idx + 10:])
if end:
    end_idx = start_idx + 10 + end.start()
else:
    end_idx = len(content)

# zamjena
new_content = content[:start_idx] + new_func + "\n\n" + content[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ CLEAN VISION PATCH DONE")
