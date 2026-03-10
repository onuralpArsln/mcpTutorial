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
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))

MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

class BackupAgent:
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
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            return yaml.dump(yaml.safe_load(f), allow_unicode=True)

    async def connect(self):
        if not os.path.exists(MCP_CONFIG_PATH):
            raise FileNotFoundError("mcp_config.json bulunamadı.")

        with open(MCP_CONFIG_PATH, "r") as f:
            mcp_config = json.load(f)

        for name, cfg in mcp_config.get("mcpServers", {}).items():
            if "postgres" in name.lower() or "sql" in name.lower():
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=cfg["args"],
                    env=os.environ.copy()
                )
                read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                self.db_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await self.db_session.initialize()
                print(f"🤖 [BACKEND] Veritabanına bağlandım: {name} (Model: {self.model_id})")
                return True
        return False

    async def generate_sql(self, user_query):
        prompt = f"""Sen Reklam Optimizasyon Botu'nun 'Hafif ve Doğrudan' versiyonusun.
SADECE Google Gemini zekasını ve MCP araçlarını kullanırsın. Başka bir katman yoktur.

VERİTABANI KURALLARI VE YAPISI:
{self.schema}

BUGÜNÜN TARİHİ: {datetime.now().strftime('%Y-%m-%d')}

USER QUESTION: {user_query}
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
        try:
            res = await self.db_session.call_tool("query", arguments={"sql": sql_query})
            if res.content:
                return res.content[0].text
            return "Veri bulunamadı."
        except Exception as e:
            return f"SQL Hatası: {e}"

    async def get_answer(self, user_query, sql_query, db_result):
        prompt = f"""Kullanıcı şunu sordu: {user_query}
            
KRİTİK MANTIK ÖZETİ:
1. Veritabanında her gün için birden fazla "snapshot" (kümülatif veri) bulunur. 
2. Toplam hesaplanırken önce her gün için MAX değeri alınmış, sonra toplanmıştır.
3. "Bugün" verisi DB'de dünün tarihiyle görünebilir (En güncel tarih baz alınır).
4. 'reklam_cirosu' genel cirodur, 'net_satis' ise sadece o ürünün doğrudan satışıdır.

Sistemin çalıştırdığı SQL: {sql_query}
Veritabanı Sonucu: {db_result}

Lütfen bu bilgilere göre uzman bir reklamcı gibi samimi ve Türkçe bir cevap yaz.
"""
        response = self.client.models.generate_content(model=self.model_id, contents=prompt)
        return response.text

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    agent = BackupAgent()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 CLI Bot uyanıyor...")
    
    if await agent.connect():
        try:
            while True:
                query = input("\n👤 Soru Sor: ").strip()
                if query.lower() in ['q', 'exit', 'quit']: break
                if not query: continue

                print("⏳ SQL hazırlanıyor...")
                sql = await agent.generate_sql(query)
                print(f"💾 SQL: {sql}")

                print("📊 Veri çekiliyor...")
                result = await agent.execute_sql(sql)
                print(f"✅ Sonuç alındı.")

                print("🧠 Cevap yazılıyor...")
                answer = await agent.get_answer(query, sql, result)
                print(f"\n🤖 Bot: {answer}")
        finally:
            await agent.close()
    else:
        print("❌ Bağlantı başarısız.")

if __name__ == "__main__":
    asyncio.run(main())