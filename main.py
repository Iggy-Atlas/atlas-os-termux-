import os, uvicorn, httpx, json, asyncio, subprocess, re
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import aiosqlite

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI()
DB_PATH = "database.db"

# ══════════════════════════════════════
# MODEL REGISTRY
# ══════════════════════════════════════
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]
GROQ_VISION_MODELS = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]

_groq_model, _gemini_model, _vision_model = None, None, None

URL_BLACKLIST = ["api.groq.com", "googleapis.com", "generativelanguage", "openai.com", "fonts.googleapis", "cdnjs.cloudflare", "anthropic.com", "localhost", "127.0.0.1", "0.0.0.0"]

# ══════════════════════════════════════
# GITHUB UPDATE LOGIC
# ══════════════════════════════════════
def run_git_update():
    try:
        # Povlačenje koda s GitHub-a i ažuriranje ovisnosti
        subprocess.run(["git", "pull"], check=True, timeout=60)
        subprocess.run(["pip", "install", "-r", "requirements.txt"], timeout=60)
        return "✅ Sustav ažuriran s GitHub-a. Restartaj Atlas za primjenu."
    except Exception as e:
        return f"❌ Greška pri ažuriranju: {str(e)[:50]}"

# ══════════════════════════════════════
# TERMUX API & METRICS
# ══════════════════════════════════════
def get_metrics():
    try:
        bat_res = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=1)
        bat_str = "N/A"
        if bat_res.returncode == 0:
            b_data = json.loads(bat_res.stdout)
            bat_p = b_data.get("percentage", 0)
            status = "⚡" if b_data.get("status") != "DISCHARGING" else "🔋"
            bat_str = f"{status}{bat_p}"
        mem_res = subprocess.run(["free", "-m"], capture_output=True, text=True)
        mem_lines = mem_res.stdout.split('\n')
        mem_info = mem_lines[1].split()
        total, used = int(mem_info[1]), int(mem_info[2])
        mem_p = round((used / total) * 100, 1)
        return {"cpu": bat_str, "mem": mem_p}
    except: return {"cpu": "!", "mem": "!"}

# ══════════════════════════════════════
# DATABASE & TOKEN MGMT
# ══════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, data TEXT)")
        await db.commit()

async def save_msg(role: str, content: str):
    short = str(content)[:500]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO memory (role, content, timestamp) VALUES (?,?,?)", (role, short, str(datetime.now())))
        await db.execute("DELETE FROM memory WHERE id NOT IN (SELECT id FROM memory ORDER BY id DESC LIMIT 30)")
        await db.commit()

async def get_history(limit: int = 8) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT ?", (limit,)) as c:
            rows = await c.fetchall()
    return [{"role": r, "content": cnt} for r, cnt in reversed(rows)]

async def clear_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM memory"); await db.commit()

def trim_to_limit(messages: list, limit: int = 4000) -> list:
    count = sum(len(str(m.get("content", ""))) for m in messages) // 4
    if count <= limit: return messages
    sys, rest = [m for m in messages if m["role"] == "system"], [m for m in messages if m["role"] != "system"]
    last = rest[-1:] if rest else []
    hist = rest[:-1]
    while hist and (sum(len(str(m.get("content", ""))) for m in sys+hist+last)//4) > limit: hist = hist[2:]
    return sys + hist + last

# ══════════════════════════════════════
# SMART PROFILE & DETECTION
# ══════════════════════════════════════
PROFILE_TRIGGERS = ["zovem se", "moje ime", "radim na", "volim", "preferiram", "projekt", "koristim", "my name", "i am", "i work", "i like"]

async def update_profile(user_msg: str):
    if not any(k in user_msg.lower() for k in PROFILE_TRIGGERS): return
    prompt = f"Extract user info as JSON only. No markdown. Schema: {{\"name\":\"\",\"preferences\":[],\"projects\":[]}} Message: {user_msg[:200]}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json={"model": GROQ_MODELS[0], "messages": [{"role": "user", "content": prompt}], "temperature": 0.1})
            raw = re.sub(r"```json?", "", r.json()["choices"][0]["message"]["content"]).replace("```", "").strip()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO profile VALUES (1,?)", (json.dumps(json.loads(raw)),)); await db.commit()
    except: pass

async def get_profile() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT data FROM profile WHERE id=1") as c: row = await c.fetchone()
        return json.loads(row[0]) if row else {}
    except: return {}

def detect_language(text: str) -> str:
    hr = sum(1 for w in ["što", "kako", "zašto", "jer", "imam", "mogu"] if w in text.lower())
    en = sum(1 for w in ["what", "how", "why", "because", "have", "can"] if w in text.lower())
    return "en" if en > hr else "hr"

def detect_mode(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ["bug", "kod", "python", "code"]): return "code"
    if any(k in m for k in ["zašto", "objasni", "sto je", "explain"]): return "analysis"
    if any(k in m for k in ["vijesti", "danas", "news"]): return "search"
    if re.search(r'https?://', m): return "url"
    return "fast"

def extract_urls(text: str) -> list:
    return [u for u in re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text) if not any(b in u for b in URL_BLACKLIST)]

async def read_url(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if "pdf" in r.headers.get("content-type", "").lower(): return "[PDF sadržaj]"
            text = re.sub(r'<[^>]+>', ' ', r.text); return re.sub(r'\s+', ' ', text).strip()[:3000]
    except: return "[Greška pri čitanju]"

def _web_search(query: str, news: bool = False) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.news(query, max_results=4)) if news else list(ddgs.text(query, max_results=4))
            return "\n".join(f"• {r.get('title')}: {r.get('body', r.get('snippet'))[:150]}" for r in res)
    except: return ""

def run_backup(filepath: str = "") -> str:
    try:
        subprocess.run(["python", "cloud_backup.py"], check=True, timeout=120)
        return "Backup završen — Google Cloud sinkroniziran."
    except: return "Backup greška."

def build_system(profile: dict, mode: str, lang: str = "hr", media_mode: str = "text") -> str:
    l_rule = "Respond in English." if lang == "en" else "Hrvatski jezik. BEZ ijekavice."
    return f"Ti si ATLAS — napredan AI sustav.{f' MOD: {media_mode.upper()}.' if media_mode != 'text' else ''}\nJEZIK: {l_rule}\nKARAKTER: Iskren. Bez laskanja.\nKod u blokovima."

# ══════════════════════════════════════
# AI ENGINE
# ══════════════════════════════════════
async def call_groq(messages: list, temp: float) -> str | None:
    global _groq_model
    messages = trim_to_limit(messages, 4000)
    order = ([_groq_model] + [m for m in GROQ_MODELS if m != _groq_model]) if _groq_model else GROQ_MODELS
    async with httpx.AsyncClient(timeout=40) as client:
        for model in order:
            try:
                r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json={"model": model, "messages": messages, "temperature": temp, "max_tokens": 900})
                if r.status_code == 200: _groq_model = model; return r.json()["choices"][0]["message"]["content"]
            except: continue
    return None

async def call_gemini(messages: list) -> str | None:
    global _gemini_model
    prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)[-15000:]
    order = ([_gemini_model] + [m for m in GEMINI_MODELS if m != _gemini_model]) if _gemini_model else GEMINI_MODELS
    async with httpx.AsyncClient(timeout=40) as client:
        for model in order:
            try:
                r = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}", json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200: _gemini_model = model; return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except: continue
    return None

async def call_ai(messages: list, mode: str = "fast") -> tuple:
    temp = {"fast": 0.3, "analysis": 0.2, "creative": 0.7, "code": 0.1, "search": 0.3}.get(mode, 0.3)
    out = await call_groq(messages, temp)
    if out: return out, _groq_model
    out = await call_gemini(messages)
    return (out, _gemini_model) if out else ("Oba AI servisa nedostupna.", "ERROR")

