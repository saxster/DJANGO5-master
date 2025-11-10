"""
Django management command for importing spatial data using LayerMapping.

Usage examples:
python manage.py import_spatial_data assets.shp activity.Asset --mapping='{"assetname": "NAME", "gpslocation": "GEOMETRY"}'
python manage.py import_spatial_data locations.geojson activity.Location --inspect
python manage.py import_spatial_data sites.kml client_onboarding.Bt --template
"""

import json
from pathlib import Path
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from apps.core.services.spatial_data_import_service import SpatialDataImportService, ImportResult
from apps.core.exceptions.patterns import FILE_EXCEPTIONS

from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS



class Command(BaseCommand):
    help = 'Import spatial data into Django models using GeoDjango LayerMapping'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the spatial data file (shapefile, GeoJSON, KML, etc.)'
        )

        parser.add_argument(
            'model',
            type=str,
            nargs='?',
            help='Model to import into (format: app_label.ModelName)'
        )

        parser.add_argument(
            '--mapping',
            type=str,
            help='JSON string mapping model fields to source fields'
        )

        parser.add_argument(
            '--inspect',
            action='store_true',
            help='Inspect file structure without importing'
        )

        parser.add_argument(
            '--template',
            action='store_true',
            help='Generate mapping template for the file and model'
        )

        parser.add_argument(
            '--srid',
            type=int,
            help='Target SRID for coordinate transformation (default: 4326)',
            default=4326
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of records to process in each batch (default: 1000)',
            default=1000
        )

        parser.add_argument(
            '--strict',
            action='store_true',
            help='Stop on first error (default: continue with warnings)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate without actually importing data'
        )

        parser.add_argument(
            '--output',
            type=str,
            help='Output file for inspection results (JSON format)'
        )

    def handle(self, *args, **options):
        file_path = Path(options['file_path'])
        service = SpatialDataImportService()

        try:
            # Check if file exists
            if not file_path.exists():
                raise CommandError(f"File not found: {file_path}")

            # Inspect mode
            if options['inspect']:
                self._handle_inspect(service, file_path, options)
                return

            # Template generation mode
            if options['template']:
                if not options['model']:
                    raise CommandError("Model must be specified for template generation")
                self._handle_template(service, file_path, options)
                return

            # Import mode
            if not options['model'] or not options['mapping']:
                raise CommandError("Both model and mapping must be specified for import")

            self._handle_import(service, file_path, options)

        except TEMPLATE_EXCEPTIONS as e:
            raise CommandError(f"Command failed: {str(e)}")

    def _handle_inspect(self, service, file_path, options):
        """Handle file inspection"""
        self.stdout.write(self.style.HTTP_INFO(f"Inspecting file: {file_path}"))

        try:
            inspection_result = service.inspect_spatial_file(file_path)

            # Display results
            self.stdout.write(self.style.SUCCESS("\nFile Inspection Results:"))
            self.stdout.write(f"Format: {inspection_result['file_format']}")
            self.stdout.write(f"Features: {inspection_result['feature_count']}")
            self.stdout.write(f"Geometry Type: {inspection_result['geometry']['type']}")

            if inspection_result['geometry']['srid']:
                self.stdout.write(f"SRID: {inspection_result['geometry']['srid']}")

            self.stdout.write(f"\nFields ({len(inspection_result['fields'])}):")
            for field in inspection_result['fields']:
                self.stdout.write(f"  - {field['name']} ({field['type']})")

            # Save to file if requested
            if options['output']:
                output_path = Path(options['output'])
                with open(output_path, 'w') as f:
                    json.dump(inspection_result, f, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"Inspection results saved to: {output_path}")
                )

        except FILE_EXCEPTIONS as e:
            raise CommandError(f"Inspection failed: {str(e)}")

    def _handle_template(self, service, file_path, options):
        """Handle template generation"""
        model_class = self._get_model_class(options['model'])

        self.stdout.write(self.style.HTTP_INFO(f"Generating mapping template for: {options['model']}"))

        try:
            template_result = service.create_import_mapping_template(file_path, model_class)

            # Display template
            self.stdout.write(self.style.SUCCESS("\nSuggested Field Mappings:"))

            if template_result['suggested_mappings']:
                mapping_json = json.dumps(template_result['suggested_mappings'], indent=2)
                self.stdout.write(mapping_json)

                self.stdout.write(self.style.WARNING("\nUsage example:"))
                self.stdout.write(
                    f"python manage.py import_spatial_data {file_path} {options['model']} "
                    f"--mapping='{json.dumps(template_result['suggested_mappings'])}'"
                )
            else:
                self.stdout.write(self.style.WARNING("No automatic mappings could be suggested"))

            # Show unmapped fields
            if template_result['unmapped_source_fields']:
                self.stdout.write(self.style.WARNING(f"\nUnmapped Source Fields:"))
                for field in template_result['unmapped_source_fields']:
                    self.stdout.write(f"  - {field}")

            if template_result['unmapped_model_fields']:
                self.stdout.write(self.style.WARNING(f"\nUnmapped Model Fields:"))
                for field in template_result['unmapped_model_fields']:
                    model_field_info = template_result['model_fields'][field]
                    required_text = " (required)" if model_field_info['required'] else ""
                    self.stdout.write(f"  - {field} ({model_field_info['type']}){required_text}")

            # Save template if requested
            if options['output']:
                output_path = Path(options['output'])
                with open(output_path, 'w') as f:
                    json.dump(template_result, f, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"Template saved to: {output_path}")
                )

        except TEMPLATE_EXCEPTIONS as e:
            raise CommandError(f"Template generation failed: {str(e)}")

    def _handle_import(self, service, file_path, options):
        """Handle data import"""
        model_class = self._get_model_class(options['model'])

        try:
            field_mapping = json.loads(options['mapping'])
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid mapping JSON: {str(e)}")

        self.stdout.write(
            self.style.HTTP_INFO(
                f"Importing {file_path} into {options['model']} "
                f"({'dry run' if options['dry_run'] else 'live import'})"
            )
        )

        # Display import parameters
        self.stdout.write(f"Field Mapping: {json.dumps(field_mapping, indent=2)}")
        self.stdout.write(f"Target SRID: {options['srid']}")
        self.stdout.write(f"Batch Size: {options['batch_size']}")
        self.stdout.write(f"Strict Mode: {options['strict']}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - No data will be imported"))
            # For dry run, just inspect and validate
            try:
                inspection = service.inspect_spatial_file(file_path)
                self.stdout.write(self.style.SUCCESS(f"✓ File validation passed"))
                self.stdout.write(self.style.SUCCESS(f"✓ Found {inspection['feature_count']} features"))

                # Validate field mapping
                source_fields = [f['name'] for f in inspection['fields']]
                missing_fields = [f for f in field_mapping.values() if f not in source_fields]
                if missing_fields:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Missing source fields: {missing_fields}")
                    )
                else:
                    self.stdout.write(self.style.SUCCESS("✓ Field mapping validated"))

            except FILE_EXCEPTIONS as e:
                raise CommandError(f"Dry run validation failed: {str(e)}")
            return

        try:
            # Perform actual import
            result = service.import_spatial_data(
                file_path=file_path,
                model_class=model_class,
                field_mapping=field_mapping,
                transform_srid=options['srid'],
                batch_size=options['batch_size'],
                strict_mode=options['strict']
            )

            # Display results
            self._display_import_results(result)

        except FILE_EXCEPTIONS as e:
            raise CommandError(f"Import failed: {str(e)}")

    def _get_model_class(self, model_string):
        """Get model class from string format 'app_label.ModelName'"""
        try:
            app_label, model_name = model_string.split('.')
            return apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            raise CommandError(
                f"Invalid model '{model_string}'. Use format: app_label.ModelName"
            )

    def _display_import_results(self, result: ImportResult):
        """Display import results"""
        if result.success:
            self.stdout.write(self.style.SUCCESS("\n✓ Import Completed Successfully"))
        else:
            self.stdout.write(self.style.ERROR("\n✗ Import Failed"))

        # Statistics
        self.stdout.write(f"Records Processed: {result.records_processed}")
        self.stdout.write(f"Records Imported: {result.records_imported}")
        self.stdout.write(f"Records Skipped: {result.records_skipped}")

        # Success rate
        if result.records_processed > 0:
            success_rate = (result.records_imported / result.records_processed) * 100
            self.stdout.write(f"Success Rate: {success_rate:.1f}%")

        # Summary information
        if result.import_summary:
            self.stdout.write("\nImport Summary:")
            for key, value in result.import_summary.items():
                self.stdout.write(f"  {key}: {value}")

        # Warnings
        if result.warnings:
            self.stdout.write(self.style.WARNING(f"\nWarnings ({len(result.warnings)}):"))
            for warning in result.warnings[:5]:  # Show first 5 warnings
                self.stdout.write(self.style.WARNING(f"  - {warning}"))
            if len(result.warnings) > 5:
                self.stdout.write(f"  ... and {len(result.warnings) - 5} more warnings")

        # Errors
        if result.errors:
            self.stdout.write(self.style.ERROR(f"\nErrors ({len(result.errors)}):"))
            for error in result.errors[:5]:  # Show first 5 errors
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            if len(result.errors) > 5:
                self.stdout.write(f"  ... and {len(result.errors) - 5} more errors")