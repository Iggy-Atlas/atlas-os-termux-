import re

path = "main.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# novi blok (ULTRA SIGURAN)
block = """
            # ── IMAGE FORCE VISION ──
            if file_data and file_data.get("isImage"):
                print("[VISION] IMAGE DETECTED")

                img_data = file_data["data"]

                preview = {
                    "type": "image",
                    "data": img_data,
                    "mime": file_data.get("type", "image/jpeg")
                }

                vision_prompt = user_msg if user_msg else "Detaljno opisi ovu sliku."

                out, model = await call_vision(img_data, vision_prompt)

                if not out:
                    out = "Slika učitana, ali vision nije odgovorio."

                await save_msg("user", "[SLIKA]")
                await save_msg("assistant", out)

                await websocket.send_json({
                    "message": out,
                    "model": model or "VISION",
                    "tags": ["vision"],
                    "mode": "analysis",
                    "preview": preview
                })

                continue
"""

# ubaci odmah nakon parsiranja inputa
pattern = r'file_data\s*=\s*data\.get\("file"\)'
match = re.search(pattern, content)

if not match:
    print("❌ Nije pronađen file_data dio")
    exit()

insert_pos = match.end()

new_content = content[:insert_pos] + "\n" + block + content[insert_pos:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ IMAGE FLOW PATCH DONE")
