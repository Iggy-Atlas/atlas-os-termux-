import json

async def decide_tool(user_msg: str, ai_callback):
    """
    AI odlučuje da li treba tool.

    Vraća:
    {
        "use_tool": bool,
        "tool": "file_write",
        "args": {...}
    }
    """

    prompt = f"""
Ti si AI agent koji odlučuje da li treba koristiti sistemski alat.

Dostupni alati:
- file_write(path, content)
- file_read(path)
- run_python(code)
- run_shell(command)
- list_files(path)

Vrati ISKLJUČIVO JSON bez objašnjenja.

Format:
{{
  "use_tool": true/false,
  "tool": "ime_alata",
  "args": {{...}}
}}

Poruka:
{user_msg}
"""

    result, _ = await ai_callback(prompt)

    try:
        cleaned = result.strip().replace("```json","").replace("```","")
        data = json.loads(cleaned)
        return data
    except:
        return {"use_tool": False}
