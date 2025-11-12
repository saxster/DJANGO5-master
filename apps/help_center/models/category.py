"""
Help Center Category Model

Hierarchical category tree for organizing help articles.

Example tree:
- Operations
  - Work Orders
    - Approval Workflows
    - Vendor Management
  - PPM Scheduling
- Assets
  - Inventory Management
  - QR Code Scanning

Created: 2025-11-04 (Split from god file)
"""

from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager


class HelpCategory(TenantAwareModel):
    """
    Hierarchical category tree for organizing help articles.

    Example tree:
    - Operations
      - Work Orders
        - Approval Workflows
        - Vendor Management
      - PPM Scheduling
    - Assets
      - Inventory Management
      - QR Code Scanning
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )

    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class (e.g., 'fa-wrench', 'material-icons:build')"
    )
    color = models.CharField(
        max_length=7,
        default='#1976d2',
        help_text="Hex color code for category badge"
    )

    display_order = models.IntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    objects = TenantAwareManager()

    class Meta:
        db_table = 'help_center_category'
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Help Categories'
        unique_together = [['tenant', 'slug']]

    def get_ancestors(self):
        """Get all parent categories up to root."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        """Get all child categories recursively."""
        descendants = []
        for child in self.children.filter(is_active=True):
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_breadcrumb(self):
        """Get breadcrumb path: Operations > Work Orders > Approval Workflows"""
        ancestors = self.get_ancestors()
        ancestors.append(self)
        return ' > '.join(cat.name for cat in ancestors)

    def __str__(self):
        return self.get_breadcrumb()
