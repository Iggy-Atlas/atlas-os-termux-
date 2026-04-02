# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from duckduckgo_search import DDGS

def atlas_search(query, max_results=3):
    print(f"🔍 Atlas pretražuje internet za: '{query}'...")
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            if not results:
                return "Nisam pronašao ništa relevantno."
            
            formatted_results = "\n".join([f"- {r['title']}: {r['href']}\n  {r['body']}\n" for r in results])
            return formatted_results
    except Exception as e:
        return f"❌ Greška pri pretraživanju: {e}"

if __name__ == "__main__":
    # Test pretrage
    print(atlas_search("Termux latest version 2026"))
