import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

def get_llm_by_role(role: str) -> BaseChatModel:
    """
    Returns an LLM instance based on the role indirection.
    role='cheap' -> looks for CHEAP_CONFIG variable -> e.g. 'OLLAMA_SMALL'
    Then looks for OLLAMA_SMALL_PROVIDER, OLLAMA_SMALL_MODEL, etc.
    """
    env_prefix = role.upper()
    # 1. Get the profile id for this role (e.g. CHEAP_CONFIG)
    config_id = os.getenv(f"{env_prefix}_CONFIG")
    
    # Fallback to old behavior or default if CONFIG is missing
    if not config_id:
        print(f"[LLM_FACTORY] Warning: {env_prefix}_CONFIG not set. Falling back to default Gemini profile.")
        config_id = "GEMINI_DEFAULT"
        # Ensure we have some default settings if the env is totally empty
        if not os.getenv("GEMINI_DEFAULT_PROVIDER"):
             os.environ["GEMINI_DEFAULT_PROVIDER"] = "gemini"
             os.environ["GEMINI_DEFAULT_MODEL"] = os.getenv("EXPENSIVE_MODEL", "gemini-2.5-flash-lite")

    # 2. Get the provider for this profile
    provider = os.getenv(f"{config_id}_PROVIDER", "gemini").lower()
    
    if provider == "ollama":
        base_url = os.getenv(f"{config_id}_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        model_name = os.getenv(f"{config_id}_MODEL", "llama3.1")
        print(f"[LLM_FACTORY] Role: {role} | Profile: {config_id} | Provider: ollama | Model: {model_name}")
        return ChatOllama(
            base_url=base_url,
            model=model_name,
            temperature=0
        )

    elif provider == "gemini":
        model_name = os.getenv(f"{config_id}_MODEL", "gemini-2.5-flash-lite")
        print(f"[LLM_FACTORY] Role: {role} | Profile: {config_id} | Provider: gemini | Model: {model_name}")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0
        )
        
    else:
        raise ValueError(f"Unknown provider '{provider}' for config id '{config_id}'.")
