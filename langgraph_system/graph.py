from typing import Annotated, TypedDict, Union, List
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models.chat_models import BaseChatModel

class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[List[BaseMessage], "The messages in the conversation"]

def create_mcp_graph(model: BaseChatModel, tools: list):
    """Creates a LangGraph that uses the provided tools."""
    
    # Define the function that calls the model
    async def call_model(state: AgentState):
        messages = state['messages']
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    # Define the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    def should_continue(state: AgentState):
        last_message = state['messages'][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges(
        "agent",
        should_continue,
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()
