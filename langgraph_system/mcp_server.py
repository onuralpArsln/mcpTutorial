# langgraph_system/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os
import difflib
import platform

# Specialized server for LangGraph experimentation
mcp = FastMCP("LangGraph-Experimental-Server")

# --- Core Tools (copied from original for baseline) ---

@mcp.tool()
def dosya_yaz(dosya_adi: str, icerik: str) -> str:
    """Creates a new file and writes content to it."""
    try:
        # Step out once to reach the root project directory from langgraph_system/
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(root_path, dosya_adi)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(icerik)
        return f"{dosya_adi} created successfully in root."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def notlari_listele() -> str:
    """Lists all .txt files in the root directory."""
    try:
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dosyalar = [f for f in os.listdir(root_path) if f.endswith('.txt')]
        if not dosyalar:
            return "No notes found in root."
        return "Notes:\n" + "\n".join(f"- {d}" for d in dosyalar)
    except Exception as e:
        return f"Error: {str(e)}"

# --- Experimental Tools (New!) ---

@mcp.tool()
def rag_search(query: str) -> str:
    """Simulates a RAG (Retrieval Augmented Generation) search in a knowledge base."""
    # This is a mock for now
    knowledge_base = {
        "mcp": "Model Context Protocol (MCP) is an open standard that enables developers to build secure, two-way integrations between their data sources and AI models.",
        "langgraph": "LangGraph is a library for building stateful, multi-actor applications with LLMs, used to create agent and multi-agent workflows.",
        "gemini": "Gemini is a family of generative AI models developed by Google."
    }
    
    query_lower = query.lower()
    for key, value in knowledge_base.items():
        if key in query_lower:
            return f"[RAG RESULT for '{key}']: {value}"
    
    return f"No specific RAG entry found for '{query}'. Try searching for 'mcp', 'langgraph', or 'gemini'."

@mcp.tool()
def system_info() -> str:
    """Returns basic system information (OS, Python version)."""
    return f"OS: {platform.system()} {platform.release()} | Python: {platform.python_version()}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
