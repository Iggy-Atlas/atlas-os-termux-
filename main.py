"""
ATLAS OS v21.6
Termux Edition - Groq + Gemini - Ultra-Search + Global Radar + bs4 DDG Scraping
"""
import os, uvicorn, httpx, json, asyncio, subprocess, re, base64, io, hashlib, time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import aiosqlite

ATLAS_VERSION = "v21.6"
load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID", "")

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
GOOGLE_TIMEOUT     = 5
_approved_tools    = set()

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _psutil = None
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

try:
    from bs4 import BeautifulSoup as BS4
    _BS4_OK = True
except ImportError:
    _BS4_OK = False
    BS4 = None

try:
    import feedparser as _fp
    _FP_OK = True
except ImportError:
    _fp = None
    _FP_OK = False

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
    def validate_code(c):    return {"safe": True, "reason": ""}
    def validate_url(u):     return {"safe": True, "reason": ""}
    def safe_error(m, c=""): return f"[ERROR] {m}"

try:
    from web_fix import inject_web_results, build_search_system_prompt
except ImportError:
    def inject_web_results(m, w, l=""):   return m
    def build_search_system_prompt(l=""): return ""

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

# === GLOBAL RADAR RSS ===
RADAR_FEEDS = {
    "Oxford":     "https://www.ox.ac.uk/news-and-events/find-an-expert/news-listing.rss",
    "MIT":        "https://news.mit.edu/rss/research",
    "Harvard":    "https://news.harvard.edu/gazette/feed/",
    "Stanford":   "https://news.stanford.edu/feed/",
    "HackerNews": "https://hnrss.org/frontpage",
    "TechCrunch": "https://techcrunch.com/feed/",
    "TheVerge":   "https://www.theverge.com/rss/index.xml",
}

async def fetch_radar_feed(name, url, limit=4):
    if _FP_OK:
        try:
            loop = asyncio.get_event_loop()
            parsed = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _fp.parse(url)), timeout=10
            )
            results = []
            for e in parsed.get("entries", [])[:limit]:
                results.append({
                    "source":  name,
                    "title":   e.get("title", "")[:120],
                    "link":    e.get("link", ""),
                    "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:200],
                })
            return results
        except Exception as ex:
            print(f"[RADAR feedparser] {name}: {ex}")
    try:
        headers = {"User-Agent": "Atlas/21.6 (RSS reader)"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers, follow_redirects=True)
            if r.status_code != 200:
                return []
        items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
        if not items:
            items = re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL)
        results = []
        for item in items[:limit]:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
            link_m  = (re.search(r"<link>(.*?)</link>", item, re.DOTALL) or
                       re.search(r'href="([^"]+)"', item))
            desc_m  = (re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", item, re.DOTALL) or
                       re.search(r"<summary[^>]*>(.*?)</summary>", item, re.DOTALL))
            title   = title_m.group(1).strip() if title_m else ""
            link    = link_m.group(1).strip()  if link_m  else ""
            summary = re.sub(r"<[^>]+>", "", desc_m.group(1))[:200].strip() if desc_m else ""
            if title:
                results.append({"source": name, "title": title, "link": link, "summary": summary})
        return results
    except Exception as ex:
        print(f"[RADAR httpx] {name}: {ex}")
        return []

async def global_radar(sources=None, limit_per=3):
    if sources is None:
        sources = list(RADAR_FEEDS.keys())
    feeds = {k: v for k, v in RADAR_FEEDS.items() if k in sources}
    tasks = [fetch_radar_feed(name, url, limit_per) for name, url in feeds.items()]
    all_res = await asyncio.gather(*tasks, return_exceptions=True)
    items = []
    for res in all_res:
        if isinstance(res, list):
            items.extend(res)
    if not items:
        return "[RADAR] Nema dostupnih vijesti. Provjeri konekciju."
    lines = []
    for item in items:
        src   = item.get("source", "")
        title = item.get("title", "")
        link  = item.get("link", "")
        summ  = item.get("summary", "")
        lines.append(f"* [{src}] **{title}**{(' -- ' + summ) if summ else ''} [{link}]")
    return "\n".join(lines)

# === ULTRA-SEARCH ===
_search_cache = {}
_search_ts    = {}

def _scache_get(q):
    k = hashlib.md5(q.encode()).hexdigest()
    if k in _search_cache and time.time() - _search_ts.get(k, 0) < 180:
        return _search_cache[k]
    return None

def _scache_set(q, r):
    k = hashlib.md5(q.encode()).hexdigest()
    _search_cache[k] = r
    _search_ts[k]    = time.time()

async def _google_search(query, news=False):
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
                    f"* {it.get('title','')}: {it.get('snippet','')[:180]} [{it.get('link','')}]"
                    for it in items[:5]
                ]
                print(f"[GOOGLE] OK -- {len(items)} rezultata")
                return "\n".join(lines)
            print(f"[GOOGLE] {r.status_code} -- fallback")
            return ""
    except Exception as e:
        print(f"[GOOGLE] {e} -- fallback")
        return ""

async def _ddg_bs4_scrape(query):
    if not _BS4_OK:
        return await _ddg_instant(query)
    try:
        url     = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            r = await client.post(url, data={"q": query, "kl": "us-en"}, headers=headers)
            if r.status_code != 200:
                return await _ddg_instant(query)
        soup    = BS4(r.text, "html.parser")
        results_els = soup.find_all("div", class_="result__body")
        if not results_els:
            results_els = soup.find_all("div", class_=re.compile("result"))
        lines = []
        for res in results_els[:5]:
            title_el = res.find("a", class_=re.compile(r"result__a|result__title"))
            snip_el  = (res.find("a", class_=re.compile(r"result__snippet")) or
                        res.find("div", class_=re.compile(r"snippet")))
            if not title_el:
                continue
            title   = title_el.get_text(strip=True)[:120]
            href    = title_el.get("href", "")
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                import urllib.parse
                href = urllib.parse.unquote(m.group(1))
            snippet = snip_el.get_text(strip=True)[:200] if snip_el else ""
            if title:
                lines.append(f"* [DDG] {title}: {snippet} [{href}]")
        if lines:
            print(f"[DDG bs4] OK -- {len(lines)} rezultata")
            return "\n".join(lines)
        return await _ddg_instant(query)
    except Exception as e:
        print(f"[DDG bs4] {e}")
        return await _ddg_instant(query)

async def _ddg_instant(query):
    try:
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.duckduckgo.com/", params=params,
                headers={"User-Agent": "Atlas/21.6"},
            )
            if r.status_code != 200:
                return ""
        data    = r.json()
        results = []
        abstract = data.get("AbstractText", "")
        ab_url   = data.get("AbstractURL", "")
        if abstract:
            results.append(f"* [DDG] {abstract[:300]} [{ab_url}]")
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"* [DDG] {topic.get('Text','')[:200]} [{topic.get('FirstURL','')}]")
        if results:
            print(f"[DDG instant] OK -- {len(results)} rezultata")
        return "\n".join(results)
    except Exception as e:
        print(f"[DDG instant] {e}")
        return ""

async def _wikipedia_search(query):
    try:
        params = {"action":"query","list":"search","srsearch":query,"srlimit":4,"format":"json","utf8":1}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://en.wikipedia.org/w/api.php", params=params,
                headers={"User-Agent": "Atlas/21.6"},
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
            link    = f"https://en.wikipedia.org/wiki/{title.replace(' ','_')}"
            lines.append(f"* [Wikipedia] {title}: {snippet[:200]} [{link}]")
        print(f"[WIKIPEDIA] OK -- {len(lines)} rezultata")
        return "\n".join(lines)
    except Exception as e:
        print(f"[WIKIPEDIA] {e}")
        return ""

