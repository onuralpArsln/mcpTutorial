import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from mcp_adapter import create_langchain_tools
from graph import create_mcp_graph

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

            # 4. Model Setup (Gemini)
            # This model is model-agnostic in the graph, so we could switch to Claude easily
            model = ChatGoogleGenerativeAI(model="gemini-2.0-flash").bind_tools(tools)

            # 5. Graph Creation
            app = create_mcp_graph(model, tools)

            # 6. Execution Loop
            print("\nLangGraph + MCP System Ready. (Type 'exit' to quit)")
            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ("exit", "quit", "q"):
                    break

                inputs = {"messages": [HumanMessage(content=user_input)]}
                
                # Run the graph
                async for output in app.astream(inputs):
                    # For brevity, we just print the outgoing messages from nodes
                    for key, value in output.items():
                        if "messages" in value:
                            last_msg = value["messages"][-1]
                            if last_msg.content:
                                print(f"\n[{key}]: {last_msg.content}")
                            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                                for tc in last_msg.tool_calls:
                                    print(f"[{key}]: calling tool '{tc['name']}' with {tc['args']}")

if __name__ == "__main__":
    try:
        asyncio.run(run_system())
    except KeyboardInterrupt:
        pass
