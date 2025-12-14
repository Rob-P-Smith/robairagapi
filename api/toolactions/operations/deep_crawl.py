import sys
import os
import time
import requests
import hashlib
import traceback
from typing import Dict, Any
from urllib.parse import urlparse

from api.toolactions.operations.validation import validate_deep_crawl_params


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


def is_english(content: str, url: str = "") -> bool:
    """
    Simple keyword-based English detection

    Checks for at least ONE common English word or technical term.
    This is intentionally permissive for technical documentation.

    Args:
        content: Text content to analyze
        url: URL being checked (for logging)

    Returns:
        bool: True if English content detected
    """
    if not content or len(content) < 50:
        return False

    content_lower = content.lower()

    english_indicators = [
        'the ', 'and ', 'for ', 'are ', 'not ', 'you ', 'with ',
        'from ', 'this ', 'that ', 'have ', 'was ', 'can ', 'will ',
        'about ', 'when ', 'where ', 'what ', 'which ', 'who ',
        'use ', 'example', 'code', 'function', 'class', 'method',
        'install', 'configure', 'documentation', 'guide', 'tutorial',
        'how to', 'getting started', 'introduction', 'overview'
    ]

    sample_text = content_lower[:2000]
    for indicator in english_indicators:
        if indicator in sample_text:
            print(f"✓ English detected ('{indicator.strip()}'): {url}", file=sys.stderr, flush=True)
            return True

    print(f"⊘ No English keywords found: {url}", file=sys.stderr, flush=True)
    return False


def add_links_to_queue(links: dict, visited: set, queue: list,
                       current_depth: int, base_domain: str, include_external: bool):
    """
    Extract internal links and add to BFS queue

    Filters out blocked domains, social media, and adult content patterns.

    Args:
        links: Dict containing internal and external links
        visited: Set of already visited URLs
        queue: BFS queue to append new URLs to
        current_depth: Current crawl depth
        base_domain: Base domain for internal link filtering
        include_external: Whether to include external domain links
    """
    # Social media and unwanted link patterns to exclude from deep crawl
    SOCIAL_MEDIA_PATTERNS = [
        'facebook.com', 'fb.com', 'instagram.com', 'twitter.com', 'x.com',
        'linkedin.com', 'tiktok.com', 'pinterest.com', 'bluesky.social',
        'reddit.com', 'discourse.', 'forum.', 'mailto:', 'donate', 'donation',
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'snapchat.com', 'whatsapp.com', 'telegram.', 'discord.gg', 'discord.com',
        'twitch.tv', 'substack.com', 'patreon.com'
    ]

    # Adult content word filter - exclude URLs containing these words
    ADULT_CONTENT_WORDS = [
        'dick', 'pussy', 'cock', 'tits', 'boobs', 'slut', 'cunt', 'fuck',
        'anal', 'cum', 'throat', 'deepthroat', 'rape', 'incest', 'porn',
        'pron', 'spitroast', 'trans', 'gay', 'bisexual', 'girlongirl',
        'lesbian'
    ]

    # Safe words that should not be filtered even if they contain adult words
    SAFE_WORD_EXCEPTIONS = [
        'document', 'documentation', 'documents', 'documented',
        'circumstance', 'circumstances', 'accumulate', 'accumulated',
        'scum', 'vacuum', 'cucumber', 'circumference', 'circumvent'
    ]

    internal_links = links.get("internal", [])

    for link in internal_links:
        link_url = link.get("href", "")
        if not link_url or link_url in visited:
            continue

        # DEFENSE LAYER 0: Domain blocking (first check)
        from api.toolactions.utilities.blockeddomains import is_domain_blocked
        block_check = is_domain_blocked(link_url)
        if block_check["blocked"]:
            print(f"⊘ Blocked domain ({block_check['category']}): {link_url}",
                  file=sys.stderr, flush=True)
            continue

        # DEFENSE LAYER 1: Check for social media and unwanted patterns
        link_lower = link_url.lower()
        if any(pattern in link_lower for pattern in SOCIAL_MEDIA_PATTERNS):
            print(f"⊘ Skipping social/unwanted link: {link_url}", file=sys.stderr, flush=True)
            continue

        # Check for adult content words in URL with smart filtering
        has_safe_word = any(safe_word in link_lower for safe_word in SAFE_WORD_EXCEPTIONS)

        if not has_safe_word:
            # Only check adult words if no safe word exception found
            if any(word in link_lower for word in ADULT_CONTENT_WORDS):
                print(f"⊘ Skipping adult content link: {link_url}", file=sys.stderr, flush=True)
                continue

        # Domain check
        link_domain = urlparse(link_url).netloc
        if not include_external and link_domain != base_domain:
            continue

        queue.append((link_url, current_depth + 1))


