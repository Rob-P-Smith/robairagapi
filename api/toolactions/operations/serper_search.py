import sys
import os
from typing import Dict, Any
import httpx


async def serper_search(query: str, num_results: int = 20, max_chars_per_result: int = 500) -> Dict[str, Any]:
    """
    Search the web using Serper API (Google Search) with per-result content length limits

    Performs a web search and returns the top results with snippet content.
    Each result is individually limited by character count (title + snippet combined).

    IMPORTANT FOR LLM: You can control the response length by setting max_chars_per_result
    between 1000 and 15000 characters. Adjust this based on how much detail you need:
    - 1000-2000: Brief snippets (default: 2000)
    - 3000-5000: Moderate detail
    - 6000-15000: Comprehensive content per result

    Args:
        query: Search query string
        num_results: Maximum number of results to return (1-10, default: 3)
        max_chars_per_result: Maximum characters per result, title+snippet combined
                             (1000-15000, default: 2000). LLM can adjust this value.

    Returns:
        Dict with:
            - success: bool - Whether search succeeded
            - query: str - Original search query
            - results: list - List of search results
                - title: str - Page title
                - link: str - URL of the page
                - snippet: str - Text snippet from the page
            - total_results: int - Number of results returned
            - total_chars: int - Total character count of all snippets
            - truncated: bool - Whether any results were truncated
            - max_chars_per_result: int - Character limit used per result
            - error: str (if failed)

    Example:
        # Default brief snippets
        result = await serper_search("python async patterns", num_results=3)

        # Request more detailed results
        result = await serper_search("react architecture", num_results=2, max_chars_per_result=5000)
    """
    try:
        # Get Serper API key from environment
        api_key = os.getenv("SERPER_API_KEY", "")

        if not api_key:
            return {
                "success": False,
                "query": query,
                "error": "SERPER_API_KEY environment variable not set",
                "results": [],
                "total_results": 0,
                "total_chars": 0,
                "truncated": False
            }

        # Validate parameters
        if not 1 <= num_results <= 20:
            return {
                "success": False,
                "query": query,
                "error": f"num_results must be between 1 and 20 (got {num_results})",
                "results": [],
                "total_results": 0,
                "total_chars": 0,
                "truncated": False,
                "max_chars_per_result": max_chars_per_result
            }

        if not 100 <= max_chars_per_result <= 15000:
            return {
                "success": False,
                "query": query,
                "error": f"max_chars_per_result must be between 100 and 15000 (got {max_chars_per_result})",
                "results": [],
                "total_results": 0,
                "total_chars": 0,
                "truncated": False,
                "max_chars_per_result": max_chars_per_result
            }

        if len(query.strip()) < 2:
            return {
                "success": False,
                "query": query,
                "error": "Query must be at least 2 characters",
                "results": [],
                "total_results": 0,
                "total_chars": 0,
                "truncated": False,
                "max_chars_per_result": max_chars_per_result
            }

        print(f"Serper search: '{query}' (num_results={num_results}, max_chars_per_result={max_chars_per_result})",
              file=sys.stderr, flush=True)

        # Prepare Serper API request
        url = "https://google.serper.dev/search"

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "q": query,
            "num": num_results
        }

        # Execute search
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        # Extract organic results with per-result character limits
        results = []
        total_chars = 0
        truncated = False

        if "organic" in data:
            for item in data["organic"][:num_results]:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")

                # Calculate this result's character count (title + snippet)
                result_chars = len(title) + len(snippet)

                # Check if this individual result exceeds per-result limit
                if result_chars > max_chars_per_result:
                    # Truncate snippet to fit within per-result limit
                    available_chars = max_chars_per_result - len(title)

                    if available_chars > 100:  # Only truncate if we have at least 100 chars for snippet
                        snippet = snippet[:available_chars - 3] + "..."
                        truncated = True
                        result_chars = len(title) + len(snippet)
                    else:
                        # If title alone is too long, skip this result
                        continue

                # Add result (full or truncated)
                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet
                })
                total_chars += result_chars

        print(f"Serper search complete: {len(results)} results, {total_chars} total chars, truncated={truncated}",
              file=sys.stderr, flush=True)

        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results),
            "total_chars": total_chars,
            "truncated": truncated,
            "max_chars_per_result": max_chars_per_result
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"Serper API error {e.response.status_code}: {e.response.text}"
        print(f"Error: {error_msg}", file=sys.stderr, flush=True)
        return {
            "success": False,
            "query": query,
            "error": error_msg,
            "results": [],
            "total_results": 0,
            "total_chars": 0,
            "truncated": False,
            "max_chars_per_result": max_chars_per_result
        }
    except Exception as e:
        print(f"Error in Serper search: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {
            "success": False,
            "query": query,
            "error": str(e),
            "results": [],
            "total_results": 0,
            "total_chars": 0,
            "truncated": False,
            "max_chars_per_result": max_chars_per_result
        }
