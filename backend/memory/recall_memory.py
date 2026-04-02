# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from .cloud_memory import list_memories

def recall():
    try:
        mems = list_memories()
        return "Zadnje memorije:\n" + "\n".join(mems)
    except:
        return "Memory error."
