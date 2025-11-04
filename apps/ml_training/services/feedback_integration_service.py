"""
Feedback Integration Service - Production-to-training feedback loop.

Captures production errors, user corrections, and model failures
to create training data and improve model performance continuously.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.db import transaction, models
from django.db.models import Q, Count, Avg
from django.utils import timezone

from ..models import TrainingDataset, TrainingExample, LabelingTask
from apps.activity.models import MeterReading, VehicleEntry
from apps.peoples.models import People
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class FeedbackIntegrationService:
    """
    Production feedback integration for continuous model improvement.

    Automatically captures production errors, user corrections,
    and model failures to create high-value training data.
    """

    def __init__(self):
        """Initialize feedback integration service."""
        self.confidence_threshold = 0.7  # Below this, consider for training
        self.batch_size = 50  # Batch size for processing feedback
        self.auto_dataset_names = {
            'meter_readings': 'Production Meter Reading Feedback',
            'vehicle_entries': 'Production Vehicle Entry Feedback',
            'ocr_general': 'Production OCR Feedback'
        }

    def capture_meter_reading_feedback(
        self,
        meter_reading: MeterReading,
        corrected_value: str,
        corrected_by: People,
        correction_type: str = "user_correction"
    ) -> Dict[str, Any]:
        """
        Capture feedback from meter reading corrections.

        Args:
            meter_reading: Original meter reading with error
            corrected_value: User-corrected reading value
            corrected_by: User who made the correction
            correction_type: Type of correction (user_correction, validation_failure, etc.)

        Returns:
            {
                'success': bool,
                'training_example': TrainingExample | None,
                'dataset': TrainingDataset | None,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'training_example': None,
            'dataset': None,
            'error': None
        }

        try:
            # Only capture low-confidence predictions or validation failures
            if (meter_reading.confidence_score and
                meter_reading.confidence_score >= self.confidence_threshold and
                correction_type != "validation_failure"):
                result['error'] = "High confidence reading - not suitable for training"
                return result

            # Get or create feedback dataset
            dataset = self._get_or_create_feedback_dataset(
                'meter_readings',
                TrainingDataset.DatasetType.OCR_METERS.value,
                "Automatically collected meter reading corrections from production"
            )

            if not dataset:
                result['error'] = "Failed to create/get feedback dataset"
                return result

            # Create training example from the correction
            training_example = self._create_meter_reading_example(
                dataset=dataset,
                meter_reading=meter_reading,
                corrected_value=corrected_value,
                corrected_by=corrected_by,
                correction_type=correction_type
            )

            if training_example:
                result['success'] = True
                result['training_example'] = training_example
                result['dataset'] = dataset

                logger.info(
                    f"Captured meter reading feedback: {meter_reading.id} -> {corrected_value}"
                )
            else:
                result['error'] = "Failed to create training example"

        except Exception as e:
            logger.error(f"Error capturing meter reading feedback: {str(e)}", exc_info=True)
            result['error'] = f"Feedback capture failed: {str(e)}"

        return result

    def capture_vehicle_entry_feedback(
        self,
        vehicle_entry: VehicleEntry,
        corrected_license_plate: str,
        corrected_by: People,
        correction_type: str = "user_correction"
    ) -> Dict[str, Any]:
        """
        Capture feedback from vehicle entry corrections.

        Args:
            vehicle_entry: Original vehicle entry with error
            corrected_license_plate: User-corrected license plate
            corrected_by: User who made the correction
            correction_type: Type of correction

        Returns:
            Feedback capture result
        """
        result = {
            'success': False,
            'training_example': None,
            'dataset': None,
            'error': None
        }

        try:
            # Only capture uncertain predictions
            if (vehicle_entry.confidence_score and
                vehicle_entry.confidence_score >= self.confidence_threshold and
                correction_type != "validation_failure"):
                result['error'] = "High confidence prediction - not suitable for training"
                return result

            # Get or create feedback dataset
            dataset = self._get_or_create_feedback_dataset(
                'vehicle_entries',
                TrainingDataset.DatasetType.OCR_LICENSE_PLATES.value,
                "Automatically collected license plate corrections from production"
            )

            if not dataset:
                result['error'] = "Failed to create/get feedback dataset"
                return result

            # Create training example
            training_example = self._create_vehicle_entry_example(
                dataset=dataset,
                vehicle_entry=vehicle_entry,
                corrected_license_plate=corrected_license_plate,
                corrected_by=corrected_by,
                correction_type=correction_type
            )

            if training_example:
                result['success'] = True
                result['training_example'] = training_example
                result['dataset'] = dataset

                logger.info(
                    f"Captured vehicle entry feedback: {vehicle_entry.id} -> {corrected_license_plate}"
                )
            else:
                result['error'] = "Failed to create training example"

        except Exception as e:
            logger.error(f"Error capturing vehicle entry feedback: {str(e)}", exc_info=True)
            result['error'] = f"Feedback capture failed: {str(e)}"

        return result

    def batch_import_uncertain_predictions(
        self,
        source_model: str,  # 'meter_readings' or 'vehicle_entries'
        days_back: int = 7,
        max_examples: int = 100
    ) -> Dict[str, Any]:
        """
        Batch import uncertain predictions from production for labeling.

        Args:
            source_model: Source model type to import from
            days_back: Number of days to look back
            max_examples: Maximum examples to import

        Returns:
            Batch import results
        """
        result = {
            'success': False,
            'imported': 0,
            'skipped': 0,
            'errors': [],
            'dataset': None
        }

        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            if source_model == 'meter_readings':
                result = self._import_uncertain_meter_readings(cutoff_date, max_examples)
            elif source_model == 'vehicle_entries':
                result = self._import_uncertain_vehicle_entries(cutoff_date, max_examples)
            else:
                result['error'] = f"Unknown source model: {source_model}"
                return result

            logger.info(
                f"Batch imported {result['imported']} uncertain {source_model} "
                f"({result['skipped']} skipped)"
            )

        except Exception as e:
            logger.error(f"Error in batch import: {str(e)}", exc_info=True)
            result['error'] = f"Batch import failed: {str(e)}"

        return result

    def create_feedback_labeling_tasks(
        self,
        dataset: TrainingDataset,
        assignee: People,
        batch_size: int = None
    ) -> Dict[str, Any]:
        """
        Create labeling tasks from feedback examples.

        Args:
            dataset: Feedback dataset with examples
            assignee: Person to assign labeling tasks
            batch_size: Size of each labeling batch

        Returns:
            Task creation results
        """
        result = {
            'success': False,
            'tasks_created': 0,
            'examples_assigned': 0,
            'error': None
        }

        try:
            batch_size = batch_size or self.batch_size

            # Get unlabeled feedback examples prioritized by uncertainty
            unlabeled_examples = TrainingExample.objects.filter(
                dataset=dataset,
                is_labeled=False,
                selected_for_labeling=False
            ).order_by('-uncertainty_score', '-labeling_priority', '-created_at')

            if not unlabeled_examples.exists():
                result['error'] = "No unlabeled examples available"
                return result

            # Create batched labeling tasks
            examples_list = list(unlabeled_examples)
            task_batches = [
                examples_list[i:i + batch_size]
                for i in range(0, len(examples_list), batch_size)
            ]

            with transaction.atomic():
                for i, batch in enumerate(task_batches):
                    task = LabelingTask.objects.create(
                        dataset=dataset,
                        task_type=LabelingTask.TaskType.CORRECTION.value,
                        assigned_to=assignee,
                        priority=8,  # High priority for feedback corrections
                        instructions=f"Review and correct production feedback examples. "
                                   f"These are cases where the AI was uncertain or made errors.",
                        total_examples=len(batch),
                        due_date=timezone.now() + timedelta(days=3)  # Shorter deadline
                    )

                    # Add examples to task
                    task.examples.set(batch)

                    # Mark examples as selected
                    TrainingExample.objects.filter(
                        id__in=[ex.id for ex in batch]
                    ).update(
                        selected_for_labeling=True,
                        labeling_status=TrainingExample.LabelingStatus.IN_PROGRESS.value
                    )

                    result['tasks_created'] += 1
                    result['examples_assigned'] += len(batch)

                result['success'] = True

                logger.info(
                    f"Created {result['tasks_created']} feedback labeling tasks "
                    f"with {result['examples_assigned']} examples"
                )

        except Exception as e:
            logger.error(f"Error creating feedback labeling tasks: {str(e)}", exc_info=True)
            result['error'] = f"Task creation failed: {str(e)}"

        return result

    def analyze_feedback_patterns(
        self,
        dataset: TrainingDataset,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze patterns in production feedback to identify systematic issues.

        Args:
            dataset: Feedback dataset to analyze
            days_back: Analysis period in days

        Returns:
            Analysis results and recommendations
        """
        result = {
            'success': False,
            'analysis': {},
            'patterns': [],
            'recommendations': [],
            'error': None
        }

        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            # Get feedback examples from the period
            feedback_examples = TrainingExample.objects.filter(
                dataset=dataset,
                created_at__gte=cutoff_date,
                example_type=TrainingExample.ExampleType.PRODUCTION.value
            )

            if not feedback_examples.exists():
                result['error'] = "No feedback examples in the specified period"
                return result

            # Analyze error patterns
            analysis = {
                'total_feedback': feedback_examples.count(),
                'avg_uncertainty': feedback_examples.aggregate(
                    avg=Avg('uncertainty_score')
                )['avg'] or 0,
                'correction_types': self._analyze_correction_types(feedback_examples),
                'temporal_patterns': self._analyze_temporal_patterns(feedback_examples),
                'quality_distribution': self._analyze_quality_distribution(feedback_examples)
            }

            # Identify patterns
            patterns = self._identify_feedback_patterns(analysis)

            # Generate recommendations
            recommendations = self._generate_feedback_recommendations(patterns, analysis)

            result['analysis'] = analysis
            result['patterns'] = patterns
            result['recommendations'] = recommendations
            result['success'] = True

            logger.info(f"Analyzed {analysis['total_feedback']} feedback examples")

        except Exception as e:
            logger.error(f"Error analyzing feedback patterns: {str(e)}", exc_info=True)
            result['error'] = f"Analysis failed: {str(e)}"

        return result

    def _get_or_create_feedback_dataset(
        self,
        dataset_key: str,
        dataset_type: str,
        description: str
    ) -> Optional[TrainingDataset]:
        """Get or create a feedback dataset."""
        try:
            dataset_name = self.auto_dataset_names[dataset_key]

            dataset, created = TrainingDataset.objects.get_or_create(
                name=dataset_name,
                defaults={
                    'dataset_type': dataset_type,
                    'description': description,
                    'status': TrainingDataset.Status.ACTIVE.value,
                    'created_by_id': 1,  # System user
                    'metadata': {
                        'auto_generated': True,
                        'source': 'production_feedback',
                        'dataset_key': dataset_key
                    }
                }
            )

            if created:
                logger.info(f"Created new feedback dataset: {dataset_name}")

            return dataset

        except Exception as e:
            logger.error(f"Error getting/creating feedback dataset: {str(e)}")
            return None

    def _create_meter_reading_example(
        self,
        dataset: TrainingDataset,
        meter_reading: MeterReading,
        corrected_value: str,
        corrected_by: People,
        correction_type: str
    ) -> Optional[TrainingExample]:
        """Create training example from meter reading correction."""
        try:
            # Check if already exists
            if TrainingExample.objects.filter(
                source_system='meter_readings',
                source_id=str(meter_reading.id)
            ).exists():
                return None

            return TrainingExample.objects.create(
                dataset=dataset,
                image_path=meter_reading.image_path or '',
                image_hash=meter_reading.image_hash or '',
                ground_truth_text=corrected_value,
                ground_truth_data={
                    'original_reading': str(meter_reading.reading_value),
                    'corrected_reading': corrected_value,
                    'meter_type': meter_reading.meter_type,
                    'unit': meter_reading.unit,
                    'correction_type': correction_type
                },
                example_type=TrainingExample.ExampleType.PRODUCTION.value,
                uncertainty_score=1.0 - (meter_reading.confidence_score or 0.5),
                source_system='meter_readings',
                source_id=str(meter_reading.id),
                capture_metadata={
                    'original_confidence': meter_reading.confidence_score,
                    'corrected_by': corrected_by.peoplename,
                    'correction_timestamp': timezone.now().isoformat(),
                    'meter_type': meter_reading.meter_type,
                    'asset_id': meter_reading.asset.id if meter_reading.asset else None
                },
                selected_for_labeling=True,
                labeling_priority=int((1.0 - (meter_reading.confidence_score or 0.5)) * 10)
            )

        except Exception as e:
            logger.error(f"Error creating meter reading example: {str(e)}")
            return None

    def _create_vehicle_entry_example(
        self,
        dataset: TrainingDataset,
        vehicle_entry: VehicleEntry,
        corrected_license_plate: str,
        corrected_by: People,
        correction_type: str
    ) -> Optional[TrainingExample]:
        """Create training example from vehicle entry correction."""
        try:
            # Check if already exists
            if TrainingExample.objects.filter(
                source_system='vehicle_entries',
                source_id=str(vehicle_entry.id)
            ).exists():
                return None

            return TrainingExample.objects.create(
                dataset=dataset,
                image_path=vehicle_entry.image_path or '',
                image_hash=vehicle_entry.image_hash or '',
                ground_truth_text=corrected_license_plate,
                ground_truth_data={
                    'original_license_plate': vehicle_entry.license_plate,
                    'corrected_license_plate': corrected_license_plate,
                    'entry_type': vehicle_entry.entry_type,
                    'correction_type': correction_type
                },
                example_type=TrainingExample.ExampleType.PRODUCTION.value,
                uncertainty_score=1.0 - (vehicle_entry.confidence_score or 0.5),
                source_system='vehicle_entries',
                source_id=str(vehicle_entry.id),
                capture_metadata={
                    'original_confidence': vehicle_entry.confidence_score,
                    'corrected_by': corrected_by.peoplename,
                    'correction_timestamp': timezone.now().isoformat(),
                    'entry_type': vehicle_entry.entry_type,
                    'gate_location': vehicle_entry.gate_location.locationname if vehicle_entry.gate_location else None
                },
                selected_for_labeling=True,
                labeling_priority=int((1.0 - (vehicle_entry.confidence_score or 0.5)) * 10)
            )

        except Exception as e:
            logger.error(f"Error creating vehicle entry example: {str(e)}")
            return None

    def _import_uncertain_meter_readings(
        self,
        cutoff_date: datetime,
        max_examples: int
    ) -> Dict[str, Any]:
        """Import uncertain meter readings for training."""
        result = {'success': False, 'imported': 0, 'skipped': 0, 'errors': []}

        try:
            # Get uncertain meter readings
            uncertain_readings = MeterReading.objects.filter(
                created_at__gte=cutoff_date,
                confidence_score__lt=self.confidence_threshold,
                status=MeterReading.ReadingStatus.FLAGGED.value
            ).order_by('-created_at')[:max_examples]

            dataset = self._get_or_create_feedback_dataset(
                'meter_readings',
                TrainingDataset.DatasetType.OCR_METERS.value,
                "Uncertain meter readings from production"
            )

            for reading in uncertain_readings:
                try:
                    # Create training example for uncertain reading
                    example = TrainingExample.objects.create(
                        dataset=dataset,
                        image_path=reading.image_path or '',
                        image_hash=reading.image_hash or '',
                        ground_truth_text='',  # Needs labeling
                        example_type=TrainingExample.ExampleType.PRODUCTION.value,
                        uncertainty_score=1.0 - (reading.confidence_score or 0.5),
                        source_system='meter_readings',
                        source_id=str(reading.id),
                        capture_metadata={
                            'confidence_score': reading.confidence_score,
                            'meter_type': reading.meter_type,
                            'raw_ocr_text': reading.raw_ocr_text
                        },
                        selected_for_labeling=True
                    )
                    result['imported'] += 1

                except Exception as e:
                    result['skipped'] += 1
                    result['errors'].append(f"Reading {reading.id}: {str(e)}")

            result['success'] = True
            result['dataset'] = dataset

        except Exception as e:
            result['errors'].append(f"Import failed: {str(e)}")

        return result

    def _import_uncertain_vehicle_entries(
        self,
        cutoff_date: datetime,
        max_examples: int
    ) -> Dict[str, Any]:
        """Import uncertain vehicle entries for training."""
        result = {'success': False, 'imported': 0, 'skipped': 0, 'errors': []}

        try:
            # Get uncertain vehicle entries
            uncertain_entries = VehicleEntry.objects.filter(
                created_at__gte=cutoff_date,
                confidence_score__lt=self.confidence_threshold,
                status=VehicleEntry.Status.FLAGGED.value
            ).order_by('-created_at')[:max_examples]

            dataset = self._get_or_create_feedback_dataset(
                'vehicle_entries',
                TrainingDataset.DatasetType.OCR_LICENSE_PLATES.value,
                "Uncertain vehicle entries from production"
            )

            for entry in uncertain_entries:
                try:
                    # Create training example for uncertain entry
                    example = TrainingExample.objects.create(
                        dataset=dataset,
                        image_path=entry.image_path or '',
                        image_hash=entry.image_hash or '',
                        ground_truth_text='',  # Needs labeling
                        example_type=TrainingExample.ExampleType.PRODUCTION.value,
                        uncertainty_score=1.0 - (entry.confidence_score or 0.5),
                        source_system='vehicle_entries',
                        source_id=str(entry.id),
                        capture_metadata={
                            'confidence_score': entry.confidence_score,
                            'entry_type': entry.entry_type,
                            'raw_ocr_text': entry.raw_ocr_text
                        },
                        selected_for_labeling=True
                    )
                    result['imported'] += 1

                except Exception as e:
                    result['skipped'] += 1
                    result['errors'].append(f"Entry {entry.id}: {str(e)}")

            result['success'] = True
            result['dataset'] = dataset

        except Exception as e:
            result['errors'].append(f"Import failed: {str(e)}")

        return result

    def _analyze_correction_types(self, examples: models.QuerySet) -> Dict[str, int]:
        """Analyze types of corrections in feedback examples."""
        correction_types = {}
        for example in examples:
            correction_type = example.ground_truth_data.get('correction_type', 'unknown')
            correction_types[correction_type] = correction_types.get(correction_type, 0) + 1
        return correction_types

    def _analyze_temporal_patterns(self, examples: models.QuerySet) -> Dict[str, Any]:
        """Analyze temporal patterns in feedback."""
        # Group by day and count
        daily_counts = examples.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(count=Count('id')).order_by('day')

        return {
            'daily_feedback': list(daily_counts),
            'total_days': len(daily_counts),
            'avg_daily_feedback': sum(item['count'] for item in daily_counts) / max(len(daily_counts), 1)
        }

    def _analyze_quality_distribution(self, examples: models.QuerySet) -> Dict[str, Any]:
        """Analyze quality score distribution."""
        quality_examples = examples.filter(quality_score__isnull=False)
        if not quality_examples.exists():
            return {'message': 'No quality scores available'}

        return {
            'avg_quality': quality_examples.aggregate(avg=Avg('quality_score'))['avg'],
            'quality_count': quality_examples.count(),
            'low_quality_count': quality_examples.filter(quality_score__lt=0.6).count()
        }

    def _identify_feedback_patterns(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify patterns in feedback data."""
        patterns = []

        # High volume pattern
        if analysis['total_feedback'] > 100:
            patterns.append("High volume of production feedback indicates model uncertainty")

        # Quality patterns
        quality_dist = analysis.get('quality_distribution', {})
        if quality_dist.get('low_quality_count', 0) > 10:
            patterns.append("High number of low-quality labels requiring review")

        # Temporal patterns
        temporal = analysis.get('temporal_patterns', {})
        if temporal.get('avg_daily_feedback', 0) > 10:
            patterns.append("Consistent daily feedback indicates systematic model issues")

        return patterns

    def _generate_feedback_recommendations(
        self,
        patterns: List[str],
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on feedback analysis."""
        recommendations = []

        if "High volume of production feedback" in patterns:
            recommendations.append(
                "Consider retraining model with accumulated feedback data"
            )

        if "High number of low-quality labels" in patterns:
            recommendations.append(
                "Implement additional quality assurance for labeling tasks"
            )

        if "Consistent daily feedback" in patterns:
            recommendations.append(
                "Investigate root causes of model uncertainty in production environment"
            )

        if analysis['total_feedback'] > 50:
            recommendations.append(
                f"Ready for model retraining with {analysis['total_feedback']} feedback examples"
            )

        return recommendations


# Factory function
def get_feedback_integration_service() -> FeedbackIntegrationService:
    """Factory function to get feedback integration service instance."""
    return FeedbackIntegrationService()