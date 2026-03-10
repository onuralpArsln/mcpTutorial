import streamlit as st # İnternet sayfası arayüzü yapmak için kütüphane
import asyncio      # Aynı anda birden fazla iş (bağlantı vb.) yönetmek için
import os           # Dosya yolları ve sistem ayarları için
import json         # Ayar dosyalarını (json) okumak için
import yaml         # Veritabanı şemasını (yaml) okumak için
from datetime import datetime # Şu anki tarih ve saati öğrenmek için
from contextlib import AsyncExitStack # Bağlantıları güvenle kapatmak için
from dotenv import load_dotenv # Şifreleri (.env) yüklemek için
from google import genai # Google Gemini ile konuşmak için
from google.genai import types # Mesaj tiplerini belirlemek için
from mcp import ClientSession, StdioServerParameters # Veritabanı köprüsü ayarları
from mcp.client.stdio import stdio_client # Veritabanı kapısını açmak için
from textcomplete import textcomplete, StrategyProps # Yazarken otomatik tamamlama özelliği

# 1. AYARLARI HAZIRLA
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Ana klasörü bul
load_dotenv(os.path.join(root_dir, ".env")) # Şifreleri yükle

# Dosya yerlerini belirle
MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

# Sayfanın başlığını ve ikonunu ayarla
st.set_page_config(page_title="ROB-GEMINICharged", page_icon="⚡", layout="centered")

st.title("⚡ Reklam Botu PRO 2.5")
st.markdown("Arka plan gemini ve çok hızlı ayrıca her mesaj maliyeti sadece 0.4 cent")

# Yazarken "/" koyunca çıkacak ürün kodları listesi
PRODUCT_CODES = [
    "XPUFFY4040KAREPUF", "XPET4545KEDIYUVA", "XKATYAT14DENYE", "XOZELURTMMNDR",
    "XPETBIS6055BOND28", "TYCB55ED7921F34205", "XSANDMIN60120BISDENY",
    "XPETMERD4DENYE", "XPETPATIMINSUNSET", "XSANDMIN4514BISDENY",
    "XSANDMIN08OVALDEN6", "XSANDMIN04DENY6"
]

# Otomatik tamamlama ayarları (Mala anlatır gibi: Yazarken sana seçenek sunar)
product_strategy = StrategyProps(
    id="productCodes",
    match=r"\B/(\w*)$",
    template="""(product) => `📦 ${product.name}`""",
    replace="""(product) => `${product.name}`""",
    data=[{"name": code} for code in PRODUCT_CODES],
)

# Sayfa yenilense de silinmemesi gereken verileri (mesajlar vb.) hazırla
if "messages" not in st.session_state:
    st.session_state.messages = []
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

def load_schema():
    """Gemini'ye veritabanını tanıtmak için şemayı okur."""
    if not os.path.exists(SCHEMA_PATH):
        return "Şema bulunamadı."
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.dump(yaml.safe_load(f), allow_unicode=True)

