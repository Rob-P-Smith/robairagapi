"""
Domain Blocking Utility

Comprehensive URL blocking system to prevent crawling and storing content from:
- Unsafe top-level domains (TLDs)
- Social media platforms
- Adult content sites
- Malicious domains
- Scam/phishing sites

This provides the first layer of defense before any crawling occurs.
"""

from typing import Dict
from urllib.parse import urlparse


# ============================================================================
# UNSAFE TOP-LEVEL DOMAINS (TLDs)
# ============================================================================
BLOCKED_TLDS = {
    # Russia and former Soviet states
    '.ru', '.su', '.by',

    # China
    '.cn', '.china',

    # High-risk countries
    '.ir',  # Iran
    '.kp',  # North Korea
    '.sy',  # Syria
    '.ye',  # Yemen
    '.af',  # Afghanistan
    '.so',  # Somalia
    '.ly',  # Libya
    '.sd',  # Sudan

    # Other risky TLDs
    '.tk', '.ml', '.ga', '.cf', '.gq',  # Free TLDs often used for spam
    '.to', '.cc',  # Commonly abused
}


# ============================================================================
# SOCIAL MEDIA PLATFORMS
# ============================================================================
BLOCKED_SOCIAL_MEDIA = {
    # Major platforms
    'facebook.com', 'fb.com', 'fb.watch',
    'twitter.com', 'x.com', 't.co',
    'instagram.com', 'instagr.am',
    'linkedin.com', 'lnkd.in',
    'tiktok.com',
    'reddit.com', 'redd.it',
    'youtube.com', 'youtu.be', 'youtube-nocookie.com',
    'snapchat.com',
    'pinterest.com', 'pin.it',
    'tumblr.com',
    'vimeo.com',
    'dailymotion.com',

    # Messaging platforms
    'whatsapp.com', 'wa.me',
    'telegram.org', 'telegram.me', 't.me',
    'discord.com', 'discord.gg', 'discordapp.com',
    'slack.com',
    'signal.org',

    # Streaming/Gaming
    'twitch.tv',
    'kick.com',

    # Publishing/Blogging
    'substack.com',
    'patreon.com',
    'ko-fi.com',
    'buymeacoffee.com',

    # Alternative/Decentralized
    'bluesky.social', 'bsky.app',
    'mastodon.social', 'mastodon.online',
    'minds.com',
    'gab.com', 'gettr.com', 'parler.com', 'truthsocial.com',

    # Forums (generic patterns handled separately)
    'discourse.org',
}


# ============================================================================
# ADULT CONTENT DOMAINS & KEYWORDS
# ============================================================================
BLOCKED_ADULT_KEYWORDS = {
    'porn', 'pron', 'xxx', 'adult', 'sex', 'nude', 'nsfw',
    'hentai', 'erotic', 'escort', 'webcam', 'camgirl',
    'onlyfans', 'fansly', 'manyvids',
}


# ============================================================================
# MALICIOUS/SCAM KEYWORDS
# ============================================================================
BLOCKED_MALICIOUS_KEYWORDS = {
    'donate', 'donation', 'donate-now',
    'spam', 'phishing', 'scam',
    'pills', 'pharmacy', 'viagra', 'cialis',
    'casino', 'poker', 'betting', 'gambling',
    'lottery', 'prize', 'winner',
    'cryptocurrency', 'bitcoin', 'crypto-wallet',
    'download-now', 'free-download', 'crack', 'keygen',
}


# ============================================================================
# URL PATTERNS TO BLOCK
# ============================================================================
BLOCKED_URL_PATTERNS = {
    # Email/Contact links
    'mailto:',

    # Forum/Discussion patterns
    'forum.',
    'forums.',
    'discuss.',
    'community.',

    # Advertising/Tracking
    'ads.',
    'ad.',
    'analytics.',
    'tracker.',
    'pixel.',

    # Common spam patterns
    'free-', 'get-free-', 'download-free',
    'click-here', 'clickhere',
}


def is_domain_blocked(url: str) -> Dict[str, any]:
    """
    Check if a URL should be blocked from crawling/storage

    Checks against:
    - Unsafe TLDs (.ru, .cn, etc.)
    - Social media platforms
    - Adult content sites
    - Malicious/scam domains
    - Blocked URL patterns

    Args:
        url: The URL to check

    Returns:
        Dict with:
            - blocked: bool - True if URL should be blocked
            - reason: str - Human-readable reason for blocking
            - category: str - Category of block (tld, social_media, adult, malicious, pattern)
    """
    if not url:
        return {"blocked": False, "reason": "", "category": ""}

    url_lower = url.lower()

    try:
        parsed = urlparse(url_lower)
        domain = parsed.netloc or parsed.path.split('/')[0]

        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]

    except Exception:
        # If URL parsing fails, allow it (will be caught by other validation)
        return {"blocked": False, "reason": "", "category": ""}

    # ========== CHECK 1: Unsafe TLDs ==========
    for tld in BLOCKED_TLDS:
        if domain.endswith(tld) or url_lower.endswith(tld):
            return {
                "blocked": True,
                "reason": f"Unsafe top-level domain: {tld}",
                "category": "tld"
            }

    # ========== CHECK 2: Social Media Platforms ==========
    for social_domain in BLOCKED_SOCIAL_MEDIA:
        # Use proper domain matching (exact match or subdomain match)
        # This prevents false positives like "t.co" matching "microsoft.com"
        if domain == social_domain or domain.endswith('.' + social_domain):
            return {
                "blocked": True,
                "reason": f"Social media platform: {social_domain}",
                "category": "social_media"
            }

    # ========== CHECK 3: Adult Content ==========
    for adult_keyword in BLOCKED_ADULT_KEYWORDS:
        if adult_keyword in domain or adult_keyword in url_lower:
            return {
                "blocked": True,
                "reason": f"Adult content detected: {adult_keyword}",
                "category": "adult"
            }

    # ========== CHECK 4: Malicious/Scam Keywords ==========
    for malicious_keyword in BLOCKED_MALICIOUS_KEYWORDS:
        if malicious_keyword in url_lower:
            return {
                "blocked": True,
                "reason": f"Malicious/scam keyword: {malicious_keyword}",
                "category": "malicious"
            }

    # ========== CHECK 5: URL Patterns ==========
    for pattern in BLOCKED_URL_PATTERNS:
        if pattern in url_lower:
            return {
                "blocked": True,
                "reason": f"Blocked URL pattern: {pattern}",
                "category": "pattern"
            }

    # URL is not blocked
    return {
        "blocked": False,
        "reason": "",
        "category": ""
    }


def get_block_stats() -> Dict[str, int]:
    """
    Get statistics about blocking rules

    Returns:
        Dict with counts of each blocking category
    """
    return {
        "blocked_tlds": len(BLOCKED_TLDS),
        "blocked_social_media": len(BLOCKED_SOCIAL_MEDIA),
        "blocked_adult_keywords": len(BLOCKED_ADULT_KEYWORDS),
        "blocked_malicious_keywords": len(BLOCKED_MALICIOUS_KEYWORDS),
        "blocked_url_patterns": len(BLOCKED_URL_PATTERNS),
        "total_rules": (
            len(BLOCKED_TLDS) +
            len(BLOCKED_SOCIAL_MEDIA) +
            len(BLOCKED_ADULT_KEYWORDS) +
            len(BLOCKED_MALICIOUS_KEYWORDS) +
            len(BLOCKED_URL_PATTERNS)
        )
    }
