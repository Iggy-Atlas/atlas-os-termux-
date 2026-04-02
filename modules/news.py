# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------



import requests
import xml.etree.ElementTree as ET

def fetch_rss(url):
    try:
        r = requests.get(url, timeout=5)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")

        results = []
        for item in items[:6]:
            title = item.find("title")
            if title is not None:
                results.append(title.text.strip())

        return results
    except:
        return []

def detect_region(msg: str) -> str:
    m = msg.lower()

    if any(k in m for k in ["bosna","bih","bosanske","bosni"]):
        return "bih"

    if any(k in m for k in ["hrvatska","hrvatske","croatia"]):
        return "hr"

    if any(k in m for k in ["njema","germany","deutschland"]):
        return "de"

    return "global"

def handle_news(msg: str) -> str | None:
    m = msg.lower()

    if not any(k in m for k in ["vijesti","news","naslovi"]):
        return None

    region = detect_region(m)

    sources = []

    if region == "bih":
        sources = [
            "https://www.klix.ba/rss",
            "https://avaz.ba/rss"
        ]

    elif region == "hr":
        sources = [
            "https://www.vecernji.hr/feeds/latest",
            "https://www.jutarnji.hr/rss"
        ]

    elif region == "de":
        sources = [
            "https://www.spiegel.de/schlagzeilen/tops/index.rss",
            "https://www.welt.de/feeds/latest.rss"
        ]

    else:
        sources = [
            "https://www.bbc.com/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss"
        ]

    all_news = []

    for src in sources:
        all_news += fetch_rss(src)

    if not all_news:
        return "Nema dostupnih vijesti."

    return "\n".join(f"• {n}" for n in all_news[:10])
