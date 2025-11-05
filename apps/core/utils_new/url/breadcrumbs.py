"""
Breadcrumb and Navigation Utilities

Breadcrumb generation with accessibility features and JSON-LD support.
"""

from typing import Dict, List

from django.http import HttpRequest
from django.utils.safestring import mark_safe


class BreadcrumbGenerator:
    """Generate accessible breadcrumbs from URL structure"""

    @staticmethod
    def generate_breadcrumb_html(breadcrumbs: List[Dict[str, str]]) -> str:
        """Generate HTML for breadcrumbs with accessibility features"""
        if not breadcrumbs:
            return ''

        breadcrumb_items = []

        for i, crumb in enumerate(breadcrumbs):
            is_active = crumb.get('is_active', False)

            if is_active:
                item_html = f'''
                <li class="breadcrumb-item active" aria-current="page">
                    <i class="material-icons breadcrumb-icon" aria-hidden="true">{crumb.get('icon', 'folder')}</i>
                    <span class="breadcrumb-text">{crumb['title']}</span>
                </li>
                '''
            else:
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
        """Generate JSON-LD structured data for breadcrumbs"""
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


__all__ = [
    'BreadcrumbGenerator',
]
