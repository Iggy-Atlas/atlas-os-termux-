import os, uvicorn, httpx, json, asyncio, subprocess, re, base64
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
GROQ_VISION_MODEL = "llama-3.2-11b-vision-preview"
GEMINI_VISION_MODEL = "gemini-1.5-flash"

_groq_model, _gemini_model = None, None
URL_BLACKLIST = ["api.groq.com", "googleapis.com", "generativelanguage", "openai.com", "fonts.googleapis", "cdnjs.cloudflare", "anthropic.com", "localhost", "127.0.0.1", "0.0.0.0"]

# ══════════════════════════════════════
# ENGINES: VISION (Dual Core Bypass)
# ══════════════════════════════════════
async def call_vision(image_data: str, prompt: str) -> tuple:
    try:
        b64 = image_data.split(",")[-1] if "," in image_data else image_data
        async with httpx.AsyncClient(timeout=40) as client:
            payload = {
                "model": GROQ_VISION_MODEL,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt or "Opiši sliku detaljno."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}],
                "max_tokens": 1024
            }
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=payload)
            if r.status_code == 200: return r.json()["choices"][0]["message"]["content"], "GROQ VISION"
    except: pass

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt or "Analiziraj sliku."}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}]}
            r = await client.post(url, json=payload)
            if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"], "GEMINI VISION"
    except: pass
    return "Vision senzori nedostupni (API Limit).", "ERROR"

# ══════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════
async def _wiki_search(query: str, lang: str = "hr") -> str:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200: return f"📚 [WIKIPEDIA]: {r.json().get('extract', '')}"
    except: pass
    return ""

def get_metrics():
    try:
        bat_res = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=1)
        bat_str = "N/A"
        if bat_res.returncode == 0:
            b = json.loads(bat_res.stdout)
            bat_str = f"{'⚡' if b.get('status') != 'DISCHARGING' else '🔋'}{b.get('percentage', 0)}"
        mem_res = subprocess.run(["free", "-m"], capture_output=True, text=True)
        mem_info = mem_res.stdout.split('\n')[1].split()
        mem_p = round((int(mem_info[2]) / int(mem_info[1])) * 100, 1)
        return {"cpu": bat_str, "mem": mem_p}
    except: return {"cpu": "!", "mem": "!"}

def run_git_update():
    try:
        subprocess.run(["git", "pull"], check=True, timeout=60)
        return "✅ Ažurirano. Restartaj Atlas."
    except: return "❌ Greška ažuriranja."

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, data TEXT)")
        await db.commit()

async def save_msg(role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO memory (role, content, timestamp) VALUES (?,?,?)", (role, str(content)[:500], str(datetime.now())))
        await db.commit()

async def get_history(limit=8):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT ?", (limit,)) as c:
            rows = await c.fetchall()
        return [{"role": r, "content": cnt} for r, cnt in reversed(rows)]

async def get_profile() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT data FROM profile WHERE id=1") as c: row = await c.fetchone()
        return json.loads(row[0]) if row else {}
    except: return {}

def detect_language(text):
    hr = sum(1 for w in ["što", "kako", "imam", "mogu"] if w in text.lower())
    en = sum(1 for w in ["what", "how", "have", "can"] if w in text.lower())
    return "en" if en > hr else "hr"

def detect_mode(msg):
    m = msg.lower()
    if any(k in m for k in ["kod", "python", "code"]): return "code"
    if any(k in m for k in ["tko je", "što je", "wiki"]): return "wiki"
    return "fast"

def build_system(profile, media_mode, lang):
    l_rule = "Respond in English." if lang == "en" else "Hrvatski jezik. BEZ ijekavice."
    return f"Ti si ATLAS — napredan AI sustav. MOD: {media_mode.upper()}.\nJEZIK: {l_rule}\nMOĆI: VISION, WIKIPEDIA.\nKARAKTER: Iskren."

async def call_ai(messages):
    global _groq_model
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", 
                                 headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, 
                                 json={"model": GROQ_MODELS[0], "messages": messages, "temperature": 0.3})
            if r.status_code == 200: 
                _groq_model = GROQ_MODELS[0]
                return r.json()["choices"][0]["message"]["content"], _groq_model
    except: pass
    
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODELS[0]}:generateContent?key={GEMINI_API_KEY}"
            r = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], GEMINI_MODELS[0]
    except: pass
    return "AI servisi nedostupni.", "ERROR"