async def _arxiv_search(query):
    try:
        params = {"search_query": f"all:{query}", "start": 0, "max_results": 3}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://export.arxiv.org/api/query", params=params,
                headers={"User-Agent": "Atlas/21.6"},
            )
            if r.status_code != 200:
                return ""
        entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL)
        if not entries:
            return ""
        lines = []
        for entry in entries[:3]:
            title_m   = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            link_m    = re.search(r'href="(https://arxiv\.org/abs/[^"]+)"', entry)
            t_str = title_m.group(1).strip().replace("\n", " ")         if title_m   else ""
            s_str = summary_m.group(1).strip().replace("\n", " ")[:200] if summary_m else ""
            l_str = link_m.group(1) if link_m else ""
            if t_str:
                lines.append(f"* [ArXiv] {t_str}: {s_str} [{l_str}]")
        if lines:
            print(f"[ARXIV] OK -- {len(lines)} radova")
        return "\n".join(lines)
    except Exception as e:
        print(f"[ARXIV] {e}")
        return ""

async def _openlibrary_search(query):
    try:
        params = {"q": query, "limit": 3, "fields": "title,author_name,first_publish_year,key"}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://openlibrary.org/search.json", params=params,
                headers={"User-Agent": "Atlas/21.6"},
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
            lines.append(f"* [OpenLibrary] {title} -- {authors} ({year}) [{url}]")
        if lines:
            print(f"[OPENLIBRARY] OK -- {len(lines)} knjiga")
        return "\n".join(lines)
    except Exception as e:
        print(f"[OPENLIBRARY] {e}")
        return ""

async def _scout_direct(query):
    if not _scout:
        return ""
    try:
        loop   = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _scout.get_live_info(query)),
            timeout=15
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

async def web_search(query, news=False):
    query = re.sub(r"[<>&\"']", "", query)[:200].strip()
    if not query:
        return ""
    ck     = ("news:" if news else "") + query
    cached = _scache_get(ck)
    if cached:
        return cached
    google_result = await _google_search(query, news)
    if google_result:
        _scache_set(ck, google_result)
        return google_result
    print("[ULTRA-SEARCH] Google nedostupan -- paralelna pretraga")
    results = await asyncio.gather(
        _ddg_bs4_scrape(query),
        _wikipedia_search(query),
        _arxiv_search(query),
        _openlibrary_search(query),
        _scout_direct(query),
        return_exceptions=True
    )
    parts = [r for r in results if isinstance(r, str) and r.strip()]
    if parts:
        combined = "\n".join(parts)[:3000]
        _scache_set(ck, combined)
        print(f"[ULTRA-SEARCH] OK -- {len(parts)} izvora")
        return combined
    print("[ULTRA-SEARCH] Nema rezultata")
    return ""

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
def blocked(tool):          return f"[BLOCKED] Potrebna dozvola za: {tool}. Posalji 'approve:{tool}'."

def safe_path(path):
    try:
        full = (PROJECT_DIR / path.lstrip("/")).resolve()
        if not str(full).startswith(str(PROJECT_DIR.resolve())):
            if _vault_check(str(full)).get("status") != "ALLOWED":
                return None
        return full
    except Exception:
        return None

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
                        if query.lower() in d.get("user","").lower()
                        or query.lower() in d.get("atlas","").lower()]
            data = filtered or data
        lines = [
            f"[{d.get('timestamp','')[:16]}]\nTi: {d.get('user','')}\nAtlas: {d.get('atlas','')}\n"
            for d in reversed(data[-5:])
        ]
        return "Sjecam se:\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Greska: {e}"

def get_metrics():
    bat = "N/A"
    try:
        r = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            b    = json.loads(r.stdout)
            icon = "E" if b.get("status") != "DISCHARGING" else "B"
            bat  = f"{icon}{b.get('percentage', 0)}%"
    except Exception:
        pass
    return {"cpu": bat, "mem": _get_mem_percent()}

def get_modules_status():
    return {
        "scout":      _scout          is not None,
        "media":      _media          is not None,
        "lingua":     _lingua         is not None,
        "vault":      _security_vault is not None,
        "brain":      _memory_brain   is not None,
        "ctx":        _context        is not None,
        "bs4":        _BS4_OK,
        "feedparser": _FP_OK,
    }

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

async def get_history(limit=5):
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
            "Extract user info as JSON only. "
            "Schema: {\"name\":\"\",\"preferences\":[],\"projects\":[]} "
            "Message: " + msg[:300]
        )
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 150, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            if r.status_code != 200:
                return
            raw = re.sub(r"```json?", "",
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
        "hr": sum(1 for w in ["sto","kako","zasто","gdje","kada","imam","treba","mogu","ovo","nije","da","ali","jer","sam","koji"] if w in t.split()),
        "en": sum(1 for w in ["what","how","why","where","when","have","need","can","this","that","the","and","for","is","are"] if w in t.split()),
        "de": sum(1 for w in ["was","wie","warum","wo","ich","habe","kann","das","und","ist"] if w in t.split()),
        "fr": sum(1 for w in ["que","comment","pourquoi","je","avoir","peut","est","les","des"] if w in t.split()),
        "es": sum(1 for w in ["que","como","por","yo","tengo","puede","los","una","para"] if w in t.split()),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "hr"

def detect_mode(msg):
    m = msg.lower()
    if re.search(r"https?://", m):                                                  return "url"
    if any(k in m for k in ["bug","error","greska","kod","debug","fix","python","script","funkcij","code"]): return "code"
    if any(k in m for k in ["zasто","objasni","analiziraj","usporedi","razlika","kako radi","sto je","analyze","explain","compare"]): return "analysis"
    if any(k in m for k in ["ideja","napravi","smisli","kreativan","prijedlog","osmisli","create","design","imagine"]): return "creative"
    if any(k in m for k in ["vijesti","danas","pretrazi","tko je","ko je","cijena","trenutno","news","search","today","arxiv","wikipedia","radar"]): return "search"
    return "fast"

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
    if m.startswith("TOOL:file_read:"):  return tool_file_read(m.split(":", 2)[-1])
    if m.startswith("TOOL:list_files"):  return tool_list_files(m.split(":", 2)[-1] if m.count(":") >= 2 else ".")
    if m.startswith("TOOL:run_python:"): return tool_run_python(m.split(":", 2)[-1])
    if m.startswith("TOOL:run_shell:"):  return tool_run_shell(m.split(":", 2)[-1])
    lm = m.lower()
    if lm.startswith("pokazi fajlove") or lm.startswith("list files"): return tool_list_files(".")
    match = re.match(r"^(?:procitaj|otvori) fajl (.+)", lm)
    if match: return tool_file_read(match.group(1).strip())
    match = re.match(r"^pokreni: (.+)", m)
    if match: return tool_run_shell(match.group(1).strip())
    return None

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
    except httpx.ConnectError:     return "[Greska veze]", "error"
    except Exception as e:         return f"[Greska: {str(e)[:120]}]", "error"

def _parse_pdf(content):
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        text   = ""
        for i, page in enumerate(reader.pages[:12]):
            text += f"\n--- Str. {i+1} ---\n{page.extract_text() or ''}"
        return f"[PDF -- {len(reader.pages)} stranica]\n{text[:5000]}"
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
        return "[PDF ucitan. Instaliraj: pip install pypdf]"
    except Exception as e:
        return f"[PDF greska: {str(e)[:100]}]"

def _parse_file(name, content):
    ext = name.lower().split(".")[-1] if "." in name else ""
    if ext == "pdf":
        try:
            b64 = content.split(",")[1] if "," in content else content
            return _parse_pdf(base64.b64decode(b64))
        except Exception as e:
            return f"[PDF greska: {e}]"
    if ext == "csv":
        return "[CSV]\n" + "\n".join(content.split("\n")[:50])
    if ext == "json":
        try:
            return f"[JSON]\n{json.dumps(json.loads(content), indent=2, ensure_ascii=False)[:3000]}"
        except Exception:
            pass
    return f"[Fajl: {name}]\n{content[:3000]}"

def run_backup(filepath=""):
    if filepath:
        if not check_permission("cloud"): return blocked("cloud")
        full = safe_path(filepath)
        if not full or not full.exists(): return f"Fajl nije pronaden: {filepath}"
        try:
            r = subprocess.run(
                ["rclone", "copy", str(full), "remote:AtlasBackup/"],
                capture_output=True, text=True, timeout=60
            )
            return f"Fajl prenesen: {full.name}" if r.returncode == 0 else f"rclone greska: {r.stderr[:200]}"
        except FileNotFoundError:         return "rclone nije instaliran."
        except subprocess.TimeoutExpired: return "Backup timeout."
        except Exception as e:            return f"Backup greska: {str(e)[:100]}"
    try:
        r = subprocess.run(
            ["python", "cloud_backup.py"],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_DIR)
        )
        return "Backup zavrsen." if r.returncode == 0 else f"Backup greska: {r.stderr[:200]}"
    except subprocess.TimeoutExpired: return "Backup timeout."
    except Exception as e:            return f"Backup greska: {str(e)[:100]}"

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
            f"GitHub update uspijesan.\n{r.stdout[:300]}"
            if r.returncode == 0
            else f"Git greska:\n{r.stderr[:300]}"
        )
    except Exception as e:
        return f"Git greska: {e}"

LANG_RULES = {
    "hr": "Jezik: standardni hrvatski knjizevni. Gramaticki ispravno. Bez ijekavice.",
    "en": "Language: fluent, natural English.",
    "de": "Sprache: fliessend, natuerliches Deutsch.",
    "fr": "Langue: francais courant et naturel.",
    "es": "Idioma: espanol fluido y natural.",
}
MODE_INSTRUCTIONS = {
    "code":     "Samo kod + kratko objasnjenje.",
    "analysis": "Korak po korak. Jasan zakljucak.",
    "creative": "Originalno. Izbjegavaj kliseje.",
    "search":   "Koristi ISKLJUCIVO prilozene web podatke. Ako nema -- reci da nema.",
    "url":      "Analiziraj ucitani sadrzaj. Kljucne tocke.",
    "fast":     "Direktno i kratko.",
    "video":    "Strucnjak za video produkciju.",
    "audio":    "Strucnjak za audio i glazbu.",
    "photo":    "Strucnjak za fotografiju.",
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

    media_ctx = f" MULTIMEDIJSKI MOD: {media_mode.upper()}." if media_mode != "text" else ""
    task_ctx  = f"\nPRETHODNI ZADATAK: {task_context}" if task_context else ""
    rag_addon = f"\n[RAG KONTEKST]\n{rag_context[:1200]}" if rag_context else ""
    tone_hint = f"\nTON: {lingua_hints.get('tone','')}" if lingua_hints and lingua_hints.get("tone") else ""

    dt        = get_current_datetime_str()
    date_line = (
        f"\nDANAS JE: {dt}. Znanje se azurira putem Ultra-Search sustava "
        "(Google, DDG/bs4, Wikipedia, ArXiv, OpenLibrary, Global Radar RSS). "
        "Ako nema rezultata -- priznas to."
    )
    truth_mode = "" if has_real_data else (
        "\nANTI-HALLUCINATION: Priznas da nemas svjeze informacije ako nema [WEB REZULTATI]."
    )
    mods = [m for m, v in [
        ("web_scout", _scout), ("media_pro", _media), ("lingua_core", _lingua),
        ("context_helper", _context), ("vector_brain", _memory_brain), ("vault", _security_vault),
        ("bs4", _BS4_OK), ("feedparser", _FP_OK),
    ] if v] + [("google_search" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "ultra_search_only")]

    return (
        f"Ti si ATLAS -- napredni AI operativni sustav. {ATLAS_VERSION}{media_ctx}\n"
        f"MOD: {mode.upper()} -- {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['fast'])}\n"
        f"{LANG_RULES.get(lang, LANG_RULES['hr'])}\n"
        "KARAKTER: Direktan. Iskren. Bez laskanja. Bez 'Naravno!' i slicnih fraza.\n"
        "SPOSOBNOSTI: URL/PDF citanje. Ultra-Search. Global Radar RSS. Cloud backup. Multimedija.\n"
        + (f"PROFIL: {user_ctx}\n" if user_ctx else "")
        + task_ctx + date_line + truth_mode + rag_addon + tone_hint
        + f"\nAKTIVNI MODULI: {', '.join(str(m) for m in mods)}\n"
        + "Kod u blokovima. Tablice u markdown formatu."
    )

_response_cache = {}

def _ck(messages, temp):
    return hashlib.md5((json.dumps(messages, sort_keys=True) + str(temp)).encode()).hexdigest()

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
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": model, "messages": messages,
                          "temperature": temp, "max_tokens": 1000},
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
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                                 "Content-Type": "application/json"},
                        json={"model": model, "messages": messages,
                              "temperature": temp, "max_tokens": 700},
                    )
                    if r2.status_code == 200:
                        _groq_model = model
                        result = r2.json()["choices"][0]["message"]["content"]
                        _cache_set(ck, result)
                        return result
                if r.status_code == 429:
                    print(f"[GROQ] {model} rate limit")
                    continue
                print(f"[GROQ] {model} -- {r.status_code}")
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
                print(f"[GEMINI] {model} -- {r.status_code}")
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
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": model, "max_tokens": 1000,
                          "messages": [{"role": "user", "content": [
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
                print(f"[VISION] {model} -- {r.status_code}")
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
    return "[ATLAS] Oba AI servisa su nedostupna. Provjeri API kljuceve."

def detect_media_mode(msg, has_image=False):
    if has_image: return "photo"
    m = msg.lower()
    if any(k in m for k in ["video","film","montaza","editing","reels","shorts"]): return "video"
    if any(k in m for k in ["audio","glazb","muzik","mixing","mastering","sound"]): return "audio"
    if any(k in m for k in ["foto","slika","kamera","lightroom","photoshop"]):     return "photo"
    return "text"

async def agentic_pipeline(user_msg, history, profile, lang, mode, media_mode,
                            web_data="", rag_ctx="", lingua_h=None):
    last_task = await get_last_task()
    task_ctx  = (
        f"{last_task.get('goal','')} -> {last_task.get('result','')[:150]}" if last_task else ""
    )
    sys_p    = build_system(profile, mode, lang, media_mode,
                             task_context=task_ctx, has_real_data=bool(web_data),
                             rag_context=rag_ctx, lingua_hints=lingua_h)
    messages = [{"role": "system", "content": sys_p}] + history[-6:]
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
        messages.append({"role": "user", "content": "Nastavi s iducim korakom. Budi koncizan."})
    return "\n\n".join(acc)

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
    if lm in ("recall", "memorija", "sjeti se"):
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

    # Global Radar trigger
    radar_triggers = [
        "globalni radar", "global radar", "radar vijesti", "science radar",
        "mit vijesti", "oxford vijesti", "hackernews", "hacker news",
        "techcrunch", "verge vijesti", "harvard vijesti", "stanford vijesti",
    ]
    if any(k in lm for k in radar_triggers):
        src_map = {
            "oxford": "Oxford", "mit": "MIT", "harvard": "Harvard",
            "stanford": "Stanford", "hackernews": "HackerNews",
            "hacker news": "HackerNews", "techcrunch": "TechCrunch", "verge": "TheVerge",
        }
        selected = [v for k, v in src_map.items() if k in lm]
        radar_data = await global_radar(sources=selected or None)
        synth_prompt = (
            f"Korisnik trazi pregled najvaznijih vijesti iz globalnih izvora.\n\n"
            f"Naslovi:\n{radar_data[:2000]}\n\n"
            "Napravi kratku AI sintezu od 3-5 recenica. Izdvoji 2-3 najzanimljivija naslova."
        )
        lang_det = detect_language(user_msg)
        synthesis = (
            await call_groq(
                [{"role": "system", "content": build_system({}, "search", lang_det, "text")},
                 {"role": "user", "content": synth_prompt}], 0.5
            ) or
            await call_gemini(
                [{"role": "system", "content": "Napravi kratku sintezu vijesti."},
                 {"role": "user", "content": synth_prompt}]
            ) or ""
        )
        result = f"GLOBALNI RADAR\n\n{radar_data}\n\n---\nAI Sinteza:\n{synthesis}"
        await save_msg("user", user_msg)
        await save_msg("assistant", result[:600])
        auto_save(user_msg, result[:600])
        save_context_json(user_msg, result[:600], "search")
        return result

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

    full_msg = f"{extra_ctx}\n\nKORISNICKI UPIT: {user_msg}" if extra_ctx else user_msg

    if has_image:
        vp = f"Analiziraj ovu sliku. Kontekst: {user_msg}\nJezik: {lang}"
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

@app.on_event("startup")
async def startup():
    await init_db()
    print(f"[ATLAS] {ATLAS_VERSION} pokrenut")
    print(f"[ATLAS] bs4: {'OK' if _BS4_OK else 'NEDOSTAJE -- pip install beautifulsoup4 --break-system-packages'}")
    print(f"[ATLAS] feedparser: {'OK' if _FP_OK else 'NEDOSTAJE -- pip install feedparser --break-system-packages'}")

@app.get("/metrics")
async def metrics_ep():
    return JSONResponse(get_metrics())

@app.get("/modules")
async def modules_ep():
    return JSONResponse(get_modules_status())

@app.get("/history")
async def history_ep():
    return JSONResponse(await get_history(20))

@app.get("/radar")
async def radar_ep():
    data = await global_radar()
    return JSONResponse({"radar": data, "sources": list(RADAR_FEEDS.keys())})

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

            history = await get_history(5)
            await ws.send_text(json.dumps({"type": "typing", "content": "..."}))

            try:
                response = await process_message(
                    user_msg, history,
                    image_b64=image_b64, image_mime=image_mime,
                    file_name=file_name, file_content=file_content,
                )
            except Exception as e:
                print(f"[WS] {e}")
                response = f"[ATLAS] Greska: {str(e)[:200]}"

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



HTML_UI = r"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ATLAS OS v21.6</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0c10;--sf:#111318;--sf2:#181c24;--bd:#1e2430;
  --ac:#00c8ff;--ac2:#7b61ff;--ok:#00e676;--wn:#ffd740;--dn:#ff5252;
  --tx:#e8eaf0;--td:#6b7280;--tm:#9ca3af;
  --mono:'JetBrains Mono','Fira Code',monospace;
  --ui:'Segoe UI',system-ui,sans-serif;
  --sw:252px;--hh:48px;
}
html,body{height:100%;background:var(--bg);color:var(--tx);font-family:var(--ui);font-size:14px;overflow:hidden}
#app{display:flex;height:100vh;width:100vw;overflow:hidden}
#ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:40;backdrop-filter:blur(3px)}
#ov.show{display:block}
#sb{
  width:var(--sw);min-width:var(--sw);
  background:var(--sf);border-right:1px solid var(--bd);
  display:flex;flex-direction:column;
  overflow:hidden;z-index:50;flex-shrink:0;
  transition:transform .28s cubic-bezier(.4,0,.2,1);
}
#sb.col{transform:translateX(calc(-1 * var(--sw)))}
@media(max-width:640px){
  #sb{position:fixed;top:0;left:0;height:100%;
      transform:translateX(calc(-1 * var(--sw)))}
  #sb:not(.col){transform:translateX(0)}
}
#sbi{display:flex;flex-direction:column;height:100%;
  overflow-y:auto;overflow-x:hidden;
  scrollbar-width:thin;scrollbar-color:var(--bd) transparent}
