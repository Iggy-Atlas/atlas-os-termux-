# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import subprocess

def run_python_file(path: str) -> str:
    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=10
        )

        out = result.stdout.strip()
        err = result.stderr.strip()

        if err:
            return f"[ERROR]\n{err[:300]}"
        return f"[OUTPUT]\n{out}"

    except subprocess.TimeoutExpired:
        return "[ERROR]\nTimeout"
    except Exception as e:
        return f"[ERROR]\n{str(e)}"
