from duckduckgo_search import DDGS

def get_live_info(query):
    """Pretražuje internet za najnovije informacije."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results: return "Nema rezultata na mreži."
            summary = "\n".join([f"- {r['title']}: {r['body']} ({r['href']})" for r in results])
            return f"REZULTATI PRETRAGE:\n{summary}"
    except Exception as e:
        return f"Greška pri pretraživanju mreže: {e}"
