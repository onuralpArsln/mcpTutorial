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
    """The complex state of the final target agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    intent: str
    metrics: Dict
    rules: List[str]
    confidence_score: int
    compliance_approved: bool


def create_mcp_graph(model_with_tools: BaseChatModel, model_plain: BaseChatModel, tools: list, registry: IntentRegistry):
    """Creates an advanced LangGraph driven by the intent registry.

    Args:
        model_with_tools: LLM bound to tools — used for tool selection only.
        model_plain: Plain LLM with no tools — used for reasoning/text output.
        tools: Full list of ALL LangChain tools loaded from MCP server.
        registry: IntentRegistry instance loaded from intents.yaml.
    """

    # Build a Pydantic model dynamically from registry intent names
    # This locks the model to only return VALID intent keys — no more hallucination.
    valid_intents = registry.get_intent_names()
    IntentChoice = type(
        "IntentChoice",
        (BaseModel,),
        {
            "__annotations__": {"intent": Literal[tuple(valid_intents)]},  # type: ignore
        }
    )

    # Build the structured output router model
    # We apply with_retry AFTER with_structured_output
    intent_model = model_with_tools.with_structured_output(IntentChoice).with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True
    )

    # -------------------------------------------------------------------------
    # Node 1: Intent Router — powered by registry, locked by Pydantic
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
        return {"intent": intent}

    # -------------------------------------------------------------------------
    # Node 2: Tool Selector — only receives the narrow, intent-specific tools
    # -------------------------------------------------------------------------
    async def tool_selector(state: AgentState):
        intent = state["intent"]
        intent_tools = registry.get_tools_for_intent(intent, tools)

        if not intent_tools:
            # No tools for this intent — skip directly to reasoning
            return {"messages": [AIMessage(content="")]}

        # Build a focused model for this tool call with only the relevant tools
        # We apply with_retry AFTER bind_tools
        focused_model = model_with_tools.bind_tools(intent_tools).with_retry(
            stop_after_attempt=4,
            wait_exponential_jitter=True
        )

        intent_desc = registry.get_intent_descriptions()
        prompt = f"""Kullanıcı niyeti '{intent}', gerekli araçları kullan ve çağır."""

        response = await focused_model.ainvoke(
            [HumanMessage(content=prompt)] + state["messages"]
        )
        return {"messages": [response]}

    # -------------------------------------------------------------------------
    # Node 3: Tool Execution (LangGraph built-in ToolNode)
    # -------------------------------------------------------------------------
    tool_node = ToolNode(tools)

    # -------------------------------------------------------------------------
    # Node 4: Reasoning — uses model_plain (no tools) to generate text output
    # -------------------------------------------------------------------------
    async def reasoning_engine(state: AgentState):
        prompt = """Verileri analiz et ve kullanıcıya Türkçe, net bir yanıt ver.
        Eğer ürün listesi geldiyse mutlaka listele.
        Eğer maliyet verisi varsa tablo gibi sun.
        Eğer performans verisi varsa ilgili stratejik kurallarla karşılaştırarak yorum yap.
        İnsani ve profesyonel bir üslup kullan. Kesinlikle araç çağırma, sadece metin yaz."""

        response = await model_plain.ainvoke(
            state["messages"] + [HumanMessage(content=prompt)]
        )
        return {"messages": [response]}

    # -------------------------------------------------------------------------
    # Node 5: Evaluator
    # -------------------------------------------------------------------------
    async def evaluator_node(state: AgentState):
        return {"confidence_score": 85}

    # -------------------------------------------------------------------------
    # Wire up the graph
    # -------------------------------------------------------------------------
    def should_use_tools(state: AgentState):
        """If the last message has tool calls, route to ToolNode. Otherwise skip."""
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"
        return "reasoning"

    workflow = StateGraph(AgentState)
    workflow.add_node("intent", intent_analyzer)
    workflow.add_node("tool_selection", tool_selector)
    workflow.add_node("tools", tool_node)
    workflow.add_node("reasoning", reasoning_engine)
    workflow.add_node("evaluator", evaluator_node)

    workflow.set_entry_point("intent")
    workflow.add_edge("intent", "tool_selection")
    workflow.add_conditional_edges("tool_selection", should_use_tools)
    workflow.add_edge("tools", "reasoning")
    workflow.add_edge("reasoning", "evaluator")

    def check_confidence(state: AgentState):
        if state["confidence_score"] >= 70:
            return END
        return "intent"

    workflow.add_conditional_edges("evaluator", check_confidence)

    return workflow.compile()
