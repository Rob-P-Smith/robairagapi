import sys
from typing import Dict, Any
import httpx
import os


async def get_database_stats() -> Dict[str, Any]:
    """
    Get comprehensive database statistics from GraphRAG Neo4j database

    Retrieves detailed metrics about the knowledge graph including entity counts,
    relationship statistics, top entities, and recent additions.

    Returns:
        Dict with:
            - success: bool - Whether request succeeded
            - entity_count: int - Total entities
            - relationship_count: int - Total entity-to-entity relationships
            - chunk_count: int - Total chunks
            - document_count: int - Total documents
            - database_size_mb: float - Estimated database size
            - avg_relationships_per_chunk: float - Average relationships per chunk
            - top_entities: list - Top 10 most occurring entities
                - entity_name: str - Entity display name
                - entity_type: str - Entity classification
                - occurrence_count: int - Chunks mentioning this entity
            - isolated_entity_count: int - Entities not connected to any chunks
            - last_addition_time: str - ISO timestamp of last document added
            - recent_urls: list - Last 5 URLs added
                - url: str - Document URL
                - title: str - Document title
                - added_at: str - ISO timestamp
                - chunk_count: int - Number of chunks
            - error: str (if failed)

    Example:
        stats = await get_database_stats()
        if stats["success"]:
            print(f"Database contains {stats['entity_count']} entities")
            print(f"Top entity: {stats['top_entities'][0]['entity_name']}")
    """
    try:
        # Get GraphRAG API URL from environment
        graphrag_url = os.getenv("ROBAIGRAPHRAG_URL", "http://localhost:8089")
        api_key = os.getenv("OPENAI_API_KEY", "")

        if not api_key:
            return {
                "success": False,
                "error": "OPENAI_API_KEY environment variable not set",
                "entity_count": 0,
                "relationship_count": 0,
                "chunk_count": 0,
                "document_count": 0
            }

        print(f"Fetching GraphRAG database statistics from {graphrag_url}",
              file=sys.stderr, flush=True)

        # Call GraphRAG db-stats API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{graphrag_url}/api/v1/db-stats",
                headers={
                    "Authorization": f"Bearer {api_key}"
                }
            )
            response.raise_for_status()
            result = response.json()

        print(f"Database stats: {result.get('entity_count', 0)} entities, "
              f"{result.get('relationship_count', 0)} relationships, "
              f"{result.get('chunk_count', 0)} chunks, "
              f"{result.get('document_count', 0)} documents",
              file=sys.stderr, flush=True)

        # Add success flag
        result["success"] = True
        return result

    except httpx.HTTPStatusError as e:
        error_msg = f"GraphRAG API error {e.response.status_code}: {e.response.text}"
        print(f"Error: {error_msg}", file=sys.stderr, flush=True)
        return {
            "success": False,
            "error": error_msg,
            "entity_count": 0,
            "relationship_count": 0,
            "chunk_count": 0,
            "document_count": 0
        }
    except Exception as e:
        print(f"Error fetching database stats: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "entity_count": 0,
            "relationship_count": 0,
            "chunk_count": 0,
            "document_count": 0
        }
