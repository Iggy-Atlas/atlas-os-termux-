# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from modules.tools.file_agent import create_file, run_file

def route_tool(msg: str):
    if msg.startswith("create_file:"):
        _, name, content = msg.split(":", 2)
        return create_file(name, content)

    if msg.startswith("run_file:"):
        _, name = msg.split(":", 1)
        return run_file(name)

    return None