#sbi::-webkit-scrollbar{width:3px}
#sbi::-webkit-scrollbar-thumb{background:var(--bd);border-radius:2px}
.sb-hd{
  padding:12px 14px;border-bottom:1px solid var(--bd);
  display:flex;align-items:center;justify-content:space-between;
  flex-shrink:0;min-height:56px;
}
.sb-logo{display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden}
.an{font-size:15px;font-weight:700;letter-spacing:.04em;color:var(--ac);white-space:nowrap}
.av{font-size:10px;color:var(--td);white-space:nowrap}
#btn-x{background:none;border:none;color:var(--td);font-size:17px;cursor:pointer;
  padding:4px 6px;border-radius:6px;transition:color .15s;line-height:1;flex-shrink:0}
#btn-x:hover{color:var(--dn)}
.sb-met{padding:10px 14px;border-bottom:1px solid var(--bd);flex-shrink:0}
.mr{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}
.ml{font-size:9px;color:var(--td);letter-spacing:.05em;text-transform:uppercase}
.mv{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--ac)}
.bw{height:3px;background:var(--bd);border-radius:2px;overflow:hidden;margin-top:2px}
.bf{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .4s}
.sb-nav{flex:1;padding:4px 0 8px;overflow-y:auto;overflow-x:hidden}
.ns{padding:8px 14px 3px;font-size:9px;letter-spacing:.08em;text-transform:uppercase;
    color:var(--td);white-space:nowrap}
