"""
Template Tags for Help Center.

Provides custom Django template tags for easy widget integration.

Usage:
{% load help_center_tags %}
{% help_center_widget %}
{% help_article_link 123 %}
{% help_search_box %}
"""

from django import template
from django.utils.safestring import mark_safe
from apps.help_center.models import HelpArticle

register = template.Library()


@register.inclusion_tag('help_center/widgets/help_button.html')
def help_center_widget():
    """
    Load help center widget (floating button + chat panel).

    Usage:
    {% load help_center_tags %}
    {% help_center_widget %}
    """
    return {}


@register.simple_tag
def help_article_link(article_id):
    """
    Generate link to help article.

    Usage:
    {% load help_center_tags %}
    <a href="{% help_article_link 123 %}">View Help</a>
    """
    try:
        article = HelpArticle.objects.get(id=article_id)
        return f'/help/articles/{article.slug}/'
    except HelpArticle.DoesNotExist:
        return '#'


@register.inclusion_tag('help_center/widgets/search_box.html')
def help_search_box(placeholder='Search help articles...'):
    """
    Render help search box.

    Usage:
    {% load help_center_tags %}
    {% help_search_box "Find answers..." %}
    """
    return {'placeholder': placeholder}


@register.simple_tag
def help_contextual(page_url):
    """
    Load contextual help for specific page.

    Usage:
    {% load help_center_tags %}
    {% help_contextual request.path %}
    """
    # Returns data attribute for JavaScript to fetch contextual help
    return mark_safe(f'data-help-page="{page_url}"')


@register.filter
def help_difficulty_class(difficulty_level):
    """
    Convert difficulty level to CSS class.

    Usage:
    <span class="badge {% difficulty|help_difficulty_class %}">
    """
    return f"difficulty-{difficulty_level.lower()}"
