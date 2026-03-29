import os, uvicorn, httpx, json, asyncio, subprocess, re, base64, io
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import aiosqlite

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI()
DB_PATH = "database.db"

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
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

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, data TEXT)")
        await db.commit()

async def save_msg(role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO memory (role, content, timestamp) VALUES (?,?,?)", (role, str(content)[:600], str(datetime.now())))
        await db.execute("DELETE FROM memory WHERE id NOT IN (SELECT id FROM memory ORDER BY id DESC LIMIT 40)")
        await db.commit()

async def get_history(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT ?", (limit,)) as c:
            rows = await c.fetchall()
    return [{"role": r, "content": cnt} for r, cnt in reversed(rows)]

async def clear_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM memory")
        await db.commit()

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
    print(f"[TOKENS] ~{count_tokens(system + history + last)} tokena")
    return system + history + last

PROFILE_TRIGGERS = ["zovem se", "moje ime", "radim na", "volim", "preferiram", "projekt", "koristim", "my name", "i am", "i work", "i like"]

async def update_profile(user_msg: str):
    if not any(k in user_msg.lower() for k in PROFILE_TRIGGERS):
        return
    try:
        model = _groq_model or GROQ_MODELS[0]
        prompt = f'Extract user info as JSON only. Schema: {{"name":"","preferences":[],"projects":[]}} Message: {user_msg[:300]}'
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 150, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]})
            if r.status_code != 200: return
            raw = re.sub(r"```json?", "", r.json()["choices"][0]["message"]["content"]).replace("```","").strip()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO profile VALUES (1,?)", (json.dumps(json.loads(raw)),))
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

def detect_language(text: str) -> str:
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

def detect_mode(msg: str) -> str:
    m = msg.lower()
    if re.search(r'https?://', m): return "url"
    if any(k in m for k in ["bug","error","greška","kod","debug","fix","python","script","funkcij","code"]): return "code"
    if any(k in m for k in ["zašto","objasni","analiziraj","usporedi","razlika","kako radi","sto je","analyze","explain","compare"]): return "analysis"
    if any(k in m for k in ["ideja","napravi","smisli","kreativan","prijedlog","osmisli","create","design","imagine"]): return "creative"
    if any(k in m for k in ["vijesti","danas","pretrazi","tko je","ko je","cijena","trenutno","news","search","today"]): return "search"
    return "fast"

def extract_urls(text: str) -> list:
    found = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    return [u for u in found if not any(b in u for b in URL_BLACKLIST)]

async def fetch_url_content(url: str) -> tuple:
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
               "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.9"}
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
            html = re.sub(r'&[a-zA-Z]+;', ' ', html)
            html = re.sub(r'\s+', ' ', html).strip()
            return html[:4000], "web"
    except httpx.TimeoutException: return "[Timeout — stranica ne reagira]", "error"
    except httpx.ConnectError: return "[Greska veze — stranica nedostupna]", "error"
    except Exception as e: return f"[Greska: {str(e)[:120]}]", "error"

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
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = ""
            for i, page in enumerate(reader.pages[:12]):
                text += f"\n--- Str. {i+1} ---\n{page.extract_text() or ''}"
            return f"[PDF — {len(reader.pages)} stranica]\n{text[:5000]}"
        except ImportError:
            try:
                raw = content.decode("latin-1", errors="ignore")
                chunks = re.findall(r'BT\s*(.*?)\s*ET', raw, re.DOTALL)
                texts = [p for c in chunks for p in re.findall(r'\((.*?)\)', c)]
                result = " ".join(texts)
                if result: return f"[PDF parcijalno]\n{result[:4000]}"
            except: pass
            return "[PDF ucitan. Instaliraj: pip install pypdf]"
    except Exception as e: return f"[PDF greska: {str(e)[:100]}]"

