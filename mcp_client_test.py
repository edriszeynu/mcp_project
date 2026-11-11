import os
from typing import Any

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": f"https://api.tavily.com/mcp/?tavily_api_key={TAVILY_API_KEY}",
        }
    }
)

_tavily_search_tool: Any | None = None


async def get_all_tools():
    tools = await client.get_tools()
    print("\nAvailable tools:")
    for tool in tools:
        print(tool.name)


async def tavily_mcp_search(query: str):
    global _tavily_search_tool

    if _tavily_search_tool is None:
        tools = await client.get_tools()
        _tavily_search_tool = next(
            (tool for tool in tools if tool.name == "tavily_search"), None
        )
        if _tavily_search_tool is None:
            raise ValueError("MCP tool 'tavily_search' was not found.")

    return await _tavily_search_tool.ainvoke({"query": query})
