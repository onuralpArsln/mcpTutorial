import asyncio # Bilgisayarın aynı anda birden fazla iş yapmasını sağlayan kütüphane
import os      # Dosya yolları ve sistem ayarlarıyla konuşmak için
import json    # Ayar dosyalarını (json) okumak için
import yaml    # Veritabanı şemasını (yaml) okumak için
import sys     # Sistemle ilgili temel işler için
from datetime import datetime # Şu anki tarih ve saati öğrenmek için
from contextlib import AsyncExitStack # Bağlantıları düzgünce kapatmak için yardımcı
from dotenv import load_dotenv # .env dosyasındaki şifreleri yüklemek için
from google import genai # Google'ın yapay zekasıyla (Gemini) konuşmak için
from google.genai import types # Gemini'ye ne göndereceğimizi belirlemek için
from mcp import ClientSession, StdioServerParameters # MCP (Veritabanı köprüsü) ayarları
from mcp.client.stdio import stdio_client # Veritabanıyla mesajlaşmak için kapı açar

# 1. AYARLARI YÜKLE
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Projenin ana klasörünü bul
load_dotenv(os.path.join(root_dir, ".env")) # Şifreleri (API Key) yükle

# Dosya yollarını belirle (Hangi dosya nerede?)
MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

def load_schema():
    """Yapay zekaya veritabanının yapısını anlatmak için dosyayı okur."""
    if not os.path.exists(SCHEMA_PATH):
        return "Şema dosyası bulunamadı."
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        # YAML dosyasını oku ve metin haline getir
        return yaml.dump(yaml.safe_load(f), allow_unicode=True)

async def main():
    """Ana program burada başlar."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Bot uyanıyor...")
    
    # 2. GEMINI'YI HAZIRLA
    api_key = os.getenv("GOOGLE_API_KEY") # Şifreni al
    # Using gemini-1.5-flash for higher rate limits than 2.0-flash-lite
    model_id = "gemini-2.5-flash" # Hangi robotla konuşacağımızı seç (En yenisi)
    client = genai.Client(api_key=api_key) # Yapay zeka bağlantısını kur
    
    # 3. VERİTABANI BAĞLANTISINI KUR
    exit_stack = AsyncExitStack() # Hata olursa her şeyi güvenle kapatmak için
    
    if not os.path.exists(MCP_CONFIG_PATH):
        print("Hata: mcp_config.json dosyası yok.")
        return

    with open(MCP_CONFIG_PATH, "r") as f:
        mcp_config = json.load(f) # Ayarları oku
    
    # Veritabanı sunucusunu bulmaya çalış
    db_session = None
    for name, cfg in mcp_config.get("mcpServers", {}).items():
        if "postgres" in name.lower() or "sql" in name.lower():
            # Veritabanına nasıl bağlanacağımızı söyleyen ayarlar
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg["args"],
                env=os.environ.copy()
            )
            # Kapıyı aç ve içeri gir
            read, write = await exit_stack.enter_async_context(stdio_client(params))
            db_session = await exit_stack.enter_async_context(ClientSession(read, write))
            await db_session.initialize() # Bağlantıyı başlat
            print(f"✅ Veritabanına bağlandım: {name}")
            break
    
    if not db_session:
        print("❌ Veritabanı sunucusu bulunamadı!")
        return

    chat_history = [] # Konuşmaları aklımızda tutmak için boş bir liste

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Hazırım! Çıkmak için 'q' yaz.")

    try:
        while True: # Sen 'q' diyene kadar döngü devam eder
            query = input("\n👤 Soru Sor: ").strip() # Senden bir cümle bekler
            if query.lower() in ['q', 'exit', 'quit']: break # 'q' dersen kapatır
            if not query: continue # Boş basarsan bir şey yapmaz

            # ADIM 1: Gemini'ye soruyu verip ondan SQL kodu istiyoruz
            step1_prompt = f"""Sen Reklam Optimizasyon Botu'nun 'Hafif ve Doğrudan' versiyonusun.
            SADECE Google Gemini zekasını ve MCP araçlarını kullanırsın. Başka bir katman yoktur.

            VERİTABANI KURALLARI VE YAPISI:
            {load_schema()}

            BUGÜNÜN TARİHİ: {datetime.now().strftime('%Y-%m-%d')}

            USER QUESTION: {query}
            """
            print("⏳ Yapay zeka SQL yazıyor...")
            response1 = client.models.generate_content(model=model_id, contents=step1_prompt)
            
            # Gemini'den gelen cevaptan SQL kodunu ayıkla
            sql_query = response1.text.strip()
            # If it contains code blocks, extract it
            if "```sql" in sql_query: # Kod bloklarının arasını al
                sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql_query:
                sql_query = sql_query.split("```")[1].split("```")[0].strip()
            
            # İçinde SELECT kelimesi geçen kısmı bul, gerisini at
            if "SELECT" in sql_query.upper() and not sql_query.upper().startswith("SELECT"):
                start_index = sql_query.upper().find("SELECT")
                sql_query = sql_query[start_index:].strip()
                
            print(f"💾 ÇALIŞACAK SQL:\n{sql_query}")

            # ADIM 2: SQL kodunu veritabanına gönderip sonuçları getiriyoruz
            db_result = "Veri bulunamadı."
            try:
                # Veritabanında sorguyu çalıştır
                # We assume the tool name is 'query' as per standard postgres mcp
                res = await db_session.call_tool("query", arguments={"sql": sql_query})
                if res.content:
                    db_result = res.content[0].text # Sonucu al
                
                # Terminale ham sonucu bas
                print(f"📊 VERİTABANI SONUCU:\n{db_result}")
            except Exception as e:
                db_result = f"Sorgu çalışırken hata oldu: {e}"
                print(f"❌ SQL HATASI: {e}")
            
            # ADIM 3: Gelen veriyi Gemini'ye verip insanca bir cevap yazdırıyoruz
            final_prompt = f"""Kullanıcı şunu sordu: {query}
                        
            KRİTİK MANTIK ÖZETİ:
            1. Veritabanında her gün için birden fazla "snapshot" (kümülatif veri) bulunur. 
            2. Toplam hesaplanırken önce her gün için MAX değeri alınmış, sonra toplanmıştır.
            3. "Bugün" verisi DB'de dünün tarihiyle görünebilir (En güncel tarih baz alınır).
            4. 'reklam_cirosu' genel cirodur, 'net_satis' ise sadece o ürünün doğrudan satışıdır.

            Sistemin çalıştırdığı SQL: {sql_query}
            Veritabanı Sonucu: {db_result}

            Lütfen bu bilgilere göre uzman bir reklamcı gibi samimi ve Türkçe bir cevap yaz.
            """
            print("🧠 Cevap hazırlanıyor...")
            response2 = client.models.generate_content(model=model_id, contents=final_prompt)
            final_answer = response2.text
            
            # Cevabı ekrana bas
            print(f"\n🤖 Bot: {final_answer}")
            
            # Konuşmayı hafızaya kaydet
            chat_history.append({"user": query, "sql": sql_query, "bot": final_answer})

    except Exception as e:
        print(f"❌ Bir hata oluştu: {e}")
    finally:
        # Bağlantıları düzgünce kapat
        await exit_stack.aclose()
        print("Güle güle!")

if __name__ == "__main__":
    asyncio.run(main()) # Programı başlat