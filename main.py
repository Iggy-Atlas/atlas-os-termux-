"""
ATLAS OS v21.5
Termux Edition · Groq + Gemini · Ultra-Search (Wikipedia/DDG/ArXiv/OpenLibrary)
"""
import os, uvicorn, httpx, json, asyncio, subprocess, re, base64, io, hashlib, time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import aiosqlite

# ══════════════════════════════════════
# KONFIGURACIJA
# ══════════════════════════════════════
ATLAS_VERSION = "v21.5"
load_dotenv()

GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID       = os.getenv("GOOGLE_CSE_ID", "")
GOOGLE_ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN", "")  # OneDrive backup — NE BRISATI

app         = FastAPI()
DB_PATH     = "database.db"
PROJECT_DIR = Path(os.path.expanduser("~")) / "atlas_os_v1"
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_JSON = PROJECT_DIR / "context.json"

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

_groq_model = _gemini_model = _vision_model = None

URL_BLACKLIST = [
    "api.groq.com", "googleapis.com", "generativelanguage", "openai.com",
    "fonts.googleapis", "cdnjs.cloudflare", "anthropic.com",
    "127.0.0.1", "0.0.0.0", "localhost", "shields.io", "flaticon.com", "github.com/login",
]

REALTIME_KEYWORDS = [
    "2025", "2026", "trendov", "trend", "vijesti", "news", "danas", "today",
    "trenutno", "current", "latest", "najnovij", "aktualno", "breaking", "live", "sada", "now",
]

MAX_MEMORY_BYTES   = 2 * 1024 * 1024
MAX_MEMORY_ENTRIES = 100
MAX_AUTO_STEPS     = 4
AUTO_TIMEOUT       = 30
REQUIRES_APPROVAL  = {"shell", "python", "file_write", "cloud"}
ALLOWED_CMDS       = ["ls", "pwd", "echo"]
_approved_tools: set = set()

# ══════════════════════════════════════
# SOFT IMPORT: psutil
# ══════════════════════════════════════
try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _psutil    = None
    _PSUTIL_OK = False

def _get_mem_percent():
    if _PSUTIL_OK:
        try:
            return round(_psutil.virtual_memory().percent, 1)
        except Exception:
            pass
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mt = int(lines[0].split()[1])
        ma = int(lines[2].split()[1])
        return round((1 - ma / mt) * 100, 1)
    except Exception:
        return "N/A"

# ══════════════════════════════════════
# SOFT MODULE IMPORTS
# ══════════════════════════════════════
_scout = _media = _lingua = _security_vault = _memory_brain = _context = None

for _mod_path, _var in [
    ("modules.tools.web_scout",     "_scout"),
    ("modules.tools.media_pro",     "_media"),
    ("modules.tools.lingua_core",   "_lingua"),
    ("modules.security.vault",      "_security_vault"),
    ("modules.core.vector_brain",   "_memory_brain"),
    ("modules.core.context_helper", "_context"),
]:
    try:
        import importlib
        globals()[_var] = importlib.import_module(_mod_path)
        print(f"[MODULE] {_mod_path} ucitan")
    except Exception as _e:
        print(f"[MODULE] {_mod_path} nedostupan: {_e}")

try:
    from safe_layer import validate_code, validate_url, safe_error
except ImportError:
    def validate_code(c):     return {"safe": True, "reason": ""}
    def validate_url(u):      return {"safe": True, "reason": ""}
    def safe_error(m, c=""):  return f"[ERROR] {m}"

try:
    from web_fix import inject_web_results, build_search_system_prompt
except ImportError:
    def inject_web_results(m, w, l=""):  return m
    def build_search_system_prompt(l=""): return ""

# ══════════════════════════════════════
# MODULE HELPERS
# ══════════════════════════════════════
def _lingua_adapt(msg):
    if not _lingua:
        return {}
    try:
        r = _lingua.adapt_to_user(msg)
        return r if isinstance(r, dict) else {}
    except Exception:
        return {}

def _vault_check(path):
    if not _security_vault:
        return {"status": "ALLOWED"}
    try:
        r = _security_vault.check_access(path)
        return r if isinstance(r, dict) else {"status": "ALLOWED"}
    except Exception:
        return {"status": "ALLOWED"}

def _memory_save(u, r):
    if not _memory_brain:
        return
    try:
        _memory_brain.save(u, r)
    except Exception as e:
        print(f"[VECTOR_BRAIN save] {e}")

def _memory_recall(q):
    if not _memory_brain:
        return ""
    try:
        r = _memory_brain.recall(q)
        if isinstance(r, str):  return r[:1000]
        if isinstance(r, list): return "\n".join(str(x) for x in r[:5])[:1000]
        return ""
    except Exception:
        return ""

async def _context_get(msg):
    if not _context:
        return ""
    try:
        r = _context.get_code_context(msg)
        if asyncio.iscoroutine(r):
            r = await r
        if isinstance(r, str):  return r[:1500]
        if isinstance(r, dict): return json.dumps(r, ensure_ascii=False)[:1500]
        return ""
    except Exception:
        return ""

# ══════════════════════════════════════
# SIDEBAR TOOL WRAPPERS
# ══════════════════════════════════════
def sidebar_media_pro(query="status"):
    if not _media:
        return "[MEDIA PRO] Modul nije učitan."
    try:
        for m in ("process", "run", "analyze"):
            if hasattr(_media, m):
                return str(getattr(_media, m)(query))[:1500]
        return f"[MEDIA PRO] Aktivan. Metode: {[x for x in dir(_media) if not x.startswith('_')]}"
    except Exception as e:
        return f"[MEDIA PRO] Greška: {e}"

def sidebar_vault_status():
    if not _security_vault:
        return "[VAULT] Modul nije učitan."
    try:
        for m in ("status", "get_status"):
            if hasattr(_security_vault, m):
                return str(getattr(_security_vault, m)())[:1000]
        return "[VAULT] Aktivan."
    except Exception as e:
        return f"[VAULT] Greška: {e}"

# ══════════════════════════════════════
# ULTRA-SEARCH — bez Google limita
# Paralelni fallback: Wikipedia + DDG + ArXiv + OpenLibrary
# ══════════════════════════════════════
_search_cache: dict = {}
_search_ts: dict    = {}
GOOGLE_TIMEOUT = 4   # sekunde — brzi timeout, onda fallback


def _scache_get(q):
    k = hashlib.md5(q.encode()).hexdigest()
    if k in _search_cache and time.time() - _search_ts.get(k, 0) < 180:
        return _search_cache[k]
    return None

def _scache_set(q, r):
    k = hashlib.md5(q.encode()).hexdigest()
    _search_cache[k] = r
    _search_ts[k]    = time.time()


