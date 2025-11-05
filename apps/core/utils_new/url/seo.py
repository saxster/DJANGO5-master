"""
SEO and Structured Data Utilities

Metadata generation, sitemap entries, and JSON-LD structured data.
"""

import json
import re
from typing import Dict, List, Any
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest
from django.utils.safestring import mark_safe


class SEOOptimizer:
    """SEO optimization utilities for URLs and metadata"""

    @staticmethod
    def generate_meta_tags(metadata: Dict[str, str]) -> str:
        """Generate HTML meta tags for SEO and social sharing"""
        tags = []

        if metadata.get('description'):
            tags.append(f'<meta name="description" content="{metadata["description"]}">')

        if metadata.get('canonical_url'):
            tags.append(f'<link rel="canonical" href="{metadata["canonical_url"]}">')

        if metadata.get('title'):
            tags.append(f'<meta property="og:title" content="{metadata["title"]}">')
            tags.append(f'<meta property="og:site_name" content="{metadata.get("site_name", "YOUTILITY")}">')

        if metadata.get('description'):
            tags.append(f'<meta property="og:description" content="{metadata["description"]}">')

        if metadata.get('canonical_url'):
            tags.append(f'<meta property="og:url" content="{metadata["canonical_url"]}">')

        if metadata.get('image'):
            tags.append(f'<meta property="og:image" content="{metadata["image"]}">')

        tags.append(f'<meta property="og:type" content="{metadata.get("type", "website")}">')

        tags.append('<meta name="twitter:card" content="summary_large_image">')

        if metadata.get('title'):
            tags.append(f'<meta name="twitter:title" content="{metadata["title"]}">')

        if metadata.get('description'):
            tags.append(f'<meta name="twitter:description" content="{metadata["description"]}">')

        if metadata.get('image'):
            tags.append(f'<meta name="twitter:image" content="{metadata["image"]}">')

        return mark_safe('\n'.join(tags))

    @staticmethod
    def generate_sitemap_entry(url: str, last_modified: str = None, priority: float = 0.5, changefreq: str = 'weekly') -> Dict:
        """Generate sitemap entry for URL"""
        entry = {
            'loc': url,
            'priority': priority,
            'changefreq': changefreq,
        }

        if last_modified:
            entry['lastmod'] = last_modified

        return entry


class URLValidator:
    """URL validation and optimization utilities"""

    @staticmethod
    def validate_url_structure(url: str) -> Dict[str, Any]:
        """Validate URL structure against best practices"""
        parsed = urlparse(url)
        path = parsed.path

        issues = []
        score = 100

        if len(url) > 255:
            issues.append('URL too long (over 255 characters)')
            score -= 10

        if '//' in path:
            issues.append('Multiple consecutive slashes found')
            score -= 5

        if path != '/' and path.endswith('/'):
            issues.append('Unnecessary trailing slash')
            score -= 2

        if re.search(r'[^a-zA-Z0-9\-_/.]', path):
            issues.append('Special characters in URL (should use hyphens)')
            score -= 5

        if '_' in path:
            issues.append('Underscores found (hyphens preferred for SEO)')
            score -= 3

        segments = [s for s in path.split('/') if s]
        if len(segments) > 4:
            issues.append('URL depth too deep (over 4 levels)')
            score -= 5

        return {
            'score': max(0, score),
            'issues': issues,
            'is_valid': score >= 80,
            'segments': segments,
            'depth': len(segments)
        }

    @staticmethod
    def suggest_url_improvements(url: str) -> List[str]:
        """Suggest improvements for URL structure"""
        suggestions = []
        validation = URLValidator.validate_url_structure(url)

        if validation['score'] < 80:
            suggestions.append('Consider simplifying the URL structure')

        if any('underscores' in issue for issue in validation['issues']):
            suggestions.append('Replace underscores with hyphens for better SEO')

        if any('trailing slash' in issue for issue in validation['issues']):
            suggestions.append('Remove unnecessary trailing slashes')

        if validation['depth'] > 4:
            suggestions.append('Consider reducing URL depth for better user experience')

        return suggestions


__all__ = [
    'SEOOptimizer',
    'URLValidator',
]
