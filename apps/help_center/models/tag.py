"""
Help Center Tag Model

Simple tagging for help articles.

Created: 2025-11-04 (Split from god file)
"""

from django.db import models
from apps.tenants.models import TenantAwareModel


class HelpTag(TenantAwareModel):
    """Simple tagging for help articles."""

    name = models.CharField(max_length=50, db_index=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        db_table = 'help_center_tag'
        ordering = ['name']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.name