async def _google_search(query: str, news: bool = False) -> str:
    """Google Custom Search — kratki timeout da ne blokira."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return ""
    try:
        q      = query[:200] + (" 2026" if news else "")
        params = {"q": q, "cx": GOOGLE_CSE_ID, "key": GOOGLE_API_KEY, "num": 5}
        if news:
            params["dateRestrict"] = "d7"
        async with httpx.AsyncClient(timeout=GOOGLE_TIMEOUT) as client:
            r = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if not items:
                    return ""
                lines = [
                    f"• {it.get('title','')}: {it.get('snippet','')[:180]} [{it.get('link','')}]"
                    for it in items[:5]
                ]
                print(f"[GOOGLE] OK — {len(items)} rezultata")
                return "\n".join(lines)
            print(f"[GOOGLE] {r.status_code} — prelazim na Ultra-Search")
            return ""
    except Exception as e:
        print(f"[GOOGLE] {e} — prelazim na Ultra-Search")
        return ""


async def _wikipedia_search(query: str) -> str:
    """Wikipedia OpenSearch API — bez ključa."""
    try:
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": 4, "format": "json", "utf8": 1,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://en.wikipedia.org/w/api.php", params=params,
                headers={"User-Agent": "Atlas/21.5 (educational bot)"},
            )
            if r.status_code != 200:
                return ""
            results = r.json().get("query", {}).get("search", [])
            if not results:
                return ""
            lines = []
            for item in results[:4]:
                title   = item.get("title", "")
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                link    = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                lines.append(f"• [Wikipedia] {title}: {snippet[:200]} [{link}]")
            print(f"[WIKIPEDIA] OK — {len(results)} rezultata")
            return "\n".join(lines)
    except Exception as e:
        print(f"[WIKIPEDIA] {e}")
        return ""


async def _duckduckgo_search(query: str) -> str:
    """DuckDuckGo Instant Answer API — bez ključa."""
    try:
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.duckduckgo.com/", params=params,
                headers={"User-Agent": "Atlas/21.5"},
            )
            if r.status_code != 200:
                return ""
            data    = r.json()
            results = []
            # Abstract
            abstract = data.get("AbstractText", "")
            ab_url   = data.get("AbstractURL", "")
            if abstract:
                results.append(f"• [DDG] {abstract[:300]} [{ab_url}]")
            # Related Topics
            for topic in data.get("RelatedTopics", [])[:4]:
                if isinstance(topic, dict) and topic.get("Text"):
                    text = topic.get("Text", "")[:200]
                    url  = topic.get("FirstURL", "")
                    results.append(f"• [DDG] {text} [{url}]")
            if not results:
                return ""
            print(f"[DDG] OK — {len(results)} rezultata")
            return "\n".join(results)
    except Exception as e:
        print(f"[DDG] {e}")
        return ""


async def _arxiv_search(query: str) -> str:
    """ArXiv API — za znanstvene radove, bez ključa."""
    try:
        params = {
            "search_query": f"all:{query}",
            "start": 0, "max_results": 3,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://export.arxiv.org/api/query", params=params,
                headers={"User-Agent": "Atlas/21.5"},
            )
            if r.status_code != 200:
                return ""
            entries = re.findall(
                r"<entry>(.*?)</entry>", r.text, re.DOTALL
            )
            if not entries:
                return ""
            lines = []
            for entry in entries[:3]:
                title   = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                link    = re.search(r'href="(https://arxiv\.org/abs/[^"]+)"', entry)
                t_str   = title.group(1).strip().replace("\n", " ") if title else ""
                s_str   = summary.group(1).strip().replace("\n", " ")[:200] if summary else ""
                l_str   = link.group(1) if link else ""
                if t_str:
                    lines.append(f"• [ArXiv] {t_str}: {s_str} [{l_str}]")
            if not lines:
                return ""
            print(f"[ARXIV] OK — {len(lines)} radova")
            return "\n".join(lines)
    except Exception as e:
        print(f"[ARXIV] {e}")
        return ""


async def _openlibrary_search(query: str) -> str:
    """Open Library API — knjige i publikacije, bez ključa."""
    try:
        params = {"q": query, "limit": 3, "fields": "title,author_name,first_publish_year,key"}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://openlibrary.org/search.json", params=params,
                headers={"User-Agent": "Atlas/21.5"},
            )
            if r.status_code != 200:
                return ""
            docs = r.json().get("docs", [])
            if not docs:
                return ""
            lines = []
            for doc in docs[:3]:
                title   = doc.get("title", "")
                authors = ", ".join(doc.get("author_name", [])[:2])
                year    = doc.get("first_publish_year", "")
                key     = doc.get("key", "")
                url     = f"https://openlibrary.org{key}" if key else ""
                lines.append(f"• [OpenLibrary] {title} — {authors} ({year}) [{url}]")
            if not lines:
                return ""
            print(f"[OPENLIBRARY] OK — {len(lines)} knjiga")
            return "\n".join(lines)
    except Exception as e:
        print(f"[OPENLIBRARY] {e}")
        return ""


async def _scout_direct(query: str) -> str:
    """web_scout fallback — direktna veza."""
    if not _scout:
        return ""
    try:
        loop = asyncio.get_event_loop()
        def _run():
            try:
                return _scout.get_live_info(query)
            except Exception as ex:
                print(f"[SCOUT] {ex}")
                return ""
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run), timeout=15
        )
        if isinstance(result, str):  return result[:2000]
        if isinstance(result, dict): return json.dumps(result, ensure_ascii=False)[:2000]
        return ""
    except asyncio.TimeoutError:
        print("[SCOUT] Timeout")
        return ""
    except Exception as e:
        print(f"[SCOUT] {e}")
        return ""


async def web_search(query: str, news: bool = False) -> str:
    """
    Ultra-Search redoslijed:
    1. Google (brzi timeout 4s)
    2. Paralelno: Wikipedia + DuckDuckGo + ArXiv + OpenLibrary
    3. web_scout direktni fallback
    Kombinira sve izvore koji vrate rezultate.
    """
    query = re.sub(r"[<>&\"']", "", query)[:200].strip()
    if not query:
        return ""
    ck     = ("news:" if news else "") + query
    cached = _scache_get(ck)
    if cached:
        return cached

    # 1. Google (kratki timeout)
    google_result = await _google_search(query, news)
    if google_result:
        _scache_set(ck, google_result)
        return google_result

    # 2. Paralelni fallback — svi izvori odjednom
    print("[ULTRA-SEARCH] Google nedostupan — pokrećem paralelnu pretragu")
    tasks = [
        _wikipedia_search(query),
        _duckduckgo_search(query),
        _arxiv_search(query),
        _openlibrary_search(query),
        _scout_direct(query),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    combined_parts = []
    source_labels  = ["Wikipedia", "DuckDuckGo", "ArXiv", "OpenLibrary", "Scout"]
    for label, res in zip(source_labels, results):
        if isinstance(res, str) and res.strip():
            combined_parts.append(res.strip())

    if combined_parts:
        combined = "\n".join(combined_parts)[:3000]
        _scache_set(ck, combined)
        print(f"[ULTRA-SEARCH] OK — {len(combined_parts)} izvora")
        return combined

    print("[ULTRA-SEARCH] Nema rezultata ni iz jednog izvora")
    return ""


# ══════════════════════════════════════
# HELPERS
# ══════════════════════════════════════
def get_current_datetime_str():
    return datetime.now(timezone.utc).strftime("%A, %d. %B %Y. u %H:%M UTC")

def needs_realtime(msg):
    return any(kw in msg.lower() for kw in REALTIME_KEYWORDS)

def save_context_json(u, r, m):
    try:
        with open(CONTEXT_JSON, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": str(datetime.now()),
                "user_msg":  u[:400],
                "response":  r[:600],
                "mode":      m,
                "version":   ATLAS_VERSION,
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONTEXT_JSON] {e}")

def check_permission(tool): return tool not in REQUIRES_APPROVAL or tool in _approved_tools
def approve_tool(tool):     _approved_tools.add(tool)
def blocked(tool):          return f"[BLOCKED] Potrebna dozvola za: {tool}. Pošalji 'approve:{tool}'."

def safe_path(path):
    try:
        full = (PROJECT_DIR / path.lstrip("/")).resolve()
        if not str(full).startswith(str(PROJECT_DIR.resolve())):
            if _vault_check(str(full)).get("status") != "ALLOWED":
                return None
        return full
    except Exception:
        return None

# ══════════════════════════════════════
# AUTO MEMORY
# ══════════════════════════════════════
AUTO_MEMORY_PATH = PROJECT_DIR / "auto_memory.json"

def _dedup(data):
    seen, result = set(), []
    for e in reversed(data):
        k = hashlib.md5((e.get("user", "") + e.get("atlas", "")).encode()).hexdigest()
        if k not in seen:
            seen.add(k)
            result.append(e)
    return list(reversed(result))

def _compress(data, keep=20):
    if len(data) <= keep:
        return data
    recent = data[-keep:]
    older  = data[:-keep]
    comp   = []
    for i in range(0, len(older), 3):
        chunk = older[i:i+3]
        comp.append({
            "timestamp": chunk[-1].get("timestamp", ""),
            "user":  "[SAZETAK] " + " | ".join(e.get("user", "")[:60] for e in chunk),
            "atlas": chunk[-1].get("atlas", "")[:200],
        })
    return comp + recent

def auto_save(u, a):
    try:
        data = []
        if AUTO_MEMORY_PATH.exists() and AUTO_MEMORY_PATH.stat().st_size < MAX_MEMORY_BYTES:
            with open(AUTO_MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data.append({"timestamp": str(datetime.now()), "user": u[:400], "atlas": a[:600]})
        data = _dedup(_compress(data))[-MAX_MEMORY_ENTRIES:]
        with open(AUTO_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AUTO_MEMORY] {e}")
    try:
        _memory_save(u, a)
    except Exception as e:
        print(f"[VECTOR_BRAIN_SAVE] {e}")

def recall(query=""):
    if _memory_brain:
        try:
            vr = _memory_recall(query)
            if vr:
                return f"[Vektorska memorija]\n{vr}"
        except Exception:
            pass
    try:
        if not AUTO_MEMORY_PATH.exists():
            return "Memorija je prazna."
        with open(AUTO_MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return "Memorija je prazna."
        if query:
            filtered = [d for d in data
                        if query.lower() in d.get("user", "").lower()
                        or query.lower() in d.get("atlas", "").lower()]
            data = filtered or data
        lines = [
            f"[{d.get('timestamp','')[:16]}]\nTi: {d.get('user','')}\nAtlas: {d.get('atlas','')}\n"
            for d in reversed(data[-5:])
        ]
        return "Sjećam se:\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Greška: {e}"

# ══════════════════════════════════════
# METRICS
# ══════════════════════════════════════
def get_metrics():
    bat = "N/A"
    try:
        r = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            b    = json.loads(r.stdout)
            icon = "⚡" if b.get("status") != "DISCHARGING" else "🔋"
            bat  = f"{icon}{b.get('percentage', 0)}%"
    except Exception:
        pass
    return {"cpu": bat, "mem": _get_mem_percent()}

def get_modules_status():
    return {
        "scout":  _scout          is not None,
        "media":  _media          is not None,
        "lingua": _lingua         is not None,
        "vault":  _security_vault is not None,
        "brain":  _memory_brain   is not None,
        "ctx":    _context        is not None,
    }

# ══════════════════════════════════════
# DATABASE  (history limit = 5 za brzinu)
# ══════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS memory "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, data TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS tasks "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, result TEXT, timestamp TEXT)"
        )
        await db.commit()

async def save_msg(role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memory (role,content,timestamp) VALUES (?,?,?)",
            (role, str(content)[:600], str(datetime.now()))
        )
        await db.execute(
            "DELETE FROM memory WHERE id NOT IN "
            "(SELECT id FROM memory ORDER BY id DESC LIMIT 20)"
        )
        await db.commit()

async def get_history(limit: int = 5) -> list:    # ← smanjeno na 5 za brzinu
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role,content FROM memory ORDER BY id DESC LIMIT ?", (limit,)
        ) as c:
            rows = await c.fetchall()
    return [{"role": r, "content": cnt} for r, cnt in reversed(rows)]

async def clear_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM memory")
        await db.commit()

async def get_last_task():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT goal,result,timestamp FROM tasks ORDER BY id DESC LIMIT 1"
            ) as c:
                row = await c.fetchone()
        if row:
            return {"goal": row[0], "result": row[1], "timestamp": row[2]}
    except Exception:
        pass
    return {}

def count_tokens(messages):
    return sum(len(str(m.get("content", ""))) for m in messages) // 4

def trim_messages(messages, limit=4500):
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
PROFILE_TRIGGERS = [
    "zovem se", "moje ime", "radim na", "volim", "preferiram",
    "projekt", "koristim", "my name", "i am", "i work", "i like",
]

async def update_profile(msg):
    if not any(k in msg.lower() for k in PROFILE_TRIGGERS):
        return
    try:
        model  = _groq_model or GROQ_MODELS[0]
        prompt = (
            f'Extract user info as JSON only. '
            f'Schema: {{"name":"","preferences":[],"projects":[]}} '
            f'Message: {msg[:300]}'
        )
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 150, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            if r.status_code != 200:
                return
            raw = re.sub(
                r"```json?", "",
                r.json()["choices"][0]["message"]["content"]
            ).replace("```", "").strip()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO profile VALUES (1,?)",
                    (json.dumps(json.loads(raw)),)
                )
                await db.commit()
    except Exception as e:
        print(f"[PROFILE] {e}")

async def get_profile():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT data FROM profile WHERE id=1") as c:
                row = await c.fetchone()
        return json.loads(row[0]) if row else {}
    except Exception:
        return {}

# ══════════════════════════════════════
# LANGUAGE & MODE
# ══════════════════════════════════════
def detect_language(text):
    if _lingua:
        try:
            a    = _lingua_adapt(text)
            lang = a.get("lang", "")
            if lang in ("hr", "en", "de", "fr", "es"):
                return lang
        except Exception:
            pass
    t = text.lower()
    scores = {
        "hr": sum(1 for w in ["što","kako","zašto","gdje","kada","imam","treba","mogu","ovo","nije","da","ali","jer","sam","koji"] if w in t.split()),
        "en": sum(1 for w in ["what","how","why","where","when","have","need","can","this","that","the","and","for","is","are"] if w in t.split()),
        "de": sum(1 for w in ["was","wie","warum","wo","ich","habe","kann","das","und","ist"] if w in t.split()),
        "fr": sum(1 for w in ["que","comment","pourquoi","je","avoir","peut","est","les","des"] if w in t.split()),
        "es": sum(1 for w in ["que","como","por","yo","tengo","puede","los","una","para"] if w in t.split()),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "hr"

def detect_mode(msg):
    m = msg.lower()
    if re.search(r"https?://", m):                                              return "url"
    if any(k in m for k in ["bug","error","greška","kod","debug","fix","python","script","funkcij","code"]): return "code"
    if any(k in m for k in ["zašto","objasni","analiziraj","usporedi","razlika","kako radi","sto je","analyze","explain","compare"]): return "analysis"
    if any(k in m for k in ["ideja","napravi","smisli","kreativan","prijedlog","osmisli","create","design","imagine"]): return "creative"
    if any(k in m for k in ["vijesti","danas","pretrazi","tko je","ko je","cijena","trenutno","news","search","today","arxiv","wikipedia"]): return "search"
    return "fast"

# ══════════════════════════════════════
# TOOL SYSTEM
# ══════════════════════════════════════
def tool_file_write(path, content):
    if not check_permission("file_write"): return blocked("file_write")
    full = safe_path(path)
    if not full: return safe_error("Path traversal blocked", "file_write")
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"[TOOL] Fajl zapisan: {path} ({full.stat().st_size} bytes)"
    except Exception as e:
        return safe_error(str(e), "file_write")

def tool_file_read(path):
    full = safe_path(path)
    if not full: return safe_error("Path traversal blocked", "file_read")
    try:
        return f"[TOOL] {path}:\n{full.read_text(encoding='utf-8')[:3000]}"
    except Exception as e:
        return safe_error(str(e), "file_read")

def tool_list_files(path="."):
    full = safe_path(path)
    if not full: return safe_error("Path traversal blocked", "list_files")
    try:
        return f"[TOOL] Fajlovi u {path}:\n" + "\n".join(f.name for f in full.iterdir())[:2000]
    except Exception as e:
        return safe_error(str(e), "list_files")

def tool_run_python(code):
    if not check_permission("python"): return blocked("python")
    check = validate_code(code)
    if not check["safe"]: return safe_error(check["reason"], "python")
    allowed = {
        "print": None, "len": len, "range": range, "str": str, "int": int, "float": float,
        "list": list, "dict": dict, "bool": bool, "sum": sum, "min": min, "max": max,
        "abs": abs, "round": round, "sorted": sorted, "enumerate": enumerate, "zip": zip,
    }
    out = []
    allowed["print"] = lambda *a, **k: out.append(" ".join(str(x) for x in a))
    try:
        exec(compile(code, "<atlas>", "exec"), {"__builtins__": allowed})
        res = "\n".join(out)
        return f"[TOOL] Python:\n{res[:1000]}" if res else "[TOOL] Python: OK"
    except Exception as e:
        return safe_error(str(e)[:200], "python")

def tool_run_shell(cmd):
    if not check_permission("shell"): return blocked("shell")
    parts = cmd.strip().split()
    if not parts or parts[0] not in ALLOWED_CMDS:
        return safe_error(f"Nije u whitelist. Dozvoljeno: {ALLOWED_CMDS}", "shell")
    try:
        r = subprocess.run(parts, capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR))
        return f"[TOOL] Shell:\n{r.stdout[:1000]}"
    except subprocess.TimeoutExpired:
        return safe_error("Timeout (10s)", "shell")
    except Exception as e:
        return safe_error(str(e), "shell")

def handle_tool_request(msg):
    m = msg.strip()
    if m.startswith("TOOL:file_write:"):
        parts = m.split(":", 3)
        if len(parts) >= 4: return tool_file_write(parts[2], parts[3])
    if m.startswith("TOOL:file_read:"):   return tool_file_read(m.split(":", 2)[-1])
    if m.startswith("TOOL:list_files"):   return tool_list_files(m.split(":", 2)[-1] if m.count(":") >= 2 else ".")
    if m.startswith("TOOL:run_python:"):  return tool_run_python(m.split(":", 2)[-1])
    if m.startswith("TOOL:run_shell:"):   return tool_run_shell(m.split(":", 2)[-1])
    if m.startswith("TOOL:media_pro:"):   return sidebar_media_pro(m.split(":", 2)[-1])
    if m.startswith("TOOL:vault_status"): return sidebar_vault_status()
    lm = m.lower()
    if lm.startswith("pokazi fajlove") or lm.startswith("list files"): return tool_list_files(".")
    match = re.match(r"^(?:procitaj|otvori) fajl (.+)", lm)
    if match: return tool_file_read(match.group(1).strip())
    match = re.match(r"^pokreni: (.+)", m)
    if match: return tool_run_shell(match.group(1).strip())
    return None

# ══════════════════════════════════════
# URL & FILE PARSING
# ══════════════════════════════════════
def extract_urls(text):
    found = re.findall(r"https?://[^\s<>\"{}|\\^`\[\]]+", text)
    return [u for u in found if not any(b in u for b in URL_BLACKLIST)]

async def fetch_url_content(url):
    chk = validate_url(url)
    if not chk["safe"]:
        return f"[BLOCKED] {chk['reason']}", "error"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Accept":     "text/html,application/xhtml+xml,*/*;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, verify=False) as client:
            r  = await client.get(url, headers=headers)
            ct = r.headers.get("content-type", "").lower()
            if "pdf" in ct or url.lower().endswith(".pdf"):
                return _parse_pdf(r.content), "pdf"
            if "json" in ct:
                try:
                    return json.dumps(r.json(), indent=2, ensure_ascii=False)[:3000], "json"
                except Exception:
                    return r.text[:3000], "json"
            html = r.text
            for pat in [
                r"<script[^>]*>.*?</script>", r"<style[^>]*>.*?</style>",
                r"<nav[^>]*>.*?</nav>",       r"<footer[^>]*>.*?</footer>",
                r"<header[^>]*>.*?</header>",  r"<!--.*?-->",
            ]:
                html = re.sub(pat, "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<[^>]+>", " ", html)
            html = re.sub(r"&[a-zA-Z#0-9]+;", " ", html)
            html = re.sub(r"\s+", " ", html).strip()
            return html[:4000], "web"
    except httpx.TimeoutException: return "[Timeout]", "error"
    except httpx.ConnectError:     return "[Greška veze]", "error"
    except Exception as e:         return f"[Greška: {str(e)[:120]}]", "error"

def _parse_pdf(content):
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        text   = ""
        for i, page in enumerate(reader.pages[:12]):
            text += f"\n--- Str. {i+1} ---\n{page.extract_text() or ''}"
        return f"[PDF — {len(reader.pages)} stranica]\n{text[:5000]}"
    except ImportError:
        try:
            raw    = content.decode("latin-1", errors="ignore")
            chunks = re.findall(r"BT\s*(.*?)\s*ET", raw, re.DOTALL)
            texts  = [p for c in chunks for p in re.findall(r"\((.*?)\)", c)]
            result = " ".join(texts)
            if result:
                return f"[PDF parcijalno]\n{result[:4000]}"
        except Exception:
            pass
        return "[PDF učitan. Instaliraj: pip install pypdf]"
    except Exception as e:
        return f"[PDF greška: {str(e)[:100]}]"

def _parse_file(name, content):
    ext = name.lower().split(".")[-1] if "." in name else ""
    if ext == "pdf":
        try:
            b64 = content.split(",")[1] if "," in content else content
            return _parse_pdf(base64.b64decode(b64))
        except Exception as e:
            return f"[PDF greška: {e}]"
    if ext == "csv":
        return "[CSV]\n" + "\n".join(content.split("\n")[:50])
    if ext == "json":
        try:
            return f"[JSON]\n{json.dumps(json.loads(content), indent=2, ensure_ascii=False)[:3000]}"
        except Exception:
            pass
    return f"[Fajl: {name}]\n{content[:3000]}"

# ══════════════════════════════════════
# BACKUP & GIT
# ══════════════════════════════════════
def run_backup(filepath=""):
    if filepath:
        if not check_permission("cloud"): return blocked("cloud")
        full = safe_path(filepath)
        if not full or not full.exists(): return f"Fajl nije pronađen: {filepath}"
        try:
            r = subprocess.run(
                ["rclone", "copy", str(full), "remote:AtlasBackup/"],
                capture_output=True, text=True, timeout=60
            )
            return f"Fajl prenesen: {full.name}" if r.returncode == 0 else f"rclone greška: {r.stderr[:200]}"
        except FileNotFoundError:         return "rclone nije instaliran."
        except subprocess.TimeoutExpired: return "Backup timeout."
        except Exception as e:            return f"Backup greška: {str(e)[:100]}"
    try:
        r = subprocess.run(
            ["python", "cloud_backup.py"],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_DIR)
        )
        return "Backup završen." if r.returncode == 0 else f"Backup greška: {r.stderr[:200]}"
    except subprocess.TimeoutExpired: return "Backup timeout."
    except Exception as e:            return f"Backup greška: {str(e)[:100]}"

def _detect_backup_file(msg):
    for p in [
        r"prenesi\s+[\"']?(.+?)[\"']?\s+na\s+oblak",
        r"upload\s+[\"']?(.+?)[\"']?\s+(?:na|to)\s+(?:oblak|cloud)",
        r"spremi\s+[\"']?(.+?)[\"']?\s+na\s+oblak",
    ]:
        m = re.search(p, msg.lower())
        if m: return m.group(1).strip()
    return ""

def run_git_update():
    try:
        r = subprocess.run(
            ["git", "pull"], capture_output=True, text=True,
            timeout=60, cwd=str(PROJECT_DIR)
        )
        return (
            f"GitHub update uspješan.\n{r.stdout[:300]}"
            if r.returncode == 0
            else f"Git greška:\n{r.stderr[:300]}"
        )
    except Exception as e:
        return f"Git greška: {e}"

# ══════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════
LANG_RULES = {
    "hr": "Jezik: standardni hrvatski književni. Gramatički ispravno. Bez ijekavice.",
    "en": "Language: fluent, natural English.",
    "de": "Sprache: fließendes, natürliches Deutsch.",
    "fr": "Langue: français courant et naturel.",
    "es": "Idioma: español fluido y natural.",
}
MODE_INSTRUCTIONS = {
    "code":     "Samo kod + kratko objašnjenje.",
    "analysis": "Korak po korak. Jasan zaključak.",
    "creative": "Originalno. Izbjegavaj klišeje.",
    "search":   "Koristi ISKLJUČIVO priložene web podatke. Ako nema — reci da nema.",
    "url":      "Analiziraj učitani sadržaj. Ključne točke.",
    "fast":     "Direktno i kratko.",
    "video":    "Stručnjak za video produkciju.",
    "audio":    "Stručnjak za audio i glazbu.",
    "photo":    "Stručnjak za fotografiju.",
}

def build_system(profile, mode, lang, media_mode,
                 task_context="", has_real_data=False,
                 rag_context="", lingua_hints=None):
    name     = profile.get("name", "")
    prefs    = profile.get("preferences", [])
    projects = profile.get("projects", [])
    user_ctx = ""
    if name:     user_ctx += f"Korisnik: {name}. "
    if prefs:    user_ctx += f"Interesi: {', '.join(prefs[:4])}. "
    if projects: user_ctx += f"Projekti: {', '.join(projects[:3])}. "

    media_ctx  = f" MULTIMEDIJSKI MOD: {media_mode.upper()}." if media_mode != "text" else ""
    task_ctx   = f"\nPRETHODNI ZADATAK: {task_context}" if task_context else ""
    rag_addon  = f"\n[RAG KONTEKST]\n{rag_context[:1200]}" if rag_context else ""
    tone_hint  = f"\nTON: {lingua_hints.get('tone','')}" if lingua_hints and lingua_hints.get("tone") else ""

    dt          = get_current_datetime_str()
    date_anchor = (
        f"\nDANAS JE: {dt}. Znanje se ažurira putem Ultra-Search sustava "
        "(Wikipedia, DuckDuckGo, ArXiv, OpenLibrary, Google). "
        "Ako nema rezultata — priznaš to."
    )
    truth_mode = "" if has_real_data else (
        "\nANTI-HALLUCINATION: Priznaš da nemaš svježe informacije ako nema [WEB REZULTATI]."
    )
    mods = [m for m, v in [
        ("web_scout", _scout), ("media_pro", _media), ("lingua_core", _lingua),
        ("context_helper", _context), ("vector_brain", _memory_brain), ("vault", _security_vault),
    ] if v] + [("google_search" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "ultra_search_only")]

    return (
        f"Ti si ATLAS — napredni AI operativni sustav. {ATLAS_VERSION}{media_ctx}\n"
        f"MOD: {mode.upper()} — {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['fast'])}\n"
        f"{LANG_RULES.get(lang, LANG_RULES['hr'])}\n"
        "KARAKTER: Direktan. Iskren. Bez laskanja. Bez 'Naravno!' i sličnih fraza.\n"
        "SPOSOBNOSTI: URL/PDF čitanje. Ultra-Search (Wiki+DDG+ArXiv+OpenLibrary). Cloud backup. Multimedija.\n"
        + (f"PROFIL: {user_ctx}\n" if user_ctx else "")
        + task_ctx + date_anchor + truth_mode + rag_addon + tone_hint
        + f"\nAKTIVNI MODULI: {', '.join(mods)}\n"
        + "Kod u blokovima. Tablice u markdown formatu."
    )

# ══════════════════════════════════════
# AI ENGINE
# ══════════════════════════════════════
_response_cache: dict = {}

def _ck(messages, temp):
    return hashlib.md5(
        (json.dumps(messages, sort_keys=True) + str(temp)).encode()
    ).hexdigest()

def _cache_get(k):
    e = _response_cache.get(k)
    if e and time.time() - e["ts"] < 300:
        return e["val"]
    return None

def _cache_set(k, v):
    if len(_response_cache) > 200:
        del _response_cache[min(_response_cache, key=lambda x: _response_cache[x]["ts"])]
    _response_cache[k] = {"val": v, "ts": time.time()}

async def call_groq(messages, temp):
    global _groq_model
    messages = trim_messages(messages, 4500)
    ck       = _ck(messages, temp)
    cached   = _cache_get(ck)
    if cached:
        return cached
    order = [_groq_model] + [m for m in GROQ_MODELS if m != _groq_model] if _groq_model else GROQ_MODELS
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": temp, "max_tokens": 1000},
                )
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
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={"model": model, "messages": messages, "temperature": temp, "max_tokens": 700},
                    )
                    if r2.status_code == 200:
                        _groq_model = model
                        result = r2.json()["choices"][0]["message"]["content"]
                        _cache_set(ck, result)
                        return result
                if r.status_code == 429:
                    print(f"[GROQ] {model} rate limit")
                    continue
                print(f"[GROQ] {model} — {r.status_code}")
            except Exception as e:
                print(f"[GROQ] {model}: {e}")
                continue
    _groq_model = None
    return None

async def call_gemini(messages):
    global _gemini_model
    prompt = "\n".join(
        f"{'ATLAS' if m['role'] == 'assistant' else 'KORISNIK'}: {m['content']}"
        for m in messages if isinstance(m.get("content"), str)
    )
    if len(prompt) > 18000:
        prompt = prompt[-18000:]
    order = [_gemini_model] + [m for m in GEMINI_MODELS if m != _gemini_model] if _gemini_model else GEMINI_MODELS
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200}},
                )
                if r.status_code == 200:
                    cands = r.json().get("candidates", [])
                    if cands:
                        text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            if _gemini_model != model:
                                print(f"[GEMINI] Aktivan: {model}")
                                _gemini_model = model
                            return text
                if r.status_code == 429:
                    print(f"[GEMINI] {model} rate limit")
                    continue
                print(f"[GEMINI] {model} — {r.status_code}")
            except Exception as e:
                print(f"[GEMINI] {model}: {e}")
                continue
    _gemini_model = None
    return None

async def call_vision(image_b64, prompt, mime="image/jpeg"):
    global _vision_model
    order = [_vision_model] + [m for m in GROQ_VISION_MODELS if m != _vision_model] if _vision_model else GROQ_VISION_MODELS
    async with httpx.AsyncClient(timeout=60) as client:
        for model in order:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ]}]},
                )
                if r.status_code == 200:
                    result = r.json()["choices"][0]["message"]["content"]
                    if _vision_model != model:
                        print(f"[VISION] Aktivan: {model}")
                        _vision_model = model
                    return result
                if r.status_code == 429:
                    print(f"[VISION] {model} rate limit")
                    continue
                print(f"[VISION] {model} — {r.status_code}")
            except Exception as e:
                print(f"[VISION] {model}: {e}")
                continue
    _vision_model = None
    return None

async def call_ai(messages, temp=0.7, prefer_gemini=False):
    if prefer_gemini:
        r = await call_gemini(messages)
        if r: return r
        r = await call_groq(messages, temp)
        if r: return r
    else:
        r = await call_groq(messages, temp)
        if r: return r
        r = await call_gemini(messages)
        if r: return r
    return "[ATLAS] Oba AI servisa su nedostupna. Provjeri API ključeve i konekciju."

def detect_media_mode(msg, has_image=False):
    if has_image: return "photo"
    m = msg.lower()
    if any(k in m for k in ["video","film","montaža","editing","reels","shorts","premiere","davinci"]): return "video"
    if any(k in m for k in ["audio","glazb","muzik","mixing","mastering","sound","daw","ableton","fl studio"]): return "audio"
    if any(k in m for k in ["foto","slika","kamera","lightroom","photoshop","raw"]): return "photo"
    return "text"

async def agentic_pipeline(user_msg, history, profile, lang, mode, media_mode,
                            web_data="", rag_ctx="", lingua_h=None):
    sys_p    = build_system(profile, mode, lang, media_mode,
                             has_real_data=bool(web_data), rag_context=rag_ctx, lingua_hints=lingua_h)
    messages = [{"role": "system", "content": sys_p}] + history[-8:]
    uc       = f"[WEB REZULTATI]\n{web_data}\n\n{user_msg}" if web_data else user_msg
    messages.append({"role": "user", "content": uc})
    steps = 0
    acc   = []
    while steps < MAX_AUTO_STEPS:
        try:
            response = await asyncio.wait_for(call_ai(messages, temp=0.7), timeout=AUTO_TIMEOUT)
        except asyncio.TimeoutError:
            acc.append("[ATLAS] Timeout.")
            break
        acc.append(response)
        steps += 1
        if not re.search(r"\[NEXT_STEP\]|\[NASTAVI\]|\[CONTINUE\]", response, re.IGNORECASE):
            break
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": "Nastavi s idućim korakom. Budi koncizan."})
    return "\n\n".join(acc)

# ══════════════════════════════════════
# MAIN PROCESS FUNCTION
# ══════════════════════════════════════
async def process_message(user_msg, history,
                          image_b64="", image_mime="image/jpeg",
                          file_name="", file_content=""):
    if user_msg.lower().startswith("approve:"):
        tool = user_msg.split(":", 1)[1].strip()
        approve_tool(tool)
        return f"[ATLAS] Alat '{tool}' je odobren."

    tool_result = handle_tool_request(user_msg)
    if tool_result:
        await save_msg("user", user_msg)
        await save_msg("assistant", tool_result)
        auto_save(user_msg, tool_result)
        return tool_result

    lm = user_msg.lower().strip()
    if lm in ("recall", "memorija", "sjeti se", "zapamti sve"):
        return recall(user_msg if len(user_msg) > 10 else "")
    if lm in ("clear", "zaboravi", "reset memorije"):
        await clear_db()
        return "[ATLAS] Memorija obrisana."
    if lm in ("backup", "spremi na oblak"):
        return run_backup()
    if re.match(r"^(backup|prenesi)\s+(.+)", lm):
        fp = _detect_backup_file(user_msg)
        return run_backup(fp) if fp else run_backup()
    if lm in ("git pull", "update", "azuriraj kod"):
        return run_git_update()
    if lm.startswith("recall:"):
        return recall(user_msg.split(":", 1)[1].strip())

    lang       = detect_language(user_msg)
    has_image  = bool(image_b64)
    media_mode = detect_media_mode(user_msg, has_image)
    mode       = detect_mode(user_msg)
    if has_image:
        mode = "analysis"

    lingua_h = _lingua_adapt(user_msg) if _lingua else {}

    await update_profile(user_msg)
    profile  = await get_profile()
    rag_ctx  = await _context_get(user_msg)

    file_ctx = ""
    if file_name and file_content:
        file_ctx = _parse_file(file_name, file_content)

    url_ctx = ""
    urls    = extract_urls(user_msg)
    if urls:
        mode = "url"
        for url in urls[:2]:
            c, _ = await fetch_url_content(url)
            url_ctx += f"\n[URL: {url}]\n{c[:3000]}\n"

    web_data = ""
    if needs_realtime(user_msg) or mode == "search":
        news     = any(k in user_msg.lower() for k in ["vijesti","news","breaking","danas","today"])
        web_data = await web_search(user_msg, news=news)

    extra_ctx = ""
    if url_ctx:  extra_ctx += url_ctx
    if file_ctx: extra_ctx += f"\n{file_ctx}"
    if rag_ctx:  extra_ctx += f"\n[RAG]\n{rag_ctx}"

    full_msg = f"{extra_ctx}\n\nKORISNIČKI UPIT: {user_msg}" if extra_ctx else user_msg

    if has_image:
        vp = f"Analiziraj ovu sliku. Kontekst korisnika: {user_msg}\nOdgovaraj na jeziku: {lang}"
        vr = await call_vision(image_b64, vp, image_mime)
        if vr:
            await save_msg("user",      f"[SLIKA] {user_msg}")
            await save_msg("assistant", vr)
            auto_save(user_msg, vr)
            save_context_json(user_msg, vr, "vision")
            return vr

    await save_msg("user", user_msg)
    response = await agentic_pipeline(
        full_msg, history, profile, lang, mode, media_mode,
        web_data=web_data, rag_ctx=rag_ctx, lingua_h=lingua_h,
    )
    await save_msg("assistant", response)
    auto_save(user_msg, response)
    save_context_json(user_msg, response, mode)
    return response

# ══════════════════════════════════════
# FASTAPI ROUTES
# ══════════════════════════════════════
@app.on_event("startup")
async def startup():
    await init_db()
    print(f"[ATLAS] {ATLAS_VERSION} pokrenut — Ultra-Search aktivan")

@app.get("/metrics")
async def metrics_ep():
    return JSONResponse(get_metrics())

@app.get("/modules")
async def modules_ep():
    return JSONResponse(get_modules_status())

@app.get("/history")
async def history_ep():
    return JSONResponse(await get_history(20))

@app.get("/task")
async def task_ep():
    return JSONResponse(await get_last_task())

@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await ws.accept()
    print("[WS] Klijent spojen")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                data = {"message": raw}

            user_msg     = data.get("message", "").strip()
            image_b64    = data.get("image_b64", "")
            image_mime   = data.get("image_mime", "image/jpeg")
            file_name    = data.get("file_name", "")
            file_content = data.get("file_content", "")

            if not user_msg and not image_b64 and not file_name:
                await ws.send_text(json.dumps({"type": "error", "content": "Prazna poruka"}))
                continue

            history = await get_history(5)   # ← 5 poruka za brzinu
            await ws.send_text(json.dumps({"type": "typing", "content": "..."}))

            try:
                response = await process_message(
                    user_msg, history,
                    image_b64=image_b64, image_mime=image_mime,
                    file_name=file_name, file_content=file_content,
                )
            except Exception as e:
                print(f"[WS] {e}")
                response = f"[ATLAS] Greška: {str(e)[:200]}"

            await ws.send_text(json.dumps({
                "type":    "message",
                "content": response,
                "mode":    detect_mode(user_msg),
                "lang":    detect_language(user_msg),
            }))
    except WebSocketDisconnect:
        print("[WS] Klijent odspojio")
    except Exception as e:
        print(f"[WS] {e}")


# ══════════════════════════════════════
# HTML UI  — ATLAS OS v21.5
# Koristi r""" (raw string) — nema SyntaxWarning s kosim crtama
# ══════════════════════════════════════
HTML_UI = r"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ATLAS OS v21.5</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0c10;--sf:#111318;--sf2:#181c24;--bd:#1e2430;
  --ac:#00c8ff;--ac2:#7b61ff;--ok:#00e676;--wn:#ffd740;--dn:#ff5252;
  --tx:#e8eaf0;--td:#6b7280;--tm:#9ca3af;
  --r:10px;--rs:6px;--sw:240px;--hh:48px;
  --mono:'JetBrains Mono','Fira Code',monospace;
  --ui:'Segoe UI',system-ui,sans-serif;
}
html,body{height:100%;background:var(--bg);color:var(--tx);font-family:var(--ui);font-size:14px;overflow:hidden}
#app{display:flex;height:100vh;width:100vw;overflow:hidden}

