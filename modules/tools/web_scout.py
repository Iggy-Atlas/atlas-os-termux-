import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

def search_web(query):
    # Uzimamo isključivo ključeve za Search
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        return "Greška: Nedostaju ključevi za Google Search u .env datoteci."

    try:
        # Koristimo službeni Google klijent (ne šalje Access Token zaglavlje!)
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=5).execute()
        
        results = []
        if 'items' in res:
            for item in res['items']:
                results.append(f"{item['title']}: {item['snippet']} ({item['link']})")
            return "\n".join(results)
        return "Nema rezultata za taj upit."
    except Exception as e:
        return f"Google API Greška: {str(e)}"
