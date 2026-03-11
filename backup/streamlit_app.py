import streamlit as st
import asyncio
import os
import json
from datetime import datetime
from simple_agent import BackupAgent

# Sayfanın başlığını ve ikonunu ayarla
st.set_page_config(page_title="ROB", page_icon="💥🚀", layout="centered")

st.title("⚡ Reklam Analiz Yardımcısı")
st.markdown("Gemini ile çalışıyor! 🚀")

# --- 1. AYARLAR VE HAFIZA ---
MAX_HISTORY_MESSAGES = 10  # LLM'e gönderilecek son mesaj sayısı
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

def get_history_path(username):
    return os.path.join(HISTORY_DIR, f"{username.lower().strip()}.json")

def save_history(username, messages):
    if not username: return
    path = get_history_path(username)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def load_history(username):
    path = get_history_path(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# --- 2. KULLANICI GİRİŞİ (SIDEBAR) ---
with st.sidebar:
    st.header("👤 Kullanıcı Paneli")
    username = st.text_input("Kullanıcı Adı", placeholder="Örn: Onur").strip()
    if st.button("Sohbeti Temizle") and username:
        st.session_state.messages = []
        st.session_state.active_product = None
        save_history(username, [])
        st.rerun()

    st.divider()
    active_prod = st.session_state.get("active_product")
    if active_prod:
        st.success(f"📌 **Odak Ürün:** {active_prod}")
        if st.button("Kilidi Kaldır"):
            st.session_state.active_product = None
            st.rerun()
    else:
        st.info("📌 Ürün kilidi yok.")

# --- 3. OTURUM HAFIZASINI HAZIRLA ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "active_product" not in st.session_state:
    st.session_state.active_product = None

# Kullanıcı değişmişse veya yeni girilmişse geçmişi yükle
if username and st.session_state.current_user != username:
    st.session_state.messages = load_history(username)
    st.session_state.current_user = username

if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()

@st.cache_resource
def get_backup_agent():
    """BackupAgent nesnesini bir kez oluşturup hafızada tutar."""
    agent = BackupAgent()
    loop = st.session_state.loop
    loop.run_until_complete(agent.connect())
    return agent

# Agent'ı başlat
with st.spinner("Ajan Başlıyor..."):
    agent = get_backup_agent()

# Eski mesajları ekrana çiz
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 SQL Detayı"):
                st.code(msg["sql"], language="sql")

# --- 4. CHAT INPUT ---
if not username:
    st.info("💡 Lütfen sohbete başlamak için soldaki menüden bir kullanıcı adı girin.")
else:
    if prompt := st.chat_input("Ürün Hakkında Soru Sor..."):
        # Kullanıcının mesajını ekrana bas ve hafızaya al
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_history(username, st.session_state.messages) # Kaydet
        with st.chat_message("user"):
            st.markdown(prompt)

        # Ürün kodunu tara (Yeni ürün varsa kilidi güncelle)
        new_product = agent.extract_product_code(prompt)
        if new_product:
            st.session_state.active_product = new_product
            # Sayfayı yenilemeden UI'daki indicator'ın güncellenmesi zor olabilir 
            # ancak işlem bitince zaten bir state change olacak.

        # Botun cevabını üret
        with st.chat_message("assistant"):
            with st.status("Düşünülüyor...", expanded=True) as status:
                try:
                    loop = st.session_state.loop
                    
                    # Adım 1: SQL Üret
                    st.write("⏳ SQL hazırlanıyor...")
                    # Sadece son MAX_HISTORY_MESSAGES kadar mesajı gönder
                    limited_history = st.session_state.messages[-MAX_HISTORY_MESSAGES-1:-1]
                    active_prod = st.session_state.active_product
                    sql_query = loop.run_until_complete(agent.generate_sql(
                        prompt, 
                        history=limited_history, 
                        active_product=active_prod
                    ))
                    
                    # Eğer doğrudan cevap ise (SQL değilse)
                    if sql_query.startswith("[DIRECT_ANSWER]"):
                        answer = sql_query.replace("[DIRECT_ANSWER]", "").strip()
                        status.update(label="Sohbet Yanıtı", state="complete", expanded=False)
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        save_history(username, st.session_state.messages)
                    else:
                        st.code(sql_query, language="sql")
                        
                        # Adım 2: SQL Çalıştır
                        st.write("📊 Veritabanına soruluyor...")
                        db_result = loop.run_until_complete(agent.execute_sql(sql_query))
                        
                        # Adım 3: Final Cevap
                        st.write("🧠 Cevap hazırlanıyor..")
                        # Sadece son MAX_HISTORY_MESSAGES kadar mesajı gönder
                        limited_history = st.session_state.messages[-MAX_HISTORY_MESSAGES-1:-1]
                        active_prod = st.session_state.active_product
                        answer = loop.run_until_complete(agent.get_answer(
                            prompt, 
                            sql_query, 
                            db_result, 
                            history=limited_history,
                            active_product=active_prod
                        ))
                        
                        status.update(label="Tamamlandı!", state="complete", expanded=False)
                        
                        # Sonucu göster
                        st.markdown(answer)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer, 
                            "sql": sql_query
                        })
                        save_history(username, st.session_state.messages) # Kaydet
                    
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")
                    status.update(label="Hata!", state="error")
