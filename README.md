# robairagapi

**RobAI RAG API Bridge** – A production‑grade FastAPI service that exposes the full capabilities of the RobAI Retrieval‑Augmented Generation (RAG) stack via a clean, versioned HTTP/JSON interface.  
It is deliberately **self‑contained** (no MCP server) and is built to be consumed by **AI agents**, external tools (e.g., OpenWebUI), and human developers alike.

---  

## Table of Contents
1. [Overview](#overview)  
2. [Architecture Diagram & Data Flow](#architecture-diagram--data-flow)  
3. [Key Concepts & Terminology](#key-concepts--terminology)  
4. [Installation & Quick‑Start](#installation--quick‑start)  
5. [Configuration (Environment Variables)](#configuration-environment-variables)  
6. [Authentication & Security Model](#authentication--security-model)  
7. [Rate Limiting & Session Management](#rate-limiting--session-management)  
8. [API Reference (V2 Endpoints)](#api-reference-v2-endpoints)  
   - [Health & Status](#health--status)  
   - [Crawling](#crawling)  
   - [Search](#search)  
   - [Web‑Search (Serper)](#web‑search-serper)  
   - [Memory Management](#memory-management)  
   - [Domain Management](#domain-management)  
   - [Statistics & Container Health](#statistics--container-health)  
   - [Help / Tool Discovery](#help--tool-discovery)  
   - [OpenAPI Customisation](#openapi-customisation)  
9. [Internal Module Walk‑through](#internal-module-walk‑through)  
10. [Detailed Toolactions Overview](#detailed-toolactions-overview)  
11. [Validation Layer Details](#validation-layer-details)  
12. [Security Middleware Deep Dive](#security-middleware-deep-dive)  
13. [Network Utilities](#network-utilities)  
14. [Error Handling Strategy](#error-handling-strategy)  
15. [Logging & Observability](#logging--observability)  
16. [Docker Image & Deployment](#docker-image--deployment)  
17. [Performance Considerations](#performance-considerations)  
18. [Development Workflow & Testing](#development-workflow--testing)  
19. [Extending the API](#extending-the-api)  
20. [CI/CD Pipeline (Suggested)](#cicd-pipeline-suggested)  
21. [Contributing Guidelines](#contributing-guidelines)  
22. [License & Contact](#license--contact)  

---  

## Overview
`robairagapi` is a **REST façade** for the core `robaimodeltools` library (the shared RAG engine). It abstracts away direct Python imports and lets callers:

* **Crawl** arbitrary URLs (single‑page or deep recursive crawl) and optionally store the extracted content.  
* **Search** using three distinct modes:  
  1. **Simple Vector** – fast similarity lookup.  
  2. **KG‑Hybrid** – vector + knowledge‑graph enrichment.  
  3. **Enhanced 5‑phase** – full pipeline with entity expansion, multi‑signal ranking, and markdown rendering.  
* **Manage Memory** – list, delete, or clear stored content with retention‑policy granularity.  
* **Control Security** – add/remove blocked‑domain patterns, enforce URL validation, and apply rate limits.  
* **Monitor** – health checks, container status, and database statistics.

All endpoints (except `/health` and `/api/v1/tools/list`) require **Bearer token authentication**.

---  

## Architecture Diagram & Data Flow
```
┌─────────────────────┐
│  External Clients   │   (OpenWebUI, curl, python scripts, AI agents)
└─────────┬───────────┘
          │ HTTP/JSON
          ▼
┌─────────────────────┐
│   robairagapi       │  FastAPI server (this repo)
│  ├─ config.py       │  → env‑var based configuration
│  ├─ auth.py         │  → token validation, rate limiting, sessions
│  ├─ models.py       │  → request/response validation (Pydantic)
│  ├─ security.py     │  → security middleware (IP/MAC, header checks)
│  ├─ network_utils.py│  → MAC lookup & subnet helpers
│  ├─ validation.py   │  → URL sanitisation, string‑length checks
│  ├─ tool_discovery.py│→ background client pulling LLM tool definitions
│  └─ toolactions/    │  → self‑contained crawling/search utilities
│      ├─ data/       │     • storage.py (error logging)
│      │   ├─ content_cleaner.py
│      │   └─ dbdefense.py
│      └─ operations/  │     • crawl_operations.py
│          │          │     • deep_crawl.py
│          │          │     • search_operations.py
│          │          │     • serper_search.py
│          │          │     • stats_operations.py
│          │          │     • validation.py
│          └─ utilities/│     • blockeddomains.py
└───────┬─────────────┘
        │ Direct imports
        ▼
┌─────────────────────┐
│   robaimodeltools  │   (shared RAG core)
│   • Crawl4AIRAG    │   → external Crawl4AI service (http://localhost:11235)
│   • GLOBAL_DB     │   → SQLite DB (`crawl4ai_rag.db`)
│   • SearchHandler │   → vector store + Neo4j KG
└─────────────────────┘
```
*No MCP server is used – all calls are direct Python imports, reducing latency and image size.*

---  

## Key Concepts & Terminology
| Term | Meaning |
|------|---------|
| **Crawl4AI** | External micro‑service that fetches a page, extracts text/markdown, and returns embeddings. |
| **Retention Policy** | Determines how stored content is kept: `permanent`, `session_only` (auto‑deleted after 24 h), or `30_days`. |
| **Session** | Short‑lived context tied to an API key, tracked for activity and request counting. |
| **Toolactions** | Self‑contained modules under `api/toolactions/` that implement the actual business logic (crawling, searching, stats). |
| **KG (Knowledge Graph)** | Neo4j‑backed graph that stores entity relationships for enriched search. |
| **V2 Endpoints** | Newer API version that uses the unified `toolactions` layer; older V1 endpoints are deprecated. |
| **OpenAPI Customisation** | `api/server.py` overrides the default schema to remove `anyOf` patterns for easier consumption by LLM agents. |

---  

## Installation & Quick‑Start
```bash
# Clone (already present at /home/robiloo/Documents/robaitools)
cd robairagapi

# Optional: create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt   # fastapi, uvicorn, pydantic, python-dotenv, httpx, etc.

# Copy example environment file and edit
cp .env.example .env
nano .env   # At minimum set OPENAI_API_KEY; adjust other vars as needed

# Run in development mode
python main.py
# Or production mode with uvicorn workers
uvicorn api.server:app --host 0.0.0.0 --port 8080 --workers 4
```

**Health check** (should always return 200):
```bash
curl http://localhost:8080/health
```

---  

## Configuration (Environment Variables)
All settings are read via `python-dotenv` in `config.py`. The most important variables are:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Interface to bind FastAPI |
| `SERVER_PORT` | `8080` | HTTP port |
| `OPENAI_API_KEY` | *(none)* | Primary bearer token – **required** |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per API key in a sliding 60‑second window |
| `ENABLE_RATE_LIMIT` | `true` | Set `false` to disable rate limiting (e.g., bulk migrations) |
| `ENABLE_CORS` | `true` | Enables CORS; origins defined by `CORS_ORIGINS` |
| `CORS_ORIGINS` | `*` | Comma‑separated list of allowed origins |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `BLOCKED_DOMAIN_KEYWORD` | *(none)* | Secret used to authorize domain unblock requests |
| `CRAWL4AI_URL` | `http://localhost:11235` | URL of the Crawl4AI micro‑service |
| `TOOLS_SERVICE_URL` | `http://localhost:8099` | URL of the optional LLM tool‑discovery service (used by `/api/v1/tools/list`) |
| `TOOLS_REFRESH_INTERVAL` | `30` | Seconds between tool‑discovery cache refreshes |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` | `localhost` / `3000` | Retained for backwards compatibility – not used by current code |
| `ENABLE_MAC_VALIDATION` / `STRICT_AUTH_FOR_PFSENSE` | `true` | Advanced security flags (future‑proof, currently unused) |

*All variables are automatically type‑cast where appropriate (int, bool, etc.).*

---  

## Authentication & Security Model
1. **Bearer Token** – Every protected endpoint expects an `Authorization: Bearer <token>` header.  
2. **Token Normalisation** – `auth.py` accepts any case/whitespace variation (`bearer`, `BEARER`, multiple spaces).  
3. **Token Validation** – Only the value of `OPENAI_API_KEY` (and any additional keys you manually add) are accepted.  
4. **Failed Authentication** – Returns **404 Not Found** to obscure the existence of the endpoint.  
5. **Rate‑Limit Exceeded** – Also returns 404 for the same reason.  

*Security logs are printed to stdout with token previews (first 8 characters) for audit purposes.*

---  

## Rate Limiting & Session Management
- **Sliding Window**: `RateLimiter` stores timestamps per API key, pruning entries older than 60 seconds.  
- **Disabling**: Set `ENABLE_RATE_LIMIT=false` for bulk operations.  
- **Sessions**: `SessionManager` creates a 16‑character SHA‑256‑derived session ID on each successful request.  
  - Stored in an in‑memory dict with `created_at`, `last_activity`, and `requests_count`.  
  - Expire after **24 hours** of inactivity; cleanup runs hourly via a background task (`session_cleanup_task`).  

---  

## API Reference (V2 Endpoints)

All request/response bodies are defined in `api/models.py`. The OpenAPI schema is automatically generated and **simplified** (no `anyOf` patterns) for easier consumption by AI agents.

### Health & Status
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | **No** | Simple health check; always returns 200 with `status: "healthy"`. |
| `GET` | `/api/v1/status` | **Yes** | Detailed service status (`api_status`, `mcp_status`, `components` map). |

### Crawling (V2)
| Method | Path | Model | Description |
|--------|------|-------|-------------|
| `POST` | `/api/v2/crawl` | `CrawlRequest` | Crawl a URL **without** storing. Optional `max_chars` (5 k‑25 k). |
| `POST` | `/api/v2/crawl/store` | `CrawlStoreRequest` | Crawl **and permanently store** content. Optional `tags`, `retention_policy`. |
| `POST` | `/api/v2/crawl/temp` | `CrawlStoreRequest` | Crawl **and store temporarily** (`session_only`). |
| `POST` | `/api/v2/crawl/deep/store` | `DeepCrawlStoreRequest` | Recursive crawl up to `max_depth` (1‑5) and `max_pages` (1‑250). Supports external links, score thresholds, and timeout. |

**Common behaviours**  
- URL validation via `api.validation.validate_url`.  
- Errors → `400 Bad Request` with explicit messages.  
- Internal failures → `500` with stack trace logged.  

### Search (V2)
| Method | Path | Model | Description |
|--------|------|-------|-------------|
| `POST` | `/api/v2/search` | `SearchRequest` | GraphRAG hybrid search (vector + KG). Parameters: `term`, `depth` (`low|medium|high|all`), `limit`. |
| `POST` | `/api/v2/web_search` | `WebSearchRequest` | Proxy to **Serper** (Google) API; returns titles, URLs, snippets. |
| `GET` | `/api/v2/stats` & `/api/v2/db/stats` | – | Database statistics (content count, vector count, storage size, etc.). |
| `GET` | `/api/v2/health/containers` | – | Docker container health (name, status, state). |

### Memory Management
| Method | Path | Model | Description |
|--------|------|-------|-------------|
| `GET` | `/api/v1/memory` *(deprecated)* | – | List stored content; supports `filter` and `limit`. |
| `DELETE` | `/api/v1/memory` *(deprecated)* | `ForgetUrlRequest` | Remove a specific URL from storage. |
| `DELETE` | `/api/v1/memory/temp` *(deprecated)* | – | Clear all `session_only` content. |

*Future releases will migrate these to `/api/v2/memory/*`.*

### Domain Management
| Method | Path | Model | Description |
|--------|------|-------|-------------|
| `GET` | `/api/v1/blocked-domains` | – | List all blocked domain patterns. |
| `POST` | `/api/v1/blocked-domains` | `BlockedDomainRequest` | Add a new pattern (e.g., `*.ru`). |
| `DELETE` | `/api/v1/blocked-domains` | `UnblockDomainRequest` | Remove a pattern; requires `BLOCKED_DOMAIN_KEYWORD`. |

### Help / Tool Discovery
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tools/list` | **Public** endpoint returning LLM‑compatible tool definitions (no auth). |
| `GET` | `/api/v2/help` | Authenticated endpoint describing all V2 tools, parameters, and examples. |

### OpenAPI Customisation
`api/server.py` overrides `app.openapi` with `custom_openapi()` which:
- **Simplifies** component schemas (removes `anyOf`).  
- **Adds** an `X-Process-Time` header to every response.  
- **Caches** the generated schema for performance.  

---  

## Internal Module Walk‑through
Below is a concise map of the most relevant source files, their responsibilities, and notable implementation details.

| Module | Path | Responsibility | Highlights |
|--------|------|----------------|------------|
| **Configuration** | `config.py` | Reads env vars, validates required keys (`OPENAI_API_KEY`), provides class‑level constants (host, port, CORS, etc.). | Uses `dotenv.load_dotenv()`; raises `ValueError` on missing required keys. |
| **Authentication** | `api/auth.py` | Bearer token validation, rate limiting, session creation, session cleanup. | Normalises tokens, logs failed attempts (first 8 chars), returns 404 on auth failures to hide endpoint existence. |
| **Models** | `api/models.py` | Pydantic request/response schemas; includes validators (`validate_url`, `validate_string_length`). | Centralised validation ensures consistent error handling across endpoints. |
| **Network Utils** | `api/network_utils.py` | Thin wrapper around `httpx.AsyncClient` for outbound HTTP calls (e.g., Serper API). Handles timeouts and exception translation. |
| **Security** | `api/security.py` | Implements IP + MAC validation, header‑tampering checks, strict vs relaxed mode, and returns security‑oriented JSON errors. |
| **Tool Discovery** | `api/tool_discovery.py` | Background client that periodically fetches LLM tool definitions from a configurable service (`TOOLS_SERVICE_URL`). Caches results and exposes via `/api/v1/tools/list`. |
| **Validation Helpers** | `api/validation.py` | URL safety checks (rejects localhost, private IPs, cloud‑metadata endpoints), and generic string‑length validation. |
| **Toolactions – Data** | `api/toolactions/data/` | `content_cleaner.py` (post‑crawl HTML sanitisation), `dbdefense.py` (SQL‑injection guard), `storage.py` (centralised error logging). |
| **Toolactions – Operations** | `api/toolactions/operations/` | **crawl_operations.py** – core crawling logic using `Crawl4AIRAG`. <br> **deep_crawl.py** – recursive BFS crawl with depth/page limits. <br> **search_operations.py** – GraphRAG search pipeline (vector + KG). <br> **serper_search.py** – wrapper for Serper Google Search API. <br> **stats_operations.py** – collects DB statistics (row counts, storage size). <br> **validation.py** – re‑uses `api.validation` helpers for request payloads. <br> **queue_managers.py** – internal async queue for background crawl tasks (not currently exposed). |
| **Toolactions – Utilities** | `api/toolactions/utilities/blockeddomains.py` | Functions to check URLs against blocked patterns, using simple glob‑style matching. |
| **Server** | `api/server.py` | FastAPI app creation, middleware registration (security, CORS, process‑time header, V2 logging). Defines all routes, background tasks, and custom OpenAPI schema. |
| **Entry Point** | `main.py` | Prints startup banner and launches the app via `uvicorn.run`. |

---  

## Detailed Toolactions Overview
The **toolactions** package houses the business logic that powers every V2 endpoint. It is deliberately isolated from the FastAPI layer to enable unit‑testing without a running server.

### `crawl_operations.py`
* **`crawl_url`** – Calls the external Crawl4AI service, trims the result to `max_chars`, and returns a JSON‑serialisable dict containing `url`, `title`, `content`, `markdown`, and a success flag.  
* **`crawl_and_store`** – Extends `crawl_url` by persisting the result via `robaimodeltools.GLOBAL_DB`. Handles `retention_policy` and optional `tags`.  
* **Error handling** – Wraps all external calls in try/except, logs via `toolactions/data/storage.py`, and raises `ValueError` for client‑side misuse.

### `deep_crawl.py`
* Implements a **breadth‑first search** across a domain, respecting `max_depth`, `max_pages`, and optional `include_external`.  
* Utilises a **thread‑pool executor** (`asyncio.to_thread`) to keep the FastAPI event loop responsive.  
* Returns a summary dict with `pages_crawled`, list of `urls`, and generated `content_ids`.

### `search_operations.py`
* Orchestrates the **GraphRAG** pipeline:
  1. **Entity extraction** via `robaimodeltools.search.search_handler`.  
  2. **Vector similarity** query against the embedding store.  
  3. **Knowledge‑graph lookup** in Neo4j (if configured).  
  4. **Hybrid ranking** using five signals (similarity, KG connectivity, recency, tag match, and entity relevance).  
  5. **Result formatting** – either raw JSON or markdown‑rich payloads.  
* Supports configurable `depth` levels (`low`, `medium`, `high`, `all`) that control the breadth of KG traversal.

### `serper_search.py`
* Thin async wrapper around the **Serper** Google Search API. Handles API key injection, pagination (`num_results`), and per‑result character trimming (`max_chars_per_result`).  
* Returns a list of `title`, `url`, `snippet` entries, mirroring the format expected by downstream LLM tools.

### `stats_operations.py`
* Queries the SQLite database (`crawl4ai_rag.db`) for **row counts**, **storage size**, **average content length**, and **KG processing stats**.  
* Provides both a **high‑level** (`/api/v2/stats`) and a **raw DB** (`/api/v2/db/stats`) endpoint.

### `validation.py` (inside operations)
* Re‑uses the top‑level `api.validation` helpers but also adds **operation‑specific checks** (e.g., ensuring `max_depth` ≤ 5).  
* Centralises error messages so that the API layer can simply propagate them.

### `queue_managers.py`
* Implements an **asynchronous job queue** used by the deep‑crawl endpoint to schedule background fetches when the request payload exceeds the synchronous threshold.  
* Not currently exposed via a public endpoint, but useful for future “fire‑and‑forget” crawling.

---  

## Validation Layer Details
All incoming payloads pass through **three validation layers**:

1. **Pydantic Model Validation** – Enforced automatically by FastAPI. Each field uses `Field(..., description="…")` and custom validators in `api/models.py`.  
2. **URL Safety Validation (`api/validation.py`)** – Rejects:
   * localhost (`127.0.0.1`, `::1`)  
   * private IPv4 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)  
   * link‑local (`169.254.0.0/16`)  
   * cloud metadata endpoints (`169.254.169.254`, `100.100.100.200`)  
   * domain suffixes like `.local`, `.internal`, `.corp`  
3. **Operation‑Specific Validation** – Implemented in `api/toolactions/operations/validation.py`. Examples:
   * `max_depth` must be `1 ≤ depth ≤ 5`.  
   * `max_pages` capped at `250`.  
   * `timeout` must be between `60` and `1800` seconds.  

When validation fails, a **`400 Bad Request`** is raised with a concise error message; the response body follows the standard error schema:
```json
{
  "success": false,
  "error": "Detailed validation message",
  "timestamp": "2025-12-14T10:22:00.123456"
}
```

---  

## Security Middleware Deep Dive
`api/security.py` provides a **defence‑in‑depth** request‑inspection pipeline executed **before** any route handler:

| Step | Description | Outcome on Failure |
|------|-------------|--------------------|
| **IP Extraction** (`get_client_ip`) | Looks at `X‑Forwarded‑For` (proxy) then `request.client.host`. | Returns `"unknown"` if unavailable. |
| **MAC Lookup** (`get_mac_address_from_ip`) | Reads `/proc/net/arp` on Linux; returns `None` if ARP cache missing or entry not found. | If MAC validation is enabled and lookup fails, request proceeds (no MAC check). |
| **PfSense Detection** | Compares client IP to `Config.PFSENSE_IP`. If match, optionally validates MAC against `Config.PFSENSE_MAC`. | Mismatch → **403 Forbidden** (hidden as 404). |
| **Strict vs Relaxed Mode** | `strict_mode_enabled` determines whether the request undergoes the full “strict” checklist (header tampering, path traversal, method override, protocol downgrade). | Any violation → **404 Not Found** (to hide endpoint). |
| **Header Checks** | Ensures exactly one `Authorization` header, no duplicate or suspicious headers (`X‑Authorization`, `Proxy-Authorization`, etc.). | Violation → 404. |
| **Path Checks** | Blocks `".."` and encoded traversal patterns (`%2e%2e`, `%2f`, `%5c`, `%00`). | Violation → 404. |
| **Method Override Checks** | Detects `X‑HTTP-Method-Override` family of headers. | Violation → 404. |
| **Protocol Downgrade** | Disallows `Upgrade` header in strict mode (prevents WebSocket hijack). | Violation → 404. |
| **Logging** | Every security‑relevant event prints a prefixed line (`⚠️  SECURITY:`) to stdout with a timestamp, IP, and brief context. | N/A |

The middleware returns a **JSON error response** with fields `success`, `error`, and `timestamp` to keep client‑side handling consistent.

---  

## Network Utilities
`api/network_utils.py` supplies two low‑level helpers used by the security middleware and, potentially, by custom extensions:

| Function | Purpose | Edge Cases Handled |
|----------|---------|-------------------|
| `get_mac_address_from_ip(ip_address)` | Reads `/proc/net/arp` to resolve a MAC for a given IPv4 address. | Returns `None` if `/proc/net/arp` does not exist, if the IP is not present, or if the MAC format fails validation. |
| `validate_mac_address(mac_address)` | Simple regex validation (`aa:bb:cc:dd:ee:ff`). | Normalises case, rejects empty strings. |
| `ip_in_subnet(ip, subnet)` | Checks IPv4 membership for `/24` CIDR only (the most common LAN size). | Returns `False` for malformed CIDR, non‑/24 prefixes, or IPv6 inputs. |

These utilities are deliberately **minimal** to keep the container footprint low; they can be expanded (e.g., using `ipaddress` stdlib) without breaking the public API.

---  

## Error Handling Strategy
Robairagapi adopts a **centralised error handling** approach:

1. **FastAPI Exception Handlers** – `api/server.py` registers a global `Exception` handler that captures any uncaught exception and returns a **500 Internal Server Error** with a JSON payload:
   ```json
   {
     "success": false,
     "error": "<exception message>",
     "timestamp": "<ISO timestamp>"
   }
   ```
2. **HTTPException Propagation** – Business‑logic modules raise `HTTPException(status_code=400, detail="…")` for client‑side errors (validation, missing resources).  
3. **Toolactions Logging** – Each operation catches unexpected errors, logs them via `toolactions/data/storage.py`, and re‑raises an `HTTPException(500)`.  
4. **Security Middleware** – Returns **404** on auth/authorization failures to avoid leaking endpoint existence.  

All error responses conform to the same JSON schema, making downstream client code (including AI agents) deterministic.

---  

## Logging & Observability
- **Standard Output** – The service prints human‑readable log lines prefixed with emojis (`🚀`, `🔧`, `⚠️`, `❌`).  
- **Request Timing** – Middleware injects an `X-Process-Time` header (milliseconds) for each response.  
- **Security Audits** – Security events (failed auth, header tampering, MAC mismatches) are logged with the offending token’s first 8 characters (or IP) to aid forensic analysis while avoiding full token leakage.  
- **Tool Action Errors** – `api/toolactions/data/storage.py` provides a `log_error(name, exc, context)` helper that writes a JSON‑compatible line to stdout, enabling easy parsing by log aggregators (e.g., Loki, Fluentd).  
- **Future Integration** – The architecture is ready for integration with structured loggers (`structlog`, `loguru`) or external observability platforms (Prometheus metrics could be added as a later enhancement).

---  

## Docker Image & Deployment
A minimal **Alpine‑based** Dockerfile is located at the repository root (`Dockerfile`). Key points:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy source (including shared robaimodeltools)
COPY robaimodeltools/ ./robaimodeltools/
COPY robairagapi/requirements.txt .
COPY robairagapi/api/ ./api/
COPY robairagapi/config.py robairagapi/main.py ./

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r robaimodeltools/requirements.txt

# Run as non‑root user
RUN useradd -m -u 1000 apiuser
USER apiuser

HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "main.py"]
```

**Running the container**
```bash
docker build -t robairagapi:latest -f Dockerfile .
docker run -d \
  --name robairagapi \
  -p 8080:8080 \
  -e OPENAI_API_KEY=your-secret-key \
  -e SERVER_HOST=0.0.0.0 \
  -e SERVER_PORT=8080 \
  robairagapi:latest
```

The container automatically executes the **healthcheck**; Docker will mark the container unhealthy if `/health` does not return `200`.

---  

## Performance Considerations
| Component | Typical Latency | Bottleneck | Mitigation |
|-----------|----------------|------------|------------|
| **Crawl4AI Call** | 2‑10 s (depends on page size) | External service I/O | Increase `uvicorn` workers, cache frequent crawls. |
| **Vector Search** (`/api/v2/search`) | 100‑500 ms | Embedding index size | Use FAISS/HNSW index, keep it in RAM. |
| **KG Search** | 500‑2000 ms | Neo4j query complexity | Pre‑compute common relationships, tune Cypher queries. |
| **Enhanced Search** | 1‑3 s | Combined vector + KG + markdown rendering | Parallelise vector & KG stages (already async). |
| **Deep Crawl** | 30‑300 s (depends on `max_pages`) | Recursive network I/O | Run as background task, expose a webhook for completion notification. |

The service is **CPU‑bound** during heavy search; allocating multiple Uvicorn workers (`--workers 4`) on a multi‑core host yields near‑linear scaling.

---  

## Development Workflow & Testing
1. **Live Reload** – `uvicorn api.server:app --reload` watches source files and restarts automatically.  
2. **Unit Tests** – Place tests under `tests/` (e.g., `tests/test_crawl.py`). Use `pytest` with the `--asyncio` plugin for async endpoints.  
3. **Static Analysis** – Run `flake8` and `black --check .` to enforce style.  
4. **Integration Tests** – Spin up a Docker Compose stack that includes the **Crawl4AI** service and a **Neo4j** container; run end‑to‑end tests against `http://localhost:8080`.  
5. **CI** – A suggested GitHub Actions workflow:  
   ```yaml
   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Set up Python
           uses: actions/setup-python@v5
           with:
             python-version: "3.11"
         - name: Install deps
           run: |
             pip install -r robairagapi/requirements.txt
             pip install -r robairagapi/tests/requirements.txt
         - name: Lint
           run: |
             pip install flake8 black
             flake8 .
             black --check .
         - name: Test
           run: pytest robairagapi/tests
         - name: Build Docker image
           run: docker build -t robairagapi:ci -f Dockerfile .
   ```

---  

## Extending the API
When adding a new endpoint:

1. **Define a Pydantic model** in `api/models.py` (include validators).  
2. **Implement business logic** in a new `toolactions/operations/` module (or extend an existing one).  
3. **Add a route** in `api/server.py` – remember to add the `Depends(verify_api_key)` dependency for protected routes.  
4. **Update OpenAPI** – the `custom_openapi()` function automatically reflects new models; no manual changes required.  
5. **Write tests** covering happy path, validation failures, and security edge cases.  

---  

## CI/CD Pipeline (Suggested)
A robust pipeline could include:

| Stage | Tools |
|-------|-------|
| **Build** | Docker build (multi‑stage for minimal image). |
| **Static Analysis** | `flake8`, `black`, `mypy` (type checking). |
| **Unit Tests** | `pytest` with coverage (`--cov`). |
| **Integration Tests** | Docker Compose bringing up `crawl4ai` + Neo4j; run API smoke tests. |
| **Security Scan** | `bandit` for Python security linting; `trivy` for container vulnerability scanning. |
| **Deploy** | Push image to registry; Kubernetes `Deployment` with rolling update strategy; health checks ensure zero‑downtime. |

---  

## Contributing Guidelines
1. **Fork** the repository and create a feature branch (`git checkout -b feature/xyz`).  
2. **Write code** *and* update documentation (README, docs/*) accordingly.  
3. **Add tests** for any new functionality.  
4. **Run linters & tests** locally (`make lint && make test` if a Makefile is provided).  
5. **Submit a Pull Request** – CI will automatically verify style, tests, and Docker build.  
6. **Review** – maintainers will check for security implications (especially around URL validation and token handling).  

---  

## License & Contact
`robairagapi` is released under the **MIT License**.  
For questions, bug reports, or contribution discussions, please open an issue on the GitHub repository:  
<https://github.com/Rob-P-Smith/robaitools>

---  

*This documentation is intentionally exhaustive to enable AI agents and developers to understand, extend, and safely modify the `robairagapi` codebase without ambiguity.*
