"""
Content cleaning and post-processing for crawled web pages
Removes navigation, boilerplate, and low-value content before embedding
"""

import re
from typing import List, Dict, Any


class ContentCleaner:
    """Clean and filter web content for better embedding quality"""

    NAVIGATION_PATTERNS = [
        r'\[.*?\]\(.*?\)',
        r'^[\s\*\-]+\[.*?\].*$',
        r'^\s*[\*\-]\s+\[.*?\]\s*\(.*?\)\s*$',
    ]

    NAV_KEYWORDS = [
        'navigation', 'menu', 'sidebar', 'breadcrumb', 'skip to',
        'table of contents', 'on this page', 'quick links',
        'sign in', 'log in', 'subscribe', 'newsletter',
        'follow us', 'social media', 'share on', 'tweet',
        'copyright ©', 'all rights reserved', '© 20',
        'privacy policy', 'terms of service', 'cookie policy',
        'back to top', 'scroll to top', 'go to top'
    ]

    SOCIAL_DOMAINS = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'github.com', 'discord.', 'reddit.com',
        'x.com', 'bsky.app', 'bluesky'
    ]

    IMAGE_PATTERNS = [
        # Inline images with various extensions
        r'!\[.*?\]\(data:image/[^)]+\)',
        r'!\[.*?\]\([^)]*?\.(svg|bmp|jpg|jpeg|png|gif|webp|ico)[^)]*?\)',

        # Base64 encoded data URIs (images and other data)
        r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+',
        r'data:[^;]+;base64,[A-Za-z0-9+/=]{100,}',

        # SVG inline data (can be massive)
        r'<svg[^>]*>.*?</svg>',
        r'data:image/svg\+xml[^)}\s]*',

        # URL-encoded SVG fragments (like %3csvg...%3c/svg%3e or '...'/%3e%3c/svg%3e)
        r'[\'"][^\'\"]*?%3[cC]svg.*?%3[cC]/svg%3[eE][^\'\"]*?[\'"]',
        r'[\'"][^\'\"]*?/%3[eE]%3[cC].*?%3[cC]/svg%3[eE][^\'\"]*?[)\'"]',

        # Standalone image URLs in markdown
        r'https?://[^\s\)]*?\.(svg|bmp|jpg|jpeg|png|gif|webp|ico)(\?[^\s\)]*)?',
    ]

    @staticmethod
    def remove_image_data(content: str) -> str:
        """
        Remove all image data including inline images, SVG, and base64 encoded content

        Args:
            content: Content that may contain image data

        Returns:
            Content with all image data removed
        """
        import sys

        if not content:
            return ""

        original_len = len(content)
        cleaned = content

        # Apply all image removal patterns
        for i, pattern in enumerate(ContentCleaner.IMAGE_PATTERNS):
            before_len = len(cleaned)
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
            after_len = len(cleaned)
            if before_len != after_len:
                print(f"🔧 Pattern {i+1} removed {before_len - after_len} chars", file=sys.stderr, flush=True)

        # Remove empty markdown image references that might remain
        cleaned = re.sub(r'!\[\s*\]\s*\(\s*\)', '', cleaned)

        # Clean up excessive whitespace that might be left behind
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r' {3,}', '  ', cleaned)

        final_len = len(cleaned)
        if original_len != final_len:
            print(f"✂️  Image removal: {original_len} → {final_len} chars (removed {original_len - final_len})", file=sys.stderr, flush=True)

        return cleaned.strip()

    @staticmethod
    def clean_content(markdown: str, url: str = "") -> str:
        """
        Clean markdown content by removing navigation and boilerplate

        Args:
            markdown: Raw markdown content from crawler
            url: URL of the page (for context)

        Returns:
            Cleaned markdown with navigation removed
        """
        if not markdown:
            return ""

        # First remove all image data (SVG, base64, inline images)
        markdown = ContentCleaner.remove_image_data(markdown)

        lines = markdown.split('\n')
        cleaned_lines = []

        # Track consecutive nav headers
        nav_header_keywords = [
            # Product/Service navigation
            'products', 'solutions', 'services', 'platform', 'features', 'models',
            'pricing', 'plans', 'offerings', 'capabilities', 'tools', 'integrations',
            'api', 'apis', 'sdk', 'sdks', 'enterprise', 'business', 'individual',

            # Documentation/Learning
            'documentation', 'docs', 'learn', 'resources', 'tutorials', 'guides',
            'getting started', 'quickstart', 'examples', 'samples', 'reference',
            'changelog', 'release notes', 'what\'s new', 'updates', 'roadmap',

            # Company/Organization
            'company', 'about', 'about us', 'team', 'careers', 'jobs', 'contact',
            'partners', 'partnership', 'news', 'press', 'media', 'events',
            'investors', 'leadership', 'mission', 'vision', 'values',

            # Support/Community
            'support', 'help', 'faq', 'community', 'forum', 'discuss', 'chat',
            'feedback', 'status', 'blog', 'newsletter', 'social', 'follow',

            # Legal/Policies
            'terms', 'policies', 'privacy', 'security', 'legal', 'compliance',
            'cookies', 'gdpr', 'terms of service', 'terms of use', 'license',
            'copyright', 'trademark', 'accessibility', 'trust', 'safety',

            # Navigation UI
            'menu', 'navigation', 'home', 'overview', 'dashboard', 'account',
            'settings', 'profile', 'preferences', 'sign in', 'sign up', 'login',
            'logout', 'register', 'subscribe', 'download', 'search'
        ]
        consecutive_headers = []
        i = 0

        while i < len(lines):
            line = lines[i]
            line_lower = line.lower().strip()

            if not line_lower:
                i += 1
                continue

            # Check if this is a navigation header (###, ##, #)
            if re.match(r'^#{1,6}\s+\w+', line):
                header_text = re.sub(r'^#{1,6}\s+', '', line_lower)
                if any(keyword in header_text for keyword in nav_header_keywords):
                    consecutive_headers.append(i)
                    i += 1
                    continue
                else:
                    # Real content header - flush nav headers if we have 3+
                    if len(consecutive_headers) >= 3:
                        print(f"🧹 Removed {len(consecutive_headers)} consecutive nav headers", file=sys.stderr, flush=True)
                    consecutive_headers = []

            # Regular navigation keyword filtering
            if any(keyword in line_lower for keyword in ContentCleaner.NAV_KEYWORDS):
                i += 1
                continue

            if any(domain in line_lower for domain in ContentCleaner.SOCIAL_DOMAINS):
                i += 1
                continue

            # Remove markdown links [text](url) on their own line
            if re.match(r'^[\s\*\-]+\[.*?\]\s*\(.*?\)\s*$', line):
                i += 1
                continue

            # Remove inline navigation links like [ Install ], [ Learn ], [ API ]
            line = re.sub(r'\[\s+[^\]]+?\s+\]', '', line)

            # Skip line if it became empty after removing nav links
            if not line.strip():
                i += 1
                continue

            if re.match(r'^\s*[\*\-]\s+(Learn|Reference|API|Community|Blog|Docs?)\s*\[', line):
                i += 1
                continue

            # Flush any remaining nav headers if we have 3+
            if len(consecutive_headers) >= 3:
                print(f"🧹 Removed {len(consecutive_headers)} consecutive nav headers", file=sys.stderr, flush=True)
            consecutive_headers = []

            cleaned_lines.append(line)
            i += 1

        cleaned = '\n'.join(cleaned_lines)

        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    @staticmethod
    def filter_chunks(chunks: List[str]) -> List[str]:
        """
        Filter out low-quality chunks before embedding

        Args:
            chunks: List of content chunks

        Returns:
            Filtered list with navigation chunks removed
        """
        filtered = []

        for chunk in chunks:
            chunk_lower = chunk.lower()

            nav_count = sum(1 for keyword in ContentCleaner.NAV_KEYWORDS if keyword in chunk_lower)
            if nav_count >= 3:
                continue

            link_count = chunk.count('[') + chunk.count('](')
            word_count = len(chunk.split())
            if word_count > 0 and link_count / word_count > 0.3:
                continue

            if word_count < 10:
                continue

            if chunk.count('[') > word_count / 3:
                continue

            filtered.append(chunk)

        return filtered

    @staticmethod
    def clean_and_validate(content: str, markdown: str, url: str = "") -> Dict[str, Any]:
        """
        Clean content and validate quality

        Args:
            content: HTML content
            markdown: Markdown content
            url: Page URL

        Returns:
            Dict with cleaned content and quality metrics
        """
        text_to_clean = markdown if markdown else content

        cleaned = ContentCleaner.clean_content(text_to_clean, url)

        original_lines = len(text_to_clean.split('\n'))
        cleaned_lines = len(cleaned.split('\n'))
        reduction_ratio = (original_lines - cleaned_lines) / original_lines if original_lines > 0 else 0

        nav_count = sum(1 for keyword in ContentCleaner.NAV_KEYWORDS
                       if keyword in text_to_clean.lower())

        is_mostly_navigation = reduction_ratio > 0.7 or nav_count > 10

        return {
            "cleaned_content": cleaned,
            "original_lines": original_lines,
            "cleaned_lines": cleaned_lines,
            "reduction_ratio": reduction_ratio,
            "navigation_indicators": nav_count,
            "quality_warning": "Content appears to be mostly navigation/boilerplate" if is_mostly_navigation else None,
            "is_clean": not is_mostly_navigation
        }

    @staticmethod
    def is_error_page(content: str, title: str = "", status_code: int = 200) -> Dict[str, Any]:
        """
        Detect if page is an error/empty/rate-limited page

        Args:
            content: Page content (markdown or HTML)
            title: Page title
            status_code: HTTP status code

        Returns:
            Dict with is_error flag and reason
        """
        if not content or len(content.strip()) < 50:
            return {"is_error": True, "reason": "Empty or too short content"}

        content_lower = content.lower()
        title_lower = title.lower() if title else ""

        # Check HTTP status code
        if status_code >= 400:
            return {"is_error": True, "reason": f"HTTP {status_code} error"}

        # Error indicators in title (strong signal)
        title_error_patterns = [
            '404', 'not found', 'page not found', 'error',
            'access denied', 'forbidden', '403', '401',
            'unauthorized', 'unavailable', 'does not exist'
        ]
        if any(pattern in title_lower for pattern in title_error_patterns):
            return {"is_error": True, "reason": f"Error in title: {title}"}

        # Rate limiting / bot detection patterns
        rate_limit_patterns = [
            'rate limit', 'too many requests', 'please slow down',
            'bot detection', 'captcha', 'human verification',
            'access denied', 'blocked', 'suspicious activity',
            'verify you are human', 'security check'
        ]

        # Check for rate limiting in first 500 chars (usually appears early)
        content_sample = content_lower[:500]
        for pattern in rate_limit_patterns:
            if pattern in content_sample:
                return {"is_error": True, "reason": f"Rate limiting/bot detection: '{pattern}'"}

        # Error page patterns (but be more careful - check context)
        # Only flag if multiple indicators or if content is very short
        word_count = len(content.split())

        if word_count < 100:
            # For very short content, be more aggressive
            short_error_patterns = [
                'page not found', '404', 'not found', 'error occurred',
                'something went wrong', 'page does not exist',
                'reach this site in error', 'reached this page in error'
            ]
            if any(pattern in content_lower for pattern in short_error_patterns):
                return {"is_error": True, "reason": "Error page (short content)"}

        # For longer content, require multiple error indicators
        error_keywords = [
            'page not found', '404 error', 'page does not exist',
            'something went wrong', 'error occurred', 'cannot find',
            'reach this site in error', 'reached this page in error',
            'page you are looking for', 'page has been removed'
        ]

        error_count = sum(1 for keyword in error_keywords if keyword in content_lower)

        if error_count >= 2 and word_count < 300:
            return {"is_error": True, "reason": f"Multiple error indicators ({error_count})"}

        # Check for redirect/moved pages
        redirect_patterns = [
            'permanently moved', 'page has moved', 'redirecting',
            'this page has been moved to'
        ]
        if any(pattern in content_lower for pattern in redirect_patterns) and word_count < 200:
            return {"is_error": True, "reason": "Redirect/moved page"}

        return {"is_error": False, "reason": None}

    @staticmethod
    def extract_main_content(markdown: str) -> str:
        """
        Extract main article content, removing headers/footers

        Args:
            markdown: Full markdown content

        Returns:
            Main content section
        """
        lines = markdown.split('\n')

        start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('#') or len(line.split()) >= 20:
                start_idx = i
                break

        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            line_lower = lines[i].lower()
            if any(pattern in line_lower for pattern in ['copyright', '©', 'all rights reserved', 'privacy policy']):
                end_idx = i
                break

        main_content = '\n'.join(lines[start_idx:end_idx])

        return main_content.strip()
