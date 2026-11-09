import os

import requests


class WebSearchError(RuntimeError):
    """Raised when Tavily cannot return web search results."""


def web_search(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise WebSearchError("TAVILY_API_KEY is missing. Add it to your .env file.")

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code == 401:
            message = "Tavily rejected the API key. Check TAVILY_API_KEY in .env."
        elif status_code == 403:
            message = (
                "Tavily denied this request (HTTP 403). Check whether the endpoint "
                "is blocked by the network or whether your Tavily account has access."
            )
        elif status_code == 402:
            message = "Tavily requires available plan credits for web search."
        elif status_code == 429:
            message = "Tavily web search rate limit or quota was reached."
        else:
            message = f"Tavily web search request failed: {error}"
        raise WebSearchError(message) from error

    payload = response.json()
    search_results = payload.get("results")
    if not isinstance(search_results, list):
        raise WebSearchError("Tavily returned an invalid search response.")

    formatted = []
    for item in search_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        title = item.get("title") or "Web search result"
        content = (item.get("content") or "").strip()
        if len(content) > 500:
            content = content[:500].rsplit(" ", 1)[0] + "..."
        formatted.append(
            f"{len(formatted) + 1}. **{title}**\n  {url}\n  {content}"
        )

    if not formatted:
        raise WebSearchError("Tavily returned no search results.")

    return "\n\n".join(formatted)
