# robairagapi

**Lightweight FastAPI REST API Bridge for RobAI RAG System**

A production-ready REST API that provides HTTP/JSON access to the RobAI Retrieval-Augmented Generation (RAG) system. Enables external tools like OpenWebUI to perform web crawling, semantic search, and knowledge management through a clean RESTful interface.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
  - [Health & Status](#health--status)
  - [Crawling](#crawling)
  - [Search](#search)
  - [Memory Management](#memory-management)
  - [Statistics](#statistics)
  - [Domain Management](#domain-management)
  - [Help](#help)
- [Search Modes](#search-modes)
- [Authentication & Security](#authentication--security)
- [Configuration](#configuration)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Docker Deployment](#docker-deployment)
- [Validation & Error Handling](#validation--error-handling)
- [Integration](#integration)
- [Performance](#performance)
- [Statistics](#statistics-1)

## Overview

**robairagapi** is a lightweight (~50MB) FastAPI-based REST API that bridges HTTP clients to the RobAI RAG infrastructure. Unlike traditional MCP-based bridges, it uses direct Python imports from [robaimodeltools](../robaimodeltools) for minimal overhead and maximum performance.

### What It Does

- **Web Crawling**: Extract and store content from URLs (single or deep crawl)
- **Semantic Search**: Vector similarity search with optional knowledge graph enhancement
- **Memory Management**: Store, retrieve, and organize crawled content
- **Domain Blocking**: Pattern-based URL blocking for security
- **Knowledge Graph Integration**: Entity extraction and relationship-based search

### What Makes It Different

- **Lightweight**: ~50MB Docker image vs ~600MB for full stack alternatives
- **Direct Integration**: No external MCP dependency, uses robaimodeltools directly
- **Multi-Layer Security**: 5-layer validation with defense-in-depth architecture
- **Production-Ready**: Bearer token auth, rate limiting, session management
- **OpenAPI Compatible**: Auto-generated Swagger docs at `/docs`

## Key Features

### API Capabilities

- **23 REST Endpoints** across 6 categories
- **3 Search Modes**: Simple (vector), KG-enhanced (hybrid), Full pipeline (5-phase)
- **3 Retention Policies**: Permanent, session-only, 30-day
- **Bearer Token Authentication** with rate limiting (60 req/min default)
- **Session Management**: 24-hour sessions with auto-cleanup
- **CORS Support**: Configurable cross-origin requests

### Search Features

- **Simple Search**: Fast vector similarity (100-500ms)
- **KG Search**: Hybrid vector + knowledge graph (500-2000ms)
- **Enhanced Search**: Full 5-phase pipeline with entity expansion (1-3s)
- **Tag Filtering**: Organize and filter by custom tags
- **Entity Extraction**: GLiNER-based entity recognition
- **Multi-Signal Ranking**: 5 signals (similarity, connectivity, density, recency, tags)

### Security Features

- **URL Validation**: Blocks localhost, private IPs, cloud metadata endpoints
- **SQL Injection Prevention**: Multi-layer SQL keyword detection
- **Rate Limiting**: Configurable per-API-key sliding window
- **Input Sanitization**: Length limits, range validation, type checking
- **Domain Blocking**: Wildcard pattern matching for malicious domains

## Architecture

### System Design

```
External Clients (OpenWebUI, curl, scripts)
    ↓ HTTP REST (port 8080)
┌─────────────────────────────────────────┐
│  robairagapi (FastAPI Bridge)           │
│  ├─ Authentication & Rate Limiting      │
│  ├─ Input Validation (5 layers)         │
│  ├─ REST Endpoints (23 endpoints)       │
│  └─ Response Formatting                 │
└────────────┬────────────────────────────┘
             │ Direct Python Imports
             ↓
┌─────────────────────────────────────────┐
│  robaimodeltools (Shared Library)       │
│  ├─ Crawl4AIRAG (crawler)               │
│  ├─ SearchHandler (KG search)           │
│  ├─ GLOBAL_DB (storage)                 │
│  └─ Domain Management                   │
└────────────┬────────────────────────────┘
             │
             ├──→ Crawl4AI (port 11235)
             ├──→ SQLite Database (crawl4ai_rag.db)
             ├──→ KG Service (port 8088)
             └──→ Neo4j Graph DB (port 7687)
```

### Data Flow

```
1. CLIENT REQUEST (HTTP)
   ↓
2. FASTAPI ENDPOINT
   ├─ HTTP parsing
   ├─ Pydantic validation (Layer 1)
   └─ Bearer token authentication
   ↓
3. RATE LIMITING CHECK
   ├─ Per-API-key sliding 60-second window
   └─ Default: 60 requests/minute
   ↓
4. OPERATION EXECUTION
   ├─ Crawling: URL → Crawl4AI → SQLite storage
   ├─ Search: Query → Vector DB → Optional KG expansion
   ├─ Memory: CRUD operations on stored content
   └─ Domain Management: Block/unblock patterns
   ↓
5. VALIDATION (Layers 2-5)
   ├─ Input validation (URL security, SQL injection)
   ├─ Parameter range checking
   ├─ Operation validation
   └─ Response format validation
   ↓
6. RESPONSE GENERATION
   └─ JSON serialization with timestamp
```

### Directory Structure

```
robairagapi/
├── README.md                 # This file
├── QUICKSTART.md             # 5-minute quickstart guide
├── main.py                   # Entry point (Uvicorn launcher)
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies (7 packages)
├── Dockerfile                # Alpine-based container
├── docker-compose.yml        # Service orchestration
├── .env.example             # Configuration template
└── api/
    ├── __init__.py          # Package marker
    ├── server.py            # FastAPI app & endpoints (525 lines)
    ├── models.py            # Pydantic models (170 lines)
    ├── auth.py              # Authentication & rate limiting (198 lines)
    └── validation.py        # Input validation (221 lines)
```

## API Endpoints

### Health & Status

#### GET /health

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:45.123456",
  "mcp_connected": true,
  "version": "1.0.0"
}
```

**Use Case:** Service monitoring, load balancer health checks

#### GET /api/v1/status

Detailed system status (authentication required).

**Response:**
```json
{
  "api_status": "running",
  "mcp_status": "direct",
  "timestamp": "2024-01-15T10:30:45.123456",
  "components": {
    "crawl4ai_url": "http://localhost:11235",
    "mode": "direct"
  }
}
```

**Use Case:** Operational monitoring, debugging

### Crawling

#### POST /api/v1/crawl

Crawl URL without storing (temporary extraction).

**Request:**
```json
{
  "url": "https://example.com/article"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "url": "https://example.com/article",
    "title": "Article Title",
    "content": "Extracted text content...",
    "markdown": "# Article Title\n\nMarkdown formatted...",
    "status": "success"
  },
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Validation:**
- URL must be HTTP/HTTPS
- Not localhost/private IPs/metadata endpoints
- Valid hostname required

**Use Case:** Preview content before storing, one-time extraction

#### POST /api/v1/crawl/store

Crawl and permanently store URL.

**Request:**
```json
{
  "url": "https://example.com/article",
  "tags": "python,tutorial,documentation",
  "retention_policy": "permanent"
}
```

**Parameters:**
- `url` (required): URL to crawl and store
- `tags` (optional): Comma-separated tags for organization
- `retention_policy` (optional): `permanent` | `session_only` | `30_days` (default: `permanent`)

**Response:** Same as `/crawl` plus:
```json
{
  "data": {
    "content_id": 123,
    "stored": true,
    "retention_policy": "permanent",
    "tags": ["python", "tutorial", "documentation"],
    ...
  }
}
```

**Side Effects:**
- Creates embeddings (384-dimensional vectors)
- Queues for knowledge graph processing
- Stores in SQLite database

**Use Case:** Build knowledge base, permanent content storage

#### POST /api/v1/crawl/temp

Crawl and store temporarily (session-only).

**Request:** Same as `/crawl/store`

**Difference:** Content deleted when user's session expires (24 hours)

**Use Case:** Temporary research, disposable content

#### POST /api/v1/crawl/deep/store

Deep crawl multiple pages from a domain (recursive BFS).

**Request:**
```json
{
  "url": "https://docs.python.org",
  "max_depth": 2,
  "max_pages": 10,
  "include_external": false,
  "score_threshold": 0.0,
  "timeout": 600,
  "tags": "python,docs",
  "retention_policy": "permanent"
}
```

**Parameters:**
- `url` (required): Root URL to start crawling
- `max_depth` (1-5, default 2): Maximum crawl depth
- `max_pages` (1-250, default 10): Maximum pages to crawl
- `include_external` (default false): Follow external domain links
- `score_threshold` (0.0-1.0, default 0.0): URL relevance filter
- `timeout` (60-1800 seconds): Total operation timeout
- `tags`, `retention_policy`: Same as `/crawl/store`

**Response:**
```json
{
  "success": true,
  "data": {
    "root_url": "https://docs.python.org",
    "pages_crawled": 8,
    "urls": [
      "https://docs.python.org/3/tutorial/",
      ...
    ],
    "content_ids": [123, 124, 125, ...],
    "timestamp": "2024-01-15T10:30:45.123456"
  }
}
```

**Execution:** Runs in thread pool (async, non-blocking)

**Use Case:** Crawl documentation sites, wikis, knowledge bases

### Search

#### POST /api/v1/search (or /api/v1/search/simple)

Simple vector similarity search (fast, no KG).

**Request:**
```json
{
  "query": "FastAPI authentication",
  "limit": 5,
  "tags": "python,web"
}
```

**Parameters:**
- `query` (required, max 500 chars): Search query
- `limit` (1-1000, default 10): Number of results
- `tags` (optional): Filter by tags (ANY match)

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "FastAPI authentication",
    "results": [
      {
        "content_id": 123,
        "url": "https://example.com/fastapi-auth",
        "title": "FastAPI Authentication Guide",
        "chunk_text": "FastAPI uses Bearer tokens...",
        "similarity_score": 0.95,
        "tags": ["python", "web"]
      }
    ],
    "count": 5
  },
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Performance:** ~100-500ms

**Use Case:** Fast lookups, simple queries

#### POST /api/v1/search/kg

Hybrid search (vector + knowledge graph).

**Request:**
```json
{
  "query": "FastAPI async patterns",
  "rag_limit": 5,
  "kg_limit": 10,
  "tags": "python",
  "enable_expansion": true,
  "include_context": true
}
```

**Parameters:**
- `query` (required): Search query
- `rag_limit` (1-100, default 5): Vector search results
- `kg_limit` (1-100, default 10): Graph search results
- `tags` (optional): Tag filter
- `enable_expansion` (default true): Entity expansion via KG
- `include_context` (default true): Include surrounding text

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "FastAPI async patterns",
    "rag_results": [
      {
        "content_id": 123,
        "url": "...",
        "similarity_score": 0.95,
        ...
      }
    ],
    "kg_results": [
      {
        "entity": "asyncio",
        "type": "Library",
        "context": "Python's asyncio is used for async programming",
        "confidence": 0.87,
        "referenced_chunks": [3, 5, 7]
      }
    ],
    "rag_count": 5,
    "kg_count": 10
  }
}
```

**Features:**
- Entity expansion: Finds related entities automatically
- Context extraction: Returns surrounding text
- Multi-signal ranking: Combines similarity + graph connectivity

**Performance:** ~500-2000ms

**Use Case:** Complex queries, entity-focused research

#### POST /api/v1/search/enhanced

Full 5-phase search pipeline (most comprehensive).

**Request:**
```json
{
  "query": "React performance optimization techniques",
  "tags": "javascript,react"
}
```

**FIXED Configuration** (not customizable):
- RAG results: Always 3 with FULL markdown content
- KG results: Always 5 with referenced chunks
- Entity expansion: Always enabled
- Context extraction: Always enabled

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "React performance optimization techniques",
    "rag_results": [
      {
        "content_id": 123,
        "url": "...",
        "title": "...",
        "markdown": "# Full markdown content with all formatting...",
        "similarity_score": 0.95
      }
    ],
    "kg_results": [
      {
        "entity": "Virtual DOM",
        "type": "Concept",
        "description": "...",
        "referenced_chunks": [1, 3, 5]
      }
    ],
    "processing_stages": {
      "entity_extraction": "completed",
      "vector_search": "completed",
      "graph_search": "completed",
      "ranking": "completed"
    }
  }
}
```

**5-Phase Pipeline:**
1. **Phase 1**: GLiNER entity extraction + query embedding
2. **Phase 2**: Parallel vector + Neo4j graph search (up to 100 entities)
3. **Phase 3**: KG-powered entity expansion
4. **Phase 4**: Multi-signal ranking (5 signals)
5. **Phase 5**: Format results with full markdown

**Performance:** ~1-3 seconds

**Use Case:** Deep research, complex topics, comprehensive answers

### Memory Management

#### GET /api/v1/memory

List all stored content with optional filtering.

**Query Parameters:**
- `retention_policy` (optional): Filter by `permanent` | `session_only` | `30_days`
- `limit` (1-1000, default 100): Maximum results

**Response:**
```json
{
  "success": true,
  "content": [
    {
      "content_id": 123,
      "url": "https://example.com/article",
      "title": "Article Title",
      "tags": ["python", "tutorial"],
      "retention_policy": "permanent",
      "created_at": "2024-01-15T10:30:45.123456",
      "updated_at": "2024-01-15T10:35:20.654321",
      "word_count": 5000,
      "chunk_count": 5
    }
  ],
  "count": 5,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Use Case:** Audit storage, view knowledge base, cleanup planning

#### DELETE /api/v1/memory

Remove specific URL from memory.

**Query Parameters:**
- `url` (required): URL to forget

**Response:**
```json
{
  "success": true,
  "message": "Removed https://example.com/article",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Side Effects:** Deletes content, vectors, chunks, and KG nodes

**Use Case:** Remove outdated or sensitive content

#### DELETE /api/v1/memory/temp

Clear all session-only (temporary) content.

**Response:**
```json
{
  "success": true,
  "message": "Cleared temporary content",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Use Case:** End-of-session cleanup, free storage

### Statistics

#### GET /api/v1/stats (or /api/v1/db/stats)

Get database statistics and usage metrics.

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_content": 42,
    "total_chunks": 512,
    "total_vectors": 512,
    "database_size_bytes": 52428800,
    "permanent_content": 35,
    "session_content": 5,
    "thirty_day_content": 2,
    "avg_content_size": 1243,
    "avg_chunk_size": 987,
    "oldest_content": "2024-01-01T10:30:45.123456",
    "newest_content": "2024-01-15T10:30:45.123456",
    "kg_processed": 38,
    "kg_pending": 4
  },
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Use Case:** Monitoring, capacity planning, debugging

### Domain Management

#### GET /api/v1/blocked-domains

List all blocked domain patterns.

**Response:**
```json
{
  "success": true,
  "blocked_domains": [
    {
      "pattern": "*.ru",
      "keyword": "geo-blocking",
      "created_at": "2024-01-10T12:00:00"
    },
    {
      "pattern": "*spam*",
      "keyword": "malicious-content",
      "created_at": "2024-01-05T09:15:30"
    }
  ],
  "count": 2,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Use Case:** Security audit, view firewall rules

#### POST /api/v1/blocked-domains

Add domain pattern to blocklist.

**Request:**
```json
{
  "pattern": "*.malicious.com",
  "description": "Known malicious domain"
}
```

**Pattern Types:**
- `*.ru` - Wildcard suffix (all .ru domains)
- `*spam*` - Keyword wildcard (contains "spam")
- `example.com` - Exact match

**Response:**
```json
{
  "success": true,
  "message": "Added *.malicious.com",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Use Case:** Block malicious sites, geo-restrictions, spam

#### DELETE /api/v1/blocked-domains

Remove domain pattern from blocklist.

**Query Parameters:**
- `pattern` (required): Domain pattern to unblock
- `keyword` (required): Authorization keyword (from env var)

**Security:** Requires `BLOCKED_DOMAIN_KEYWORD` environment variable

**Response:**
```json
{
  "success": true,
  "message": "Removed *.ru",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Help

#### GET /api/v1/help

Tool documentation for LLM providers (no authentication required).

**Response:**
```json
{
  "success": true,
  "tools": [
    {
      "name": "crawl_url",
      "example": "Crawl http://www.example.com without storing",
      "parameters": "url: string"
    },
    {
      "name": "crawl_and_store",
      "example": "Crawl and permanently store https://github.com/...",
      "parameters": "url: string, tags?: string, retention_policy?: string"
    }
  ],
  "api_info": {
    "base_url": "/api/v1",
    "authentication": "Bearer token required in Authorization header",
    "public_endpoints": {
      "/health": {...},
      "/api/v1/help": {...}
    }
  }
}
```

**Use Case:** LLM tool discovery, API documentation

## Search Modes

### Comparison Table

| Feature | Simple | KG Search | Enhanced |
|---------|--------|-----------|----------|
| **Speed** | ~100-500ms | ~500-2000ms | ~1-3s |
| **Vector Search** | ✓ | ✓ | ✓ |
| **Knowledge Graph** | ✗ | ✓ | ✓ |
| **Entity Expansion** | ✗ | Optional | Always |
| **Full Markdown** | ✗ | ✗ | ✓ |
| **Multi-Signal Ranking** | ✗ | ✓ | ✓ (5 signals) |
| **Configurable Limits** | ✓ | ✓ | ✗ (fixed) |
| **Best For** | Quick lookups | Research | Deep analysis |

### When to Use Each Mode

**Simple Search** (`/api/v1/search`):
- Quick fact lookups
- Known topic searches
- Performance-critical applications
- No entity relationships needed

**KG Search** (`/api/v1/search/kg`):
- Entity-focused queries
- Relationship exploration
- Configurable result counts
- Balanced speed/quality

**Enhanced Search** (`/api/v1/search/enhanced`):
- Comprehensive research
- Complex topics
- Full content needed
- Best possible results

## Authentication & Security

### Bearer Token Authentication

All endpoints except `/health` and `/api/v1/help` require Bearer token authentication:

```bash
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### API Key Configuration

**Environment Variables:**
```bash
# At least ONE required:
LOCAL_API_KEY=your-secret-api-key-here
REMOTE_API_KEY_2=optional-second-api-key
```

**Multiple Keys:**
- Supports up to 2 API keys (primary + secondary)
- Any valid key is accepted
- Useful for key rotation without downtime

### Rate Limiting

**Default Configuration:**
```
Maximum: 60 requests per minute per API key
Window: Sliding 60-second window
Status Code: 429 Too Many Requests (when exceeded)
```

**Environment Configuration:**
```bash
RATE_LIMIT_PER_MINUTE=60        # Requests per minute
ENABLE_RATE_LIMIT=true          # Can be disabled
```

**Rate Limit Response:**
```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

### Session Management

**Features:**
- Created per API key on first request
- 24-hour session timeout
- Auto-cleanup every hour
- 16-character session ID (SHA256-based)

**Session Data:**
```python
{
  "api_key": "token",
  "session_id": "abc123def456",
  "created_at": "2024-01-15T10:30:45",
  "last_activity": "2024-01-15T10:35:20",
  "requests_count": 42
}
```

### Security Features

**5-Layer Validation:**

1. **Layer 1 - Pydantic Models**:
   - Type validation (str, int, float, bool)
   - Required vs optional fields
   - Length limits (255-500 chars)
   - Range validation (1-250 for integers)

2. **Layer 2 - URL Validation**:
   - HTTP/HTTPS only
   - Valid hostname required
   - Blocks localhost (127.0.0.1, ::1)
   - Blocks private IPs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
   - Blocks link-local (169.254.0.0/16)
   - Blocks cloud metadata endpoints (169.254.169.254, 100.100.100.200)
   - Blocks .local, .internal, .corp domains

3. **Layer 3 - SQL Injection Prevention**:
   - Blocks SQL keywords (SELECT, INSERT, DROP, etc.)
   - Context-aware detection
   - NULL byte filtering

4. **Layer 4 - Operation Validation**:
   - Business logic validation in robaimodeltools
   - Database integrity checks
   - Service availability checks

5. **Layer 5 - Response Validation**:
   - HTTP status code verification
   - JSON serialization check
   - Timestamp presence
   - Success flag accuracy

### HTTP Security Headers

- **CORS**: Configurable (default: * for all origins)
- **X-Process-Time**: Performance tracking header
- **Standard Status Codes**: Proper HTTP semantics

## Configuration

### Environment Variables

Create a `.env` file in the robairagapi directory:

```bash
# API Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Authentication (at least one required)
LOCAL_API_KEY=your-secret-key-here
REMOTE_API_KEY_2=optional-second-key

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
ENABLE_RATE_LIMIT=true

# CORS
ENABLE_CORS=true
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO

# Domain Blocking (for DELETE operations)
BLOCKED_DOMAIN_KEYWORD=your-auth-keyword
```

### Configuration Validation

The config module validates critical settings on startup:

**Required:**
- At least one API key (LOCAL_API_KEY or REMOTE_API_KEY_2)

**Optional (uses defaults):**
- All other settings

### Startup Output

```
🚀 Starting RobAI RAG API Bridge on 0.0.0.0:8080
   MCP Server: localhost:3000
   CORS: Enabled
   Rate Limiting: Enabled

   API Docs: http://0.0.0.0:8080/docs
   Health Check: http://0.0.0.0:8080/health
```

## Installation

### Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- [robaimodeltools](../robaimodeltools) (shared library dependency)
- Crawl4AI service running on port 11235
- SQLite database access

### Install Dependencies

```bash
cd robairagapi

# Install Python packages
pip install -r requirements.txt

# Install robaimodeltools dependencies
pip install -r ../robaimodeltools/requirements.txt
```

### Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

### Start the Service

**Development Mode:**
```bash
python main.py
```

**Production Mode:**
```bash
uvicorn api.server:app --host 0.0.0.0 --port 8080 --workers 4
```

**With Gunicorn:**
```bash
gunicorn api.server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
```

### Verify Installation

```bash
# Check health
curl http://localhost:8080/health

# View API docs
open http://localhost:8080/docs
```

## Usage Examples

### Basic Crawling

**Python:**
```python
import requests

url = "http://localhost:8080/api/v1/crawl/store"
headers = {
    "Authorization": "Bearer your-api-key",
    "Content-Type": "application/json"
}
data = {
    "url": "https://example.com/article",
    "tags": "python,tutorial",
    "retention_policy": "permanent"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

**cURL:**
```bash
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/article",
    "tags": "python,tutorial",
    "retention_policy": "permanent"
  }'
```

### Deep Crawling

```python
data = {
    "url": "https://docs.python.org",
    "max_depth": 2,
    "max_pages": 20,
    "include_external": False,
    "tags": "python,documentation",
    "retention_policy": "permanent"
}

response = requests.post(
    "http://localhost:8080/api/v1/crawl/deep/store",
    headers=headers,
    json=data
)
print(f"Crawled {response.json()['data']['pages_crawled']} pages")
```

### Simple Search

```python
data = {
    "query": "FastAPI authentication patterns",
    "limit": 10,
    "tags": "python,web"
}

response = requests.post(
    "http://localhost:8080/api/v1/search",
    headers=headers,
    json=data
)

for result in response.json()['data']['results']:
    print(f"{result['title']} ({result['similarity_score']:.2f})")
    print(f"  {result['url']}")
```

### Enhanced Search

```python
data = {
    "query": "React performance optimization techniques",
    "tags": "javascript,react"
}

response = requests.post(
    "http://localhost:8080/api/v1/search/enhanced",
    headers=headers,
    json=data
)

# Always returns exactly 3 RAG results with full markdown
for result in response.json()['data']['rag_results']:
    print(f"\n{result['title']}")
    print(result['markdown'])  # Full markdown content
```

### Memory Management

**List Content:**
```python
response = requests.get(
    "http://localhost:8080/api/v1/memory?retention_policy=permanent&limit=50",
    headers=headers
)

for item in response.json()['content']:
    print(f"{item['title']} - {item['word_count']} words")
```

**Delete Content:**
```python
response = requests.delete(
    "http://localhost:8080/api/v1/memory?url=https://example.com/old-article",
    headers=headers
)
print(response.json()['message'])
```

### Domain Blocking

**Add Block:**
```python
data = {
    "pattern": "*.spam.com",
    "description": "Known spam domain"
}

response = requests.post(
    "http://localhost:8080/api/v1/blocked-domains",
    headers=headers,
    json=data
)
```

**Remove Block:**
```python
response = requests.delete(
    "http://localhost:8080/api/v1/blocked-domains?pattern=*.spam.com&keyword=your-auth-keyword",
    headers=headers
)
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Minimal dependencies
RUN apt-get update && apt-get install -y curl

# Copy code
COPY robaimodeltools/ ./robaimodeltools/
COPY robaidata/ ./robaidata/
COPY robairagapi/requirements.txt .
COPY robairagapi/api/ ./api/
COPY robairagapi/config.py robairagapi/main.py ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r robaimodeltools/requirements.txt

# Non-root user (security)
RUN useradd -m -u 1000 apiuser
USER apiuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run
CMD ["python3", "main.py"]
```

**Key Features:**
- Python 3.11-slim base (~50MB final image)
- Non-root user for security
- Built-in health checks
- Minimal OS dependencies

### Docker Compose

```yaml
services:
  robairagapi:
    build:
      context: ..
      dockerfile: robairagapi/Dockerfile
    image: robairagapi:latest
    container_name: robairagapi
    network_mode: "host"
    restart: unless-stopped
    environment:
      - LOCAL_API_KEY=${LOCAL_API_KEY}
      - RATE_LIMIT_PER_MINUTE=60
      - SERVER_PORT=8080
```

### Build and Run

```bash
# Build image
docker build -t robairagapi:latest -f robairagapi/Dockerfile .

# Run container
docker run -d \
  --name robairagapi \
  --network host \
  -e LOCAL_API_KEY=your-secret-key \
  robairagapi:latest

# Check logs
docker logs -f robairagapi

# Check health
curl http://localhost:8080/health
```

## Validation & Error Handling

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | All successful operations |
| 400 | Bad Request | Invalid URL, invalid parameters |
| 401 | Unauthorized | Missing/invalid API key |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected exception |

### Error Response Format

**Standard Error:**
```json
{
  "detail": "Invalid or unsafe URL provided"
}
```

**Global Exception (500):**
```json
{
  "success": false,
  "error": "Exception message here",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Common Errors

**Invalid URL:**
```bash
curl -X POST http://localhost:8080/api/v1/crawl \
  -H "Authorization: Bearer key" \
  -d '{"url": "http://localhost:8000"}'

# Response (400):
{"detail": "Invalid or unsafe URL provided"}
```

**Missing API Key:**
```bash
curl http://localhost:8080/api/v1/status

# Response (403):
{"detail": "Not authenticated"}
```

**Rate Limited:**
```bash
# After 60 requests in one minute:
# Response (429):
{"detail": "Rate limit exceeded. Try again later."}
```

## Integration

### With robaimodeltools

**Direct Imports:**
```python
from robaimodeltools.operations.crawler import Crawl4AIRAG
from robaimodeltools.data.storage import GLOBAL_DB
from robaimodeltools.search.search_handler import SearchHandler
from robaimodeltools.operations.domain_management import (
    list_blocked_domains,
    add_blocked_domain,
    remove_blocked_domain
)
```

**Usage Pattern:**
```python
# Initialize
rag_system = Crawl4AIRAG(crawl4ai_url="http://localhost:11235")

# Operations
await rag_system.crawl_and_store(url, retention_policy, tags)
await rag_system.search_knowledge(query, limit, tags)
GLOBAL_DB.forget(url)
```

### With OpenWebUI

**Configuration:**
```
Connection Settings:
- Base URL: http://your-server:8080
- Auth Type: Bearer Token
- API Key: your-api-key-here
- Name: RobAI RAG API
```

**Supported Operations:**
- Crawl URLs
- Store and search content
- View stored content
- Manage blocked domains

### Service Communication Flow

```
OpenWebUI Client
    ↓ HTTP
robairagapi (REST API)
    ↓ Python imports
robaimodeltools (RAG core)
    ├→ Crawl4AIRAG → Crawl4AI Service
    ├→ GLOBAL_DB → SQLite Database
    └→ SearchHandler → KG Service → Neo4j
```

## Performance

### Response Times (Typical)

| Endpoint | Time | Notes |
|----------|------|-------|
| `/health` | 1ms | Simple response |
| `/api/v1/status` | 5ms | Config check |
| `/api/v1/crawl` | 2-10s | Depends on page size |
| `/api/v1/crawl/store` | 3-15s | Plus DB storage |
| `/api/v1/search` | 100-500ms | Vector similarity |
| `/api/v1/search/kg` | 500-2000ms | Includes graph query |
| `/api/v1/search/enhanced` | 1-3s | Full 5-phase pipeline |
| `/api/v1/crawl/deep/store` | 30-300s | Depends on max_pages |

### Throughput

- **Rate Limit**: 60 requests/minute/key (default)
- **Concurrent Connections**: Limited by Uvicorn workers
- **Default Workers**: 1 (configurable)
- **Bottleneck**: Crawl4AI service for crawling operations

### Resource Usage

- **Docker Image**: ~50MB
- **RAM Usage**: 100-300MB (with database loaded)
- **Per Request**: ~1-5MB (depends on content size)
- **Sessions Table**: ~1KB per session

### Comparison with Alternatives

| Aspect | robairagapi | mcpragcrawl4ai |
|--------|-------------|-----------------|
| **Image Size** | ~50MB | ~600MB |
| **Dependencies** | 7 packages | Full ML stack |
| **Startup Time** | ~5 seconds | ~30 seconds |
| **Memory Usage** | 100-300MB | 1-2GB |
| **Protocol** | HTTP/JSON | HTTP + gRPC |
| **Use Case** | External API | Standalone |

## Statistics

### Code Metrics

- **Total Lines**: ~1,200 lines of application code
- **Main Implementation**: server.py (525 lines)
- **Pydantic Models**: 12 models (170 lines)
- **Authentication**: 198 lines
- **Validation**: 221 lines

### API Endpoints

- **Total Endpoints**: 23
- **Categories**: 6 (Health, Crawling, Search, Memory, Stats, Domain)
- **Public Endpoints**: 2 (/health, /api/v1/help)
- **Authenticated Endpoints**: 21

### Dependencies

- **Python Packages**: 7 direct dependencies
  - fastapi==0.115.6
  - uvicorn==0.32.1
  - pydantic==2.10.4
  - python-dotenv==1.0.1
  - httpx==0.28.1
  - gunicorn==23.0.0
  - robaimodeltools (local)

### External Services

- **Required**: 2 (Crawl4AI, SQLite)
- **Optional**: 2 (KG Service, Neo4j)
- **Monitored**: All 4 services

---

## Quick Reference

### Most Common Operations

**Start service:**
```bash
docker compose up -d robairagapi
```

**Check health:**
```bash
curl http://localhost:8080/health
```

**Crawl and store:**
```bash
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tags": "example"}'
```

**Search:**
```bash
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 10}'
```

**View API docs:**
```
http://localhost:8080/docs
```

---

## Additional Resources

- [QUICKSTART.md](QUICKSTART.md) - 5-minute quickstart guide
- [robaimodeltools Documentation](../robaimodeltools/README.md) - Core RAG library
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [OpenAPI Specification](http://localhost:8080/openapi.json)

## Contributing

When contributing to robairagapi:

1. **Maintain API Compatibility**: All changes must be backward-compatible
2. **Update Pydantic Models**: Keep request/response models in sync
3. **Add Tests**: Test new endpoints and validation logic
4. **Update Documentation**: Keep this README and OpenAPI specs current
5. **Follow Security Practices**: Maintain 5-layer validation approach

## License

[Include license information here]

## Contact

[Include contact/support information here]
