import asyncio
import os
import json
import yaml
import sys
from datetime import datetime
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. SETUP ENVIRONMENT
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))

# Constants
MCP_CONFIG_PATH = os.path.join(root_dir, "mcp_config.json")
SCHEMA_PATH = os.path.join(root_dir, "langgraph_system", "knowledge", "database_schema.yaml")

def load_schema():
    """Loads the database schema for the system prompt."""
    if not os.path.exists(SCHEMA_PATH):
        return "Schema not found."
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.dump(yaml.safe_load(f), allow_unicode=True)

async def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Simple Agent Starting...")
    
    # 2. GEMINI CLIENT (DIRECT)
    api_key = os.getenv("GOOGLE_API_KEY")
    # Using gemini-1.5-flash for higher rate limits than 2.0-flash-lite
    model_id = "gemini-2.5-flash"
    client = genai.Client(api_key=api_key)
    
    # 3. MCP CONNECTION (ONLY POSTGRES/DATABASE)
    exit_stack = AsyncExitStack()
    
    if not os.path.exists(MCP_CONFIG_PATH):
        print("Error: mcp_config.json missing.")
        return

    with open(MCP_CONFIG_PATH, "r") as f:
        mcp_config = json.load(f)
    
    # Connect to first postgresql server found
    db_session = None
    for name, cfg in mcp_config.get("mcpServers", {}).items():
        if "postgres" in name.lower() or "sql" in name.lower():
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg["args"],
                env=os.environ.copy()
            )
            read, write = await exit_stack.enter_async_context(stdio_client(params))
            db_session = await exit_stack.enter_async_context(ClientSession(read, write))
            await db_session.initialize()
            print(f"✅ Connected to Database: {name}")
            break
    
    if not db_session:
        print("❌ No database server found in mcp_config.json")
        return

    schema_context = load_schema()
    chat_history = []

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ready. Type 'q' to exit.")

    try:
        while True:
            query = input("\n👤 Question: ").strip()
            if query.lower() in ['q', 'exit', 'quit']: break
            if not query: continue

            # STEP 2 & 3: Ask Gemini how to solve it (Directly ask for SQL)
            # We always send the schema and instruct it to use the 'query' tool or just write the SQL.
            step1_prompt = f"""You are a SQL expert. Based on the user question and the database schema below, write the CORRECT SQL query to answer it.
            
SCHEMA:
{schema_context}

IMPORTANT: 
- Return ONLY the SQL query.
- Use aggregation (SUM) where appropriate.
- Today is {datetime.now().strftime('%Y-%m-%d')}.

USER QUESTION: {query}
"""
            print("⏳ Generating SQL...")
            response1 = client.models.generate_content(model=model_id, contents=step1_prompt)
            sql_query = response1.text.strip().replace("```sql", "").replace("```", "").strip()
            
            # STEP 5: Log SQL
            print(f"💾 SQL TO RUN:\n{sql_query}")

            # STEP 6: Execute SQL
            db_result = "No results found."
            try:
                # We assume the tool name is 'query' as per standard postgres mcp
                res = await db_session.call_tool("query", arguments={"sql": sql_query})
                if res.content:
                    db_result = res.content[0].text
                
                # LOG RESULT TO TERMINAL
                print(f"📊 SQL RESULT:\n{db_result}")
            except Exception as e:
                db_result = f"SQL Execution Error: {e}"
                print(f"❌ SQL ERROR: {e}")
            
            # STEP 6 (cont): Final Answer
            final_prompt = f"""User asked: {query}
            
Based on the following data retrieved from the database, please provide a clear and concise answer in Turkish.

DATABASE RESULT:
{db_result}

CHAT HISTORY:
{chat_history[-5:] if chat_history else "None"}

Ensure your answer is friendly and does not show technical details.
"""
            print("🧠 Thinking about result...")
            response2 = client.models.generate_content(model=model_id, contents=final_prompt)
            final_answer = response2.text
            
            # STEP 7: Report back
            print(f"\n🤖 Bot: {final_answer}")
            
            # Save history
            chat_history.append({"user": query, "sql": sql_query, "bot": final_answer})

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await exit_stack.aclose()
        print("Connections closed.")

if __name__ == "__main__":
    asyncio.run(main())