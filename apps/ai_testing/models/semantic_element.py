"""
ML-Enhanced Baselines - Semantic Element Model.

Individual semantic elements identified in UI baselines.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .baseline_config import MLBaseline
from .ml_baseline_enums import ELEMENT_TYPES, INTERACTION_TYPES


class SemanticElement(models.Model):
    """
    Individual semantic elements identified in UI baselines.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        MLBaseline,
        on_delete=models.CASCADE,
        related_name='elements'
    )

    # Element identification
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES)
    element_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="UI element ID if available"
    )
    element_text = models.TextField(
        blank=True,
        help_text="Visible text content"
    )
    element_description = models.TextField(
        blank=True,
        help_text="AI-generated description"
    )

    # Position and layout
    bounding_box = models.JSONField(
        help_text="Element bounding box: {x, y, width, height}"
    )
    z_index = models.IntegerField(
        default=0,
        help_text="Layer/depth information"
    )

    # Interaction properties
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES,
        default='display_only'
    )
    is_critical = models.BooleanField(
        default=False,
        help_text="Whether this element is critical for user flow"
    )

    # Visual properties
    visual_properties = models.JSONField(
        default=dict,
        help_text="Visual properties: colors, fonts, styles, etc."
    )

    # ML confidence
    detection_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML confidence in element detection and classification"
    )

    class Meta:
        ordering = ['baseline', 'element_type', 'z_index']
        indexes = [
            models.Index(fields=['baseline', 'element_type']),
            models.Index(fields=['interaction_type', 'is_critical']),
            models.Index(fields=['detection_confidence']),
        ]

    def __str__(self):
        return f"{self.element_type}: {self.element_text[:50] or self.element_description[:50]}"

    @property
    def element_center(self):
        """Calculate center point of element."""
        bbox = self.bounding_box
        return {
            'x': bbox['x'] + bbox['width'] / 2,
            'y': bbox['y'] + bbox['height'] / 2
        }

    @property
    def element_area(self):
        """Calculate element area in pixels."""
        bbox = self.bounding_box
        return bbox['width'] * bbox['height']

    def overlaps_with(self, other_element):
        """Check if this element overlaps with another."""
        bbox1 = self.bounding_box
        bbox2 = other_element.bounding_box

        return not (
            bbox1['x'] + bbox1['width'] < bbox2['x'] or
            bbox2['x'] + bbox2['width'] < bbox1['x'] or
            bbox1['y'] + bbox1['height'] < bbox2['y'] or
            bbox2['y'] + bbox2['height'] < bbox1['y']
        )

    def distance_to(self, other_element):
        """Calculate distance to another element's center."""
        center1 = self.element_center
        center2 = other_element.element_center

        dx = center1['x'] - center2['x']
        dy = center1['y'] - center2['y']

        return (dx**2 + dy**2)**0.5


__all__ = ['SemanticElement']
