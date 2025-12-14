import sys
import os
import requests
import hashlib
import time
from typing import Dict, Optional
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from robaitools root .env
    env_path = Path(__file__).resolve().parents[2] / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not available, rely on system env vars


def generate_content_id(url: str) -> int:
    """
    Generate a unique content ID by hashing URL + timestamp

    Args:
        url: The URL to generate ID for

    Returns:
        int: Last 7 digits of the hash as content_id
    """
    content = f"{url}{time.time()}"
    hash_obj = hashlib.sha256(content.encode())
    hash_hex = hash_obj.hexdigest()
    # Take last 7 hex digits and convert to int
    content_id = int(hash_hex[-7:], 16)
    return content_id


def _crawl_with_params(crawl4ai_url: str, url: str, params: dict, timeout: int = 30) -> Optional[dict]:
    """
    Internal helper: Make a single crawl attempt with given parameters.

    Args:
        crawl4ai_url: Base URL of Crawl4AI service
        url: Target URL to crawl
        params: Parameters to send to crawl4ai
        timeout: Request timeout in seconds

    Returns:
        Response dict from crawl4ai, or None if request fails
    """
    try:
        response = requests.post(
            f"{crawl4ai_url}/crawl",
            json=params,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Crawl attempt failed with params {params.keys()}: {str(e)}", file=sys.stderr, flush=True)
        return None


def _crawl_url_with_fallback(crawl4ai_url: str, url: str) -> Optional[dict]:
    """
    Internal helper: Try crawling with progressively simpler parameter sets.

    Attempts three strategies:
    1. Full parameters (only_text, word_count_threshold, excluded_tags, remove_forms)
    2. Without only_text (allows crawl4ai to handle markdown conversion differently)
    3. Minimal parameters (just urls and basic excludes)

    Args:
        crawl4ai_url: Base URL of Crawl4AI service
        url: Target URL to crawl

    Returns:
        First successful crawl4ai response, or None if all attempts fail
    """
    # Attempt 1: Full parameters (current behavior)
    print(f"Attempting crawl with full parameters for {url}", file=sys.stderr, flush=True)
    result = _crawl_with_params(crawl4ai_url, url, {
        "urls": [url],
        "word_count_threshold": 10,
        "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
        "remove_forms": True,
        "only_text": True
    })
    if result and result.get("success") and result.get("results"):
        first_result = result["results"][0]
        # Check if this specific URL succeeded (no error field)
        if "error" not in first_result or not first_result.get("error"):
            print(f"✓ Crawl succeeded with full parameters", file=sys.stderr, flush=True)
            return result
        else:
            # Log the error and continue to next fallback
            error_msg = first_result.get("error", "unknown")
            print(f"✗ Crawl4ai error with full params: {error_msg}", file=sys.stderr, flush=True)

    # Attempt 2: Without only_text (less aggressive markdown processing)
    print(f"Retrying without only_text parameter for {url}", file=sys.stderr, flush=True)
    result = _crawl_with_params(crawl4ai_url, url, {
        "urls": [url],
        "word_count_threshold": 10,
        "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
        "remove_forms": True
    })
    if result and result.get("success") and result.get("results"):
        first_result = result["results"][0]
        if "error" not in first_result or not first_result.get("error"):
            print(f"✓ Crawl succeeded without only_text", file=sys.stderr, flush=True)
            return result
        else:
            error_msg = first_result.get("error", "unknown")
            print(f"✗ Crawl4ai error without only_text: {error_msg}", file=sys.stderr, flush=True)

    # Attempt 3: Minimal parameters
    print(f"Retrying with minimal parameters for {url}", file=sys.stderr, flush=True)
    result = _crawl_with_params(crawl4ai_url, url, {
        "urls": [url],
        "excluded_tags": ['script', 'style']
    })
    if result and result.get("success") and result.get("results"):
        first_result = result["results"][0]
        if "error" not in first_result or not first_result.get("error"):
            print(f"✓ Crawl succeeded with minimal parameters", file=sys.stderr, flush=True)
            return result
        else:
            error_msg = first_result.get("error", "unknown")
            print(f"✗ Crawl4ai error with minimal params: {error_msg}", file=sys.stderr, flush=True)

    print(f"✗ All crawl attempts failed for {url}", file=sys.stderr, flush=True)
    return None


async def crawl_url(crawl4ai_url: str, url: str, return_full_content: bool = False, max_chars: int = 5000) -> dict:
    """
    Crawl a single URL and return extracted content

    Performs domain blocking check, content extraction via Crawl4AI,
    error page detection, and content cleaning.

    NOTE: return_full_content parameter is deprecated and ignored.
    Always returns cleaned markdown to prevent storing garbage in the database.

    Args:
        crawl4ai_url: Base URL of the Crawl4AI service
        url: Target URL to crawl
        return_full_content: DEPRECATED - ignored, always returns cleaned content
        max_chars: Maximum characters to return (default: 5000, range: 5000-25000).
                   Responses under the limit are returned in full. Truncated responses include a notification.

    Returns:
        Dict containing:
            - success: bool
            - url: str
            - title: str
            - content: str (raw HTML for reference)
            - markdown: str (cleaned and truncated if needed)
            - status_code: int
            - truncated: bool (True if content was truncated)
            - original_length: int (length before truncation)
            - error: str (if failed)
    """
    try:
        from api.toolactions.utilities.blockeddomains import is_domain_blocked
        from api.toolactions.data.content_cleaner import ContentCleaner
        from api.toolactions.operations.validation import validate_url
        from api.toolactions.data.dbdefense import SQLInjectionDefense

        # BEFORE-CRAWL DEFENSE LAYER 0: Domain blocking (earliest check)
        block_check = is_domain_blocked(url)
        if block_check["blocked"]:
            return {
                "success": False,
                "error": f"Domain blocked: {block_check['reason']}",
                "blocked": True,
                "category": block_check["category"],
                "url": url
            }

        # BEFORE-CRAWL DEFENSE LAYER 1: SSRF Protection
        if not validate_url(url):
            return {
                "success": False,
                "error": "Invalid or unsafe URL (localhost, private IP, or internal domain blocked)",
                "url": url
            }

        # BEFORE-CRAWL DEFENSE LAYER 2: Adult content & SQL injection in URL
        try:
            sanitized_url = SQLInjectionDefense.sanitize_url(url)
        except ValueError as e:
            return {
                "success": False,
                "error": f"URL blocked by security filter: {str(e)}",
                "url": url,
                "blocked_by": "dbdefense"
            }

        # Use fallback strategy to handle sites that break crawl4ai's markdown processing
        result = _crawl_url_with_fallback(crawl4ai_url, url)

        if not result:
            return {
                "success": False,
                "error": "All crawl attempts failed - crawl4ai unavailable or incompatible site structure",
                "url": url
            }

        if result.get("success") and result.get("results"):
            crawl_result = result["results"][0]
            content = crawl_result.get("cleaned_html", "")

            # Improved markdown extraction with null checks and HTML fallback
            markdown = ""
            markdown_obj = crawl_result.get("markdown", {})
            if isinstance(markdown_obj, dict):
                # Prefer fit_markdown (cleaned) over raw_markdown
                markdown = markdown_obj.get("fit_markdown", "") or markdown_obj.get("raw_markdown", "")

            # Fall back to cleaned_html if markdown is empty or invalid
            if not markdown or not isinstance(markdown, str):
                markdown = content
                print(f"Warning: Using cleaned_html fallback for {url} (markdown unavailable)",
                      file=sys.stderr, flush=True)
            title = crawl_result.get("metadata", {}).get("title", "")
            status_code = crawl_result.get("metadata", {}).get("status_code", 0)

            if status_code >= 400:
                return {
                    "success": False,
                    "error": f"HTTP {status_code} error",
                    "status_code": status_code,
                    "url": url
                }

            # Check if page is an error/rate-limited page
            error_check = ContentCleaner.is_error_page(markdown or content, title, status_code)
            if error_check["is_error"]:
                return {
                    "success": False,
                    "error": f"Error page detected: {error_check['reason']}",
                    "error_reason": error_check["reason"],
                    "url": url
                }

            # Clean the markdown content to remove navigation/boilerplate
            cleaned_result = ContentCleaner.clean_and_validate(content, markdown, url)
            cleaned_markdown = cleaned_result["cleaned_content"]

            # Validate max_chars parameter (enforce 5000-25000 range)
            if max_chars < 5000:
                max_chars = 5000  # Enforce minimum
            elif max_chars > 25000:
                max_chars = 25000  # Enforce maximum

            # Truncate if needed (after cleaning, before return)
            truncated = False
            original_length = len(cleaned_markdown)

            if max_chars > 0 and original_length > max_chars:
                cleaned_markdown = cleaned_markdown[:max_chars]
                cleaned_markdown += "\n\n((This response has been truncated, crawl with a longer limit if more is required from this page))"
                truncated = True

            # Return cleaned markdown with truncation metadata
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": content,  # Keep raw HTML for reference
                "markdown": cleaned_markdown,  # Cleaned and truncated if needed
                "status_code": status_code,
                "content_length": len(cleaned_markdown),
                "truncated": truncated,
                "original_length": original_length,
                "cleaning_stats": {
                    "original_lines": cleaned_result.get("original_lines", 0),
                    "cleaned_lines": cleaned_result.get("cleaned_lines", 0),
                    "reduction_ratio": cleaned_result.get("reduction_ratio", 0),
                    "navigation_indicators": cleaned_result.get("navigation_indicators", 0)
                }
            }
    except Exception as e:
        print(f"Error crawling URL {url}: {str(e)}", file=sys.stderr, flush=True)
        return {"success": False, "error": str(e)}


