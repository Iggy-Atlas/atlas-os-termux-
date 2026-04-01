def inject_web_results(user_msg: str, web_data: str, lang: str = "hr") -> str:
    if not web_data:
        return "Nema dostupnih web podataka za ovaj upit."
    return f"""
KORISTI ISKLJUČIVO ove podatke:

{web_data}

Pitanje: {user_msg}

Odgovori konkretno iz podataka.
Ako nema podataka → reci da nema.
"""

def build_search_system_prompt(lang: str = "hr") -> str:
    return (
        "PRAVILA ZA WEB SEARCH:\n"
        "- Koristi SAMO dostavljene web rezultate\n"
        "- Ne izmišljaj informacije\n"
        "- Ako nema podataka → jasno reci\n"
    )

def has_web_data(text: str) -> bool:
    return bool(text and text.strip())
