"""
Data storage client for robaigraphrag API

Sends all storage operations to the robaigraphrag API instead of managing local database.
"""

import os
import sys
import logging
import traceback
import httpx
from datetime import datetime
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


def log_error(calling_function: str, error: Exception, url: str = "", error_code: str = ""):
    """Log errors to stderr"""
    timestamp = datetime.now().isoformat()
    error_message = str(error)
    stack_trace = traceback.format_exc()

    log_entry = f"{timestamp}|{calling_function}|{url}|{error_message}|{error_code}|{stack_trace}"
    print(f"Error logged: {calling_function} - {error_message}", file=sys.stderr, flush=True)


class GraphRAGClient:
    """
    HTTP client for robaigraphrag API

    Sends content storage requests to the GraphRAG service which handles:
    - Neo4j graph database storage
    - Entity and relationship extraction
    - Vector embeddings
    - Graph-based search
    """

    def __init__(self, api_url: str = None):
        """
        Initialize GraphRAG client

        Args:
            api_url: Base URL of robaigraphrag API (default: http://localhost:8089)
        """
        self.api_url = api_url or os.getenv("ROBAIGRAPHRAG_URL", "http://localhost:8089")
        self.api_key = os.getenv("OPENAI_API_KEY", "")

        if not self.api_key:
            print("⚠️  WARNING: OPENAI_API_KEY not set - GraphRAG API calls will fail",
                  file=sys.stderr, flush=True)

        print(f"✓ GraphRAG client initialized: {self.api_url}", file=sys.stderr, flush=True)

    async def store_content(
        self,
        url: str,
        title: str,
        content: str,
        markdown: str,
        retention_policy: str = 'permanent',
        tags: str = '',
        metadata: Optional[Dict[str, Any]] = None,
        content_id: int = None
    ) -> Dict[str, Any]:
        """
        Store content in GraphRAG database via API

        Sends content to robaigraphrag API which handles:
        - Entity extraction
        - Relationship extraction
        - Vector embedding generation
        - Neo4j graph storage

        Args:
            url: Document URL
            title: Document title
            content: Plain text content
            markdown: Markdown formatted content (preferred)
            retention_policy: Retention policy (permanent, session_only, 30_days)
            tags: Comma-separated tags
            metadata: Optional metadata dict
            content_id: Optional content ID from vector DB

        Returns:
            Dict with success status and results
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "OPENAI_API_KEY not set - cannot authenticate with GraphRAG API",
                    "url": url
                }

            # Use markdown if available, otherwise use content
            content_to_send = markdown if markdown else content

            # Generate content_id if not provided (use hash of URL)
            if content_id is None:
                import hashlib
                content_id = int(hashlib.sha256(url.encode()).hexdigest()[:8], 16)

            # Build metadata
            if metadata is None:
                metadata = {}

            metadata.update({
                "retention_policy": retention_policy,
                "tags": tags
            })

            # Prepare request payload
            payload = {
                "content_id": content_id,
                "url": url,
                "title": title,
                "markdown": content_to_send,
                "metadata": {
                    "retention_policy": retention_policy,
                    "tags": tags,
                    "source": "crawl4ai",
                    "user": "Robert P Smith"
                }
            }

            print(f"📤 Sending to GraphRAG: {url} (content_id={content_id}, {len(content_to_send)} chars)",
                  file=sys.stderr, flush=True)

            # Call GraphRAG ingest API
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_url}/api/v1/ingest",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            # Check if queued (async processing)
            if result.get("status") == "accepted":
                print(f"✓ Content queued for GraphRAG processing: {url} (queue_id={result.get('queue_id')})",
                      file=sys.stderr, flush=True)
                return {
                    "success": True,
                    "content_id": content_id,
                    "url": url,
                    "status": "queued",
                    "queue_id": result.get("queue_id"),
                    "queue_size": result.get("queue_size")
                }

            # Immediate processing result
            print(f"✓ Content stored in GraphRAG: {url} (content_id={content_id})",
                  file=sys.stderr, flush=True)

            return {
                "success": True,
                "content_id": content_id,
                "url": url,
                **result
            }

        except httpx.HTTPStatusError as e:
            error_msg = f"GraphRAG API error {e.response.status_code}: {e.response.text}"
            print(f"❌ {error_msg}", file=sys.stderr, flush=True)
            log_error("store_content", Exception(error_msg), url)
            return {
                "success": False,
                "error": error_msg,
                "url": url
            }
        except Exception as e:
            print(f"❌ Error storing content: {str(e)}", file=sys.stderr, flush=True)
            log_error("store_content", e, url)
            return {
                "success": False,
                "error": str(e),
                "url": url
            }


# Global singleton instance
GLOBAL_DB = GraphRAGClient()
print(f"✓ Storage client ready: robaigraphrag @ {GLOBAL_DB.api_url}", file=sys.stderr, flush=True)