def _parse_file(name: str, content: str) -> str:
    ext = name.lower().split(".")[-1] if "." in name else ""
    if ext == "pdf":
        try:
            b64 = content.split(",")[1] if "," in content else content
            raw = base64.b64decode(b64)
            return _parse_pdf(raw)
        except Exception as e: return f"[PDF greska: {e}]"
    if ext == "csv": return f"[CSV]\n" + "\n".join(content.split("\n")[:50])
    if ext == "json":
        try: return f"[JSON]\n{json.dumps(json.loads(content), indent=2, ensure_ascii=False)[:3000]}"
        except: pass
    return f"[Fajl: {name}]\n{content[:3000]}"

def _web_search(query: str, news: bool = False) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            if news:
                results = list(ddgs.news(query, max_results=5))
                return "\n".join(f"• [{r.get('date','')[:10]}] {r['title']}: {r.get('body','')[:200]}" for r in results)
            results = list(ddgs.text(query, max_results=5))
            return "\n".join(f"• {r['title']}: {r['body'][:200]}" for r in results)
    except Exception as e:
        print(f"[SEARCH] {e}")
        return ""

def run_backup(filepath: str = "") -> str:
    try:
        if filepath:
            fp = filepath.strip().strip("'\"")
            if not os.path.isabs(fp):
                fp = os.path.join(os.path.expanduser("~"), "atlas_os_v1", fp)
            if os.path.exists(fp):
                result = subprocess.run(["rclone", "copy", fp, "remote:AtlasBackup/", "-v"],
                                        capture_output=True, text=True, timeout=120)
                return f"Fajl prenesen: {os.path.basename(fp)}" if result.returncode == 0 else f"rclone greska: {result.stderr[:200]}"
            return f"Fajl nije pronaden: {fp}"
        result = subprocess.run(["python", "cloud_backup.py"], capture_output=True, text=True, timeout=120)
        return "Backup zavrsen — Google Cloud sinkroniziran." if result.returncode == 0 else f"Backup greska: {result.stderr[:200]}"
    except FileNotFoundError: return "rclone nije instaliran. Instaliraj: pkg install rclone"
    except subprocess.TimeoutExpired: return "Backup traje predugo."
    except Exception as e: return f"Backup greska: {str(e)[:100]}"

def _detect_backup_file(msg: str) -> str:
    for p in [r'prenesi\s+["\']?(.+?)["\']?\s+na\s+oblak',
              r'upload\s+["\']?(.+?)["\']?\s+(?:na|to)\s+(?:oblak|cloud)',
              r'spremi\s+["\']?(.+?)["\']?\s+na\s+oblak']:
        m = re.search(p, msg.lower())
        if m: return m.group(1).strip()
    return ""

def run_git_update() -> str:
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=60)
        return f"GitHub azuriranje uspjesno.\n{result.stdout[:300]}\nRestartaj Atlas." if result.returncode == 0 else f"Git greska:\n{result.stderr[:300]}"
    except Exception as e: return f"Git greska: {e}"

LANG_RULES = {
    "hr": "Jezik: standardni hrvatski knjizevni. Gramaticki ispravno.",
    "en": "Language: fluent, natural English.",
    "de": "Sprache: fließendes, natürliches Deutsch.",
    "fr": "Langue: français courant et naturel.",
    "es": "Idioma: español fluido y natural.",
}
MODE_INSTRUCTIONS = {
    "code":     "Samo kod + kratko objasnjenje.",
    "analysis": "Korak po korak. Jasan zakljucak.",
    "creative": "Originalno. Izbjegavaj kliseje.",
    "search":   "Konkretno. Koristi web podatke.",
    "url":      "Analiziraj ucitani sadrzaj. Kljucne tocke.",
    "fast":     "Direktno i kratko.",
    "video":    "Strucnjak za video produkciju.",
    "audio":    "Strucnjak za audio i glazbu.",
    "photo":    "Strucnjak za fotografiju i obradu slika.",
}

