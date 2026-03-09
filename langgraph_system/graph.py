from typing import Annotated, TypedDict, List, Dict, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

import yaml
import time
import datetime
import re
import os

from intent_registry import IntentRegistry

def _ts():
    """Returns current timestamp string for debug output."""
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

def load_prompt(prompt_name: str, **kwargs) -> str:
    """Reads a specific prompt template from prompts.yaml and formats it."""
    try:
        import os
        import yaml
        prompt_path = os.path.join(os.path.dirname(__file__), "knowledge", "prompts.yaml")
        with open(prompt_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        template = data.get(prompt_name, "")
        if template and kwargs:
            return template.format(**kwargs)
        return template
    except Exception as e:
        print(f"[{_ts()}] ERROR: Prompt Could Not Load - {prompt_name}: {e}")
        return ""

def load_schema_context() -> str:
    """Reads the database schema and aliases from YAML and formats it for the LLM."""
    try:
        import os
        schema_path = os.path.join(os.path.dirname(__file__), "knowledge", "database_schema.yaml")
        with open(schema_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        context = ""
        if "product_aliases" in data:
            context += "ÜRÜN KODLARI (Mutlaka bunları kullan):\n"
            for code, alias in data["product_aliases"].items():
                context += f"- {alias} -> {code}\n"
        
        context += "\nTABLO: product_report\n"
        # Only technical column names to avoid confusing 3B models with descriptions
        context += "KOLONLAR (SADECE BUNLARI KULLAN): id, sorgu_tarihi, urun_kodu, harcanan_butce, gosterim_sayisi, tiklanma_sayisi, reklam_cirosu, harcama_getirisi, gerceklesen_tbm, tbm_teklif, onerilen_tbm, satis_adet, net_satis, created_at, gunluk_butce\n"
        context += "HINT: ROAS = harcama_getirisi, Reklam Maliyeti = harcanan_butce\n"
                    
        if "sql_rules" in data:
            context += "\nRULES:\n"
            for rule in data["sql_rules"]:
                context += f"- {rule}\n"
                
        if "product_aliases" in data:
            context += "\nALIASES:\n"
            for code, alias in data["product_aliases"].items():
                context += f"- {alias} -> {code}\n"
                
        return context
    except Exception as e:
        return f"Şema Dosyası Okunamadı: {e}"



_PRODUCT_CODE_RE = re.compile(r'\b[A-Z][A-Z0-9]{9,}\b')

def _build_context_summary(intent: str, raw_data: str, last_human_content: str) -> str:
    """Builds a compact (~50-100 token) context summary for the next turn."""
    codes = set(_PRODUCT_CODE_RE.findall(raw_data)) | set(_PRODUCT_CODE_RE.findall(last_human_content))
    parts = [f"Önceki niyet: {intent}"]
    if codes:
        parts.append(f"Ürün kodları: {', '.join(sorted(codes))}")
    if raw_data:
        # Take only the first 200 chars of raw_data as a snippet
        snippet = raw_data[:200].replace('\n', ' ').strip()
        parts.append(f"Veri özeti: {snippet}")
    return " | ".join(parts)


class AgentState(TypedDict):
    """The dynamic state of the hybrid target agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    intent: str

    # Context
    raw_data: str
    context_summary: str

    # Analysis & Safeguards
    analysis_result: str
    violates_rules: bool


def create_mcp_graph(model_with_tools: BaseChatModel, model_plain: BaseChatModel, tools: list, registry: IntentRegistry):
    """Creates an advanced LangGraph driven by the intent registry."""

    valid_intents = registry.get_intent_names()
    IntentChoice = type(
        "IntentChoice",
        (BaseModel,),
        {
            "__annotations__": {"intent": Literal[tuple(valid_intents)]},  # type: ignore
        }
    )

    # Intent identification with structured output (for models that support it)
    # However, for small models we'll provide a fallback in the node logic.
    intent_model_structured = model_with_tools.with_structured_output(IntentChoice).with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True
    )

    # -------------------------------------------------------------------------
    # Node 1: Intent Router
    # -------------------------------------------------------------------------
    async def intent_analyzer(state: AgentState):
        descriptions = registry.get_intent_descriptions()
        examples = registry.get_few_shot_examples()

        prompt = load_prompt("intent_analyzer_prompt", descriptions=descriptions, examples=examples)
        
        last_human_msg = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        prompt_chars = len(prompt)
        msg_count = len(state["messages"])
        print(f"[{_ts()}] DEBUG INTENT ▶ ainvoke başlıyor | prompt: {prompt_chars} karakter | toplam geçmiş: {msg_count} mesaj → sadece son kullanıcı mesajı gönderiliyor")
        print(f"[{_ts()}] DEBUG INTENT ▶ Kullanılan model: model_plain (retry wrapper)")
        _t0 = time.time()
        # Only send the current user message — full history is not needed for classification
        messages_for_intent = [SystemMessage(content=prompt)]
        if last_human_msg:
            messages_for_intent.append(last_human_msg)
        response = await model_plain.ainvoke(messages_for_intent)
        _elapsed = time.time() - _t0
        print(f"[{_ts()}] DEBUG INTENT ◀ ainvoke tamamlandı | süre: {_elapsed:.2f}s")

        raw_intent = str(response.content).strip().lower()
        print(f"[{_ts()}] DEBUG INTENT ◀ Ham yanıt: '{raw_intent[:200]}'")  # truncate long responses
        
        # Simple cleanup to find the intent in the text
        intent = "unknown"
        for candidate in valid_intents:
            if candidate in raw_intent:
                intent = candidate
                break
        
        if intent == "unknown":
            intent = "info_only" # Default fallback
            print(f"⚠️ Niyet anlaşılamadı, '{intent}' olarak devam ediliyor.")

        print(f"Niyet Analiz Edildi: {intent}")
        
        return {
            "intent": intent, 
            "raw_data": "", 
            "analysis_result": "", 
            "violates_rules": False
        }

    # -------------------------------------------------------------------------
    # Node 2: Tool Selector
    # -------------------------------------------------------------------------
    async def tool_selector(state: AgentState):
        intent = state["intent"]
        intent_tools = registry.get_tools_for_intent(intent, tools)

        if not intent_tools:
            return {"messages": [AIMessage(content="")]}

        focused_model = model_with_tools.bind_tools(intent_tools).with_retry(
            stop_after_attempt=4,
            wait_exponential_jitter=True
        )

        context_summary = state.get("context_summary", "")
        context_block = f"\nÖNCEKİ BAĞLAM: {context_summary}\n" if context_summary else ""
        
        prompt = load_prompt("tool_selector_prompt", intent=intent, schema_context=load_schema_context())
        
        last_human_msg = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        prompt_chars = len(prompt)
        tool_names = [t.name for t in intent_tools]
        print(f"[{_ts()}] DEBUG TOOL_SEL ▶ ainvoke başlıyor | intent: '{intent}' | araçlar: {tool_names}")
        print(f"[{_ts()}] DEBUG TOOL_SEL ▶ prompt: {prompt_chars} karakter | toplam geçmiş: {len(state['messages'])} mesaj → sadece son kullanıcı mesajı gönderiliyor")
        _t0 = time.time()
        # Only send the current user message — history and prior tool results not needed for tool selection
        messages_for_selector = [SystemMessage(content=prompt)]
        if last_human_msg:
            messages_for_selector.append(last_human_msg)
        response = await focused_model.ainvoke(messages_for_selector)
        _elapsed = time.time() - _t0
        print(f"[{_ts()}] DEBUG TOOL_SEL ◀ ainvoke tamamlandı | süre: {_elapsed:.2f}s")
        has_tool_calls = hasattr(response, 'tool_calls') and bool(response.tool_calls)
        print(f"[{_ts()}] DEBUG TOOL_SEL ◀ tool_calls var mı: {has_tool_calls}")
        if has_tool_calls:
            for tc in response.tool_calls:
                print(f"[{_ts()}] DEBUG TOOL_SEL ◀   → araç: '{tc['name']}' | args: {tc.get('args', {})}")
        return {"messages": [response]}

    # -------------------------------------------------------------------------
    # Node 3: Tool Execution
    # -------------------------------------------------------------------------
    async def run_tools_node(state: AgentState):
        """Manually executes tools and collects results into raw_data."""
        last_msg = state["messages"][-1]
        pending_calls = last_msg.tool_calls if hasattr(last_msg, 'tool_calls') else []
        
        # --- ROBUST PARAMETER MAPPING (Fix for 3B models) ---
        user_query = ""
        for m in state["messages"]:
            if isinstance(m, HumanMessage):
                user_query = m.content.lower()

        for tc in pending_calls:
            if tc['name'] == 'query':
                args = tc.get('args', {})
                # Extract SQL from nested structure if needed
                if 'kwargs' in args and isinstance(args['kwargs'], dict):
                    inner = args['kwargs']
                    if 'sql' in inner: args['sql'] = inner['sql']
                    elif 'query' in inner: args['sql'] = inner['query']
                elif 'query' in args and 'sql' not in args:
                    args['sql'] = args['query']
                
                # Auto-fix for common 3B errors: 'ROAS' column name
                if 'sql' in args and 'ROAS' in args['sql']:
                    args['sql'] = args['sql'].replace('ROAS', 'harcama_getirisi')
                
                # Auto-fix for placeholders '?' and missing aliases
                if 'sql' in args and '?' in args['sql']:
                    # Try to find an alias in the user query and replace '?' with its code
                    schema_path = os.path.join(os.path.dirname(__file__), "knowledge", "database_schema.yaml")
                    with open(schema_path, "r") as f:
                        schema_data = yaml.safe_load(f)
                    
                    found_code = None
                    for code, alias in schema_data.get('product_aliases', {}).items():
                        if alias.lower() in user_query:
                            found_code = code
                            break
                    
                    if found_code:
                        args['sql'] = args['sql'].replace('?', f"'{found_code}'")
                    else:
                        # If no alias found, maybe it's a raw string we can find
                        pass

                # Clean up
                for k in ['query', 'kwargs', 'type']:
                    if k in args: del args[k]
        # ----------------------------------------------------

        print(f"[{_ts()}] DEBUG TOOLS ▶ {len(pending_calls)} araç çalıştırılacak: {[tc['name'] for tc in pending_calls]}")
        tool_node = ToolNode(tools)
        _t0 = time.time()
        result = await tool_node.ainvoke({"messages": state["messages"]})
        _elapsed = time.time() - _t0
        print(f"[{_ts()}] DEBUG TOOLS ◀ araç çalışması tamamlandı | süre: {_elapsed:.2f}s")
        
        raw = ""
        for msg in result["messages"]:
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                # Handle multimodal/complex outputs
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                    else:
                        text_parts.append(str(part))
                raw += "\n".join(text_parts) + "\n"
            else:
                raw += str(content) + "\n"
                  
        print(f"✅ Araçlar Tamamlandı. Veri boyutu: {len(raw)} karakter.")
        return {"messages": result["messages"], "raw_data": raw}

    # -------------------------------------------------------------------------
    # Node 4: The Analyst (Deep Track Only)
    # -------------------------------------------------------------------------
    class AnalystOutput(BaseModel):
        analysis: str
        violates_rules: bool

    async def analyst_node(state: AgentState):
        print(f"[{_ts()}] DEBUG ANALYST ▶ Analist devreye giriyor | raw_data boyutu: {len(state.get('raw_data', ''))} karakter")
        # If model_plain is wrapped in RunnableRetry, we need its base to use structured output
        base_llm = getattr(model_plain, "bound", model_plain)
        print(f"[{_ts()}] DEBUG ANALYST ▶ base_llm tipi: {type(base_llm).__name__}")
        analyst_llm = base_llm.with_structured_output(AnalystOutput).with_retry(
             stop_after_attempt=3, wait_exponential_jitter=True
        )

        prompt = load_prompt("analyst_node_prompt", intent=state['intent'], raw_data=state['raw_data'])

        print(f"[{_ts()}] DEBUG ANALYST ▶ ainvoke başlıyor | prompt: {len(prompt)} karakter")
        _t0 = time.time()
        response = await analyst_llm.ainvoke([HumanMessage(content=prompt)])
        _elapsed = time.time() - _t0
        print(f"[{_ts()}] DEBUG ANALYST ◀ ainvoke tamamlandı | süre: {_elapsed:.2f}s")
        print(f"[{_ts()}] DEBUG ANALYST ◀ violates_rules: {response.violates_rules}")
        
        return {
            "analysis_result": response.analysis,
            "violates_rules": response.violates_rules
        }

    # -------------------------------------------------------------------------
    # Node 5: The Explainer (User Facing)
    # -------------------------------------------------------------------------
    async def explainer_node(state: AgentState):
        """Generates the final human-readable response."""
        print(f"[{_ts()}] DEBUG EXPLAINER ▶ Explainer devreye giriyor")
        print(f"[{_ts()}] DEBUG EXPLAINER ▶ violates_rules: {state.get('violates_rules')} | analysis_result var mı: {bool(state.get('analysis_result'))} | raw_data boyutu: {len(state.get('raw_data',''))} karakter")
        
        if state.get("violates_rules"):
             context_prompt = f"Analist Notu (Kritik): {state['analysis_result']}\nSİSTEM UYARISI: Güvenlik kuralları ihlal edildi (örn: ROAS=0)."
        elif state.get("analysis_result"):
             context_prompt = f"Analist Notu: {state['analysis_result']}"
        else:
             context_prompt = f"Veri Özeti:\n{state['raw_data']}"
             
        prompt = load_prompt("explainer_node_prompt", context_prompt=context_prompt)

        # Build message list: system + optional previous AI turn + current human message
        last_human_msg = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        prev_ai_msg = next(
            (m for m in reversed(state["messages"])
             if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)),
            None
        )
        messages_for_llm = [SystemMessage(content=prompt)]
        if prev_ai_msg:
            messages_for_llm.append(prev_ai_msg)
        if last_human_msg:
             messages_for_llm.append(last_human_msg)

        print(f"[{_ts()}] DEBUG EXPLAINER ▶ ainvoke başlıyor | prompt: {len(prompt)} karakter | mesaj sayısı: {len(messages_for_llm)} (önceki AI mesajı: {prev_ai_msg is not None})")
        _t0 = time.time()
        response = await model_plain.ainvoke(messages_for_llm)
        _elapsed = time.time() - _t0
        print(f"[{_ts()}] DEBUG EXPLAINER ◀ ainvoke tamamlandı | süre: {_elapsed:.2f}s")
        print(f"[{_ts()}] DEBUG EXPLAINER ◀ yanıt uzunluğu: {len(str(response.content))} karakter")

        # Build compact context_summary for the next turn
        last_human_content = last_human_msg.content if last_human_msg else ""
        new_context_summary = _build_context_summary(
            state.get("intent", ""), state.get("raw_data", ""), last_human_content
        )
        return {"messages": [response], "context_summary": new_context_summary}

    # -------------------------------------------------------------------------
    # Wire up the dynamic graph
    # -------------------------------------------------------------------------
    def route_after_intent(state: AgentState):
        last_msg = state["messages"][-1]
        has_tool_calls = hasattr(last_msg, "tool_calls") and bool(last_msg.tool_calls)
        route = "tools" if has_tool_calls else "explainer"
        print(f"[{_ts()}] DEBUG ROUTE ▶ tool_selection sonrası yönlendirme: '{route}' (tool_calls var mı: {has_tool_calls})")
        return route

    def route_after_tools(state: AgentState):
        intent = state.get("intent", "")
        route_type = registry.get_route_type_for_intent(intent)
        route = "analyst" if route_type in ["deep_track", "orchestration"] else "explainer"
        print(f"[{_ts()}] DEBUG ROUTE ▶ tools sonrası yönlendirme: '{route}' (intent: '{intent}', route_type: '{route_type}')")
        return route

    workflow = StateGraph(AgentState)
    workflow.add_node("intent", intent_analyzer)
    workflow.add_node("tool_selection", tool_selector)
    workflow.add_node("tools", run_tools_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("explainer", explainer_node)

    # Define flow
    workflow.set_entry_point("intent") #bşlangıç
    workflow.add_edge("intent", "tool_selection") # hep sabit sıra 
    
    # Conditional route 1: Do we have tools to run?
    workflow.add_conditional_edges("tool_selection", route_after_intent, {
         "tools": "tools",
         "explainer": "explainer"
    })
    
    # Conditional route 2: Fast track or Deep track?
    workflow.add_conditional_edges("tools", route_after_tools, {
         "analyst": "analyst",
         "explainer": "explainer"
    })
    
    workflow.add_edge("analyst", "explainer")
    workflow.add_edge("explainer", END)

    return workflow.compile()
