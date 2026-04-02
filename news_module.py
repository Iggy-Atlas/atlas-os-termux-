# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------


from duckduckgo_search import DDGS

def get_news(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=6))
            if not results:
                return ""

            lines = []
            for r in results:
                title = r.get("title","")
                src   = r.get("source","")
                lines.append(f"• {title} ({src})")

            return "\n".join(lines)
    except Exception as e:
        return f"[NEWS ERROR] {e}"
