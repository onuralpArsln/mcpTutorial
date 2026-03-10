import streamlit as st
import asyncio
import os
import json
import yaml
from datetime import datetime
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from textcomplete import textcomplete, StrategyProps

# 1. SETUP ENVIRONMENT
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))

MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

# Set page config
st.set_page_config(page_title="ROB Backup", page_icon="🛡️", layout="centered")

st.title("🛡️ Reklam Optimizasyon Botu (Backup)")
st.markdown("Bu sayfa doğrudan Gemini ve Veritabanı bağlantısı ile en isabetli ve hızlı yanıtları üretir.")

# Product codes for auto-complete (Ported from main app)
PRODUCT_CODES = [
    "XPUFFY4040KAREPUF", "XPET4545KEDIYUVA", "XKATYAT14DENYE", "XOZELURTMMNDR",
    "XPETBIS6055BOND28", "TYCB55ED7921F34205", "XSANDMIN60120BISDENY",
    "XPETMERD4DENYE", "XPETPATIMINSUNSET", "XSANDMIN4514BISDENY",
    "XSANDMIN08OVALDEN6", "XSANDMIN04DENY6"
]

product_strategy = StrategyProps(
    id="productCodes",
    match=r"\B/(\w*)$",
    template="""(product) => `📦 ${product.name}`""",
    replace="""(product) => `${product.name}`""",
    data=[{"name": code} for code in PRODUCT_CODES],
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

def load_schema():
    if not os.path.exists(SCHEMA_PATH):
        return "Schema not found."
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.dump(yaml.safe_load(f), allow_unicode=True)

@st.cache_resource
def get_agent_resources():
    """Connects to MCP and initializes Gemini."""
    api_key = os.getenv("GOOGLE_API_KEY")
    # Using the user-specified experimental model
    model_id = "gemini-2.5-flash"
    client = genai.Client(api_key=api_key)
    
    # Connect to MCP (Simplified for DB only)
    with open(MCP_CONFIG_PATH, "r") as f:
        mcp_config = json.load(f)
    
    db_config = None
    for name, cfg in mcp_config.get("mcpServers", {}).items():
        if "postgres" in name.lower() or "sql" in name.lower():
            db_config = cfg
            break
            
    if not db_config:
        return None, None, None
        
    loop = st.session_state.loop
    
    async def connect_mcp():
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

    db_session, exit_stack = loop.run_until_complete(connect_mcp())
    return client, db_session, exit_stack, model_id

# Initialize backend
with st.spinner("Veritabanı ve Gemini'ye bağlanılıyor..."):
    client, db_session, exit_stack, model_id = get_agent_resources()

if not client:
    st.error("Bağlantı hatası! Lütfen mcp_config.json ve .env dosyalarınızı kontrol edin.")
    st.stop()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("Görüntüle: SQL Sorgusu"):
                st.code(msg["sql"], language="sql")

# React to user input
chat_placeholder = "Sorunuzu buraya yazın veya / ile ürun seçin..."

textcomplete(
    area_label=chat_placeholder,
    strategies=[product_strategy],
    max_count=10,
    stop_enter_propagation=True,
    placement="top",
)

if prompt := st.chat_input(chat_placeholder):
    # Display user message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Process response
    with st.chat_message("assistant"):
        with st.status("Veriler inceleniyor...") as status:
            loop = st.session_state.loop
            schema_context = load_schema()
            
            # 1. GENERATE SQL
            st.write("📝 SQL Sorgusu oluşturuluyor...")
            step1_prompt = f"""You are a SQL expert. Based on the user question and the database schema below, write the CORRECT SQL query to answer it.
SCHEMA:
{schema_context}
IMPORTANT: 
- Return ONLY the SQL query.
- Use aggregation (SUM) where appropriate.
- Today is {datetime.now().strftime('%Y-%m-%d')}.
USER QUESTION: {prompt}
"""
            response1 = client.models.generate_content(model=model_id, contents=step1_prompt)
            sql_query = response1.text.strip().replace("```sql", "").replace("```", "").strip()
            
            st.write("💾 SQL Çalıştırılıyor...")
            st.code(sql_query, language="sql")
            
            # 2. RUN SQL
            db_result = "Veri bulunamadı."
            try:
                async def run_sql():
                    res = await db_session.call_tool("query", arguments={"sql": sql_query})
                    if res.content:
                        result_text = res.content[0].text
                        # LOG RESULT TO TERMINAL
                        print(f"📊 SQL RESULT (Streamlit):\n{result_text}")
                        return result_text
                    return "Sonuç boş."
                
                db_result = loop.run_until_complete(run_sql())
            except Exception as e:
                db_result = f"SQL Hatası: {e}"
            
            # 3. FINAL ANSWER
            st.write("🧠 Sonuç harmanlanıyor...")
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
            final_prompt = f"""User asked: {prompt}
DATABASE RESULT:
{db_result}
CHAT HISTORY:
{history_text}

Provide a clear, friendly, and concise answer in Turkish based strictly on the result.
"""
            response2 = client.models.generate_content(model=model_id, contents=final_prompt)
            final_answer = response2.text
            
            status.update(label="Tamamlandı!", state="complete", expanded=False)

        st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer, "sql": sql_query})
