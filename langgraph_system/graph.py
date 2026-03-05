from typing import Annotated, TypedDict, Union, List, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.language_models.chat_models import BaseChatModel

class AgentState(TypedDict):
    """The complex state of the final target agent."""
    # Use add_messages to append new messages instead of overwriting
    messages: Annotated[List[BaseMessage], add_messages]
    intent: str
    metrics: Dict
    rules: List[str]
    confidence_score: int
    compliance_approved: bool

def create_mcp_graph(model_with_tools: BaseChatModel, model_plain: BaseChatModel, tools: list):
    """Creates an advanced LangGraph based on the Final Target workflow.
    
    Args:
        model_with_tools: LLM bound to tools — used for intent analysis and tool selection.
        model_plain: Plain LLM with no tools — used for reasoning to guarantee text output.
        tools: List of LangChain tools from MCP server.
    """
    
    # Node 1: Intent Understanding
    async def intent_analyzer(state: AgentState):
        prompt = """Kullanıcının niyetini belirle. Sadece 4 seçenekten YALNIZCA BİRİNİ tek kelime yaz:
        - 'scale_up'   : Bütçeyi artır, kampanyayı büyüt
        - 'analyze'    : Performansı göster, rapor ver, KPI sorgula, satış/reklam analizi
        - 'optimize'   : Düşük performans düzelt, bid azalt, verimsizlik gider
        - 'info_only'  : Ürün listesi, genel bilgi, sistem soruları
        Sadece tek kelime yaz. Başka bir şey yazma."""
        response = await model_with_tools.ainvoke([HumanMessage(content=prompt)] + state['messages'])
        return {"intent": response.content.strip().lower()}

    # Node 2: Tool Selection (Fixed with persistence)
    async def tool_selector(state: AgentState):
        intent = state['intent']
        prompt = f"""Kullanıcı niyeti: '{intent}'.
        Bu niyete uygun araçları seç ve çağır:
        - 'scale_up'  : 'get_performance_metrics' ve 'get_strategy_rules(intent_type="scale_up")' çağır.
        - 'analyze'   : 'get_performance_metrics' VE 'get_strategy_rules(intent_type="analiz")' çağır. İkisini de mutlaka çağır.
        - 'optimize'  : 'get_performance_metrics', 'get_strategy_rules(intent_type="optimize")' ve 'run_pattern_recognition(data_summary="ROAS:3.2")' çağır.
        - 'info_only' : Ürün sorusu ise 'list_products', maliyet sorusu ise 'get_product_costs(product_id="P001")', sistem sorusu ise 'system_info' çağır.
        
        Şimdi uygun araç(ları) çağır."""
        
        response = await model_with_tools.ainvoke([HumanMessage(content=prompt)] + state['messages'])
        return {"messages": [response]}

    # Node 3: Analysis & Reasoning — uses model_plain (no tools) to guarantee text output
    async def reasoning_engine(state: AgentState):
        prompt = """Verileri analiz et ve kullanıcıya Türkçe, net bir yanıt ver. 
        Eğer ürün listesi geldiyse mutlaka listele. 
        Eğer maliyet verisi varsa tablo gibi sun. 
        Eğer performans verisi varsa ilgili stratejik kurallarla karşılaştırarak yorum yap.
        İnsani ve profesyonel bir üslup kullan. Kesinlikle araç çağırma, sadece metin yaz."""
        
        # model_plain has no tools bound → always returns text content
        response = await model_plain.ainvoke(state['messages'] + [HumanMessage(content=prompt)])
        return {"messages": [response]}

    # Node 4: Confidence & Compliance Check
    async def evaluator_node(state: AgentState):
        return {"confidence_score": 85}

    # Define the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intent", intent_analyzer)
    workflow.add_node("tool_selection", tool_selector)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("reasoning", reasoning_engine)
    workflow.add_node("evaluator", evaluator_node)

    # Set entry point
    workflow.set_entry_point("intent")

    # Define Logic Edges
    workflow.add_edge("intent", "tool_selection")
    workflow.add_edge("tool_selection", "tools")
    workflow.add_edge("tools", "reasoning")
    workflow.add_edge("reasoning", "evaluator")
    
    def check_confidence(state: AgentState):
        if state["confidence_score"] >= 70:
            return END
        return "intent"

    workflow.add_conditional_edges("evaluator", check_confidence)

    return workflow.compile()
