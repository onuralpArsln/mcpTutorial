import streamlit as st
import asyncio
import os
from datetime import datetime
from simple_agent import BackupAgent

# Sayfanın başlığını ve ikonunu ayarla
st.set_page_config(page_title="ROB-DeliDestiko", page_icon="💥🚀", layout="centered")

st.title("⚡ Reklam Analiz Yardımcısı")
st.markdown("Gemini ile güçlendirildi! 🚀")


# 1. OTURUM HAFIZASINI HAZIRLA (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []

if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()

@st.cache_resource
def get_backup_agent():
    """BackupAgent nesnesini bir kez oluşturup hafızada tutar."""
    agent = BackupAgent()
    loop = st.session_state.loop
    # Bağlantıyı asenkron olarak başlat
    loop.run_until_complete(agent.connect())
    return agent

# Agent'ı başlat
with st.spinner("Motor ısınıyor..."):
    agent = get_backup_agent()

# Eski mesajları ekrana çiz
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 SQL Detayı"):
                st.code(msg["sql"], language="sql")

# Ürün kodları (Otomatik tamamlama için)
PRODUCT_CODES = [
    "XPUFFY4040KAREPUF", "XPET4545KEDIYUVA", "XKATYAT14DENYE", "XOZELURTMMNDR",
    "XPETBIS6055BOND28", "TYCB55ED7921F34205", "XSANDMIN60120BISDENY",
    "XPETMERD4DENYE", "XPETMERD4DENYE", "XPETPATIMINSUNSET", "XSANDMIN4514BISDENY",
    "XSANDMIN08OVALDEN6", "XSANDMIN04DENY6"
]

# JavaScript Kestirmeleri ve Auto-Focus
import streamlit.components.v1 as components
components.html(
    """
    <script>
    const doc = window.parent.document;
    function setupInteractions() {
        const input = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (!input) return;
        if (doc.activeElement !== input) input.focus();
        if (!input.dataset.shortcutAdded) {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && (e.shiftKey || e.ctrlKey)) {
                    e.preventDefault();
                    e.stopPropagation();
                    const btn = input.closest('div[data-testid="stChatInput"]').querySelector('button[data-testid="stChatInputSubmitButton"]');
                    if (btn) btn.click();
                }
            }, true);
            input.dataset.shortcutAdded = "true";
        }
    }
    setInterval(setupInteractions, 1000);
    setTimeout(setupInteractions, 500);
    </script>
    """,
    height=0,
)

# 2. CHAT INPUT
if prompt := st.chat_input("Ürün Hakkında Soru Sor..."):
    # Kullanıcının mesajını ekrana bas ve hafızaya al
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Botun cevabını üret
    with st.chat_message("assistant"):
        with st.status("Düşünülüyor...", expanded=True) as status:
            try:
                loop = st.session_state.loop
                
                # Adım 1: SQL Üret
                st.write("⏳ SQL hazırlanıyor...")
                sql_query = loop.run_until_complete(agent.generate_sql(prompt))
                st.code(sql_query, language="sql")
                
                # Adım 2: SQL Çalıştır
                st.write("📊 Veritabanına soruluyor...")
                db_result = loop.run_until_complete(agent.execute_sql(sql_query))
                print(f"🔍 [LOG] SQL: {sql_query}")
                
                # Adım 3: Final Cevap
                st.write("🧠 Cevap hazırlanıyor..")
                answer = loop.run_until_complete(agent.get_answer(prompt, sql_query, db_result))
                
                status.update(label="Tamamlandı!", state="complete", expanded=False)
                
                # Sonucu göster
                st.markdown(answer)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer, 
                    "sql": sql_query
                })
                
            except Exception as e:
                st.error(f"Hata oluştu: {e}")
                status.update(label="Hata!", state="error")