.ni{
  display:flex;align-items:center;gap:8px;padding:7px 14px;
  cursor:pointer;font-size:12.5px;color:var(--tm);
  border-left:2px solid transparent;
  transition:background .13s,color .13s,border-color .13s;
  white-space:nowrap;overflow:hidden;min-height:36px;user-select:none;
}
.ni:hover{background:rgba(255,255,255,.04);color:var(--tx)}
.ni.act{background:rgba(0,200,255,.08);color:var(--ac);border-left-color:var(--ac)}
.ni .ico{font-size:14px;flex-shrink:0}
.ni-arr{margin-left:auto;font-size:10px;color:var(--td);flex-shrink:0;transition:transform .22s;display:inline-block}
.ni-arr.open{transform:rotate(90deg)}
.ni-badge{
  margin-left:auto;font-size:9px;padding:1px 5px;border-radius:8px;
  background:rgba(0,200,255,.1);color:var(--ac);
  border:1px solid rgba(0,200,255,.2);white-space:nowrap;flex-shrink:0;
}
.ni-badge.off{background:rgba(255,255,255,.04);color:var(--td);border-color:var(--bd)}
.sub{overflow:hidden;max-height:0;transition:max-height .26s ease}
.sub.open{max-height:600px}
.si{
  display:flex;align-items:center;gap:7px;
  padding:6px 14px 6px 30px;cursor:pointer;font-size:12px;
  color:var(--td);border-left:2px solid transparent;
  transition:color .13s,background .13s;white-space:nowrap;overflow:hidden;min-height:32px;
}
.si:hover{color:var(--ac);background:rgba(0,200,255,.05);border-left-color:rgba(0,200,255,.3)}
.si .ico{font-size:13px;flex-shrink:0}
.si.head{color:var(--ac);font-weight:600;padding-left:20px}
.si-nested{padding-left:42px}
.sb-set{padding:10px 14px;border-top:1px solid var(--bd);flex-shrink:0}
.sr{display:flex;align-items:center;justify-content:space-between;padding:3px 0}
.sr label{font-size:9px;color:var(--td);text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.sr select{background:var(--sf2);border:1px solid var(--bd);color:var(--tx);
  font-size:11px;padding:2px 6px;border-radius:4px;outline:none;cursor:pointer;max-width:120px}
.sr select:focus{border-color:var(--ac)}
.sb-mods{padding:8px 14px 10px;border-top:1px solid var(--bd);flex-shrink:0}
.mod-title{font-size:9px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:5px;color:var(--td)}
.md{display:flex;align-items:center;gap:6px;padding:2px 0;font-size:11px;white-space:nowrap}
.dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.dot.on{background:var(--ok)}
.dot.off{background:var(--bd)}
#main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
#hdr{
  height:var(--hh);min-height:var(--hh);
  background:var(--sf);border-bottom:1px solid var(--bd);
  display:flex;align-items:center;padding:0 12px;gap:8px;flex-shrink:0;
}
#btn-sb{background:none;border:none;color:var(--tm);font-size:18px;cursor:pointer;
  padding:4px 6px;border-radius:6px;flex-shrink:0;transition:color .15s}
#btn-sb:hover{color:var(--ac)}
#htitle{font-size:13px;font-weight:600;color:var(--tx);flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hb{font-size:10px;padding:2px 7px;border-radius:20px;
  background:rgba(0,200,255,.1);color:var(--ac);
  border:1px solid rgba(0,200,255,.2);white-space:nowrap;flex-shrink:0}
#conn{font-size:10px;padding:2px 7px;border-radius:20px;white-space:nowrap;flex-shrink:0}
#conn.ok{background:rgba(0,230,118,.1);color:var(--ok);border:1px solid rgba(0,230,118,.2)}
#conn.err{background:rgba(255,82,82,.1);color:var(--dn);border:1px solid rgba(255,82,82,.2)}
#conn.con{background:rgba(255,215,64,.1);color:var(--wn);border:1px solid rgba(255,215,64,.2)}
#chat{flex:1;overflow-y:auto;padding:14px 12px 6px;
  display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-thumb{background:var(--bd);border-radius:2px}
.msg{display:flex;flex-direction:column;max-width:90%;animation:fi .2s ease}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.msg.user{align-self:flex-end}
.msg.atlas{align-self:flex-start}
.bubble{padding:9px 13px;border-radius:10px;line-height:1.55;font-size:13.5px;word-break:break-word}
.msg.user .bubble{
  background:linear-gradient(135deg,rgba(0,200,255,.15),rgba(123,97,255,.15));
  border:1px solid rgba(0,200,255,.22);border-bottom-right-radius:2px;
}
.msg.atlas .bubble{background:var(--sf2);border:1px solid var(--bd);border-bottom-left-radius:2px}
.ma{display:flex;gap:4px;margin-top:4px;opacity:0;transition:opacity .15s}
.msg:hover .ma{opacity:1}
.msg.user .ma{align-self:flex-end}
.ab{background:var(--sf);border:1px solid var(--bd);color:var(--td);
  font-size:10px;padding:2px 7px;border-radius:4px;cursor:pointer;
  transition:color .15s,border-color .15s}
.ab:hover{color:var(--ac);border-color:var(--ac)}
.mm{font-size:10px;color:var(--td);margin-top:3px;padding:0 2px}
.msg.user .mm{text-align:right}
#typ{display:none;align-self:flex-start;padding:8px 14px;background:var(--sf2);
  border:1px solid var(--bd);border-radius:10px;border-bottom-left-radius:2px;
  font-size:12px;color:var(--td)}
#typ.show{display:flex;align-items:center;gap:6px}
.db{width:5px;height:5px;background:var(--ac);border-radius:50%;animation:bl .8s infinite}
.db:nth-child(2){animation-delay:.15s}.db:nth-child(3){animation-delay:.3s}
@keyframes bl{0%,80%,100%{transform:scale(.6);opacity:.4}40%{transform:scale(1);opacity:1}}
pre{background:#0d0f14;border:1px solid var(--bd);border-radius:6px;padding:10px 12px;
  overflow-x:auto;font-family:var(--mono);font-size:12px;line-height:1.5;
  margin:6px 0;position:relative}
.cc{position:absolute;top:6px;right:6px;background:var(--sf);border:1px solid var(--bd);
  color:var(--td);font-size:10px;padding:2px 7px;border-radius:4px;cursor:pointer;transition:color .15s}
.cc:hover{color:var(--ac)}
code{font-family:var(--mono);font-size:12px}
p code{background:rgba(255,255,255,.06);padding:1px 5px;border-radius:3px}
.src-badge{display:inline-block;font-size:9px;padding:1px 5px;border-radius:4px;
  background:rgba(0,200,255,.1);border:1px solid rgba(0,200,255,.2);
  color:var(--ac);margin:0 2px;vertical-align:middle}
#ia{background:var(--sf);border-top:1px solid var(--bd);padding:8px 10px;
  display:flex;flex-direction:column;gap:6px;flex-shrink:0}
#fp{display:none;align-items:center;gap:6px;padding:5px 10px;
  background:var(--sf2);border:1px solid var(--bd);border-radius:6px;
  font-size:11px;color:var(--tm)}
#fp.show{display:flex}
#fpn{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#fpc{background:none;border:none;color:var(--dn);cursor:pointer;font-size:14px;padding:0 2px}
.ir{display:flex;align-items:flex-end;gap:6px}
#mi{flex:1;background:var(--sf2);border:1px solid var(--bd);border-radius:6px;
  color:var(--tx);font-family:var(--ui);font-size:13.5px;padding:8px 11px;
  resize:none;outline:none;min-height:36px;max-height:130px;
  overflow-y:hidden;line-height:1.5;transition:border-color .15s}
#mi:focus{border-color:var(--ac)}
#mi::placeholder{color:var(--td)}
.ibt{display:flex;gap:4px;flex-shrink:0;align-items:flex-end}
.ib{width:36px;height:36px;background:var(--sf2);border:1px solid var(--bd);
  border-radius:6px;color:var(--tm);font-size:16px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:color .15s,border-color .15s}
.ib:hover{color:var(--ac);border-color:var(--ac)}
#bsnd{width:36px;height:36px;background:var(--ac);border:none;border-radius:6px;
  color:#000;font-size:17px;cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:background .15s,opacity .15s}
