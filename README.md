# 🛰️ ATLAS OS (v8.3)
**Personal AI Operating System Layer for Android/Termux**

ATLAS OS je napredni, asinkroni AI sloj optimiziran za rad unutar Termux okruženja. Koristi WebSocket arhitekturu za fluidnu komunikaciju i Llama Vision modele za analizu vizualnih podataka.

## ✨ Značajke
- 🧠 **Neural Interaction:** Interaktivni Canvas koji reagira na dodir.
- 🖼️ **Vision Support:** Analiza slika putem Llama-3.2-Vision modela.
- 📂 **File Processing:** Direktno učitavanje i analiza skripti i dokumenata.
- ⚡ **Async Engine:** FastAPI pozadina koja osigurava rad bez latencije.
- 🔒 **Security:** AST Sandbox za sigurnu analizu koda.

## 🛠️ Tehnologije
- **Jezik:** Python 3.13+
- **Backend:** FastAPI, Uvicorn, HTTPX
- **Frontend:** HTML5, CSS3 (Orbitron & Syne fontovi), JavaScript
- **AI jezgra:** Groq API (Llama-3.3-70B & Llama-3.2-11B-Vision)

## 🚀 Instalacija
1. Instaliraj potrebne pakete u Termuxu:
   `pkg install python clang make cmake`
2. Kloniraj repozitorij i instaliraj zavisnosti:
   `pip install -r requirements.txt`
3. Postavi svoj `GROQ_API_KEY` u `.env` datoteku.
4. Pokreni sustav:
   `python main.py`

## 🗺️ Roadmap

Iduće faze razvoja ATLAS OS-a:

- 🤖 **Vision AI Integration (Llama-3.2-Vision)**
  Napredna analiza vizualnih podataka s lokalnim Vision modelima za real-time procesiranje slika unutar Termux okruženja.

- 🔒 **Python Sandbox Executor (Sigurno izvršavanje koda)**
  Sigurna AST-bazirana evaluacija Python koda s ograničenjima izvršavanja i zaštitom od opasnih operacija.

- ☁️ **Google Cloud Backup (rclone integracija)**
  Automatizirana rclone sinhronizacija `database.db` datoteke na Google Drive s 200GB prostora. Skriptu pokreneš sa `python cloud_backup.py`.

## ⚖️ Licenca
MIT License - vidi [LICENSE](LICENSE) datoteku za detalje.