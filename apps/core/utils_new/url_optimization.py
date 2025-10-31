"""
URL Optimization Utilities
Enhanced URL handling for better UX, SEO, and analytics
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from django.http import HttpRequest


class UrlOptimizer:
    """
    Utility class for URL optimization and enhancement
    """

    # Domain mapping for semantic URLs
    DOMAIN_MAPPING = {
        'operations': {
            'title': 'Operations',
            'description': 'Task management, scheduling, work orders, and preventive maintenance',
            'icon': 'build',
            'color': '#377dff',
            'children': {
                'tasks': {'title': 'Tasks', 'icon': 'task'},
                'tours': {'title': 'Site Tours', 'icon': 'route'},
                'work-orders': {'title': 'Work Orders', 'icon': 'build'},
                'ppm': {'title': 'Preventive Maintenance', 'icon': 'schedule'},
            }
        },
        'assets': {
            'title': 'Assets',
            'description': 'Inventory, maintenance tracking, and location management',
            'icon': 'inventory',
            'color': '#00c9a7',
            'children': {
                'inventory': {'title': 'Inventory', 'icon': 'inventory'},
                'maintenance': {'title': 'Maintenance', 'icon': 'settings'},
                'locations': {'title': 'Locations', 'icon': 'location_on'},
                'monitoring': {'title': 'Monitoring', 'icon': 'monitor'},
            }
        },
        'people': {
            'title': 'People',
            'description': 'User management, attendance, and directory services',
            'icon': 'people',
            'color': '#ffc107',
            'children': {
                'directory': {'title': 'Directory', 'icon': 'people'},
                'attendance': {'title': 'Attendance', 'icon': 'access_time'},
                'groups': {'title': 'Groups', 'icon': 'groups'},
                'expenses': {'title': 'Expenses', 'icon': 'receipt'},
            }
        },
        'help-desk': {
            'title': 'Help Desk',
            'description': 'Support tickets, escalations, and service requests',
            'icon': 'support',
            'color': '#de4437',
            'children': {
                'tickets': {'title': 'Tickets', 'icon': 'support'},
                'escalations': {'title': 'Escalations', 'icon': 'priority_high'},
                'requests': {'title': 'Service Requests', 'icon': 'request_quote'},
            }
        },
        'reports': {
            'title': 'Reports',
            'description': 'Analytics, insights, and data exports',
            'icon': 'assessment',
            'color': '#00d4ff',
            'children': {
                'dashboard': {'title': 'Dashboard', 'icon': 'dashboard'},
                'analytics': {'title': 'Analytics', 'icon': 'insights'},
                'exports': {'title': 'Exports', 'icon': 'file_download'},
            }
        }
    }

    @classmethod
    def generate_breadcrumbs(cls, request: HttpRequest) -> List[Dict[str, str]]:
        """
        Generate semantic breadcrumbs from URL path
        """
        path = request.path.strip('/')
        segments = [segment for segment in path.split('/') if segment]

        breadcrumbs = [
            {'title': 'Home', 'url': '/', 'icon': 'home'}
        ]

        current_path = ''
        for i, segment in enumerate(segments):
            current_path += f'/{segment}'

            # Get segment info from domain mapping
            segment_info = cls.get_segment_info(segments, i)

            breadcrumb = {
                'title': segment_info['title'],
                'url': current_path + '/',
                'icon': segment_info.get('icon', 'folder'),
                'is_active': i == len(segments) - 1,
            }

            breadcrumbs.append(breadcrumb)

        return breadcrumbs

    @classmethod
    def get_segment_info(cls, segments: List[str], index: int) -> Dict[str, str]:
        """
        Get information about a URL segment
        """
        segment = segments[index]

        # Check domain mapping
        if index == 0 and segment in cls.DOMAIN_MAPPING:
            domain_info = cls.DOMAIN_MAPPING[segment]
            return {
                'title': domain_info['title'],
                'icon': domain_info['icon'],
                'description': domain_info['description']
            }

        # Check subdomain mapping
        if index == 1 and len(segments) > 1:
            parent_domain = segments[0]
            if parent_domain in cls.DOMAIN_MAPPING:
                children = cls.DOMAIN_MAPPING[parent_domain].get('children', {})
                if segment in children:
                    return children[segment]

        # Fallback to prettified segment name
        return {
            'title': cls.prettify_segment(segment),
            'icon': cls.get_segment_icon(segment)
        }

    @classmethod
    def prettify_segment(cls, segment: str) -> str:
        """
        Convert URL segment to human-readable title
        """
        # Handle common patterns
        replacements = {
            'id': 'ID',
            'uuid': 'ID',
            'api': 'API',
            'ui': 'UI',
            'seo': 'SEO',
            'url': 'URL',
            'csv': 'CSV',
            'pdf': 'PDF',
            'xml': 'XML',
            'json': 'JSON',
        }

        # Split by hyphens and underscores
        words = re.split(r'[-_]', segment)

        # Capitalize and apply replacements
        prettified_words = []
        for word in words:
            if word.lower() in replacements:
                prettified_words.append(replacements[word.lower()])
            elif word.isdigit():
                prettified_words.append(f"#{word}")
            else:
                prettified_words.append(word.capitalize())

        return ' '.join(prettified_words)

    @classmethod
    def get_segment_icon(cls, segment: str) -> str:
        """
        Get appropriate icon for URL segment
        """
        icon_mapping = {
            'add': 'add',
            'create': 'add',
            'new': 'add',
            'edit': 'edit',
            'update': 'edit',
            'delete': 'delete',
            'remove': 'delete',
            'list': 'list',
            'view': 'visibility',
            'detail': 'visibility',
            'settings': 'settings',
            'config': 'settings',
            'profile': 'person',
            'user': 'person',
            'admin': 'admin_panel_settings',
            'api': 'api',
            'export': 'file_download',
            'import': 'file_upload',
            'search': 'search',
            'filter': 'filter_alt',
            'sort': 'sort',
        }

        for key, icon in icon_mapping.items():
            if key in segment.lower():
                return icon

        return 'folder'

    @classmethod
    def generate_canonical_url(cls, request: HttpRequest) -> str:
        """
        Generate canonical URL for SEO
        """
        # Build canonical URL
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        path = request.path

        # Remove trailing slash for consistency (except root)
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Remove query parameters for canonical URL
        canonical = f"{scheme}://{host}{path}"

        return canonical

    @classmethod
    def generate_page_metadata(cls, request: HttpRequest, title: str = None, description: str = None) -> Dict[str, str]:
        """
        Generate page metadata for SEO and social sharing
        """
        path = request.path.strip('/')
        segments = [segment for segment in path.split('/') if segment]

        # Get domain information
        domain_info = None
        if segments and segments[0] in cls.DOMAIN_MAPPING:
            domain_info = cls.DOMAIN_MAPPING[segments[0]]

        # Generate metadata
        site_name = getattr(settings, 'SITE_NAME', 'YOUTILITY')
        default_description = 'Enterprise facility management platform for efficient operations, asset management, and team coordination.'

        metadata = {
            'title': title or cls.generate_page_title(segments),
            'description': description or domain_info.get('description', default_description) if domain_info else default_description,
            'canonical_url': cls.generate_canonical_url(request),
            'site_name': site_name,
            'type': 'website',
            'image': cls.get_default_image_url(request),
        }

        # Add domain-specific metadata
        if domain_info:
            metadata.update({
                'domain': segments[0],
                'domain_title': domain_info['title'],
                'domain_color': domain_info['color'],
                'domain_icon': domain_info['icon'],
            })

        return metadata

    @classmethod
    def generate_page_title(cls, segments: List[str]) -> str:
        """
        Generate semantic page title from URL segments
        """
        if not segments:
            return 'Dashboard'

        title_parts = []

        for i, segment in enumerate(segments):
            segment_info = cls.get_segment_info(segments, i)
            title_parts.append(segment_info['title'])

        return ' | '.join(title_parts)

    @classmethod
    def get_default_image_url(cls, request: HttpRequest) -> str:
        """
        Get default Open Graph image URL
        """
        return request.build_absolute_uri(settings.STATIC_URL + 'assets/media/images/og-default.png')

    @classmethod
    def generate_structured_data(cls, request: HttpRequest, page_type: str = 'WebPage') -> Dict:
        """
        Generate JSON-LD structured data for SEO
        """
        canonical_url = cls.generate_canonical_url(request)
        metadata = cls.generate_page_metadata(request)

        structured_data = {
            '@context': 'https://schema.org',
            '@type': page_type,
            'name': metadata['title'],
            'description': metadata['description'],
            'url': canonical_url,
            'isPartOf': {
                '@type': 'WebSite',
                'name': metadata['site_name'],
                'url': request.build_absolute_uri('/'),
            }
        }

        # Add organization data
        if hasattr(settings, 'ORGANIZATION_NAME'):
            structured_data['publisher'] = {
                '@type': 'Organization',
                'name': settings.ORGANIZATION_NAME,
                'url': request.build_absolute_uri('/'),
            }

        return structured_data


class URLAnalytics:
    """
    URL analytics and tracking utilities
    """

    @staticmethod
    def track_page_view(request: HttpRequest, additional_data: Dict = None):
        """
        Track page view for analytics
        """
        # This would integrate with your analytics system
        analytics_data = {
            'url': request.path,
            'canonical_url': UrlOptimizer.generate_canonical_url(request),
            'referrer': request.META.get('HTTP_REFERER'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'timestamp': timezone.now().isoformat(),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'session_key': request.session.session_key if hasattr(request, 'session') else None,
        }

        if additional_data:
            analytics_data.update(additional_data)

        # Send to analytics service (Google Analytics, etc.)
        # This would be implemented based on your analytics provider

        return analytics_data

    @staticmethod
    def track_url_error(request: HttpRequest, error_code: int, error_type: str = None):
        """
        Track URL errors for 404 analysis and dead link detection
        """
        error_data = {
            'url': request.path,
            'error_code': error_code,
            'error_type': error_type,
            'referrer': request.META.get('HTTP_REFERER'),
            'timestamp': timezone.now().isoformat(),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
        }

        # Log for analysis
        import logging
        logger = logging.getLogger('url_analytics')
        logger.warning(f"URL Error {error_code}: {request.path}", extra=error_data)

        return error_data


class LegacyURLRedirector:
    """
    Smart redirects for legacy URLs to maintain SEO and user bookmarks
    """

    # Legacy URL mappings
    LEGACY_REDIRECTS = {
        # Old admin URLs
        r'^admin/peoples/people/$': '/people/directory/',
        r'^admin/activity/task/$': '/operations/tasks/',
        r'^admin/y_helpdesk/ticket/$': '/help-desk/tickets/',

        # Old app URLs
        r'^peoples/$': '/people/directory/',
        r'^peoples/people/$': '/people/directory/',
        r'^activity/$': '/operations/tasks/',
        r'^activity/task/$': '/operations/tasks/',
        r'^scheduler/$': '/operations/tasks/',
        r'^y_helpdesk/$': '/help-desk/tickets/',
        r'^work_order_management/$': '/operations/work-orders/',

        # Common typos
        r'^schedhule/': '/operations/tasks/',  # Common typo
        r'^helpdesk/': '/help-desk/',
        r'^workorder/': '/operations/work-orders/',
    }

    @classmethod
    def get_redirect_url(cls, path: str) -> Optional[str]:
        """
        Get redirect URL for legacy path
        """
        for pattern, redirect_url in cls.LEGACY_REDIRECTS.items():
            if re.match(pattern, path):
                return redirect_url

        return None

    @classmethod
    def track_legacy_usage(cls, old_url: str, new_url: str, request: HttpRequest):
        """
        Track legacy URL usage for migration analysis
        """
        import logging
        logger = logging.getLogger('legacy_urls')

        logger.info(f"Legacy URL redirect: {old_url} -> {new_url}", extra={
            'old_url': old_url,
            'new_url': new_url,
            'referrer': request.META.get('HTTP_REFERER'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'user_id': request.user.id if request.user.is_authenticated else None,
        })


class BreadcrumbGenerator:
    """
    Generate accessible breadcrumbs from URL structure
    """

    @staticmethod
    def generate_breadcrumb_html(breadcrumbs: List[Dict[str, str]]) -> str:
        """
        Generate HTML for breadcrumbs with accessibility features
        """
        if not breadcrumbs:
            return ''

        breadcrumb_items = []

        for i, crumb in enumerate(breadcrumbs):
            is_active = crumb.get('is_active', False)

            if is_active:
                # Active breadcrumb (current page)
                item_html = f'''
                <li class="breadcrumb-item active" aria-current="page">
                    <i class="material-icons breadcrumb-icon" aria-hidden="true">{crumb.get('icon', 'folder')}</i>
                    <span class="breadcrumb-text">{crumb['title']}</span>
                </li>
                '''
            else:
                # Clickable breadcrumb
                item_html = f'''
                <li class="breadcrumb-item">
                    <a href="{crumb['url']}"
                       class="breadcrumb-link"
                       aria-label="Navigate to {crumb['title']}">
                        <i class="material-icons breadcrumb-icon" aria-hidden="true">{crumb.get('icon', 'folder')}</i>
                        <span class="breadcrumb-text">{crumb['title']}</span>
                    </a>
                </li>
                '''

            breadcrumb_items.append(item_html)

        breadcrumb_nav = f'''
        <nav aria-label="Breadcrumb navigation" class="breadcrumb-nav">
            <ol class="breadcrumb" role="list">
                {''.join(breadcrumb_items)}
            </ol>
        </nav>
        '''

        return mark_safe(breadcrumb_nav)

    @staticmethod
    def generate_breadcrumb_json_ld(breadcrumbs: List[Dict[str, str]], request: HttpRequest) -> Dict:
        """
        Generate JSON-LD structured data for breadcrumbs
        """
        if not breadcrumbs:
            return {}

        items = []
        for i, crumb in enumerate(breadcrumbs, 1):
            items.append({
                '@type': 'ListItem',
                'position': i,
                'name': crumb['title'],
                'item': request.build_absolute_uri(crumb['url'])
            })

        return {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            'itemListElement': items
        }


class SEOOptimizer:
    """
    SEO optimization utilities for URLs and metadata
    """

    @staticmethod
    def generate_meta_tags(metadata: Dict[str, str]) -> str:
        """
        Generate HTML meta tags for SEO and social sharing
        """
        tags = []

        # Basic meta tags
        if metadata.get('description'):
            tags.append(f'<meta name="description" content="{metadata["description"]}">')

        if metadata.get('canonical_url'):
            tags.append(f'<link rel="canonical" href="{metadata["canonical_url"]}">')

        # Open Graph tags
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

        # Twitter Card tags
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
        """
        Generate sitemap entry for URL
        """
        entry = {
            'loc': url,
            'priority': priority,
            'changefreq': changefreq,
        }

        if last_modified:
            entry['lastmod'] = last_modified

        return entry


class URLValidator:
    """
    URL validation and optimization utilities
    """

    @staticmethod
    def validate_url_structure(url: str) -> Dict[str, Any]:
        """
        Validate URL structure against best practices
        """
        parsed = urlparse(url)
        path = parsed.path

        issues = []
        score = 100

        # Check length (should be under 255 characters)
        if len(url) > 255:
            issues.append('URL too long (over 255 characters)')
            score -= 10

        # Check for multiple consecutive slashes
        if '//' in path:
            issues.append('Multiple consecutive slashes found')
            score -= 5

        # Check for trailing slash consistency
        if path != '/' and path.endswith('/'):
            issues.append('Unnecessary trailing slash')
            score -= 2

        # Check for special characters
        if re.search(r'[^a-zA-Z0-9\-_/.]', path):
            issues.append('Special characters in URL (should use hyphens)')
            score -= 5

        # Check for underscores (hyphens preferred)
        if '_' in path:
            issues.append('Underscores found (hyphens preferred for SEO)')
            score -= 3

        # Check depth (should be reasonable)
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
        """
        Suggest improvements for URL structure
        """
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


# Template tags for easy use in templates
from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def url_breadcrumbs(context):
    """
    Template tag to generate breadcrumbs
    """
    request = context.get('request')
    if not request:
        return ''

    breadcrumbs = UrlOptimizer.generate_breadcrumbs(request)
    return BreadcrumbGenerator.generate_breadcrumb_html(breadcrumbs)

@register.simple_tag(takes_context=True)
def page_metadata(context, title=None, description=None):
    """
    Template tag to generate page metadata
    """
    request = context.get('request')
    if not request:
        return {}

    return UrlOptimizer.generate_page_metadata(request, title, description)

@register.simple_tag(takes_context=True)
def seo_meta_tags(context, title=None, description=None):
    """
    Template tag to generate SEO meta tags
    """
    request = context.get('request')
    if not request:
        return ''

    metadata = UrlOptimizer.generate_page_metadata(request, title, description)
    return SEOOptimizer.generate_meta_tags(metadata)

@register.simple_tag(takes_context=True)
def structured_data(context, page_type='WebPage'):
    """
    Template tag to generate structured data
    """
    request = context.get('request')
    if not request:
        return ''

    data = UrlOptimizer.generate_structured_data(request, page_type)
    return mark_safe(f'<script type="application/ld+json">{json.dumps(data, indent=2)}</script>')

@register.simple_tag(takes_context=True)
def canonical_url(context):
    """
    Template tag to get canonical URL
    """
    request = context.get('request')
    if not request:
        return ''

    return UrlOptimizer.generate_canonical_url(request)