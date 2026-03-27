import os, uvicorn, httpx, json, sqlite3, asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
app = FastAPI()

def init_db():
    conn = sqlite3.connect("database.db")
    conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)")
    conn.commit(); conn.close()

def save_to_db(role, content):
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO memory (role, content, timestamp) VALUES (?, ?, ?)", (role, str(content), str(datetime.now())))
    conn.commit(); conn.close()

def get_recent_context(limit=3): # Smanjen limit na 3 za uštedu tokena
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM memory ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall(); conn.close()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

html_content = r"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>ATLAS OS</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@800&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root { --bg: #030508; --accent: #38bdf8; --text: #e2e8f0; --border: rgba(56, 189, 248, 0.2); --sidebar-w: 280px; }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body { height: 100dvh; background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif; overflow: hidden; position: fixed; width: 100%; }
  #neural-canvas { position: fixed; inset: 0; z-index: 1; pointer-events: none; }
  .grid-overlay { position: fixed; inset: 0; z-index: 2; pointer-events: none; background-image: linear-gradient(rgba(56,189,248,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.02) 1px, transparent 1px); background-size: 45px 45px; }
  .sidebar { position: fixed; top: 0; left: 0; width: var(--sidebar-w); height: 100%; background: #050a12; border-right: 1px solid var(--border); z-index: 1001; transition: 0.3s ease; transform: translateX(-100%); }
  .sidebar.open { transform: translateX(0); }
  .sidebar-overlay { display: none; position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.6); }
  .sidebar-overlay.visible { display: block; }
  .logo-font { font-family: 'Orbitron', sans-serif; letter-spacing: 5px; font-weight: 800; color: #fff; }
  .header { padding: 15px; background: rgba(3,5,8,0.9); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; z-index: 10; }
  .chat-area { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; position: relative; z-index: 5; }
  .msg { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 15px; background: rgba(10, 20, 30, 0.8); border: 1px solid var(--border); align-self: flex-start; word-wrap: break-word; }
  .msg.user { align-self: flex-end; border-color: rgba(129,140,248,0.4); background: rgba(129,140,248,0.1); }
  .input-zone { padding: 15px; background: #030508; border-top: 1px solid var(--border); z-index: 10; }
  .input-wrapper { display: flex; align-items: center; gap: 10px; background: #0a0f18; border: 1.5px solid var(--accent); border-radius: 16px; padding: 8px 12px; max-width: 650px; margin: 0 auto; position: relative; }
  #chat-input { flex: 1; background: transparent; border: none; outline: none; color: #fff; font-size: 16px; font-family: inherit; resize: none; min-height: 24px; }
  #file-info { position: absolute; top: -25px; left: 15px; font-size: 10px; color: var(--accent); display: none; }
  .send-btn { background: var(--accent); border: none; width: 38px; height: 38px; border-radius: 12px; color: #000; cursor: pointer; display: flex; align-items: center; justify-content: center; }
</style>
</head>
<body>
<canvas id="neural-canvas"></canvas>
<div class="grid-overlay"></div>
<div class="sidebar-overlay" id="overlay" onclick="toggleSidebar()"></div>
<div class="app" style="display:flex; flex-direction:column; height:100dvh;">
  <aside class="sidebar" id="sidebar">
    <div style="padding:40px 25px; border-bottom:1px solid var(--border);"><h1 class="logo-font" style="font-size:24px;">ATLAS</h1></div>
    <div style="padding:20px;"><div onclick="location.reload()" style="cursor:pointer; margin-bottom:20px;">✦ NOVA SESIJA</div><div onclick="clearMem()" style="color:#f87171; cursor:pointer;">⚠ OBRIŠI MEMORIJU</div></div>
  </aside>
  <header class="header"><button style="background:none; border:none; color:var(--accent); font-size:28px;" onclick="toggleSidebar()">☰</button><div class="logo-font" style="font-size:18px; color:var(--accent);">ATLAS OS</div><div style="width:30px;"></div></header>
  <div class="chat-area" id="chat-area"></div>
  <div class="input-zone">
    <div class="input-wrapper">
      <div id="file-info"></div>
      <button style="background:none; border:none; color:var(--accent); font-size:24px;" onclick="document.getElementById('file-input').click()">+</button>
      <input type="file" id="file-input" style="display:none" accept="image/*,.txt,.py" onchange="handleFile(this)">
      <textarea id="chat-input" rows="1" placeholder="Pitaj Atlas..."></textarea>
      <button class="send-btn" onclick="sendMessage()">➤</button>
    </div>
  </div>
</div>
<script>
const ws = new WebSocket('ws://' + location.host + '/ws');
const chatArea = document.getElementById('chat-area');
const chatInput = document.getElementById('chat-input');
let pendingFile = null;

ws.onmessage = (e) => {
    const loader = document.getElementById('atlas-loader'); if(loader) loader.remove();
    try {
        const d = JSON.parse(e.data);
        if(d.message) addMessage('assistant', d.message);
        if(d.action === 'reload') location.reload();
    } catch(err) { console.error("Parse Error"); }
};

function addMessage(role, text) {
  const div = document.createElement('div'); div.className = `msg ${role}`;
  if(role === 'loading') div.id = 'atlas-loader';
  div.innerHTML = text.replace(/\n/g, '<br>');
  chatArea.appendChild(div); chatArea.scrollTop = chatArea.scrollHeight;
}

function handleFile(input) {
  const file = input.files[0]; if(!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const isImg = file.type.startsWith('image/');
    pendingFile = { name: file.name, type: file.type, data: e.target.result, isImage: isImg };
    document.getElementById('file-info').innerText = (isImg ? "🖼️ " : "📄 ") + file.name;
    document.getElementById('file-info').style.display = "block";
  };
  if(file.type.startsWith('image/')) reader.readAsDataURL(file); else reader.readAsText(file);
}

function sendMessage() {
  const v = chatInput.value.trim(); if(!v && !pendingFile) return;
  addMessage('user', pendingFile ? `[${pendingFile.name}] ` + v : v);
  addMessage('loading', '<i>Atlas obrađuje...</i>');
  ws.send(JSON.stringify({ text: v, file: pendingFile }));
  chatInput.value = ''; pendingFile = null; document.getElementById('file-info').style.display = "none";
}

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); document.getElementById('overlay').classList.toggle('visible'); }
function clearMem() { if(confirm("Obrisati memoriju?")) ws.send("__CLEAR_MEMORY__"); }
chatInput.onkeydown = (e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } };

const canvas = document.getElementById('neural-canvas'); const ctx = canvas.getContext('2d');
let nodes = [], W, H, mouse = {x: -1000, y: -1000};
function resize() { W=canvas.width=window.innerWidth; H=canvas.height=window.innerHeight; init(); }
function init() { nodes=[]; for(let i=0; i<40; i++) nodes.push({x:Math.random()*W, y:Math.random()*H, vx:(Math.random()-0.5)*0.5, vy:(Math.random()-0.5)*0.5}); }
function draw() {
  ctx.clearRect(0,0,W,H);
  nodes.forEach(n => {
    n.x+=n.vx; n.y+=n.vy; if(n.x<0||n.x>W) n.vx*=-1; if(n.y<0||n.y>H) n.vy*=-1;
    ctx.beginPath(); ctx.arc(n.x,n.y,2,0,Math.PI*2); ctx.fillStyle='rgba(56,189,248,0.3)'; ctx.fill();
    const d = Math.hypot(n.x-mouse.x, n.y-mouse.y);
    if(d<160) { ctx.beginPath(); ctx.moveTo(n.x,n.y); ctx.lineTo(mouse.x,mouse.y); ctx.strokeStyle=`rgba(56,189,248,${0.3*(1-d/160)})`; ctx.stroke(); }
  });
  requestAnimationFrame(draw);
}
window.addEventListener('mousemove', e => { mouse.x=e.clientX; mouse.y=e.clientY; });
window.addEventListener('touchstart', e => { mouse.x=e.touches[0].clientX; mouse.y=e.touches[0].clientY; });
window.onresize=resize; resize(); draw();
</script>
</body>
</html>"""

@app.get("/")
async def get(): return HTMLResponse(html_content)

async def call_groq(model, messages):
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": model, "messages": messages, "temperature": 0.2}
        )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    init_db()
    while True:
        try:
            raw = await websocket.receive_text()
            if raw == "__CLEAR_MEMORY__":
                conn = sqlite3.connect("database.db"); conn.execute("DELETE FROM memory"); conn.commit(); conn.close()
                await websocket.send_json({"action": "reload"}); continue
            
            data = json.loads(raw)
            user_msg = data.get("text", "")
            file_data = data.get("file")
            
            sys_prompt = "Ti si Atlas OS. Pismen hrvatski, bez ijekavice. Budi kratak i precizan."
            
            if file_data and file_data.get("isImage"):
                model = "llama-3.2-11b-vision-preview"
                b64 = file_data['data'].split(",")[1]
                messages = [{"role": "system", "content": sys_prompt},
                            {"role": "user", "content": [{"type": "text", "text": user_msg or "Što je na slici?"},
                             {"type": "image_url", "image_url": {"url": f"data:{file_data['type']};base64,{b64}"}}]}]
            else:
                history = get_recent_context(3) # Minimalni kontekst
                content = f"[FILE: {file_data['name']}]\n{file_data['data']}\n\n{user_msg}" if file_data else user_msg
                save_to_db("user", content)
                messages = [{"role": "system", "content": sys_prompt}] + history + [{"role": "user", "content": content}]

            resp = await call_groq("llama-3.3-70b-versatile", messages)
            
            # FALLBACK: Ako je limit dostignut, pokušaj s manjim modelom
            if resp.status_code == 429:
                print("70B Limit! Prebacujem na 8B...")
                resp = await call_groq("llama-3.1-8b-instant", messages)

            if resp.status_code == 200:
                out = resp.json()['choices'][0]['message']['content']
                save_to_db("assistant", out)
                await websocket.send_json({"message": out})
            else:
                await websocket.send_json({"message": f"API Error ({resp.status_code}): {resp.text[:50]}"})
        except Exception as e: break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
