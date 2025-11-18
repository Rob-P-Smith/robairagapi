"""
RobAI RAG API Bridge - Main Entry Point

Starts the FastAPI server using Uvicorn.
"""

import uvicorn
from config import Config

if __name__ == "__main__":
    print(f"🚀 Starting RobAI RAG API Bridge on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    print(f"   MCP Server: {Config.MCP_SERVER_HOST}:{Config.MCP_SERVER_PORT}")
    print(f"   CORS: {'Enabled' if Config.ENABLE_CORS else 'Disabled'}")
    print(f"   Rate Limiting: {'Enabled' if Config.ENABLE_RATE_LIMIT else 'Disabled'}")
    print()
    print(f"   API Docs: http://{Config.SERVER_HOST}:{Config.SERVER_PORT}/docs")
    print(f"   Health Check: http://{Config.SERVER_HOST}:{Config.SERVER_PORT}/health")
    print()

    uvicorn.run(
        "api.server:app",
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        log_level=Config.LOG_LEVEL.lower(),
        reload=False
    )
