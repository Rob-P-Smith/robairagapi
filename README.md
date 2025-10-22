# RobAI RAG API Bridge

Lightweight REST API bridge that translates HTTP requests to MCP protocol and forwards them to the **robairagmcp** MCP server. Designed for external tools like OpenWebUI to access RAG capabilities via REST endpoints.

## Architecture

```
External Clients (OpenWebUI, curl, scripts)
    ↓ HTTP REST (port 8080)
┌─────────────────────────┐
│  robairagapi            │
│  (FastAPI Bridge)       │
│  - Auth & Rate Limit    │
│  - REST → MCP translate │
│  - Validation Layer     │
└──────────┬──────────────┘
           │ TCP/JSON-RPC 2.0 (port 3000)
┌──────────▼──────────────┐
│  robairagmcp            │
│  (MCP Server)           │
│  - RAG operations       │
│  - Vector search        │
│  - Knowledge Graph      │
└─────────────────────────┘
```

## Features

- **REST API** - Standard HTTP/JSON endpoints
- **Bearer Token Auth** - API key authentication with rate limiting
- **MCP Translation** - Automatic REST ↔ MCP protocol conversion
- **Defense in Depth** - Multi-layer validation (API + MCP)
- **Lightweight** - ~50MB Docker image (no heavy ML dependencies)
- **OpenAPI Docs** - Auto-generated at `/docs`
- **Production Ready** - Health checks, error handling, logging

## Quick Start

### Prerequisites

- Docker and docker-compose installed
- robairagmcp MCP server (separate project)
- Crawl4AI service running on port 11235

### Option 1: Docker Deployment (Recommended)

1. **Configure environment**:
```bash
cd /path/to/robairagapi
cp .env.example .env
# Edit .env with your API keys and MCP server details
```

2. **Start services** (both API bridge and MCP server):
```bash
docker compose up -d
```

3. **Verify deployment**:
```bash
curl http://localhost:8080/health
```

### Option 2: Local Development

1. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Ensure MCP server is running** on TCP port 3000

5. **Run API bridge**:
```bash
python3 main.py
```

## API Endpoints

### Crawling

- `POST /api/v1/crawl` - Crawl URL without storing
- `POST /api/v1/crawl/store` - Crawl and store permanently
- `POST /api/v1/crawl/temp` - Crawl and store temporarily
- `POST /api/v1/crawl/deep/store` - Deep crawl multiple pages

### Search

- `POST /api/v1/search` - Simple vector similarity search
- `POST /api/v1/search/simple` - Alias for simple search
- `POST /api/v1/search/kg` - Knowledge Graph-enhanced search

### Memory Management

- `GET /api/v1/memory` - List stored content
- `DELETE /api/v1/memory?url=...` - Remove specific URL
- `DELETE /api/v1/memory/temp` - Clear temporary content

### Statistics

- `GET /api/v1/stats` - Database statistics
- `GET /api/v1/db/stats` - Alias for stats

### Domain Management

- `GET /api/v1/blocked-domains` - List blocked patterns
- `POST /api/v1/blocked-domains` - Add blocked pattern
- `DELETE /api/v1/blocked-domains?pattern=...&keyword=...` - Remove pattern

### System

- `GET /health` - Health check (no auth)
- `GET /api/v1/status` - Detailed status (requires auth)
- `GET /api/v1/help` - Tool documentation

## Authentication

All endpoints (except `/health`) require Bearer token authentication:

```bash
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/tutorial/", "tags": "python,docs"}'
```

## OpenWebUI Integration

1. **In OpenWebUI**, add a new connection:
   - **URL**: `http://your-server-ip:8080`
   - **Auth Type**: Bearer Token
   - **API Key**: Your configured `LOCAL_API_KEY`
   - **Name**: RobAI RAG API

2. **Test the connection**:
   - Try crawling and storing a URL
   - Search your stored content
   - List what's in memory

## Configuration

See [`.env.example`](.env.example) for all configuration options:

```bash
# API Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Authentication (required)
LOCAL_API_KEY=your-secret-key

# MCP Server Connection (required)
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=3000

# Rate Limiting (optional)
RATE_LIMIT_PER_MINUTE=60
ENABLE_RATE_LIMIT=true

# CORS (optional)
CORS_ORIGINS=*
```

## Validation Layers

This API implements defense-in-depth with 5 validation layers:

1. **API Input Validation** - Pydantic models, URL format, SQL injection prevention
2. **MCP Request Validation** - JSON-RPC 2.0 format, parameter completeness
3. **MCP Server Validation** - Re-validates all inputs in MCP server
4. **MCP Response Validation** - Validates response structure before sending
5. **API Response Validation** - Final check before returning to client

## Development

### Project Structure

```
robairagapi/
├── api/
│   ├── __init__.py
│   ├── server.py         # FastAPI endpoints
│   ├── auth.py           # Authentication & rate limiting
│   ├── models.py         # Pydantic request/response models
│   └── validation.py     # Input validation
├── mcp/
│   ├── __init__.py
│   ├── client.py         # TCP client for MCP server
│   ├── protocol.py       # JSON-RPC 2.0 implementation
│   └── translator.py     # REST ↔ MCP translation
├── docs/                 # Documentation
├── config.py             # Configuration management
├── main.py               # Entry point
├── requirements.txt      # Dependencies
├── Dockerfile            # Lightweight API container
└── docker-compose.yml    # Co-deployment config
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests (when implemented)
pytest
```

## Troubleshooting

### API not connecting to MCP server

- Verify MCP server is running: `docker logs robairagmcp`
- Check MCP server is listening on TCP port 3000
- Verify network connectivity: `telnet localhost 3000`

### Authentication errors

- Check API keys are configured in `.env`
- Verify Bearer token format: `Authorization: Bearer your-key`
- Check rate limit not exceeded (60 req/min default)

### Docker container exits

```bash
# Check logs
docker logs robairagapi

# Rebuild
docker compose build --no-cache
docker compose up -d
```

## MCP Server Setup (robairagmcp)

The API bridge requires the **robairagmcp** MCP server to be running with TCP/socat support:

```bash
# In robairagmcp project, update docker-compose.yml:
command: ["socat", "TCP-LISTEN:3000,reuseaddr,fork", "EXEC:'python3 core/rag_processor.py'"]
```

Or update the Dockerfile to install socat:
```dockerfile
RUN apt-get update && apt-get install -y socat
```

## Comparison with mcpragcrawl4ai

| Feature | robairagapi | mcpragcrawl4ai |
|---------|-------------|----------------|
| **Purpose** | REST API bridge | Full-stack RAG system |
| **Backend** | MCP server (external) | Integrated RAG core |
| **Dependencies** | FastAPI only (~5 libs) | Full ML stack (~20+ libs) |
| **Docker Size** | ~50MB | ~600MB |
| **Use Case** | External API access | Standalone RAG + API |
| **Mode** | API-only | Server + Client modes |

**Use robairagapi when**: You want lightweight API access for external tools (OpenWebUI, scripts)

**Use mcpragcrawl4ai when**: You need a complete standalone RAG system with REST API

## License

Part of the RobAI tools suite.

## Related Projects

- **robairagmcp** - MCP server (backend for this API bridge)
- **mcpragcrawl4ai** - Full-stack RAG system with integrated API