def build_system(profile: dict, mode: str, lang: str, media_mode: str) -> str:
    name = profile.get("name",""); prefs = profile.get("preferences",[]); projects = profile.get("projects",[])
    user_ctx = ""
    if name: user_ctx += f"Korisnik: {name}. "
    if prefs: user_ctx += f"Interesi: {', '.join(prefs[:4])}. "
    if projects: user_ctx += f"Projekti: {', '.join(projects[:3])}. "
    media_ctx = f" MULTIMEDIJSKI MOD: {media_mode.upper()}." if media_mode != "text" else ""
    return (
        f"Ti si ATLAS — napredni AI operativni sustav.{media_ctx}\n"
        f"MOD: {mode.upper()} — {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['fast'])}\n"
        f"{LANG_RULES.get(lang, LANG_RULES['hr'])}\n"
        f"KARAKTER: Direktan. Iskren. Bez laskanja. Bez 'Naravno!' i slicnih fraza. Ako korisnik grjesi reci mu konstruktivno.\n"
        f"SPOSOBNOSTI: Citas URL-ove i PDF-ove. Web pretraga. Google Cloud backup. Pamtis razgovor. Analiziras audio i video.\n"
        + (f"PROFIL: {user_ctx}\n" if user_ctx else "")
        + "Kod u blokovima. Tablice u markdown formatu."
    )

