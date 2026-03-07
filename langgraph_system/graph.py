from typing import Annotated, TypedDict, List, Dict, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from intent_registry import IntentRegistry


class AgentState(TypedDict):
    """The dynamic state of the hybrid target agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    intent: str
    
    # Context
    raw_data: str
    
    # Analysis & Safeguards
    analysis_result: str
    violates_rules: bool
    
    # Evaluator metrics
    confidence_score: int


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

    intent_model = model_with_tools.with_structured_output(IntentChoice).with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True
    )

    # -------------------------------------------------------------------------
    # Node 1: Intent Router
    # -------------------------------------------------------------------------
    async def intent_analyzer(state: AgentState):
        descriptions = registry.get_intent_descriptions()
        examples = registry.get_few_shot_examples()

        prompt = f"""Kullanıcının niyetini tespit et. SADECE aşağıdaki seçeneklerden birini seç:

{descriptions}

Örnekler:
{examples}

Yukarıdaki kategorilerden dışına ÇIKMA. Sadece seçeneklerden birini seç."""

        response = await intent_model.ainvoke(
            [HumanMessage(content=prompt)] + state["messages"]
        )
        intent = response.intent.strip().lower()
        print(f"   🔍 Niyet Analiz Edildi: {intent}")
        
        # Initialize the fresh state fields
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

        prompt = f"""Kullanıcı niyeti '{intent}', gerekli araçları kullan ve çağır."""
        response = await focused_model.ainvoke(
            [HumanMessage(content=prompt)] + state["messages"]
        )
        return {"messages": [response]}

    # -------------------------------------------------------------------------
    # Node 3: Tool Execution
    # -------------------------------------------------------------------------
    async def run_tools_node(state: AgentState):
        # We manually run the ToolNode so we can extract all output into the state `raw_data`
        tool_node = ToolNode(tools)
        result = await tool_node.ainvoke({"messages": state["messages"]})
        
        # Extract the tool message content
        raw = ""
        for msg in result["messages"]:
             if hasattr(msg, "content"):
                 raw += msg.content + "\n"
                 
        return {"messages": result["messages"], "raw_data": raw}

    # -------------------------------------------------------------------------
    # Node 4: The Analyst (Deep Track Only)
    # -------------------------------------------------------------------------
    class AnalystOutput(BaseModel):
        analysis: str
        violates_rules: bool

    async def analyst_node(state: AgentState):
        print("   🧠 Analist Devrede: Derin veri inceleniyor...")
        analyst_llm = model_plain.with_structured_output(AnalystOutput).with_retry(
             stop_after_attempt=3, wait_exponential_jitter=True
        )
        
        prompt = f"""Bir reklam yöneticisi olarak aşağıdaki verileri incele. 
        Kullanıcının niyeti: {state['intent']}
        
        Araçlardan Gelen Ham Veriler:
        {state['raw_data']}
        
        1. Verideki kalıpları ve riskleri analiz et. (Bunu 'analysis' kısmına yaz).
        2. Eğer ROAS 0 ise veya aşırı zarar eden bir durum varsa 'violates_rules' değerini true yap, aksi halde false.
        
        Bu senin içsel notundur, müşteri görmeyecek."""
        
        response = await analyst_llm.ainvoke([HumanMessage(content=prompt)])
        
        return {
            "analysis_result": response.analysis,
            "violates_rules": response.violates_rules
        }

    # -------------------------------------------------------------------------
    # Node 5: The Explainer (User Facing)
    # -------------------------------------------------------------------------
    async def explainer_node(state: AgentState):
        
        if state.get("violates_rules"):
             context_prompt = f"""Analist Notu (Kritik): {state['analysis_result']}
             SİSTEM UYARISI: Güvenlik kuralları ihlal edildi (örn: ROAS=0)."""
        elif state.get("analysis_result"):
             context_prompt = f"""Analist Notu: {state['analysis_result']}"""
        else:
             context_prompt = f"""Gelen Araç Verisi: {state['raw_data']}"""
             
        prompt = f"""Sen arkadaş canlısı, teknik olmayan kullanıcılara yardımcı olan bir asistansın.
        Kullanıcıya Türkçe yanıt ver. Asla JSON, araç veya kod terimi kullanma.
        
        Kullanıcı Mesaj Geçmişi: 
        (En sondaki istemine yanıt veriyorsun)
        
        Bağlam: 
        {context_prompt}
        
        Eğer bir güvenlik kuralı ihlali varsa (örn. harcama yapılıyor ama sıfır ciro), durumu kibarca açıkla ve işlemi (örn. bütçe artırımı) yapmanın riskli olduğunu söyle. Sadece tavsiye ver.
        """

        response = await model_plain.ainvoke(
            state["messages"] + [HumanMessage(content=prompt)]
        )
        return {"messages": [response]}

    # -------------------------------------------------------------------------
    # Node 6: Evaluator
    # -------------------------------------------------------------------------
    async def evaluator_node(state: AgentState):
        return {"confidence_score": 85}

    # -------------------------------------------------------------------------
    # Wire up the dynamic graph
    # -------------------------------------------------------------------------
    def route_after_intent(state: AgentState):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "execute_tools"
        return "explainer"
        
    def route_after_tools(state: AgentState):
         intent = state.get("intent", "")
         if intent in ["analyze", "optimize", "scale_up"]:
              return "analyst"
         return "explainer"

    workflow = StateGraph(AgentState)
    workflow.add_node("intent", intent_analyzer)
    workflow.add_node("tool_selection", tool_selector)
    workflow.add_node("execute_tools", run_tools_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("explainer", explainer_node)
    workflow.add_node("evaluator", evaluator_node)

    # Define flow
    workflow.set_entry_point("intent")
    workflow.add_edge("intent", "tool_selection")
    
    # Conditional route 1: Do we have tools to run?
    workflow.add_conditional_edges("tool_selection", route_after_intent, {
         "execute_tools": "execute_tools",
         "explainer": "explainer"
    })
    
    # Conditional route 2: Fast track or Deep track?
    workflow.add_conditional_edges("execute_tools", route_after_tools, {
         "analyst": "analyst",
         "explainer": "explainer"
    })
    
    workflow.add_edge("analyst", "explainer")
    workflow.add_edge("explainer", "evaluator")

    def check_confidence(state: AgentState):
        if state["confidence_score"] >= 70:
            return END
        return "intent"

    workflow.add_conditional_edges("evaluator", check_confidence)

    return workflow.compile()
