# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import os

def check_access(path):
    path = os.path.abspath(os.path.expanduser(path))
    safe_zone = os.path.expanduser("~/atlas_os_v1")
    if path.startswith(safe_zone):
        return "AUTHORIZED"
    return "PENDING_PERMISSION"
