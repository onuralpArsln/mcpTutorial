import sys
import os
import json
import time
import yaml
import requests
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# 1. AYARLARI YÜKLE
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))

HISTORY_DIR = os.path.join(root_dir, "backup", "chat_history")
INTENTS_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "intents.yaml")

# Ollama Ayarları
OLLAMA_BASE_URL = os.getenv("OLLAMA_SMALL_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_SMALL_MODEL", "llama3.2:3b")

class QualityAssuranceAgent(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.intents_context = self._load_intents()
        print(f"✅ Intent tanımları yüklendi: {INTENTS_PATH}")

    def _load_intents(self):
        try:
            with open(INTENTS_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"❌ Intent dosyası okunamadı: {e}")
            return ""

    def analyze_intent(self, query):
        """Ollama kullanarak intent analizi yapar."""
        prompt = f"""Aşağıdaki niyet (intent) tanımlarına göre, kullanıcının sorusunun niyetini belirle.
SADECE ve SADECE niyet ismini (key) döndür. Başka hiçbir açıklama yapma.

NİYET TANIMLARI:
{self.intents_context}

KULLANICI SORUSU: {query}

NİYET:"""
        
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            if response.status_code == 200:
                intent = response.json().get("response", "").strip().lower()
                # Temizlik (noktalama işaretlerini kaldır)
                intent = "".join(c for c in intent if c.isalnum() or c == "_")
                return intent
        except Exception as e:
            print(f"❌ Ollama hatası: {e}")
        return "unknown"

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return
        
        # Dosya yazma işleminin bitmesini bekle
        time.sleep(0.5)
        self.process_history_file(event.src_path)

    def process_history_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return

            updated = False
            for msg in data:
                # Sadece kullanıcı mesajlarını ve intent'i olmayanları işle
                if msg.get("role") == "user" and "intent" not in msg:
                    query = msg.get("content", "")
                    print(f"🔍 [ANALİZ] Yeni soru tespit edildi: {query[:50]}...")
                    
                    intent = self.analyze_intent(query)
                    msg["intent"] = intent
                    print(f"🎯 [INTENT] Tespit edilen niyet: {intent}")
                    updated = True
            
            if updated:
                # Kendi yazdığımız dosyanın tekrar event tetiklemesini önlemek için
                # kısa bir süre watchdog'u bypass etmiyoruz ama içeriği kontrol ediyoruz (intent varsa dokunmuyoruz)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"💾 [KAYIT] {os.path.basename(file_path)} güncellendi.")
                
        except Exception as e:
            print(f"❌ Dosya işleme hatası: {e}")

def main():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR, exist_ok=True)

    event_handler = QualityAssuranceAgent()
    observer = Observer()
    observer.schedule(event_handler, HISTORY_DIR, recursive=False)
    
    print("=" * 50)
    print(f"🚀 Quality Assurance Agent (Ollama: {OLLAMA_MODEL})")
    print(f"📂 İzlenen Klasör: {HISTORY_DIR}")
    print("=" * 50)
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 QA Agent durduruluyor...")
    observer.join()

if __name__ == "__main__":
    main()
