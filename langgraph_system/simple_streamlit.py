import streamlit as st
import asyncio
import os
from datetime import datetime
from simple_agent import SimpleAgent

# Sayfanın başlığını ve ikonunu ayarla
st.set_page_config(page_title="ROB-Simple", page_icon="⚡", layout="centered")

st.title("⚡ Reklam Analiz Yardımcısı (Simple)")
st.markdown("Gemini-Direct Mode 🚀")

# 1. OTURUM HAFIZASINI HAZIRLA (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []

if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()

@st.cache_resource
def get_agent():
    """SimpleAgent nesnesini bir kez oluşturup hafızada tutar."""
    agent = SimpleAgent()
    loop = st.session_state.loop
    # Bağlantıyı asenkron olarak başlat
    loop.run_until_complete(agent.connect())
    return agent

# Agent'ı başlat
with st.spinner("Veritabanına bağlanılıyor..."):
    agent = get_agent()

# Eski mesajları ekrana çiz
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 SQL Detayı"):
                st.code(msg["sql"], language="sql")

# 2. CHAT INPUT
if prompt := st.chat_input("Ürün Hakkında Soru Sor..."):
    # Kullanıcının mesajını ekrana bas ve hafızaya al
    st.chat_message("user").markdown(prompt)

    # Botun cevabını üret
    with st.chat_message("assistant"):
        with st.status("Düşünülüyor...", expanded=True) as status:
            try:
                loop = st.session_state.loop
                
                # Geçmişi al (Son 5 mesaj yeterli)
                history = st.session_state.messages[-5:] if st.session_state.messages else []

                # Adım 1: SQL Üret
                st.write("⏳ SQL hazırlanıyor...")
                sql_query = loop.run_until_complete(agent.generate_sql(prompt, history=history))
                st.code(sql_query, language="sql")
                
                # Adım 2: SQL Çalıştır
                st.write("📊 Veritabanına soruluyor...")
                db_result = loop.run_until_complete(agent.execute_sql(sql_query))
                
                # Adım 3: Final Cevap
                st.write("🧠 Cevap hazırlanıyor..")
                answer = loop.run_until_complete(agent.get_answer(prompt, sql_query, db_result, history=history))
                
                status.update(label="Tamamlandı!", state="complete", expanded=False)
                
                # Sonucu göster
                st.markdown(answer)
                
                # Hafızaya kaydet
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer, 
                    "sql": sql_query
                })
                
            except Exception as e:
                st.error(f"Hata oluştu: {e}")
                status.update(label="Hata!", state="error")
