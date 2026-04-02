# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import os
import ast
import aiosqlite
from pathlib import Path

DB_PATH = os.path.expanduser("~/atlas_os_v1/database.db")
SAFE_ZONE = os.path.expanduser("~/atlas_os_v1")

async def index_project():
    """Skenira i indeksira sve Python datoteke u sigurnoj zoni."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS code_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                name TEXT,
                type TEXT,
                line_number INTEGER
            )
        """)
        await db.execute("DELETE FROM code_index") # Osvježavamo indeks
        
        for root, _, files in os.walk(SAFE_ZONE):
            if "venv" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    await index_file(db, path)
        await db.commit()

async def index_file(db, path):
    """Analizira Python datoteku i izvlači funkcije i klase."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
            rel_path = os.path.relpath(path, SAFE_ZONE)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    await db.execute(
                        "INSERT INTO code_index (file_path, name, type, line_number) VALUES (?, ?, ?, ?)",
                        (rel_path, node.name, "function", node.lineno)
                    )
                elif isinstance(node, ast.ClassDef):
                    await db.execute(
                        "INSERT INTO code_index (file_path, name, type, line_number) VALUES (?, ?, ?, ?)",
                        (rel_path, node.name, "class", node.lineno)
                    )
    except:
        pass