async def crawl_and_store(crawl4ai_url: str, url: str, retention_policy: str = 'permanent',
                          tags: str = '') -> dict:
    """
    Crawl a URL and store the content in the database

    Combines crawling with persistent storage, triggering embedding
    generation and knowledge graph queue population.

    Args:
        crawl4ai_url: Base URL of the Crawl4AI service
        url: Target URL to crawl
        retention_policy: Storage retention policy ('permanent', 'session_only', '30_days')
        tags: Comma-separated tags for categorization

    Returns:
        Dict containing:
            - success: bool
            - url: str
            - title: str
            - content_preview: str
            - content_length: int
            - stored: bool
            - retention_policy: str
            - message: str
            - error: str (if failed)
    """
    try:
        from api.toolactions.utilities.blockeddomains import is_domain_blocked
        from api.toolactions.data.dbdefense import SQLInjectionDefense

        # BEFORE-CRAWL DEFENSE LAYER 0: Domain blocking (earliest check)
        block_check = is_domain_blocked(url)
        if block_check["blocked"]:
            return {
                "success": False,
                "error": f"Domain blocked: {block_check['reason']}",
                "blocked": True,
                "category": block_check["category"],
                "url": url
            }

        # BEFORE-CRAWL DEFENSE LAYER 3: Sanitize user-provided parameters
        # Tags could contain SQL injection attempts
        if tags:
            try:
                tags = SQLInjectionDefense.sanitize_tags(tags)
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Invalid tags: {str(e)}",
                    "url": url
                }

        # Validate retention policy against whitelist
        try:
            retention_policy = SQLInjectionDefense.sanitize_retention_policy(retention_policy)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid retention policy: {str(e)}",
                "url": url
            }

        # Now crawl with validated parameters
        crawl_result = await crawl_url(crawl4ai_url, url, return_full_content=True)

        if not crawl_result.get("success"):
            return crawl_result

        # Send to robaigraphrag for ingestion into Neo4j
        print(f"Sending to robaigraphrag for ingestion", file=sys.stderr, flush=True)
        try:
            import requests

            graphrag_url = os.getenv("ROBAIGRAPHRAG_URL", "http://localhost:8089")
            api_key = os.getenv("OPENAI_API_KEY", "")
            print(f"GraphRAG URL: {graphrag_url}, has_api_key={bool(api_key)}", file=sys.stderr, flush=True)

            if api_key:
                content_id = generate_content_id(url)
                payload = {
                    "content_id": content_id,
                    "url": url,
                    "title": crawl_result["title"],
                    "markdown": crawl_result.get("markdown", ""),
                    "metadata": {
                        "retention_policy": retention_policy or "permanent",
                        "tags": tags,
                        "source": "crawl4ai",
                        "user": "Robert P Smith"
                    }
                }

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }

                try:
                    response = requests.post(
                        f"{graphrag_url}/api/v1/ingest",
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    if response.status_code == 200:
                        print(f"✓ Content ingested to robaigraphrag", file=sys.stderr, flush=True)
                    else:
                        print(f"⚠️  robaigraphrag returned status {response.status_code}", file=sys.stderr, flush=True)
                        return {
                            "success": False,
                            "error": f"GraphRAG ingestion failed with status {response.status_code}",
                            "url": url
                        }
                except requests.exceptions.ConnectionError:
                    print(f"ℹ️  robaigraphrag not available", file=sys.stderr, flush=True)
                    return {
                        "success": False,
                        "error": "GraphRAG service not available",
                        "url": url
                    }
                except requests.exceptions.Timeout:
                    print(f"⚠️  robaigraphrag timeout", file=sys.stderr, flush=True)
                    return {
                        "success": False,
                        "error": "GraphRAG service timeout",
                        "url": url
                    }
                except Exception as req_err:
                    print(f"⚠️  robaigraphrag error: {req_err}", file=sys.stderr, flush=True)
                    return {
                        "success": False,
                        "error": f"GraphRAG error: {str(req_err)}",
                        "url": url
                    }
            else:
                return {
                    "success": False,
                    "error": "OPENAI_API_KEY not configured",
                    "url": url
                }
        except Exception as e:
            print(f"⚠️  robaigraphrag ingestion failed: {e}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": f"Ingestion error: {str(e)}",
                "url": url
            }

        return {
            "success": True,
            "url": url,
            "title": crawl_result["title"],
            "content_preview": crawl_result["content"][:200] + "..." if len(crawl_result["content"]) > 200 else crawl_result["content"],
            "content_length": len(crawl_result["content"]),
            "stored": True,
            "retention_policy": retention_policy,
            "message": f"Successfully crawled and stored '{crawl_result['title']}' ({len(crawl_result['content'])} characters)"
        }
    except Exception as e:
        print(f"Error storing content from {url}: {str(e)}", file=sys.stderr, flush=True)
        return {"success": False, "error": str(e)}
