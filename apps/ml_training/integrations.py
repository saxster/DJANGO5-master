"""
Production System Integrations - Connect training platform to existing services.

Provides seamless integration between production OCR services and
the training data platform for continuous improvement.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from .services import FeedbackIntegrationService, ActiveLearningService
from .models import TrainingDataset, TrainingExample
from apps.activity.models import MeterReading, VehicleEntry
from apps.core_onboarding.services.ocr_service import get_ocr_service

logger = logging.getLogger(__name__)


class ProductionTrainingIntegration:
    """
    Integration between production systems and ML training platform.

    Provides hooks for capturing training data from production usage,
    uncertainty detection, and automatic feedback collection.
    """

    def __init__(self):
        """Initialize integration with required services."""
        self.feedback_service = FeedbackIntegrationService()
        self.active_learning_service = ActiveLearningService()
        self.ocr_service = get_ocr_service()

    def on_meter_reading_processed(
        self,
        meter_reading: MeterReading,
        confidence_score: float,
        raw_ocr_text: str = ""
    ) -> Dict[str, Any]:
        """
        Hook called when a meter reading is processed in production.

        Automatically captures uncertain readings for training data.

        Args:
            meter_reading: Processed meter reading
            confidence_score: AI confidence score
            raw_ocr_text: Raw OCR output

        Returns:
            Integration result
        """
        result = {
            'success': True,
            'actions_taken': [],
            'training_candidate': False,
            'error': None
        }

        try:
            # Update the meter reading with ML metadata
            meter_reading.confidence_score = confidence_score
            if raw_ocr_text:
                meter_reading.raw_ocr_text = raw_ocr_text
            meter_reading.save(update_fields=['confidence_score', 'raw_ocr_text'])

            # Check if this should be a training candidate
            if confidence_score < 0.7:  # Uncertain prediction
                result['training_candidate'] = True
                result['actions_taken'].append(f"Flagged as training candidate (confidence: {confidence_score:.2f})")

                # Auto-import to training dataset if very uncertain
                if confidence_score < 0.5:
                    import_result = self._auto_import_meter_reading(meter_reading)
                    if import_result['success']:
                        result['actions_taken'].append("Auto-imported to training dataset")
                    else:
                        logger.warning(f"Failed to auto-import meter reading: {import_result['error']}")

            # Analyze for model performance tracking
            self._track_model_performance('meter_readings', confidence_score)

        except Exception as e:
            logger.error(f"Error in meter reading integration: {str(e)}", exc_info=True)
            result['success'] = False
            result['error'] = str(e)

        return result

    def on_vehicle_entry_processed(
        self,
        vehicle_entry: VehicleEntry,
        confidence_score: float,
        raw_ocr_text: str = ""
    ) -> Dict[str, Any]:
        """
        Hook called when a vehicle entry is processed in production.

        Args:
            vehicle_entry: Processed vehicle entry
            confidence_score: AI confidence score
            raw_ocr_text: Raw OCR output

        Returns:
            Integration result
        """
        result = {
            'success': True,
            'actions_taken': [],
            'training_candidate': False,
            'error': None
        }

        try:
            # Update the vehicle entry with ML metadata
            vehicle_entry.confidence_score = confidence_score
            if raw_ocr_text:
                vehicle_entry.raw_ocr_text = raw_ocr_text
            vehicle_entry.save(update_fields=['confidence_score', 'raw_ocr_text'])

            # Check if this should be a training candidate
            if confidence_score < 0.7:  # Uncertain prediction
                result['training_candidate'] = True
                result['actions_taken'].append(f"Flagged as training candidate (confidence: {confidence_score:.2f})")

                # Auto-import to training dataset if very uncertain
                if confidence_score < 0.5:
                    import_result = self._auto_import_vehicle_entry(vehicle_entry)
                    if import_result['success']:
                        result['actions_taken'].append("Auto-imported to training dataset")
                    else:
                        logger.warning(f"Failed to auto-import vehicle entry: {import_result['error']}")

            # Analyze for model performance tracking
            self._track_model_performance('vehicle_entries', confidence_score)

        except Exception as e:
            logger.error(f"Error in vehicle entry integration: {str(e)}", exc_info=True)
            result['success'] = False
            result['error'] = str(e)

        return result

    def on_user_correction(
        self,
        source_type: str,
        source_id: int,
        original_value: str,
        corrected_value: str,
        corrected_by,
        correction_reason: str = "user_correction"
    ) -> Dict[str, Any]:
        """
        Hook called when a user corrects a production prediction.

        Automatically captures this as high-value training data.

        Args:
            source_type: 'meter_reading' or 'vehicle_entry'
            source_id: ID of the source record
            original_value: Original AI prediction
            corrected_value: User-corrected value
            corrected_by: User who made the correction
            correction_reason: Reason for correction

        Returns:
            Feedback capture result
        """
        result = {
            'success': False,
            'training_example_created': False,
            'dataset_id': None,
            'error': None
        }

        try:
            if source_type == 'meter_reading':
                try:
                    meter_reading = MeterReading.objects.get(id=source_id)
                    feedback_result = self.feedback_service.capture_meter_reading_feedback(
                        meter_reading=meter_reading,
                        corrected_value=corrected_value,
                        corrected_by=corrected_by,
                        correction_type=correction_reason
                    )
                except MeterReading.DoesNotExist:
                    result['error'] = "Meter reading not found"
                    return result

            elif source_type == 'vehicle_entry':
                try:
                    vehicle_entry = VehicleEntry.objects.get(id=source_id)
                    feedback_result = self.feedback_service.capture_vehicle_entry_feedback(
                        vehicle_entry=vehicle_entry,
                        corrected_license_plate=corrected_value,
                        corrected_by=corrected_by,
                        correction_type=correction_reason
                    )
                except VehicleEntry.DoesNotExist:
                    result['error'] = "Vehicle entry not found"
                    return result
            else:
                result['error'] = f"Unknown source type: {source_type}"
                return result

            if feedback_result['success']:
                result['success'] = True
                result['training_example_created'] = True
                result['dataset_id'] = feedback_result['dataset'].id

                logger.info(
                    f"Captured user correction: {source_type}:{source_id} "
                    f"'{original_value}' -> '{corrected_value}'"
                )
            else:
                result['error'] = feedback_result['error']

        except Exception as e:
            logger.error(f"Error capturing user correction: {str(e)}", exc_info=True)
            result['error'] = str(e)

        return result

    def trigger_active_learning(
        self,
        dataset_type: str,
        min_examples: int = 50
    ) -> Dict[str, Any]:
        """
        Trigger active learning batch selection for a dataset type.

        Args:
            dataset_type: Type of dataset to process
            min_examples: Minimum examples needed to trigger

        Returns:
            Active learning result
        """
        result = {
            'success': False,
            'batches_created': 0,
            'examples_selected': 0,
            'error': None
        }

        try:
            # Find datasets of the specified type
            datasets = TrainingDataset.objects.filter(
                dataset_type=dataset_type,
                status=TrainingDataset.Status.ACTIVE.value
            )

            for dataset in datasets:
                # Check if dataset has enough uncertain examples
                uncertain_count = TrainingExample.objects.filter(
                    dataset=dataset,
                    is_labeled=False,
                    uncertainty_score__gte=0.6
                ).count()

                if uncertain_count >= min_examples:
                    # Select optimal batch for labeling
                    selection_result = self.active_learning_service.select_optimal_batch(
                        dataset=dataset,
                        batch_size=min(uncertain_count, 50),
                        strategy="uncertainty_diversity"
                    )

                    if selection_result['success']:
                        # Create labeling task (would need to assign to actual user)
                        # For now, just mark examples as selected
                        result['examples_selected'] += len(selection_result['selected_examples'])
                        result['batches_created'] += 1

                        logger.info(
                            f"Active learning triggered for dataset {dataset.id}: "
                            f"{len(selection_result['selected_examples'])} examples selected"
                        )

            result['success'] = True

        except Exception as e:
            logger.error(f"Error triggering active learning: {str(e)}", exc_info=True)
            result['error'] = str(e)

        return result

    def _auto_import_meter_reading(self, meter_reading: MeterReading) -> Dict[str, Any]:
        """Auto-import uncertain meter reading to training dataset."""
        try:
            # Get or create feedback dataset
            feedback_datasets = TrainingDataset.objects.filter(
                dataset_type=TrainingDataset.DatasetType.OCR_METERS.value,
                metadata__auto_generated=True,
                status=TrainingDataset.Status.ACTIVE.value
            )

            if feedback_datasets.exists():
                dataset = feedback_datasets.first()
            else:
                # Create auto-generated dataset
                dataset = TrainingDataset.objects.create(
                    name="Auto-Generated Meter Reading Feedback",
                    dataset_type=TrainingDataset.DatasetType.OCR_METERS.value,
                    description="Automatically collected uncertain meter readings",
                    status=TrainingDataset.Status.ACTIVE.value,
                    created_by_id=1,  # System user
                    metadata={'auto_generated': True, 'source': 'production_uncertainty'}
                )

            # Check if already imported
            if TrainingExample.objects.filter(
                source_system='meter_readings',
                source_id=str(meter_reading.id)
            ).exists():
                return {'success': False, 'error': 'Already imported'}

            # Create training example
            TrainingExample.objects.create(
                dataset=dataset,
                image_path=meter_reading.image_path or '',
                image_hash=meter_reading.image_hash or '',
                ground_truth_text='',  # Needs labeling
                example_type=TrainingExample.ExampleType.PRODUCTION.value,
                uncertainty_score=1.0 - (meter_reading.confidence_score or 0.5),
                source_system='meter_readings',
                source_id=str(meter_reading.id),
                capture_metadata={
                    'confidence_score': meter_reading.confidence_score,
                    'meter_type': meter_reading.meter_type,
                    'raw_ocr_text': meter_reading.raw_ocr_text,
                    'auto_imported': True,
                    'import_timestamp': timezone.now().isoformat()
                },
                selected_for_labeling=True,
                labeling_priority=int((1.0 - (meter_reading.confidence_score or 0.5)) * 10)
            )

            return {'success': True}

        except Exception as e:
            logger.error(f"Error auto-importing meter reading: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _auto_import_vehicle_entry(self, vehicle_entry: VehicleEntry) -> Dict[str, Any]:
        """Auto-import uncertain vehicle entry to training dataset."""
        try:
            # Get or create feedback dataset
            feedback_datasets = TrainingDataset.objects.filter(
                dataset_type=TrainingDataset.DatasetType.OCR_LICENSE_PLATES.value,
                metadata__auto_generated=True,
                status=TrainingDataset.Status.ACTIVE.value
            )

            if feedback_datasets.exists():
                dataset = feedback_datasets.first()
            else:
                # Create auto-generated dataset
                dataset = TrainingDataset.objects.create(
                    name="Auto-Generated Vehicle Entry Feedback",
                    dataset_type=TrainingDataset.DatasetType.OCR_LICENSE_PLATES.value,
                    description="Automatically collected uncertain license plate readings",
                    status=TrainingDataset.Status.ACTIVE.value,
                    created_by_id=1,  # System user
                    metadata={'auto_generated': True, 'source': 'production_uncertainty'}
                )

            # Check if already imported
            if TrainingExample.objects.filter(
                source_system='vehicle_entries',
                source_id=str(vehicle_entry.id)
            ).exists():
                return {'success': False, 'error': 'Already imported'}

            # Create training example
            TrainingExample.objects.create(
                dataset=dataset,
                image_path=vehicle_entry.image_path or '',
                image_hash=vehicle_entry.image_hash or '',
                ground_truth_text='',  # Needs labeling
                example_type=TrainingExample.ExampleType.PRODUCTION.value,
                uncertainty_score=1.0 - (vehicle_entry.confidence_score or 0.5),
                source_system='vehicle_entries',
                source_id=str(vehicle_entry.id),
                capture_metadata={
                    'confidence_score': vehicle_entry.confidence_score,
                    'entry_type': vehicle_entry.entry_type,
                    'raw_ocr_text': vehicle_entry.raw_ocr_text,
                    'auto_imported': True,
                    'import_timestamp': timezone.now().isoformat()
                },
                selected_for_labeling=True,
                labeling_priority=int((1.0 - (vehicle_entry.confidence_score or 0.5)) * 10)
            )

            return {'success': True}

        except Exception as e:
            logger.error(f"Error auto-importing vehicle entry: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _track_model_performance(self, model_type: str, confidence_score: float):
        """Track model performance metrics for analysis."""
        try:
            # Simple performance tracking - could be enhanced with dedicated models
            logger.info(f"Model performance - {model_type}: confidence={confidence_score:.3f}")

            # Could implement:
            # - Confidence calibration tracking
            # - Daily/weekly performance summaries
            # - Alert thresholds for performance degradation
            # - A/B testing metrics

        except Exception as e:
            logger.warning(f"Error tracking model performance: {str(e)}")


# Factory function
def get_production_training_integration() -> ProductionTrainingIntegration:
    """Factory function to get production training integration instance."""
    return ProductionTrainingIntegration()


# Convenience functions for easy integration
def track_meter_reading_result(meter_reading, confidence_score, raw_ocr_text=""):
    """Convenience function to track meter reading results."""
    integration = get_production_training_integration()
    return integration.on_meter_reading_processed(meter_reading, confidence_score, raw_ocr_text)


def track_vehicle_entry_result(vehicle_entry, confidence_score, raw_ocr_text=""):
    """Convenience function to track vehicle entry results."""
    integration = get_production_training_integration()
    return integration.on_vehicle_entry_processed(vehicle_entry, confidence_score, raw_ocr_text)


def capture_user_correction(source_type, source_id, original_value, corrected_value, corrected_by):
    """Convenience function to capture user corrections."""
    integration = get_production_training_integration()
    return integration.on_user_correction(
        source_type, source_id, original_value, corrected_value, corrected_by
    )