@st.cache_resource
def get_agent_resources():
    """Gemini ve Veritabanı bağlantılarını bir kez kurup hafızada tutar."""
    api_key = os.getenv("GOOGLE_API_KEY")
    model_id = "gemini-2.5-flash" # En akıllı robotu seç
    client = genai.Client(api_key=api_key)
    
    # Veritabanı ayarlarını oku
    with open(MCP_CONFIG_PATH, "r") as f:
        mcp_config = json.load(f)
    
    db_config = None
    for name, cfg in mcp_config.get("mcpServers", {}).items():
        if "postgres" in name.lower() or "sql" in name.lower():
            db_config = cfg
            break
            
    if not db_config: return None, None, None, None
        
    loop = st.session_state.loop
    
    async def connect_mcp():
        """Veritabanına asıl bağlantıyı yapan gizli kutu."""
        stack = AsyncExitStack()
        params = StdioServerParameters(
            command=db_config["command"],
            args=db_config["args"],
            env=os.environ.copy()
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session, stack

    # Bağlantıyı gerçekleştir
    db_session, exit_stack = loop.run_until_complete(connect_mcp())
    return client, db_session, exit_stack, model_id

# Robot ve Veritabanı bağlantısını başlat
with st.spinner("Sistem hazırlanıyor..."):
    client, db_session, exit_stack, model_id = get_agent_resources()

if not client:
    st.error("Bağlantı kurulamadı! Ayarları kontrol et.")
    st.stop()

# Eski mesajları ekrana çiz
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("Görüntüle: SQL Sorgusu"):
                st.code(msg["sql"], language="sql")

# Yazı yazma kutusunu hazırla
chat_placeholder = "Sorunuzu buraya yazın veya / ile ürün seçin..."

# Otomatik tamamlamayı kutuya bağla
textcomplete(
    area_label=chat_placeholder,
    strategies=[product_strategy],
    max_count=10,
    stop_enter_propagation=True,
    placement="top",
)

# Sen bir şey yazıp Enter'a basınca burası çalışır
if prompt := st.chat_input(chat_placeholder):
    # Senin mesajını ekrana ekle
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Cevap üretme kısmı
    with st.chat_message("assistant"):
        with st.status("Veriler inceleniyor...") as status:
            loop = st.session_state.loop
            schema_context = load_schema()
            
            # ADIM 1: Gemini'den SQL kodu istiyoruz
            st.write("📝 SQL Sorgusu oluşturuluyor...")
            step1_prompt = f"""Sen Reklam Botusun. SADECE SQL kodu yaz. Açıklama yapma.
            VERİTABANI ŞEMASI:
            {schema_context}
            BUGÜN: {datetime.now().strftime('%Y-%m-%d')}
            SORU: {prompt}
            """
            response1 = client.models.generate_content(model=model_id, contents=step1_prompt)
            
            # SQL kodunu temizle (Sağındaki solundaki fazlalıkları at)
            sql_query = response1.text.strip()
            if "```sql" in sql_query:
                sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql_query:
                sql_query = sql_query.split("```")[1].split("```")[0].strip()
            
            if "SELECT" in sql_query.upper() and not sql_query.upper().startswith("SELECT"):
                start_index = sql_query.upper().find("SELECT")
                sql_query = sql_query[start_index:].strip()
                
            st.write("💾 Veritabanı sorgulanıyor...")
            st.code(sql_query, language="sql")
            print(f"\n🔍 [LOG] Çalıştırılan SQL:\n{sql_query}\n")
            
            # ADIM 2: SQL kodunu çalıştırıp verileri getir
            db_result = "Veri bulunamadı."
            try:
                async def run_sql():
                    res = await db_session.call_tool("query", arguments={"sql": sql_query})
                    if res.content:
                        result_text = res.content[0].text
                        print(f"📊 SQL SONUCU: {result_text}") # Terminale de yaz
                        return result_text
                    return "Sonuç boş."
                
                db_result = loop.run_until_complete(run_sql())
            except Exception as e:
                db_result = f"Hata: {e}"
            
            # ADIM 3: Verileri insanca bir cevaba dönüştür
            st.write("🧠 Cevap yazılıyor...")
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
            final_prompt = f"""Kullanıcı sorusu: {prompt}

            KRİTİK MANTIK ÖZETİ:
            1. Veritabanında her gün için birden fazla "snapshot" (kümülatif veri) bulunur. 
            2. Toplam hesaplanırken önce her gün için MAX değeri alınmış, sonra toplanmıştır.
            3. "Bugün" verisi DB'de dünün tarihiyle görünebilir (En güncel tarih baz alınır).
            4. 'reklam_cirosu' genel cirodur, 'net_satis' ise sadece o ürünün doğrudan satışıdır.

            Çalıştırılan SQL Sorgusu: {sql_query}
            Veritabanından Gelen Ham Veri: {db_result}
            Geçmiş: {history_text}

            Lütfen bu bilgilere göre uzman bir reklamcı gibi Türkçe ve samimi bir cevap yaz.
            """
            
            response2 = client.models.generate_content(model=model_id, contents=final_prompt)
            final_answer = response2.text
            
            status.update(label="İşlem Tamam!", state="complete", expanded=False)

        # Robotun cevabını ekrana bas ve kaydet
        st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer, "sql": sql_query})
