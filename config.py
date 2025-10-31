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
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8081"))

    # Authentication
    LOCAL_API_KEY = os.getenv("OPENAI_API_KEY")
    REMOTE_API_KEY_2 = os.getenv("OPENAI_API_KEY_2")

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

    # Security Settings
    # pfSense firewall identification (for public proxy requests)
    PFSENSE_IP = os.getenv("PFSENSE_IP", "192.168.10.1")
    PFSENSE_MAC = os.getenv("PFSENSE_MAC", "58:9c:fc:10:ff:d8")

    # Trusted LAN subnet for relaxed authentication
    TRUSTED_LAN_SUBNET = os.getenv("TRUSTED_LAN_SUBNET", "192.168.10.0/24")

    # Enable strict authentication checks for pfSense proxy requests
    STRICT_AUTH_FOR_PFSENSE = os.getenv("STRICT_AUTH_FOR_PFSENSE", "true").lower() == "true"

    # Enable MAC address validation (IP + MAC verification)
    ENABLE_MAC_VALIDATION = os.getenv("ENABLE_MAC_VALIDATION", "true").lower() == "true"

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
