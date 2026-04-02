# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import json
import os

MEMORY_FILE = os.path.expanduser("~/atlas_os_v1/long_term_memory.json")

def save_to_memory(key, content):
    """Sprema važna iskustva i preferencije."""
    memory = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
    
    memory[key] = content
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)
    return "Memorija ažurirana."

def get_memory(key):
    """Izvlači spremljeno znanje."""
    if not os.path.exists(MEMORY_FILE): return None
    with open(MEMORY_FILE, 'r') as f:
        memory = json.load(f)
    return memory.get(key)
