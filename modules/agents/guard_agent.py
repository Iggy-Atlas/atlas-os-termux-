# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

BLOCKED = ["hack", "exploit", "ddos"]

def is_allowed(msg: str) -> bool:
    return not any(b in msg.lower() for b in BLOCKED)
