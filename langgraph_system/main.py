import asyncio
import os
import json
from contextlib import AsyncExitStack
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
    # 1. Configuration & Server Discovery
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root_dir, "mcp_config.json")
    
    if not os.path.exists(config_path):
        print(f"❌ Error: {config_path} not found. Please create it first.")
        return

    with open(config_path, "r") as f:
        config = json.load(f)
    
    server_configs = config.get("mcpServers", {})
    active_tools = []
    
    # We use AsyncExitStack to manage multiple concurrent context managers (sessions)
    async with AsyncExitStack() as exit_stack:
        sessions = []
        
        print("\n--- 🔌 Connecting to MCP Servers ---")
        for name, cfg in server_configs.items():
            if cfg.get("disabled", False):
                continue
            
            print(f"Connecting to '{name}'...")
            
            # stdio transport (local)
            if cfg.get("type", "stdio") == "stdio":
                # Ensure we find the script relative to root if it's a python script
                args = cfg["args"]
                if args and args[0].endswith(".py") and not os.path.isabs(args[0]):
                    args[0] = os.path.join(root_dir, args[0])
                
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=args,
                    env=os.environ.copy()
                )
                
                # Enter the stdio_client context
                read, write = await exit_stack.enter_async_context(stdio_client(params))
                session = await exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                sessions.append(session)
                
                # Discovery tools for this specific session
                server_tools = await create_langchain_tools(session)
                active_tools.extend(server_tools)
                print(f"✅ '{name}' connected. Found {len(server_tools)} tools.")
            
            # TODO: sse transport (remote) can be added here
        
        if not active_tools:
            print("❌ No active tools found from any server. Exiting.")
            return

        print(f"\nTotal Unified Tools: {len(active_tools)}")

        # 2. Model Setup
        base_model = get_llm()
        model_plain = base_model.with_retry(
            stop_after_attempt=4,
            wait_exponential_jitter=True
        )

        # 3. Load Intent Registry
        registry = IntentRegistry()
        print(f"Loaded {len(registry.get_intent_names())} intents: {registry.get_intent_names()}")

        # 4. Graph Creation
        app = create_mcp_graph(base_model, model_plain, active_tools, registry)

        # 5. Execution Loop
        print("\n" + " ✨ " * 10)
        print("Final Target LangGraph (Multi-Server) Ready.")
        print("Try: 'Scale up my campaign' or 'Hangi ürünler mevcut'")
        print("Type 'exit' to quit.")
        print(" ✨ " * 10)
        
        while True:
            user_msg = input("\nYou: ")
            if user_msg.lower() in ("exit", "quit", "q"):
                break

            inputs = {
                "messages": [HumanMessage(content=user_msg)],
                "intent": "unknown",
                "metrics": {},
                "rules": [],
                "confidence_score": 0,
                "compliance_approved": False
            }
            
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
                        print(f"   🛠️ Araçlar Kullanıldı (Unified MCP Pool)")
                        if "messages" in data:
                            for msg in data["messages"]:
                                if hasattr(msg, 'content') and msg.content:
                                    print(f"   ✅ Veri Çekildi: {msg.content[:100]}...")

                    elif node == "reasoning":
                        print(f"   🧠 Yapay Zeka Akıl Yürütüyor...")
                        if "messages" in data:
                            m = data["messages"][-1]
                            content = m.content
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
