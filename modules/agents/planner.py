
async def plan(goal: str) -> list:
    # minimalni planner (kasnije LLM)
    steps = []

    if "napravi" in goal or "build" in goal:
        steps = [
            "Analiziraj zahtjev",
            "Generiraj rješenje",
            "Testiraj i optimiziraj"
        ]
    else:
        steps = [
            "Analiza",
            "Rješenje"
        ]

    return steps
