import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage

from mcp_adapter import create_langchain_tools
from graph import create_mcp_graph
from llm_factory import get_llm
from intent_registry import IntentRegistry

load_dotenv()

async def run_system():
    # 1. Configuration
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Use the dedicated experimental server
    server_script = os.path.join(root_dir, "langgraph_system", "mcp_server.py")
    
    server_params = StdioServerParameters(
        command="python",
        args=[server_script]
    )

    print(f"Connecting to MCP Server at: {server_script}...")

    # 2. Connection and Orchestration
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP Session Initialized.")

            # 3. Dynamic Tool Discovery
            tools = await create_langchain_tools(session)
            print(f"Loaded {len(tools)} tools dynamically: {[t.name for t in tools]}")

            # 4. Model Setup
            # We pass the base_model and apply retries/binding inside the graph
            # to avoid AttributeError with with_structured_output.
            base_model = get_llm()
            
            # Plain model for reasoning (no tools)
            model_plain = base_model.with_retry(
                stop_after_attempt=4,
                wait_exponential_jitter=True
            )

            # 5. Load Intent Registry from YAML config
            registry = IntentRegistry()
            print(f"Loaded {len(registry.get_intent_names())} intents: {registry.get_intent_names()}")

            # 6. Graph Creation (registry now drives intent routing + tool filtering)
            app = create_mcp_graph(base_model, model_plain, tools, registry)

            # 6. Execution Loop
            print("\nFinal Target LangGraph + Mock MCP Ready. (Type 'exit' to quit)")
            print("Try: 'Scale up my campaign' or 'Optimize performance'")
            
            while True:
                user_msg = input("\nYou: ")
                if user_msg.lower() in ("exit", "quit", "q"):
                    break

                # Initialize State
                inputs = {
                    "messages": [HumanMessage(content=user_msg)],
                    "intent": "unknown",
                    "metrics": {},
                    "rules": [],
                    "confidence_score": 0,
                    "compliance_approved": False
                }
                
                # Run the graph
                print("\n" + "="*50)
                print("🚀 FLOW STARTED: Processing your request...")
                print("="*50)

                async for output in app.astream(inputs, stream_mode="updates"):
                    for node, data in output.items():
                        print(f"\n📍 [BAŞAMAK]: {node.upper()}")
                        
                        if node == "intent":
                            print(f"   🔍 Niyet Analiz Edildi: {data['intent']}")
                        
                        elif node == "tool_selection":
                            print(f"   🎯 Araç Seçimi Yapılıyor...")
                            if "messages" in data:
                                m = data["messages"][-1]
                                if hasattr(m, 'tool_calls') and m.tool_calls:
                                    tools_to_call = [tc['name'] for tc in m.tool_calls]
                                    print(f"   📋 Seçilen Araçlar: {tools_to_call}")

                        elif node == "tools":
                            print(f"   🛠️ Araçlar Kullanıldı (MCP Server)")
                            if "messages" in data:
                                for msg in data["messages"]:
                                    if hasattr(msg, 'content') and msg.content:
                                        print(f"   ✅ Veri Çekildi: {msg.content[:100]}...")

                        elif node == "reasoning":
                            print(f"   🧠 Yapay Zeka Akıl Yürütüyor...")
                            if "messages" in data:
                                m = data["messages"][-1]
                                content = m.content
                                # Handle list-based content (some models return blocks)
                                if isinstance(content, list):
                                    text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                                    clean_text = "".join(text_parts).strip()
                                else:
                                    clean_text = str(content).strip()
                                
                                print(f"   📝 Öneri:\n\n{clean_text}")

                        elif node == "evaluator":
                            print(f"   ⚖️ Güven Puanlaması Yapılıyor...")
                            if "confidence_score" in data:
                                score = data['confidence_score']
                                status = "✅ GÜVENLİ" if score >= 70 else "⚠️ DÜŞÜK GÜVEN"
                                print(f"   📊 Puan: {score}/100 -> {status}")

                print("\n" + "="*50)
                print("🏁 FLOW COMPLETED")
                print("="*50)

if __name__ == "__main__":
    try:
        asyncio.run(run_system())
    except KeyboardInterrupt:
        print("\n👋 Çıkılıyor...")
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ API kotası doldu. Birkaç dakika bekleyip tekrar deneyin.")
            print("   (Günlük Free Tier limiti: 20 istek. Gece 00:00'da sıfırlanır.)")
        else:
            raise
