"""
SQL Injection Defense Middleware

This module provides comprehensive input sanitization and validation to prevent
SQL injection attacks and other malicious input across the entire application.

All user inputs that could potentially reach the database should be sanitized
through this middleware before being processed.
"""

import re
from typing import Any, Optional, List, Dict
from urllib.parse import urlparse


class SQLInjectionDefense:
    """SQL Injection defense middleware with comprehensive input sanitization"""

    # Dangerous SQL keywords and patterns
    DANGEROUS_SQL_KEYWORDS = [
        # SQL Commands
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'EXEC', 'EXECUTE', 'UNION', 'JOIN', 'MERGE',

        # SQL Functions and Operations
        'CHAR', 'CONCAT', 'SUBSTRING', 'ASCII', 'HEX', 'UNHEX',
        'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE',

        # SQL Injection Patterns
        'OR 1=1', 'OR 1=0', 'AND 1=1', 'AND 1=0',
        "' OR '1'='1", '" OR "1"="1',

        # Comments and terminators
        '--', '/*', '*/', '#', ';--', '/**/', 'COMMENT',

        # Database introspection
        'INFORMATION_SCHEMA', 'SYSOBJECTS', 'SYSCOLUMNS',
        'TABLE_SCHEMA', 'TABLE_NAME', 'COLUMN_NAME',

        # Script injection
        '<SCRIPT', 'JAVASCRIPT:', 'ONERROR=', 'ONLOAD=',
        'EVAL(', 'EXPRESSION(', 'VBSCRIPT:',

        # Time-based attacks
        'SLEEP(', 'BENCHMARK(', 'WAITFOR DELAY',

        # Stacked queries
        '; DROP', '; DELETE', '; UPDATE', '; INSERT',
    ]

    # Dangerous characters that could be part of SQL injection
    DANGEROUS_CHARS = [
        '\x00',  # NULL byte
        '\x1a',  # EOF
        '\r\n',  # CRLF injection
    ]

    # Maximum safe lengths for different input types
    MAX_LENGTHS = {
        'url': 2048,
        'query': 1000,
        'tag': 100,
        'tags': 500,
        'description': 1000,
        'pattern': 200,
        'keyword': 100,
        'filter': 100,
        'title': 500,
    }

    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None,
                       field_name: str = "input") -> str:
        """
        Sanitize a string input to prevent SQL injection

        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            field_name: Name of the field (for error messages)

        Returns:
            Sanitized string

        Raises:
            ValueError: If input contains dangerous patterns
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")

        # Check for NULL bytes and other dangerous characters
        for char in SQLInjectionDefense.DANGEROUS_CHARS:
            if char in value:
                raise ValueError(f"{field_name} contains dangerous characters")

        # Convert to uppercase for keyword checking
        value_upper = value.upper()

        # Check for dangerous SQL keywords and patterns
        # Only check for SQL keywords if they appear in suspicious contexts
        # (e.g., with quotes, semicolons, or after operators like =, OR, AND)
        for keyword in SQLInjectionDefense.DANGEROUS_SQL_KEYWORDS:
            # Skip checking for keywords that are common in URLs/documentation
            # (UPDATE, SELECT, DELETE, INSERT, CREATE, ALTER, DROP, JOIN, UNION, EXECUTE, EXEC)
            common_url_words = ['UPDATE', 'SELECT', 'DELETE', 'INSERT', 'CREATE',
                               'ALTER', 'DROP', 'JOIN', 'UNION', 'EXECUTE', 'EXEC',
                               'MERGE', 'TRUNCATE']

            # For common SQL words, only flag if in suspicious context
            if keyword in common_url_words:
                # Check for suspicious patterns: keyword with quotes, semicolons, or operators
                suspicious_patterns = [
                    r"['\";]\s*" + re.escape(keyword),  # Quote before keyword
                    re.escape(keyword) + r"\s*['\";]",  # Quote after keyword
                    r"=\s*" + re.escape(keyword),        # Equals before keyword
                    r";\s*" + re.escape(keyword),        # Semicolon before keyword
                    r"\b(OR|AND)\s+" + re.escape(keyword),  # OR/AND before keyword
                ]
                if any(re.search(p, value_upper) for p in suspicious_patterns):
                    raise ValueError(
                        f"{field_name} contains potentially dangerous SQL pattern: {keyword}"
                    )
            else:
                # For other dangerous keywords (LOAD_FILE, SLEEP, etc.), always block
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, value_upper):
                    raise ValueError(
                        f"{field_name} contains potentially dangerous SQL pattern: {keyword}"
                    )

        # Check for common SQL injection patterns
        if re.search(r"['\";].*(\bOR\b|\bAND\b).*['\";=]", value_upper):
            raise ValueError(f"{field_name} contains SQL injection pattern")

        # Check for stacked queries
        if re.search(r';[\s]*\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b', value_upper):
            raise ValueError(f"{field_name} contains stacked query pattern")

        # Check maximum length
        if max_length and len(value) > max_length:
            raise ValueError(
                f"{field_name} exceeds maximum length of {max_length} characters"
            )

        # Remove any potential encoding tricks
        # Normalize unicode characters
        value = value.encode('utf-8', errors='ignore').decode('utf-8')

        return value

    @staticmethod
    def sanitize_url(url: str) -> str:
        """
        Sanitize and validate a URL input

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL

        Raises:
            ValueError: If URL is invalid or dangerous
        """
        if not isinstance(url, str):
            raise ValueError("URL must be a string")

        # Basic length check
        if len(url) > SQLInjectionDefense.MAX_LENGTHS['url']:
            raise ValueError(
                f"URL exceeds maximum length of {SQLInjectionDefense.MAX_LENGTHS['url']}"
            )

        # Check for NULL bytes and dangerous characters
        for char in SQLInjectionDefense.DANGEROUS_CHARS:
            if char in url:
                raise ValueError("URL contains dangerous characters")

        # Check for SQL keywords in URL (could be in query parameters)
        url_upper = url.upper()
        url_lower = url.lower()

        # Adult content word filter - block URLs containing these words anywhere
        ADULT_CONTENT_WORDS = [
            'dick', 'pussy', 'cock', 'tits', 'boobs', 'slut', 'cunt', 'fuck',
            'anal', 'throat', 'deepthroat', 'rape', 'incest', 'porn',
            'pron', 'spitroast', 'trans', 'gay', 'bisexual', 'girlongirl',
            'lesbian', 'xxx', 'nsfw', 'nude', 'naked', 'sex', 'hentai',
            'adullt', 'erotic', 'fetish', 'bdsm', 'milf'
        ]

        # Check for adult content words in URL (case-insensitive substring match)
        for word in ADULT_CONTENT_WORDS:
            if word in url_lower:
                raise ValueError(f"URL contains inappropriate content keyword: {word}")

        # More strict checking for dangerous SQL injection patterns in URLs
        # Note: Only block SQL keywords in suspicious contexts (query params, after special chars)
        # Allow legitimate URLs like /rules/no-delete-var or /components/select

        # These patterns should always be blocked (exact match)
        dangerous_exact_patterns = [
            '; DROP', '; DELETE', '; SELECT', '; INSERT', '; UPDATE',
            '<SCRIPT', 'JAVASCRIPT:', 'UNION SELECT', '1=1', '1 = 1',
            "'OR'", '"OR"', "' OR '", '" OR "', '-- ', '/*', '*/'
        ]

        # Check exact patterns (substring match)
        for pattern in dangerous_exact_patterns:
            if pattern in url_upper:
                raise ValueError(f"URL contains dangerous SQL injection pattern: {pattern}")

        # Check for SQL keywords in query parameters (after ? or &)
        # Pattern: keyword appears after = or after ? or & with suspicious chars
        sql_in_params_pattern = r'[?&=][^&]*\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|EXEC)\b'
        if re.search(sql_in_params_pattern, url_upper):
            raise ValueError(f"URL contains SQL keywords in query parameters")

        # Parse URL to validate structure (if it has a scheme)
        if '://' in url:
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError("Invalid URL structure")
            except Exception as e:
                raise ValueError(f"Invalid URL: {str(e)}")

        return url

    @staticmethod
    def sanitize_tags(tags: str | list) -> str:
        """
        Sanitize comma-separated tags

        Args:
            tags: Comma-separated tag string OR list of tags

        Returns:
            Sanitized tags string

        Raises:
            ValueError: If tags contain dangerous patterns
        """
        if not tags:
            return ""

        # Handle list input (e.g., from JSON/MCP)
        if isinstance(tags, list):
            tags = ','.join(str(tag) for tag in tags)

        # Check overall length
        sanitized = SQLInjectionDefense.sanitize_string(
            tags,
            max_length=SQLInjectionDefense.MAX_LENGTHS['tags'],
            field_name="tags"
        )

        # Split and validate individual tags
        tag_list = [tag.strip() for tag in sanitized.split(',')]

        for tag in tag_list:
            if tag and len(tag) > SQLInjectionDefense.MAX_LENGTHS['tag']:
                raise ValueError(
                    f"Individual tag exceeds maximum length of {SQLInjectionDefense.MAX_LENGTHS['tag']}"
                )

            # Tags should be alphanumeric, spaces, hyphens, underscores only
            if tag and not re.match(r'^[a-zA-Z0-9\s\-_]+$', tag):
                raise ValueError(
                    f"Tag contains invalid characters: {tag}. Only alphanumeric, spaces, hyphens, and underscores allowed."
                )

        return sanitized

    @staticmethod
    def sanitize_integer(value: Any, min_val: Optional[int] = None,
                        max_val: Optional[int] = None, field_name: str = "value") -> int:
        """
        Sanitize and validate an integer input

        Args:
            value: Value to convert to integer
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of the field (for error messages)

        Returns:
            Validated integer

        Raises:
            ValueError: If value is not a valid integer or out of range
        """
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be a valid integer")

        if min_val is not None and int_value < min_val:
            raise ValueError(f"{field_name} must be at least {min_val}")

        if max_val is not None and int_value > max_val:
            raise ValueError(f"{field_name} must be at most {max_val}")

        return int_value

    @staticmethod
    def sanitize_boolean(value: Any, field_name: str = "value") -> bool:
        """
        Sanitize and validate a boolean input

        Args:
            value: Value to convert to boolean
            field_name: Name of the field (for error messages)

        Returns:
            Boolean value

        Raises:
            ValueError: If value cannot be converted to boolean
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ('true', '1', 'yes', 'on'):
                return True
            elif value_lower in ('false', '0', 'no', 'off'):
                return False

        raise ValueError(f"{field_name} must be a boolean value")

    @staticmethod
    def sanitize_retention_policy(policy: str) -> str:
        """
        Validate retention policy against whitelist

        Args:
            policy: Retention policy string

        Returns:
            Validated policy

        Raises:
            ValueError: If policy is not in whitelist
        """
        VALID_POLICIES = {'permanent', 'session_only', '30_days'}

        if not isinstance(policy, str):
            raise ValueError("Retention policy must be a string")

        policy_lower = policy.lower()

        if policy_lower not in VALID_POLICIES:
            raise ValueError(
                f"Invalid retention policy. Must be one of: {', '.join(VALID_POLICIES)}"
            )

        return policy_lower

    @staticmethod
    def sanitize_pattern(pattern: str) -> str:
        """
        Sanitize domain blocking pattern

        Args:
            pattern: Pattern string (e.g., *.ru, *spam*)

        Returns:
            Sanitized pattern

        Raises:
            ValueError: If pattern contains dangerous content
        """
        sanitized = SQLInjectionDefense.sanitize_string(
            pattern,
            max_length=SQLInjectionDefense.MAX_LENGTHS['pattern'],
            field_name="pattern"
        )

        # Pattern should only contain: letters, numbers, dots, hyphens, asterisks
        if not re.match(r'^[a-zA-Z0-9.*\-_]+$', sanitized):
            raise ValueError(
                "Pattern can only contain letters, numbers, dots, hyphens, asterisks, and underscores"
            )

        return sanitized

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], schema: Dict[str, str]) -> Dict[str, Any]:
        """
        Sanitize a dictionary of inputs based on a schema

        Args:
            data: Dictionary to sanitize
            schema: Schema mapping field names to types
                   Types: 'string', 'url', 'tags', 'integer', 'boolean', 'retention_policy', 'pattern'

        Returns:
            Sanitized dictionary

        Raises:
            ValueError: If any field fails validation
        """
        sanitized = {}

        for field, field_type in schema.items():
            if field not in data:
                continue

            value = data[field]

            if value is None:
                sanitized[field] = None
                continue

            try:
                if field_type == 'string':
                    max_length = SQLInjectionDefense.MAX_LENGTHS.get(field, 1000)
                    sanitized[field] = SQLInjectionDefense.sanitize_string(
                        value, max_length=max_length, field_name=field
                    )

                elif field_type == 'url':
                    sanitized[field] = SQLInjectionDefense.sanitize_url(value)

                elif field_type == 'tags':
                    sanitized[field] = SQLInjectionDefense.sanitize_tags(value)

                elif field_type == 'integer':
                    sanitized[field] = SQLInjectionDefense.sanitize_integer(
                        value, field_name=field
                    )

                elif field_type == 'boolean':
                    sanitized[field] = SQLInjectionDefense.sanitize_boolean(
                        value, field_name=field
                    )

                elif field_type == 'retention_policy':
                    sanitized[field] = SQLInjectionDefense.sanitize_retention_policy(value)

                elif field_type == 'pattern':
                    sanitized[field] = SQLInjectionDefense.sanitize_pattern(value)

                else:
                    raise ValueError(f"Unknown field type: {field_type}")

            except ValueError as e:
                raise ValueError(f"Validation error in field '{field}': {str(e)}")

        return sanitized