def deep_crawl_and_store(crawl4ai_url: str, url: str, retention_policy: str = 'permanent',
                         tags: str = '', max_depth: int = 2, max_pages: int = 10,
                         include_external: bool = False, score_threshold: float = 0.0,
                         timeout: int = None) -> dict:
    """
    Client-side BFS deep crawl with English-only language filtering

    Algorithm:
    1. Initialize: visited set, BFS queue [(url, depth)]
    2. While queue not empty and stored < max_pages:
       a. Pop URL from queue (BFS order)
       b. Crawl single page via Crawl4AI
       c. Check language (keyword-based English detection)
       d. If English: store in database
       e. If non-English: skip storage, log
       f. Extract links, add to queue for next depth
    3. Return statistics

    Args:
        crawl4ai_url: Base URL of the Crawl4AI service
        url: Starting URL for the crawl
        retention_policy: 'permanent' or 'session_only'
        tags: Comma-separated tags for categorization
        max_depth: Maximum depth to crawl (0 = starting page only, max 5)
        max_pages: Maximum number of English pages to store (max 250)
        include_external: Whether to follow external links
        score_threshold: (unused in client-side implementation)
        timeout: (unused in client-side implementation)

    Returns:
        Dict with:
            - success: bool
            - starting_url: str
            - pages_crawled: int (total pages crawled)
            - pages_stored: int (English pages stored)
            - pages_skipped_language: int (non-English pages)
            - pages_failed: int (error pages)
            - stored_pages: list
            - skipped_pages: list
            - failed_pages: list
            - retention_policy: str
            - language_filter: str
            - message: str
    """
    try:
        from api.toolactions.utilities.blockeddomains import is_domain_blocked

        # DEFENSE LAYER 0: Domain blocking (earliest check)
        block_check = is_domain_blocked(url)
        if block_check["blocked"]:
            return {
                "success": False,
                "error": f"Starting URL domain blocked: {block_check['reason']}",
                "blocked": True,
                "category": block_check["category"],
                "url": url,
                "pages_crawled": 0,
                "pages_stored": 0,
                "pages_skipped_language": 0,
                "pages_failed": 0,
                "stored_pages": [],
                "skipped_pages": [],
                "failed_pages": []
            }

        print(f"Starting deep crawl: {url} (depth={max_depth}, max_pages={max_pages}, English only)",
              file=sys.stderr, flush=True)

        max_depth, max_pages = validate_deep_crawl_params(max_depth, max_pages)

        visited = set()
        queue = [(url, 0)]
        stored_pages = []
        skipped_non_english = []
        failed_pages = []
        crawled_pages = 0  # Track total pages actually crawled
        base_domain = urlparse(url).netloc

        while queue and len(stored_pages) < max_pages:
            current_url, depth = queue.pop(0)
            if current_url in visited or depth > max_depth:
                continue

            visited.add(current_url)
            crawled_pages += 1
            print(f"📄 Crawling (depth {depth}): {current_url}", file=sys.stderr, flush=True)

            try:
                response = requests.post(
                    f"{crawl4ai_url}/crawl",
                    json={
                        "urls": [current_url],
                        "word_count_threshold": 10,
                        "excluded_tags": ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
                        "remove_forms": True,
                        "only_text": True
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()

                if not result.get("success") or not result.get("results"):
                    failed_pages.append(current_url)
                    continue

                crawl_result = result["results"][0]
                content = crawl_result.get("cleaned_html", "")
                # Prefer fit_markdown (cleaned) over raw_markdown
                markdown = crawl_result.get("markdown", {}).get("fit_markdown", "") or \
                          crawl_result.get("markdown", {}).get("raw_markdown", "")
                title = crawl_result.get("metadata", {}).get("title", "")
                links = crawl_result.get("links", {})
                status_code = crawl_result.get("metadata", {}).get("status_code", 0)

                if status_code >= 400:
                    print(f"⊘ Skipping error page (HTTP {status_code}): {current_url}",
                          file=sys.stderr, flush=True)
                    failed_pages.append(current_url)
                    continue

                if not content:
                    failed_pages.append(current_url)
                    continue

                # Check if page is an error/rate-limited page
                from api.toolactions.data.content_cleaner import ContentCleaner
                error_check = ContentCleaner.is_error_page(markdown or content, title, status_code)
                if error_check["is_error"]:
                    print(f"⊘ Skipping error page ({error_check['reason']}): {current_url}",
                          file=sys.stderr, flush=True)
                    failed_pages.append(current_url)
                    continue

                if not is_english(content, current_url):
                    skipped_non_english.append(current_url)
                    # Only add links if we haven't crawled too many pages yet
                    if depth < max_depth and crawled_pages < max_pages * 1.1:
                        add_links_to_queue(links, visited, queue, depth,
                                          base_domain, include_external)
                    continue

                # Send to robaigraphrag for ingestion
                try:
                    graphrag_url = os.getenv("ROBAIGRAPHRAG_URL", "http://localhost:8089")
                    api_key = os.getenv("OPENAI_API_KEY", "")

                    if api_key:
                        content_id = generate_content_id(current_url)
                        payload = {
                            "content_id": content_id,
                            "url": current_url,
                            "title": title,
                            "markdown": markdown,
                            "metadata": {
                                "retention_policy": retention_policy or "permanent",
                                "tags": tags,
                                "source": "deep_crawl",
                                "depth": depth,
                                "starting_url": url,
                                "language": "en",
                                "user": "Robert P Smith"
                            }
                        }

                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        }

                        response = requests.post(
                            f"{graphrag_url}/api/v1/ingest",
                            json=payload,
                            headers=headers,
                            timeout=30
                        )

                        if response.status_code == 200:
                            stored_pages.append(current_url)
                            print(f"✓ Ingested English page (depth {depth}): {title}", file=sys.stderr, flush=True)
                        else:
                            print(f"⚠️ GraphRAG ingestion failed (status {response.status_code}): {current_url}",
                                  file=sys.stderr, flush=True)
                            failed_pages.append(current_url)
                    else:
                        print(f"⚠️ No API key configured, skipping storage: {current_url}", file=sys.stderr, flush=True)
                        failed_pages.append(current_url)

                except Exception as storage_err:
                    print(f"⚠️ GraphRAG ingestion error for {current_url}: {storage_err}",
                          file=sys.stderr, flush=True)
                    failed_pages.append(current_url)

                # Only add links if we haven't crawled too many pages yet
                if depth < max_depth and crawled_pages < max_pages * 1.1:
                    add_links_to_queue(links, visited, queue, depth,
                                      base_domain, include_external)

            except Exception as e:
                print(f"Error crawling {current_url}: {str(e)}", file=sys.stderr, flush=True)
                failed_pages.append(current_url)

            # Rate limiting: wait 0.5 seconds between crawl requests
            time.sleep(0.5)

        print(f"Deep crawl completed: {crawled_pages} pages crawled, {len(stored_pages)} stored (English), "
              f"{len(skipped_non_english)} skipped (non-English), {len(failed_pages)} failed",
              file=sys.stderr, flush=True)

        return {
            "success": True,
            "starting_url": url,
            "pages_crawled": crawled_pages,
            "pages_stored": len(stored_pages),
            "pages_skipped_language": len(skipped_non_english),
            "pages_failed": len(failed_pages),
            "stored_pages": stored_pages,
            "skipped_pages": skipped_non_english,
            "failed_pages": failed_pages,
            "retention_policy": retention_policy,
            "language_filter": "en",
            "message": f"Deep crawl completed: {len(stored_pages)} English pages stored, {len(skipped_non_english)} non-English skipped"
        }

    except Exception as e:
        print(f"Deep crawl failed: {str(e)}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "starting_url": url,
            "pages_crawled": 0,
            "pages_stored": 0,
            "pages_skipped_language": 0,
            "pages_failed": 0,
            "stored_pages": [],
            "skipped_pages": [],
            "failed_pages": []
        }