/* ── OVERLAY ── */
#ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:40;backdrop-filter:blur(3px);transition:opacity .2s}
#ov.show{display:block}

/* ── SIDEBAR ── */
#sb{
  width:var(--sw);min-width:var(--sw);background:var(--sf);
  border-right:1px solid var(--bd);display:flex;flex-direction:column;
  overflow:hidden;z-index:50;
  transition:transform .28s cubic-bezier(.4,0,.2,1),width .28s cubic-bezier(.4,0,.2,1),min-width .28s;
}
/* Desktop — collapse via width */
#sb.col{width:0;min-width:0;border-right:none}

/* Mobile — slide over content */
@media(max-width:640px){
  #sb{position:fixed;top:0;left:0;height:100%;
    width:var(--sw)!important;min-width:var(--sw)!important;
    border-right:1px solid var(--bd)!important;
    transform:translateX(0)}
  #sb.col{transform:translateX(calc(-1 * var(--sw)));
    width:var(--sw)!important;min-width:var(--sw)!important;
    border-right:1px solid var(--bd)!important}
}

/* Sidebar scrolls if screen is short */
#sb-inner{display:flex;flex-direction:column;height:100%;overflow-y:auto;overflow-x:hidden}
#sb-inner::-webkit-scrollbar{width:3px}
#sb-inner::-webkit-scrollbar-thumb{background:var(--bd)}