async def call_groq(messages: list, temp: float) -> str | None:
    global _groq_model
    messages = trim_messages(messages, 4500)
    order = ([_groq_model] + [m for m in GROQ_MODELS if m != _groq_model] if _groq_model else GROQ_MODELS)
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": temp, "max_tokens": 1000})
                if r.status_code == 200:
                    if _groq_model != model: print(f"[GROQ] Aktivan: {model}"); _groq_model = model
                    return r.json()["choices"][0]["message"]["content"]
                if r.status_code == 413:
                    messages = trim_messages(messages, 2500)
                    r2 = await client.post("https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={"model": model, "messages": messages, "temperature": temp, "max_tokens": 700})
                    if r2.status_code == 200: _groq_model = model; return r2.json()["choices"][0]["message"]["content"]
                if r.status_code == 429: print(f"[GROQ] {model} rate limit"); continue
                print(f"[GROQ] {model} — {r.status_code}")
            except Exception as e: print(f"[GROQ] {model}: {e}"); continue
    _groq_model = None
    return None

async def call_gemini(messages: list) -> str | None:
    global _gemini_model
    prompt = "\n".join(f"{'ATLAS' if m['role']=='assistant' else 'KORISNIK'}: {m['content']}"
                       for m in messages if isinstance(m.get("content"), str))
    if len(prompt) > 18000: prompt = prompt[-18000:]
    order = ([_gemini_model] + [m for m in GEMINI_MODELS if m != _gemini_model] if _gemini_model else GEMINI_MODELS)
    async with httpx.AsyncClient(timeout=45) as client:
        for model in order:
            try:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    if _gemini_model != model: print(f"[GEMINI] Aktivan: {model}"); _gemini_model = model
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if r.status_code == 429: print(f"[GEMINI] {model} quota"); continue
                print(f"[GEMINI] {model} — {r.status_code}")
            except Exception as e: print(f"[GEMINI] {model}: {e}"); continue
    _gemini_model = None
    return None

async def call_ai(messages: list, mode: str = "fast") -> tuple:
    temp = {"fast":0.35,"analysis":0.2,"creative":0.75,"code":0.1,"search":0.3,
            "url":0.2,"video":0.3,"audio":0.3,"photo":0.3}.get(mode, 0.35)
    out = await call_groq(messages, temp)
    if out: return out, _groq_model or "GROQ"
    print("[ATLAS] Groq nedostupan → Gemini")
    out = await call_gemini(messages)
    if out: return out, _gemini_model or "GEMINI"
    return "Oba AI servisa trenutno nedostupna.", "ERROR"

async def call_vision(image_data: str, prompt: str) -> tuple:
    global _vision_model
    b64 = image_data.split(",")[-1] if "," in image_data else image_data
    order = ([_vision_model] + [m for m in GROQ_VISION_MODELS if m != _vision_model]
             if _vision_model else GROQ_VISION_MODELS)
    async with httpx.AsyncClient(timeout=40) as client:
        for model in order:
            try:
                r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "max_tokens": 900, "temperature": 0.2,
                          "messages": [{"role":"user","content":[
                              {"type":"text","text": prompt or "Analiziraj ovu sliku detaljno."},
                              {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}
                          ]}]})
                if r.status_code == 200:
                    _vision_model = model
                    return r.json()["choices"][0]["message"]["content"], "GROQ VISION"
                print(f"[VISION] {model} — {r.status_code}: {r.text[:100]}")
            except Exception as e: print(f"[VISION] {model}: {e}")
    # Gemini Vision fallback
    try:
        gem = _gemini_model or GEMINI_MODELS[0]
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gem}:generateContent?key={GEMINI_API_KEY}",
                json={"contents":[{"parts":[
                    {"text": prompt or "Analiziraj ovu sliku."},
                    {"inline_data":{"mime_type":"image/jpeg","data": b64}}
                ]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], "GEMINI VISION"
            print(f"[VISION GEMINI] {r.status_code}: {r.text[:100]}")
    except Exception as e: print(f"[VISION GEMINI]: {e}")
    return "Vision analiza nedostupna.", "ERROR"

async def call_gemini_media(b64: str, mime: str, prompt: str) -> str | None:
    """Gemini analiza audio/video sadržaja."""
    try:
        gem = _gemini_model or GEMINI_MODELS[0]
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gem}:generateContent?key={GEMINI_API_KEY}",
                json={"contents":[{"parts":[
                    {"text": prompt or "Analiziraj ovaj medijski sadržaj."},
                    {"inline_data":{"mime_type": mime, "data": b64}}
                ]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[MEDIA GEMINI] {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"[MEDIA GEMINI] {e}")
    return None

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
.mt{font-size:9px;color:var(--mu);margin-top:5px}
.fbg{display:inline-flex;align-items:center;gap:4px;background:rgba(14,165,233,.08);border:1px solid var(--br);border-radius:5px;padding:2px 7px;font-size:11px;color:var(--acc);margin-bottom:4px}
.dots{display:flex;gap:4px;padding:3px 0}
.dots span{width:6px;height:6px;border-radius:50%;background:var(--acc);opacity:.3;animation:blink 1.2s infinite}
.dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
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
<aside class="sb" id="sb">
  <div class="sb-hd"><div class="sb-logo">ATLAS</div><div class="sb-sub">OS v17.0 · IMAGO</div></div>
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
  </div>
  <div class="sb-ft">ATLAS AI OS · Groq + Gemini · v17.0</div>
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
  <small style="color:var(--mu)">PDF ✓ &nbsp;Slike ✓ &nbsp;Audio ✓ &nbsp;Video ✓ &nbsp;URL ✓</small></div>
  <div class="mt">BOOT · v17.0</div></div>
</div>
<div id="find">📎 <span id="fname"></span><span onclick="clrF()" style="cursor:pointer;color:var(--rd);margin-left:5px">✕</span></div>
<div class="izone">
  <div class="ibox" id="ibox">
    <input type="file" id="fi" style="display:none" onchange="onFile(this)"
      accept="image/*,audio/*,video/*,application/pdf,text/*,.py,.js,.json,.csv,.md,.txt,.xml,.pdf">
    <button class="ibtn" onclick="document.getElementById('fi').click()">📎</button>
    <textarea id="inp" placeholder="Pitaj Atlas... ili zalijepi URL" rows="1" oninput="ar(this)" onkeydown="hk(event)"></textarea>
    <button class="ibtn sbtn" id="sbtn" onclick="send()">➤</button>
  </div>
</div>
<script>
let ws,pF=null,typEl=null,cMod='text';
const MODS={
  text:{label:'Tekst mod',ph:'Pitaj Atlas... ili zalijepi URL',cls:''},
  video:{label:'Video obrada',ph:'Montaza, kodeci, FPS, export...',cls:'video',tools:['🎬 Montaza','⚙️ Kodeci','📐 Rezolucija','🎞️ FPS','🔊 Audio sync','📤 Export']},
  audio:{label:'Audio / Glazba',ph:'Mix, EQ, snimanje, format...',cls:'audio',tools:['🎵 Mix','🎤 Snimanje','🔉 EQ','🥁 Ritam','📻 Format','💿 Export']},
  photo:{label:'Foto / Slika',ph:'Editing, boja, crop, kompozicija...',cls:'photo',tools:['🖼️ Edit','🎨 Boja','✂️ Crop','💡 Ekspozicija','🔲 Kompozicija','📁 Export']}
};
function setMod(m){
  cMod=m;const cfg=MODS[m];
  ['text','video','audio','photo'].forEach(x=>document.getElementById('m-'+x).classList.toggle('act',x===m));
  document.getElementById('mlabel').textContent=cfg.label;
  document.getElementById('inp').placeholder=cfg.ph;
  const mp=document.getElementById('modp');mp.textContent=m.toUpperCase();mp.className='modp '+(m!=='text'?m:'');
  document.getElementById('ibox').className='ibox '+cfg.cls;
  document.getElementById('sbtn').className='ibtn sbtn '+cfg.cls;
  const bar=document.getElementById('mbar');
  if(cfg.tools){bar.className='mbar show '+m;bar.innerHTML=cfg.tools.map(t=>`<button class="mbtn" onclick="qp('${t}')">${t}</button>`).join('');}
  else{bar.className='mbar';bar.innerHTML='';}
  if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'media_mode',mode:m}));
  closeSb();
}
function qp(t){document.getElementById('inp').value=t.replace(/\p{Emoji}/gu,'').trim()+': ';document.getElementById('inp').focus();}
function conn(){
  ws=new WebSocket('ws://'+location.host+'/ws');
  ws.onopen=()=>setWs(true);
  ws.onclose=()=>{setWs(false);setTimeout(conn,2500);};
  ws.onmessage=e=>{
    const d=JSON.parse(e.data);
    if(d.type==='metrics'){document.getElementById('cpu').textContent=d.data.cpu;document.getElementById('mem').textContent=d.data.mem;return;}
    rmTyp();
    if(d.action==='reload'){location.reload();return;}
    if(d.message)addMsg('atlas',d.message,d.model,d.tags||[],d.mode||'');
    if(d.error)addMsg('error',d.error,null,[]);
  };
}
function setWs(on){document.getElementById('wdot').className='wdot '+(on?'on':'off');}
function setPill(model){
  if(!model)return;
  const el=document.getElementById('mpill');el.textContent=model.split(' ')[0];
  const m=model.toLowerCase();el.className='mpill '+(m.includes('gemini')?'gemini':m.includes('error')?'error':'groq');
}
function addMsg(type,text,model,tags,mode){
  const chat=document.getElementById('chat');
  const now=new Date().toLocaleTimeString('hr',{hour:'2-digit',minute:'2-digit'});
  const d=document.createElement('div');d.className='msg '+(type==='atlas'?'':type);
  const who=type==='atlas'?'Atlas':type==='error'?'Greška':'Ti';
  const wc=type==='atlas'?'atlas':type==='error'?'err':'user';
  let meta=`<div class="mm"><span class="mw ${wc}">${who}</span>`;
  if(model){const mc=model.toLowerCase().includes('gemini')?'gemini':'groq';meta+=`<span class="tg ${mc}">${model.split(' ')[0]}</span>`;setPill(model);}
  ['web','url','pdf','vision','cloud','code','analysis','video','audio','photo'].forEach(t=>{if(tags.includes(t))meta+=`<span class="tg ${t}">${t.toUpperCase()}</span>`;});
  meta+='</div>';
  if(mode&&!['fast','text','url'].includes(mode))document.getElementById('modp').textContent=mode.toUpperCase();
  d.innerHTML=meta+`<div>${esc(text)}</div><div class="mt">${now}</div>`;
  chat.appendChild(d);chat.scrollTop=chat.scrollHeight;
}
function showTyp(){
  const chat=document.getElementById('chat');
  typEl=document.createElement('div');typEl.className='msg';
  typEl.innerHTML=`<div class="mm"><span class="mw atlas">Atlas</span></div><div class="dots"><span></span><span></span><span></span></div>`;
  chat.appendChild(typEl);chat.scrollTop=chat.scrollHeight;
}
function rmTyp(){if(typEl){typEl.remove();typEl=null;}}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');}
function ar(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px';}
function hk(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function send(){
  const inp=document.getElementById('inp');const txt=inp.value.trim();
  if(!txt&&!pF)return;
  const chat=document.getElementById('chat');
  const d=document.createElement('div');d.className='msg user';
  const badge=pF?`<div class="fbg">📎 ${pF.name}</div>`:'';
  d.innerHTML=`<div class="mm"><span class="mw user">Ti</span></div>${badge}<div>${esc(txt)}</div>`;
  chat.appendChild(d);chat.scrollTop=chat.scrollHeight;
  showTyp();
  ws.send(JSON.stringify({text:txt,file:pF,mediaMode:cMod}));
  inp.value='';inp.style.height='auto';clrF();
}
function onFile(input){
  const file=input.files[0];if(!file)return;
  const ext=file.name.split('.').pop().toLowerCase();
  const isImg=file.type.startsWith('image/');
  const isPdf=ext==='pdf'||file.type==='application/pdf';
  const isAudio=file.type.startsWith('audio/')||['mp3','wav','ogg','flac','m4a','aac'].includes(ext);
  const isVideo=file.type.startsWith('video/')||['mp4','mkv','avi','mov','webm'].includes(ext);
  const reader=new FileReader();
  reader.onload=e=>{
    pF={name:file.name,type:file.type,data:e.target.result,
        isImage:isImg,isPdf:isPdf,isAudio:isAudio,isVideo:isVideo,ext:ext};
    document.getElementById('find').style.display='block';
    document.getElementById('fname').textContent=file.name;
  };
  // PDF, slike, audio, video — sve kao base64
  if(isImg||isPdf||isAudio||isVideo) reader.readAsDataURL(file);
  else reader.readAsText(file);
}
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

@app.get("/manifest.json")
async def manifest():
    return JSONResponse({"name":"ATLAS OS","short_name":"ATLAS","start_url":"/","display":"standalone",
                         "background_color":"#000","theme_color":"#0ea5e9",
                         "icons":[{"src":"https://cdn-icons-png.flaticon.com/512/714/714390.png","sizes":"512x512","type":"image/png"}]})

@app.get("/sw.js")
async def sw():
    return HTMLResponse("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));self.addEventListener('fetch',e=>{});",
                        media_type="application/javascript")

@app.get("/")
async def home():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    await init_db()
    loop = asyncio.get_event_loop()
    session_media = "text"

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
                await websocket.send_json({"message":msg,"model":"SYSTEM","tags":["cloud"],"mode":"fast"}); continue

            if raw == "__GIT_UPDATE__":
                msg = await loop.run_in_executor(None, run_git_update)
                await websocket.send_json({"message":msg,"model":"SYSTEM","tags":[],"mode":"fast"}); continue

            try: data = json.loads(raw)
            except: data = {"text": raw}

            if data.get("type") == "media_mode":
                session_media = data.get("mode","text"); continue

            user_msg   = data.get("text","").strip()
            file_data  = data.get("file")
            media_mode = data.get("mediaMode", session_media)

            if not user_msg and not file_data: continue
            if user_msg: asyncio.create_task(update_profile(user_msg))

            lang = detect_language(user_msg) if user_msg else "hr"

            # Backup po imenu fajla
            backup_kw = ["prenesi na oblak","upload na oblak","spremi na oblak","prenesi fajl","backup fajl"]
            if any(k in user_msg.lower() for k in backup_kw):
                fname = _detect_backup_file(user_msg)
                msg = await loop.run_in_executor(None, run_backup, fname)
                await save_msg("user", user_msg); await save_msg("assistant", msg)
                await websocket.send_json({"message":msg,"model":"SYSTEM","tags":["cloud"],"mode":"fast"}); continue

            # ── SLIKA → Vision ──
            if file_data and file_data.get("isImage"):
                out, model = await call_vision(file_data["data"], user_msg)
                await save_msg("user", f"[SLIKA] {user_msg[:150]}")
                await save_msg("assistant", out)
                await websocket.send_json({"message":out,"model":model,"tags":["vision"],"mode":"analysis"}); continue

            # ── AUDIO → Gemini ──
            if file_data and file_data.get("isAudio"):
                b64  = file_data["data"].split(",")[-1] if "," in file_data["data"] else file_data["data"]
                mime = file_data.get("type","audio/mpeg")
                out  = await call_gemini_media(b64, mime, user_msg or "Transkribiraj i analiziraj ovaj audio.")
                if out:
                    await save_msg("user", f"[AUDIO] {user_msg[:150]}")
                    await save_msg("assistant", out)
                    await websocket.send_json({"message":out,"model":"GEMINI","tags":["audio"],"mode":"audio"}); continue
                await websocket.send_json({"message":"Audio analiza trenutno nedostupna.","model":"ERROR","tags":["audio"],"mode":"audio"}); continue

            # ── VIDEO → Gemini ──
            if file_data and file_data.get("isVideo"):
                b64  = file_data["data"].split(",")[-1] if "," in file_data["data"] else file_data["data"]
                mime = file_data.get("type","video/mp4")
                out  = await call_gemini_media(b64, mime, user_msg or "Analiziraj ovaj video sadržaj.")
                if out:
                    await save_msg("user", f"[VIDEO] {user_msg[:150]}")
                    await save_msg("assistant", out)
                    await websocket.send_json({"message":out,"model":"GEMINI","tags":["video"],"mode":"video"}); continue
                await websocket.send_json({"message":"Video analiza trenutno nedostupna.","model":"ERROR","tags":["video"],"mode":"video"}); continue

            mode = detect_mode(user_msg)
            tags = []; extra_ctx = ""

            # ── URL čitanje ──
            urls = extract_urls(user_msg) if user_msg else []
            if urls:
                parts = []
                for url in urls[:3]:
                    print(f"[URL] Citam: {url}")
                    content, ctype = await fetch_url_content(url)
                    parts.append(f"[SADRZAJ: {url}]\n{content}")
                    tags.append("pdf" if ctype == "pdf" else "url")
                extra_ctx = "\n\n" + "\n\n---\n\n".join(parts)
                mode = "url"

            # ── Web search ──
            elif mode == "search":
                is_news = any(k in user_msg.lower() for k in ["vijesti","news","danas","today","trenutno"])
                web = await loop.run_in_executor(None, _web_search, user_msg, is_news)
                if web: extra_ctx = f"\n\n[WEB REZULTATI]\n{web}"; tags.append("web")

            # ── PDF upload ──
            if file_data and file_data.get("isPdf"):
                fname   = file_data.get("name","dokument.pdf")
                fdata   = file_data.get("data","")
                parsed  = _parse_file(fname, fdata)
                extra_ctx += f"\n\n{parsed}"
                tags.append("pdf")

            # ── Ostale datoteke (tekst, kod, CSV, JSON) ──
            elif file_data and not file_data.get("isImage") and not file_data.get("isAudio") and not file_data.get("isVideo") and not file_data.get("isPdf"):
                fname   = file_data.get("name","nepoznato")
                fcontent = file_data.get("data","")
                parsed  = _parse_file(fname, fcontent)
                extra_ctx += f"\n\n{parsed}"

            profile    = await get_profile()
            history    = await get_history(10)
            sys_prompt = build_system(profile, mode, lang, media_mode)

            user_content = user_msg
            if extra_ctx: user_content = f"{user_msg}\n{extra_ctx[:3500]}"

            messages = [{"role":"system","content":sys_prompt}] + history + [{"role":"user","content":user_content}]

            out, model = await call_ai(messages, mode)
            await save_msg("user", user_msg[:400])
            await save_msg("assistant", out[:600])

            if media_mode != "text" and media_mode not in tags:
                tags.append(media_mode)

            await websocket.send_json({"message":out,"model":model,"tags":tags,"mode":mode})

        except WebSocketDisconnect: break
        except Exception as e:
            print(f"[ATLAS ERROR] {e}")
            try: await websocket.send_json({"error":f"Greska: {str(e)[:150]}","tags":[],"mode":"fast"})
            except: break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)