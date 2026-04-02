# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import os
import subprocess

BASE = os.path.join(os.path.expanduser("~"), "atlas_os_v1")

def create_file(name: str, content: str) -> str:
    path = os.path.join(BASE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"[FILE CREATED] {name}"

def run_file(name: str) -> str:
    path = os.path.join(BASE, name)

    result = subprocess.run(
        ["python3", path],
        capture_output=True,
        text=True
    )

    if result.stderr:
        return f"[ERROR]\n{result.stderr[:300]}"

    return f"[OUTPUT]\n{result.stdout}"
