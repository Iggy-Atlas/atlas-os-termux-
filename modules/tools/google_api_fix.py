import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

def official_google_search(query):
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=3).execute()
        
        search_results = []
        if 'items' in res:
            for item in res['items']:
                search_results.append(f"{item['title']}: {item['snippet']} ({item['link']})")
            return "\n".join(search_results)
        return "Nema rezultata."
    except Exception as e:
        return f"Greška u API-ju: {str(e)}"

# Testiramo odmah
print(official_google_search("cijena nafte po barelu danas"))
