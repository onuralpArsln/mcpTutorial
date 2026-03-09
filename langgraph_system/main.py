import asyncio
import os
import json
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage, AIMessage

from mcp_adapter import create_langchain_tools
from graph import create_mcp_graph
from llm_factory import get_llm
from intent_registry import IntentRegistry

load_dotenv()

async def initialize_agent():
    # 1. Configuration & Server Discovery
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root_dir, "mcp_config.json")
    
    if not os.path.exists(config_path):
        print(f" Error: {config_path} not found. Please create it first.")
        return None, None
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    server_configs = config.get("mcpServers", {})
    active_tools = []
    
    exit_stack = AsyncExitStack()
    try:
        sessions = []
        print("\n---  Connecting to MCP Servers ---")
        for name, cfg in server_configs.items():
            if cfg.get("disabled", False):
                continue
            
            print(f"Connecting to '{name}'...")
            
            # stdio transport (local)
            if cfg.get("type", "stdio") == "stdio":
                args = cfg["args"]
                if args and args[0].endswith(".py") and not os.path.isabs(args[0]):
                    args[0] = os.path.join(root_dir, args[0])
                
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=args,
                    env=os.environ.copy()
                )
                
                read, write = await exit_stack.enter_async_context(stdio_client(params))
                session = await exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                sessions.append(session)
                
                server_tools = await create_langchain_tools(session)
                active_tools.extend(server_tools)
                print(f"✅ '{name}' connected. Found {len(server_tools)} tools.")
        
        if not active_tools:
            print("No active tools found from any server. Exiting.")
            await exit_stack.aclose()
            return None, None

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
        
        return app, exit_stack
    
    except Exception as e:
        await exit_stack.aclose()
        raise e

async def run_cli_loop(app):
    print("Assitan Kullanıma Hazır.")
    chat_history = []
    
    while True:
        user_msg = input("\nYou: ")
        if user_msg.lower() in ("exit", "quit", "q"):
            break

        # Persist history
        new_human_msg = HumanMessage(content=user_msg)
        chat_history.append(new_human_msg)

        inputs = {
            "messages": chat_history,
            "intent": "unknown"
        }
        
        print("\n" + "="*50)
        print(" FLOW STARTED: Processing your request...")
        print("="*50)

        final_response_text = ""
        async for output in app.astream(inputs, stream_mode="updates"):
            for node, data in output.items():
                print(f"\n [BASAMAK]: {node.upper()}")
                
                if node == "intent":
                    print(f"   🔍 Niyet Analiz Edildi: {data['intent']}")
                
                elif node == "tool_selection":
                    print(f"   🎯 Araç Seçimi Yapılıyor...")
                    if "messages" in data:
                        m = data["messages"][-1]
                        if hasattr(m, 'tool_calls') and m.tool_calls:
                            tools_to_call = []
                            for tc in m.tool_calls:
                                name = tc['name']
                                tools_to_call.append(name)
                                if name == "query":
                                    query_str = tc.get('args', {}).get('sql', 'Bilinmeyen Sorgu')
                                    print(f"   💾 SQL Sorgusu Oluşturuldu:\n     > {query_str}")
                                    
                            print(f"   📋 Seçilen Araçlar: {tools_to_call}")

                elif node == "tools":
                    print(f"  Araçlar Kullanıldı (Unified MCP Pool)")
                    if "messages" in data:
                        for msg in data["messages"]:
                            if hasattr(msg, 'content') and msg.content:
                                print(f"   ✅ Veri Çekildi: {msg.content[:100]}...")

                elif node == "analyst":
                    print(f"   🔬 Analist Çalışıyor...")
                    if "analysis_result" in data:
                        print(f"   📊 Analiz: {data['analysis_result'][:200]}...")
                    if "violates_rules" in data:
                        flag = "⚠️ KURAL İHLALİ VAR" if data["violates_rules"] else "✅ Kural İhlali Yok"
                        print(f"   {flag}")

                elif node == "explainer":
                    print(f"   🧠 Yapay Zeka Akıl Yürütüyor...")
                    if "messages" in data:
                        m = data["messages"][-1]
                        content = m.content
                        if isinstance(content, list):
                            text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                            final_response_text = "".join(text_parts).strip()
                        else:
                            final_response_text = str(content).strip()
                        print(f"    Öneri:\n\n{final_response_text}")


        # Capture response in history
        if final_response_text:
            chat_history.append(AIMessage(content=final_response_text))

        print("\n" + "="*50)
        print("🏁 FLOW COMPLETED")
        print("="*50)

async def run_system():
    app, exit_stack = await initialize_agent()
    if not app:
        return
        
    try:
        await run_cli_loop(app)
    finally:
        await exit_stack.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(run_system())
    except KeyboardInterrupt:
        print("\n Sonlanıyor...")
    except Exception as e:
        print(f"\n[DEBUG FULL EXCEPTION]: {repr(e)}")
        if "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ API kotası doldu. Birkaç dakika bekleyip tekrar deneyin.")
            print("   (Günlük Free Tier limiti: 20 istek. Gece 00:00'da sıfırlanır.)")
        else:
            raise
