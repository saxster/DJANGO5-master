"""
Initialize LLM Feature Flags

Creates default feature flags for LLM provider selection.

Following CLAUDE.md patterns

Sprint 7-8 Phase 4: Feature Flag Initialization
"""

from django.core.management.base import BaseCommand
from apps.core.feature_flags.models import FeatureFlag


class Command(BaseCommand):
    help = 'Initialize LLM provider feature flags'

    def handle(self, *args, **options):
        """Create default LLM feature flags."""

        flags_created = 0

        # Primary provider
        flag, created = FeatureFlag.objects.get_or_create(
            key='llm_provider_primary',
            defaults={
                'value': 'openai',
                'enabled': True,
                'description': 'Primary LLM provider for all tenants'
            }
        )
        if created:
            flags_created += 1
            self.stdout.write(self.style.SUCCESS(f'Created flag: llm_provider_primary = openai'))

        # Secondary provider (fallback)
        flag, created = FeatureFlag.objects.get_or_create(
            key='llm_provider_secondary',
            defaults={
                'value': 'anthropic',
                'enabled': True,
                'description': 'Secondary LLM provider (fallback)'
            }
        )
        if created:
            flags_created += 1
            self.stdout.write(self.style.SUCCESS(f'Created flag: llm_provider_secondary = anthropic'))

        # Tertiary provider (optional)
        flag, created = FeatureFlag.objects.get_or_create(
            key='llm_provider_tertiary',
            defaults={
                'value': 'gemini',
                'enabled': False,
                'description': 'Tertiary LLM provider (optional)'
            }
        )
        if created:
            flags_created += 1
            self.stdout.write(self.style.SUCCESS(f'Created flag: llm_provider_tertiary = gemini (disabled)'))

        if flags_created == 0:
            self.stdout.write(self.style.WARNING('All LLM feature flags already exist'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Initialized {flags_created} LLM feature flags'))
