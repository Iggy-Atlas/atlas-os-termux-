# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from .cloud_memory import save_memory

def auto_save(user_msg: str, response: str):
    try:
        data = {
            "user": user_msg[:300],
            "assistant": response[:500]
        }
        save_memory(data)
    except:
        pass
