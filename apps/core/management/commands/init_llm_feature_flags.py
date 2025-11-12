"""
Initialize LLM Feature Flag Metadata

Seeds FeatureFlagMetadata entries that the LLM provider router consumes for
tenant-level overrides and fallback chain orchestration.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.feature_flags.models import FeatureFlagMetadata


class Command(BaseCommand):
    help = "Initialize LLM provider metadata records"

    def handle(self, *args, **options):
        definitions = [
            ("llm_provider_primary", "openai", True, 0),
            ("llm_provider_secondary", "anthropic", True, 1),
            ("llm_provider_tertiary", "gemini", False, 2),
        ]

        created = 0
        updated = 0

        qs = FeatureFlagMetadata.objects.cross_tenant_query()

        for flag_name, provider, enabled, rank in definitions:
            payload = {
                "rollout_percentage": 100 if enabled else 0,
                "deployment_metadata": {
                    "provider": provider,
                    "enabled": enabled,
                    "rank": rank,
                    "seeded_at": timezone.now().isoformat(),
                },
            }
            metadata = qs.filter(flag_name=flag_name).first()

            if metadata:
                for field, value in payload.items():
                    setattr(metadata, field, value)
                metadata.save(
                    update_fields=["rollout_percentage", "deployment_metadata", "updated_at"],
                    skip_tenant_validation=True,
                )
                updated += 1
            else:
                metadata = FeatureFlagMetadata(flag_name=flag_name, **payload)
                metadata.save(skip_tenant_validation=True)
                created += 1

        chain_metadata = qs.filter(flag_name="llm_provider_chain").first()
        chain_payload = {
            "deployment_metadata": {
                "chain": [definition[1] for definition in definitions if definition[2]],
                "seeded_at": timezone.now().isoformat(),
            },
        }
        if chain_metadata:
            chain_metadata.deployment_metadata = chain_payload["deployment_metadata"]
            chain_metadata.save(
                update_fields=["deployment_metadata", "updated_at"],
                skip_tenant_validation=True,
            )
            updated += 1
        else:
            chain_metadata = FeatureFlagMetadata(
                flag_name="llm_provider_chain",
                rollout_percentage=0,
                deployment_metadata=chain_payload["deployment_metadata"],
            )
            chain_metadata.save(skip_tenant_validation=True)
            created += 1

        summary = []
        if created:
            summary.append(f"created {created}")
        if updated:
            summary.append(f"updated {updated}")

        if summary:
            self.stdout.write(self.style.SUCCESS(f"LLM feature flag metadata {' & '.join(summary)}"))
        else:
            self.stdout.write(self.style.WARNING("No LLM metadata changes applied"))
