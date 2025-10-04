"""
Active Learning Service - Intelligent training sample selection.

Implements uncertainty-based sampling, diversity selection, and
smart prioritization for maximum training efficiency.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from django.db import models, transaction
from django.db.models import Q, F, Avg, Count, Max
from django.utils import timezone

from ..models import TrainingDataset, TrainingExample, LabelingTask
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class ActiveLearningService:
    """
    Intelligent active learning for optimal training data selection.

    Uses uncertainty sampling, diversity analysis, and strategic selection
    to maximize learning efficiency with minimal labeling effort.
    """

    def __init__(self):
        """Initialize active learning service with configuration."""
        self.uncertainty_threshold = 0.6  # Minimum uncertainty for selection
        self.diversity_weight = 0.3  # Weight for diversity vs uncertainty
        self.batch_size_default = 50  # Default batch size for labeling
        self.confidence_bands = {
            'very_low': (0.0, 0.3),
            'low': (0.3, 0.5),
            'medium': (0.5, 0.7),
            'high': (0.7, 0.9),
            'very_high': (0.9, 1.0)
        }

    def detect_uncertain_examples(
        self,
        dataset: TrainingDataset,
        min_uncertainty: float = None,
        limit: int = None
    ) -> Dict[str, Any]:
        """
        Detect examples with high uncertainty scores for labeling.

        Args:
            dataset: Target dataset
            min_uncertainty: Minimum uncertainty threshold
            limit: Maximum number of examples to return

        Returns:
            {
                'success': bool,
                'examples': List[TrainingExample],
                'uncertainty_stats': Dict[str, Any],
                'error': str | None
            }
        """
        result = {
            'success': False,
            'examples': [],
            'uncertainty_stats': {},
            'error': None
        }

        try:
            min_uncertainty = min_uncertainty or self.uncertainty_threshold

            # Query uncertain examples
            uncertain_examples = TrainingExample.objects.filter(
                dataset=dataset,
                uncertainty_score__gte=min_uncertainty,
                is_labeled=False
            ).select_related('dataset').order_by('-uncertainty_score', '-created_at')

            if limit:
                uncertain_examples = uncertain_examples[:limit]

            result['examples'] = list(uncertain_examples)

            # Calculate uncertainty statistics
            result['uncertainty_stats'] = self._calculate_uncertainty_stats(dataset)
            result['success'] = True

            logger.info(
                f"Found {len(result['examples'])} uncertain examples in dataset {dataset.id}"
            )

        except Exception as e:
            logger.error(f"Error detecting uncertain examples: {str(e)}", exc_info=True)
            result['error'] = f"Detection failed: {str(e)}"

        return result

    def select_optimal_batch(
        self,
        dataset: TrainingDataset,
        batch_size: int = None,
        strategy: str = "uncertainty_diversity"
    ) -> Dict[str, Any]:
        """
        Select optimal batch of examples for labeling using active learning.

        Args:
            dataset: Target dataset
            batch_size: Size of batch to select
            strategy: Selection strategy (uncertainty, diversity, uncertainty_diversity)

        Returns:
            {
                'success': bool,
                'selected_examples': List[TrainingExample],
                'selection_stats': Dict[str, Any],
                'error': str | None
            }
        """
        result = {
            'success': False,
            'selected_examples': [],
            'selection_stats': {},
            'error': None
        }

        try:
            batch_size = batch_size or self.batch_size_default

            if strategy == "uncertainty":
                selection_result = self._select_by_uncertainty(dataset, batch_size)
            elif strategy == "diversity":
                selection_result = self._select_by_diversity(dataset, batch_size)
            elif strategy == "uncertainty_diversity":
                selection_result = self._select_by_uncertainty_diversity(dataset, batch_size)
            else:
                result['error'] = f"Unknown selection strategy: {strategy}"
                return result

            if not selection_result['success']:
                result['error'] = selection_result['error']
                return result

            # Mark selected examples
            selected_ids = [ex.id for ex in selection_result['examples']]
            TrainingExample.objects.filter(id__in=selected_ids).update(
                selected_for_labeling=True,
                labeling_priority=F('uncertainty_score') * 10
            )

            result['selected_examples'] = selection_result['examples']
            result['selection_stats'] = selection_result['stats']
            result['success'] = True

            logger.info(
                f"Selected optimal batch of {len(result['selected_examples'])} examples "
                f"using {strategy} strategy"
            )

        except Exception as e:
            logger.error(f"Error selecting optimal batch: {str(e)}", exc_info=True)
            result['error'] = f"Selection failed: {str(e)}"

        return result

    def create_labeling_task(
        self,
        dataset: TrainingDataset,
        examples: List[TrainingExample],
        assigned_to: People,
        task_type: str = "INITIAL_LABELING",
        priority: int = 5,
        instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Create a labeling task from selected examples.

        Args:
            dataset: Target dataset
            examples: Examples to include in task
            assigned_to: User to assign task to
            task_type: Type of labeling task
            priority: Task priority (1-10)
            instructions: Specific instructions

        Returns:
            {
                'success': bool,
                'task': LabelingTask | None,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'task': None,
            'error': None
        }

        try:
            if not examples:
                result['error'] = "No examples provided for labeling task"
                return result

            with transaction.atomic():
                # Create labeling task
                task = LabelingTask.objects.create(
                    dataset=dataset,
                    task_type=task_type,
                    assigned_to=assigned_to,
                    priority=priority,
                    instructions=instructions or dataset.labeling_guidelines,
                    total_examples=len(examples),
                    due_date=timezone.now() + timedelta(days=7)  # Default 7-day deadline
                )

                # Add examples to task
                task.examples.set(examples)

                # Update example labeling status
                TrainingExample.objects.filter(
                    id__in=[ex.id for ex in examples]
                ).update(
                    labeling_status=TrainingExample.LabelingStatus.IN_PROGRESS.value
                )

                result['success'] = True
                result['task'] = task

                logger.info(
                    f"Created labeling task {task.id} with {len(examples)} examples "
                    f"for {assigned_to.peoplename}"
                )

        except Exception as e:
            logger.error(f"Error creating labeling task: {str(e)}", exc_info=True)
            result['error'] = f"Task creation failed: {str(e)}"

        return result

    def analyze_model_performance(
        self,
        dataset: TrainingDataset,
        confidence_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Analyze model performance and identify areas for improvement.

        Args:
            dataset: Target dataset
            confidence_scores: Map of example IDs to confidence scores

        Returns:
            Performance analysis and recommendations
        """
        result = {
            'success': False,
            'analysis': {},
            'recommendations': [],
            'error': None
        }

        try:
            # Update uncertainty scores from confidence scores
            updated_count = 0
            for example_id, confidence in confidence_scores.items():
                uncertainty = 1.0 - confidence
                updated = TrainingExample.objects.filter(
                    dataset=dataset,
                    uuid=example_id
                ).update(
                    uncertainty_score=uncertainty,
                    difficulty_score=uncertainty  # Simple heuristic
                )
                updated_count += updated

            # Analyze performance by confidence bands
            performance_by_band = self._analyze_confidence_bands(dataset)

            # Identify weak areas
            weak_areas = self._identify_weak_areas(dataset, performance_by_band)

            # Generate recommendations
            recommendations = self._generate_recommendations(weak_areas, performance_by_band)

            result['analysis'] = {
                'updated_examples': updated_count,
                'performance_by_band': performance_by_band,
                'weak_areas': weak_areas,
                'dataset_stats': self._calculate_uncertainty_stats(dataset)
            }
            result['recommendations'] = recommendations
            result['success'] = True

            logger.info(f"Analyzed performance for dataset {dataset.id}: {updated_count} examples updated")

        except Exception as e:
            logger.error(f"Error analyzing model performance: {str(e)}", exc_info=True)
            result['error'] = f"Analysis failed: {str(e)}"

        return result

    def _select_by_uncertainty(
        self,
        dataset: TrainingDataset,
        batch_size: int
    ) -> Dict[str, Any]:
        """Select examples with highest uncertainty scores."""
        try:
            examples = list(
                TrainingExample.objects.filter(
                    dataset=dataset,
                    is_labeled=False,
                    uncertainty_score__isnull=False
                ).order_by('-uncertainty_score')[:batch_size]
            )

            stats = {
                'strategy': 'uncertainty',
                'avg_uncertainty': np.mean([ex.uncertainty_score for ex in examples]) if examples else 0,
                'min_uncertainty': min([ex.uncertainty_score for ex in examples]) if examples else 0,
                'max_uncertainty': max([ex.uncertainty_score for ex in examples]) if examples else 0
            }

            return {'success': True, 'examples': examples, 'stats': stats}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _select_by_diversity(
        self,
        dataset: TrainingDataset,
        batch_size: int
    ) -> Dict[str, Any]:
        """Select diverse examples using clustering approximation."""
        try:
            # Simple diversity heuristic: select examples with different metadata
            examples = list(
                TrainingExample.objects.filter(
                    dataset=dataset,
                    is_labeled=False
                ).order_by('image_width', 'image_height', 'file_size')[:batch_size]
            )

            stats = {
                'strategy': 'diversity',
                'size_range': self._calculate_size_diversity(examples),
                'selected_count': len(examples)
            }

            return {'success': True, 'examples': examples, 'stats': stats}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _select_by_uncertainty_diversity(
        self,
        dataset: TrainingDataset,
        batch_size: int
    ) -> Dict[str, Any]:
        """Select examples balancing uncertainty and diversity."""
        try:
            # Hybrid approach: select top uncertain examples, then diversify
            uncertain_pool_size = min(batch_size * 3, 200)  # Larger pool for diversity

            uncertain_pool = list(
                TrainingExample.objects.filter(
                    dataset=dataset,
                    is_labeled=False,
                    uncertainty_score__isnull=False
                ).order_by('-uncertainty_score')[:uncertain_pool_size]
            )

            if len(uncertain_pool) <= batch_size:
                selected = uncertain_pool
            else:
                # Select diverse subset from uncertain pool
                selected = self._diversify_selection(uncertain_pool, batch_size)

            stats = {
                'strategy': 'uncertainty_diversity',
                'uncertain_pool_size': len(uncertain_pool),
                'final_selection': len(selected),
                'avg_uncertainty': np.mean([ex.uncertainty_score for ex in selected]) if selected else 0
            }

            return {'success': True, 'examples': selected, 'stats': stats}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _diversify_selection(
        self,
        examples: List[TrainingExample],
        target_size: int
    ) -> List[TrainingExample]:
        """Diversify selection using simple greedy algorithm."""
        if not examples or target_size <= 0:
            return []

        if len(examples) <= target_size:
            return examples

        selected = [examples[0]]  # Start with highest uncertainty
        remaining = examples[1:]

        while len(selected) < target_size and remaining:
            # Find example most different from selected ones
            best_candidate = None
            best_diversity_score = -1

            for candidate in remaining:
                diversity_score = self._calculate_diversity_score(candidate, selected)
                if diversity_score > best_diversity_score:
                    best_diversity_score = diversity_score
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)

        return selected

    def _calculate_diversity_score(
        self,
        candidate: TrainingExample,
        selected: List[TrainingExample]
    ) -> float:
        """Calculate diversity score for candidate example."""
        if not selected:
            return 1.0

        # Simple diversity based on image dimensions and file size
        diversity_scores = []
        for selected_ex in selected:
            size_diff = abs(
                (candidate.image_width or 0) * (candidate.image_height or 0) -
                (selected_ex.image_width or 0) * (selected_ex.image_height or 0)
            )
            file_size_diff = abs(
                (candidate.file_size or 0) - (selected_ex.file_size or 0)
            )

            # Normalize and combine
            normalized_score = min(size_diff / 1000000 + file_size_diff / 1000000, 1.0)
            diversity_scores.append(normalized_score)

        return min(diversity_scores)  # Minimum distance to any selected example

    def _calculate_uncertainty_stats(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """Calculate comprehensive uncertainty statistics."""
        try:
            examples = TrainingExample.objects.filter(dataset=dataset)
            uncertain_examples = examples.filter(uncertainty_score__isnull=False)

            if not uncertain_examples.exists():
                return {'total_examples': examples.count(), 'uncertain_examples': 0}

            stats = uncertain_examples.aggregate(
                count=Count('id'),
                avg_uncertainty=Avg('uncertainty_score'),
                max_uncertainty=Max('uncertainty_score')
            )

            # Calculate confidence band distribution
            band_distribution = {}
            for band_name, (min_conf, max_conf) in self.confidence_bands.items():
                min_uncertainty = 1.0 - max_conf
                max_uncertainty = 1.0 - min_conf
                count = uncertain_examples.filter(
                    uncertainty_score__gte=min_uncertainty,
                    uncertainty_score__lt=max_uncertainty
                ).count()
                band_distribution[band_name] = count

            return {
                'total_examples': examples.count(),
                'uncertain_examples': stats['count'],
                'avg_uncertainty': float(stats['avg_uncertainty'] or 0),
                'max_uncertainty': float(stats['max_uncertainty'] or 0),
                'band_distribution': band_distribution,
                'needs_labeling': uncertain_examples.filter(
                    uncertainty_score__gte=self.uncertainty_threshold,
                    is_labeled=False
                ).count()
            }

        except Exception as e:
            logger.error(f"Error calculating uncertainty stats: {str(e)}")
            return {'error': str(e)}

    def _analyze_confidence_bands(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """Analyze model performance across confidence bands."""
        band_analysis = {}

        for band_name, (min_conf, max_conf) in self.confidence_bands.items():
            min_uncertainty = 1.0 - max_conf
            max_uncertainty = 1.0 - min_conf

            examples_in_band = TrainingExample.objects.filter(
                dataset=dataset,
                uncertainty_score__gte=min_uncertainty,
                uncertainty_score__lt=max_uncertainty
            )

            band_analysis[band_name] = {
                'total_examples': examples_in_band.count(),
                'labeled_examples': examples_in_band.filter(is_labeled=True).count(),
                'avg_quality': examples_in_band.filter(
                    quality_score__isnull=False
                ).aggregate(avg=Avg('quality_score'))['avg'] or 0
            }

        return band_analysis

    def _identify_weak_areas(
        self,
        dataset: TrainingDataset,
        performance_by_band: Dict[str, Any]
    ) -> List[str]:
        """Identify areas where model performance is weak."""
        weak_areas = []

        # High uncertainty with low quality
        if (performance_by_band.get('very_low', {}).get('total_examples', 0) > 10 and
            performance_by_band.get('very_low', {}).get('avg_quality', 1.0) < 0.6):
            weak_areas.append("High uncertainty predictions with poor quality labels")

        # Large number of medium confidence predictions
        medium_conf_count = performance_by_band.get('medium', {}).get('total_examples', 0)
        total_examples = sum(band.get('total_examples', 0) for band in performance_by_band.values())

        if total_examples > 0 and medium_conf_count / total_examples > 0.4:
            weak_areas.append("Too many medium-confidence predictions")

        return weak_areas

    def _generate_recommendations(
        self,
        weak_areas: List[str],
        performance_by_band: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations for model improvement."""
        recommendations = []

        if "High uncertainty predictions with poor quality labels" in weak_areas:
            recommendations.append(
                "Focus labeling efforts on very low confidence examples to improve model reliability"
            )

        if "Too many medium-confidence predictions" in weak_areas:
            recommendations.append(
                "Collect more training data for edge cases to improve model confidence calibration"
            )

        # General recommendations
        very_low_count = performance_by_band.get('very_low', {}).get('total_examples', 0)
        if very_low_count > 20:
            recommendations.append(
                f"Consider reviewing {very_low_count} very low confidence examples for potential model improvement"
            )

        return recommendations

    def _calculate_size_diversity(self, examples: List[TrainingExample]) -> Dict[str, Any]:
        """Calculate diversity metrics based on image sizes."""
        if not examples:
            return {}

        widths = [ex.image_width for ex in examples if ex.image_width]
        heights = [ex.image_height for ex in examples if ex.image_height]

        if not widths or not heights:
            return {}

        return {
            'width_range': max(widths) - min(widths),
            'height_range': max(heights) - min(heights),
            'avg_width': np.mean(widths),
            'avg_height': np.mean(heights)
        }


# Factory function
def get_active_learning_service() -> ActiveLearningService:
    """Factory function to get active learning service instance."""
    return ActiveLearningService()