import streamlit as st
from textcomplete import textcomplete, StrategyProps
import asyncio
from langchain_core.messages import HumanMessage, AIMessage

from main import initialize_agent

# Set basic page config
st.set_page_config(page_title="ROB", page_icon="📈", layout="centered")

st.title("Reklam Optimizsayon Botu")
st.markdown("Ask me to analyze your campaigns, look directly at product costs, or optimize performance.")

# Product codes for auto-complete
PRODUCT_CODES = [
    "XPUFFY4040KAREPUF", "XPET4545KEDIYUVA", "XKATYAT14DENYE", "XOZELURTMMNDR",
    "XPETBIS6055BOND28", "TYCB55ED7921F34205", "XSANDMIN60120BISDENY",
    "XPETMERD4DENYE", "XPETMERD4DENYE", "XPETPATIMINSUNSET", "XSANDMIN4514BISDENY",
    "XSANDMIN08OVALDEN6", "XSANDMIN04DENY6"
]

# Auto-complete strategy for product codes (triggered by /)
# Auto-complete strategy for product codes (triggered by /)
product_strategy = StrategyProps(
    id="productCodes",
    match=r"\B/(\w*)$",
    template="""(product) => `📦 ${product.name}`""",
    replace="""(product) => `${product.name}`""",
    data=[{"name": code} for code in PRODUCT_CODES],
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context_summary" not in st.session_state:
    st.session_state.context_summary = ""

# Get or create an event loop for the session
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

# Cache the agent initialization so we don't reconnect to MCP servers on every stream/re-render
@st.cache_resource
def get_agent():
    # Use the session loop to run the async initialization
    loop = st.session_state.loop
    return loop.run_until_complete(initialize_agent())

with st.spinner("Connecting to MCP Servers and loading Agent..."):
    app, exit_stack = get_agent()

if not app:
    st.error("Failed to initialize Agent. Check your mcp_config.json")
    st.stop()

# Display chat messages from history on app rerun
for msg in st.session_state.messages:
    # simple formatting for AIMessage and HumanMessage
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(msg.content)

# React to user input
chat_placeholder = "Hangi kampanyaya bakayım?"

# Enable auto-complete for the chat input (rendered before or after, but placing before for priority)
textcomplete(
    area_label=chat_placeholder,
    strategies=[product_strategy],
    max_count=10,
    stop_enter_propagation=True,
    placement="bottom",

)

if prompt := st.chat_input(chat_placeholder):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to session memory
    user_msg = HumanMessage(content=prompt)
    st.session_state.messages.append(user_msg)

    # Process the response
    with st.chat_message("assistant"):
        # We use an expander to show the "Thought process" (LangGraph Nodes)
        with st.status("Thinking...", expanded=True) as status:
            
            async def run_graph():
                inputs = {
                    "messages": st.session_state.messages,
                    "intent": "unknown",
                    "context_summary": st.session_state.context_summary,
                }
                
                final_response = None
                
                async for output in app.astream(inputs, stream_mode="updates"):
                    for node, data in output.items():
                        if node == "intent":
                            st.write(f"🔍 Niyet Analizi: **{data['intent']}**")
                        elif node == "tool_selection":
                            st.write(f"🎯 Araç Seçimi Yapılıyor...")
                            if "messages" in data and data["messages"]:
                                m = data["messages"][-1]
                                if hasattr(m, 'tool_calls') and m.tool_calls:
                                    tools_to_call = [tc['name'] for tc in m.tool_calls]
                                    st.write(f"📋 Seçilen Araçlar: `{tools_to_call}`")
                        elif node == "tools":
                            st.write(f"🛠️ Araçlar Kullanıldı (MCP Pool)")
                            if "messages" in data:
                                for msg in data["messages"]:
                                    if hasattr(msg, 'content') and msg.content:
                                        # only show a snippet of the raw data drawn
                                        snippet = str(msg.content)[:150].replace('\n', ' ')
                                        st.write(f"✅ Veri Çekildi: _{snippet}..._")
                        elif node == "analyst":
                             if "analysis_result" in data:
                                 st.write(f"🔬 **Analist Notu:** {data['analysis_result'][:300]}...")
                             if "violates_rules" in data:
                                 flag = "⚠️ Kural İhlali Tespit Edildi" if data["violates_rules"] else "✅ Kural İhlali Yok"
                                 st.write(flag)
                        elif node == "explainer":
                             if "messages" in data:
                                 m = data["messages"][-1]
                                 content = m.content
                                 if isinstance(content, list):
                                     text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                                     final_response = "".join(text_parts).strip()
                                 else:
                                     final_response = str(content).strip()
                             if "context_summary" in data:
                                 st.session_state.context_summary = data["context_summary"]
                # We can just return the response captured during the "explainer" step
                if final_response:
                    return AIMessage(content=final_response)
                
                return AIMessage(content="Bir hata oluştu, yanıt alınamadı.")

            # Run the asynchronous graph using the session's active event loop
            final_message_obj = st.session_state.loop.run_until_complete(run_graph())
            
            # Update status block
            status.update(label="Complete!", state="complete", expanded=False)
            
        # Display the final text output outside the status box
        final_text = final_message_obj.content
        if isinstance(final_text, list):
             text_parts = [part.get("text", "") for part in final_text if isinstance(part, dict) and part.get("type") == "text"]
             final_text = "".join(text_parts).strip()
             
        st.markdown(final_text)
        
        # Save to memory, but ensure it's always an AIMessage object.
        st.session_state.messages.append(AIMessage(content=final_text))
