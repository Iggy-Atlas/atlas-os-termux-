# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import re

FORBIDDEN_PATTERNS = [
    r'__', r'import', r'open\(', r'exec\(', r'eval\('
]

def validate_code(code: str) -> dict:
    for p in FORBIDDEN_PATTERNS:
        if re.search(p, code):
            return {"safe": False, "reason": f"Blocked pattern: {p}"}
    return {"safe": True}

def validate_url(url: str) -> dict:
    blocked = ["127.0.0.1", "localhost", "0.0.0.0", "169.254"]
    for b in blocked:
        if b in url:
            return {"safe": False, "reason": f"Blocked URL: {b}"}
    return {"safe": True}

def safe_error(msg: str, module: str) -> str:
    return f'{{"error": "{msg}", "module": "{module}"}}'
