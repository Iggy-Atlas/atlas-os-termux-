def check_intent(msg):
    msg = msg.lower()
    # Ako su ovo ključne riječi, NE pali web
    local_keywords = ["dobar si", "hvala", "tko si", "napravi file", "izbrisi", "pogledaj kôd", "popravi", "zdravo", "atlas"]
    if any(k in msg for k in local_keywords) and len(msg.split()) < 5:
        return "local"
    return "auto"
