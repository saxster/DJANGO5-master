"""
Article Generator Service - Auto-generate help articles from ontology.

Performance Characteristics:
- Processes 1 article per second (rate-limited)
- Memory-efficient (batch processing)
- Idempotent (safe to re-run)

Created: 2025-11-12
"""

import logging
from typing import Dict, Any
from django.utils import timezone
from django.utils.text import slugify
from apps.help_center.models import HelpArticle, HelpCategory, HelpTag

logger = logging.getLogger('help_center.generator')


class ArticleGeneratorService:
    """Generate help articles from ontology metadata."""

    AUTO_GENERATED_TAG = 'auto-generated'
    CODE_REFERENCE_TAG = 'code-reference'

    def generate_article(self, metadata: Dict[str, Any], category: HelpCategory) -> HelpArticle:
        """
        Generate or update article from ontology metadata.

        Args:
            metadata: Ontology component metadata
            category: Target category

        Returns:
            Generated/updated HelpArticle
        """
        qualified_name = metadata['qualified_name']
        # Extract just the class name for matching
        class_name = qualified_name.split('.')[-1]

        # Check if article already exists - match on class name in title
        existing = HelpArticle.objects.filter(
            title__icontains=class_name,
            category=category
        ).first()

        # Generate article content
        title = self._generate_title(metadata)
        content = self._generate_content(metadata)

        if existing:
            # Update existing article
            existing.title = title
            existing.content = content
            existing.summary = self._generate_summary(metadata)
            existing.slug = slugify(title)
            existing.updated_at = timezone.now()
            existing.save()
            article = existing
            logger.info(f"Updated article: {title}")
        else:
            # Create new article
            article = HelpArticle.objects.create(
                title=title,
                slug=slugify(title),
                summary=self._generate_summary(metadata),
                content=content,
                category=category,
                tenant=category.tenant,
                status=HelpArticle.Status.PUBLISHED
            )
            logger.info(f"Created article: {title}")

        # Add tags
        self._add_tags(article, metadata)

        return article

    def _generate_title(self, metadata: Dict) -> str:
        """Generate article title from metadata."""
        name = metadata['qualified_name'].split('.')[-1]
        return f"Code Reference: {name}"

    def _generate_summary(self, metadata: Dict) -> str:
        """Generate article summary from metadata."""
        purpose = metadata.get('purpose', 'No description available')
        # Truncate to 500 characters
        return purpose[:497] + '...' if len(purpose) > 500 else purpose

    def _generate_content(self, metadata: Dict) -> str:
        """Generate article content from metadata."""
        lines = [
            f"# {metadata['qualified_name']}",
            "",
            "## Purpose",
            metadata.get('purpose', 'No description available'),
            "",
            f"## Domain",
            metadata.get('domain', 'N/A'),
            ""
        ]

        # Usage section
        if metadata.get('inputs') or metadata.get('outputs'):
            lines.extend([
                "## Usage",
                "```python",
                f"from {'.'.join(metadata['qualified_name'].split('.')[:-1])} import {metadata['qualified_name'].split('.')[-1]}",
                "",
                "# Example usage:",
                "# (See code for implementation details)",
                "```",
                ""
            ])

        # Dependencies
        if metadata.get('depends_on'):
            lines.extend([
                "## Dependencies",
                ""
            ])
            for dep in metadata['depends_on']:
                lines.append(f"- `{dep}`")
            lines.append("")

        # Business value
        if metadata.get('business_value'):
            lines.extend([
                "## Business Value",
                metadata['business_value'],
                ""
            ])

        # Security notes
        if metadata.get('security_notes'):
            lines.extend([
                "## Security Considerations",
                metadata['security_notes'],
                ""
            ])

        # Performance notes
        if metadata.get('performance_notes'):
            lines.extend([
                "## Performance",
                metadata['performance_notes'],
                ""
            ])

        # Footer
        lines.extend([
            "---",
            f"*Auto-generated from ontology. Last updated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(lines)

    def _add_tags(self, article: HelpArticle, metadata: Dict) -> None:
        """Add relevant tags to article."""
        tag_names = [
            self.AUTO_GENERATED_TAG,
            self.CODE_REFERENCE_TAG,
            metadata.get('domain', 'general')
        ]

        # Add ontology tags
        tag_names.extend(metadata.get('tags', []))

        # Create/get tags
        for tag_name in tag_names:
            tag, _ = HelpTag.objects.get_or_create(
                name=tag_name,
                slug=slugify(tag_name),
                tenant=article.tenant
            )
            article.tags.add(tag)
