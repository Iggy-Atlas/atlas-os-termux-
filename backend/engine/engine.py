from backend.tools.tool_bridge import handle_tool_request
from backend.tools.tool_executor import execute_tool
from backend.tools.tool_decider import decide_tool
from backend.engine.fallback import fallback_response

MAX_STEPS = 4

async def safe_ai(ai_callback, prompt):
    try:
        result = await ai_callback(prompt)
        if not result or not result[0]:
            return None
        return result
    except:
        return None

async def run_engine(user_msg: str, ai_callback):
    context = user_msg
    last_output = ""
    used_tools = []

    for step in range(MAX_STEPS):

        # HARD TOOL
        tool_result = handle_tool_request(context)
        if tool_result:
            return {
                "type": "tool",
                "output": tool_result
            }

        # AI DECISION
        decision_res = await safe_ai(ai_callback, f"DECIDE:\n{context}")
        if decision_res:
            decision_text, _ = decision_res
            try:
                import json
                decision = json.loads(decision_text)
            except:
                decision = {"use_tool": False}
        else:
            decision = {"use_tool": False}

        if decision.get("use_tool"):
            tool = decision.get("tool")
            args = decision.get("args", {})

            tool_output = execute_tool(tool, args)
            used_tools.append(tool)

            context = f"""
Korisnik: {user_msg}

Dosadašnji rezultat:
{last_output}

Tool {tool} vratio:
{tool_output}

Nastavi.
"""
            last_output = tool_output
            continue

        # FINAL AI
        final_res = await safe_ai(ai_callback, context)

        if final_res:
            final_output, model = final_res
            return {
                "type": "agent",
                "output": final_output,
                "steps": step + 1,
                "tools": used_tools,
                "model": model
            }

        # FALLBACK
        fb = fallback_response(user_msg)
        return fb

    # FINAL FALLBACK
    return fallback_response(user_msg)
