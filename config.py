"""
Configuration management for RobAI RAG API Bridge
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # API Server
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))

    # Authentication
    LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")
    REMOTE_API_KEY_2 = os.getenv("REMOTE_API_KEY_2")

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    ENABLE_RATE_LIMIT = os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"

    # MCP Server Connection
    MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "3000"))
    MCP_CONNECTION_TIMEOUT = int(os.getenv("MCP_CONNECTION_TIMEOUT", "30"))

    # CORS
    ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []

        if not cls.LOCAL_API_KEY and not cls.REMOTE_API_KEY_2:
            errors.append("At least one API key must be configured (LOCAL_API_KEY or REMOTE_API_KEY_2)")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True


# Validate on import
Config.validate()