.sb-head{padding:12px 14px 10px;border-bottom:1px solid var(--bd);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.sb-logo{display:flex;align-items:center;gap:8px}
.an{font-size:15px;font-weight:700;letter-spacing:.04em;color:var(--ac);white-space:nowrap}
.av{font-size:10px;color:var(--td);white-space:nowrap}
#btn-xsb{background:none;border:none;color:var(--td);font-size:18px;cursor:pointer;
  padding:2px 6px;border-radius:var(--rs);transition:color .15s;line-height:1;flex-shrink:0}
#btn-xsb:hover{color:var(--dn)}

/* Metrics */
.sb-met{padding:10px 14px;border-bottom:1px solid var(--bd);display:flex;flex-direction:column;gap:5px;flex-shrink:0}
.mr{display:flex;align-items:center;justify-content:space-between;font-size:11px;white-space:nowrap}
.ml{font-size:9px;color:var(--td);letter-spacing:.05em;text-transform:uppercase}
.mv{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--ac)}
.bw{height:3px;background:var(--bd);border-radius:2px;overflow:hidden;margin-top:2px}
.bf{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .4s}

/* Nav */
.sb-nav{padding:4px 0}
.ns{padding:7px 14px 2px;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--td)}
.ni{display:flex;align-items:center;gap:8px;padding:7px 14px;cursor:pointer;
  font-size:12.5px;color:var(--tm);transition:background .15s,color .15s;
  white-space:nowrap;overflow:hidden;border-left:2px solid transparent;user-select:none}
