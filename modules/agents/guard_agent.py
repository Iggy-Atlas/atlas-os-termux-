# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


BLOCKED = ["hack", "exploit", "ddos"]

def is_allowed(msg: str) -> bool:
    return not any(b in msg.lower() for b in BLOCKED)
