# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

BLOCKED = ["os.remove", "rm -rf", "subprocess", "sys.exit"]

def is_safe(code: str) -> bool:
    return not any(b in code for b in BLOCKED)