.ni:hover{background:var(--sf2);color:var(--tx)}
.ni.active{background:rgba(0,200,255,.08);color:var(--ac);border-left-color:var(--ac)}
.ni .ico{font-size:14px;flex-shrink:0}
.tb{margin-left:auto;font-size:9px;padding:1px 5px;border-radius:8px;
  background:rgba(0,200,255,.12);color:var(--ac);border:1px solid rgba(0,200,255,.2);
  white-space:nowrap;flex-shrink:0;transition:all .2s}
.tb.off{background:rgba(255,255,255,.04);color:var(--td);border-color:var(--bd)}

/* Sub-categories */
.sub-cat{overflow:hidden;max-height:0;transition:max-height .3s ease}
.sub-cat.open{max-height:300px}
.sub-item{display:flex;align-items:center;gap:6px;padding:5px 14px 5px 32px;cursor:pointer;
  font-size:12px;color:var(--td);transition:color .15s,background .15s;border-left:2px solid transparent}
.sub-item:hover{color:var(--ac);background:rgba(0,200,255,.05)}

/* Settings */
.sb-set{padding:10px 14px;border-top:1px solid var(--bd);flex-shrink:0}
.sr{display:flex;align-items:center;justify-content:space-between;padding:3px 0;font-size:11px}
.sr label{color:var(--td);font-size:9px;text-transform:uppercase;letter-spacing:.05em}
.sr select{background:var(--sf2);border:1px solid var(--bd);color:var(--tx);
  font-size:11px;padding:2px 6px;border-radius:4px;outline:none;cursor:pointer}
.sr select:focus{border-color:var(--ac)}

/* Module dots */
.sb-mods{padding:8px 14px;border-top:1px solid var(--bd);font-size:10px;color:var(--td);flex-shrink:0}
.md{display:flex;align-items:center;gap:5px;padding:2px 0;white-space:nowrap}
.dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.dot.on{background:var(--ok)}
.dot.off{background:var(--td)}

/* ── MAIN ── */
#main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
#hdr{height:var(--hh);min-height:var(--hh);background:var(--sf);border-bottom:1px solid var(--bd);
  display:flex;align-items:center;padding:0 12px;gap:8px;flex-shrink:0}
#btn-sb{background:none;border:none;color:var(--tm);font-size:18px;cursor:pointer;
  padding:4px 6px;border-radius:var(--rs);flex-shrink:0;transition:color .15s}
#btn-sb:hover{color:var(--ac)}
#htitle{font-size:13px;font-weight:600;color:var(--tx);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hb{font-size:10px;padding:2px 7px;border-radius:20px;background:rgba(0,200,255,.1);
  color:var(--ac);border:1px solid rgba(0,200,255,.2);white-space:nowrap}
#conn{font-size:10px;padding:2px 7px;border-radius:20px;white-space:nowrap}
#conn.ok{background:rgba(0,230,118,.1);color:var(--ok);border:1px solid rgba(0,230,118,.2)}
#conn.err{background:rgba(255,82,82,.1);color:var(--dn);border:1px solid rgba(255,82,82,.2)}
#conn.con{background:rgba(255,215,64,.1);color:var(--wn);border:1px solid rgba(255,215,64,.2)}

