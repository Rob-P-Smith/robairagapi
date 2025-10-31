"""
Security middleware for robairagapi
Implements IP+MAC validation and protection against bypass attacks
"""

import re
from typing import Optional, Tuple
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from api.network_utils import get_mac_address_from_ip, ip_in_subnet
from config import Config


class SecurityValidator:
    """
    Security validation for incoming requests.

    Implements strict validation for pfSense proxy requests and
    relaxed validation for internal LAN requests.
    """

    def __init__(self):
        self.pfsense_ip = Config.PFSENSE_IP
        self.pfsense_mac = Config.PFSENSE_MAC
        self.trusted_subnet = Config.TRUSTED_LAN_SUBNET
        self.strict_mode_enabled = Config.STRICT_AUTH_FOR_PFSENSE
        self.mac_validation_enabled = Config.ENABLE_MAC_VALIDATION

    def get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request.

        Checks X-Forwarded-For first (for proxy), then falls back to client.host.
        """
        # Check X-Forwarded-For header (set by pfSense/proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can be comma-separated list, take first IP
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    def validate_ip_and_mac(self, request: Request) -> Tuple[str, Optional[str], bool]:
        """
        Validate client IP and MAC address.

        Returns:
            Tuple of (client_ip, mac_address, is_pfsense_request)
        """
        client_ip = self.get_client_ip(request)

        # Get MAC address if IP validation is enabled
        mac_address = None
        if self.mac_validation_enabled and client_ip != "unknown":
            mac_address = get_mac_address_from_ip(client_ip)

        # Check if this is a pfSense proxy request
        is_pfsense = False
        if client_ip == self.pfsense_ip:
            if self.mac_validation_enabled:
                # Verify MAC address matches
                if mac_address and mac_address.lower() == self.pfsense_mac.lower():
                    is_pfsense = True
                else:
                    # IP matches but MAC doesn't - possible spoofing attempt
                    print(f"⚠️  SECURITY ALERT: IP {client_ip} matches pfSense but MAC doesn't match "
                          f"(expected: {self.pfsense_mac}, got: {mac_address})", flush=True)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Invalid network identity"
                    )
            else:
                # MAC validation disabled, just check IP
                is_pfsense = True

        return client_ip, mac_address, is_pfsense

    def check_authorization_header_security(self, request: Request, is_strict: bool):
        """
        Check Authorization header for common bypass attempts.

        Args:
            request: FastAPI request object
            is_strict: True for strict validation (pfSense), False for relaxed (LAN)
        """
        # Get all Authorization headers (should only be one)
        auth_headers = request.headers.getlist("Authorization")

        if is_strict:
            # Strict mode: Exactly one Authorization header required
            if len(auth_headers) == 0:
                print(f"⚠️  SECURITY: Missing Authorization header from {self.get_client_ip(request)}",
                      flush=True)
                # Return 404 to hide endpoint existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not Found"
                )

            if len(auth_headers) > 1:
                print(f"⚠️  SECURITY: Multiple Authorization headers detected from {self.get_client_ip(request)}",
                      flush=True)
                # Return 404 to hide endpoint existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not Found"
                )

            # Check for suspicious authorization-related headers
            suspicious_headers = [
                "X-Authorization",
                "X-Forwarded-Authorization",
                "X-Original-Authorization",
                "X-Auth",
                "Proxy-Authorization"
            ]

            for header in suspicious_headers:
                if request.headers.get(header):
                    print(f"⚠️  SECURITY: Suspicious header '{header}' detected from {self.get_client_ip(request)}",
                          flush=True)
                    # Return 404 to hide endpoint existence
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Not Found"
                    )

    def check_path_security(self, request: Request, is_strict: bool):
        """
        Check request path for traversal and injection attempts.

        Args:
            request: FastAPI request object
            is_strict: True for strict validation, False for relaxed
        """
        path = request.url.path

        if is_strict:
            # Check for path traversal attempts
            if ".." in path:
                print(f"⚠️  SECURITY: Path traversal attempt '..' in {path} from {self.get_client_ip(request)}",
                      flush=True)
                # Return 404 to hide endpoint existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not Found"
                )

            # Check for encoded path traversal
            encoded_patterns = ["%2e%2e", "%2f", "%5c", "%00"]
            path_lower = path.lower()
            for pattern in encoded_patterns:
                if pattern in path_lower:
                    print(f"⚠️  SECURITY: Encoded path attack '{pattern}' in {path} from {self.get_client_ip(request)}",
                          flush=True)
                    # Return 404 to hide endpoint existence
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Not Found"
                    )

    def check_method_override(self, request: Request, is_strict: bool):
        """
        Check for HTTP method override attempts.

        Args:
            request: FastAPI request object
            is_strict: True for strict validation, False for relaxed
        """
        if is_strict:
            override_headers = [
                "X-HTTP-Method-Override",
                "X-Method-Override",
                "X-HTTP-Method"
            ]

            for header in override_headers:
                if request.headers.get(header):
                    print(f"⚠️  SECURITY: Method override attempt via '{header}' from {self.get_client_ip(request)}",
                          flush=True)
                    # Return 404 to hide endpoint existence
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Not Found"
                    )

    def check_protocol_downgrade(self, request: Request, is_strict: bool):
        """
        Check for protocol downgrade/upgrade attempts.

        Args:
            request: FastAPI request object
            is_strict: True for strict validation, False for relaxed
        """
        if is_strict:
            if request.headers.get("Upgrade"):
                print(f"⚠️  SECURITY: Protocol upgrade attempt from {self.get_client_ip(request)}",
                      flush=True)
                # Return 404 to hide endpoint existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not Found"
                )

    async def validate_request(self, request: Request):
        """
        Main validation function - validates entire request for security issues.

        Args:
            request: FastAPI request object

        Raises:
            HTTPException: If security validation fails
        """
        # NO PUBLIC ENDPOINTS - All requests must pass security validation
        # (Documentation endpoints /docs, /redoc, /openapi.json now require auth)

        # Validate IP and MAC
        client_ip, mac_address, is_pfsense = self.validate_ip_and_mac(request)

        # Determine if strict mode should be applied
        is_strict = is_pfsense and self.strict_mode_enabled

        # Log request details
        if is_pfsense:
            print(f"🔒 STRICT MODE: Request from pfSense ({client_ip}, MAC: {mac_address})", flush=True)
        else:
            print(f"🔓 RELAXED MODE: Request from LAN ({client_ip})", flush=True)

        # Run security checks
        self.check_authorization_header_security(request, is_strict)
        self.check_path_security(request, is_strict)
        self.check_method_override(request, is_strict)
        self.check_protocol_downgrade(request, is_strict)


# Global security validator instance
security_validator = SecurityValidator()


async def security_middleware(request: Request, call_next):
    """
    Security middleware for FastAPI.

    Validates requests before they reach endpoint handlers.
    """
    try:
        # Validate request security
        await security_validator.validate_request(request)

        # Continue to next middleware/handler
        response = await call_next(request)
        return response

    except HTTPException as e:
        # Return HTTP exception as JSON response
        return JSONResponse(
            status_code=e.status_code,
            content={
                "success": False,
                "error": e.detail,
                "timestamp": datetime.now().isoformat()
            },
            headers=e.headers
        )
    except Exception as e:
        # Unexpected error
        print(f"❌ Security middleware error: {e}", flush=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal security error",
                "timestamp": datetime.now().isoformat()
            }
        )
