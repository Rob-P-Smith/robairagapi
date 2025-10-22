# Quick Start - RobAI RAG API Bridge

Get the API bridge running in 5 minutes.

## Prerequisites

- Docker and docker-compose installed
- robairagmcp MCP server (in ../robaitragmcp/)
- Crawl4AI service running on port 11235

## Step 1: Configure Environment

```bash
cd /home/robiloo/Documents/robaitools/robairagapi
cp .env.example .env
```

Edit `.env` and set your API key:
```bash
LOCAL_API_KEY=your-secret-key-here
```

## Step 2: Start Services

```bash
# Start both API bridge and MCP server
docker compose up -d
```

## Step 3: Verify It's Running

```bash
# Health check (no auth)
curl http://localhost:8080/health

# Test authenticated endpoint
curl -H "Authorization: Bearer your-secret-key-here" \
  http://localhost:8080/api/v1/status
```

## Step 4: Test Crawling & Search

```bash
# Crawl and store a page
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/tutorial/", "tags": "python,docs"}'

# Search stored content
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{"query": "python functions", "limit": 5}'
```

## Step 5: Access API Documentation

Open in browser:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## OpenWebUI Integration

1. In OpenWebUI, add connection:
   - URL: `http://localhost:8080`
   - Auth: Bearer Token
   - Token: `your-secret-key-here`

2. Test by crawling a URL through OpenWebUI interface

## Troubleshooting

**API not responding?**
```bash
docker logs robairagapi
```

**MCP server connection failed?**
```bash
docker logs robairagmcp
telnet localhost 3000
```

**Authentication errors?**
- Check API key matches .env file
- Verify Bearer token format: `Authorization: Bearer your-key`

## Next Steps

- Read [README.md](README.md) for full documentation
- Check available endpoints at http://localhost:8080/docs
- Integrate with OpenWebUI or other tools

That's it! Your REST API bridge to the MCP server is ready.
