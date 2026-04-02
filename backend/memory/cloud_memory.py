# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import os
import requests
import json
from datetime import datetime

ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN", "")

UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=media"


def _headers():
    return {
        "Authorization": "Bearer " + ACCESS_TOKEN,
        "Content-Type": "application/json"
    }


def save_memory(data):
    if not ACCESS_TOKEN:
        return "ERROR: Missing GOOGLE_ACCESS_TOKEN"

    filename = "atlas_mem_" + str(int(datetime.now().timestamp())) + ".json"

    r = requests.post(
        UPLOAD_URL,
        headers=_headers(),
        data=json.dumps(data)
    )

    if r.status_code in (200, 201):
        return "Saved"
    else:
        return "ERROR: " + str(r.status_code)


def list_memories(limit=5):
    if not ACCESS_TOKEN:
        return ["ERROR: Missing GOOGLE_ACCESS_TOKEN"]

    url = "https://www.googleapis.com/drive/v3/files?pageSize=20"

    r = requests.get(url, headers=_headers())

    if r.status_code != 200:
        return ["ERROR: " + str(r.status_code)]

    files = r.json().get("files", [])
    return [f.get("name", "Untitled") for f in files[:limit]]


def test_memory():
    return save_memory({"msg": "atlas radi"})
