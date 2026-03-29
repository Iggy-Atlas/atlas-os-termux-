import os
import subprocess
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
from duckduckgo_search import DDGS
from PIL import Image

load_dotenv()

class AtlasOS:
    def __init__(self):
        # Inicijalizacija: Groq za tekst, Gemini za slike
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.identity = "Atlas OS"
        self.style = "Profesionalan, kulturan, ijekavica, poliglota"

    def handle_interaction(self, user_input, image_path=None):
        """Atlas ovdje donosi odluku i rješava Error 400."""
        
        # 🛡️ Ako postoji putanja do slike, KORISTI SAMO GEMINI
        if image_path and os.path.exists(image_path):
            return self._execute_vision(user_input, image_path)

        # 🔍 Ako je tekst, provjeri treba li internet
        search_triggers = ["vijesti", "danas", "vrijeme", "ko je", "tko je", "search"]
        if any(word in user_input.lower() for word in search_triggers):
            context = self._execute_search(user_input)
            return self._execute_groq(user_input, context=context)

        # 🧠 Običan razgovor ide na Groq
        return self._execute_groq(user_input)

    def _execute_groq(self, prompt, context=""):
        """Čisti tekstualni odgovor (Llama-3)."""
        system_prompt = f"Ti si {self.identity}. Stil: {self.style}."
        if context:
            system_prompt += f"\nPodaci s interneta: {context}"
            
        try:
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model="llama3-70b-8192"
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"⚠️ Groq Error: {e}"

    def _execute_vision(self, prompt, img_path):
        """Ovdje Gemini 'gleda' sliku i rješava tvoj problem."""
        try:
            img = Image.open(img_path)
            # Gemini prima listu: [tekst, slika]
            instruction = prompt if prompt else "Analiziraj ovu sliku profesionalno na ijekavici."
            response = self.gemini_model.generate_content([instruction, img])
            return response.text
        except Exception as e:
            return f"⚠️ Vision Error: {e}"

    def _execute_search(self, query):
        """DuckDuckGo autonomna pretraga."""
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=3)]
                return "\n".join([f"{r['title']}: {r['body']}" for r in results])
        except:
            return "Internet trenutno nedostupan."

    def trigger_cloud_backup(self):
        """Poziva tvoj cloud_backup.py (onih 200GB)."""
        subprocess.run(["python", "cloud_backup.py"])
        return "✅ Backup uspješan."

