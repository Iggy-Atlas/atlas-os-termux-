# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


def adapt_to_user(text):
    """
    Analizira dolazni tekst i naređuje sustavu da odgovori na istom jeziku.
    Ako detektira engleski, cijeli 'System Prompt' se interno tretira kao engleski.
    """
    # Atlasu dajemo uputu da prati jezik korisnika
    directive = "IMPORTANT: Respond in the SAME LANGUAGE as the user. If the user speaks English, use English. If Croatian, use Croatian. Maintain a professional, neutral tone."
    return f"{text}\n\n[LANG_AUTO_DETECT]: {directive}"

def get_ui_labels(lang_code):
    """Vraća prijevode za UI elemente na temelju jezika."""
    translations = {
        "hr": {"settings": "Postavke", "search": "Traži", "status": "Status sustava"},
        "en": {"settings": "Settings", "search": "Search", "status": "System Status"},
        "de": {"settings": "Einstellungen", "search": "Suche", "status": "Systemstatus"}
    }
    return translations.get(lang_code, translations["en"])
