"""
Input validation for API requests

Provides security and data validation before forwarding to MCP server.
Defense-in-depth strategy: validate at API layer before MCP layer.
"""

import sys
from urllib.parse import urlparse
from typing import Any


def validate_url(url: str) -> bool:
    """
    Validate URL for security and accessibility

    Checks:
    - Valid HTTP/HTTPS scheme
    - Valid hostname
    - Not localhost or private IP ranges
    - Not cloud metadata endpoints

    Args:
        url: URL string to validate

    Returns:
        bool: True if URL is valid and safe to crawl
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ['http', 'https']:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
            return False

        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            if any(hostname.lower().endswith(suffix) for suffix in ['.local', '.internal', '.corp']):
                return False

        metadata_ips = ['169.254.169.254', '100.100.100.200', '192.0.0.192']
        if hostname in metadata_ips:
            return False

        return True

    except Exception:
        return False


def validate_string_length(value: str, max_length: int, field_name: str) -> str:
    """
    Validate and truncate string to maximum length

    Args:
        value: String to validate
        max_length: Maximum allowed length
        field_name: Name of field for error messages

    Returns:
        str: Validated (possibly truncated) string

    Raises:
        ValueError: If value is not a string
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    if len(value) > max_length:
        print(f"Warning: {field_name} exceeds maximum length of {max_length}. Truncating.",
              file=sys.stderr, flush=True)
        return value[:max_length]

    return value


def validate_integer_range(value: int, min_val: int, max_val: int, field_name: str) -> int:
    """
    Validate integer is within acceptable range

    Args:
        value: Integer value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of field for error messages

    Returns:
        int: Validated integer value

    Raises:
        ValueError: If value is not an integer or outside range
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")

    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")

    return value


def validate_float_range(value: float, min_val: float, max_val: float, field_name: str) -> float:
    """
    Validate float is within acceptable range

    Args:
        value: Float value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of field for error messages

    Returns:
        float: Validated float value

    Raises:
        ValueError: If value is not a number or outside range
    """
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be a number")

    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")

    return float(value)


def validate_deep_crawl_params(max_depth: int, max_pages: int) -> tuple:
    """
    Validate deep crawl parameters

    Args:
        max_depth: Maximum crawl depth (1-5)
        max_pages: Maximum pages to crawl (1-250)

    Returns:
        tuple: (validated_max_depth, validated_max_pages)

    Raises:
        ValueError: If parameters are outside acceptable ranges
    """
    max_depth = validate_integer_range(max_depth, 1, 5, "max_depth")
    max_pages = validate_integer_range(max_pages, 1, 250, "max_pages")

    return max_depth, max_pages


def validate_mcp_response(response: dict) -> bool:
    """
    Validate MCP JSON-RPC 2.0 response structure

    Args:
        response: MCP response dictionary

    Returns:
        bool: True if response is valid

    Security layer: Ensure MCP server returns properly formatted responses
    """
    if not isinstance(response, dict):
        return False

    if response.get("jsonrpc") != "2.0":
        return False

    if "id" not in response:
        return False

    has_result = "result" in response
    has_error = "error" in response

    if has_result == has_error:
        return False

    return True


def sanitize_sql_input(value: str) -> str:
    """
    Basic SQL injection prevention for string inputs

    Args:
        value: String to sanitize

    Returns:
        str: Sanitized string

    Raises:
        ValueError: If dangerous patterns detected
    """
    dangerous_patterns = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'TRUNCATE', 'EXEC', 'EXECUTE', '--', ';--',
        'UNION', 'SCRIPT', '<script'
    ]

    value_upper = value.upper()
    for pattern in dangerous_patterns:
        if pattern in value_upper:
            raise ValueError(f"Invalid input: contains dangerous pattern '{pattern}'")

    return value
