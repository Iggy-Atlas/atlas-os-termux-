# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import subprocess
import tempfile

async def run_python_code(code: str) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as f:
            f.write(code.encode("utf-8"))
            path = f.name

        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=5
        )

        out = result.stdout.strip()
        err = result.stderr.strip()

        if err:
            return f"[ERROR]\n{err}"

        return f"[OUTPUT]\n{out}"

    except Exception as e:
        return f"[RUN ERROR] {e}"
