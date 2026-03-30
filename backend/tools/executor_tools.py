import os
import subprocess
from datetime import datetime

BASE_PATH = os.path.expanduser("~/atlas_os_v1")

def _safe_path(path: str) -> str:
    path = path.strip().strip('"').strip("'")
    if not os.path.isabs(path):
        path = os.path.join(BASE_PATH, path)
    return os.path.abspath(path)

# ─────────────────────────────
# FILE WRITE
# ─────────────────────────────
def file_write(path: str, content: str) -> str:
    try:
        full_path = _safe_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Fajl zapisan: {full_path}"
    except Exception as e:
        return f"[FILE WRITE ERROR] {e}"

# ─────────────────────────────
# FILE READ
# ─────────────────────────────
def file_read(path: str) -> str:
    try:
        full_path = _safe_path(path)
        if not os.path.exists(full_path):
            return "Fajl ne postoji."

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()[:4000]
    except Exception as e:
        return f"[FILE READ ERROR] {e}"

# ─────────────────────────────
# RUN PYTHON
# ─────────────────────────────
def run_python(code: str) -> str:
    try:
        temp_file = os.path.join(BASE_PATH, "temp_exec.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True,
            text=True,
            timeout=15
        )

        return result.stdout or result.stderr or "Nema outputa."
    except Exception as e:
        return f"[PYTHON ERROR] {e}"

# ─────────────────────────────
# SHELL COMMAND
# ─────────────────────────────
def run_shell(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"[SHELL ERROR] {e}"

# ─────────────────────────────
# LIST FILES
# ─────────────────────────────
def list_files(path: str = ".") -> str:
    try:
        full_path = _safe_path(path)
        if not os.path.exists(full_path):
            return "Putanja ne postoji."

        files = os.listdir(full_path)
        return "\n".join(files[:200])
    except Exception as e:
        return f"[LIST ERROR] {e}"
