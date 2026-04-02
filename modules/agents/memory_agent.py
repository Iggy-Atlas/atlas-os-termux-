# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import aiosqlite, json, os
from datetime import datetime

DB_PATH = 'database.db'

async def remember(user_msg, assistant_res):
    """Analizira dijalog i sprema ključne informacije u bazu."""
    # Ovdje Atlas odlučuje je li informacija vrijedna trajnog pamćenja
    # (npr. imena, preferencije, projekti, ključne odluke)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                content TEXT,
                category TEXT
            )
        """)
        
        # Logika za prepoznavanje bitnih stavki (osnovni filter)
        important_keywords = ['zovi me', 'moje ime', 'projekt', 'volim', 'ne volim', 'koristi', 'adresa', 'ključ']
        low_msg = user_msg.lower()
        
        if any(word in low_input for word in important_keywords):
            await db.execute(
                "INSERT INTO long_term_memory (timestamp, content, category) VALUES (?, ?, ?)",
                (timestamp, f"Korisnik je naveo: {user_msg}", 'user_preference')
            )
            await db.commit()

async def get_relevant_context(user_msg):
    """Pretražuje bazu za slične teme kako bi Atlas imao 'deja vu'."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Jednostavna pretraga po ključnim riječima (dok ne uvedemo Vector Embeddings)
        words = user_msg.split()
        context_parts = []
        
        for word in words:
            if len(word) > 3:
                cursor = await db.execute(
                    "SELECT content FROM long_term_memory WHERE content LIKE ? LIMIT 2",
                    (f'%{word}%',)
                )
                rows = await cursor.fetchall()
                for row in rows:
                    context_parts.append(row['content'])
        
        return "\n".join(set(context_parts)) if context_parts else ""
