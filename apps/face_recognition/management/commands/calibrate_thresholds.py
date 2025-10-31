"""
Management command for empirical threshold calibration

This command analyzes face recognition performance on a dataset and
recommends optimal thresholds based on ROC analysis and Equal Error Rate (EER).
"""

import os
import json
import logging
import numpy as np
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.face_recognition.models import (
    FaceRecognitionModel,
    FaceEmbedding,
    FaceVerificationLog,
)
from apps.face_recognition.services import get_face_recognition_service, VerificationEngine
from apps.core.exceptions import LLMServiceException
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from typing import List, Dict, Any


User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calibrate face recognition thresholds based on empirical data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset-path',
            type=str,
            help='Path to calibration dataset directory'
        )
        parser.add_argument(
            '--model-type',
            type=str,
            default='FACENET512',
            choices=['FACENET512', 'ARCFACE', 'INSIGHTFACE', 'ENSEMBLE'],
            help='Model type to calibrate'
        )
        parser.add_argument(
            '--engine',
            type=str,
            default='deepface',
            choices=['deepface', 'enhanced'],
            help='Engine to use for calibration'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=100,
            help='Minimum number of samples required for calibration'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file for calibration results (JSON)'
        )
        parser.add_argument(
            '--apply-results',
            action='store_true',
            help='Apply calibration results to database models'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform calibration but do not save results'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        self.options = options
        self.setup_logging()

        try:
            # Validate input parameters
            self.validate_options()

            # Get or create face recognition model
            face_model = self.get_face_model()

            # Collect calibration data
            if options['dataset_path']:
                calibration_data = self.collect_dataset_calibration_data(
                    options['dataset_path']
                )
            else:
                calibration_data = self.collect_historical_calibration_data()

            # Analyze performance and calculate optimal thresholds
            analysis_results = self.analyze_performance(calibration_data)

            # Calculate ROC and EER
            roc_results = self.calculate_roc_and_eer(calibration_data)

            # Combine results
            calibration_results = {
                'model_type': options['model_type'],
                'engine': options['engine'],
                'timestamp': timezone.now().isoformat(),
                'sample_count': len(calibration_data),
                'analysis': analysis_results,
                'roc_analysis': roc_results,
                'recommendations': self.generate_recommendations(analysis_results, roc_results)
            }

            # Output results
            self.output_results(calibration_results)

            # Apply results if requested
            if options['apply_results'] and not options['dry_run']:
                self.apply_calibration_results(face_model, calibration_results)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Threshold calibration completed successfully. "
                    f"Processed {len(calibration_data)} samples."
                )
            )

        except (AttributeError, ConnectionError, FileNotFoundError, IOError, LLMServiceException, OSError, PermissionError, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.exception("Error during threshold calibration")
            raise CommandError(f"Calibration failed: {str(e)}")

    def setup_logging(self):
        """Setup logging based on verbosity"""
        if self.options.get('verbose'):
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def validate_options(self):
        """Validate command options"""
        dataset_path = self.options.get('dataset_path')
        if dataset_path and not os.path.exists(dataset_path):
            raise CommandError(f"Dataset path does not exist: {dataset_path}")

        if dataset_path and not os.path.isdir(dataset_path):
            raise CommandError(f"Dataset path is not a directory: {dataset_path}")

    def get_face_model(self) -> FaceRecognitionModel:
        """Get or create the face recognition model"""
        try:
            face_model = FaceRecognitionModel.objects.filter(
                model_type=self.options['model_type'],
                status='ACTIVE'
            ).first()

            if not face_model:
                # Create new model for calibration
                face_model = FaceRecognitionModel.objects.create(
                    name=f'Calibrated_{self.options["model_type"]}',
                    model_type=self.options['model_type'],
                    version='1.0',
                    status='ACTIVE'
                )
                self.stdout.write(
                    self.style.WARNING(f"Created new model: {face_model.name}")
                )

            return face_model

        except (AttributeError, ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValidationError, ValueError) as e:
            raise CommandError(f"Error getting face model: {str(e)}")

    def collect_dataset_calibration_data(self, dataset_path: str) -> List[Dict[str, Any]]:
        """
        Collect calibration data from a dataset directory

        Expected structure:
        dataset_path/
        ├── positive_pairs/     # Images that should match
        │   ├── user1_img1.jpg
        │   ├── user1_img2.jpg
        │   └── ...
        └── negative_pairs/     # Images that should NOT match
            ├── user1_vs_user2/
            │   ├── user1.jpg
            │   └── user2.jpg
            └── ...
        """
        calibration_data = []
        dataset_path = Path(dataset_path)

        # Process positive pairs (same person)
        positive_path = dataset_path / 'positive_pairs'
        if positive_path.exists():
            positive_data = self._process_positive_pairs(positive_path)
            calibration_data.extend(positive_data)
            self.stdout.write(f"Collected {len(positive_data)} positive samples")

        # Process negative pairs (different people)
        negative_path = dataset_path / 'negative_pairs'
        if negative_path.exists():
            negative_data = self._process_negative_pairs(negative_path)
            calibration_data.extend(negative_data)
            self.stdout.write(f"Collected {len(negative_data)} negative samples")

        if len(calibration_data) < self.options['min_samples']:
            raise CommandError(
                f"Insufficient calibration data. Got {len(calibration_data)}, "
                f"need at least {self.options['min_samples']}"
            )

        return calibration_data

    def _process_positive_pairs(self, positive_path: Path) -> List[Dict[str, Any]]:
        """Process positive pairs (same person)"""
        positive_data = []
        face_service = get_face_recognition_service(
            VerificationEngine.ENHANCED if self.options['engine'] == 'enhanced'
            else VerificationEngine.DEEPFACE
        )

        # Group images by user (based on filename prefix)
        user_images = defaultdict(list)
        for img_file in positive_path.glob('*.jpg'):
            user_id = img_file.stem.split('_')[0]
            user_images[user_id].append(img_file)

        # Create positive pairs for each user
        for user_id, images in user_images.items():
            if len(images) < 2:
                continue

            for i in range(len(images)):
                for j in range(i + 1, len(images)):
                    try:
                        # Use a mock user ID for calibration
                        result = face_service._verify_with_deepface(
                            user_id=1,  # Mock user ID
                            image_path=str(images[j]),
                            face_model=self.get_face_model(),
                            correlation_id=f"calib_pos_{user_id}_{i}_{j}"
                        )

                        positive_data.append({
                            'image1': str(images[i]),
                            'image2': str(images[j]),
                            'ground_truth': True,  # Should match
                            'distance': result.distance,
                            'similarity_score': result.similarity_score,
                            'user_id': user_id
                        })

                    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError) as e:
                        logger.warning(f"Error processing positive pair {images[i]} vs {images[j]}: {e}")

        return positive_data

    def _process_negative_pairs(self, negative_path: Path) -> List[Dict[str, Any]]:
        """Process negative pairs (different people)"""
        negative_data = []
        face_service = get_face_recognition_service(
            VerificationEngine.ENHANCED if self.options['engine'] == 'enhanced'
            else VerificationEngine.DEEPFACE
        )

        # Process pairs in subdirectories
        for pair_dir in negative_path.iterdir():
            if not pair_dir.is_dir():
                continue

            images = list(pair_dir.glob('*.jpg'))
            if len(images) != 2:
                logger.warning(f"Expected exactly 2 images in {pair_dir}, found {len(images)}")
                continue

            try:
                result = face_service._verify_with_deepface(
                    user_id=1,  # Mock user ID
                    image_path=str(images[1]),
                    face_model=self.get_face_model(),
                    correlation_id=f"calib_neg_{pair_dir.name}"
                )

                negative_data.append({
                    'image1': str(images[0]),
                    'image2': str(images[1]),
                    'ground_truth': False,  # Should NOT match
                    'distance': result.distance,
                    'similarity_score': result.similarity_score,
                    'pair_name': pair_dir.name
                })

            except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError) as e:
                logger.warning(f"Error processing negative pair in {pair_dir}: {e}")

        return negative_data

    def collect_historical_calibration_data(self) -> List[Dict[str, Any]]:
        """Collect calibration data from historical verification logs"""
        try:
            # Get recent verification logs
            logs = FaceVerificationLog.objects.filter(
                verification_model__model_type=self.options['model_type'],
                result__in=['SUCCESS', 'FAILED'],
                similarity_score__isnull=False,
                verification_timestamp__gte=timezone.now() - timezone.timedelta(days=30)
            ).select_related('verification_model')

            calibration_data = []
            for log in logs:
                calibration_data.append({
                    'log_id': log.id,
                    'ground_truth': log.result == 'SUCCESS',
                    'distance': 1.0 - log.similarity_score if log.similarity_score else None,
                    'similarity_score': log.similarity_score,
                    'confidence_score': log.confidence_score,
                    'user_id': log.user_id,
                    'processing_time': log.processing_time_ms
                })

            self.stdout.write(f"Collected {len(calibration_data)} historical samples")

            if len(calibration_data) < self.options['min_samples']:
                raise CommandError(
                    f"Insufficient historical data. Got {len(calibration_data)}, "
                    f"need at least {self.options['min_samples']}. "
                    f"Consider providing a calibration dataset with --dataset-path"
                )

            return calibration_data

        except (AttributeError, ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValidationError, ValueError) as e:
            raise CommandError(f"Error collecting historical data: {str(e)}")

    def analyze_performance(self, calibration_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance across different threshold values"""
        distances = [item['distance'] for item in calibration_data if item['distance'] is not None]
        ground_truths = [item['ground_truth'] for item in calibration_data if item['distance'] is not None]

        if len(distances) != len(ground_truths):
            raise CommandError("Mismatch between distance and ground truth data")

        distances = np.array(distances)
        ground_truths = np.array(ground_truths)

        # Test threshold values from 0.1 to 0.9
        thresholds = np.arange(0.1, 0.9, 0.05)
        results = []

        for threshold in thresholds:
            predictions = distances <= threshold

            # Calculate metrics
            tp = np.sum((predictions == True) & (ground_truths == True))
            tn = np.sum((predictions == False) & (ground_truths == False))
            fp = np.sum((predictions == True) & (ground_truths == False))
            fn = np.sum((predictions == False) & (ground_truths == True))

            # Calculate rates
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0  # True Positive Rate (Recall)
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0  # False Positive Rate
            tnr = tn / (tn + fp) if (tn + fp) > 0 else 0  # True Negative Rate (Specificity)
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0  # False Negative Rate

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tpr
            accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            results.append({
                'threshold': float(threshold),
                'tp': int(tp), 'tn': int(tn), 'fp': int(fp), 'fn': int(fn),
                'tpr': float(tpr), 'fpr': float(fpr),
                'tnr': float(tnr), 'fnr': float(fnr),
                'precision': float(precision),
                'recall': float(recall),
                'accuracy': float(accuracy),
                'f1_score': float(f1_score)
            })

        return {
            'sample_count': len(calibration_data),
            'positive_samples': int(np.sum(ground_truths)),
            'negative_samples': int(len(ground_truths) - np.sum(ground_truths)),
            'threshold_analysis': results,
            'distance_stats': {
                'mean': float(np.mean(distances)),
                'std': float(np.std(distances)),
                'min': float(np.min(distances)),
                'max': float(np.max(distances)),
                'median': float(np.median(distances))
            }
        }

    def calculate_roc_and_eer(self, calibration_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate ROC curve and Equal Error Rate (EER)"""
        distances = np.array([item['distance'] for item in calibration_data if item['distance'] is not None])
        ground_truths = np.array([item['ground_truth'] for item in calibration_data if item['distance'] is not None])

        # Calculate ROC curve points
        thresholds = np.sort(np.unique(distances))
        tpr_values = []
        fpr_values = []

        for threshold in thresholds:
            predictions = distances <= threshold

            tp = np.sum((predictions == True) & (ground_truths == True))
            tn = np.sum((predictions == False) & (ground_truths == False))
            fp = np.sum((predictions == True) & (ground_truths == False))
            fn = np.sum((predictions == False) & (ground_truths == True))

            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

            tpr_values.append(tpr)
            fpr_values.append(fpr)

        # Calculate AUC (Area Under Curve)
        auc = np.trapz(tpr_values, fpr_values)

        # Find EER (Equal Error Rate) - where FPR = FNR
        eer_threshold = None
        eer_value = None
        min_diff = float('inf')

        for i, threshold in enumerate(thresholds):
            fpr = fpr_values[i]
            fnr = 1 - tpr_values[i]  # FNR = 1 - TPR
            diff = abs(fpr - fnr)

            if diff < min_diff:
                min_diff = diff
                eer_threshold = threshold
                eer_value = (fpr + fnr) / 2

        return {
            'auc': float(auc),
            'eer_threshold': float(eer_threshold) if eer_threshold else None,
            'eer_value': float(eer_value) if eer_value else None,
            'roc_points': [
                {'threshold': float(t), 'tpr': float(tpr), 'fpr': float(fpr)}
                for t, tpr, fpr in zip(thresholds, tpr_values, fpr_values)
            ]
        }

    def generate_recommendations(
        self,
        analysis_results: Dict[str, Any],
        roc_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate threshold recommendations based on analysis"""
        threshold_analysis = analysis_results['threshold_analysis']

        # Find best thresholds for different criteria
        best_accuracy = max(threshold_analysis, key=lambda x: x['accuracy'])
        best_f1 = max(threshold_analysis, key=lambda x: x['f1_score'])
        best_precision = max(threshold_analysis, key=lambda x: x['precision'])
        best_recall = max(threshold_analysis, key=lambda x: x['recall'])

        recommendations = {
            'best_for_accuracy': {
                'threshold': best_accuracy['threshold'],
                'accuracy': best_accuracy['accuracy'],
                'f1_score': best_accuracy['f1_score']
            },
            'best_for_f1_score': {
                'threshold': best_f1['threshold'],
                'accuracy': best_f1['accuracy'],
                'f1_score': best_f1['f1_score']
            },
            'best_for_precision': {
                'threshold': best_precision['threshold'],
                'precision': best_precision['precision'],
                'recall': best_precision['recall']
            },
            'best_for_recall': {
                'threshold': best_recall['threshold'],
                'precision': best_recall['precision'],
                'recall': best_recall['recall']
            }
        }

        # Add EER recommendation
        if roc_results['eer_threshold']:
            recommendations['eer_based'] = {
                'threshold': roc_results['eer_threshold'],
                'eer_value': roc_results['eer_value'],
                'rationale': 'Equal Error Rate minimizes both false positives and false negatives'
            }

        # Overall recommendation
        if roc_results['eer_threshold'] and roc_results['auc'] > 0.8:
            recommendations['recommended'] = recommendations['eer_based']
            recommendations['rationale'] = 'EER-based threshold with good AUC performance'
        else:
            recommendations['recommended'] = recommendations['best_for_f1_score']
            recommendations['rationale'] = 'F1-score optimized threshold for balanced performance'

        return recommendations

    def output_results(self, calibration_results: Dict[str, Any]):
        """Output calibration results"""
        # Console output
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("THRESHOLD CALIBRATION RESULTS"))
        self.stdout.write("="*60)

        # Summary statistics
        analysis = calibration_results['analysis']
        roc = calibration_results['roc_analysis']
        recommendations = calibration_results['recommendations']

        self.stdout.write(f"Model Type: {calibration_results['model_type']}")
        self.stdout.write(f"Engine: {calibration_results['engine']}")
        self.stdout.write(f"Sample Count: {calibration_results['sample_count']}")
        self.stdout.write(f"Positive Samples: {analysis['positive_samples']}")
        self.stdout.write(f"Negative Samples: {analysis['negative_samples']}")

        # ROC Analysis
        self.stdout.write(f"\nROC Analysis:")
        self.stdout.write(f"  AUC: {roc['auc']:.4f}")
        if roc['eer_threshold']:
            self.stdout.write(f"  EER Threshold: {roc['eer_threshold']:.4f}")
            self.stdout.write(f"  EER Value: {roc['eer_value']:.4f}")

        # Recommendations
        self.stdout.write(f"\nRecommendations:")
        rec = recommendations['recommended']
        self.stdout.write(f"  Recommended Threshold: {rec['threshold']:.4f}")
        self.stdout.write(f"  Rationale: {recommendations['rationale']}")

        if 'accuracy' in rec:
            self.stdout.write(f"  Expected Accuracy: {rec['accuracy']:.4f}")
        if 'f1_score' in rec:
            self.stdout.write(f"  Expected F1-Score: {rec['f1_score']:.4f}")

        # File output
        if self.options.get('output_file'):
            output_path = self.options['output_file']
            with open(output_path, 'w') as f:
                json.dump(calibration_results, f, indent=2, default=str)
            self.stdout.write(f"\nDetailed results saved to: {output_path}")

    def apply_calibration_results(
        self,
        face_model: FaceRecognitionModel,
        calibration_results: Dict[str, Any]
    ):
        """Apply calibration results to the face model"""
        recommendations = calibration_results['recommendations']
        recommended_threshold = recommendations['recommended']['threshold']

        # Update model with new threshold
        old_threshold = face_model.similarity_threshold
        face_model.similarity_threshold = recommended_threshold

        # Update training dataset info
        face_model.training_dataset_info = {
            'calibration_timestamp': calibration_results['timestamp'],
            'sample_count': calibration_results['sample_count'],
            'auc': calibration_results['roc_analysis']['auc'],
            'eer_value': calibration_results['roc_analysis']['eer_value'],
            'old_threshold': old_threshold,
            'calibration_method': 'empirical_roc_eer'
        }

        face_model.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated model '{face_model.name}' threshold: "
                f"{old_threshold:.4f} → {recommended_threshold:.4f}"
            )
        )

        # Log the calibration
        logger.info(
            f"Threshold calibration applied: model={face_model.name}, "
            f"old_threshold={old_threshold:.4f}, new_threshold={recommended_threshold:.4f}"
        )