/* ── CHAT ── */
#chat{flex:1;overflow-y:auto;padding:14px 12px 6px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-thumb{background:var(--bd);border-radius:2px}
.msg{display:flex;flex-direction:column;max-width:90%;animation:fi .2s ease}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.msg.user{align-self:flex-end}
.msg.atlas{align-self:flex-start}
.bubble{padding:9px 13px;border-radius:var(--r);line-height:1.55;font-size:13.5px;word-break:break-word;position:relative}
.msg.user .bubble{background:linear-gradient(135deg,rgba(0,200,255,.18),rgba(123,97,255,.18));border:1px solid rgba(0,200,255,.25);border-bottom-right-radius:2px}
.msg.atlas .bubble{background:var(--sf2);border:1px solid var(--bd);border-bottom-left-radius:2px}
.ma{display:flex;gap:4px;margin-top:4px;opacity:0;transition:opacity .15s}
.msg:hover .ma{opacity:1}
.msg.user .ma{align-self:flex-end}
.ab{background:var(--sf);border:1px solid var(--bd);color:var(--td);font-size:10px;
  padding:2px 7px;border-radius:4px;cursor:pointer;transition:color .15s,border-color .15s}
.ab:hover{color:var(--ac);border-color:var(--ac)}
.mm{font-size:10px;color:var(--td);margin-top:3px;padding:0 2px}
.msg.user .mm{text-align:right}
.msg.atlas .mm{text-align:left}

/* Typing */
#typ{display:none;align-self:flex-start;padding:8px 14px;background:var(--sf2);
  border:1px solid var(--bd);border-radius:var(--r);border-bottom-left-radius:2px;font-size:12px;color:var(--td)}
#typ.show{display:flex;align-items:center;gap:6px}
.db{width:5px;height:5px;background:var(--ac);border-radius:50%;animation:b .8s infinite}
.db:nth-child(2){animation-delay:.15s}
.db:nth-child(3){animation-delay:.30s}
@keyframes b{0%,80%,100%{transform:scale(.6);opacity:.4}40%{transform:scale(1);opacity:1}}

/* Code */
pre{background:#0d0f14;border:1px solid var(--bd);border-radius:var(--rs);padding:10px 12px;
  overflow-x:auto;font-family:var(--mono);font-size:12px;line-height:1.5;margin:6px 0;position:relative}
.cc{position:absolute;top:6px;right:6px;background:var(--sf);border:1px solid var(--bd);
  color:var(--td);font-size:10px;padding:2px 7px;border-radius:4px;cursor:pointer;transition:color .15s}
.cc:hover{color:var(--ac)}
code{font-family:var(--mono);font-size:12px}
p code{background:rgba(255,255,255,.06);padding:1px 5px;border-radius:3px}

/* Input */
#ia{background:var(--sf);border-top:1px solid var(--bd);padding:8px 10px;
  display:flex;flex-direction:column;gap:6px;flex-shrink:0}
#fp{display:none;align-items:center;gap:6px;padding:5px 10px;background:var(--sf2);
  border:1px solid var(--bd);border-radius:var(--rs);font-size:11px;color:var(--tm)}
#fp.show{display:flex}
#fpn{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#fpc{background:none;border:none;color:var(--dn);cursor:pointer;font-size:14px;padding:0 2px}
.ir{display:flex;align-items:flex-end;gap:6px}
#mi{flex:1;background:var(--sf2);border:1px solid var(--bd);border-radius:var(--rs);
  color:var(--tx);font-family:var(--ui);font-size:13.5px;padding:8px 11px;
  resize:none;outline:none;min-height:36px;max-height:130px;overflow-y:hidden;
  line-height:1.5;transition:border-color .15s}
#mi:focus{border-color:var(--ac)}
#mi::placeholder{color:var(--td)}
.ibt{display:flex;gap:4px;flex-shrink:0;align-items:flex-end}
.ib{width:36px;height:36px;background:var(--sf2);border:1px solid var(--bd);
  border-radius:var(--rs);color:var(--tm);font-size:16px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:color .15s,border-color .15s}
.ib:hover{color:var(--ac);border-color:var(--ac)}
#bsnd{width:36px;height:36px;background:var(--ac);border:none;border-radius:var(--rs);
  color:#000;font-size:17px;cursor:pointer;display:flex;align-items:center;justify-content:center;
  flex-shrink:0;transition:background .15s,opacity .15s}
#bsnd:disabled{opacity:.4;cursor:default}
#bsnd:not(:disabled):hover{background:#33d4ff}
input[type=file]{display:none}

/* Toast */
#toast{position:fixed;bottom:70px;left:50%;transform:translateX(-50%) translateY(8px);
  background:var(--sf2);border:1px solid var(--bd);color:var(--tx);
  font-size:12px;padding:6px 16px;border-radius:20px;opacity:0;pointer-events:none;
  transition:opacity .2s,transform .2s;white-space:nowrap;z-index:999}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* Search source badge inside messages */
.src-badge{display:inline-block;font-size:9px;padding:1px 5px;border-radius:4px;
  background:rgba(0,200,255,.1);border:1px solid rgba(0,200,255,.2);
  color:var(--ac);margin-left:4px;vertical-align:middle}
</style>
</head>
<body>
<div id="ov" onclick="closeSB()"></div>
<div id="app">

<!-- ══ SIDEBAR ══ -->
<aside id="sb" class="col">
  <div id="sb-inner">

    <div class="sb-head">
      <div class="sb-logo">
        <span style="font-size:20px">⬡</span>
        <div><div class="an">ATLAS OS</div><div class="av">v21.5</div></div>
      </div>
      <button id="btn-xsb" onclick="closeSB()">✕</button>
    </div>

    <!-- Metrike -->
    <div class="sb-met">
      <div class="ns" style="padding:0 0 3px" data-i18n="sys">SISTEM</div>
      <div class="mr"><span class="ml">BAT</span><span class="mv" id="m-bat">—</span></div>
      <div class="mr"><span class="ml">RAM</span><span class="mv" id="m-ram">—</span></div>
      <div class="bw"><div class="bf" id="m-bar" style="width:0%"></div></div>
    </div>

    <!-- Navigacija -->
    <nav class="sb-nav">
      <div class="ns" data-i18n="nav">NAVIGACIJA</div>
      <div class="ni active" onclick="navC(this)"><span class="ico">💬</span><span data-i18n="nav_chat">Chat</span></div>
      <div class="ni" onclick="navC(this);qCmd('recall')"><span class="ico">🧠</span><span data-i18n="nav_mem">Memorija</span></div>
      <div class="ni" onclick="navC(this);qCmd('TOOL:list_files')"><span class="ico">📁</span><span data-i18n="nav_files">Fajlovi</span></div>

      <!-- KATEGORIJE s grananjem -->
      <div class="ns" data-i18n="cat_section">KATEGORIJE</div>

      <div class="ni" onclick="toggleCat('cat-mm')">
        <span class="ico">🎬</span><span data-i18n="cat_media">Multimedija</span>
        <span class="ico" style="margin-left:auto;font-size:11px" id="arr-mm">▸</span>
      </div>
      <div class="sub-cat" id="cat-mm">
        <div class="sub-item" onclick="qCmd('Pomozi mi s video montažom')">🎞 Video</div>
        <div class="sub-item" onclick="qCmd('Pomozi mi s audio miksanjem')">🎵 Audio</div>
        <div class="sub-item" onclick="qCmd('Pomozi mi s foto editingom')">📷 Foto</div>
        <div class="sub-item" onclick="toolMediaPro()">⚙ Media Pro<span class="tb off" id="badge-media" style="margin-left:6px">—</span></div>
      </div>

      <div class="ni" onclick="toggleCat('cat-prog')">
        <span class="ico">💻</span><span data-i18n="cat_prog">Programiranje</span>
        <span class="ico" style="margin-left:auto;font-size:11px" id="arr-prog">▸</span>
      </div>
      <div class="sub-cat" id="cat-prog">
        <div class="sub-item" onclick="qCmd('Napiši Python skriptu za')">🐍 Python</div>
        <div class="sub-item" onclick="qCmd('Napiši JavaScript kod za')">🌐 JavaScript</div>
        <div class="sub-item" onclick="qCmd('Pomozi mi debugirati grešku')">🐛 Debug</div>
        <div class="sub-item" onclick="qCmd('TOOL:list_files')">📂 Fajlovi</div>
      </div>

      <div class="ni" onclick="toggleCat('cat-sci')">
        <span class="ico">🔬</span><span data-i18n="cat_sci">Znanost</span>
        <span class="ico" style="margin-left:auto;font-size:11px" id="arr-sci">▸</span>
      </div>
      <div class="sub-cat" id="cat-sci">
        <div class="sub-item" onclick="qCmd('Pretraži ArXiv za')">📄 ArXiv radovi</div>
        <div class="sub-item" onclick="qCmd('Objasni mi znanstveni koncept')">🧪 Objašnjenje</div>
        <div class="sub-item" onclick="qCmd('Pretraži Wikipedia za')">📖 Wikipedia</div>
        <div class="sub-item" onclick="qCmd('Pretraži knjige o')">📚 Open Library</div>
      </div>

      <div class="ni" onclick="toggleCat('cat-edu')">
        <span class="ico">🎓</span><span data-i18n="cat_edu">Edukacija</span>
        <span class="ico" style="margin-left:auto;font-size:11px" id="arr-edu">▸</span>
      </div>
      <div class="sub-cat" id="cat-edu">
        <div class="sub-item" onclick="qCmd('Objasni mi ukratko')">📝 Sažetak</div>
        <div class="sub-item" onclick="qCmd('Napravi kviz pitanja o')">❓ Kviz</div>
        <div class="sub-item" onclick="qCmd('Prevedi na engleski')">🌍 Prijevod</div>
        <div class="sub-item" onclick="qCmd('Napiši esej o')">✍ Esej</div>
      </div>

      <!-- Alati -->
      <div class="ns" data-i18n="tools_s">ALATI</div>
      <div class="ni" onclick="toolWebScout()">
        <span class="ico">🔍</span><span data-i18n="tool_scout">Web Scout</span>
        <span class="tb off" id="badge-scout">—</span>
      </div>
      <div class="ni" onclick="toolVault()">
        <span class="ico">🔐</span><span data-i18n="tool_vault">Vault</span>
        <span class="tb off" id="badge-vault">—</span>
      </div>

      <!-- Akcije -->
      <div class="ns" data-i18n="actions">AKCIJE</div>
      <div class="ni" onclick="qCmd('recall')"><span class="ico">🔍</span><span data-i18n="recall">Recall</span></div>
      <div class="ni" onclick="qCmd('clear')"><span class="ico">🗑</span><span data-i18n="clear">Reset chat</span></div>
      <div class="ni" onclick="qCmd('backup')"><span class="ico">☁️</span><span data-i18n="backup">Backup</span></div>
      <div class="ni" onclick="qCmd('git pull')"><span class="ico">⬇️</span><span data-i18n="git">Git pull</span></div>
    </nav>

    <!-- Postavke -->
    <div class="sb-set">
      <div class="ns" style="padding:0 0 5px" data-i18n="settings">POSTAVKE</div>
      <div class="sr">
        <label data-i18n="lang_lbl">JEZIK</label>
        <select id="lsel" onchange="chLang(this.value)">
          <option value="hr">Hrvatski</option>
          <option value="en">English</option>
          <option value="de">Deutsch</option>
          <option value="fr">Français</option>
          <option value="es">Español</option>
        </select>
      </div>
    </div>

    <!-- Moduli -->
    <div class="sb-mods">
      <div style="font-size:9px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px;color:var(--td)" data-i18n="modules">Moduli</div>
      <div class="md"><div class="dot off" id="mod-scout"></div><span>web_scout</span></div>
      <div class="md"><div class="dot off" id="mod-media"></div><span>media_pro</span></div>
      <div class="md"><div class="dot off" id="mod-lingua"></div><span>lingua_core</span></div>
      <div class="md"><div class="dot off" id="mod-vault"></div><span>vault</span></div>
      <div class="md"><div class="dot off" id="mod-brain"></div><span>vector_brain</span></div>
      <div class="md"><div class="dot off" id="mod-ctx"></div><span>context_helper</span></div>
    </div>

  </div><!-- /sb-inner -->