# Convenience functions for common use cases
def sanitize_search_params(query: str, limit: int = 5, tags: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize search parameters"""
    result = {
        'query': SQLInjectionDefense.sanitize_string(
            query,
            max_length=SQLInjectionDefense.MAX_LENGTHS['query'],
            field_name='query'
        ),
        'limit': SQLInjectionDefense.sanitize_integer(
            limit, min_val=1, max_val=1000, field_name='limit'
        )
    }

    if tags:
        result['tags'] = SQLInjectionDefense.sanitize_tags(tags)

    return result


def sanitize_crawl_params(url: str, tags: Optional[str] = None,
                         retention_policy: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize crawl parameters"""
    result = {
        'url': SQLInjectionDefense.sanitize_url(url)
    }

    if tags:
        result['tags'] = SQLInjectionDefense.sanitize_tags(tags)

    if retention_policy:
        result['retention_policy'] = SQLInjectionDefense.sanitize_retention_policy(
            retention_policy
        )

    return result


def sanitize_block_domain_params(pattern: str, description: Optional[str] = None,
                                 keyword: Optional[str] = None) -> Dict[str, Any]:
    """Sanitize block domain parameters"""
    result = {
        'pattern': SQLInjectionDefense.sanitize_pattern(pattern)
    }

    if description:
        result['description'] = SQLInjectionDefense.sanitize_string(
            description,
            max_length=SQLInjectionDefense.MAX_LENGTHS['description'],
            field_name='description'
        )

    if keyword:
        result['keyword'] = SQLInjectionDefense.sanitize_string(
            keyword,
            max_length=SQLInjectionDefense.MAX_LENGTHS['keyword'],
            field_name='keyword'
        )

    return result