# ══════════════════════════════════════
# UI - CIJELI ORIGINALNI HTML (Preko 600 linija)
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
const MODS = { text: {label:'Tekst mod', ph:'Pitaj Atlas...', cls:''}, video: {label:'Video obrada', ph:'Montaza, formati, alati...', cls:'video', tools:['🎬 Montaza','⚙️ Kodeci','📐 Rezolucija','🎞️ FPS','🔊 Audio sync','📤 Export']}, audio: {label:'Audio / Glazba', ph:'Glazba, zvuk, DAW, mix...', cls:'audio', tools:['🎵 Mix','🎤 Snimanje','🔉 EQ','🥁 Ritam','📻 Format','CDC Export']}, photo: {label:'Foto / Slika', ph:'Fotografija, editing, filteri...', cls:'photo', tools:['🖼️ Edit','🎨 Boja','✂️ Crop','💡 Ekspozicija','🔲 Kompozicija','📁 Export']}, };
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
# FINAL ENDPOINTS & WEBSOCKET
# ══════════════════════════════════════
@app.get("/")
async def home():
    return HTMLResponse(HTML)

@app.get("/manifest.json")
async def manifest():
    return {"name": "ATLAS OS", "short_name": "ATLAS", "start_url": "/", "display": "standalone", "background_color": "#000", "theme_color": "#0ea5e9", "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/714/714390.png", "sizes": "512x512", "type": "image/png"}]}

@app.get("/sw.js")
async def sw():
    return HTMLResponse(content="self.addEventListener('install', e=>self.skipWaiting()); self.addEventListener('activate', e=>e.waitUntil(clients.claim())); self.addEventListener('fetch', e=>{});", media_type="application/javascript")

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    await init_db()
    session_media = "text"
    while True:
        try:
            raw = await websocket.receive_text()
            if raw == "__METRICS__":
                await websocket.send_json({"type": "metrics", "data": get_metrics()}); continue
            if raw == "__CLEAR__":
                await clear_db(); await websocket.send_json({"action": "reload"}); continue
            
            data = json.loads(raw)
            user_msg = data.get("text", "").strip()
            file_data = data.get("file")
            media_mode = data.get("mediaMode", session_media)

            if file_data and (file_data.get("isImage") or "image" in file_data.get("type", "")):
                out, model = await call_vision(file_data["data"], user_msg)
                await websocket.send_json({"message": out, "model": model, "tags": ["vision"], "mode": "photo"})
                continue

            mode = detect_mode(user_msg)
            tags = []
            extra_ctx = ""
            lang = detect_language(user_msg) if user_msg else "hr"

            if mode == "wiki":
                wiki = await _wiki_search(user_msg.lower().replace("tko je","").strip(), lang)
                if wiki: extra_ctx = f"\n\n{wiki}"; tags.append("web")

            profile = await get_profile()
            history = await get_history()
            messages = [{"role": "system", "content": build_system(profile, media_mode, lang)}] + history + [{"role": "user", "content": user_msg + extra_ctx}]
            
            out, model = await call_ai(messages)
            await save_msg("user", user_msg); await save_msg("assistant", out)
            await websocket.send_json({"message": out, "model": model, "tags": tags, "mode": mode})
            
        except WebSocketDisconnect: break
        except Exception as e: await websocket.send_json({"error": str(e)[:100]}); break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
