import asyncio
import os

import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

Tavily_API_KEY = os.getenv("TAVILY_API_KEY")


client = MultiServerMCPClient({
"tavily":{
    "transport":"streamable_http",
    "url":f"https://api.tavily.com/mcp/?tavily_api_key={Tavily_API_KEY}",
}
})



async def get_all_tools():
    tools = await client.get_tools()
    print("\nAvailable tools:")
    for tool in tools:
        print(tool.name)