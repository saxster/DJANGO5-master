"""
URL Optimization Utilities

Enhanced URL handling for better UX, SEO, and analytics.
"""

import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


class UrlOptimizer:
    """
    Utility class for URL optimization and enhancement
    """

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
        """Generate semantic breadcrumbs from URL path"""
        path = request.path.strip('/')
        segments = [segment for segment in path.split('/') if segment]

        breadcrumbs = [
            {'title': 'Home', 'url': '/', 'icon': 'home'}
        ]

        current_path = ''
        for i, segment in enumerate(segments):
            current_path += f'/{segment}'

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
        """Get information about a URL segment"""
        segment = segments[index]

        if index == 0 and segment in cls.DOMAIN_MAPPING:
            domain_info = cls.DOMAIN_MAPPING[segment]
            return {
                'title': domain_info['title'],
                'icon': domain_info['icon'],
                'description': domain_info['description']
            }

        if index == 1 and len(segments) > 1:
            parent_domain = segments[0]
            if parent_domain in cls.DOMAIN_MAPPING:
                children = cls.DOMAIN_MAPPING[parent_domain].get('children', {})
                if segment in children:
                    return children[segment]

        return {
            'title': cls.prettify_segment(segment),
            'icon': cls.get_segment_icon(segment)
        }

    @staticmethod
    def prettify_segment(segment: str) -> str:
        """Convert URL segment to human-readable title"""
        import re

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

        words = re.split(r'[-_]', segment)

        prettified_words = []
        for word in words:
            if word.lower() in replacements:
                prettified_words.append(replacements[word.lower()])
            elif word.isdigit():
                prettified_words.append(f"#{word}")
            else:
                prettified_words.append(word.capitalize())

        return ' '.join(prettified_words)

    @staticmethod
    def get_segment_icon(segment: str) -> str:
        """Get appropriate icon for URL segment"""
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
        """Generate canonical URL for SEO"""
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        path = request.path

        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        canonical = f"{scheme}://{host}{path}"

        return canonical

    @classmethod
    def generate_page_metadata(cls, request: HttpRequest, title: str = None, description: str = None) -> Dict[str, str]:
        """Generate page metadata for SEO and social sharing"""
        path = request.path.strip('/')
        segments = [segment for segment in path.split('/') if segment]

        domain_info = None
        if segments and segments[0] in cls.DOMAIN_MAPPING:
            domain_info = cls.DOMAIN_MAPPING[segments[0]]

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
        """Generate semantic page title from URL segments"""
        if not segments:
            return 'Dashboard'

        title_parts = []

        for i, segment in enumerate(segments):
            segment_info = cls.get_segment_info(segments, i)
            title_parts.append(segment_info['title'])

        return ' | '.join(title_parts)

    @classmethod
    def get_default_image_url(cls, request: HttpRequest) -> str:
        """Get default Open Graph image URL"""
        return request.build_absolute_uri(settings.STATIC_URL + 'assets/media/images/og-default.png')

    @classmethod
    def generate_structured_data(cls, request: HttpRequest, page_type: str = 'WebPage') -> Dict:
        """Generate JSON-LD structured data for SEO"""
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

        if hasattr(settings, 'ORGANIZATION_NAME'):
            structured_data['publisher'] = {
                '@type': 'Organization',
                'name': settings.ORGANIZATION_NAME,
                'url': request.build_absolute_uri('/'),
            }

        return structured_data


__all__ = [
    'UrlOptimizer',
]
