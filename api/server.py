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


def simplify_schema(schema: dict) -> dict:
    """Recursively simplify OpenAPI schema by removing anyOf patterns."""
    import copy

    # Deep copy to avoid modifying original
    result = copy.deepcopy(schema)

    if isinstance(result, dict):
        # Handle anyOf pattern
        if "anyOf" in result:
            # Extract the non-null type
            for option in result["anyOf"]:
                if isinstance(option, dict) and option.get("type") != "null":
                    # Replace anyOf with the non-null type
                    non_null_schema = copy.deepcopy(option)
                    # Preserve parent-level fields
                    for key in ["title", "description", "default"]:
                        if key in result and key not in non_null_schema:
                            non_null_schema[key] = result[key]
                    # Remove anyOf
                    result = non_null_schema
                    break

        # Clean up numeric constraints (1000.0 -> 1000)
        for key in ["maximum", "minimum"]:
            if key in result and isinstance(result[key], float):
                if result[key].is_integer():
                    result[key] = int(result[key])

        # Recursively process nested objects
        for key, value in list(result.items()):
            if isinstance(value, dict):
                result[key] = simplify_schema(value)
            elif isinstance(value, list):
                result[key] = [simplify_schema(item) if isinstance(item, dict) else item for item in value]

    return result


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

        # Database initialization no longer needed - KGServiceClient is HTTP-only
        print("✅ Database client ready (kg-service HTTP)", flush=True)

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
    async def health_check():
        """Health check endpoint (no authentication required for Docker healthchecks)"""
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
        """
        KG Search - Full 5-Phase Knowledge Graph Pipeline:

        Complete comprehensive search using all phases:
        - Phase 1: GLiNER entity extraction + query embedding
        - Phase 2: Parallel vector + Neo4j graph search
        - Phase 3: KG-powered entity expansion (configurable)
        - Phase 4: Multi-signal ranking (5 signals: vector similarity, graph connectivity, entity density, recency, tag match)
        - Phase 5: Context extraction and formatted results

        Returns separate RAG and KG result sets with full context.
        Most comprehensive search for complex queries requiring deep knowledge graph analysis.
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

            # Initialize SearchHandler (5-phase pipeline)
            handler = SearchHandler(
                db_manager=GLOBAL_DB,
                kg_service_url=kg_service_url
            )

            # Execute 5-phase search
            result = await asyncio.to_thread(
                handler.search_separate,
                query=request.query,
                rag_limit=request.rag_limit or 5,
                kg_limit=request.kg_limit or 10,
                tags=tags_list,
                enable_expansion=request.enable_expansion if hasattr(request, 'enable_expansion') else True,
                include_context=request.include_context if hasattr(request, 'include_context') else True
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
        Enhanced Search - Optimized KG Search with Focused Results:

        Returns focused, high-quality results optimized for manageable data transfer:
        - 1 top RAG vector result (100K character limit)
        - 10 KG chunks with targeted entity mentions
        - 1 top KG document (100K character limit, guaranteed different URL from RAG)

        Pipeline:
        - GLiNER entity extraction
        - Parallel vector search + Neo4j graph search (fetches 250 chunks)
        - Chunk aggregation to documents (up to 20 documents)
        - Entity density ranking
        - Top result selection

        Data Size: ~200-250KB (90% smaller than full pipeline)
        Best for: Getting comprehensive context with controlled data size
        """
        try:
            import asyncio
            from robaimodeltools.search.enhanced_search import get_enhanced_search_orchestrator

            # Parse tags
            tags_list = None
            if request.tags:
                tags_list = [tag.strip() for tag in request.tags.split(',') if tag.strip()]

            # Get KG service URL from environment
            kg_service_url = os.getenv("KG_SERVICE_URL", "http://localhost:8088")

            # Initialize EnhancedSearchOrchestrator
            orchestrator = get_enhanced_search_orchestrator(
                db_manager=GLOBAL_DB,
                kg_service_url=kg_service_url
            )

            # Execute enhanced search (returns: rag_result, kg_chunks, kg_document)
            result = await asyncio.to_thread(
                orchestrator.search,
                query=request.query,
                rag_limit=request.rag_limit or 1,
                kg_limit=request.kg_limit or 10,
                tags=tags_list
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
                    "parameters": "query: string, limit?: number (default 10, max 1000), tags?: string (comma-separated), min_similarity?: number (default 0.2), max_content_length?: number (default 10000)"
                },
                {
                    "name": "kg_search",
                    "example": "Full 5-phase KG pipeline: 'React performance optimization' - comprehensive entity extraction, graph traversal, and multi-signal ranking",
                    "parameters": "query: string, rag_limit?: number (default 5), kg_limit?: number (default 10), tags?: string, enable_expansion?: boolean (default true), include_context?: boolean (default true)",
                    "description": "Complete 5-phase knowledge graph search: GLiNER entity extraction, parallel vector+graph search (Neo4j), KG entity expansion, multi-signal ranking (5 signals: vector similarity, graph connectivity, entity density, recency, tag match), context extraction. Most comprehensive search for complex queries requiring deep knowledge graph analysis."
                },
                {
                    "name": "enhanced_search",
                    "example": "Optimized KG search for 'FastAPI async patterns' - Returns 1 top RAG result + 10 entity-rich chunks + 1 top KG document",
                    "parameters": "query: string, rag_limit?: number (default 1), kg_limit?: number (default 10), tags?: string",
                    "description": "Optimized search returning focused results: 1 top RAG vector result (100K char limit), 10 KG chunks (targeted entity mentions), 1 top KG document (100K char limit, different URL from RAG). Fetches 250 chunks from KG service, aggregates to 20 documents, returns top-ranked results. Best for getting comprehensive context with manageable data size (~200-250KB vs 1-4MB)."
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

    # Custom OpenAPI schema generator with simplified schemas for Cline compatibility
    def custom_openapi():
        """Generate OpenAPI schema with simplified schemas (no anyOf patterns)."""
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        # Generate base schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Simplify all component schemas
        if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
            for schema_name, schema_def in openapi_schema["components"]["schemas"].items():
                openapi_schema["components"]["schemas"][schema_name] = simplify_schema(schema_def)

        # Simplify all path parameter schemas
        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                for method, operation in path_item.items():
                    if method in ["get", "post", "put", "delete", "patch"]:
                        # Simplify requestBody schemas
                        if "requestBody" in operation:
                            operation["requestBody"] = simplify_schema(operation["requestBody"])
                        # Simplify parameter schemas
                        if "parameters" in operation:
                            operation["parameters"] = [simplify_schema(p) for p in operation["parameters"]]

        # Cache the simplified schema
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    # Override the openapi method
    app.openapi = custom_openapi

    return app


# Create app instance
app = create_app()
