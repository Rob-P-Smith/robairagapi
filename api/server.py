"""
RobAI RAG API - FastAPI Server

REST API that provides direct access to RAG operations via robaimodeltools shared library.
"""

import os
import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Import local modules
from api.auth import verify_api_key, log_api_request, cleanup_sessions
from api.security import security_middleware
from api.models import (
    CrawlRequest,
    CrawlStoreRequest,
    DeepCrawlStoreRequest,
    SearchRequest,
    KGSearchRequest,
    EnhancedSearchRequest,
    MemoryListRequest,
    ForgetUrlRequest,
    BlockedDomainRequest,
    UnblockDomainRequest,
    HealthResponse,
    StatusResponse
)

# Direct imports from shared robaimodeltools
from robaimodeltools.operations.crawler import Crawl4AIRAG
from robaimodeltools.data.storage import GLOBAL_DB, log_error

# Load environment variables
load_dotenv()

# Initialize RAG system
crawl4ai_url = os.getenv("CRAWL4AI_URL", "http://localhost:11235")
rag_system = Crawl4AIRAG(crawl4ai_url=crawl4ai_url)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="RobAI RAG API",
        description="REST API for RAG operations (crawling, search, KG)",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Security middleware (MUST be before CORS and other middleware)
    app.middleware("http")(security_middleware)

    # CORS middleware
    if os.getenv("ENABLE_CORS", "true").lower() == "true":
        cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Session cleanup background task
    async def session_cleanup_task():
        """Cleanup expired sessions periodically"""
        while True:
            await asyncio.sleep(3600)  # Every hour
            cleanup_sessions()

    @app.on_event("startup")
    async def startup_event():
        """Initialize components and start background tasks"""
        print("🚀 Starting RobAI RAG API", flush=True)
        print(f"   Crawl4AI URL: {crawl4ai_url}", flush=True)

        # Initialize database (critical for memory mode)
        print("📊 Initializing database...", flush=True)
        await GLOBAL_DB.initialize_async()
        print("✅ Database initialized successfully", flush=True)

        # Start background tasks
        asyncio.create_task(session_cleanup_task())

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        print("Shutting down RAG API", flush=True)

    # Middleware for request timing
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add processing time header to responses"""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
        return response

    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler"""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(exc),
                "timestamp": datetime.now().isoformat()
            }
        )

    # ========== Health & Status Endpoints ==========

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check(session: Dict = Depends(verify_api_key)):
        """Health check endpoint (requires bearer token authentication)"""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            mcp_connected=True,  # Not using MCP anymore
            version="1.0.0"
        )

    @app.get("/api/v1/status", response_model=StatusResponse, tags=["System"])
    async def get_status(session: Dict = Depends(verify_api_key)):
        """Get detailed system status"""
        return StatusResponse(
            api_status="running",
            mcp_status="direct",  # Direct imports, no MCP
            timestamp=datetime.now().isoformat(),
            components={
                "crawl4ai_url": crawl4ai_url,
                "mode": "direct"
            }
        )

    # ========== Crawling Endpoints ==========

    @app.post("/api/v1/crawl", tags=["Crawling"])
    async def crawl_url(
        request: CrawlRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Crawl a URL without storing it"""
        try:
            result = await rag_system.crawl_url(request.url)
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_url", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/crawl/store", tags=["Crawling"])
    async def crawl_and_store(
        request: CrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Crawl a URL and store it permanently"""
        try:
            result = await rag_system.crawl_and_store(
                request.url,
                retention_policy=request.retention_policy or "permanent",
                tags=request.tags or ""
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_store", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/crawl/temp", tags=["Crawling"])
    async def crawl_temp(
        request: CrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Crawl a URL and store temporarily (session only)"""
        try:
            result = await rag_system.crawl_and_store(
                request.url,
                retention_policy="session_only",
                tags=request.tags or ""
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_crawl_temp", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/crawl/deep/store", tags=["Crawling"])
    async def deep_crawl_and_store(
        request: DeepCrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Deep crawl multiple pages and store all content"""
        try:
            # Run in thread pool to avoid blocking the API
            result = await asyncio.to_thread(
                rag_system.deep_crawl_and_store,
                request.url,
                retention_policy=request.retention_policy or "permanent",
                tags=request.tags or "",
                max_depth=request.max_depth or 2,
                max_pages=request.max_pages or 10,
                include_external=request.include_external or False,
                score_threshold=request.score_threshold or 0.0,
                timeout=request.timeout
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log_error("api_deep_crawl", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Search Endpoints ==========

    @app.post("/api/v1/search", tags=["Search"])
    @app.post("/api/v1/search/simple", tags=["Search"])
    async def search(
        request: SearchRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Simple vector similarity search"""
        try:
            result = await rag_system.search_knowledge(
                query=request.query,
                limit=request.limit or 5,
                tags=request.tags
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_search", e, request.query)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/search/kg", tags=["Search"])
    async def kg_search(
        request: KGSearchRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Knowledge Graph-enhanced search (uses intelligent tag-based expansion)"""
        try:
            # Use target_search which provides tag discovery and expansion
            result = await rag_system.target_search(
                query=request.query,
                initial_limit=request.rag_limit or 5,
                expanded_limit=request.kg_limit or 10
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_kg_search", e, request.query)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/search/enhanced", tags=["Search"])
    async def enhanced_search(
        request: EnhancedSearchRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """
        Enhanced Search - Predefined Optimized Search (Phase 1-5 Pipeline):

        This is a highly optimized, predefined search configuration using the complete KG pipeline:
        - Phase 1: GLiNER entity extraction + query embedding
        - Phase 2: Parallel vector + Neo4j graph search (up to 100 entities)
        - Phase 3: KG-powered entity expansion (always enabled)
        - Phase 4: Multi-signal ranking (5 signals: vector similarity, graph connectivity, entity density, recency, tag match)
        - Phase 5: Formatted results with full markdown content

        Fixed Configuration:
        - Returns exactly 3 RAG results with FULL MARKDOWN content
        - Returns exactly 5 KG results with referenced chunks
        - Entity expansion: ALWAYS ENABLED
        - Context extraction: ALWAYS ENABLED

        This is the most comprehensive search - use for complex queries requiring deep knowledge graph analysis.
        """
        try:
            import asyncio
            from robaimodeltools.search.search_handler import SearchHandler

            # Parse tags
            tags_list = None
            if request.tags:
                tags_list = [tag.strip() for tag in request.tags.split(',') if tag.strip()]

            # Get KG service URL from environment
            kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")

            # Initialize SearchHandler with complete pipeline
            handler = SearchHandler(
                db_manager=GLOBAL_DB,
                kg_service_url=kg_service_url
            )

            # Execute enhanced search with FIXED PARAMETERS (predefined optimization)
            result = await asyncio.to_thread(
                handler.search_separate,
                query=request.query,
                rag_limit=3,  # FIXED: Always return top 3 RAG results with full markdown
                kg_limit=5,   # FIXED: Always return top 5 KG results with referenced chunks
                tags=tags_list,
                enable_expansion=True,   # FIXED: Always enabled for comprehensive results
                include_context=True     # FIXED: Always enabled for context extraction
            )

            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_enhanced_search", e, request.query)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Memory Management Endpoints ==========

    @app.get("/api/v1/memory", tags=["Memory"])
    async def list_memory(
        retention_policy: str = None,
        limit: int = 100,
        session: Dict = Depends(verify_api_key)
    ):
        """List all stored content"""
        try:
            results = GLOBAL_DB.list_content(retention_policy=retention_policy, limit=limit)
            return {"success": True, "content": results, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_list_memory", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/v1/memory", tags=["Memory"])
    async def forget_url(
        url: str,
        session: Dict = Depends(verify_api_key)
    ):
        """Remove specific URL from memory"""
        try:
            GLOBAL_DB.forget(url)
            return {"success": True, "message": f"Removed {url}", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_forget_url", e, url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/v1/memory/temp", tags=["Memory"])
    async def clear_temp_memory(session: Dict = Depends(verify_api_key)):
        """Clear all temporary content"""
        try:
            GLOBAL_DB.clear_temp()
            return {"success": True, "message": "Cleared temporary content", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_clear_temp", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Statistics Endpoints ==========

    @app.get("/api/v1/stats", tags=["Statistics"])
    @app.get("/api/v1/db/stats", tags=["Statistics"])
    async def get_stats(session: Dict = Depends(verify_api_key)):
        """Get database statistics"""
        try:
            stats = GLOBAL_DB.get_database_stats()
            return {"success": True, "stats": stats, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_get_stats", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Domain Blocking Endpoints ==========

    @app.get("/api/v1/blocked-domains", tags=["Domain Management"])
    async def list_blocked_domains(session: Dict = Depends(verify_api_key)):
        """List all blocked domain patterns"""
        try:
            from robaimodeltools.operations.domain_management import list_blocked_domains as get_blocked
            domains = get_blocked()
            return {"success": True, "blocked_domains": domains, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_list_blocked", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/blocked-domains", tags=["Domain Management"])
    async def add_blocked_domain(
        request: BlockedDomainRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """Add a domain pattern to blocklist"""
        try:
            from robaimodeltools.operations.domain_management import add_blocked_domain as add_blocked
            add_blocked(request.pattern, request.keyword)
            return {"success": True, "message": f"Added {request.pattern}", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_add_blocked", e, request.pattern)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/v1/blocked-domains", tags=["Domain Management"])
    async def remove_blocked_domain(
        pattern: str,
        keyword: str,
        session: Dict = Depends(verify_api_key)
    ):
        """Remove a domain pattern from blocklist"""
        try:
            from robaimodeltools.operations.domain_management import remove_blocked_domain as remove_blocked
            remove_blocked(pattern, keyword)
            return {"success": True, "message": f"Removed {pattern}", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            log_error("api_remove_blocked", e, pattern)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Help Endpoint ==========

    @app.get("/api/v1/help", tags=["Help"])
    async def get_help(session: Dict = Depends(verify_api_key)):
        """Get help documentation for all tools (requires bearer token authentication)"""
        help_data = {
            "success": True,
            "tools": [
                {
                    "name": "crawl_url",
                    "example": "Crawl https://github.com/torvalds/linux without storing",
                    "parameters": "url: string"
                },
                {
                    "name": "crawl_and_store",
                    "example": "Crawl and permanently store https://github.com/anthropics/anthropic-sdk-python",
                    "parameters": "url: string, tags?: string, retention_policy?: string"
                },
                {
                    "name": "crawl_temp",
                    "example": "Crawl and temporarily store https://news.ycombinator.com",
                    "parameters": "url: string, tags?: string"
                },
                {
                    "name": "deep_crawl_and_store",
                    "example": "Deep crawl https://docs.python.org starting from main page",
                    "parameters": "url: string, max_depth?: number (1-5, default 2), max_pages?: number (1-250, default 10), retention_policy?: string, tags?: string, include_external?: boolean, score_threshold?: number (0.0-1.0), timeout?: number (60-1800)"
                },
                {
                    "name": "simple_search",
                    "example": "Simple vector similarity search for 'FastAPI authentication' without KG enhancement",
                    "parameters": "query: string, limit?: number (default 10, max 1000), tags?: string (comma-separated tags for filtering)"
                },
                {
                    "name": "kg_search",
                    "example": "KG-enhanced search for 'FastAPI async' with intelligent tag expansion",
                    "parameters": "query: string, rag_limit?: number (default 5, max 100), kg_limit?: number (default 10, max 100), tags?: string, enable_expansion?: boolean (default true), include_context?: boolean (default true)"
                },
                {
                    "name": "enhanced_search",
                    "example": "Advanced search using full KG pipeline: 'React performance optimization techniques' - Returns 3 RAG results with FULL MARKDOWN + 5 KG results with referenced chunks",
                    "parameters": "query: string (required), tags?: string (optional comma-separated filter)",
                    "description": "PREDEFINED OPTIMIZED SEARCH - Most comprehensive search with FIXED configuration: Always returns exactly 3 RAG results with complete markdown content and 5 KG results with referenced chunks. Uses complete 5-phase pipeline: GLiNER entity extraction, parallel vector+graph search (Neo4j), KG entity expansion (always on), multi-signal ranking, full markdown content. Entity expansion and context extraction are always enabled. Use this for complex queries requiring deep knowledge graph analysis with full content."
                },
                {
                    "name": "list_memory",
                    "example": "List all stored pages or filter by retention policy",
                    "parameters": "filter?: string (permanent|session_only|30_days), limit?: number (default 100, max 1000)"
                },
                {
                    "name": "get_database_stats",
                    "example": "Get database statistics including record counts and storage size",
                    "parameters": "none"
                },
                {
                    "name": "add_blocked_domain",
                    "example": "Block all .ru domains or URLs containing 'spam'",
                    "parameters": "pattern: string (e.g., *.ru, *.cn, *spam*, example.com), description?: string"
                },
                {
                    "name": "remove_blocked_domain",
                    "example": "Unblock a previously blocked domain pattern",
                    "parameters": "pattern: string, keyword: string (authorization)"
                },
                {
                    "name": "list_blocked_domains",
                    "example": "Show all currently blocked domain patterns",
                    "parameters": "none"
                },
                {
                    "name": "forget_url",
                    "example": "Remove specific URL from knowledge base",
                    "parameters": "url: string"
                },
                {
                    "name": "clear_temp_memory",
                    "example": "Clear all temporary/session-only content",
                    "parameters": "none"
                }
            ],
            "api_info": {
                "base_url": "/api/v1",
                "authentication": "Bearer token required in Authorization header",
                "public_endpoints": {
                    "/health": {
                        "method": "GET",
                        "description": "System health check (no auth required)",
                        "returns": "Health status of all services"
                    },
                    "/api/v1/help": {
                        "method": "GET",
                        "description": "Get tool list for LLM providers (no auth required)",
                        "returns": "Structured tool list with examples and parameters"
                    }
                },
                "formats": {
                    "retention_policy": ["permanent", "session_only", "30_days"],
                    "http_methods": {
                        "GET": ["/status", "/memory", "/stats", "/db/stats", "/blocked-domains", "/help"],
                        "POST": ["/crawl", "/crawl/store", "/crawl/temp", "/crawl/deep/store", "/search", "/search/simple", "/search/kg", "/blocked-domains"],
                        "DELETE": ["/memory", "/memory/temp", "/blocked-domains"]
                    }
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        return help_data

    return app


# Create app instance
app = create_app()
