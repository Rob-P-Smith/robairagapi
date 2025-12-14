"""
Tool Discovery Service - HTTP-based tool discovery from robaiLLMtools

Fetches tool definitions via HTTP from robaiLLMtools service on port 8099.
Caches results and refreshes every 30 seconds.
Pure microservices architecture - no cross-project imports.
"""

import logging
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class ToolDiscoveryService:
    """
    HTTP-based tool discovery service.

    Features:
    - Fetches tools from robaiLLMtools:8099 via HTTP GET
    - 30-second refresh cycle
    - Thread-safe caching
    - Graceful error handling
    """

    def __init__(self, tools_service_url: str = "http://localhost:8099", refresh_interval: int = 30):
        """
        Initialize tool discovery service.

        Args:
            tools_service_url: URL for robaiLLMtools service (default: http://localhost:8099)
            refresh_interval: How often to refresh tool cache in seconds (default: 30)
        """
        self.tools_service_url = tools_service_url.rstrip('/')
        self.refresh_interval = refresh_interval
        self.tools: List[Dict[str, Any]] = []
        self.last_refresh: Optional[datetime] = None
        self.service_available = False
        self._lock = threading.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None

        # Initial discovery (sync version for __init__)
        logger.info(f"🔍 Initializing tool discovery from {self.tools_service_url}")

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def _fetch_tools(self) -> List[Dict[str, Any]]:
        """
        Fetch tools from robaiLLMtools service via HTTP GET.

        Returns:
            List of tool definitions in OpenAI format
        """
        try:
            client = await self._get_http_client()
            url = f"{self.tools_service_url}/tools"

            logger.debug(f"Fetching tools from {url}")
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            tools = data.get("tools", [])

            with self._lock:
                self.tools = tools
                self.last_refresh = datetime.now()
                self.service_available = True

            logger.info(f"✅ Fetched {len(tools)} tools from robaiLLMtools")
            return tools

        except httpx.HTTPError as e:
            logger.warning(f"⚠️  HTTP error fetching tools: {e}")
            with self._lock:
                self.service_available = False
            return []

        except Exception as e:
            logger.error(f"❌ Error fetching tools: {e}", exc_info=True)
            with self._lock:
                self.service_available = False
            return []

    async def refresh_tools(self) -> Dict[str, Any]:
        """
        Manually trigger tool refresh.

        Returns:
            Dict with refresh statistics
        """
        logger.info("🔄 Manual refresh requested...")

        with self._lock:
            old_count = len(self.tools)

        new_tools = await self._fetch_tools()
        new_count = len(new_tools)

        result = {
            'success': self.service_available,
            'total_tools': new_count,
            'previous_count': old_count,
            'added': max(0, new_count - old_count),
            'removed': max(0, old_count - new_count),
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
            'service_available': self.service_available
        }

        if new_count != old_count:
            logger.info(f"  Tool count changed: {old_count} → {new_count}")
        else:
            logger.info(f"  ✅ No changes ({new_count} tools)")

        return result

    async def start_refresh_loop(self):
        """
        Start background task for periodic tool refresh.
        Automatically fetches new tools every 30 seconds.
        """
        logger.info(f"🔁 Starting tool refresh loop (every {self.refresh_interval}s)")

        # Initial fetch
        await self._fetch_tools()

        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self._fetch_tools()
            except asyncio.CancelledError:
                logger.info("Tool refresh loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}", exc_info=True)
                # Continue loop even on error

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get cached tool definitions.

        Returns:
            List of tool definitions in OpenAI format
        """
        with self._lock:
            return self.tools.copy()

    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool by name.

        Args:
            tool_name: Name of the tool (e.g., "crawler_search")

        Returns:
            Tool definition or None if not found
        """
        with self._lock:
            for tool in self.tools:
                if tool.get("function", {}).get("name") == tool_name:
                    return tool
        return None

    def get_tool_names(self) -> List[str]:
        """
        Get list of all tool names.

        Returns:
            Sorted list of tool names
        """
        with self._lock:
            names = [tool.get("function", {}).get("name") for tool in self.tools if "function" in tool]
            return sorted([name for name in names if name])

    def get_stats(self) -> Dict[str, Any]:
        """
        Get tool discovery statistics.

        Returns:
            Dict with discovery stats
        """
        with self._lock:
            return {
                'total_tools': len(self.tools),
                'service_available': self.service_available,
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
                'refresh_interval_seconds': self.refresh_interval,
                'tools_service_url': self.tools_service_url
            }

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Global instance (initialized in server.py startup)
_global_discovery_service: Optional[ToolDiscoveryService] = None


def get_discovery_service() -> ToolDiscoveryService:
    """
    Get global tool discovery service instance.

    Returns:
        ToolDiscoveryService instance

    Raises:
        RuntimeError: If service not initialized
    """
    global _global_discovery_service
    if _global_discovery_service is None:
        raise RuntimeError("Tool discovery service not initialized. Call init_discovery_service() first.")
    return _global_discovery_service


def init_discovery_service(
    tools_service_url: str = "http://localhost:8099",
    refresh_interval: int = 30
) -> ToolDiscoveryService:
    """
    Initialize global tool discovery service.

    Args:
        tools_service_url: URL for robaiLLMtools service
        refresh_interval: Refresh interval in seconds (default: 30)

    Returns:
        Initialized ToolDiscoveryService instance
    """
    global _global_discovery_service
    _global_discovery_service = ToolDiscoveryService(tools_service_url, refresh_interval)
    return _global_discovery_service
