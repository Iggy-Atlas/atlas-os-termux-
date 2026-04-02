# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import ast

def analyze_code(code: str) -> str:
    try:
        tree = ast.parse(code)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        return f"[ANALYSIS] Functions: {funcs}" if funcs else "[ANALYSIS] No functions found"
    except Exception as e:
        return f"[ANALYSIS ERROR] {e}"
