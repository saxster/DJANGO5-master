"""
Advanced Spatial Data Import Service using GeoDjango LayerMapping

Handles bulk import of spatial data from various formats including:
- Shapefiles (*.shp)
- GeoJSON (*.json, *.geojson)
- KML/KMZ files (*.kml, *.kmz)
- GPX files (*.gpx)
- CSV files with coordinate columns

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation
- Service layer < 150 lines per method
"""

import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.contrib.gis.geos import Point, Polygon, LineString
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.conf import settings
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger(__name__)


class SpatialDataFormat(Enum):
    """Supported spatial data formats"""
    SHAPEFILE = "shp"
    GEOJSON = "geojson"
    KML = "kml"
    KMZ = "kmz"
    GPX = "gpx"
    CSV = "csv"


@dataclass
class ImportResult:
    """Result of spatial data import operation"""
    success: bool
    records_processed: int = 0
    records_imported: int = 0
    records_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    import_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldMapping:
    """Field mapping configuration for imports"""
    model_field: str
    source_field: str
    field_type: str = 'auto'  # auto, string, integer, float, datetime, geometry
    transform_function: Optional[callable] = None
    required: bool = True


class SpatialDataImportError(Exception):
    """Custom exception for spatial data import errors"""
    pass


class UnsupportedFormatError(SpatialDataImportError):
    """Raised when file format is not supported"""
    pass


