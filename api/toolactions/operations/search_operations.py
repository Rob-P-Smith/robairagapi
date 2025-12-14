import sys
from typing import Dict, Any
import httpx
import os


async def search(term: str, depth: str = "medium", limit: int = 10) -> Dict[str, Any]:
    """
    Search the GraphRAG knowledge graph using hybrid vector + graph search

    Combines Neo4j HNSW vector similarity with graph traversal for intelligent
    context retrieval. Automatically expands search via entity relationships
    to find semantically related content.

    Search Depths:
    - low: Pure vector search (fastest, ~150ms)
    - medium: 1-hop graph expansion (balanced, ~2s)
    - high: 2-hop graph expansion (broader, ~500ms)
    - all: 3-hop graph expansion (comprehensive, ~750ms)

    Args:
        term: Search query or topic (e.g., "vllm configuration", "react hooks")
        depth: Search depth - "low", "medium", "high", or "all" (default: "medium")
        limit: Maximum number of chunks to return, 1-500 (default: 10)

    Returns:
        Dict with:
            - success: bool - Whether search succeeded
            - results: list - Matching chunks with metadata
                - chunk_id: str - Unique chunk identifier
                - text: str - Chunk content text
                - similarity_score: float - Vector similarity (0-1)
                - matched_entities: list - Entities found in chunk
                - relationships: list - Entity relationships
            - total_chunks: int - Number of results returned
            - search_depth_used: str - Depth level used
            - entities_found: int - Total unique entities
            - processing_time_ms: float - Query execution time
            - error: str (if failed)

    Example:
        # Quick vector search
        result = await search("python async patterns", depth="low", limit=5)

        # Balanced graph search
        result = await search("docker configuration", depth="medium", limit=10)

        # Deep exploration
        result = await search("machine learning", depth="high", limit=20)
    """
    try:
        # Get GraphRAG API URL from environment
        graphrag_url = os.getenv("GRAPHRAG_API_URL", "http://localhost:8089")
        api_key = os.getenv("OPENAI_API_KEY", "")

        # Validate depth parameter
        valid_depths = ["low", "medium", "high", "all"]
        if depth not in valid_depths:
            return {
                "success": False,
                "error": f"Invalid depth '{depth}'. Must be one of: {', '.join(valid_depths)}",
                "results": [],
                "total_chunks": 0
            }

        # Validate limit
        if not 1 <= limit <= 500:
            return {
                "success": False,
                "error": f"Invalid limit {limit}. Must be between 1 and 500",
                "results": [],
                "total_chunks": 0
            }

        print(f"GraphRAG search: '{term}' (depth={depth}, limit={limit})",
              file=sys.stderr, flush=True)

        # Call GraphRAG search API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{graphrag_url}/api/v1/search",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "term": term,
                    "depth": depth,
                    "limit": limit
                }
            )
            response.raise_for_status()
            result = response.json()

        print(f"GraphRAG search complete: {result.get('total_chunks', 0)} chunks, "
              f"{result.get('processing_time_ms', 0):.0f}ms",
              file=sys.stderr, flush=True)

        return result

    except httpx.HTTPStatusError as e:
        error_msg = f"GraphRAG API error {e.response.status_code}: {e.response.text}"
        print(f"Error: {error_msg}", file=sys.stderr, flush=True)
        return {
            "success": False,
            "error": error_msg,
            "results": [],
            "total_chunks": 0
        }
    except Exception as e:
        print(f"Error in GraphRAG search: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "total_chunks": 0
        }
