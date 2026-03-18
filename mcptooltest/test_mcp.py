import asyncio
import json
import sys
import os
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def list_tools(config_path: str):
    """Parses an MCP config and lists all tools from the connected servers."""
    if not os.path.exists(config_path):
        print(f"❌ Error: Config file not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON: {e}")
            return

    servers = config.get("mcpServers", {})
    if not servers:
        print("⚠️ No mcpServers found in config.")
        return

    # Use AsyncExitStack to safely manage the stdio sessions
    async with AsyncExitStack() as exit_stack:
        for name, cfg in servers.items():
            print(f"\n--- 🔌 Testing Connection to Server: '{name}' ---")
            command = cfg.get("command")
            args = cfg.get("args", [])
            env = cfg.get("env", os.environ.copy())
            
            if not command:
                print(f"❌ Error: 'command' required for server '{name}'")
                continue

            print(f"Command: {command}")
            if args:
                print(f"Args: {args}")

            params = StdioServerParameters(command=command, args=args, env=env)
            
            try:
                # 1. Start the process
                read, write = await exit_stack.enter_async_context(stdio_client(params))
                # 2. Attach the MCP session
                session = await exit_stack.enter_async_context(ClientSession(read, write))
                # 3. Initialize communication
                await session.initialize()
                
                # 4. Fetch tools
                result = await session.list_tools()
                
                print(f"✅ Connection successful!")
                print(f"🔍 Found {len(result.tools)} tool(s):\n")
                
                for i, tool in enumerate(result.tools, 1):
                    # We print the tool name and description. These match the LangChain bindings.
                    print(f"[{i}] Tool Name: {tool.name}")
                    print(f"    Description: {tool.description}")
                    
                    if tool.inputSchema:
                        print(f"    Input Schema: {json.dumps(tool.inputSchema, indent=2)}")
                    print()
                
                # 5. Execute a specific SQL query
                #query = "SELECT * FROM product_report ORDER BY id DESC LIMIT 100"
                #query = "SELECT DISTINCT urun_kodu FROM product_report"
                query = "SELECT DISTINCT reklam_kodu FROM store_report"
                print(f"\n🚀 Executing query: {query}")
                try:
                    query_result = await session.call_tool("query", arguments={"sql": query})
                    print("\n📊 Query Result:")
                    for content in query_result.content:
                        if content.type == "text":
                            print(content.text)
                        else:
                            print(content)
                except Exception as e:
                    print(f"❌ Failed to execute query via 'query' tool (trying 'read_query' next): {e}")
                    try:
                        query_result = await session.call_tool("read_query", arguments={"sql": query})
                        print("\n📊 Query Result:")
                        for content in query_result.content:
                            if content.type == "text":
                                print(content.text)
                            else:
                                print(content)
                    except Exception as e2:
                        print(f"❌ Failed to execute query via 'read_query' tool: {e2}")
                
            except FileNotFoundError:
                print(f"❌ Failed: Command '{command}' not found on OS.")
            except Exception as e:
                print(f"❌ Failed to connect or list tools for '{name}': {type(e).__name__} - {e}")
            
            print("-" * 50)

if __name__ == "__main__":
    # Default to config.json in the same directory, or take via argument
    default_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    config_file = default_config
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    print(f"📂 Using config from: {config_file}")
    try:
        asyncio.run(list_tools(config_file))
    except KeyboardInterrupt:
        print("\nCanceled by user.")
