"""
Authentication middleware for RobAI RAG API Bridge
Handles API key validation, rate limiting, and session management
"""

import os
import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()


class RateLimiter:
    """
    Rate limiting for API requests

    Tracks requests per API key in sliding 60-second window.
    Can be disabled via ENABLE_RATE_LIMIT=false environment variable.
    """

    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        # Allow disabling rate limiter for bulk operations
        self.enabled = os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"

    def is_allowed(self, api_key: str) -> bool:
        """Check if request is allowed for given API key"""
        # If rate limiting is disabled, always allow
        if not self.enabled:
            return True

        now = time.time()
        minute_ago = now - 60

        # Remove requests older than 60 seconds
        self.requests[api_key] = [req_time for req_time in self.requests[api_key] if req_time > minute_ago]

        # Check if limit exceeded
        if len(self.requests[api_key]) >= self.max_requests:
            return False

        # Record this request
        self.requests[api_key].append(now)
        return True


class SessionManager:
    """
    Session management for API clients

    Creates and tracks sessions with 24-hour timeout.
    Auto-cleanup of expired sessions.
    """

    def __init__(self):
        self.sessions = {}
        self.session_timeout = timedelta(hours=24)

    def create_session(self, api_key: str) -> str:
        """Create new session for API key"""
        session_id = hashlib.sha256(f"{api_key}{time.time()}".encode()).hexdigest()[:16]
        self.sessions[session_id] = {
            "api_key": api_key,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "requests_count": 0
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session info, updating last activity timestamp"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Check if session expired
        if datetime.now() - session["last_activity"] > self.session_timeout:
            del self.sessions[session_id]
            return None

        # Update activity
        session["last_activity"] = datetime.now()
        session["requests_count"] += 1
        return session

    def cleanup_expired_sessions(self):
        """Remove all expired sessions"""
        now = datetime.now()
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if now - session["last_activity"] > self.session_timeout
        ]
        for sid in expired_sessions:
            del self.sessions[sid]


# Global instances
rate_limiter = RateLimiter()
session_manager = SessionManager()


def normalize_bearer_token(auth_header: str) -> Optional[str]:
    """
    Normalize Bearer token from Authorization header.

    Handles:
    - Case insensitivity (Bearer/bearer/BEARER)
    - Extra whitespace
    - Multiple spaces between Bearer and token

    Args:
        auth_header: Raw Authorization header value

    Returns:
        Normalized token or None if invalid format
    """
    if not auth_header:
        return None

    # Strip leading/trailing whitespace
    auth_header = auth_header.strip()

    # Check for "Bearer" prefix (case insensitive)
    if not auth_header.lower().startswith("bearer "):
        return None

    # Remove "Bearer " prefix and extract token
    # Split on whitespace and take the part after "Bearer"
    parts = auth_header.split(None, 1)  # Split on any whitespace, max 2 parts
    if len(parts) != 2:
        return None

    token = parts[1].strip()
    return token if token else None


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """
    Verify API key from Authorization header with enhanced normalization

    Args:
        credentials: HTTPBearer credentials from request header

    Returns:
        Dict with session information

    Raises:
        HTTPException: If API key invalid or rate limit exceeded
    """
    # Get raw token from credentials
    raw_token = credentials.credentials

    # Normalize the token (handle case, whitespace, etc.)
    token = normalize_bearer_token(f"Bearer {raw_token}")
    if not token:
        token = raw_token.strip()  # Fallback: just strip whitespace

    # Load all valid API keys from environment
    valid_keys = [
        os.getenv("OPENAI_API_KEY"),
    ]
    # Filter out None values and normalize them
    valid_keys = [key.strip() for key in valid_keys if key]

    if not valid_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: No API keys configured"
        )

    # Compare normalized tokens
    if token not in valid_keys:
        # Log failed authentication attempt for security monitoring
        token_preview = token[:8] + "..." if len(token) > 8 else token
        print(f"⚠️  SECURITY: Failed authentication attempt - Invalid token: {token_preview}", flush=True)

        # Return 404 to hide endpoint existence from attackers
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found"
        )

    # Check rate limit
    if not rate_limiter.is_allowed(token):
        print(f"⚠️  SECURITY: Rate limit exceeded for token: {token[:8]}...", flush=True)
        # Return 404 to hide endpoint existence (even for rate limiting)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found"
        )

    # Create session
    session_id = session_manager.create_session(token)

    return {
        "api_key": token,
        "session_id": session_id,
        "authenticated": True,
        "timestamp": datetime.now().isoformat()
    }


async def log_api_request(endpoint: str, method: str, session_info: Dict[str, Any],
                         status_code: int, response_time: float):
    """
    Log API request for audit trail

    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        session_info: Session information from verify_api_key
        status_code: HTTP response status code
        response_time: Request processing time in seconds
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "session_id": session_info.get("session_id"),
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2)
    }

    print(f"API Request: {log_entry}", flush=True)


def cleanup_sessions():
    """
    Cleanup expired sessions

    Call this periodically (e.g., hourly background task)
    to remove expired sessions and free memory.
    """
    session_manager.cleanup_expired_sessions()