#bsnd:disabled{opacity:.4;cursor:default}
#bsnd:not(:disabled):hover{background:#33d4ff}
input[type=file]{display:none}
#toast{position:fixed;bottom:70px;left:50%;transform:translateX(-50%) translateY(8px);
  background:var(--sf2);border:1px solid var(--bd);color:var(--tx);
  font-size:12px;padding:6px 16px;border-radius:20px;opacity:0;pointer-events:none;
  transition:opacity .2s,transform .2s;white-space:nowrap;z-index:999}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<div id="ov" onclick="closeSB()"></div>
<div id="app">

<aside id="sb" class="col">
<div id="sbi">
  <div class="sb-hd">
    <div class="sb-logo">
      <span style="font-size:20px;flex-shrink:0">&#x2B61;</span>
      <div><div class="an">ATLAS OS</div><div class="av">v21.6</div></div>
    </div>
    <button id="btn-x" onclick="closeSB()">&#x2715;</button>
  </div>
  <div class="sb-met">
    <div class="mr"><span class="ml">BAT</span><span class="mv" id="m-bat">&#x2014;</span></div>
    <div class="mr"><span class="ml">RAM</span><span class="mv" id="m-ram">&#x2014;</span></div>
    <div class="bw"><div class="bf" id="m-bar" style="width:0%"></div></div>
  </div>
  <nav class="sb-nav">
    <div class="ns">NAVIGACIJA</div>
    <div class="ni act" onclick="navAct(this)"><span class="ico">&#x1F4AC;</span><span>Chat</span></div>
    <div class="ni" onclick="navAct(this);qCmd('recall')"><span class="ico">&#x1F9E0;</span><span>Memorija</span></div>
    <div class="ni" onclick="navAct(this);qCmd('TOOL:list_files')"><span class="ico">&#x1F4C1;</span><span>Fajlovi</span></div>
    <div class="ns">KATEGORIJE</div>
    <div class="ni" onclick="togSub('sub-mm',this)">
      <span class="ico">&#x1F3AC;</span><span>Multimedija</span>
      <span class="ni-arr" id="arr-sub-mm">&#x25B8;</span>
    </div>
    <div class="sub" id="sub-mm">
      <div class="si" onclick="qCmd('Pomozi mi s video montazom');closeSB()"><span class="ico">&#x1F39E;</span>Video</div>
      <div class="si" onclick="qCmd('Pomozi mi s audio miksanjem');closeSB()"><span class="ico">&#x1F3B5;</span>Audio</div>
      <div class="si" onclick="qCmd('Pomozi mi s foto editingom');closeSB()"><span class="ico">&#x1F4F7;</span>Foto</div>
      <div class="si" onclick="qCmd('Preporuke za video kodeke');closeSB()"><span class="ico">&#x2699;</span>Kodeci</div>
    </div>
    <div class="ni" onclick="togSub('sub-prog',this)">
      <span class="ico">&#x1F4BB;</span><span>Programiranje</span>
      <span class="ni-arr" id="arr-sub-prog">&#x25B8;</span>
    </div>
    <div class="sub" id="sub-prog">
      <div class="si" onclick="qCmd('Napisi Python skriptu za');closeSB()"><span class="ico">&#x1F40D;</span>Python</div>
      <div class="si" onclick="qCmd('Napisi JavaScript kod za');closeSB()"><span class="ico">&#x1F310;</span>JavaScript</div>
      <div class="si" onclick="qCmd('Pomozi mi debugirati gresku');closeSB()"><span class="ico">&#x1F41B;</span>Debug</div>
      <div class="si" onclick="qCmd('TOOL:list_files');closeSB()"><span class="ico">&#x1F4C2;</span>Fajlovi</div>
    </div>
    <div class="ni" onclick="togSub('sub-sci',this)">
      <span class="ico">&#x1F52C;</span><span>Znanost</span>
      <span class="ni-arr" id="arr-sub-sci">&#x25B8;</span>
    </div>
    <div class="sub" id="sub-sci">
      <div class="si head" onclick="togSub('sub-radar',this)">
        <span class="ico">&#x1F310;</span>Globalni Radar
        <span class="ni-arr" id="arr-sub-radar" style="margin-left:auto">&#x25B8;</span>
      </div>
      <div class="sub" id="sub-radar">
        <div class="si si-nested" onclick="qCmd('globalni radar');closeSB()"><span class="ico">&#x1F4E1;</span>Svi izvori</div>
        <div class="si si-nested" onclick="qCmd('MIT vijesti radar');closeSB()"><span class="ico">&#x1F393;</span>MIT News</div>
        <div class="si si-nested" onclick="qCmd('Oxford vijesti radar');closeSB()"><span class="ico">&#x1F393;</span>Oxford</div>
        <div class="si si-nested" onclick="qCmd('Harvard vijesti radar');closeSB()"><span class="ico">&#x1F393;</span>Harvard</div>
        <div class="si si-nested" onclick="qCmd('Stanford vijesti radar');closeSB()"><span class="ico">&#x1F393;</span>Stanford</div>
        <div class="si si-nested" onclick="qCmd('hackernews radar');closeSB()"><span class="ico">&#x1F4BB;</span>Hacker News</div>
        <div class="si si-nested" onclick="qCmd('techcrunch radar');closeSB()"><span class="ico">&#x1F4F1;</span>TechCrunch</div>
        <div class="si si-nested" onclick="qCmd('verge vijesti radar');closeSB()"><span class="ico">&#x1F4F0;</span>The Verge</div>
      </div>
      <div class="si" onclick="qCmd('Pretrazi ArXiv za');closeSB()"><span class="ico">&#x1F4C4;</span>ArXiv radovi</div>
      <div class="si" onclick="qCmd('Pretrazi Wikipedia za');closeSB()"><span class="ico">&#x1F4D6;</span>Wikipedia</div>
      <div class="si" onclick="qCmd('Pretrazi knjige o');closeSB()"><span class="ico">&#x1F4DA;</span>Open Library</div>
    </div>
    <div class="ni" onclick="togSub('sub-edu',this)">
      <span class="ico">&#x1F393;</span><span>Edukacija</span>
      <span class="ni-arr" id="arr-sub-edu">&#x25B8;</span>
    </div>
    <div class="sub" id="sub-edu">
      <div class="si" onclick="qCmd('Objasni mi ukratko');closeSB()"><span class="ico">&#x1F4DD;</span>Sazetak</div>
      <div class="si" onclick="qCmd('Napravi kviz pitanja o');closeSB()"><span class="ico">&#x2753;</span>Kviz</div>
      <div class="si" onclick="qCmd('Prevedi na engleski:');closeSB()"><span class="ico">&#x1F30D;</span>Prijevod</div>
      <div class="si" onclick="qCmd('Napisi esej o');closeSB()"><span class="ico">&#x270D;</span>Esej</div>
    </div>
    <div class="ns">ALATI</div>
    <div class="ni" onclick="doWebScout()">
      <span class="ico">&#x1F50D;</span><span>Web Scout</span>
      <span class="ni-badge off" id="badge-scout">&#x2014;</span>
    </div>
    <div class="ni" onclick="qCmd('TOOL:vault_status');closeSB()">
      <span class="ico">&#x1F510;</span><span>Vault</span>
      <span class="ni-badge off" id="badge-vault">&#x2014;</span>
    </div>
    <div class="ni" onclick="doUltraSearch()"><span class="ico">&#x1F30D;</span><span>Ultra-Search</span></div>
    <div class="ns">AKCIJE</div>
    <div class="ni" onclick="qCmd('recall');closeSB()"><span class="ico">&#x1F50D;</span><span>Recall</span></div>
    <div class="ni" onclick="qCmd('clear');closeSB()"><span class="ico">&#x1F5D1;</span><span>Reset chat</span></div>
    <div class="ni" onclick="qCmd('backup');closeSB()"><span class="ico">&#x2601;</span><span>Backup</span></div>
    <div class="ni" onclick="qCmd('git pull');closeSB()"><span class="ico">&#x2B07;</span><span>Git pull</span></div>
  </nav>
  <div class="sb-set">
    <div class="ns" style="padding:0 0 6px">POSTAVKE</div>
    <div class="sr">
      <label>JEZIK</label>
      <select id="lsel" onchange="chLang(this.value)">
        <option value="hr">Hrvatski</option>
        <option value="en">English</option>
        <option value="de">Deutsch</option>
        <option value="fr">Francais</option>
        <option value="es">Espanol</option>
      </select>
    </div>
  </div>
  <div class="sb-mods">
    <div class="mod-title">MODULI</div>
    <div class="md"><div class="dot off" id="mod-scout"></div><span>web_scout</span></div>
    <div class="md"><div class="dot off" id="mod-media"></div><span>media_pro</span></div>
    <div class="md"><div class="dot off" id="mod-lingua"></div><span>lingua_core</span></div>
    <div class="md"><div class="dot off" id="mod-vault"></div><span>vault</span></div>
    <div class="md"><div class="dot off" id="mod-brain"></div><span>vector_brain</span></div>
    <div class="md"><div class="dot off" id="mod-ctx"></div><span>context_helper</span></div>
    <div class="md"><div class="dot off" id="mod-bs4"></div><span>bs4 DDG scraper</span></div>
    <div class="md"><div class="dot off" id="mod-fp"></div><span>feedparser (Radar)</span></div>
  </div>
