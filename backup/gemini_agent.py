import asyncio
import os
import json
import yaml
import sys
import re
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

class GeminiAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_id = os.getenv("BACKUP_MODEL_ID", "gemini-2.5-flash-lite")
        self.client = genai.Client(api_key=self.api_key)
        self.exit_stack = AsyncExitStack()
        self.db_session = None
        self.schema = self._load_schema()

    def _load_schema(self):
        if not os.path.exists(SCHEMA_PATH):
            return "Şema dosyası bulunamadı."
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            return yaml.dump(yaml.safe_load(f), allow_unicode=True)

    def extract_product_code(self, text):
        """Metin içindeki ürün kodlarını (X ile başlayan) bulur."""
        if not text: return None
        pattern = r"X[A-Z0-9]+"
        matches = re.findall(pattern, text.upper())
        return matches[0] if matches else None

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

    async def generate_sql(self, user_query, history=None, active_product=None):
        history_context = ""
        if history:
            history_context = "ÖNCEKİ KONUŞMALAR:\n"
            for msg in history[-5:]: # Son 5 mesaj yeterli
                role = "Kullanıcı" if msg["role"] == "user" else "Bot"
                history_context += f"{role}: {msg['content']}\n"
        
        # Ürün Kilidi (Explicit Product State)
        product_lock_guard = ""
        if active_product:
            product_lock_guard = f"\nKRİTİK BAĞLAM: Şu an {active_product} ürününe odaklıyız. Yazacağın SQL MUTLAKA bu ürünü filtrelemelidir.\n"

        prompt = f"""Sen bir Reklam Optimizasyon Chat Asistanısın. Görevin, kullanıcının sorularını verilerle destekleyerek cevaplamak.
{product_lock_guard}
SQL ÜRETİM KURALLARI:
1. Eğer kullanıcı belirli bir üründen bahsediyorsa (veya geçmişte bahsedilmişse ve soru "bunun", "o ürünün" gibi bağlamsal ise), SQL sorgusunda MUTLAKA `urun_kodu` filtresi (ILIKE veya =) kullanmalısın. TÜM tabloyu asla birleştirme (JOIN), sadece bağlamdaki ürüne odaklan.
2. **DOUBLE AGGREGATION RULE**: Veritabanında her gün için birden fazla kümülatif snapshot bulunur. Toplam (Grand Total) hesaplarken önce her gün/ürün için `MAX()` almalı, sonra bu sonuçları dış sorguda `SUM()` yapmalısın.
3. Stratejik sorular ("Bütçeyi ne yapalım?") için önce gerekli verileri (ROAS, harcama vb.) getirecek SQL'i yaz.
4. SADECE SQL dön. Başında veya sonunda açıklama yapma.
5. Eğer soru veritabanı gerektirmeyen basit bir sohbet ise (Örn: "Teşekkürler"), doğrudan kısa bir cevap dön.

{history_context}

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
            
        # Eğer bir SELECT içermiyorsa, bu muhtemelen doğrudan bir cevaptır.
        # Başına [DIRECT_ANSWER] ekleyerek orchestration katmanına haber veriyoruz.
        if "SELECT" not in sql.upper():
            return f"[DIRECT_ANSWER] {sql}"
            
        if not sql.upper().startswith("SELECT"):
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

    async def get_answer(self, user_query, sql_query, db_result, history=None, active_product=None):
        history_context = ""
        if history:
            history_context = "SOHBET GEÇMİSİ:\n"
            for msg in history[-3:]: # Son 3 mesaj cevap için yeterli
                role = "Kullanıcı" if msg["role"] == "user" else "Bot"
                history_context += f"{role}: {msg['content']}\n"

        # Token limit güvenliği için veri çok büyükse kırp
        db_result_str = str(db_result)
        if len(db_result_str) > 20000:
            truncated = db_result_str[:20000]
            db_result_str = f"{truncated}... [VERI COK UZUN OLDUGU ICIN KIRPILDI]"

        prompt = f"""Sen bir Reklam Analiz Chat Asistanısın. Kullanıcıya verileri yorumlayarak kısa, öz ve profesyonel cevaplar sunarsın.

CEVAPLAMA KURALLARI:
1. **ASLA** "Sayın Yetkili", "Sayın Kullanıcı" gibi resmi hitaplar kullanma. Doğrudan konuya gir.
2. **ASLA** [Adınız Soyadınız] veya [Unvanınız] gibi imza/placeholder kullanma.
3. **KISALIK**: Sadece sorulanı cevapla. Operasyonel sorulara ("Hangisi çok harcadı?") 1-2 cümleyle veriyi verip geç. 
4. **GEREKSİZ RAPORLAMA YAPMA**: Eğer kullanıcı strateji sormadıysa analiz raporu yazma.
5. Verileri her zaman profesyonelce yorumla.
6. Eğer veri KIRPILMIŞSA, kullanıcıya bunu belirt.

{history_context}

KRİTİK MANTIK ÖZETİ:
{self.schema}

Sistemin çalıştırdığı SQL: {sql_query}
Veritabanı Sonucu: {db_result_str}
Kullanıcı Sorusu: {user_query}
ODAK ÜRÜN (BAĞLAM): {active_product if active_product else 'Belirtilmedi (Gerekirse veriden çıkar)'}
"""
        response = self.client.models.generate_content(model=self.model_id, contents=prompt)
        return response.text

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    agent = GeminiAgent()
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