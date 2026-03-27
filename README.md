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

## ⚖️ Licenca
MIT License - vidi [LICENSE](LICENSE) datoteku za detalje.
