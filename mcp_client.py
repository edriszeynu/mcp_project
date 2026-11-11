import os
from typing import Any

import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

Tavily_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY = os.getenv("AVIATION_STACK_API_KEY")


client = MultiServerMCPClient({
"tavily":{
    "transport":"streamable_http",
    "url":f"https://api.tavily.com/mcp/?tavily_api_key={Tavily_API_KEY}",
},
"aviation": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "aviation-mcp"],
    "env": {"API_NINJA_KEY": AVIATION_STACK_API_KEY},
},
})

async def get_all_tools():
    tools = await client.get_tools()
    print("\nAvailable tools:")
    for tool in tools:
        print(tool.name)



tools_by_name = None


async def _get_tools_by_name():
    global tools_by_name
    if tools_by_name is None:
        tools = await client.get_tools()
        tools_by_name = {tool.name: tool for tool in tools}
    return tools_by_name


async def tavily_mcp_search(query: str):
    tools = await _get_tools_by_name()
    tool = tools.get("tavily_search")
    if tool is None:
        raise ValueError("MCP tool 'tavily_search' was not found.")
    return await tool.ainvoke({"query": query})


async def aviation_mcp_call(
    tool_name: str, tool_args: dict[str, Any] | None = None
):
    tools = await _get_tools_by_name()
    tool = tools.get(tool_name)
    if tool is None:
        raise ValueError(f"MCP tool {tool_name!r} was not found.")
    return await tool.ainvoke(tool_args or {})





