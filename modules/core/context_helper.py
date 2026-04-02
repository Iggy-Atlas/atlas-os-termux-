import aiosqlite, os

async def get_code_context(user_msg):
    """Izvlači relevantne dijelove koda iz indeksa na temelju upita."""
    DB_PATH = os.path.expanduser("~/atlas_os_v1/database.db")
    context = ""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # Tražimo ključne riječi u imenu funkcije ili datoteke
            words = [w for w in user_msg.split() if len(w) > 3]
            for word in words:
                cursor = await db.execute(
                    "SELECT * FROM code_index WHERE name LIKE ? OR file_path LIKE ? LIMIT 5",
                    (f"%{word}%", f"%{word}%")
                )
                rows = await cursor.fetchall()
                for row in rows:
                    context += f"\n- {row["type"].upper()}: {row["name"]} (Putanja: {row["file_path"]})"
        return f"\n[LOKALNI INDEKS KODA]:{context}" if context else ""
    except:
        return ""
