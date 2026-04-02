# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


from duckduckgo_search import DDGS

class ResearchAgent:
    def search(self, query, max_results=3):
        try:
            # Koristimo context manager direktno umjesto instanciranja klase u __init__
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=max_results)]
                
                formatted = ""
                for i, r in enumerate(results, 1):
                    formatted += f"\n[{i}] {r['title']}\nURL: {r['href']}\nINFO: {r['body']}\n"
                
                return formatted if formatted else "Nema rezultata za taj upit."
        except Exception as e:
            return f"Greška pri pretrazi (HTTPX Bug): {str(e)}"
