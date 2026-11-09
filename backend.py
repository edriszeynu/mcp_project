import os
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid

from pymongo import MongoClient

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from tools.flight_tool import search_flights
from tools.tavily_search import WebSearchError, web_search

MAX_QUERY_CHARS = 1500
MAX_FLIGHT_CONTEXT_CHARS = 3500


def get_mongodb_uri():
    mongodb_uri = os.getenv("MONGODB_URI")

    if not mongodb_uri:
        raise ValueError(
            "MONGODB_URI is missing. Please add your MongoDB connection string to .env"
        )

    return mongodb_uri


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# =========================
# LLM
# =========================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=GROQ_API_KEY,
)

# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    query = state["user_query"][:MAX_QUERY_CHARS]
    flight_data = search_flights(query, limit=3)

    return {
        "flight_results": flight_data[:MAX_FLIGHT_CONTEXT_CHARS],
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    query = f"Hotels and accommodations for {state['user_query']}"
    try:
        hotel_results = web_search(query)
    except WebSearchError as error:
        hotel_results = (
            f"Live hotel web search is unavailable: {error}\n"
            "Do not present unverified hotel listings or prices. Ask the traveler "
            "to check current options with a booking provider."
        )

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




# =========================
# Itinerary Agent
# =========================

def itinerary_agent(state: TravelState):
    prompt = f"""Create the complete final travel plan in one response. Keep it concise.

User request (may be shortened):
{state['user_query'][:MAX_QUERY_CHARS]}

Flight data (may be shortened):
{state['flight_results'][:MAX_FLIGHT_CONTEXT_CHARS]}

Hotel guidance:
{state['hotel_results']}

Use these sections: Trip Summary, Flight Information, Hotel Suggestions,
Day-by-Day Itinerary, Estimated Budget, Final Recommendations.
Do not invent live flight fares, hotel listings, prices, or availability.
Make the itinerary practical and budget-aware. Clearly identify estimates."""

    response = llm.invoke([
        SystemMessage(content="You are a concise, reliable travel planner."),
        HumanMessage(content=prompt),
    ], max_tokens=1200)

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Final Response Agent
# =========================

def final_agent(state: TravelState):
    return {
        "messages": [AIMessage(content=state["itinerary"])]
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# =========================
# MongoDB Checkpointer
# =========================
mongodb_client = MongoClient(
    get_mongodb_uri(),
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
)
mongodb_client.admin.command("ping")

checkpointer = MongoDBSaver(
    mongodb_client,
    db_name=os.getenv("MONGODB_DATABASE", "tripmate"),
)

travel_graph = graph.compile(checkpointer=checkpointer)



# =========================
# Function for FastAPI
# =========================

def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }