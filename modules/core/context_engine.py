# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import os
from pathlib import Path

PROJECT_DIR = Path(os.path.expanduser("~/atlas_os_v1"))

def get_project_structure():
    """Vraća mapu projekta za bolji kontekst."""
    structure = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        if "venv" in root or "__pycache__" in root:
            continue
        level = root.replace(str(PROJECT_DIR), "").count(os.sep)
        indent = " " * 4 * level
        structure.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = " " * 4 * (level + 1)
        for f in files:
            if f.endswith((".py", ".md", ".json", ".sh")):
                structure.append(f"{sub_indent}{f}")
    return "\n".join(structure)

def read_file_content(file_path):
    """Sigurno čita sadržaj datoteke za analizu."""
    full_path = PROJECT_DIR / file_path
    if full_path.exists() and full_path.is_file():
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return "Greška pri čitanju datoteke."
    return "Datoteka ne postoji."
