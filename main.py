# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import os, uvicorn, httpx, json, asyncio, subprocess, re, base64, io, hashlib, time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import aiosqlite

from safe_layer import validate_code, validate_url, safe_error
from web_fix import inject_web_results, build_search_system_prompt, has_web_data

# ══════════════════════════════════════
# ATLAS OS v18.5 — MODULARNI SUSTAV
# ══════════════════════════════════════
ATLAS_VERSION = "v18.5"

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI()
DB_PATH     = "database.db"
PROJECT_DIR = Path(os.path.expanduser("~")) / "atlas_os_v1"
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.0-flash-lite",
]
GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

_groq_model   = None
_gemini_model = None
_vision_model = None

URL_BLACKLIST = [
    "api.groq.com", "googleapis.com", "generativelanguage",
    "openai.com", "fonts.googleapis", "cdnjs.cloudflare",
    "anthropic.com", "127.0.0.1", "0.0.0.0", "localhost",
    "shields.io", "flaticon.com", "github.com/login",
]

# ══════════════════════════════════════
# SOFT MODULE IMPORTS — sve opcionalno
# Sustav radi normalno ako moduli ne postoje
# ══════════════════════════════════════
_scout   = None
_media   = None
_lingua  = None
_security_vault = None
_memory_brain   = None
_context = None

try:
    import modules.tools.web_scout as _scout
    print(f"[MODULE] web_scout ucitan")
except Exception as e:
    print(f"[MODULE] web_scout nedostupan: {e}")

try:
    import modules.tools.media_pro as _media
    print(f"[MODULE] media_pro ucitan")
except Exception as e:
    print(f"[MODULE] media_pro nedostupan: {e}")

try:
    import modules.tools.lingua_core as _lingua
    print(f"[MODULE] lingua_core ucitan")
except Exception as e:
    print(f"[MODULE] lingua_core nedostupan: {e}")

try:
    import modules.security.vault as _security_vault
    print(f"[MODULE] security.vault ucitan")
except Exception as e:
    print(f"[MODULE] security.vault nedostupan: {e}")

try:
    import modules.core.vector_brain as _memory_brain
    print(f"[MODULE] vector_brain ucitan")
except Exception as e:
    print(f"[MODULE] vector_brain nedostupan: {e}")

try:
    import modules.core.context_helper as _context
    print(f"[MODULE] context_helper ucitan")
except Exception as e:
    print(f"[MODULE] context_helper nedostupan: {e}")

# ══════════════════════════════════════
# MODULE HELPER FUNCTIONS
# Sve f-je su safe — nikad ne crashaju sustav
# ══════════════════════════════════════

def _scout_search(query: str) -> str:
    """Autonomna web pretraga putem web_scout modula."""
    if not _scout:
        return ""
    try:
        result = _scout.get_live_info(query)
        if result and isinstance(result, str):
            return result[:2000]
        if result and isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)[:2000]
        return ""
    except Exception as e:
        print(f"[SCOUT] {e}")
        return ""

def _lingua_adapt(user_msg: str) -> dict:
    """Adaptacija jezika/tona putem lingua_core modula."""
    if not _lingua:
        return {}
    try:
        result = _lingua.adapt_to_user(user_msg)
        if isinstance(result, dict):
            return result
        return {}
    except Exception as e:
        print(f"[LINGUA] {e}")
        return {}

def _vault_check(path: str) -> dict:
    """Provjera pristupa putanji putem security.vault modula."""
    if not _security_vault:
        return {"status": "ALLOWED", "message": ""}
    try:
        result = _security_vault.check_access(path)
        if isinstance(result, dict):
            return result
        return {"status": "ALLOWED", "message": ""}
    except Exception as e:
        print(f"[VAULT] {e}")
        return {"status": "ALLOWED", "message": ""}

def _memory_save(user_msg: str, response: str) -> None:
    """Sprema u vector_brain long-term memoriju."""
    if not _memory_brain:
        return
    try:
        _memory_brain.save(user_msg, response)
    except Exception as e:
        print(f"[VECTOR_BRAIN] save: {e}")

def _memory_recall_vector(query: str) -> str:
    """Dohvaca iz vector_brain memorije."""
    if not _memory_brain:
        return ""
    try:
        result = _memory_brain.recall(query)
        if isinstance(result, str):
            return result[:1000]
        if isinstance(result, list):
            return "\n".join(str(r) for r in result[:5])[:1000]
        return ""
    except Exception as e:
        print(f"[VECTOR_BRAIN] recall: {e}")
        return ""

def _context_get(user_msg: str) -> str:
    """Dohvaca RAG kod-kontekst za sistemsku poruku."""
    if not _context:
        return ""
    try:
        result = _context.get_code_context(user_msg)
        if isinstance(result, str):
            return result[:1500]
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)[:1500]
        return ""
    except Exception as e:
        print(f"[CONTEXT] {e}")
        return ""

def _media_process(action: str, data: dict) -> dict:
    """Obrada medija putem media_pro modula."""
    if not _media:
        return {}
    try:
        result = _media.process(action, data)
        if isinstance(result, dict):
            return result
        return {}
    except Exception as e:
        print(f"[MEDIA_PRO] {e}")
        return {}

# ══════════════════════════════════════
# SECURITY / PERMISSIONS
# ══════════════════════════════════════
ALLOWED_CMDS       = ["ls", "pwd", "echo"]
MAX_MEMORY_BYTES   = 2 * 1024 * 1024
MAX_MEMORY_ENTRIES = 100
MAX_AUTO_STEPS     = 4
AUTO_TIMEOUT       = 30
REQUIRES_APPROVAL  = {"shell", "python", "file_write", "cloud"}
MAX_FILE_SIZE_B64  = 10 * 1024 * 1024

_approved_tools: set = set()

def check_permission(tool: str) -> bool:
    return tool not in REQUIRES_APPROVAL or tool in _approved_tools

def approve_tool(tool: str):
    _approved_tools.add(tool)

def blocked(tool: str) -> str:
    return f"[BLOCKED] Permission required for: {tool}. Send 'approve:{tool}' to enable."

def safe_path(path: str) -> Path | None:
    """Provjera putanje — za putanje izvan PROJECT_DIR koristi vault."""
    try:
        full = (PROJECT_DIR / path.lstrip("/")).resolve()
        is_inside = str(full).startswith(str(PROJECT_DIR.resolve()))
        if not is_inside:
            vault_result = _vault_check(str(full))
            status = vault_result.get("status", "DENIED")
            if status == "PENDING":
                print(f"[VAULT] PENDING za putanju: {full}")
                return None
            if status != "ALLOWED":
                return None
        return full
    except:
        return None

# ══════════════════════════════════════
# MODEL + SEARCH CACHE
# ══════════════════════════════════════
_response_cache: dict = {}
_search_cache: dict   = {}
_search_ts: dict      = {}

def _cache_key(messages: list, temp: float) -> str:
    content = json.dumps(messages, sort_keys=True) + str(temp)
    return hashlib.md5(content.encode()).hexdigest()

def _cache_get(key: str) -> str | None:
    entry = _response_cache.get(key)
    if entry and time.time() - entry["ts"] < 300:
        return entry["val"]
    return None

def _cache_set(key: str, val: str):
    if len(_response_cache) > 200:
        oldest = min(_response_cache, key=lambda k: _response_cache[k]["ts"])
        del _response_cache[oldest]
    _response_cache[key] = {"val": val, "ts": time.time()}

def _search_cache_get(query: str) -> str | None:
    key = hashlib.md5(query.encode()).hexdigest()
    if key in _search_cache and time.time() - _search_ts.get(key, 0) < 120:
        return _search_cache[key]
    return None

def _search_cache_set(query: str, result: str):
    key = hashlib.md5(query.encode()).hexdigest()
    _search_cache[key] = result
    _search_ts[key] = time.time()

# ══════════════════════════════════════
# AUTO MEMORY (dedup + compress)
# ══════════════════════════════════════
AUTO_MEMORY_PATH = PROJECT_DIR / "auto_memory.json"

