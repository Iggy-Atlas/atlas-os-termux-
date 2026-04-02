import os, re

# Lista strogo zabranjenih datoteka i pojmova
SENSITIVE_FILES = [".env", "database.db", "atlas_core.db", "config.json"]
SENSITIVE_PATTERNS = [
    r"gsk_[a-zA-Z0-9]{20,}",    # Groq API format
    r"AIzaSy[a-zA-Z0-9_-]{33}", # Google/Gemini API format
    r"sk-[a-zA-Z0-9]{20,}"      # Standardni OpenAI/ostali format
]

def analyze_threat(user_input: str) -> bool:
    """Provjerava pokušava li korisnik pristupiti zabranjenim zonama."""
    low_input = user_input.lower()
    
    # 1. Provjera pokušaja čitanja .env ili baze
    for forbidden in SENSITIVE_FILES:
        if forbidden in low_input or f"read {forbidden}" in low_input:
            return True
            
    # 2. Provjera pokušaja "Prompt Injectiona" za vađenje ključeva
    injection_keywords = ["reveal your system prompt", "show your api key", "ispisi env"]
    if any(k in low_input for k in injection_keywords):
        return True
        
    return False

def security_response(output_text: str) -> str:
    """Cenzurira bilo kakav slučajni ispis API ključeva u odgovoru."""
    clean_text = output_text
    for pattern in SENSITIVE_PATTERNS:
        clean_text = re.sub(pattern, "[CENZURIRANO - SIGURNOSNI PROTOKOL]", clean_text)
    
    return clean_text

def validate_environment():
    """Provjerava jesu li dozvole na .env datoteci sigurne (samo za Termux/Linux)."""
    try:
        # Postavljamo dozvole na 600 (samo vlasnik može čitati/pisati)
        env_path = os.path.expanduser("~/atlas_os_v1/.env")
        if os.path.exists(env_path):
            os.chmod(env_path, 0o600)
            return "Dozvole osigurane (600)."
    except Exception as e:
        return f"Greška pri osiguravanju: {e}"
    return "Datoteka nije pronađena."