</div>
</aside>

<div id="main">
  <header id="hdr">
    <button id="btn-sb" onclick="togSB()">&#x2630;</button>
    <div id="htitle">ATLAS OS v21.6</div>
    <span class="hb" id="mode-b">fast</span>
    <span class="hb" id="lang-b">hr</span>
    <span id="conn" class="con">&#x2B61; &#x2026;</span>
  </header>
  <div id="chat">
    <div class="msg atlas">
      <div class="bubble">
        Pozdrav! Ja sam <strong>ATLAS OS v21.6</strong>.<br>
        Ultra-Search: DDG/bs4 &bull; Wikipedia &bull; ArXiv &bull; Open Library &bull; Google.<br>
        Globalni Radar: Oxford &bull; MIT &bull; Harvard &bull; Stanford &bull; HN &bull; TechCrunch &bull; The Verge.<br>
        <small style="color:var(--td)">Otvori sidebar &#x2630; &rarr; Znanost &rarr; Globalni Radar za vijesti.</small>
      </div>
      <div class="mm">ATLAS &bull; v21.6</div>
    </div>
  </div>
  <div id="typ">
    <div class="db"></div><div class="db"></div><div class="db"></div>
    <span style="font-size:11px;color:var(--td);margin-left:2px">ATLAS razmislja&#x2026;</span>
  </div>
  <div id="ia">
    <div id="fp">
      <span>&#x1F4CE;</span><span id="fpn">&#x2014;</span>
      <button id="fpc" onclick="clrF()">&#x2715;</button>
    </div>
    <div class="ir">
      <textarea id="mi" rows="1"
        placeholder="Pitajte Atlas... (Shift+Enter = novi red)"
        oninput="aExp(this)" onkeydown="hKey(event)"></textarea>
      <div class="ibt">
        <button class="ib" title="Slika" onclick="document.getElementById('ii').click()">&#x1F5BC;</button>
        <button class="ib" title="Fajl"  onclick="document.getElementById('fi').click()">&#x1F4CE;</button>
        <button id="bsnd" onclick="sndMsg()">&#x27A4;</button>
      </div>
    </div>
  </div>
</div>
</div>
<div id="toast"></div>
<input type="file" id="ii" accept="image/*" onchange="hImg(this)">
<input type="file" id="fi" accept=".txt,.py,.js,.csv,.json,.md,.pdf" onchange="hFile(this)">
<script>
var ws=null,wsR=false,sbOpen=false,pImg=null,pFile=null,lang="hr";

function togSB(){sbOpen?closeSB():openSB()}
function openSB(){
  sbOpen=true;
  document.getElementById("sb").classList.remove("col");
  if(window.innerWidth<=640)document.getElementById("ov").classList.add("show");
}
function closeSB(){
  sbOpen=false;
  document.getElementById("sb").classList.add("col");
  document.getElementById("ov").classList.remove("show");
}
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&sbOpen)closeSB()});

function togSub(id,triggerEl){
  var el=document.getElementById(id);
  var isOpen=el.classList.contains("open");
  var parentSub=triggerEl?triggerEl.closest(".sub"):null;
  if(!parentSub){
    document.querySelectorAll(".sub").forEach(function(s){
      if(s.id!==id&&s.id!=="sub-radar"){
        s.classList.remove("open");
      }
    });
    document.querySelectorAll(".ni-arr").forEach(function(a){
      if(a.id!=="arr-sub-radar")a.classList.remove("open");
    });
  }
  el.classList.toggle("open",!isOpen);
  var arrId="arr-"+id;
  var arr=document.getElementById(arrId);
  if(arr)arr.classList.toggle("open",!isOpen);
}

function initWS(){
  var pr=location.protocol==="https:"?"wss:":"ws:";
  ws=new WebSocket(pr+"//"+location.host+"/ws");
  ws.onopen=function(){wsR=true;setConn("ok","&#x2B61; Spojeno");fetchMet();fetchMods()};
  ws.onclose=function(){wsR=false;setConn("err","&#x2B61; Odspojen");setTimeout(initWS,3000)};
  ws.onerror=function(){setConn("err","&#x2B61; Greska")};
  ws.onmessage=function(ev){
    try{
      var d=JSON.parse(ev.data);
      if(d.type==="typing"){showTyp(true);return}
      showTyp(false);
      if(d.type==="message"){
        addMsg("atlas",d.content,d.mode);
        if(d.lang&&["hr","en","de","fr","es"].indexOf(d.lang)>=0){
          lang=d.lang;
          document.getElementById("lsel").value=d.lang;
          document.getElementById("lang-b").textContent=d.lang;
        }
        if(d.mode)document.getElementById("mode-b").textContent=d.mode;
      }
      if(d.type==="error")addMsg("atlas","&#x26A0; "+d.content);
    }catch(e){showTyp(false);addMsg("atlas",ev.data)}
  };
}
function setConn(s,l){var el=document.getElementById("conn");el.className=s;el.innerHTML=l}

function aExp(el){
  el.style.height="auto";
  var lh=parseFloat(getComputedStyle(el).lineHeight)||21;
  var max=lh*5+18;
  el.style.height=Math.min(el.scrollHeight,max)+"px";
  el.style.overflowY=el.scrollHeight>max?"auto":"hidden";
}

function sndMsg(){
  var inp=document.getElementById("mi");
  var msg=inp.value.trim();
  if(!wsR){showToast("&#x26A0; Nema veze");return}
  if(!msg&&!pImg&&!pFile)return;
  if(msg.indexOf("TOOL:")<0)addMsg("user",msg||"");
  var pl={message:msg};
  if(pImg){pl.image_b64=pImg.b64;pl.image_mime=pImg.mime;if(!msg)addMsg("user","&#x1F5BC; [slika]")}
  if(pFile){pl.file_name=pFile.name;pl.file_content=pFile.content;if(!msg)addMsg("user","&#x1F4CE; "+pFile.name)}
  ws.send(JSON.stringify(pl));
  inp.value="";inp.style.height="auto";inp.style.overflowY="hidden";
  pImg=pFile=null;clrF();showTyp(true);
}
function hKey(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sndMsg()}}

