# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import aiosqlite
from datetime import datetime

DB = "database.db"

async def save_task(user_msg: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            timestamp TEXT
        )
        """)
        await db.execute(
            "INSERT INTO tasks (content, timestamp) VALUES (?,?)",
            (user_msg[:300], str(datetime.now()))
        )
        await db.commit()

async def get_last_task():
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT content FROM tasks ORDER BY id DESC LIMIT 1"
        ) as c:
            row = await c.fetchone()
    return row[0] if row else ""
