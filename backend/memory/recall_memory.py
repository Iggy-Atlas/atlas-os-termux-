# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


from .cloud_memory import list_memories

def recall():
    try:
        mems = list_memories()
        return "Zadnje memorije:\n" + "\n".join(mems)
    except:
        return "Memory error."