def _deduplicate_memory(data: list) -> list:
    seen = set()
    result = []
    for entry in reversed(data):
        key = hashlib.md5((entry.get("user","") + entry.get("atlas","")).encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(entry)
    return list(reversed(result))

def _compress_old_entries(data: list, keep_recent: int = 20) -> list:
    if len(data) <= keep_recent:
        return data
    recent = data[-keep_recent:]
    older  = data[:-keep_recent]
    compressed = []
    for i in range(0, len(older), 3):
        chunk = older[i:i+3]
        summary = " | ".join(e.get("user","")[:60] for e in chunk)
        compressed.append({
            "timestamp": chunk[-1].get("timestamp",""),
            "user": f"[SAZETAK] {summary}",
            "atlas": chunk[-1].get("atlas","")[:200]
        })
    return compressed + recent

def auto_save(user_msg: str, ai_response: str) -> None:
    try:
        data = []
        if AUTO_MEMORY_PATH.exists():
            if AUTO_MEMORY_PATH.stat().st_size < MAX_MEMORY_BYTES:
                with open(AUTO_MEMORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
        data.append({
            "timestamp": str(datetime.now()),
            "user":  user_msg[:400],
            "atlas": ai_response[:600]
        })
        data = _deduplicate_memory(data)
        data = _compress_old_entries(data)
        data = data[-MAX_MEMORY_ENTRIES:]
        with open(AUTO_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AUTO_MEMORY] {e}")
    # Vector brain save — opcionalno
    try:
        _memory_save(user_msg, ai_response)
    except Exception as e:
        print(f"[VECTOR_BRAIN_SAVE] {e}")

def recall(query: str = "") -> str:
    # Pokusaj vector brain prvo
    if _memory_brain:
        try:
            vr = _memory_recall_vector(query)
            if vr:
                return f"[Vektorska memorija]\n{vr}"
        except Exception as e:
            print(f"[VECTOR_RECALL] {e}")
    # Fallback na JSON memoriju
    try:
        if not AUTO_MEMORY_PATH.exists():
            return "Memorija je prazna."
        with open(AUTO_MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return "Memorija je prazna."
        if query:
            filtered = [d for d in data
                        if query.lower() in d.get("user","").lower()
                        or query.lower() in d.get("atlas","").lower()]
            data = filtered if filtered else data
        recent = data[-5:]
        lines = []
        for d in reversed(recent):
            ts = d.get("timestamp","")[:16]
            lines.append(f"[{ts}]\nTi: {d.get('user','')}\nAtlas: {d.get('atlas','')}\n")
        return "Sjecam se:\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Greska pri dohvatu memorije: {e}"

# ══════════════════════════════════════
# METRICS
# ══════════════════════════════════════
def get_metrics() -> dict:
    bat = "N/A"
    try:
        r = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            b = json.loads(r.stdout)
            icon = "⚡" if b.get("status") != "DISCHARGING" else "🔋"
            bat = f"{icon}{b.get('percentage', 0)}%"
    except:
        pass
    mem = "N/A"
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mt = int(lines[0].split()[1])
        ma = int(lines[2].split()[1])
        mem = round((1 - ma / mt) * 100, 1)
    except:
        pass
    return {"cpu": bat, "mem": mem}

# ══════════════════════════════════════
# DATABASE
# ══════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS memory
            (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS profile
            (id INTEGER PRIMARY KEY, data TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS tasks
            (id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, result TEXT, timestamp TEXT)""")
        await db.commit()

async def save_msg(role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memory (role, content, timestamp) VALUES (?,?,?)",
            (role, str(content)[:600], str(datetime.now())))
        await db.execute(
            "DELETE FROM memory WHERE id NOT IN "
            "(SELECT id FROM memory ORDER BY id DESC LIMIT 40)")
        await db.commit()

async def get_history(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content FROM memory ORDER BY id DESC LIMIT ?", (limit,)
        ) as c:
            rows = await c.fetchall()
    return [{"role": r, "content": cnt} for r, cnt in reversed(rows)]

async def clear_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM memory")
        await db.commit()

async def save_task(goal: str, result: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tasks (goal, result, timestamp) VALUES (?,?,?)",
            (goal[:300], result[:800], str(datetime.now())))
        await db.execute(
            "DELETE FROM tasks WHERE id NOT IN "
            "(SELECT id FROM tasks ORDER BY id DESC LIMIT 10)")
        await db.commit()

async def get_last_task() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT goal, result, timestamp FROM tasks ORDER BY id DESC LIMIT 1"
            ) as c:
                row = await c.fetchone()
        if row:
            return {"goal": row[0], "result": row[1], "timestamp": row[2]}
    except:
        pass
    return {}

def count_tokens(messages: list) -> int:
    return sum(len(str(m.get("content", ""))) for m in messages) // 4

def trim_messages(messages: list, limit: int = 4500) -> list:
    if count_tokens(messages) <= limit:
        return messages
    system  = [m for m in messages if m["role"] == "system"]
    rest    = [m for m in messages if m["role"] != "system"]
    last    = rest[-1:] if rest else []
    history = rest[:-1]
    while history and count_tokens(system + history + last) > limit:
        history = history[2:]
    return system + history + last

# ══════════════════════════════════════
# PROFILE
# ══════════════════════════════════════
PROFILE_TRIGGERS = ["zovem se", "moje ime", "radim na", "volim", "preferiram",
                    "projekt", "koristim", "my name", "i am", "i work", "i like"]

async def update_profile(user_msg: str):
    if not any(k in user_msg.lower() for k in PROFILE_TRIGGERS):
        return
    try:
        model = _groq_model or GROQ_MODELS[0]
        prompt = (
            f'Extract user info as JSON only. '
            f'Schema: {{"name":"","preferences":[],"projects":[]}} '
            f'Message: {user_msg[:300]}'
        )
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 150, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]})
            if r.status_code != 200:
                return
            raw = re.sub(r"```json?", "",
                         r.json()["choices"][0]["message"]["content"]
                         ).replace("```","").strip()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO profile VALUES (1,?)",
                                 (json.dumps(json.loads(raw)),))
                await db.commit()
    except Exception as e:
        print(f"[PROFILE] {e}")

async def get_profile() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT data FROM profile WHERE id=1") as c:
                row = await c.fetchone()
        return json.loads(row[0]) if row else {}
    except:
        return {}

# ══════════════════════════════════════
# LANGUAGE & MODE
# ══════════════════════════════════════
def detect_language(text: str) -> str:
    # Pokusaj lingua_core prvo
    if _lingua:
        try:
            adapt = _lingua_adapt(text)
            lang = adapt.get("lang","")
            if lang in ("hr","en","de","fr","es"):
                return lang
        except Exception as e:
            print(f"[LINGUA_LANG] {e}")
    # Fallback na interni detektor
    t = text.lower()
    scores = {
        "hr": sum(1 for w in ["što","kako","zašto","gdje","kada","imam","treba",
                               "mogu","ovo","nije","da","ali","jer","sam","koji"]
                  if w in t.split()),
        "en": sum(1 for w in ["what","how","why","where","when","have","need",
                               "can","this","that","the","and","for","is","are"]
                  if w in t.split()),
        "de": sum(1 for w in ["was","wie","warum","wo","ich","habe","kann",
                               "das","und","ist"] if w in t.split()),
        "fr": sum(1 for w in ["que","comment","pourquoi","je","avoir","peut",
                               "est","les","des"] if w in t.split()),
        "es": sum(1 for w in ["que","como","por","yo","tengo","puede","los",
                               "una","para"] if w in t.split()),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "hr"

def detect_mode(msg: str) -> str:
    m = msg.lower()
    if re.search(r'https?://', m): return "url"
    if any(k in m for k in ["bug","error","greška","kod","debug","fix",
                              "python","script","funkcij","code"]): return "code"
    if any(k in m for k in ["zašto","objasni","analiziraj","usporedi",
                              "razlika","kako radi","sto je","analyze",
                              "explain","compare"]): return "analysis"
    if any(k in m for k in ["ideja","napravi","smisli","kreativan",
                              "prijedlog","osmisli","create","design",
                              "imagine"]): return "creative"
    if any(k in m for k in ["vijesti","danas","pretrazi","tko je","ko je",
                              "cijena","trenutno","news","search",
                              "today"]): return "search"
    return "fast"

# ══════════════════════════════════════
# SECURE TOOL SYSTEM
# ══════════════════════════════════════
def tool_file_write(path: str, content: str) -> str:
    if not check_permission("file_write"):
        return blocked("file_write")
    full = safe_path(path)
    if not full:
        return safe_error("Path traversal blocked or vault PENDING", "file_write")
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"[TOOL] Fajl zapisan: {path}"
    except Exception as e:
        return safe_error(str(e), "file_write")

def tool_file_read(path: str) -> str:
    full = safe_path(path)
    if not full:
        return safe_error("Path traversal blocked or vault PENDING", "file_read")
    try:
        return f"[TOOL] {path}:\n{full.read_text(encoding='utf-8')[:3000]}"
    except Exception as e:
        return safe_error(str(e), "file_read")

def tool_list_files(path: str = ".") -> str:
    full = safe_path(path)
    if not full:
        return safe_error("Path traversal blocked or vault PENDING", "list_files")
    try:
        files = [f.name for f in full.iterdir()]
        return f"[TOOL] Fajlovi u {path}:\n" + "\n".join(files[:50])
    except Exception as e:
        return safe_error(str(e), "list_files")

def tool_run_python(code: str) -> str:
    if not check_permission("python"):
        return blocked("python")
    check = validate_code(code)
    if not check["safe"]:
        return safe_error(check["reason"], "python")
    allowed_builtins = {
        "print": print, "len": len, "range": range,
        "str": str, "int": int, "float": float,
        "list": list, "dict": dict, "bool": bool,
        "sum": sum, "min": min, "max": max, "abs": abs,
        "round": round, "sorted": sorted, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter,
    }
    try:
        output_lines = []
        def safe_print(*args, **kwargs):
            output_lines.append(" ".join(str(a) for a in args))
        allowed_builtins["print"] = safe_print
        exec(compile(code, "<atlas>", "exec"), {"__builtins__": allowed_builtins})
        result = "\n".join(output_lines)
        return f"[TOOL] Python output:\n{result[:1000]}" if result else "[TOOL] Python: OK (no output)"
    except Exception as e:
        return safe_error(str(e)[:200], "python")

def tool_run_shell(cmd: str) -> str:
    if not check_permission("shell"):
        return blocked("shell")
    parts = cmd.strip().split()
    if not parts:
        return safe_error("Empty command", "shell")
    if parts[0] not in ALLOWED_CMDS:
        return safe_error(
            f"Command not in whitelist: {parts[0]}. Allowed: {ALLOWED_CMDS}",
            "shell"
        )
    try:
        result = subprocess.run(
            parts, capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_DIR)
        )
        out = result.stdout[:1000] or ""
        err = result.stderr[:300] or ""
        return f"[TOOL] Shell output:\n{out}" + (f"\nStderr: {err}" if err else "")
    except subprocess.TimeoutExpired:
        return safe_error("Timeout (10s)", "shell")
    except Exception as e:
        return safe_error(str(e), "shell")

def tool_cloud_upload(filepath: str) -> str:
    if not check_permission("cloud"):
        return blocked("cloud")
    full = safe_path(filepath)
    if not full:
        return safe_error("Path traversal blocked or vault PENDING", "cloud")
    if not full.exists():
        return safe_error(f"File not found: {filepath}", "cloud")
    try:
        result = subprocess.run(
            ["rclone", "copy", str(full), "remote:AtlasBackup/"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return json.dumps({"success": True, "file": filepath, "module": "cloud"})
        return safe_error(result.stderr[:200], "cloud")
    except FileNotFoundError:
        return safe_error("rclone not installed", "cloud")
    except subprocess.TimeoutExpired:
        return safe_error("Upload timeout", "cloud")
    except Exception as e:
        return safe_error(str(e), "cloud")

TOOLS = {
    "file_write": tool_file_write,
    "file_read":  tool_file_read,
    "shell":      tool_run_shell,
    "python":     tool_run_python,
    "cloud":      tool_cloud_upload,
}

def handle_tool_request(msg: str) -> str | None:
    m = msg.strip()
    if m.startswith("TOOL:file_write:"):
        parts = m.split(":", 3)
        if len(parts) >= 4:
            return TOOLS["file_write"](parts[2], parts[3])
    if m.startswith("TOOL:file_read:"):
        return TOOLS["file_read"](m.split(":", 2)[-1])
    if m.startswith("TOOL:list_files"):
        path = m.split(":", 2)[-1] if m.count(":") >= 2 else "."
        return tool_list_files(path)
    if m.startswith("TOOL:run_python:"):
        return TOOLS["python"](m.split(":", 2)[-1])
    if m.startswith("TOOL:run_shell:"):
        return TOOLS["shell"](m.split(":", 2)[-1])
    lm = m.lower()
    if lm.startswith("pokazi fajlove") or lm.startswith("list files"):
        return tool_list_files(".")
    match = re.match(r'^(?:procitaj|otvori) fajl (.+)', lm)
    if match:
        return TOOLS["file_read"](match.group(1).strip())
    match = re.match(r'^pokreni: (.+)', m)
    if match:
        return TOOLS["shell"](match.group(1).strip())
    return None

# ══════════════════════════════════════
# MULTIMEDIA PROCESSING
# ══════════════════════════════════════
def _safe_b64_decode(b64: str) -> bytes | None:
    try:
        raw = base64.b64decode(b64)
        if len(raw) > MAX_FILE_SIZE_B64:
            return None
        return raw
    except:
        return None

def process_image_meta(b64: str, mime: str) -> dict:
    # Pokusaj media_pro modul
    if _media:
        try:
            result = _media_process("image_meta", {"b64": b64, "mime": mime})
            if result:
                return result
        except Exception as e:
            print(f"[MEDIA_PRO image_meta] {e}")
    try:
        from PIL import Image
        raw = _safe_b64_decode(b64)
        if not raw:
            return {"error": "File too large or invalid"}
        img = Image.open(io.BytesIO(raw))
        return {"format": img.format or mime.split("/")[-1].upper(),
                "size": f"{img.width}x{img.height}",
                "mode": img.mode, "bytes": len(raw)}
    except ImportError:
        return {"format": mime, "bytes": len(base64.b64decode(b64))}
    except Exception as e:
        return {"error": str(e)[:100]}

def process_image_resize(b64: str, mime: str, max_px: int = 1024) -> str:
    if _media:
        try:
            result = _media_process("image_resize", {"b64": b64, "mime": mime, "max_px": max_px})
            if result and "b64" in result:
                return result["b64"]
        except Exception as e:
            print(f"[MEDIA_PRO image_resize] {e}")
    try:
        from PIL import Image
        raw = _safe_b64_decode(b64)
        if not raw:
            return b64
        img = Image.open(io.BytesIO(raw))
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = "JPEG" if "jpeg" in mime or "jpg" in mime else "PNG"
        img.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return b64

def process_image_convert(b64: str, target_fmt: str = "jpeg") -> tuple:
    if _media:
        try:
            result = _media_process("image_convert", {"b64": b64, "target_fmt": target_fmt})
            if result and "b64" in result:
                return result["b64"], result.get("mime", f"image/{target_fmt}")
        except Exception as e:
            print(f"[MEDIA_PRO image_convert] {e}")
    try:
        from PIL import Image
        raw = _safe_b64_decode(b64)
        if not raw:
            return b64, f"image/{target_fmt}"
        img = Image.open(io.BytesIO(raw))
        if target_fmt.lower() == "jpeg" and img.mode in ("RGBA","P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format=target_fmt.upper())
        new_b64 = base64.b64encode(buf.getvalue()).decode()
        mime = f"image/{'jpeg' if target_fmt.lower() in ('jpg','jpeg') else target_fmt.lower()}"
        return new_b64, mime
    except Exception:
        return b64, f"image/{target_fmt}"

def process_audio_meta(b64: str, mime: str, filename: str = "") -> dict:
    if _media:
        try:
            result = _media_process("audio_meta", {"b64": b64, "mime": mime, "filename": filename})
            if result:
                return result
        except Exception as e:
            print(f"[MEDIA_PRO audio_meta] {e}")
    import struct
    ext = filename.split(".")[-1].lower() if "." in filename else mime.split("/")[-1]
    raw = _safe_b64_decode(b64)
    if not raw:
        return {"error": "File too large"}
    info = {"format": ext.upper(), "mime": mime, "size_bytes": len(raw)}
    try:
        if ext == "mp3" and raw[:3] == b"ID3":
            info["tag"] = "ID3"
        if ext == "wav" and raw[:4] == b"RIFF":
            channels    = struct.unpack_from("<H", raw, 22)[0]
            sample_rate = struct.unpack_from("<I", raw, 24)[0]
            bits        = struct.unpack_from("<H", raw, 34)[0]
            data_size   = struct.unpack_from("<I", raw, 40)[0]
            duration    = data_size / (sample_rate * channels * bits // 8) if sample_rate else 0
            info.update({"channels": channels, "sample_rate": sample_rate,
                         "bits": bits, "duration_s": round(duration, 2)})
    except:
        pass
    return info

def process_video_meta(b64: str, mime: str, filename: str = "") -> dict:
    if _media:
        try:
            result = _media_process("video_meta", {"b64": b64, "mime": mime, "filename": filename})
            if result:
                return result
        except Exception as e:
            print(f"[MEDIA_PRO video_meta] {e}")
    ext = filename.split(".")[-1].lower() if "." in filename else mime.split("/")[-1]
    raw = _safe_b64_decode(b64)
    if not raw:
        return {"error": "File too large"}
    info = {"format": ext.upper(), "mime": mime, "size_bytes": len(raw),
            "note": "Deep analysis requires ffprobe"}
    try:
        if raw[:4] in (b'\x00\x00\x00\x18', b'\x00\x00\x00\x20', b'ftyp'):
            info["container"] = "MP4/MOV"
        elif raw[:4] == b'\x1a\x45\xdf\xa3':
            info["container"] = "MKV/WebM"
        elif raw[:3] == b'FLV':
            info["container"] = "FLV"
    except:
        pass
    return info

def handle_media_processing(file_data: dict, user_msg: str) -> dict | None:
    if not file_data:
        return None
    fname    = file_data.get("name","")
    ftype    = file_data.get("type","")
    raw_data = file_data.get("data","")
    if len(raw_data) > MAX_FILE_SIZE_B64 * 1.4:
        return {"result": "[BLOCKED] File too large for local processing (max 10MB).", "tag": "photo"}
    b64     = raw_data.split(",")[-1] if "," in raw_data else raw_data
    msg_low = user_msg.lower()

    if file_data.get("isImage"):
        if any(k in msg_low for k in ["metadata","info","velicina","size","format"]):
            meta = process_image_meta(b64, ftype)
            return {"result": f"Slika info: {json.dumps(meta, ensure_ascii=False)}", "tag": "photo"}
        if any(k in msg_low for k in ["smanji","resize","skaliraj"]):
            new_b64 = process_image_resize(b64, ftype)
            return {"result": "Slika smanjena na max 1024px.", "b64": new_b64, "mime": ftype, "tag": "photo"}
        if any(k in msg_low for k in ["jpeg","png","konverti"]):
            fmt = "jpeg" if "jpeg" in msg_low else "png"
            new_b64, new_mime = process_image_convert(b64, fmt)
            return {"result": f"Slika konvertirana u {fmt.upper()}.", "b64": new_b64, "mime": new_mime, "tag": "photo"}

    if file_data.get("isAudio"):
        if any(k in msg_low for k in ["info","metadata","format","trajanje","duration"]):
            meta = process_audio_meta(b64, ftype, fname)
            return {"result": f"Audio info: {json.dumps(meta, ensure_ascii=False)}", "tag": "audio"}

    if file_data.get("isVideo"):
        if any(k in msg_low for k in ["info","metadata","format","rezolucija","fps","trajanje"]):
            meta = process_video_meta(b64, ftype, fname)
            return {"result": f"Video info: {json.dumps(meta, ensure_ascii=False)}", "tag": "video"}

    return None

# ══════════════════════════════════════
# URL & FILE PARSING
# ══════════════════════════════════════
def extract_urls(text: str) -> list:
    found = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    return [u for u in found if not any(b in u for b in URL_BLACKLIST)]

async def fetch_url_content(url: str) -> tuple:
    url_check = validate_url(url)
    if not url_check["safe"]:
        return f"[BLOCKED] {url_check['reason']}", "error"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.9"
    }
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, verify=False) as client:
            r = await client.get(url, headers=headers)
            ct = r.headers.get("content-type", "").lower()
            if "pdf" in ct or url.lower().endswith(".pdf"):
                return _parse_pdf(r.content), "pdf"
            if "json" in ct:
                try: return json.dumps(r.json(), indent=2, ensure_ascii=False)[:3000], "json"
                except: return r.text[:3000], "json"
            html = r.text
            for pat in [r'<script[^>]*>.*?</script>', r'<style[^>]*>.*?</style>',
                        r'<nav[^>]*>.*?</nav>', r'<footer[^>]*>.*?</footer>',
                        r'<header[^>]*>.*?</header>', r'<!--.*?-->']:
                html = re.sub(pat, '', html, flags=re.DOTALL|re.IGNORECASE)
            html = re.sub(r'<[^>]+>', ' ', html)
            html = re.sub(r'&[a-zA-Z#0-9]+;', ' ', html)
            html = re.sub(r'\s+', ' ', html).strip()
            return html[:4000], "web"
    except httpx.TimeoutException: return "[Timeout]", "error"
    except httpx.ConnectError:     return "[Greska veze]", "error"
    except Exception as e:         return f"[Greska: {str(e)[:120]}]", "error"

def _parse_pdf(content: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        text = ""
        for i, page in enumerate(reader.pages[:12]):
            text += f"\n--- Str. {i+1} ---\n{page.extract_text() or ''}"
        return f"[PDF — {len(reader.pages)} stranica]\n{text[:5000]}"
    except ImportError:
        try:
            raw    = content.decode("latin-1", errors="ignore")
            chunks = re.findall(r'BT\s*(.*?)\s*ET', raw, re.DOTALL)
            texts  = [p for c in chunks for p in re.findall(r'\((.*?)\)', c)]
            result = " ".join(texts)
            if result: return f"[PDF parcijalno]\n{result[:4000]}"
        except: pass
        return "[PDF ucitan. Instaliraj: pip install pypdf]"
    except Exception as e:
        return f"[PDF greska: {str(e)[:100]}]"

def _parse_file(name: str, content: str) -> str:
    ext = name.lower().split(".")[-1] if "." in name else ""
    if ext == "pdf":
        try:
            b64 = content.split(",")[1] if "," in content else content
            return _parse_pdf(base64.b64decode(b64))
        except Exception as e: return f"[PDF greska: {e}]"
    if ext == "csv":
        return "[CSV]\n" + "\n".join(content.split("\n")[:50])
    if ext == "json":
        try: return f"[JSON]\n{json.dumps(json.loads(content), indent=2, ensure_ascii=False)[:3000]}"
        except: pass
    return f"[Fajl: {name}]\n{content[:3000]}"

# ══════════════════════════════════════
# WEB SEARCH (safe + cached + scout fallback)
# ══════════════════════════════════════
def _sanitize_query(query: str) -> str:
    query = re.sub(r'[<>&"\']', '', query)
    return query[:200].strip()

def _web_search(query: str, news: bool = False) -> str:
    query = _sanitize_query(query)
    if not query:
        return ""
    cache_key = ("news:" if news else "") + query
    cached = _search_cache_get(cache_key)
    if cached:
        return cached

    # Primarno DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            if news:
                results = list(ddgs.news(query, max_results=5))
                out = "\n".join(
                    f"• [{r.get('date','')[:10]}] {r['title']}: "
                    f"{re.sub(r'<[^>]+>',' ',r.get('body',''))[:200]}"
                    for r in results
                )
            else:
                results = list(ddgs.text(query, max_results=5))
                out = "\n".join(
                    f"• {r['title']}: {re.sub(r'<[^>]+>',' ',r['body'])[:200]}"
                    for r in results
                )
        if out:
            _search_cache_set(cache_key, out)
            return out
    except Exception as e:
        print(f"[SEARCH DDG] {e}")

    # Fallback na web_scout modul
    scout_result = _scout_search(query)
    if scout_result:
        _search_cache_set(cache_key, scout_result)
        return scout_result

    return ""

# ══════════════════════════════════════
# BACKUP & GIT
# ══════════════════════════════════════
def run_backup(filepath: str = "") -> str:
    if filepath:
        if not check_permission("cloud"):
            return blocked("cloud")
        full = safe_path(filepath)
        if not full:
            return safe_error("Path traversal blocked or vault PENDING", "backup")
        if not full.exists():
            return f"Fajl nije pronaden: {filepath}"
        try:
            result = subprocess.run(
                ["rclone", "copy", str(full), "remote:AtlasBackup/"],
                capture_output=True, text=True, timeout=60
            )
            return (f"Fajl prenesen: {full.name}" if result.returncode == 0
                    else f"rclone greska: {result.stderr[:200]}")
        except FileNotFoundError:         return "rclone nije instaliran."
        except subprocess.TimeoutExpired: return "Backup timeout."
        except Exception as e:            return f"Backup greska: {str(e)[:100]}"
    try:
        result = subprocess.run(
            ["python", "cloud_backup.py"],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_DIR)
        )
        return ("Backup zavrsen." if result.returncode == 0
                else f"Backup greska: {result.stderr[:200]}")
    except subprocess.TimeoutExpired: return "Backup timeout."
    except Exception as e:            return f"Backup greska: {str(e)[:100]}"

def _detect_backup_file(msg: str) -> str:
    for p in [r'prenesi\s+["\']?(.+?)["\']?\s+na\s+oblak',
              r'upload\s+["\']?(.+?)["\']?\s+(?:na|to)\s+(?:oblak|cloud)',
              r'spremi\s+["\']?(.+?)["\']?\s+na\s+oblak']:
        m = re.search(p, msg.lower())
        if m: return m.group(1).strip()
    return ""

def run_git_update() -> str:
    try:
        result = subprocess.run(
            ["git", "pull"], capture_output=True, text=True,
            timeout=60, cwd=str(PROJECT_DIR)
        )
        return (f"GitHub update uspjesan.\n{result.stdout[:300]}"
                if result.returncode == 0
                else f"Git greska:\n{result.stderr[:300]}")
    except Exception as e:
        return f"Git greska: {e}"

# ══════════════════════════════════════
# SYSTEM PROMPT (s RAG kontekstom)
# ══════════════════════════════════════
LANG_RULES = {
    "hr": "Jezik: standardni hrvatski knjizevni. Gramaticki ispravno. Bez ijekavice.",
    "en": "Language: fluent, natural English.",
    "de": "Sprache: fließendes, natürliches Deutsch.",
    "fr": "Langue: français courant et naturel.",
    "es": "Idioma: español fluido y natural.",
}
MODE_INSTRUCTIONS = {
    "code":     "Samo kod + kratko objasnjenje.",
    "analysis": "Korak po korak. Jasan zakljucak.",
    "creative": "Originalno. Izbjegavaj kliseje.",
    "search":   "Koristi ISKLJUCIVO priložene web podatke. Ako nema — reci da nema.",
    "url":      "Analiziraj ucitani sadrzaj. Kljucne tocke.",
    "fast":     "Direktno i kratko.",
    "video":    "Strucnjak za video produkciju.",
    "audio":    "Strucnjak za audio i glazbu.",
    "photo":    "Strucnjak za fotografiju.",
}
TRUTH_MODE_RULE = (
    "ANTI-HALLUCINATION: Ako nemas stvarne podatke, reci jasno da ne mozes "
    "dohvatiti informacije. NE izmisljaj cinjenice, datume, ljude, citate ili statistike."
)

def build_system(profile: dict, mode: str, lang: str, media_mode: str,
                 task_context: str = "", has_real_data: bool = False,
                 rag_context: str = "", lingua_hints: dict = None) -> str:
    name     = profile.get("name","")
    prefs    = profile.get("preferences",[])
    projects = profile.get("projects",[])
    user_ctx = ""
    if name:     user_ctx += f"Korisnik: {name}. "
    if prefs:    user_ctx += f"Interesi: {', '.join(prefs[:4])}. "
    if projects: user_ctx += f"Projekti: {', '.join(projects[:3])}. "
    media_ctx    = f" MULTIMEDIJSKI MOD: {media_mode.upper()}." if media_mode != "text" else ""
    task_ctx     = f"\nPRETHODNI ZADATAK: {task_context}" if task_context else ""
    truth_ctx    = f"\n{TRUTH_MODE_RULE}" if not has_real_data else ""
    search_addon = f"\n{build_search_system_prompt(lang)}" if mode == "search" else ""
    # RAG kontekst — ubaci ako postoji
    rag_addon = f"\n[RAG KONTEKST DATOTEKA]\n{rag_context[:1200]}" if rag_context else ""
    # Lingua hints — ton adaptacija
    tone_hint = ""
    if lingua_hints:
        tone = lingua_hints.get("tone","")
        if tone:
            tone_hint = f"\nTON: {tone}"
    # Modules status
    modules_active = []
    if _scout:   modules_active.append("web_scout")
    if _media:   modules_active.append("media_pro")
    if _lingua:  modules_active.append("lingua_core")
    if _context: modules_active.append("context_helper")
    if _memory_brain: modules_active.append("vector_brain")
    if _security_vault: modules_active.append("vault")
    mod_str = f"\nAKTIVNI MODULI: {', '.join(modules_active)}" if modules_active else ""

    return (
        f"Ti si ATLAS — napredni AI operativni sustav. {ATLAS_VERSION}{media_ctx}\n"
        f"MOD: {mode.upper()} — {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['fast'])}\n"
        f"{LANG_RULES.get(lang, LANG_RULES['hr'])}\n"
        f"KARAKTER: Direktan. Iskren. Neutralan i profesionalan. Ton prilagodjen korisniku. "
        f"Bez laskanja. Bez 'Naravno!' i slicnih fraza.\n"
        f"SPOSOBNOSTI: Citas URL-ove i PDF-ove. Web pretraga. Cloud backup. Multimedija. Pamtis razgovor.\n"
        + (f"PROFIL: {user_ctx}\n" if user_ctx else "")
        + task_ctx + truth_ctx + search_addon + rag_addon + tone_hint + mod_str + "\n"
        + "Kod u blokovima. Tablice u markdown formatu."
    )

# ══════════════════════════════════════
# AI ENGINE
# ══════════════════════════════════════
async def call_groq(messages: list, temp: float) -> str | None:
    global _groq_model
    messages = trim_messages(messages, 4500)
    ck = _cache_key(messages, temp)
    cached = _cache_get(ck)
    if cached:
        return cached
    order = ([_groq_model] + [m for m in GROQ_MODELS if m != _groq_model]
             if _groq_model else GROQ_MODELS)
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": model, "messages": messages,
                          "temperature": temp, "max_tokens": 1000})
                if r.status_code == 200:
                    if _groq_model != model:
                        print(f"[GROQ] Aktivan: {model}")
                        _groq_model = model
                    result = r.json()["choices"][0]["message"]["content"]
                    _cache_set(ck, result)
                    return result
                if r.status_code == 413:
                    messages = trim_messages(messages, 2500)
                    r2 = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                                 "Content-Type": "application/json"},
                        json={"model": model, "messages": messages,
                              "temperature": temp, "max_tokens": 700})
                    if r2.status_code == 200:
                        _groq_model = model
                        result = r2.json()["choices"][0]["message"]["content"]
                        _cache_set(ck, result)
                        return result
                if r.status_code == 429:
                    print(f"[GROQ] {model} rate limit"); continue
                print(f"[GROQ] {model} — {r.status_code}")
            except Exception as e:
                print(f"[GROQ] {model}: {e}"); continue
    _groq_model = None
    return None

async def call_gemini(messages: list) -> str | None:
    global _gemini_model
    prompt = "\n".join(
        f"{'ATLAS' if m['role']=='assistant' else 'KORISNIK'}: {m['content']}"
        for m in messages if isinstance(m.get("content"), str)
    )
    if len(prompt) > 18000:
        prompt = prompt[-18000:]
    order = ([_gemini_model] + [m for m in GEMINI_MODELS if m != _gemini_model]
             if _gemini_model else GEMINI_MODELS)
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    if _gemini_model != model:
                        print(f"[GEMINI] Aktivan: {model}")
                        _gemini_model = model
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if r.status_code == 429:
                    print(f"[GEMINI] {model} quota"); continue
                print(f"[GEMINI] {model} — {r.status_code}")
            except Exception as e:
                print(f"[GEMINI] {model}: {e}"); continue
    _gemini_model = None
    return None

async def call_ai(messages: list, mode: str = "fast") -> tuple:
    temp = {"fast":0.35,"analysis":0.2,"creative":0.75,"code":0.1,
            "search":0.1,"url":0.2,"video":0.3,"audio":0.3,"photo":0.3}.get(mode, 0.35)
    out = await call_groq(messages, temp)
    if out: return out, _groq_model or "GROQ"
    out = await call_gemini(messages)
    if out: return out, _gemini_model or "GEMINI"
    return "Trenutno ne mogu dohvatiti odgovor. Pokusaj ponovno.", "ERROR"

async def call_vision(image_data: str, prompt: str) -> tuple:
    global _vision_model
    b64 = image_data.split(",")[-1] if "," in image_data else image_data
    order = ([_vision_model] + [m for m in GROQ_VISION_MODELS if m != _vision_model]
             if _vision_model else GROQ_VISION_MODELS)
    async with httpx.AsyncClient(timeout=40) as client:
        for model in order:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": model, "max_tokens": 900, "temperature": 0.2,
                          "messages": [{"role":"user","content":[
                              {"type":"text","text": prompt or "Analiziraj ovu sliku detaljno."},
                              {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}
                          ]}]})
                if r.status_code == 200:
                    _vision_model = model
                    return r.json()["choices"][0]["message"]["content"], "GROQ VISION"
                print(f"[VISION] {model} — {r.status_code}")
            except Exception as e:
                print(f"[VISION] {model}: {e}")
    try:
        gem = _gemini_model or GEMINI_MODELS[0]
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{gem}:generateContent?key={GEMINI_API_KEY}",
                json={"contents":[{"parts":[
                    {"text": prompt or "Analiziraj ovu sliku."},
                    {"inline_data":{"mime_type":"image/jpeg","data": b64}}
                ]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], "GEMINI VISION"
    except Exception as e:
        print(f"[VISION GEMINI]: {e}")
    return "Vision analiza nedostupna.", "ERROR"

async def call_gemini_media(b64: str, mime: str, prompt: str) -> str | None:
    try:
        gem = _gemini_model or GEMINI_MODELS[0]
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{gem}:generateContent?key={GEMINI_API_KEY}",
                json={"contents":[{"parts":[
                    {"text": prompt or "Analiziraj ovaj medijski sadrzaj."},
                    {"inline_data":{"mime_type": mime, "data": b64}}
                ]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[MEDIA GEMINI] {r.status_code}")
    except Exception as e:
        print(f"[MEDIA GEMINI] {e}")
    return None

# ══════════════════════════════════════
# ORCHESTRATOR (safe, timeout, MAX_STEPS)
# ══════════════════════════════════════
async def planner(goal: str, profile: dict, history: list, last_task: dict) -> list:
    task_ctx = (
        f"Prethodni zadatak: {last_task.get('goal','')}. "
        f"Rezultat: {last_task.get('result','')[:200]}"
        if last_task else ""
    )
    sys_p = (
        f"Ti si Planner unutar ATLAS OS {ATLAS_VERSION}. "
        f"Razlozi zadatak na MAKSIMALNO {MAX_AUTO_STEPS} koraka.\n"
        "Vrati SAMO JSON listu stringova. Bez objasnjenja.\n"
        f"{task_ctx}"
    )
    messages = [{"role":"system","content":sys_p},
                {"role":"user","content":f"Zadatak: {goal}"}]
    out = await call_groq(messages, 0.2) or await call_gemini(messages)
    try:
        raw   = re.sub(r"```json?|```", "", out or "[]").strip()
        steps = json.loads(raw)
        if isinstance(steps, list) and steps:
            return [str(s) for s in steps[:MAX_AUTO_STEPS]]
    except:
        pass
    return [goal]

async def executor(step: str, goal: str, context: str,
                   history: list, lang: str) -> str:
    sys_p = (
        f"Ti si Executor agent unutar ATLAS OS {ATLAS_VERSION}.\n"
        f"Cilj: {goal}\n"
        f"Kontekst dosad: {context[:600] if context else 'Nema'}\n"
        "FORMAT: STEP 1: konkretna akcija (max 3)"
    )
    messages = (
        [{"role":"system","content":sys_p}]
        + history[-4:]
        + [{"role":"user","content":f"Korak: {step}"}]
    )
    out = await call_groq(messages, 0.3) or await call_gemini(messages)

    code_match = re.search(r'```python\s*(.*?)```', out or "", re.DOTALL)
    if code_match:
        code  = code_match.group(1).strip()
        check = validate_code(code)
        if not check["safe"]:
            return f"{out}\n\n[BLOCKED] {check['reason']}"
        exec_result = tool_run_python(code)
        if any(x in exec_result.lower() for x in ["error","exception","traceback","blocked"]):
            fix_prompt = f"Popravi ovaj Python kod:\n{code}\n\nGreska:\n{exec_result}"
            fixed_out  = await call_groq([{"role":"user","content":fix_prompt}], 0.2)
            if fixed_out:
                m2 = re.search(r'```python\s*(.*?)```', fixed_out, re.DOTALL)
                if m2:
                    fixed_code  = m2.group(1).strip()
                    check2      = validate_code(fixed_code)
                    exec_result = (tool_run_python(fixed_code) if check2["safe"]
                                   else f"[BLOCKED] {check2['reason']}")
        return f"{out}\n\n{exec_result}"

    return out or f"Korak '{step}' izveden."

async def critic(goal: str, result: str) -> str:
    sys_p = (
        "Ti si Critic agent. Spoji rezultate u jedan koncizan finalni odgovor.\n"
        "Ukloni visak i ponavljanja.\n"
        "NE analiziraj sam sebe. Vrati SAMO finalni odgovor u 1-2 pasusa."
    )
    messages = [{"role":"system","content":sys_p},
                {"role":"user","content":f"Rezultat:\n{result[:2500]}"}]
    out = await call_groq(messages, 0.2) or await call_gemini(messages)
    return out or result

async def orchestrator(goal: str, profile: dict,
                       history: list, lang: str) -> tuple:
    print(f"[ORCHESTRATOR] Goal: {goal}")
    last_task    = await get_last_task()
    steps        = await planner(goal, profile, history, last_task)
    print(f"[PLANNER] Koraci: {steps}")
    context      = ""
    step_results = []
    try:
        async with asyncio.timeout(AUTO_TIMEOUT):
            for i, step in enumerate(steps):
                if i >= MAX_AUTO_STEPS:
                    break
                print(f"[EXECUTOR] Korak {i+1}/{len(steps)}: {step}")
                result = await executor(step, goal, context, history, lang)
                step_results.append(f"**{step}**\n{result}")
                context += f"\n{step}: {result[:300]}"
    except asyncio.TimeoutError:
        step_results.append(f"[TIMEOUT] Auto mod prekoracen {AUTO_TIMEOUT}s — zaustavljeno.")
    combined   = "\n\n".join(step_results)
    print("[CRITIC] Sinteza...")
    final      = await critic(goal, combined)
    await save_task(goal, final)
    model_used = _groq_model or _gemini_model or "GROQ"
    return final, model_used, steps

# ══════════════════════════════════════
# HTML UI — v18.5 s Settings panelom
# ══════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,viewport-fit=cover,user-scalable=no">
<link rel="manifest" href="/manifest.json">
<title>ATLAS OS</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Syne:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#000;--sf:#080f1a;--acc:#0ea5e9;--acc2:#a78bfa;--gr:#34d399;--rd:#f87171;--yw:#fbbf24;--tx:#f1f5f9;--mu:#475569;--br:#1e293b;--vd:#ef4444;--au:#8b5cf6;--ph:#10b981}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--tx);font-family:'Syne',sans-serif;display:flex;flex-direction:column;height:100dvh;overflow:hidden;position:fixed;width:100%}
#cvs{position:fixed;inset:0;z-index:0;pointer-events:auto}
.sb{position:fixed;top:0;left:0;width:268px;height:100%;background:rgba(4,8,18,.98);border-right:1px solid var(--br);z-index:200;transform:translateX(-100%);transition:transform .26s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;backdrop-filter:blur(20px)}
.sb.open{transform:translateX(0)}
.sb-hd{padding:26px 16px 12px;border-bottom:1px solid var(--br)}
.sb-logo{font-family:'Orbitron';color:var(--acc);font-size:19px;letter-spacing:.12em;text-shadow:0 0 14px rgba(14,165,233,.5)}
.sb-sub{font-size:10px;color:var(--mu);margin-top:3px;letter-spacing:.07em}
.sb-sec{padding:10px 10px 3px;font-size:9px;color:var(--mu);letter-spacing:.12em;text-transform:uppercase}
.sb-bd{padding:7px;display:flex;flex-direction:column;gap:2px;flex:1;overflow-y:auto}
.si{display:flex;align-items:center;gap:9px;padding:10px 12px;border-radius:9px;cursor:pointer;font-size:13px;color:var(--mu);transition:all .13s;border:1px solid transparent}
.si:hover{background:rgba(14,165,233,.07);color:var(--tx);border-color:var(--br)}
.si.act{color:var(--acc);background:rgba(14,165,233,.09);border-color:rgba(14,165,233,.2)}
.si.rd:hover{color:var(--rd);border-color:rgba(248,113,113,.3)}
.si.gh:hover{color:var(--yw);border-color:rgba(251,191,36,.3)}
.si.vm:hover,.si.vm.act{color:var(--vd);background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.2)}
.si.am:hover,.si.am.act{color:var(--au);background:rgba(139,92,246,.07);border-color:rgba(139,92,246,.2)}
.si.pm:hover,.si.pm.act{color:var(--ph);background:rgba(16,185,129,.07);border-color:rgba(16,185,129,.2)}
.sb-ft{padding:12px;border-top:1px solid var(--br);font-size:9px;color:var(--mu);letter-spacing:.07em}
.ov{display:none;position:fixed;inset:0;z-index:199;background:rgba(0,0,0,.65);backdrop-filter:blur(2px)}
.ov.on{display:block}
/* Settings panel */
.sett-panel{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:290px;background:rgba(4,8,18,.98);border:1px solid var(--br);border-radius:16px;z-index:300;padding:20px;backdrop-filter:blur(24px)}
.sett-panel.open{display:block}
.sett-title{font-family:'Orbitron';color:var(--acc);font-size:13px;letter-spacing:.1em;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center}
.sett-close{cursor:pointer;color:var(--mu);font-size:18px;line-height:1}
.sett-sec{font-size:9px;color:var(--mu);letter-spacing:.1em;text-transform:uppercase;margin:10px 0 5px}
.sett-row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(30,41,59,.6)}
.sett-label{font-size:12px;color:var(--tx)}
.sett-select{background:var(--sf);border:1px solid var(--br);color:var(--tx);padding:3px 7px;border-radius:6px;font-size:11px;font-family:'Syne',sans-serif}
.sett-btn{margin-top:14px;width:100%;padding:9px;background:var(--acc);color:#000;border:none;border-radius:9px;font-family:'Orbitron';font-size:11px;letter-spacing:.07em;cursor:pointer}
.hdr{padding:10px 13px;background:rgba(0,0,0,.9);border-bottom:1px solid var(--br);display:flex;align-items:center;gap:9px;z-index:10;flex-shrink:0;backdrop-filter:blur(12px)}
.hdr-logo{font-family:'Orbitron';color:var(--acc);font-size:12px;letter-spacing:.1em;text-shadow:0 0 10px rgba(14,165,233,.4);line-height:1.2}
.hdr-sub{font-size:9px;color:var(--mu);letter-spacing:.05em}
.met{font-family:'Orbitron';font-size:9px;color:var(--mu);letter-spacing:.05em;white-space:nowrap}
.met span{color:var(--acc)}
.hdr-r{margin-left:auto;display:flex;align-items:center;gap:6px;flex-shrink:0}
.mpill{font-size:8px;padding:2px 6px;border-radius:3px;border:1px solid var(--br);color:var(--mu);letter-spacing:.06em;transition:all .3s}
.mpill.groq{border-color:rgba(14,165,233,.4);color:var(--acc)}
.mpill.gemini{border-color:rgba(251,191,36,.4);color:var(--yw)}
.mpill.error{border-color:rgba(248,113,113,.4);color:var(--rd)}
.modp{font-size:8px;padding:2px 6px;border-radius:3px;letter-spacing:.06em;text-transform:uppercase;border:1px solid rgba(14,165,233,.3);color:var(--acc);transition:all .3s}
.modp.video{border-color:rgba(239,68,68,.4);color:var(--vd)}
.modp.audio{border-color:rgba(139,92,246,.4);color:var(--au)}
.modp.photo{border-color:rgba(16,185,129,.4);color:var(--ph)}
.modp.auto{border-color:rgba(251,191,36,.4);color:var(--yw)}
.wdot{width:7px;height:7px;border-radius:50%;background:var(--mu);transition:all .3s;flex-shrink:0}
.wdot.on{background:var(--gr);box-shadow:0 0 5px var(--gr);animation:pulse 2s infinite}
.wdot.off{background:var(--rd)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.mbar{display:none;padding:7px 11px;background:rgba(0,0,0,.75);border-bottom:1px solid var(--br);gap:7px;z-index:9;flex-shrink:0;backdrop-filter:blur(8px);overflow-x:auto}
.mbar.show{display:flex}
.mbar::-webkit-scrollbar{height:2px}
.mbtn{display:flex;align-items:center;gap:5px;padding:6px 11px;border-radius:7px;border:1px solid var(--br);background:rgba(255,255,255,.02);color:var(--mu);font-size:11px;cursor:pointer;white-space:nowrap;transition:all .13s;font-family:'Syne',sans-serif}
.mbtn:hover{border-color:var(--acc);color:var(--tx)}
.mbar.video .mbtn:hover{border-color:var(--vd);color:var(--vd)}
.mbar.audio .mbtn:hover{border-color:var(--au);color:var(--au)}
.mbar.photo .mbtn:hover{border-color:var(--ph);color:var(--ph)}
.chat{flex:1;overflow-y:auto;padding:13px 11px;display:flex;flex-direction:column;gap:9px;z-index:5;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
.chat::-webkit-scrollbar{width:2px}
.chat::-webkit-scrollbar-thumb{background:var(--br)}
.msg{max-width:88%;padding:10px 13px;border-radius:15px;font-size:15px;line-height:1.65;border:1px solid var(--br);background:rgba(8,15,26,.9);align-self:flex-start;word-break:break-word;animation:up .15s ease;z-index:5}
@keyframes up{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.msg.user{align-self:flex-end;background:rgba(167,139,250,.07);border-color:rgba(167,139,250,.25)}
.msg.error{border-color:rgba(248,113,113,.3);background:rgba(248,113,113,.05)}
.mm{display:flex;align-items:center;gap:5px;margin-bottom:5px;flex-wrap:wrap}
.mw{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.mw.atlas{color:var(--acc)}.mw.user{color:var(--acc2)}.mw.err{color:var(--rd)}
.tg{font-size:7px;padding:1px 5px;border-radius:2px;letter-spacing:.06em;text-transform:uppercase}
.tg.groq{background:rgba(14,165,233,.1);color:var(--acc);border:1px solid rgba(14,165,233,.2)}
.tg.gemini{background:rgba(251,191,36,.1);color:var(--yw);border:1px solid rgba(251,191,36,.2)}
.tg.web{background:rgba(52,211,153,.1);color:var(--gr);border:1px solid rgba(52,211,153,.2)}
.tg.url{background:rgba(251,191,36,.1);color:var(--yw);border:1px solid rgba(251,191,36,.2)}
.tg.pdf{background:rgba(248,113,113,.1);color:var(--rd);border:1px solid rgba(248,113,113,.2)}
.tg.vision{background:rgba(167,139,250,.1);color:var(--acc2);border:1px solid rgba(167,139,250,.2)}
.tg.cloud{background:rgba(52,211,153,.1);color:var(--gr);border:1px solid rgba(52,211,153,.2)}
.tg.code{background:rgba(251,191,36,.1);color:var(--yw);border:1px solid rgba(251,191,36,.2)}
.tg.analysis{background:rgba(52,211,153,.1);color:var(--gr);border:1px solid rgba(52,211,153,.2)}
.tg.video{background:rgba(239,68,68,.1);color:var(--vd);border:1px solid rgba(239,68,68,.2)}
.tg.audio{background:rgba(139,92,246,.1);color:var(--au);border:1px solid rgba(139,92,246,.2)}
.tg.photo{background:rgba(16,185,129,.1);color:var(--ph);border:1px solid rgba(16,185,129,.2)}
.tg.auto{background:rgba(251,191,36,.1);color:var(--yw);border:1px solid rgba(251,191,36,.2)}
.mt{font-size:9px;color:var(--mu);margin-top:5px}
.fbg{display:inline-flex;align-items:center;gap:4px;background:rgba(14,165,233,.08);border:1px solid var(--br);border-radius:5px;padding:2px 7px;font-size:11px;color:var(--acc);margin-bottom:4px}
.dots{display:flex;gap:4px;padding:3px 0}
.dots span{width:6px;height:6px;border-radius:50%;background:var(--acc);opacity:.3;animation:blink 1.2s infinite}
.dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
.media-preview{max-width:100%;border-radius:10px;margin-bottom:8px;border:1px solid var(--br)}
img.media-preview{max-height:280px;object-fit:contain;display:block}
video.media-preview{max-height:220px;width:100%}
audio.media-preview{width:100%;height:40px}
.izone{padding:9px 11px;padding-bottom:max(9px,env(safe-area-inset-bottom));background:rgba(0,0,0,.93);border-top:1px solid var(--br);z-index:10;flex-shrink:0;backdrop-filter:blur(10px)}
#find{display:none;font-size:10px;color:var(--acc);padding:2px 3px 5px}
.ibox{display:flex;align-items:flex-end;gap:7px;background:var(--sf);border:1.5px solid var(--acc);border-radius:17px;padding:6px 9px;transition:all .2s}
.ibox.video{border-color:var(--vd)}.ibox.audio{border-color:var(--au)}.ibox.photo{border-color:var(--ph)}
.ibox:focus-within{box-shadow:0 0 0 3px rgba(14,165,233,.08)}
.ibtn{background:none;border:none;cursor:pointer;color:var(--acc);font-size:18px;width:33px;height:33px;display:flex;align-items:center;justify-content:center;border-radius:8px;flex-shrink:0;transition:all .12s}
.ibtn:hover{background:rgba(14,165,233,.1)}
.sbtn{background:var(--acc);color:#000;border-radius:9px}
.sbtn.video{background:var(--vd)}.sbtn.audio{background:var(--au)}.sbtn.photo{background:var(--ph)}
.sbtn:active{transform:scale(.9)}
#inp{flex:1;background:transparent;border:none;outline:none;color:var(--tx);font-family:'Syne',sans-serif;font-size:15px;resize:none;min-height:33px;max-height:100px;line-height:1.5;caret-color:var(--acc);padding:4px 0}
#inp::placeholder{color:var(--mu)}
</style>
</head>
<body>
<canvas id="cvs"></canvas>
<div class="ov" id="ov" onclick="closeSb()"></div>

<!-- Settings Panel -->
<div class="sett-panel" id="sett">
  <div class="sett-title">
    <span>⚙ POSTAVKE</span>
    <span class="sett-close" onclick="closeSett()">✕</span>
  </div>
  <div class="sett-sec">Jezik sučelja</div>
  <div class="sett-row">
    <span class="sett-label">Jezik odgovora</span>
    <select class="sett-select" id="sett-lang" onchange="applyLang()">
      <option value="auto">Auto (detekcija)</option>
      <option value="hr">Hrvatski</option>
      <option value="en">English</option>
      <option value="de">Deutsch</option>
      <option value="fr">Français</option>
      <option value="es">Español</option>
    </select>
  </div>
  <div class="sett-sec">Mod rada</div>
  <div class="sett-row">
    <span class="sett-label">Defaultni mod</span>
    <select class="sett-select" id="sett-mode" onchange="applyMode()">
      <option value="fast">Fast (brzi)</option>
      <option value="analysis">Analysis</option>
      <option value="code">Code</option>
      <option value="creative">Creative</option>
    </select>
  </div>
  <div class="sett-sec">Sustav</div>
  <div class="sett-row">
    <span class="sett-label">Verzija</span>
    <span style="font-size:11px;color:var(--acc)">v18.5</span>
  </div>
  <div class="sett-row">
    <span class="sett-label">Moduli</span>
    <span id="sett-mods" style="font-size:10px;color:var(--mu)">Ucitavam...</span>
  </div>
  <button class="sett-btn" onclick="closeSett()">PRIMIJENI</button>
</div>

<aside class="sb" id="sb">
  <div class="sb-hd"><div class="sb-logo">ATLAS</div><div class="sb-sub">OS v18.5 · IMAGO</div></div>
  <div class="sb-bd">
    <div class="sb-sec">Sesija</div>
    <div class="si" onclick="newSess()">✦ &nbsp;Nova sesija</div>
    <div class="si" onclick="doBackup()">☁ &nbsp;Cloud Backup</div>
    <div class="si gh" onclick="doGit()">🐙 &nbsp;GitHub Update</div>
    <div class="si rd" onclick="doClear()">⚠ &nbsp;Obriši memoriju</div>
    <div class="sb-sec">Multimedija</div>
    <div class="si act" id="m-text"  onclick="setMod('text')">📝 &nbsp;Tekst</div>
    <div class="si vm"  id="m-video" onclick="setMod('video')">🎬 &nbsp;Video obrada</div>
    <div class="si am"  id="m-audio" onclick="setMod('audio')">🎵 &nbsp;Audio / Glazba</div>
    <div class="si pm"  id="m-photo" onclick="setMod('photo')">📷 &nbsp;Foto / Slika</div>
    <div class="sb-sec">Autonomija</div>
    <div class="si" onclick="autoHint()">🤖 &nbsp;Auto Mode (auto ...)</div>
    <div class="sb-sec">Postavke</div>
    <div class="si" onclick="openSett()">⚙ &nbsp;Settings</div>
  </div>
  <div class="sb-ft">ATLAS AI OS · Groq + Gemini · v18.5</div>
</aside>
<header class="hdr">
  <button onclick="openSb()" style="background:none;border:none;color:var(--acc);font-size:23px;cursor:pointer;line-height:1">☰</button>
  <div><div class="hdr-logo">ATLAS // IMAGO</div><div class="hdr-sub" id="mlabel">Tekst mod</div></div>
  <div class="met">BAT <span id="cpu">—</span> &nbsp;RAM <span id="mem">—</span>%</div>
  <div class="hdr-r">
    <div class="modp" id="modp">FAST</div>
    <div class="mpill" id="mpill">—</div>
    <div class="wdot" id="wdot"></div>
  </div>
</header>
<div class="mbar" id="mbar"></div>
<div class="chat" id="chat">
  <div class="msg"><div class="mm"><span class="mw atlas">Atlas</span></div>
  <div>Sustav aktivan. Memorija ucitana. Groq + Gemini online.<br>
  <small style="color:var(--mu)">PDF ✓ &nbsp;Slike ✓ &nbsp;Audio ✓ &nbsp;Video ✓ &nbsp;URL ✓ &nbsp;Auto ✓ &nbsp;v18.5</small></div>
  <div class="mt">BOOT · v18.5</div></div>
</div>
<div id="find">📎 <span id="fname"></span><span onclick="clrF()" style="cursor:pointer;color:var(--rd);margin-left:5px">✕</span></div>
<div class="izone">
  <div class="ibox" id="ibox">
    <input type="file" id="fi" style="display:none" onchange="onFile(this)"
      accept="image/*,audio/*,video/*,application/pdf,text/*,.py,.js,.json,.csv,.md,.txt,.xml,.pdf">
    <button class="ibtn" onclick="document.getElementById('fi').click()">📎</button>
    <textarea id="inp" placeholder="Pitaj Atlas... ili 'auto [zadatak]' za autonomni mod" rows="1" oninput="ar(this)" onkeydown="hk(event)"></textarea>
    <button class="ibtn sbtn" id="sbtn" onclick="send()">➤</button>
  </div>
</div>
<script>
let ws,pF=null,typEl=null,cMod='text',forceLang=null;
const MODS={
  text:{label:'Tekst mod',ph:"Pitaj Atlas... ili 'auto [zadatak]' za autonomni mod",cls:''},
  video:{label:'Video obrada',ph:'Montaza, kodeci, FPS, export...',cls:'video',tools:['🎬 Montaza','⚙️ Kodeci','📐 Rezolucija','🎞️ FPS','🔊 Audio sync','📤 Export']},
  audio:{label:'Audio / Glazba',ph:'Mix, EQ, snimanje, format...',cls:'audio',tools:['🎵 Mix',' 🎤 Snimanje','🔉 EQ','🥁 Ritam','📻 Format','💿 Export']},
  photo:{label:'Foto / Slika',ph:'Editing, boja, crop, kompozicija...',cls:'photo',tools:['🖼️ Edit','🎨 Boja','✂️ Crop','💡 Ekspozicija','🔲 Kompozicija','📁 Export']}
};
function setMod(m){cMod=m;const cfg=MODS[m];['text','video','audio','photo'].forEach(x=>document.getElementById('m-'+x).classList.toggle('act',x===m));document.getElementById('mlabel').textContent=cfg.label;document.getElementById('inp').placeholder=cfg.ph;const mp=document.getElementById('modp');mp.textContent=m.toUpperCase();mp.className='modp '+(m!=='text'?m:'');document.getElementById('ibox').className='ibox '+cfg.cls;document.getElementById('sbtn').className='ibtn sbtn '+cfg.cls;const bar=document.getElementById('mbar');if(cfg.tools){bar.className='mbar show '+m;bar.innerHTML=cfg.tools.map(t=>`<button class="mbtn" onclick="qp('${t}')">${t}</button>`).join('');}else{bar.className='mbar';bar.innerHTML='';}if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'media_mode',mode:m}));closeSb();}
function autoHint(){closeSb();document.getElementById('inp').value='auto ';document.getElementById('inp').focus();}
function qp(t){document.getElementById('inp').value=t.replace(/\p{Emoji}/gu,'').trim()+': ';document.getElementById('inp').focus();}
function openSett(){closeSb();document.getElementById('sett').classList.add('open');document.getElementById('ov').classList.add('on');fetch('/modules_status').then(r=>r.json()).then(d=>{document.getElementById('sett-mods').textContent=d.modules||'N/A';}).catch(()=>{document.getElementById('sett-mods').textContent='N/A';});}
function closeSett(){document.getElementById('sett').classList.remove('open');document.getElementById('ov').classList.remove('on');}
function applyLang(){const v=document.getElementById('sett-lang').value;forceLang=v==='auto'?null:v;if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'set_lang',lang:forceLang}));}
function applyMode(){const v=document.getElementById('sett-mode').value;if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'set_mode',mode:v}));}
function conn(){ws=new WebSocket('ws://'+location.host+'/ws');ws.onopen=()=>setWs(true);ws.onclose=()=>{setWs(false);setTimeout(conn,2500);};ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='metrics'){document.getElementById('cpu').textContent=d.data.cpu;document.getElementById('mem').textContent=d.data.mem;return;}rmTyp();if(d.action==='reload'){location.reload();return;}if(d.message)addMsg('atlas',d.message,d.model,d.tags||[],d.mode||'',d.preview||null);if(d.error)addMsg('error',d.error,null,[],'',null);};}
function setWs(on){document.getElementById('wdot').className='wdot '+(on?'on':'off');}
function setPill(model){if(!model)return;const el=document.getElementById('mpill');el.textContent=model.split(' ')[0];const m=model.toLowerCase();el.className='mpill '+(m.includes('gemini')?'gemini':m.includes('error')?'error':'groq');}
function addMsg(type,text,model,tags,mode,preview){const chat=document.getElementById('chat');const now=new Date().toLocaleTimeString('hr',{hour:'2-digit',minute:'2-digit'});const d=document.createElement('div');d.className='msg '+(type==='atlas'?'':type);const who=type==='atlas'?'Atlas':type==='error'?'Greška':'Ti';const wc=type==='atlas'?'atlas':type==='error'?'err':'user';let meta=`<div class="mm"><span class="mw ${wc}">${who}</span>`;if(model){const mc=model.toLowerCase().includes('gemini')?'gemini':'groq';meta+=`<span class="tg ${mc}">${model.split(' ')[0]}</span>`;setPill(model);}['web','url','pdf','vision','cloud','code','analysis','video','audio','photo','auto'].forEach(t=>{if(tags.includes(t))meta+=`<span class="tg ${t}">${t.toUpperCase()}</span>`;});meta+='</div>';if(mode&&!['fast','text','url'].includes(mode)){const mp=document.getElementById('modp');mp.textContent=mode.toUpperCase();mp.className='modp '+(mode==='auto'?'auto':['video','audio','photo'].includes(mode)?mode:'');}let previewHTML='';if(preview){if(preview.type==='image'){previewHTML=`<img class="media-preview" src="${preview.data}" alt="Slika">`;}else if(preview.type==='video'){previewHTML=`<video class="media-preview" controls><source src="${preview.data}" type="${preview.mime}">Video nije podrzан.</video>`;}else if(preview.type==='audio'){previewHTML=`<audio class="media-preview" controls><source src="${preview.data}" type="${preview.mime}">Audio nije podrzан.</audio>`;}}d.innerHTML=meta+previewHTML+`<div>${esc(text)}</div><div class="mt">${now}</div>`;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;}
function showTyp(){const chat=document.getElementById('chat');typEl=document.createElement('div');typEl.className='msg';typEl.innerHTML=`<div class="mm"><span class="mw atlas">Atlas</span></div><div class="dots"><span></span><span></span><span></span></div>`;chat.appendChild(typEl);chat.scrollTop=chat.scrollHeight;}
function rmTyp(){if(typEl){typEl.remove();typEl=null;}}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');}
function ar(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px';}
function hk(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function send(){const inp=document.getElementById('inp');const txt=inp.value.trim();if(!txt&&!pF)return;const chat=document.getElementById('chat');const d=document.createElement('div');d.className='msg user';let prevHTML='';if(pF){if(pF.isImage)prevHTML=`<img class="media-preview" src="${pF.data}" alt="${pF.name}">`;else if(pF.isVideo)prevHTML=`<video class="media-preview" controls><source src="${pF.data}" type="${pF.type}"></video>`;else if(pF.isAudio)prevHTML=`<audio class="media-preview" controls><source src="${pF.data}" type="${pF.type}"></audio>`;else prevHTML=`<div class="fbg">📎 ${pF.name}</div>`;}d.innerHTML=`<div class="mm"><span class="mw user">Ti</span></div>${prevHTML}<div>${esc(txt)}</div>`;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;showTyp();ws.send(JSON.stringify({text:txt,file:pF,mediaMode:cMod,forceLang:forceLang}));inp.value='';inp.style.height='auto';clrF();}
function onFile(input){const file=input.files[0];if(!file)return;const ext=file.name.split('.').pop().toLowerCase();const isImg=file.type.startsWith('image/');const isPdf=ext==='pdf'||file.type==='application/pdf';const isAudio=file.type.startsWith('audio/')||['mp3','wav','ogg','flac','m4a','aac'].includes(ext);const isVideo=file.type.startsWith('video/')||['mp4','mkv','avi','mov','webm'].includes(ext);const reader=new FileReader();reader.onload=e=>{pF={name:file.name,type:file.type,data:e.target.result,isImage:isImg,isPdf:isPdf,isAudio:isAudio,isVideo:isVideo,ext:ext};document.getElementById('find').style.display='block';document.getElementById('fname').textContent=file.name;};if(isImg||isPdf||isAudio||isVideo)reader.readAsDataURL(file);else reader.readAsText(file);}
function clrF(){pF=null;document.getElementById('find').style.display='none';document.getElementById('fi').value='';}
function openSb(){document.getElementById('sb').classList.add('open');document.getElementById('ov').classList.add('on');}
function closeSb(){document.getElementById('sb').classList.remove('open');document.getElementById('ov').classList.remove('on');}
function newSess(){closeSb();location.reload();}
function doBackup(){closeSb();showTyp();ws.send('__BACKUP__');}
function doGit(){closeSb();showTyp();ws.send('__GIT_UPDATE__');}
function doClear(){if(confirm('Obrisati memoriju?')){closeSb();ws.send('__CLEAR__');}}
setInterval(()=>{if(ws&&ws.readyState===1)ws.send('__METRICS__');},4000);
const cvs=document.getElementById('cvs'),ctx=cvs.getContext('2d');let pts=[],W,H;
function resize(){W=cvs.width=window.innerWidth;H=cvs.height=window.innerHeight;}
function spawn(x,y,n=12){for(let i=0;i<n;i++)pts.push({x,y,vx:(Math.random()-.5)*4,vy:(Math.random()-.5)*4,l:1});}
function draw(){ctx.clearRect(0,0,W,H);pts=pts.filter(p=>p.l>0);pts.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.l-=.018;ctx.beginPath();ctx.arc(p.x,p.y,1.8,0,Math.PI*2);ctx.fillStyle=`rgba(14,165,233,${p.l})`;ctx.fill();});requestAnimationFrame(draw);}
cvs.addEventListener('mousedown',e=>spawn(e.clientX,e.clientY));
cvs.addEventListener('touchstart',e=>{e.preventDefault();spawn(e.touches[0].clientX,e.touches[0].clientY);},{passive:false});
window.onresize=resize;resize();draw();conn();
</script>
</body>
</html>"""

# ══════════════════════════════════════
# PWA + MODULES STATUS ENDPOINT
# ══════════════════════════════════════
@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name":"ATLAS OS","short_name":"ATLAS","start_url":"/",
        "display":"standalone","background_color":"#000","theme_color":"#0ea5e9",
        "icons":[{"src":"https://cdn-icons-png.flaticon.com/512/714/714390.png",
                  "sizes":"512x512","type":"image/png"}]
    })

@app.get("/sw.js")
async def sw():
    return HTMLResponse(
        "self.addEventListener('install',e=>self.skipWaiting());"
        "self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
        "self.addEventListener('fetch',e=>{});",
        media_type="application/javascript"
    )

@app.get("/modules_status")
async def modules_status():
    active = []
    if _scout:          active.append("web_scout")
    if _media:          active.append("media_pro")
    if _lingua:         active.append("lingua_core")
    if _security_vault: active.append("vault")
    if _memory_brain:   active.append("vector_brain")
    if _context:        active.append("context_helper")
    return JSONResponse({
        "version": ATLAS_VERSION,
        "modules": ", ".join(active) if active else "—",
        "count": len(active)
    })

@app.get("/")
async def home():
    return HTMLResponse(HTML)

# ══════════════════════════════════════
# WEBSOCKET
# ══════════════════════════════════════
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    await init_db()
    loop          = asyncio.get_event_loop()
    session_media = "text"
    forced_lang   = None
    forced_mode   = None

    while True:
        try:
            raw = await websocket.receive_text()

            if raw == "__METRICS__":
                m = await loop.run_in_executor(None, get_metrics)
                await websocket.send_json({"type":"metrics","data":m}); continue

            if raw == "__CLEAR__":
                await clear_db()
                await websocket.send_json({"action":"reload"}); continue

            if raw == "__BACKUP__":
                msg = await loop.run_in_executor(None, run_backup, "")
                await websocket.send_json({
                    "message":msg,"model":"SYSTEM","tags":["cloud"],"mode":"fast"
                }); continue

            if raw == "__GIT_UPDATE__":
                msg = await loop.run_in_executor(None, run_git_update)
                await websocket.send_json({
                    "message":msg,"model":"SYSTEM","tags":[],"mode":"fast"
                }); continue

            try:
                data = json.loads(raw)
            except:
                data = {"text": raw}

            # Settings controls
            if data.get("type") == "media_mode":
                session_media = data.get("mode","text"); continue
            if data.get("type") == "set_lang":
                forced_lang = data.get("lang"); continue
            if data.get("type") == "set_mode":
                forced_mode = data.get("mode"); continue

            user_msg   = data.get("text","").strip()
            file_data  = data.get("file")
            media_mode = data.get("mediaMode", session_media)
            client_lang = data.get("forceLang")

            if not user_msg and not file_data:
                continue

            # APPROVE TOOL
            if user_msg.lower().startswith("approve:"):
                tool_name = user_msg.split(":", 1)[-1].strip().lower()
                if tool_name in REQUIRES_APPROVAL:
                    approve_tool(tool_name)
                    await websocket.send_json({
                        "message": f"✅ Tool '{tool_name}' odobren za ovu sesiju.",
                        "model": "SYSTEM", "tags": [], "mode": "fast"
                    }); continue

            if user_msg:
                asyncio.create_task(update_profile(user_msg))

            # Jezik: klijent override > forced > auto detekcija
            if client_lang and client_lang in ("hr","en","de","fr","es"):
                lang = client_lang
            elif forced_lang and forced_lang in ("hr","en","de","fr","es"):
                lang = forced_lang
            else:
                lang = detect_language(user_msg) if user_msg else "hr"

            # Lingua hints za ton adaptaciju
            lingua_hints = {}
            if user_msg:
                try:
                    lingua_hints = _lingua_adapt(user_msg)
                except Exception as e:
                    print(f"[LINGUA_ADAPT] {e}")

            # RAG kontekst — dohvati za sistemsku poruku
            rag_context = ""
            if user_msg:
                try:
                    rag_context = _context_get(user_msg)
                except Exception as e:
                    print(f"[RAG_CONTEXT] {e}")

            # MEMORY RECALL
            recall_kw = ["sjeti se","memory","što smo pričali","sto smo pricali",
                         "prethodni razgovor","recall"]
            if user_msg and any(k in user_msg.lower() for k in recall_kw):
                query = re.sub(
                    r'sjeti se|memory|recall|što smo pričali|sto smo pricali|prethodni razgovor',
                    '', user_msg, flags=re.IGNORECASE
                ).strip()
                mem_result = recall(query)
                await save_msg("user", user_msg)
                await save_msg("assistant", mem_result)
                await websocket.send_json({
                    "message": mem_result, "model": "MEMORY",
                    "tags": [], "mode": "fast"
                }); continue

            # TOOL PRIORITY
            if user_msg:
                tool_result = handle_tool_request(user_msg)
                if tool_result is not None:
                    await save_msg("user", user_msg)
                    await save_msg("assistant", tool_result)
                    try: auto_save(user_msg, tool_result)
                    except: pass
                    await websocket.send_json({
                        "message": tool_result, "model": "TOOL",
                        "tags": ["code"], "mode": "code"
                    }); continue

            # BACKUP TRIGGER
            backup_kw = ["prenesi na oblak","upload na oblak","spremi na oblak",
                         "prenesi fajl","backup fajl"]
            if user_msg and any(k in user_msg.lower() for k in backup_kw):
                fname = _detect_backup_file(user_msg)
                msg   = await loop.run_in_executor(None, run_backup, fname)
                await save_msg("user", user_msg)
                await save_msg("assistant", msg)
                await websocket.send_json({
                    "message":msg,"model":"SYSTEM","tags":["cloud"],"mode":"fast"
                }); continue

            # LOCAL MULTIMEDIA PROCESSING
            if file_data and user_msg:
                media_proc = handle_media_processing(file_data, user_msg)
                if media_proc:
                    tag         = media_proc.get("tag","photo")
                    result_text = media_proc.get("result","")
                    await save_msg("user", f"[MEDIA_PROC] {user_msg[:150]}")
                    await save_msg("assistant", result_text)
                    try: auto_save(f"[MEDIA_PROC] {user_msg}", result_text)
                    except: pass
                    await websocket.send_json({
                        "message": result_text, "model": "LOCAL",
                        "tags": [tag], "mode": tag
                    }); continue

            # VISION
            if file_data and file_data.get("isImage"):
                img_data = file_data["data"]
                preview  = {"type":"image","data":img_data,
                            "mime":file_data.get("type","image/jpeg")}
                out, model = await call_vision(img_data, user_msg)
                await save_msg("user", f"[SLIKA] {user_msg[:150]}")
                await save_msg("assistant", out)
                try: auto_save(f"[SLIKA] {user_msg}", out)
                except: pass
                await websocket.send_json({
                    "message":out,"model":model,"tags":["vision"],
                    "mode":"analysis","preview":preview
                }); continue

            # AUDIO
            if file_data and file_data.get("isAudio"):
                audio_data = file_data["data"]
                b64  = audio_data.split(",")[-1] if "," in audio_data else audio_data
                mime = file_data.get("type","audio/mpeg")
                preview = {"type":"audio","data":audio_data,"mime":mime}
                out = await call_gemini_media(
                    b64, mime, user_msg or "Transkribiraj i analiziraj ovaj audio."
                )
                resp_text = out or "Audio analiza nedostupna za ovaj format."
                await save_msg("user", f"[AUDIO] {user_msg[:150]}")
                await save_msg("assistant", resp_text)
                try: auto_save(f"[AUDIO] {user_msg}", resp_text)
                except: pass
                await websocket.send_json({
                    "message":resp_text,"model":"GEMINI","tags":["audio"],
                    "mode":"audio","preview":preview
                }); continue

            # VIDEO
            if file_data and file_data.get("isVideo"):
                video_data = file_data["data"]
                b64  = video_data.split(",")[-1] if "," in video_data else video_data
                mime = file_data.get("type","video/mp4")
                preview = {"type":"video","data":video_data,"mime":mime}
                out = await call_gemini_media(
                    b64, mime, user_msg or "Analiziraj ovaj video sadrzaj."
                )
                resp_text = out or "Video analiza nedostupna za ovaj format."
                await save_msg("user", f"[VIDEO] {user_msg[:150]}")
                await save_msg("assistant", resp_text)
                try: auto_save(f"[VIDEO] {user_msg}", resp_text)
                except: pass
                await websocket.send_json({
                    "message":resp_text,"model":"GEMINI","tags":["video"],
                    "mode":"video","preview":preview
                }); continue

            # AUTO MODE
            if user_msg and user_msg.lower().startswith("auto "):
                goal = user_msg[5:].strip()
                if not goal:
                    await websocket.send_json({
                        "message": "Navedi zadatak nakon 'auto '.",
                        "model": "ATLAS", "tags": [], "mode": "fast"
                    }); continue
                print(f"[AUTO] Goal: {goal}")
                profile = await get_profile()
                history = await get_history(6)
                out, model, steps = await orchestrator(goal, profile, history, lang)
                steps_info = f"\n\n*Koraci: {', '.join(steps)}*" if steps else ""
                await save_msg("user", f"[AUTO] {goal}")
                await save_msg("assistant", out)
                try: auto_save(f"[AUTO] {goal}", out)
                except: pass
                await websocket.send_json({
                    "message": out + steps_info,
                    "model": model, "tags": ["auto"], "mode": "auto"
                }); continue

            # STANDARDNI FLOW
            mode          = forced_mode or detect_mode(user_msg or "")
            tags          = []
            extra_ctx     = ""
            has_real_data = False

            # URL reading
            urls = extract_urls(user_msg) if user_msg else []
            if urls:
                parts = []
                for url in urls[:3]:
                    print(f"[URL] Citam: {url}")
                    content, ctype = await fetch_url_content(url)
                    parts.append(f"[SADRZAJ: {url}]\n{content}")
                    tags.append("pdf" if ctype == "pdf" else "url")
                extra_ctx     = "\n\n" + "\n\n---\n\n".join(parts)
                mode          = "url"
                has_real_data = True

            elif mode == "search":
                is_news = any(k in user_msg.lower()
                              for k in ["vijesti","news","danas","today","trenutno"])
                web = await loop.run_in_executor(None, _web_search, user_msg, is_news)
                if web:
                    injected      = inject_web_results(user_msg, web, lang)
                    extra_ctx     = f"\n\n[WEB REZULTATI]\n{web}"
                    tags.append("web")
                    has_real_data = True
                    user_msg      = injected
                else:
                    # Autonomna pretraga putem scout modula ako DDG faila
                    scout_out = ""
                    try:
                        scout_out = await loop.run_in_executor(None, _scout_search, user_msg)
                    except Exception as e:
                        print(f"[SCOUT_FALLBACK] {e}")
                    if scout_out:
                        injected      = inject_web_results(user_msg, scout_out, lang)
                        extra_ctx     = f"\n\n[WEB REZULTATI - scout]\n{scout_out}"
                        tags.append("web")
                        has_real_data = True
                        user_msg      = injected
                    else:
                        no_data_msg = inject_web_results(user_msg, "", lang)
                        await save_msg("user", user_msg)
                        await save_msg("assistant", no_data_msg)
                        try: auto_save(user_msg, no_data_msg)
                        except: pass
                        await websocket.send_json({
                            "message": no_data_msg, "model": "ATLAS",
                            "tags": [], "mode": "search"
                        }); continue

            # PDF upload
            if file_data and file_data.get("isPdf"):
                fname  = file_data.get("name","dokument.pdf")
                fdata  = file_data.get("data","")
                parsed = _parse_file(fname, fdata)
                extra_ctx    += f"\n\n{parsed}"
                tags.append("pdf")
                has_real_data = True
            elif file_data and not any(file_data.get(k)
                                       for k in ["isImage","isAudio","isVideo","isPdf"]):
                fname    = file_data.get("name","nepoznato")
                fcontent = file_data.get("data","")
                extra_ctx    += f"\n\n{_parse_file(fname, fcontent)}"
                has_real_data = True

            last_task    = await get_last_task()
            task_context = (
                f"{last_task.get('goal','')} → {last_task.get('result','')[:150]}"
                if last_task else ""
            )
            profile = await get_profile()
            history = await get_history(10)

            # build_system s RAG + lingua hints
            sys_prompt = build_system(
                profile, mode, lang, media_mode,
                task_context, has_real_data,
                rag_context, lingua_hints
            )

            user_content = user_msg or ""
            if extra_ctx:
                user_content = f"{user_content}\n{extra_ctx[:3500]}"

            messages = (
                [{"role":"system","content":sys_prompt}]
                + history
                + [{"role":"user","content":user_content}]
            )

            out, model = await call_ai(messages, mode)
            await save_msg("user", (user_msg or "")[:400])
            await save_msg("assistant", out[:600])
            try: auto_save(user_msg or "", out)
            except: pass

            if media_mode != "text" and media_mode not in tags:
                tags.append(media_mode)

            await websocket.send_json({
                "message": out, "model": model,
                "tags": tags, "mode": mode
            })

        except WebSocketDisconnect:
            break
        except Exception as e:
            print(f"[ATLAS ERROR] {e}")
            try:
                await websocket.send_json({
                    "error": f"Greska: {str(e)[:150]}",
                    "tags": [], "mode": "fast"
                })
            except:
                break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)