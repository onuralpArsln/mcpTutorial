import streamlit as st
import asyncio
from langchain_core.messages import HumanMessage, AIMessage

from main import initialize_agent

# Set basic page config
st.set_page_config(page_title="AI Ad Manager", page_icon="📈", layout="centered")

st.title("AI Ad Manager 📈")
st.markdown("Ask me to analyze your campaigns, look directly at product costs, or optimize performance.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

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
if prompt := st.chat_input("Hangi kampanyaya bakayım?"):
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
                    "messages": [user_msg],
                    "intent": "unknown",
                    "metrics": {},
                    "rules": [],
                    "confidence_score": 0,
                    "compliance_approved": False
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
                        elif node in ("explainer", "analyst"):
                             # In case there's an intermediate output we might want to capture
                             pass
                        elif node == "evaluator":
                             if "confidence_score" in data:
                                 score = data['confidence_score']
                                 s = "✅ GÜVENLİ" if score >= 70 else "⚠️ DÜŞÜK GÜVEN"
                                 st.write(f"⚖️ Güven Puanı: {score}/100 -> {s}")
                                 
                # After the loop finishes, extract the final AIMessage from the graph state
                final_state = await app.aget_state({"messages": [user_msg]})
                if final_state and getattr(final_state, 'values', None) and "messages" in final_state.values:
                     messages = final_state.values["messages"]
                     if messages:
                         # The Explainer or Tool selector should be the last output message 
                         return messages[-1]
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
