# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from .action_detector import detect_action
from .tool_executor import execute_tool

def handle_tool_request(user_msg: str) -> str | None:
    action_data = detect_action(user_msg)
    action = action_data.get("action")

    if not action:
        return None

    args = {}

    # FILE WRITE (FIXED PARSING)
    if action == "file_write":
        try:
            parts = user_msg.split(" ")
            path = parts[2]

            if "sadržajem" in user_msg:
                content = user_msg.split("sadržajem",1)[1].strip()
            elif "sa sadržajem" in user_msg:
                content = user_msg.split("sa sadržajem",1)[1].strip()
            else:
                return "Format: napravi fajl ime.txt sa sadržajem tekst"

            args = {"path": path, "content": content}
        except:
            return "Format: napravi fajl ime.txt sa sadržajem tekst"

    # FILE READ
    elif action == "file_read":
        try:
            path = user_msg.split(" ")[2]
            args = {"path": path}
        except:
            return "Format: procitaj fajl ime.txt"

    # RUN PYTHON
    elif action == "run_python":
        code = user_msg.replace("pokreni python", "").replace("run python", "").strip()
        args = {"code": code}

    # SHELL
    elif action == "run_shell":
        cmd = user_msg.replace("pokreni komandu", "").replace("run command", "").strip()
        args = {"command": cmd}

    # LIST FILES
    elif action == "list_files":
        args = {"path": "."}

    return execute_tool(action, args)
