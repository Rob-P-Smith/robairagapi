"""
Pydantic models for API request/response validation

Models match the original mcpragcrawl4ai API for backward compatibility.
"""

from typing import Optional
from pydantic import BaseModel, Field, validator
from api.validation import validate_url, validate_string_length


class CrawlRequest(BaseModel):
    """Request model for basic URL crawling"""
    url: str = Field(..., description="URL to crawl")
    max_chars: Optional[int] = Field(5000, description="Maximum characters to return (5000-25000)")

    @validator('url')
    def validate_url_field(cls, v):
        if not validate_url(v):
            raise ValueError('Invalid or unsafe URL provided')
        return v

    @validator('max_chars')
    def validate_max_chars(cls, v):
        if v is not None and v < 5000:
            raise ValueError('max_chars must be >= 5000')
        if v is not None and v > 25000:
            raise ValueError('max_chars must be <= 25000')
        return v if v is not None else 5000


class CrawlStoreRequest(CrawlRequest):
    """Request model for crawling and storing content"""
    tags: Optional[str] = Field("", description="Optional tags for organization")
    retention_policy: Optional[str] = Field("permanent", description="Storage policy (permanent, session_only, 30_days)")

    @validator('tags')
    def validate_tags(cls, v):
        return validate_string_length(v or "", 255, "tags")


class DeepCrawlRequest(CrawlRequest):
    """Request model for deep crawling without storage"""
    max_depth: Optional[int] = Field(2, ge=1, le=5, description="Maximum depth to crawl")
    max_pages: Optional[int] = Field(10, ge=1, le=250, description="Maximum pages to crawl")
    include_external: Optional[bool] = Field(False, description="Follow external domain links")
    score_threshold: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum URL score")
    timeout: Optional[int] = Field(None, ge=60, le=1800, description="Timeout in seconds")


class DeepCrawlStoreRequest(DeepCrawlRequest):
    """Request model for deep crawling with storage"""
    tags: Optional[str] = Field("", description="Optional tags for organization")
    retention_policy: Optional[str] = Field("permanent", description="Storage policy")

    @validator('tags')
    def validate_tags(cls, v):
        return validate_string_length(v or "", 255, "tags")


class SearchRequest(BaseModel):
    """Request model for GraphRAG hybrid vector + graph search"""
    term: str = Field(..., description="Search term or query")
    depth: Optional[str] = Field("medium", description="Search depth: low, medium, high, or all")
    limit: Optional[int] = Field(10, ge=1, le=500, description="Maximum number of results (1-500)")

    @validator('term')
    def validate_term(cls, v):
        return validate_string_length(v, 500, "term")

    @validator('depth')
    def validate_depth(cls, v):
        if v not in ["low", "medium", "high", "all"]:
            raise ValueError(f"Invalid depth '{v}'. Must be: low, medium, high, or all")
        return v


class WebSearchRequest(BaseModel):
    """Request model for web search via Serper API"""
    query: str = Field(..., description="Search query string")
    num_results: Optional[int] = Field(10, ge=1, le=20, description="Maximum number of results (1-20)")
    max_chars_per_result: Optional[int] = Field(500, ge=100, le=15000, description="Max characters per result snippet")

    @validator('query')
    def validate_query(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Query must be at least 2 characters")
        return validate_string_length(v, 500, "query")


class KGSearchRequest(BaseModel):
    """Request model for Knowledge Graph-enhanced search"""
    query: str = Field(..., description="Search query")
    rag_limit: Optional[int] = Field(1, ge=1, le=5, description="Number of RAG (vector) results")
    kg_limit: Optional[int] = Field(3, ge=1, le=10, description="Number of KG (graph) results")
    tags: Optional[str] = Field(None, description="Comma-separated tags to filter by")
    enable_expansion: Optional[bool] = Field(True, description="Enable KG entity expansion")
    include_context: Optional[bool] = Field(True, description="Include context snippets")

    @validator('query')
    def validate_query(cls, v):
        return validate_string_length(v, 500, "query")

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return validate_string_length(v, 500, "tags")
        return v


class EnhancedSearchRequest(BaseModel):
    """Request model for Enhanced Search - Optimized search with focused results"""
    query: str = Field(..., description="Search query")
    rag_limit: Optional[int] = Field(1, ge=1, le=5, description="Number of RAG (vector) results")
    kg_limit: Optional[int] = Field(10, ge=1, le=20, description="Number of KG chunks to return")
    tags: Optional[str] = Field(None, description="Comma-separated tags to filter by")

    @validator('query')
    def validate_query(cls, v):
        return validate_string_length(v, 500, "query")

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return validate_string_length(v, 500, "tags")
        return v


class MemoryListRequest(BaseModel):
    """Request model for listing stored content"""
    filter: Optional[str] = Field(None, description="Filter by retention policy (permanent, session_only, 30_days)")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Maximum number of results")

    @validator('filter')
    def validate_filter(cls, v):
        if v:
            return validate_string_length(v, 500, "filter")
        return v


class ForgetUrlRequest(BaseModel):
    """Request model for removing specific URL from memory"""
    url: str = Field(..., description="URL to remove")

    @validator('url')
    def validate_url_field(cls, v):
        if not validate_url(v):
            raise ValueError('Invalid or unsafe URL provided')
        return v


class BlockedDomainRequest(BaseModel):
    """Request model for adding blocked domain pattern"""
    pattern: str = Field(..., description="Domain pattern to block (e.g., *.ru, *spam*, example.com)")
    description: Optional[str] = Field("", description="Optional description of why pattern is blocked")

    @validator('pattern')
    def validate_pattern(cls, v):
        return validate_string_length(v, 255, "pattern")

    @validator('description')
    def validate_description(cls, v):
        return validate_string_length(v or "", 500, "description")


class UnblockDomainRequest(BaseModel):
    """Request model for removing blocked domain pattern"""
    pattern: str = Field(..., description="Domain pattern to unblock")
    keyword: str = Field(..., description="Authorization keyword (from BLOCKED_DOMAIN_KEYWORD env)")

    @validator('pattern')
    def validate_pattern(cls, v):
        return validate_string_length(v, 255, "pattern")

    @validator('keyword')
    def validate_keyword(cls, v):
        return validate_string_length(v, 100, "keyword")


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    timestamp: str
    mcp_connected: bool
    version: str


class StatusResponse(BaseModel):
    """Response model for detailed status endpoint"""
    api_status: str
    mcp_status: str
    timestamp: str
    components: dict