function addMsg(role,content,mode){
  var chat=document.getElementById("chat");
  var wrap=document.createElement("div");wrap.className="msg "+role;
  var bub=document.createElement("div");bub.className="bubble";
  bub.innerHTML=fmt(content);
  bub.querySelectorAll("pre").forEach(function(pre){
    var btn=document.createElement("button");btn.className="cc";btn.textContent="Kopiraj";
    btn.onclick=function(){
      navigator.clipboard.writeText(pre.innerText.replace(btn.innerText,"").trim())
        .then(function(){showToast("Kopirano!")});
    };
    pre.appendChild(btn);
  });
  var meta=document.createElement("div");meta.className="mm";
  var now=new Date();
  var ts=now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0");
  meta.textContent=(role==="user"?"Ti":"ATLAS")+" \u00B7 "+ts+(mode?" \u00B7 "+mode:"");
  var acts=document.createElement("div");acts.className="ma";
  var cp=document.createElement("button");cp.className="ab";cp.textContent="Kopiraj";
  cp.onclick=function(){navigator.clipboard.writeText(bub.innerText).then(function(){showToast("Kopirano!")})};
  var ed=document.createElement("button");ed.className="ab";ed.textContent="Uredi";
  ed.onclick=function(){var i=document.getElementById("mi");i.value=bub.innerText;aExp(i);i.focus()};
  acts.appendChild(cp);
  if(role==="user")acts.appendChild(ed);
  wrap.appendChild(bub);wrap.appendChild(acts);wrap.appendChild(meta);
  chat.appendChild(wrap);chat.scrollTop=chat.scrollHeight;
}

function fmt(txt){
  if(!txt)return"";
  var s=txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  s=s.replace(/```(\w*)\n?([\s\S]*?)```/g,function(_,l,c){return"<pre><code class=\"lang-"+(l||"text")+"\">"+c.trim()+"</code></pre>"});
  s=s.replace(/`([^`]+)`/g,"<code>$1</code>");
  s=s.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
  s=s.replace(/\*(.+?)\*/g,"<em>$1</em>");
  s=s.replace(/^### (.+)$/gm,"<h4 style='margin:.4em 0 .2em;font-size:13px;color:var(--ac)'>$1</h4>");
  s=s.replace(/^## (.+)$/gm,"<h3 style='margin:.5em 0 .2em;font-size:14px;color:var(--ac)'>$1</h3>");
  s=s.replace(/^# (.+)$/gm,"<h2 style='margin:.6em 0 .2em;font-size:15px;color:var(--ac)'>$1</h2>");
  s=s.replace(/^[\-\*] (.+)$/gm,"<li>$1</li>");
  s=s.replace(/(<li>.*<\/li>)+/gs,function(m){return"<ul style='padding-left:16px;margin:4px 0'>"+m+"</ul>"});
  s=s.replace(/\[(.+?)\]\((https?:\/\/[^\)]+)\)/g,"<a href=\"$2\" target=\"_blank\" rel=\"noopener\" style=\"color:var(--ac)\">$1</a>");
  var badges=[["Wikipedia","Wikipedia"],["DDG","DDG"],["ArXiv","ArXiv"],
    ["OpenLibrary","OpenLibrary"],["Oxford","Oxford"],["MIT","MIT"],
    ["Harvard","Harvard"],["Stanford","Stanford"],["HackerNews","HN"],
    ["TechCrunch","TechCrunch"],["TheVerge","The Verge"]];
  badges.forEach(function(pair){
    s=s.replace(new RegExp("\\["+pair[0]+"\\]","g"),"<span class=\"src-badge\">"+pair[1]+"</span>");
  });
  s=s.replace(/\n/g,"<br>");
  return s;
}

function showTyp(show){
  document.getElementById("typ").classList.toggle("show",show);
  if(show)document.getElementById("chat").scrollTop=999999;
}
var _tt=null;
function showToast(msg,ms){
  ms=ms||2000;
  var el=document.getElementById("toast");
  el.textContent=msg;el.classList.add("show");
  clearTimeout(_tt);_tt=setTimeout(function(){el.classList.remove("show")},ms);
}
function navAct(el){document.querySelectorAll(".ni").forEach(function(i){i.classList.remove("act")});el.classList.add("act")}
function qCmd(cmd){var inp=document.getElementById("mi");inp.value=cmd;sndMsg()}
function doWebScout(){var q=prompt("Web Scout -- upit:");if(q){qCmd(q);closeSB()}}
function doUltraSearch(){var q=prompt("Ultra-Search -- upit:");if(q){qCmd(q);closeSB()}}
function chLang(l){lang=l;document.getElementById("lang-b").textContent=l;showToast("Jezik: "+l)}
function hImg(inp){
  var f=inp.files[0];if(!f)return;
  if(f.size>10*1024*1024){showToast("Max 10MB");return}
  var r=new FileReader();
  r.onload=function(e){pImg={b64:e.target.result.split(",")[1],mime:f.type};showFP("&#x1F5BC; "+f.name)};
  r.readAsDataURL(f);inp.value="";
}
function hFile(inp){
  var f=inp.files[0];if(!f)return;
  if(f.size>5*1024*1024){showToast("Max 5MB");return}
  var r=new FileReader();
  r.onload=function(e){pFile={name:f.name,content:e.target.result};showFP("&#x1F4CE; "+f.name)};
  r.readAsText(f);inp.value="";
}
function showFP(n){document.getElementById("fpn").innerHTML=n;document.getElementById("fp").classList.add("show")}
function clrF(){pImg=pFile=null;document.getElementById("fp").classList.remove("show")}
async function fetchMet(){
  try{
    var r=await fetch("/metrics");if(!r.ok)return;
    var d=await r.json();
    document.getElementById("m-bat").textContent=d.cpu||"N/A";
    var ram=parseFloat(d.mem);
    document.getElementById("m-ram").textContent=isNaN(ram)?(d.mem||"N/A"):ram+"%";
    if(!isNaN(ram))document.getElementById("m-bar").style.width=Math.min(ram,100)+"%";
  }catch(e){}
  setTimeout(fetchMet,15000);
}
async function fetchMods(){
  try{
    var r=await fetch("/modules");if(!r.ok)return;
    var d=await r.json();
    var MAP={scout:["mod-scout","badge-scout"],media:["mod-media",null],
      lingua:["mod-lingua",null],vault:["mod-vault","badge-vault"],
      brain:["mod-brain",null],ctx:["mod-ctx",null],
      bs4:["mod-bs4",null],feedparser:["mod-fp",null]};
    Object.keys(MAP).forEach(function(k){
      var pair=MAP[k];
      var on=!!d[k];
      var dot=document.getElementById(pair[0]);
      if(dot){dot.classList.toggle("on",on);dot.classList.toggle("off",!on)}
      if(pair[1]){
        var b=document.getElementById(pair[1]);
        if(b){b.textContent=on?"aktivan":"nedostupan";b.classList.toggle("off",!on)}
      }
    });
  }catch(e){}
}
document.addEventListener("DOMContentLoaded",function(){
  setConn("con","&#x2B61; Spajam&#x2026;");
  initWS();
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(HTML_UI)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