async def call_vision(image_data: str, prompt: str) -> tuple:
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json={"model": GROQ_VISION_MODELS[0], "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data}},{"type": "text", "text": prompt or "Analiziraj."}]}]})
            if r.status_code == 200: return r.json()["choices"][0]["message"]["content"], "GROQ VISION"
    except: pass
    return "Vision nedostupan.", "ERROR"

# ══════════════════════════════════════
# STANDALONE APP ROUTES
# ══════════════════════════════════════
@app.get("/manifest.json")
async def manifest():
    return {
        "name": "ATLAS OS", "short_name": "ATLAS", "start_url": "/", "display": "standalone",
        "background_color": "#000000", "theme_color": "#0ea5e9",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/714/714390.png", "sizes": "512x512", "type": "image/png"}]
    }

@app.get("/sw.js")
async def sw():
    content = """
    self.addEventListener('install', (e) => { self.skipWaiting(); });
    self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
    self.addEventListener('fetch', (e) => {});
    """
    return HTMLResponse(content=content, media_type="application/javascript")

# ══════════════════════════════════════
# UI
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
.sb{position:fixed;top:0;left:0;width:265px;height:100%;background:rgba(4,8,18,.98);border-right:1px solid var(--br);z-index:200;transform:translateX(-100%);transition:transform .26s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;backdrop-filter:blur(20px)}
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
.met{font-family:'Orbitron';font-size:9px;color:var(--mu);letter-spacing:.05em}
.met span{color:var(--acc)}
.hdr-r{margin-left:auto;display:flex;align-items:center;gap:6px}
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
.mbtn{display:flex;align-items:center;gap:5px;padding:6px 11px;border-radius:7px;border:1px solid var(--br);background:rgba(255,255,255,.02);color:var(--mu);font-size:11px;cursor:pointer;white-space:nowrap;transition:all .13s;font-family:'Syne'}
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
  <div class="sb-hd">
    <div class="sb-logo">ATLAS</div>
    <div class="sb-sub">OS v15.0 · IMAGO</div>
  </div>
  <div class="sb-bd">
    <div class="sb-sec">Sesija</div>
    <div class="si" onclick="newSess()">✦ &nbsp;Nova sesija</div>
    <div class="si" onclick="doBackup()">☁ &nbsp;Cloud Backup (sve)</div>
    <div class="si gh" onclick="doGitUpdate()">🐙 &nbsp;GitHub Update</div>
    <div class="si rd" onclick="doClear()">⚠ &nbsp;Obriši memoriju</div>
    <div class="sb-sec">Multimedija</div>
    <div class="si act" id="m-text" onclick="setMod('text')">📝 &nbsp;Tekst</div>
    <div class="si vm"  id="m-video" onclick="setMod('video')">🎬 &nbsp;Video obrada</div>
    <div class="si am"  id="m-audio" onclick="setMod('audio')">🎵 &nbsp;Audio / Glazba</div>
    <div class="si pm"  id="m-photo" onclick="setMod('photo')">📷 &nbsp;Foto / Slika</div>
  </div>
  <div class="sb-ft">ATLAS AI OS · GitHub Update Enabled</div>
</aside>
<header class="hdr">
  <button onclick="openSb()" style="background:none;border:none;color:var(--acc);font-size:23px;cursor:pointer;line-height:1">☰</button>
  <div>
    <div class="hdr-logo">ATLAS // IMAGO</div>
    <div class="hdr-sub" id="mlabel">Tekst mod</div>
  </div>
  <div class="met">CPU <span id="cpu">—</span>% &nbsp;RAM <span id="mem">—</span>%</div>
  <div class="hdr-r">
    <div class="modp" id="modp">FAST</div>
    <div class="mpill" id="mpill">—</div>
    <div class="wdot" id="wdot"></div>
  </div>
</header>
<div class="mbar" id="mbar"></div>
<div class="chat" id="chat">
  <div class="msg"><div class="mm"><span class="mw atlas">Atlas</span></div><div>Sustav aktivan. Memorija ucitana. GitHub povezan.</div><div class="mt">BOOT · v15.0</div></div>
</div>
<div id="find">📎 <span id="fname"></span><span onclick="clrF()" style="cursor:pointer;color:var(--rd);margin-left:5px">✕</span></div>
<div class="izone">
  <div class="ibox" id="ibox">
    <input type="file" id="fi" style="display:none" onchange="onFile(this)" accept="image/*,text/*,.py,.js,.json,.csv,.md,.pdf">
    <button class="ibtn" onclick="document.getElementById('fi').click()">📎</button>
    <textarea id="inp" placeholder="Pitaj Atlas..." rows="1" oninput="ar(this)" onkeydown="hk(event)"></textarea>
    <button class="ibtn sbtn" id="sbtn" onclick="send()">➤</button>
  </div>
</div>
<script>
if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js'); }
let ws, pF=null, typEl=null, cMod='text';
const MODS = { text: {label:'Tekst mod', ph:'Pitaj Atlas...', cls:''}, video: {label:'Video obrada', ph:'Montaza, formati, alati...', cls:'video', tools:['🎬 Montaza','⚙️ Kodeci','📐 Rezolucija','🎞️ FPS','🔊 Audio sync','📤 Export']}, audio: {label:'Audio / Glazba', ph:'Glazba, zvuk, DAW, mix...', cls:'audio', tools:['🎵 Mix','🎤 Snimanje','🔉 EQ','🥁 Ritam','📻 Format','💿 Export']}, photo: {label:'Foto / Slika', ph:'Fotografija, editing, filteri...', cls:'photo', tools:['🖼️ Edit','🎨 Boja','✂️ Crop','💡 Ekspozicija','🔲 Kompozicija','📁 Export']}, };
function setMod(m) { cMod = m; const cfg = MODS[m]; ['text','video','audio','photo'].forEach(x => { document.getElementById('m-'+x).classList.toggle('act', x===m); }); document.getElementById('mlabel').textContent = cfg.label; document.getElementById('inp').placeholder = cfg.ph; const mp = document.getElementById('modp'); mp.textContent = m.toUpperCase(); mp.className = 'modp ' + (m!=='text' ? m : ''); const ib = document.getElementById('ibox'); ib.className = 'ibox ' + cfg.cls; document.getElementById('sbtn').className = 'ibtn sbtn ' + cfg.cls; const bar = document.getElementById('mbar'); if (cfg.tools) { bar.className = 'mbar show ' + m; bar.innerHTML = cfg.tools.map(t=>`<button class="mbtn" onclick="qp('${t}')">${t}</button>`).join(''); } else { bar.className = 'mbar'; bar.innerHTML = ''; } if(ws&&ws.readyState===1) ws.send(JSON.stringify({type:'media_mode',mode:m})); closeSb(); }
function qp(t) { const clean = t.replace(/\p{Emoji}/gu,'').trim(); document.getElementById('inp').value = clean + ': '; document.getElementById('inp').focus(); }
function conn() { ws = new WebSocket('ws://'+location.host+'/ws'); ws.onopen = ()=>setWs(true); ws.onclose = ()=>{setWs(false);setTimeout(conn,2500)}; ws.onmessage = e=>{ const d = JSON.parse(e.data); if(d.type==='metrics'){ document.getElementById('cpu').textContent=d.data.cpu; document.getElementById('mem').textContent=d.data.mem; return; } rmTyp(); if(d.action==='reload'){location.reload();return} if(d.message) addMsg('atlas',d.message,d.model,d.tags||[],d.mode||''); if(d.error) addMsg('error',d.error,null,[]); }; }
function setWs(on){document.getElementById('wdot').className='wdot '+(on?'on':'off')}
function setPill(model){ if(!model)return; const el=document.getElementById('mpill'); el.textContent=model.split(' ')[0]; const m=model.toLowerCase(); el.className='mpill '+(m.includes('gemini')?'gemini':m.includes('error')?'error':'groq'); }
function addMsg(type,text,model,tags,mode){ const chat=document.getElementById('chat'); const now=new Date().toLocaleTimeString('hr',{hour:'2-digit',minute:'2-digit'}); const d=document.createElement('div'); d.className='msg '+(type==='atlas'?'':type); const who=type==='atlas'?'Atlas':type==='error'?'Greška':'Ti'; const wc=type==='atlas'?'atlas':type==='error'?'err':'user'; let meta=`<div class="mm"><span class="mw ${wc}">${who}</span>`; if(model){const mc=model.toLowerCase().includes('gemini')?'gemini':'groq';meta+=`<span class="tg ${mc}">${model.split(' ')[0]}</span>`;setPill(model);} const showTags=['web','url','pdf','vision','cloud','code','analysis','video','audio','photo']; showTags.forEach(t=>{if(tags.includes(t))meta+=`<span class="tg ${t}">${t.toUpperCase()}</span>`;}); meta+='</div>'; if(mode&&!['fast','text','url'].includes(mode))document.getElementById('modp').textContent=mode.toUpperCase(); d.innerHTML=meta+`<div>${esc(text)}</div><div class="mt">${now}</div>`; chat.appendChild(d);chat.scrollTop=chat.scrollHeight; }
function showTyp(){ const chat=document.getElementById('chat'); typEl=document.createElement('div');typEl.className='msg'; typEl.innerHTML=`<div class="mm"><span class="mw atlas">Atlas</span></div><div class="dots"><span></span><span></span><span></span></div>`; chat.appendChild(typEl);chat.scrollTop=chat.scrollHeight; }
function rmTyp(){if(typEl){typEl.remove();typEl=null}}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>'); }
function ar(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px'}
function hk(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function send(){ const inp=document.getElementById('inp'); const txt=inp.value.trim(); if(!txt&&!pF)return; const chat=document.getElementById('chat'); const d=document.createElement('div');d.className='msg user'; const badge=pF?`<div class="fbg">📎 ${pF.name}</div>`:''; d.innerHTML=`<div class="mm"><span class="mw user">Ti</span></div>${badge}<div>${esc(txt)}</div>`; chat.appendChild(d);chat.scrollTop=chat.scrollHeight; showTyp(); ws.send(JSON.stringify({text:txt,file:pF,mediaMode:cMod})); inp.value='';inp.style.height='auto';clrF(); }
function onFile(input){ const file=input.files[0];if(!file)return; const reader=new FileReader(); reader.onload=e=>{ pF={name:file.name,type:file.type,data:e.target.result,isImage:file.type.startsWith('image/')}; document.getElementById('find').style.display='block'; document.getElementById('fname').textContent=file.name; }; if(file.type.startsWith('image/'))reader.readAsDataURL(file); else reader.readAsText(file); }
function clrF(){pF=null;document.getElementById('find').style.display='none';document.getElementById('fi').value=''}
function openSb(){document.getElementById('sb').classList.add('open');document.getElementById('ov').classList.add('on')}
function closeSb(){document.getElementById('sb').classList.remove('open');document.getElementById('ov').classList.remove('on')}
function newSess(){closeSb();location.reload()}
function doBackup(){closeSb();showTyp();ws.send('__BACKUP__')}
function doGitUpdate(){closeSb();showTyp();ws.send('__GIT_UPDATE__')}
function doClear(){if(confirm('Obrisati memoriju?')){closeSb();ws.send('__CLEAR__')}}
setInterval(()=>{if(ws&&ws.readyState===1)ws.send('__METRICS__')},3000);
const cvs=document.getElementById('cvs'),ctx=cvs.getContext('2d'); let pts=[],W,H; function resize(){W=cvs.width=window.innerWidth;H=cvs.height=window.innerHeight} function spawn(x,y,n=12){for(let i=0;i<n;i++)pts.push({x,y,vx:(Math.random()-.5)*4,vy:(Math.random()-.5)*4,l:1})} function draw(){ ctx.clearRect(0,0,W,H); pts=pts.filter(p=>p.l>0); pts.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.l-=.018;ctx.beginPath();ctx.arc(p.x,p.y,1.8,0,Math.PI*2);ctx.fillStyle=`rgba(14,165,233,${p.l})`;ctx.fill()}); requestAnimationFrame(draw); } cvs.addEventListener('mousedown',e=>spawn(e.clientX,e.clientY)); cvs.addEventListener('touchstart',e=>{e.preventDefault();spawn(e.touches[0].clientX,e.touches[0].clientY)},{passive:false}); window.onresize=resize;resize();draw(); conn();
</script>
</body>
</html>"""

# ══════════════════════════════════════
# ROUTES
# ══════════════════════════════════════
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
                await websocket.send_json({"type": "metrics", "data": m})
                continue
            if raw == "__CLEAR__":
                await clear_db(); await websocket.send_json({"action": "reload"}); continue
            if raw == "__BACKUP__":
                msg = await loop.run_in_executor(None, run_backup, "")
                await websocket.send_json({"message": msg, "model": "SYSTEM", "tags": ["cloud"], "mode": "fast"})
                continue
            if raw == "__GIT_UPDATE__":
                msg = await loop.run_in_executor(None, run_git_update)
                await websocket.send_json({"message": msg, "model": "GITHUB", "tags": ["cloud"], "mode": "fast"})
                continue
            try: data = json.loads(raw)
            except: data = {"text": raw}
            if data.get("type") == "media_mode": session_media = data.get("mode", "text"); continue
            user_msg, file_data, media_mode = data.get("text", "").strip(), data.get("file"), data.get("mediaMode", session_media)
            if not user_msg and not file_data: continue
            if user_msg: asyncio.create_task(update_profile(user_msg))
            lang = detect_language(user_msg) if user_msg else "hr"
            if any(k in user_msg.lower() for k in ["prenesi na oblak", "upload na oblak", "backup"]):
                msg = await loop.run_in_executor(None, run_backup, parse_backup_command(user_msg))
                await websocket.send_json({"message": msg, "model": "SYSTEM", "tags": ["cloud"], "mode": "fast"})
                continue
            if file_data and file_data.get("isImage"):
                out, model = await call_vision(file_data["data"], user_msg)
                await save_msg("user", f"[SLIKA] {user_msg[:100]}"); await save_msg("assistant", out)
                await websocket.send_json({"message": out, "model": model, "tags": ["vision"], "mode": "analysis"})
                continue
            mode, tags, extra_ctx = detect_mode(user_msg), [], ""
            urls = extract_urls(user_msg) if user_msg else []
            if urls:
                c_list = []
                for u in urls[:2]:
                    cont = await read_url(u)
                    c_list.append(f"[URL: {u}]\n{cont[:2000]}")
                    tags.append("pdf" if "pdf" in u.lower() else "url")
                extra_ctx = "\n\n" + "\n\n".join(c_list); mode = "url"
            elif mode == "search":
                web = await loop.run_in_executor(None, _web_search, user_msg, "news" in user_msg.lower())
                if web: extra_ctx = f"\n\n[WEB]\n{web}"; tags.append("web")
            if file_data and not file_data.get("isImage"):
                extra_ctx += f"\n\n[FAJL]\n{str(file_data.get('data',''))[:2000]}"; tags.append("url")
            profile, history = await get_profile(), await get_history(6)
            messages = ([{"role": "system", "content": build_system(profile, mode, lang, media_mode)}] + history + [{"role": "user", "content": f"{user_msg}\n{extra_ctx[:2500]}"}])
            out, model = await call_ai(messages, mode)
            await save_msg("user", user_msg[:300]); await save_msg("assistant", out[:500])
            if media_mode != "text": tags.append(media_mode)
            await websocket.send_json({"message": out, "model": model, "tags": tags, "mode": mode})
        except WebSocketDisconnect: break
        except Exception as e:
            try: await websocket.send_json({"error": str(e)[:100], "tags": [], "mode": "fast"})
            except: break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
