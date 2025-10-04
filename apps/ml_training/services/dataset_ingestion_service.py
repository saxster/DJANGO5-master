"""
Dataset Ingestion Service - Enterprise training data upload and processing.

Handles bulk upload, validation, deduplication, and metadata extraction
for training datasets with comprehensive quality assurance.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from PIL import Image
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction, DatabaseError
from django.conf import settings
from django.utils import timezone

from ..models import TrainingDataset, TrainingExample
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class DatasetIngestionService:
    """
    Enterprise dataset ingestion with validation and quality control.

    Provides bulk upload capabilities with automatic deduplication,
    metadata extraction, and quality scoring.
    """

    def __init__(self):
        """Initialize ingestion service with configuration."""
        self.upload_path = getattr(settings, 'ML_TRAINING_UPLOAD_PATH', 'ml_training/uploads')
        self.max_file_size = getattr(settings, 'ML_TRAINING_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.supported_formats = {'jpg', 'jpeg', 'png', 'tiff', 'bmp', 'webp'}
        self.min_image_size = (32, 32)
        self.max_image_size = (4096, 4096)

    def create_dataset(
        self,
        name: str,
        dataset_type: str,
        description: str,
        created_by: People,
        labeling_guidelines: str = "",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a new training dataset.

        Args:
            name: Dataset name
            dataset_type: Type from TrainingDataset.DatasetType choices
            description: Dataset description
            created_by: User creating the dataset
            labeling_guidelines: Instructions for labelers
            metadata: Additional configuration

        Returns:
            {
                'success': bool,
                'dataset': TrainingDataset | None,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'dataset': None,
            'error': None
        }

        try:
            # Validate dataset type
            valid_types = [choice[0] for choice in TrainingDataset.DatasetType.choices]
            if dataset_type not in valid_types:
                result['error'] = f"Invalid dataset type: {dataset_type}"
                return result

            # Check for duplicate names
            if TrainingDataset.objects.filter(name=name).exists():
                result['error'] = f"Dataset with name '{name}' already exists"
                return result

            with transaction.atomic():
                dataset = TrainingDataset.objects.create(
                    name=name,
                    dataset_type=dataset_type,
                    description=description,
                    created_by=created_by,
                    labeling_guidelines=labeling_guidelines,
                    metadata=metadata or {}
                )

                result['success'] = True
                result['dataset'] = dataset

                logger.info(f"Created dataset '{name}' (ID: {dataset.id}) by {created_by.peoplename}")

        except DatabaseError as e:
            logger.error(f"Database error creating dataset: {str(e)}")
            result['error'] = f"Database error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error creating dataset: {str(e)}", exc_info=True)
            result['error'] = f"Failed to create dataset: {str(e)}"

        return result

    def bulk_upload_images(
        self,
        dataset: TrainingDataset,
        image_files: List[UploadedFile],
        ground_truth_data: Dict[str, Any] = None,
        uploaded_by: People = None
    ) -> Dict[str, Any]:
        """
        Bulk upload images to a training dataset.

        Args:
            dataset: Target training dataset
            image_files: List of uploaded image files
            ground_truth_data: Optional ground truth labels
            uploaded_by: User uploading the data

        Returns:
            {
                'success': bool,
                'processed': int,
                'skipped': int,
                'errors': List[str],
                'examples': List[TrainingExample]
            }
        """
        result = {
            'success': False,
            'processed': 0,
            'skipped': 0,
            'errors': [],
            'examples': []
        }

        if not image_files:
            result['error'] = "No image files provided"
            return result

        try:
            with transaction.atomic():
                for i, image_file in enumerate(image_files):
                    try:
                        upload_result = self._process_single_image(
                            dataset=dataset,
                            image_file=image_file,
                            ground_truth=ground_truth_data.get(image_file.name) if ground_truth_data else None,
                            uploaded_by=uploaded_by
                        )

                        if upload_result['success']:
                            result['processed'] += 1
                            result['examples'].append(upload_result['example'])
                        else:
                            result['skipped'] += 1
                            result['errors'].append(f"{image_file.name}: {upload_result['error']}")

                    except Exception as e:
                        result['skipped'] += 1
                        result['errors'].append(f"{image_file.name}: {str(e)}")
                        logger.error(f"Error processing {image_file.name}: {str(e)}")

                # Update dataset statistics
                dataset.update_stats()
                result['success'] = True

                logger.info(
                    f"Bulk upload to dataset {dataset.id}: "
                    f"{result['processed']} processed, {result['skipped']} skipped"
                )

        except DatabaseError as e:
            logger.error(f"Database error during bulk upload: {str(e)}")
            result['errors'].append(f"Database error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during bulk upload: {str(e)}", exc_info=True)
            result['errors'].append(f"Upload failed: {str(e)}")

        return result

    def _process_single_image(
        self,
        dataset: TrainingDataset,
        image_file: UploadedFile,
        ground_truth: Any = None,
        uploaded_by: People = None
    ) -> Dict[str, Any]:
        """Process a single image file with validation and storage."""
        result = {
            'success': False,
            'example': None,
            'error': None
        }

        try:
            # Validate file
            validation_result = self._validate_image_file(image_file)
            if not validation_result['valid']:
                result['error'] = validation_result['error']
                return result

            # Calculate hash for deduplication
            image_hash = self._calculate_file_hash(image_file)

            # Check for duplicates
            if TrainingExample.objects.filter(image_hash=image_hash).exists():
                result['error'] = "Duplicate image (already exists in dataset)"
                return result

            # Save file to storage
            file_path = self._save_image_file(image_file, image_hash)
            if not file_path:
                result['error'] = "Failed to save image file"
                return result

            # Extract image metadata
            image_metadata = self._extract_image_metadata(file_path)

            # Prepare ground truth data
            ground_truth_text = ""
            ground_truth_data = {}

            if ground_truth:
                if isinstance(ground_truth, str):
                    ground_truth_text = ground_truth
                elif isinstance(ground_truth, dict):
                    ground_truth_text = ground_truth.get('text', '')
                    ground_truth_data = ground_truth

            # Create training example
            example = TrainingExample.objects.create(
                dataset=dataset,
                image_path=file_path,
                image_hash=image_hash,
                image_width=image_metadata.get('width'),
                image_height=image_metadata.get('height'),
                file_size=image_metadata.get('file_size'),
                ground_truth_text=ground_truth_text,
                ground_truth_data=ground_truth_data,
                example_type=TrainingExample.ExampleType.CROWDSOURCED.value,
                capture_metadata={
                    'upload_timestamp': timezone.now().isoformat(),
                    'uploaded_by': uploaded_by.peoplename if uploaded_by else None,
                    'original_filename': image_file.name,
                    'content_type': image_file.content_type,
                    **image_metadata
                }
            )

            result['success'] = True
            result['example'] = example

        except ValidationError as e:
            result['error'] = f"Validation error: {str(e)}"
        except (IOError, OSError) as e:
            result['error'] = f"File operation error: {str(e)}"
        except Exception as e:
            logger.error(f"Error processing image {image_file.name}: {str(e)}", exc_info=True)
            result['error'] = f"Processing failed: {str(e)}"

        return result

    def _validate_image_file(self, image_file: UploadedFile) -> Dict[str, Any]:
        """Validate uploaded image file."""
        result = {'valid': False, 'error': None}

        try:
            # Check file size
            if image_file.size > self.max_file_size:
                result['error'] = f"File too large: {image_file.size} bytes (max: {self.max_file_size})"
                return result

            # Check file extension
            file_ext = Path(image_file.name).suffix.lower().lstrip('.')
            if file_ext not in self.supported_formats:
                result['error'] = f"Unsupported format: {file_ext} (supported: {self.supported_formats})"
                return result

            # Validate image content
            try:
                with Image.open(image_file) as img:
                    # Check image dimensions
                    if (img.width < self.min_image_size[0] or
                        img.height < self.min_image_size[1]):
                        result['error'] = f"Image too small: {img.width}x{img.height} (min: {self.min_image_size})"
                        return result

                    if (img.width > self.max_image_size[0] or
                        img.height > self.max_image_size[1]):
                        result['error'] = f"Image too large: {img.width}x{img.height} (max: {self.max_image_size})"
                        return result

                    # Check if image can be processed
                    img.verify()

            except Exception as e:
                result['error'] = f"Invalid image file: {str(e)}"
                return result

            result['valid'] = True

        except Exception as e:
            result['error'] = f"Validation failed: {str(e)}"

        return result

    def _calculate_file_hash(self, image_file: UploadedFile) -> str:
        """Calculate SHA256 hash of uploaded file."""
        image_file.seek(0)
        hash_sha256 = hashlib.sha256()
        for chunk in iter(lambda: image_file.read(4096), b""):
            hash_sha256.update(chunk)
        image_file.seek(0)
        return hash_sha256.hexdigest()

    def _save_image_file(self, image_file: UploadedFile, image_hash: str) -> Optional[str]:
        """Save image file to storage with hash-based naming."""
        try:
            # Create upload directory
            upload_dir = Path(settings.MEDIA_ROOT) / self.upload_path
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from hash and original extension
            file_ext = Path(image_file.name).suffix.lower()
            filename = f"{image_hash}{file_ext}"
            file_path = upload_dir / filename

            # Save file
            with open(file_path, 'wb') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)

            # Return relative path for database storage
            return str(Path(self.upload_path) / filename)

        except (IOError, OSError) as e:
            logger.error(f"Failed to save image file: {str(e)}")
            return None

    def _extract_image_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from saved image file."""
        metadata = {}

        try:
            full_path = Path(settings.MEDIA_ROOT) / file_path

            # Get file size
            metadata['file_size'] = full_path.stat().st_size

            # Extract image properties
            with Image.open(full_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
                metadata['format'] = img.format
                metadata['mode'] = img.mode

                # Extract EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif() or {}
                    # Filter relevant EXIF data
                    metadata['exif'] = {
                        k: v for k, v in exif_data.items()
                        if k in [272, 306, 36867, 36868]  # Camera make, datetime, etc.
                    }

        except Exception as e:
            logger.warning(f"Failed to extract image metadata: {str(e)}")

        return metadata

    def import_from_production(
        self,
        dataset: TrainingDataset,
        source_system: str,
        source_records: List[Dict[str, Any]],
        confidence_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Import training examples from production data with uncertainty filtering.

        Args:
            dataset: Target dataset
            source_system: Source system identifier
            source_records: List of production records with images and metadata
            confidence_threshold: Only import records below this confidence

        Returns:
            Import statistics and results
        """
        result = {
            'success': False,
            'imported': 0,
            'skipped': 0,
            'errors': []
        }

        try:
            with transaction.atomic():
                for record in source_records:
                    try:
                        # Skip high-confidence predictions (not useful for training)
                        confidence = record.get('confidence_score', 1.0)
                        if confidence >= confidence_threshold:
                            result['skipped'] += 1
                            continue

                        # Import the uncertain example
                        import_result = self._import_production_record(
                            dataset=dataset,
                            source_system=source_system,
                            record=record
                        )

                        if import_result['success']:
                            result['imported'] += 1
                        else:
                            result['skipped'] += 1
                            result['errors'].append(
                                f"Record {record.get('id', 'unknown')}: {import_result['error']}"
                            )

                    except Exception as e:
                        result['skipped'] += 1
                        result['errors'].append(f"Record processing error: {str(e)}")

                result['success'] = True
                dataset.update_stats()

                logger.info(
                    f"Production import to dataset {dataset.id}: "
                    f"{result['imported']} imported, {result['skipped']} skipped"
                )

        except Exception as e:
            logger.error(f"Production import failed: {str(e)}", exc_info=True)
            result['errors'].append(f"Import failed: {str(e)}")

        return result

    def _import_production_record(
        self,
        dataset: TrainingDataset,
        source_system: str,
        record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Import a single production record as training example."""
        result = {
            'success': False,
            'error': None
        }

        try:
            # Check if already imported
            source_id = record.get('id') or record.get('uuid')
            if TrainingExample.objects.filter(
                source_system=source_system,
                source_id=str(source_id)
            ).exists():
                result['error'] = "Already imported"
                return result

            # Get image path (assume it's already in media storage)
            image_path = record.get('image_path')
            if not image_path:
                result['error'] = "No image path provided"
                return result

            # Calculate hash if not provided
            image_hash = record.get('image_hash')
            if not image_hash:
                full_path = Path(settings.MEDIA_ROOT) / image_path
                if full_path.exists():
                    with open(full_path, 'rb') as f:
                        image_hash = hashlib.sha256(f.read()).hexdigest()
                else:
                    result['error'] = "Image file not found"
                    return result

            # Create training example
            TrainingExample.objects.create(
                dataset=dataset,
                image_path=image_path,
                image_hash=image_hash,
                image_width=record.get('image_width'),
                image_height=record.get('image_height'),
                file_size=record.get('file_size'),
                ground_truth_text=record.get('corrected_text', ''),
                ground_truth_data=record.get('corrected_data', {}),
                example_type=TrainingExample.ExampleType.PRODUCTION.value,
                uncertainty_score=1.0 - record.get('confidence_score', 0.5),
                source_system=source_system,
                source_id=str(source_id),
                capture_metadata=record.get('metadata', {}),
                selected_for_labeling=True,  # Auto-select uncertain examples
                labeling_priority=int((1.0 - record.get('confidence_score', 0.5)) * 10)
            )

            result['success'] = True

        except Exception as e:
            logger.error(f"Failed to import production record: {str(e)}")
            result['error'] = str(e)

        return result


# Factory function
def get_dataset_ingestion_service() -> DatasetIngestionService:
    """Factory function to get dataset ingestion service instance."""
    return DatasetIngestionService()