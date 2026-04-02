# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

from .executor_tools import file_write, file_read, run_python, run_shell, list_files

TOOLS = {
    "file_write": file_write,
    "file_read": file_read,
    "run_python": run_python,
    "run_shell": run_shell,
    "list_files": list_files,
}
