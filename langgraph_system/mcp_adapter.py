from typing import Any, List, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import BaseTool
from pydantic import Field, BaseModel

class MCPTool(BaseTool):
    """A wrapper for MCP tools to make them LangChain compatible."""
    session: Any = Field(exclude=True)
    
    async def _arun(self, **kwargs) -> str:
        try:
            result = await self.session.call_tool(self.name, arguments=kwargs)
            if hasattr(result, 'content') and len(result.content) > 0:
                return result.content[0].text
            return str(result)
        except Exception as e:
            return f"Error executing tool {self.name}: {str(e)}"

    def _run(self, **kwargs) -> str:
        raise NotImplementedError("MCP tools require async execution (_arun)")

async def create_langchain_tools(session: ClientSession) -> List[BaseTool]:
    """Converts all tools in the current MCP session to LangChain BaseTool objects."""
    mcp_tools = await session.list_tools()
    langchain_tools = []
    
    for tool in mcp_tools.tools:
        # Create a dynamic LangChain Tool
        lc_tool = MCPTool(
            name=tool.name,
            description=tool.description or "No description provided",
            session=session
        )
        # Handle schema (simplified for this example, but allows arguments)
        # In a full implementation, we would map inputSchema to pydantic models
        langchain_tools.append(lc_tool)
        
    return langchain_tools