</aside>

<!-- ══ MAIN ══ -->
<div id="main">
  <header id="hdr">
    <button id="btn-sb" onclick="togSB()">☰</button>
    <div id="htitle">ATLAS OS v21.5</div>
    <span class="hb" id="mode-b">fast</span>
    <span class="hb" id="lang-b">hr</span>
    <span id="conn" class="con">⬡ …</span>
  </header>

  <div id="chat">
    <div class="msg atlas">
      <div class="bubble" id="wb"></div>
      <div class="mm">ATLAS · v21.5</div>
    </div>
  </div>

  <div id="typ">
    <div class="db"></div><div class="db"></div><div class="db"></div>
    <span id="thtxt" style="font-size:11px;color:var(--td)"></span>
  </div>

  <div id="ia">
    <div id="fp">
      <span>📎</span><span id="fpn">—</span>
      <button id="fpc" onclick="clrF()">✕</button>
    </div>
    <div class="ir">
      <textarea id="mi" rows="1" oninput="aExp(this)" onkeydown="hKey(event)"></textarea>
      <div class="ibt">
        <button class="ib" onclick="document.getElementById('ii').click()">🖼</button>
        <button class="ib" onclick="document.getElementById('fi').click()">📎</button>
        <button id="bsnd" onclick="sndMsg()">➤</button>
      </div>
    </div>
  </div>
</div>
</div>

<div id="toast"></div>
<input type="file" id="ii" accept="image/*" onchange="hImg(this)">
<input type="file" id="fi" accept=".txt,.py,.js,.csv,.json,.md,.pdf" onchange="hFile(this)">

<script>
// ══ i18n rječnik — svi natpisi na hrvatskom po defaultu ══
const D={
  hr:{
    sys:"SISTEM",nav:"NAVIGACIJA",nav_chat:"Chat",nav_mem:"Memorija",nav_files:"Fajlovi",
    cat_section:"KATEGORIJE",cat_media:"Multimedija",cat_prog:"Programiranje",
    cat_sci:"Znanost",cat_edu:"Edukacija",
    tools_s:"ALATI",tool_scout:"Web Scout",tool_vault:"Vault",
    actions:"AKCIJE",recall:"Recall",clear:"Reset chat",backup:"Backup",git:"Git pull",
    settings:"POSTAVKE",lang_lbl:"JEZIK",modules:"Moduli",
    connecting:"Spajam...",connected:"Spojeno",disconnected:"Odspojen",error:"Greška veze",
    ph:"Pitajte Atlas...",thinking:"ATLAS razmišlja...",
    copy:"Kopiraj",edit:"Uredi",copied:"Kopirano!",you:"Ti",
    bon:"aktivan",boff:"nedostupan",
    welcome:"Pozdrav! Ja sam <strong>ATLAS OS v21.5</strong>.<br>Ultra-Search: Wikipedia · DuckDuckGo · ArXiv · Open Library · Google · web_scout.<br>Mogu čitati URL-ove, PDF-ove, pisati i pokretati kod, obrađivati slike i upravljati fajlovima."
  },
  en:{
    sys:"SYSTEM",nav:"NAVIGATION",nav_chat:"Chat",nav_mem:"Memory",nav_files:"Files",
    cat_section:"CATEGORIES",cat_media:"Multimedia",cat_prog:"Programming",
    cat_sci:"Science",cat_edu:"Education",
    tools_s:"TOOLS",tool_scout:"Web Scout",tool_vault:"Vault",
    actions:"ACTIONS",recall:"Recall",clear:"Reset chat",backup:"Backup",git:"Git pull",
    settings:"SETTINGS",lang_lbl:"LANGUAGE",modules:"Modules",
    connecting:"Connecting...",connected:"Connected",disconnected:"Disconnected",error:"Connection error",
    ph:"Ask Atlas something...",thinking:"ATLAS is thinking...",
    copy:"Copy",edit:"Edit",copied:"Copied!",you:"You",
    bon:"active",boff:"unavailable",
    welcome:"Hello! I am <strong>ATLAS OS v21.5</strong>.<br>Ultra-Search: Wikipedia · DuckDuckGo · ArXiv · Open Library · Google · web_scout.<br>I can read URLs, PDFs, write and run code, process images and manage files."
  },
  de:{
    sys:"SYSTEM",nav:"NAVIGATION",nav_chat:"Chat",nav_mem:"Speicher",nav_files:"Dateien",
    cat_section:"KATEGORIEN",cat_media:"Multimedia",cat_prog:"Programmierung",
    cat_sci:"Wissenschaft",cat_edu:"Bildung",
    tools_s:"WERKZEUGE",tool_scout:"Web Scout",tool_vault:"Vault",
    actions:"AKTIONEN",recall:"Recall",clear:"Chat zurücksetzen",backup:"Backup",git:"Git pull",
    settings:"EINSTELLUNGEN",lang_lbl:"SPRACHE",modules:"Module",
    connecting:"Verbinde...",connected:"Verbunden",disconnected:"Getrennt",error:"Verbindungsfehler",
    ph:"Frag Atlas etwas...",thinking:"ATLAS denkt nach...",
    copy:"Kopieren",edit:"Bearbeiten",copied:"Kopiert!",you:"Du",
    bon:"aktiv",boff:"nicht verfügbar",
    welcome:"Hallo! Ich bin <strong>ATLAS OS v21.5</strong>.<br>Ultra-Search: Wikipedia · DuckDuckGo · ArXiv · Open Library · Google · web_scout."
  },
  fr:{
    sys:"SYSTÈME",nav:"NAVIGATION",nav_chat:"Chat",nav_mem:"Mémoire",nav_files:"Fichiers",
    cat_section:"CATÉGORIES",cat_media:"Multimédia",cat_prog:"Programmation",
    cat_sci:"Sciences",cat_edu:"Éducation",
    tools_s:"OUTILS",tool_scout:"Web Scout",tool_vault:"Vault",
    actions:"ACTIONS",recall:"Recall",clear:"Réinitialiser",backup:"Backup",git:"Git pull",
    settings:"PARAMÈTRES",lang_lbl:"LANGUE",modules:"Modules",
    connecting:"Connexion...",connected:"Connecté",disconnected:"Déconnecté",error:"Erreur",
    ph:"Demandez à Atlas...",thinking:"ATLAS réfléchit...",
    copy:"Copier",edit:"Modifier",copied:"Copié!",you:"Vous",
    bon:"actif",boff:"indisponible",
    welcome:"Bonjour! Je suis <strong>ATLAS OS v21.5</strong>.<br>Ultra-Search: Wikipedia · DuckDuckGo · ArXiv · Open Library · Google · web_scout."
  },
  es:{
    sys:"SISTEMA",nav:"NAVEGACIÓN",nav_chat:"Chat",nav_mem:"Memoria",nav_files:"Archivos",
    cat_section:"CATEGORÍAS",cat_media:"Multimedia",cat_prog:"Programación",
    cat_sci:"Ciencia",cat_edu:"Educación",
    tools_s:"HERRAMIENTAS",tool_scout:"Web Scout",tool_vault:"Vault",
    actions:"ACCIONES",recall:"Recall",clear:"Reiniciar",backup:"Backup",git:"Git pull",
    settings:"AJUSTES",lang_lbl:"IDIOMA",modules:"Módulos",
    connecting:"Conectando...",connected:"Conectado",disconnected:"Desconectado",error:"Error",
    ph:"Pregunta a Atlas...",thinking:"ATLAS está pensando...",
    copy:"Copiar",edit:"Editar",copied:"¡Copiado!",you:"Tú",
    bon:"activo",boff:"no disponible",
    welcome:"¡Hola! Soy <strong>ATLAS OS v21.5</strong>.<br>Ultra-Search: Wikipedia · DuckDuckGo · ArXiv · Open Library · Google · web_scout."
  }
};

let lang="hr";
const t=k=>(D[lang]||D.hr)[k]||k;

function applyI18n(){
  document.querySelectorAll("[data-i18n]").forEach(el=>el.textContent=t(el.getAttribute("data-i18n")));
  const mi=document.getElementById("mi"); if(mi) mi.placeholder=t("ph");
  const th=document.getElementById("thtxt"); if(th) th.textContent=t("thinking");
  const wb=document.getElementById("wb"); if(wb) wb.innerHTML=t("welcome");
  document.getElementById("lang-b").textContent=lang;
  document.documentElement.lang=lang;
  if(wsR) setConn("ok","⬡ "+t("connected"));
  // Update badge labels
  ["badge-media","badge-scout","badge-vault"].forEach(id=>{
    const b=document.getElementById(id);
    if(b && b._active!==undefined) b.textContent=b._active?t("bon"):t("boff");
  });
}

function chLang(l){
  if(!D[l]) return;
  lang=l; applyI18n(); showToast(t("connected")+" — "+l);
}

