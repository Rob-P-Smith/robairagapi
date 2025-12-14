"""
RobAI RAG API - FastAPI Server

REST API that provides access to RAG operations via self-contained toolactions.
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
from api.tool_discovery import init_discovery_service, get_discovery_service
from api.models import (
    CrawlRequest,
    CrawlStoreRequest,
    DeepCrawlStoreRequest,
    SearchRequest,
    WebSearchRequest,
    HealthResponse,
    StatusResponse
)

# Direct imports from toolactions
from api.toolactions.operations import crawl_operations, search_operations, deep_crawl, serper_search, stats_operations
from api.toolactions.data import storage as toolactions_storage

# Load environment variables
load_dotenv()

# Crawl4AI URL for toolactions
crawl4ai_url = os.getenv("CRAWL4AI_URL", "http://localhost:11235")


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

        # Initialize tool discovery service
        tools_service_url = os.getenv("TOOLS_SERVICE_URL", "http://localhost:8099")
        tools_refresh_interval = int(os.getenv("TOOLS_REFRESH_INTERVAL", "30"))
        discovery_service = init_discovery_service(tools_service_url, tools_refresh_interval)
        print(f"🔧 Tool discovery service initialized: {tools_service_url}", flush=True)

        # Start background tasks
        asyncio.create_task(session_cleanup_task())
        asyncio.create_task(discovery_service.start_refresh_loop())


    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        print("Shutting down RAG API", flush=True)

        # Close tool discovery service HTTP client
        try:
            discovery_service = get_discovery_service()
            await discovery_service.close()
        except:
            pass


    # Middleware for request timing
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add processing time header to responses"""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
        return response

    # Middleware to log all v2 tool calls for debugging
    @app.middleware("http")
    async def log_v2_tool_calls(request: Request, call_next):
        """Log all /api/v2 requests to debug tool call format"""
        import logging
        logger = logging.getLogger("robairagapi.tool_calls")

        if request.url.path.startswith("/api/v2"):
            # Log the incoming tool call
            logger.info(f"🔧 TOOL CALL: {request.method} {request.url.path}")

            # For POST/PUT requests, log the body
            if request.method in ("POST", "PUT", "PATCH"):
                body = await request.body()
                body_str = body.decode('utf-8', errors='ignore')
                logger.info(f"🔧 TOOL BODY: {body_str[:1000]}{'...' if len(body_str) > 1000 else ''}")

                # Create a new request with the cached body
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            else:
                # GET requests - log query params if any
                if request.query_params:
                    logger.info(f"🔧 TOOL PARAMS: {dict(request.query_params)}")

        response = await call_next(request)
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

    @app.get("/api/v1/tools/list", tags=["Tools"])
    async def list_tools():
        """
        Get all available LLM tools in OpenAI function calling format.

        This is a public endpoint (no authentication required).
        Tools are cached and refreshed every 30 seconds from robaiLLMtools service.

        Returns:
            List of tool definitions in OpenAI format
        """
        try:
            discovery_service = get_discovery_service()
            tools = discovery_service.get_tools()
            stats = discovery_service.get_stats()

            return {
                "success": True,
                "tools": tools,
                "count": len(tools),
                "service_available": stats.get("service_available", False),
                "last_refresh": stats.get("last_refresh"),
                "timestamp": datetime.now().isoformat()
            }
        except RuntimeError as e:
            # Service not initialized
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Tool discovery service not initialized",
                    "tools": [],
                    "count": 0,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error listing tools: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(e),
                    "tools": [],
                    "count": 0,
                    "timestamp": datetime.now().isoformat()
                }
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

    @app.post("/api/v2/crawl", tags=["Crawling V2"])
    async def crawl_url_v2(
        request: CrawlRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """
        V2: Crawl a URL without storing it. Uses self-contained toolactions.
        Supports max_chars parameter to control response length (5000-25000 chars).
        """
        try:
            result = await crawl_operations.crawl_url(
                crawl4ai_url,
                request.url,
                max_chars=request.max_chars
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            toolactions_storage.log_error("api_crawl_url_v2", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v2/crawl/store", tags=["Crawling V2"])
    async def crawl_and_store_v2(
        request: CrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """V2: Crawl a URL and store it permanently. Uses self-contained toolactions."""
        try:
            result = await crawl_operations.crawl_and_store(
                crawl4ai_url,
                request.url,
                retention_policy=request.retention_policy or "permanent",
                tags=request.tags or ""
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            toolactions_storage.log_error("api_crawl_store_v2", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v2/crawl/temp", tags=["Crawling V2"])
    async def crawl_temp_v2(
        request: CrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """V2: Crawl a URL and store temporarily (session only). Uses self-contained toolactions."""
        try:
            result = await crawl_operations.crawl_and_store(
                crawl4ai_url,
                request.url,
                retention_policy="session_only",
                tags=request.tags or ""
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            toolactions_storage.log_error("api_crawl_temp_v2", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v2/crawl/deep/store", tags=["Crawling V2"])
    async def deep_crawl_and_store_v2(
        request: DeepCrawlStoreRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """V2: Deep crawl multiple pages and store all content. Uses self-contained toolactions."""
        try:
            # Run in thread pool to avoid blocking the API
            result = await asyncio.to_thread(
                deep_crawl.deep_crawl_and_store,
                crawl4ai_url,
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
            toolactions_storage.log_error("api_deep_crawl_v2", e, request.url)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Search Endpoints ==========

    @app.post("/api/v2/search", tags=["Search V2"])
    async def search_v2(
        request: SearchRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """V2: GraphRAG hybrid vector + graph search. Uses self-contained toolactions via robaigraphrag API."""
        try:
            result = await search_operations.search(
                term=request.term,
                depth=request.depth or "medium",
                limit=request.limit or 10
            )
            return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            toolactions_storage.log_error("api_search_v2", e, request.term)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Web Search Endpoint (Serper) ==========

    @app.post("/api/v2/web_search", tags=["Search V2"])
    async def web_search_v2(
        request: WebSearchRequest,
        session: Dict = Depends(verify_api_key)
    ):
        """V2: Web search via Serper API (Google Search). Returns titles, URLs, and snippets."""
        try:
            result = await serper_search.serper_search(
                query=request.query,
                num_results=request.num_results or 10,
                max_chars_per_result=request.max_chars_per_result or 500
            )
            return result
        except Exception as e:
            toolactions_storage.log_error("api_web_search_v2", e, request.query)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Statistics Endpoints ==========

    @app.get("/api/v2/stats", tags=["Statistics V2"])
    @app.get("/api/v2/db/stats", tags=["Statistics V2"])
    async def get_stats_v2(session: Dict = Depends(verify_api_key)):
        """V2: Get database statistics. Uses self-contained toolactions."""
        try:
            stats = await stats_operations.get_database_stats()
            return {"success": True, "stats": stats, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            toolactions_storage.log_error("api_get_stats_v2", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== System Health Endpoint V2 ==========

    @app.get("/api/v2/health/containers", tags=["System Health V2"])
    async def get_container_health(session: Dict = Depends(verify_api_key)):
        """V2: Get health status of all Docker containers."""
        import subprocess
        try:
            # Run docker ps to get all containers with their status
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            containers = {}
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        name, status, state = parts[0], parts[1], parts[2]
                        containers[name] = {
                            "status": status,
                            "state": state
                        }

            return {
                "success": True,
                "containers": containers,
                "total": len(containers),
                "timestamp": datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Docker command timed out")
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="Docker not found on system")
        except Exception as e:
            toolactions_storage.log_error("api_get_container_health", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ========== Help Endpoint ==========

    @app.get("/api/v2/help", tags=["Help"])
    async def get_help(session: Dict = Depends(verify_api_key)):
        """Get help documentation for all v2 tools"""
        help_data = {
            "success": True,
            "tools": [
                {
                    "name": "crawl_url",
                    "endpoint": "POST /api/v2/crawl",
                    "example": "Crawl https://github.com/torvalds/linux without storing",
                    "parameters": "url: string, max_chars?: number (5000-25000)"
                },
                {
                    "name": "crawl_and_store",
                    "endpoint": "POST /api/v2/crawl/store",
                    "example": "Crawl and permanently store https://github.com/anthropics/anthropic-sdk-python",
                    "parameters": "url: string, tags?: string, retention_policy?: string"
                },
                {
                    "name": "crawl_temp",
                    "endpoint": "POST /api/v2/crawl/temp",
                    "example": "Crawl and temporarily store https://news.ycombinator.com",
                    "parameters": "url: string, tags?: string"
                },
                {
                    "name": "deep_crawl_and_store",
                    "endpoint": "POST /api/v2/crawl/deep/store",
                    "example": "Deep crawl https://docs.python.org starting from main page",
                    "parameters": "url: string, max_depth?: number (1-5), max_pages?: number (1-250)"
                },
                {
                    "name": "search",
                    "endpoint": "POST /api/v2/search",
                    "example": "GraphRAG hybrid search for 'FastAPI authentication'",
                    "parameters": "term: string, depth?: string (low|medium|high), limit?: number"
                },
                {
                    "name": "get_database_stats",
                    "endpoint": "GET /api/v2/stats",
                    "example": "Get database statistics",
                    "parameters": "none"
                },
                {
                    "name": "container_health",
                    "endpoint": "GET /api/v2/health/containers",
                    "example": "Get Docker container health status",
                    "parameters": "none"
                }
            ],
            "api_info": {
                "base_url": "/api/v2",
                "authentication": "Bearer token required in Authorization header",
                "public_endpoints": {
                    "/health": {
                        "method": "GET",
                        "description": "System health check (no auth required)"
                    },
                    "/api/v1/tools/list": {
                        "method": "GET",
                        "description": "Get LLM tools in OpenAI format (no auth required)"
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
