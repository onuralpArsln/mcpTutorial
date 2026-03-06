import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

def get_llm(model_role: str = "tools") -> BaseChatModel:
    """
    Returns an LLM instance based on the LLM_PROVIDER environment variable.
    
    Args:
        model_role: "tools" for the LLM that picks tools, "plain" for the reasoning LLM.
                    This allows using different models for different tasks if needed.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Ensure we pick a tool-capable model for the 'tools' role, like llama3.1
        model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
        
        return ChatOllama(
            base_url=base_url,
            model=model_name,
            temperature=0
        )
        
    elif provider == "gemini":
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0
        )
        
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use 'gemini' or 'ollama'.")