// ══ SIDEBAR ══
let sbO=false;
function togSB(){sbO?closeSB():openSB()}
function openSB(){
  sbO=true;
  document.getElementById("sb").classList.remove("col");
  if(window.innerWidth<=640) document.getElementById("ov").classList.add("show");
}
function closeSB(){
  sbO=false;
  document.getElementById("sb").classList.add("col");
  document.getElementById("ov").classList.remove("show");
}
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&sbO) closeSB()});

// Sub-category toggle
function toggleCat(id){
  const el=document.getElementById(id);
  const isOpen=el.classList.contains("open");
  // Close all
  document.querySelectorAll(".sub-cat").forEach(c=>c.classList.remove("open"));
  document.querySelectorAll("[id^='arr-']").forEach(a=>a.textContent="▸");
  if(!isOpen){
    el.classList.add("open");
    const key=id.replace("cat-","");
    const arr=document.getElementById("arr-"+key);
    if(arr) arr.textContent="▾";
  }
}

// ══ WEBSOCKET ══
let ws=null,wsR=false,pImg=null,pFile=null;
function initWS(){
  const pr=location.protocol==="https:"?"wss:":"ws:";
  ws=new WebSocket(`${pr}//${location.host}/ws`);
  ws.onopen=()=>{wsR=true;setConn("ok","⬡ "+t("connected"));fetchMet();fetchMods()};
  ws.onclose=()=>{wsR=false;setConn("err","⬡ "+t("disconnected"));setTimeout(initWS,3000)};
  ws.onerror=()=>setConn("err","⬡ "+t("error"));
  ws.onmessage=ev=>{
    try{
      const d=JSON.parse(ev.data);
      if(d.type==="typing"){showTyp(true);return}
      showTyp(false);
      if(d.type==="message"){
        addMsg("atlas",d.content,d.mode);
        if(d.lang&&D[d.lang]){lang=d.lang;document.getElementById("lsel").value=d.lang;applyI18n()}
        if(d.mode) document.getElementById("mode-b").textContent=d.mode;
      }
      if(d.type==="error") addMsg("atlas","⚠️ "+d.content);
    }catch(e){showTyp(false);addMsg("atlas",ev.data)}
  };
}

function setConn(s,l){const el=document.getElementById("conn");el.className=s;el.textContent=l}

// ══ TEXTAREA AUTO-EXPAND ══
function aExp(el){
  el.style.height="auto";
  const lh=parseFloat(getComputedStyle(el).lineHeight)||21;
  const mxH=lh*5+16;
  el.style.height=Math.min(el.scrollHeight,mxH)+"px";
  el.style.overflowY=el.scrollHeight>mxH?"auto":"hidden";
}

// ══ SEND ══
function sndMsg(){
  const inp=document.getElementById("mi"),msg=inp.value.trim();
  if(!wsR){showToast("⚠️ "+t("connecting"));return}
  if(!msg&&!pImg&&!pFile) return;
  // Sakrij TOOL: komande iz chata
  if(!msg.startsWith("TOOL:")) addMsg("user",msg||"");
  const pl={message:msg};
  if(pImg){pl.image_b64=pImg.b64;pl.image_mime=pImg.mime;if(!msg) addMsg("user","🖼 [slika]")}
  if(pFile){pl.file_name=pFile.name;pl.file_content=pFile.content;if(!msg) addMsg("user","📎 "+pFile.name)}
  ws.send(JSON.stringify(pl));
  inp.value="";inp.style.height="auto";inp.style.overflowY="hidden";
  pImg=pFile=null;clrF();showTyp(true);
}

function hKey(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sndMsg()}}

// ══ APPEND MESSAGE ══
function addMsg(role,content,mode){
  const chat=document.getElementById("chat");
  const wrap=document.createElement("div"); wrap.className=`msg ${role}`;
  const bub=document.createElement("div"); bub.className="bubble";
  bub.innerHTML=fmt(content);
  bub.querySelectorAll("pre").forEach(pre=>{
    const btn=document.createElement("button"); btn.className="cc"; btn.textContent=t("copy");
    btn.onclick=()=>navigator.clipboard.writeText(pre.innerText.replace(btn.innerText,"").trim())
      .then(()=>showToast(t("copied")));
    pre.style.position="relative"; pre.appendChild(btn);
  });
  const meta=document.createElement("div"); meta.className="mm";
  const now=new Date(),ts=now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0");
  meta.textContent=(role==="user"?t("you"):"ATLAS")+" · "+ts+(mode?" · "+mode:"");
  const acts=document.createElement("div"); acts.className="ma";
  const cp=document.createElement("button"); cp.className="ab"; cp.textContent=t("copy");
  cp.onclick=()=>navigator.clipboard.writeText(bub.innerText).then(()=>showToast(t("copied")));
  const ed=document.createElement("button"); ed.className="ab"; ed.textContent=t("edit");
  ed.onclick=()=>{const i=document.getElementById("mi");i.value=bub.innerText;aExp(i);i.focus()};
  acts.appendChild(cp);
  if(role==="user") acts.appendChild(ed);
  wrap.appendChild(bub); wrap.appendChild(acts); wrap.appendChild(meta);
  chat.appendChild(wrap); chat.scrollTop=chat.scrollHeight;
}

// ══ MARKDOWN LITE ══
function fmt(txt){
  if(!txt) return "";
  let s=txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  s=s.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>`<pre><code class="lang-${l||"text"}">${c.trim()}</code></pre>`);
  s=s.replace(/`([^`]+)`/g,"<code>$1</code>");
  s=s.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
  s=s.replace(/\*(.+?)\*/g,"<em>$1</em>");
  s=s.replace(/^### (.+)$/gm,"<h4 style='margin:.4em 0 .2em;font-size:13px;color:var(--ac)'>$1</h4>");
  s=s.replace(/^## (.+)$/gm, "<h3 style='margin:.5em 0 .2em;font-size:14px;color:var(--ac)'>$1</h3>");
  s=s.replace(/^# (.+)$/gm,  "<h2 style='margin:.6em 0 .2em;font-size:15px;color:var(--ac)'>$1</h2>");
  s=s.replace(/^[\-\*] (.+)$/gm,"<li>$1</li>");
  s=s.replace(/(<li>.*<\/li>)+/gs,m=>`<ul style='padding-left:16px;margin:4px 0'>${m}</ul>`);
  s=s.replace(/\[(.+?)\]\((https?:\/\/[^\)]+)\)/g,`<a href="$2" target="_blank" rel="noopener" style="color:var(--ac)">$1</a>`);
  // Označi izvore pretrage
  s=s.replace(/\[Wikipedia\]/g,'<span class="src-badge">Wikipedia</span>');
  s=s.replace(/\[DDG\]/g,'<span class="src-badge">DDG</span>');
  s=s.replace(/\[ArXiv\]/g,'<span class="src-badge">ArXiv</span>');
  s=s.replace(/\[OpenLibrary\]/g,'<span class="src-badge">OpenLibrary</span>');
  s=s.replace(/\n/g,"<br>");
  return s;
}

function showTyp(show){
  const el=document.getElementById("typ");
  const sp=document.getElementById("thtxt"); if(sp) sp.textContent=t("thinking");
  el.classList.toggle("show",show);
  if(show) document.getElementById("chat").scrollTop=9e9;
}

let _tt=null;
function showToast(msg,ms=2000){
  const el=document.getElementById("toast"); el.textContent=msg; el.classList.add("show");
  clearTimeout(_tt); _tt=setTimeout(()=>el.classList.remove("show"),ms);
}

function navC(el){document.querySelectorAll(".ni").forEach(i=>i.classList.remove("active"));el.classList.add("active")}

function qCmd(cmd){
  const inp=document.getElementById("mi"); inp.value=cmd; sndMsg(); closeSB();
}

function toolMediaPro(){qCmd("TOOL:media_pro:status")}
function toolWebScout(){
  const q=prompt(t("tool_scout")+":");
  if(q) qCmd(q); else closeSB();
}
function toolVault(){qCmd("TOOL:vault_status")}

// ══ FILE / IMAGE ══
function hImg(inp){
  const f=inp.files[0]; if(!f) return;
  if(f.size>10*1024*1024){showToast("⚠️ >10MB");return}
  const r=new FileReader();
  r.onload=e=>{pImg={b64:e.target.result.split(",")[1],mime:f.type};showFP("🖼 "+f.name)};
  r.readAsDataURL(f); inp.value="";
}
function hFile(inp){
  const f=inp.files[0]; if(!f) return;
  if(f.size>5*1024*1024){showToast("⚠️ >5MB");return}
  const r=new FileReader();
  r.onload=e=>{pFile={name:f.name,content:e.target.result};showFP("📎 "+f.name)};
  r.readAsText(f); inp.value="";
}
function showFP(n){document.getElementById("fpn").textContent=n;document.getElementById("fp").classList.add("show")}
function clrF(){pImg=pFile=null;document.getElementById("fp").classList.remove("show")}

// ══ METRICS ══
async function fetchMet(){
  try{
    const r=await fetch("/metrics"); if(!r.ok) return;
    const d=await r.json();
    document.getElementById("m-bat").textContent=d.cpu||"N/A";
    const ram=parseFloat(d.mem);
    document.getElementById("m-ram").textContent=isNaN(ram)?(d.mem||"N/A"):ram+"%";
    const bar=document.getElementById("m-bar"); if(!isNaN(ram)) bar.style.width=Math.min(ram,100)+"%";
  }catch(e){}
  setTimeout(fetchMet,15000);
}

// ══ MODULES ══
async function fetchMods(){
  try{
    const r=await fetch("/modules"); if(!r.ok) return;
    const d=await r.json();
    const MAP={
      scout:["mod-scout","badge-scout"],
      media:["mod-media","badge-media"],
      lingua:["mod-lingua",null],
      vault:["mod-vault","badge-vault"],
      brain:["mod-brain",null],
      ctx:["mod-ctx",null]
    };
    Object.entries(MAP).forEach(([k,[dId,bId]])=>{
      const on=!!d[k];
      const dot=document.getElementById(dId);
      if(dot){dot.classList.toggle("on",on);dot.classList.toggle("off",!on)}
      if(bId){
        const b=document.getElementById(bId);
        if(b){b._active=on;b.textContent=on?t("bon"):t("boff");b.classList.toggle("off",!on)}
      }
    });
  }catch(e){}
}

// ══ INIT ══
document.addEventListener("DOMContentLoaded",()=>{
  applyI18n();
  setConn("con","⬡ "+t("connecting"));
  initWS();
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(HTML_UI)


# ══════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")