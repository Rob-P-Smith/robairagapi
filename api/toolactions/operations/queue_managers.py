import asyncio
from typing import Dict, Any, List
from urllib.parse import urlparse


class DeepCrawlManager:
    """
    Manages active deep crawl sessions

    Tracks crawl progress, visited URLs, queued URLs, and session metadata.
    Supports session status queries and progress updates.
    """

    def __init__(self):
        self.active_crawls = {}
        self.crawl_queue = []

    def create_crawl_session(self, url: str, max_depth: int = 2, max_pages: int = 10) -> str:
        """
        Initialize a new deep crawl session

        Args:
            url: Starting URL for the crawl
            max_depth: Maximum depth to crawl
            max_pages: Maximum pages to crawl

        Returns:
            str: Unique session ID for this crawl
        """
        import uuid
        session_id = str(uuid.uuid4())

        self.active_crawls[session_id] = {
            "url": url,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "visited": set(),
            "to_visit": [(url, 0)],
            "results": [],
            "base_domain": urlparse(url).netloc,
            "start_time": asyncio.get_event_loop().time(),
            "status": "running",
            "progress": {"pages_crawled": 0, "total_pages": max_pages}
        }

        return session_id

    def get_crawl_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status of a crawl session

        Args:
            session_id: Unique session identifier

        Returns:
            Dict with crawl status, progress, and timing information
        """
        if session_id not in self.active_crawls:
            return {"error": "Crawl session not found"}

        crawl = self.active_crawls[session_id]
        return {
            "session_id": session_id,
            "url": crawl["url"],
            "status": crawl["status"],
            "progress": crawl["progress"],
            "pages_crawled": len(crawl["visited"]),
            "total_pages": crawl["max_pages"],
            "duration_seconds": asyncio.get_event_loop().time() - crawl["start_time"]
        }

    def update_progress(self, session_id: str, pages_crawled: int):
        """
        Update crawl progress for a session

        Args:
            session_id: Unique session identifier
            pages_crawled: Number of pages crawled so far
        """
        if session_id in self.active_crawls:
            self.active_crawls[session_id]["progress"]["pages_crawled"] = pages_crawled

    def add_to_queue(self, page_data: Dict[str, Any]):
        """
        Add page data to the crawl queue

        Args:
            page_data: Dictionary containing page information
        """
        self.crawl_queue.append(page_data)

    def get_queue_status(self) -> Dict[str, int]:
        """
        Get current queue status

        Returns:
            Dict with queue size and total pages
        """
        return {"queue_size": len(self.crawl_queue), "total_pages": sum(1 for item in self.crawl_queue)}

    def clear_crawl_session(self, session_id: str):
        """
        Remove a crawl session from active sessions

        Args:
            session_id: Unique session identifier to remove
        """
        if session_id in self.active_crawls:
            del self.active_crawls[session_id]


class QueueManager:
    """
    Manages the ingestion queue for batch processing

    Handles queueing, batching, and removal of crawled pages
    awaiting processing or storage.
    """

    def __init__(self):
        self.ingestion_queue = []

    def add_to_queue(self, page_data: Dict[str, Any]):
        """
        Add page data to the ingestion queue

        Args:
            page_data: Dictionary containing page information
        """
        self.ingestion_queue.append(page_data)

    def get_batch(self, batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve a batch of items from the queue

        Args:
            batch_size: Maximum number of items to retrieve

        Returns:
            List of page data dictionaries
        """
        if len(self.ingestion_queue) < batch_size:
            return self.ingestion_queue.copy()

        return self.ingestion_queue[:batch_size]

    def remove_batch(self, batch: List[Dict[str, Any]]):
        """
        Remove processed batch items from the queue

        Args:
            batch: List of items to remove
        """
        for item in batch:
            if item in self.ingestion_queue:
                self.ingestion_queue.remove(item)

    def get_status(self) -> Dict[str, int]:
        """
        Get current queue status

        Returns:
            Dict with queue size
        """
        return {"queue_size": len(self.ingestion_queue)}

    def clear_queue(self):
        """
        Clear all items from the ingestion queue
        """
        self.ingestion_queue.clear()
