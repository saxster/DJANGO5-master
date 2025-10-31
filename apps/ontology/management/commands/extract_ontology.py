"""
Management command to extract ontology metadata from the codebase.

Usage:
    python manage.py extract_ontology [--output OUTPUT] [--format {json,yaml}]
"""

import json
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ontology.extractors import APIExtractor, ASTExtractor, ModelExtractor
from apps.ontology.registry import OntologyRegistry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Extract ontology metadata from the Django codebase.

    This command scans the codebase and extracts semantic metadata about:
    - Functions and classes
    - Django models
    - REST API endpoints
    - Celery tasks (if available)
    - Security patterns
    - Configuration

    The extracted metadata is stored in the OntologyRegistry and can be
    exported to various formats.
    """

    help = "Extract ontology metadata from the codebase"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--output",
            type=str,
            default="ontology_data.json",
            help="Output file path (default: ontology_data.json)",
        )

        parser.add_argument(
            "--format",
            type=str,
            choices=["json"],
            default="json",
            help="Output format (default: json)",
        )

        parser.add_argument(
            "--apps",
            type=str,
            nargs="+",
            help="Specific apps to extract (default: all apps)",
        )

        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose output"
        )

        parser.add_argument(
            "--models-only",
            action="store_true",
            help="Extract only Django models",
        )

        parser.add_argument(
            "--api-only",
            action="store_true",
            help="Extract only API components",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing registry before extraction",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        if options["verbose"]:
            logger.setLevel(logging.DEBUG)

        self.stdout.write(
            self.style.SUCCESS("Starting ontology extraction...")
        )

        # Clear registry if requested
        if options["clear"]:
            OntologyRegistry.clear()
            self.stdout.write(
                self.style.WARNING("Cleared existing ontology registry")
            )

        # Determine which apps to scan
        apps_to_scan = self._get_apps_to_scan(options.get("apps"))

        # Initialize extractors
        extractors = self._initialize_extractors(options)

        # Extract metadata
        total_items = 0
        for app_path in apps_to_scan:
            self.stdout.write(f"Scanning app: {app_path.name}")

            for extractor in extractors:
                try:
                    metadata_items = extractor.extract_directory(app_path)
                    item_count = len(metadata_items)

                    # Register all extracted items
                    OntologyRegistry.bulk_register(metadata_items)

                    total_items += item_count

                    if options["verbose"]:
                        self.stdout.write(
                            f"  - {extractor.__class__.__name__}: {item_count} items"
                        )

                    # Report errors
                    report = extractor.get_report()
                    if report["error_count"] > 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  - {report['error_count']} errors encountered"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error scanning {app_path}: {e}")
                    )

        # Display statistics
        stats = OntologyRegistry.get_statistics()
        self.stdout.write(self.style.SUCCESS("\nExtraction complete!"))
        self.stdout.write(f"Total components extracted: {total_items}")
        self.stdout.write(f"Registered components: {stats['total_components']}")
        self.stdout.write(f"\nBreakdown by type:")
        for code_type, count in stats["by_type"].items():
            self.stdout.write(f"  - {code_type}: {count}")

        if stats["by_domain"]:
            self.stdout.write(f"\nBreakdown by domain:")
            for domain, count in stats["by_domain"].items():
                self.stdout.write(f"  - {domain}: {count}")

        # Export to file
        output_path = Path(options["output"])
        try:
            self._export_data(output_path, options["format"])
            self.stdout.write(
                self.style.SUCCESS(f"\nData exported to: {output_path}")
            )
        except Exception as e:
            raise CommandError(f"Failed to export data: {e}")

    def _get_apps_to_scan(self, specified_apps):
        """
        Get list of app directories to scan.

        Args:
            specified_apps: List of app names or None for all apps

        Returns:
            List of Path objects for app directories
        """
        base_dir = Path(settings.BASE_DIR)
        apps_dir = base_dir / "apps"

        if not apps_dir.exists():
            raise CommandError(f"Apps directory not found: {apps_dir}")

        if specified_apps:
            # Scan only specified apps
            app_paths = []
            for app_name in specified_apps:
                app_path = apps_dir / app_name
                if not app_path.exists():
                    self.stdout.write(
                        self.style.WARNING(f"App not found: {app_name}")
                    )
                else:
                    app_paths.append(app_path)
            return app_paths
        else:
            # Scan all apps
            return [
                path
                for path in apps_dir.iterdir()
                if path.is_dir() and not path.name.startswith("_")
            ]

    def _initialize_extractors(self, options):
        """
        Initialize the appropriate extractors based on options.

        Args:
            options: Command options dictionary

        Returns:
            List of extractor instances
        """
        extractors = []

        if options["models_only"]:
            extractors.append(ModelExtractor())
        elif options["api_only"]:
            extractors.append(APIExtractor())
        else:
            # Use all available extractors
            extractors.append(ASTExtractor())
            extractors.append(ModelExtractor())
            extractors.append(APIExtractor())

            # Add Phase 2 extractors if they exist
            try:
                from apps.ontology.extractors.celery_extractor import CeleryExtractor

                extractors.append(CeleryExtractor())
            except ImportError:
                pass

            try:
                from apps.ontology.extractors.security_extractor import SecurityExtractor

                extractors.append(SecurityExtractor())
            except ImportError:
                pass

            try:
                from apps.ontology.extractors.config_extractor import ConfigExtractor

                extractors.append(ConfigExtractor())
            except ImportError:
                pass

        return extractors

    def _export_data(self, output_path, format_type):
        """
        Export ontology data to file.

        Args:
            output_path: Path where data should be written
            format_type: Format type ('json' or 'yaml')
        """
        if format_type == "json":
            OntologyRegistry.export_json(output_path)
        else:
            raise CommandError(f"Unsupported format: {format_type}")