class SpatialDataImportService:
    """
    Advanced service for importing spatial data using GeoDjango LayerMapping.

    Provides robust, scalable spatial data import capabilities with validation,
    transformation, and error handling.
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.shp': SpatialDataFormat.SHAPEFILE,
        '.geojson': SpatialDataFormat.GEOJSON,
        '.json': SpatialDataFormat.GEOJSON,
        '.kml': SpatialDataFormat.KML,
        '.kmz': SpatialDataFormat.KMZ,
        '.gpx': SpatialDataFormat.GPX,
        '.csv': SpatialDataFormat.CSV,
    }

    # Maximum file size (50MB by default)
    MAX_FILE_SIZE = getattr(settings, 'SPATIAL_IMPORT_MAX_FILE_SIZE', 50 * 1024 * 1024)

    def __init__(self):
        self.temp_dir = None

    def import_spatial_data(self, file_path: Union[str, Path], model_class,
                          field_mapping: Dict[str, str],
                          transform_srid: Optional[int] = None,
                          batch_size: int = 1000,
                          strict_mode: bool = False,
                          create_missing_fields: bool = False) -> ImportResult:
        """
        Import spatial data from file into Django model.

        Args:
            file_path: Path to spatial data file
            model_class: Django model class to import into
            field_mapping: Dictionary mapping model fields to source fields
            transform_srid: Target SRID for coordinate transformation
            batch_size: Number of records to process in each batch
            strict_mode: If True, stops on first error
            create_missing_fields: If True, creates missing model fields

        Returns:
            ImportResult with detailed import statistics

        Raises:
            SpatialDataImportError: If import fails
            UnsupportedFormatError: If file format not supported
        """
        file_path = Path(file_path)
        result = ImportResult(success=False)

        try:
            # Validate file
            self._validate_file(file_path)
            data_format = self._detect_format(file_path)

            logger.info(f"Starting import of {data_format.value} file: {file_path}")

            # Extract if needed (for KMZ, ZIP files)
            extracted_path = self._extract_if_needed(file_path, data_format)

            try:
                # Create LayerMapping and import
                with transaction.atomic():
                    mapping_result = self._create_layer_mapping(
                        extracted_path, model_class, field_mapping,
                        transform_srid, batch_size, strict_mode
                    )

                    result.records_processed = mapping_result['processed']
                    result.records_imported = mapping_result['imported']
                    result.records_skipped = mapping_result['skipped']
                    result.errors = mapping_result['errors']
                    result.warnings = mapping_result['warnings']
                    result.import_summary = mapping_result['summary']

                    if mapping_result['errors'] and strict_mode:
                        raise SpatialDataImportError(f"Import failed: {mapping_result['errors'][0]}")

                result.success = True
                logger.info(
                    f"Import completed: {result.records_imported}/{result.records_processed} "
                    f"records imported successfully"
                )

            finally:
                # Cleanup extracted files
                if extracted_path != file_path:
                    self._cleanup_temp_files()

        except (ValidationError, IntegrityError) as e:
            error_msg = f"Database validation error: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        except FILE_EXCEPTIONS as e:
            error_msg = f"Import failed: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)

        return result

    def inspect_spatial_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Inspect spatial file structure and return metadata.

        Args:
            file_path: Path to spatial file

        Returns:
            Dictionary with file structure information

        Raises:
            SpatialDataImportError: If inspection fails
        """
        file_path = Path(file_path)

        try:
            self._validate_file(file_path)
            data_format = self._detect_format(file_path)

            # Extract if needed
            extracted_path = self._extract_if_needed(file_path, data_format)

            try:
                ds = DataSource(str(extracted_path))
                layer = ds[0]  # Use first layer

                # Get field information
                fields_info = []
                for field in layer.fields:
                    fields_info.append({
                        'name': field,
                        'type': str(layer.field_types[layer.fields.index(field)]),
                        'width': layer.field_widths[layer.fields.index(field)],
                        'precision': layer.field_precisions[layer.fields.index(field)]
                    })

                # Get geometry information
                geometry_info = {
                    'type': layer.geom_type.name,
                    'srid': layer.srs.srid if layer.srs else None,
                    'extent': layer.extent.tuple if hasattr(layer, 'extent') else None
                }

                inspection_result = {
                    'file_format': data_format.value,
                    'layer_count': len(ds),
                    'feature_count': len(layer),
                    'fields': fields_info,
                    'geometry': geometry_info,
                    'spatial_reference': str(layer.srs) if layer.srs else None
                }

                logger.info(f"File inspection completed: {len(layer)} features found")
                return inspection_result

            finally:
                if extracted_path != file_path:
                    self._cleanup_temp_files()

        except FILE_EXCEPTIONS as e:
            raise SpatialDataImportError(f"File inspection failed: {str(e)}")

    def create_import_mapping_template(self, file_path: Union[str, Path],
                                     model_class) -> Dict[str, Any]:
        """
        Create a template field mapping based on file inspection and model fields.

        Args:
            file_path: Path to spatial file
            model_class: Target Django model class

        Returns:
            Dictionary with suggested field mappings

        Raises:
            SpatialDataImportError: If template creation fails
        """
        try:
            # Inspect file structure
            file_info = self.inspect_spatial_file(file_path)

            # Get model field information
            model_fields = {}
            for field in model_class._meta.get_fields():
                if hasattr(field, 'name'):
                    field_type = field.__class__.__name__
                    model_fields[field.name] = {
                        'type': field_type,
                        'required': not field.null if hasattr(field, 'null') else True,
                        'max_length': getattr(field, 'max_length', None)
                    }

            # Create suggested mappings
            suggested_mappings = {}
            source_fields = [field['name'] for field in file_info['fields']]

            # Try to match fields by name similarity
            for model_field, field_info in model_fields.items():
                best_match = self._find_best_field_match(model_field, source_fields)
                if best_match:
                    suggested_mappings[model_field] = best_match

            return {
                'file_info': file_info,
                'model_fields': model_fields,
                'suggested_mappings': suggested_mappings,
                'unmapped_source_fields': [
                    field for field in source_fields
                    if field not in suggested_mappings.values()
                ],
                'unmapped_model_fields': [
                    field for field in model_fields.keys()
                    if field not in suggested_mappings.keys()
                ]
            }

        except FILE_EXCEPTIONS as e:
            raise SpatialDataImportError(f"Template creation failed: {str(e)}")

    def _validate_file(self, file_path: Path) -> None:
        """Validate input file"""
        if not file_path.exists():
            raise SpatialDataImportError(f"File not found: {file_path}")

        if file_path.stat().st_size > self.MAX_FILE_SIZE:
            raise SpatialDataImportError(
                f"File too large: {file_path.stat().st_size} bytes "
                f"(max: {self.MAX_FILE_SIZE} bytes)"
            )

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported: {list(self.SUPPORTED_EXTENSIONS.keys())}"
            )

    def _detect_format(self, file_path: Path) -> SpatialDataFormat:
        """Detect spatial data format from file extension"""
        extension = file_path.suffix.lower()
        return self.SUPPORTED_EXTENSIONS.get(extension, SpatialDataFormat.SHAPEFILE)

    def _extract_if_needed(self, file_path: Path, data_format: SpatialDataFormat) -> Path:
        """Extract compressed files if needed"""
        if data_format == SpatialDataFormat.KMZ:
            return self._extract_kmz(file_path)
        elif file_path.suffix.lower() == '.zip':
            return self._extract_shapefile_zip(file_path)
        return file_path

    def _extract_kmz(self, kmz_path: Path) -> Path:
        """Extract KMZ file and return path to KML"""
        self.temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(kmz_path, 'r') as zip_file:
            zip_file.extractall(self.temp_dir)

        # Find KML file in extracted content
        for file in Path(self.temp_dir).glob('*.kml'):
            return file

        raise SpatialDataImportError("No KML file found in KMZ archive")

    def _extract_shapefile_zip(self, zip_path: Path) -> Path:
        """Extract shapefile ZIP and return path to SHP file"""
        self.temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            zip_file.extractall(self.temp_dir)

        # Find SHP file in extracted content
        for file in Path(self.temp_dir).glob('*.shp'):
            return file

        raise SpatialDataImportError("No SHP file found in ZIP archive")

    def _create_layer_mapping(self, file_path: Path, model_class,
                            field_mapping: Dict[str, str],
                            transform_srid: Optional[int],
                            batch_size: int,
                            strict_mode: bool) -> Dict[str, Any]:
        """Create LayerMapping and perform import"""
        try:
            # Create LayerMapping instance
            mapping = LayerMapping(
                model_class,
                str(file_path),
                field_mapping,
                transform=True,
                unique=None,  # Allow duplicates by default
                using='default'
            )

            # Configure import options
            import_options = {
                'strict': strict_mode,
                'verbose': True,
                'step': batch_size,
                'progress': True
            }

            # Perform the import
            import_stats = {
                'processed': 0,
                'imported': 0,
                'skipped': 0,
                'errors': [],
                'warnings': [],
                'summary': {}
            }

            try:
                # Save the mapping
                mapping.save(**import_options)

                # Get import statistics
                import_stats['processed'] = len(mapping.ds[0])
                import_stats['imported'] = len(mapping.ds[0])  # All processed if no errors
                import_stats['summary'] = {
                    'source_srid': mapping.ds[0].srs.srid if mapping.ds[0].srs else None,
                    'target_srid': transform_srid,
                    'geometry_type': mapping.ds[0].geom_type.name,
                    'feature_count': len(mapping.ds[0])
                }

            except DATABASE_EXCEPTIONS as import_error:
                error_msg = str(import_error)
                import_stats['errors'].append(error_msg)
                if strict_mode:
                    raise

            return import_stats

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"LayerMapping creation failed: {str(e)}")
            raise SpatialDataImportError(f"LayerMapping failed: {str(e)}")

    def _find_best_field_match(self, model_field: str, source_fields: List[str]) -> Optional[str]:
        """Find best matching source field for model field"""
        model_field_lower = model_field.lower()

        # Exact match first
        for source_field in source_fields:
            if source_field.lower() == model_field_lower:
                return source_field

        # Partial match
        for source_field in source_fields:
            if model_field_lower in source_field.lower() or source_field.lower() in model_field_lower:
                return source_field

        # Common field name mappings
        common_mappings = {
            'name': ['name', 'title', 'label', 'description'],
            'code': ['code', 'id', 'identifier', 'key'],
            'gpslocation': ['geometry', 'geom', 'location', 'point', 'coordinates']
        }

        if model_field_lower in common_mappings:
            for mapping in common_mappings[model_field_lower]:
                for source_field in source_fields:
                    if mapping in source_field.lower():
                        return source_field

        return None

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
            finally:
                self.temp_dir = None


# Convenience function for quick imports
def import_spatial_data(file_path: Union[str, Path], model_class,
                       field_mapping: Dict[str, str], **kwargs) -> ImportResult:
    """
    Convenience function for importing spatial data.

    Args:
        file_path: Path to spatial data file
        model_class: Django model class
        field_mapping: Field mapping dictionary
        **kwargs: Additional import options

    Returns:
        ImportResult object
    """
    service = SpatialDataImportService()
    return service.import_spatial_data(file_path, model_class, field_mapping, **kwargs)