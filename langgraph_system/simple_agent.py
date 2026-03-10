import asyncio
import os
import json
import yaml
import sys
from datetime import datetime
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. AYARLARI YÜKLE
# Dosya yolu langgraph_system altında olacağı için bir üst dizine çıkıyoruz .env için
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))

MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

class SimpleAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_id = os.getenv("BACKUP_MODEL_ID", "gemini-1.5-flash")
        self.client = genai.Client(api_key=self.api_key)
        self.exit_stack = AsyncExitStack()
        self.db_session = None
        self.schema = self._load_schema()

    def _load_schema(self):
        if not os.path.exists(SCHEMA_PATH):
            return "Şema dosyası bulunamadı."
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                return yaml.dump(yaml.safe_load(f), allow_unicode=True)
        except Exception as e:
            return f"Şema okuma hatası: {e}"

    async def connect(self):
        """MCP sunucusuna (Postgres) bağlanır."""
        if self.db_session:
            return True

        if not os.path.exists(MCP_CONFIG_PATH):
            raise FileNotFoundError("mcp_config.json bulunamadı.")

        with open(MCP_CONFIG_PATH, "r") as f:
            mcp_config = json.load(f)

        for name, cfg in mcp_config.get("mcpServers", {}).items():
            # Postgres veya SQL sunucusunu bul
            if "postgres" in name.lower() or "sql" in name.lower():
                args = cfg["args"]
                # Eğer relative path ise absolute path'e çevir
                if args and args[0].endswith(".py") and not os.path.isabs(args[0]):
                    args[0] = os.path.join(root_dir, args[0])
                
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=args,
                    env=os.environ.copy()
                )
                read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                self.db_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await self.db_session.initialize()
                print(f"🤖 [BACKEND] Veritabanına bağlandım: {name} (Model: {self.model_id})")
                return True
        return False

    async def generate_sql(self, user_query, history=None):
        """Kullanıcı sorusuna göre SQL üretir."""
        history_context = ""
        if history:
            # Sadece son 3 mesajı al
            last_msgs = history[-3:]
            history_context = "ÖNCEKİ KONUŞMA GEÇMİŞİ:\n"
            for msg in last_msgs:
                role = "USER" if msg["role"] == "user" else "BOT"
                history_context += f"{role}: {msg['content']}\n"
        
        prompt = f"""Sen Reklam Optimizasyon Botu'nun 'Hafif ve Doğrudan' versiyonusun.
SADECE Google Gemini zekasını ve MCP araçlarını kullanırsın. Başka bir katman yoktur.

VERİTABANI KURALLARI VE YAPISI:
{self.schema}

BUGÜNÜN TARİHİ: {datetime.now().strftime('%Y-%m-%d')}

{history_context}

USER QUESTION: {user_query}

Üreteceğin cevap SADECE ama SADECE SQL kodu olmalıdır. Başka hiçbir açıklama yapma.
"""
        response = self.client.models.generate_content(model=self.model_id, contents=prompt)
        sql = response.text.strip()
        
        # SQL Temizleme
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
            
        if "SELECT" in sql.upper() and not sql.upper().startswith("SELECT"):
            start_index = sql.upper().find("SELECT")
            sql = sql[start_index:].strip()
            
        return sql

    async def execute_sql(self, sql_query):
        """Üretilen SQL'i MCP üzerinden çalıştırır."""
        try:
            if not self.db_session:
                await self.connect()
                
            res = await self.db_session.call_tool("query", arguments={"sql": sql_query})
            if res.content:
                return res.content[0].text
            return "Veri bulunamadı."
        except Exception as e:
            return f"SQL Hatası: {e}"

    async def get_answer(self, user_query, sql_query, db_result, history=None):
        """DB sonucuna göre kullanıcıya cevap yazar."""
        history_context = ""
        if history:
            last_msgs = history[-3:]
            history_context = "ÖNCEKİ KONUŞMA GEÇMİŞİ:\n"
            for msg in last_msgs:
                role = "USER" if msg["role"] == "user" else "BOT"
                history_context += f"{role}: {msg['content']}\n"

        prompt = f"""Kullanıcı şunu sordu: {user_query}
            
KRİTİK MANTIK ÖZETİ:
1. Veritabanında her gün için birden fazla "snapshot" (kümülatif veri) bulunur. 
2. Toplam hesaplanırken önce her gün için MAX değeri alınmış, sonra toplanmıştır.
3. "Bugün" verisi DB'de dünün tarihiyle görünebilir (En güncel tarih baz alınır).
4. 'reklam_cirosu' genel cirodur, 'net_satis' ise sadece o ürünün doğrudan satışıdır.

{history_context}

Sistemin çalıştırdığı SQL: {sql_query}
Veritabanı Sonucu: {db_result}

Lütfen bu bilgilere göre uzman bir reklamcı gibi samimi ve Türkçe bir cevap yaz.
"""
        response = self.client.models.generate_content(model=self.model_id, contents=prompt)
        return response.text

    async def close(self):
        """Bağlantıları kapatır."""
        await self.exit_stack.aclose()

async def main():
    agent = SimpleAgent()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 CLI Bot uyanıyor...")
    
    chat_history = []

    if await agent.connect():
        try:
            while True:
                query = input("\n👤 Soru Sor (Çıkmak için 'q'): ").strip()
                if query.lower() in ['q', 'exit', 'quit']: break
                if not query: continue

                print("⏳ SQL hazırlanıyor...")
                sql = await agent.generate_sql(query, history=chat_history)
                print(f"💾 SQL: {sql}")

                print("📊 Veri çekiliyor...")
                result = await agent.execute_sql(sql)
                # print(f"✅ Ham sonuç: {result}")

                print("🧠 Cevap yazılıyor...")
                answer = await agent.get_answer(query, sql, result, history=chat_history)
                print(f"\n🤖 Bot: {answer}")

                # Geçmişe ekle
                chat_history.append({"role": "user", "content": query})
                chat_history.append({"role": "assistant", "content": answer})
        finally:
            await agent.close()
    else:
        print("❌ Bağlantı başarısız.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Güle güle!")
