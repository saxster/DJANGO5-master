"""
Comprehensive tests for ML Active Learning Service.

Tests uncertainty sampling, diversity selection, batch optimization,
and intelligent training data selection strategies.

Coverage target: 80%+
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase

from apps.ml_training.services.active_learning_service import (
    ActiveLearningService,
    get_active_learning_service
)
from apps.ml_training.models import TrainingDataset, TrainingExample, LabelingTask
from apps.peoples.models import People


@pytest.fixture
def active_learning_service():
    """Create ActiveLearningService instance."""
    return ActiveLearningService()


@pytest.fixture
def sample_dataset(db):
    """Create sample training dataset."""
    return TrainingDataset.objects.create(
        name="Test Dataset",
        dataset_type="OBJECT_DETECTION",
        labeling_guidelines="Test labeling guidelines",
        status="ACTIVE"
    )


@pytest.fixture
def sample_user(db):
    """Create sample user for testing."""
    return People.objects.create(
        peoplename="testuser",
        peopleemail="test@example.com",
        peoplecontactno="+919876543210"
    )


@pytest.fixture
def uncertain_examples(db, sample_dataset):
    """Create examples with various uncertainty scores."""
    examples = []
    for i in range(20):
        example = TrainingExample.objects.create(
            dataset=sample_dataset,
            file_path=f"/test/image_{i}.jpg",
            uncertainty_score=0.3 + (i * 0.03),  # Range from 0.3 to 0.9
            is_labeled=False,
            image_width=640 + (i * 10),
            image_height=480 + (i * 10),
            file_size=50000 + (i * 1000)
        )
        examples.append(example)
    return examples


class TestUncertaintyDetection:
    """Test uncertainty-based example detection."""

    def test_detect_uncertain_examples_default_threshold(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test detecting uncertain examples with default threshold."""
        result = active_learning_service.detect_uncertain_examples(sample_dataset)
        
        assert result['success'] is True
        assert len(result['examples']) > 0
        assert all(ex.uncertainty_score >= 0.6 for ex in result['examples'])
        assert 'uncertainty_stats' in result

    def test_detect_uncertain_examples_custom_threshold(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test detecting uncertain examples with custom threshold."""
        result = active_learning_service.detect_uncertain_examples(
            sample_dataset,
            min_uncertainty=0.8
        )
        
        assert result['success'] is True
        assert all(ex.uncertainty_score >= 0.8 for ex in result['examples'])

    def test_detect_uncertain_examples_with_limit(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test limiting number of uncertain examples returned."""
        result = active_learning_service.detect_uncertain_examples(
            sample_dataset,
            limit=5
        )
        
        assert result['success'] is True
        assert len(result['examples']) <= 5

    def test_detect_uncertain_examples_empty_dataset(
        self,
        active_learning_service,
        sample_dataset
    ):
        """Test detecting uncertain examples in empty dataset."""
        result = active_learning_service.detect_uncertain_examples(sample_dataset)
        
        assert result['success'] is True
        assert len(result['examples']) == 0

    def test_uncertainty_stats_calculation(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test uncertainty statistics calculation."""
        result = active_learning_service.detect_uncertain_examples(sample_dataset)
        stats = result['uncertainty_stats']
        
        assert 'total_examples' in stats
        assert 'uncertain_examples' in stats
        assert 'avg_uncertainty' in stats
        assert 'needs_labeling' in stats
        assert stats['total_examples'] == 20


class TestBatchSelection:
    """Test optimal batch selection strategies."""

    def test_select_by_uncertainty_strategy(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test uncertainty-based batch selection."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            batch_size=5,
            strategy="uncertainty"
        )
        
        assert result['success'] is True
        assert len(result['selected_examples']) <= 5
        
        # Verify examples are sorted by uncertainty (highest first)
        uncertainties = [ex.uncertainty_score for ex in result['selected_examples']]
        assert uncertainties == sorted(uncertainties, reverse=True)

    def test_select_by_diversity_strategy(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test diversity-based batch selection."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            batch_size=5,
            strategy="diversity"
        )
        
        assert result['success'] is True
        assert len(result['selected_examples']) <= 5
        assert 'selection_stats' in result

    def test_select_by_uncertainty_diversity_strategy(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test combined uncertainty-diversity strategy."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            batch_size=5,
            strategy="uncertainty_diversity"
        )
        
        assert result['success'] is True
        assert len(result['selected_examples']) <= 5
        assert result['selection_stats']['strategy'] == 'uncertainty_diversity'

    def test_select_unknown_strategy_fails(
        self,
        active_learning_service,
        sample_dataset
    ):
        """Test unknown selection strategy returns error."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            strategy="invalid_strategy"
        )
        
        assert result['success'] is False
        assert 'Unknown selection strategy' in result['error']

    def test_batch_selection_marks_examples(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples,
        db
    ):
        """Test that batch selection marks examples for labeling."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            batch_size=5,
            strategy="uncertainty"
        )
        
        assert result['success'] is True
        
        # Verify examples were marked
        marked_count = TrainingExample.objects.filter(
            dataset=sample_dataset,
            selected_for_labeling=True
        ).count()
        assert marked_count == len(result['selected_examples'])


class TestDiversityCalculation:
    """Test diversity scoring and selection."""

    def test_diversify_selection_greedy_algorithm(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test greedy diversification algorithm."""
        diverse_batch = active_learning_service._diversify_selection(
            uncertain_examples,
            target_size=5
        )
        
        assert len(diverse_batch) == 5
        assert diverse_batch[0] == uncertain_examples[0]  # Highest uncertainty first

    def test_diversity_score_calculation(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test diversity score calculation between examples."""
        candidate = uncertain_examples[0]
        selected = uncertain_examples[5:10]
        
        score = active_learning_service._calculate_diversity_score(candidate, selected)
        
        assert 0.0 <= score <= 1.0

    def test_diversity_score_empty_selected(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test diversity score with no selected examples."""
        score = active_learning_service._calculate_diversity_score(
            uncertain_examples[0],
            []
        )
        
        assert score == 1.0

    def test_calculate_size_diversity(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test image size diversity calculation."""
        diversity = active_learning_service._calculate_size_diversity(uncertain_examples)
        
        assert 'width_range' in diversity
        assert 'height_range' in diversity
        assert 'avg_width' in diversity
        assert 'avg_height' in diversity


class TestLabelingTaskCreation:
    """Test labeling task creation from selected examples."""

    def test_create_labeling_task_success(
        self,
        active_learning_service,
        sample_dataset,
        sample_user,
        uncertain_examples
    ):
        """Test successful labeling task creation."""
        examples_to_label = uncertain_examples[:5]
        
        result = active_learning_service.create_labeling_task(
            dataset=sample_dataset,
            examples=examples_to_label,
            assigned_to=sample_user,
            task_type="INITIAL_LABELING",
            priority=7,
            instructions="Label all objects in images"
        )
        
        assert result['success'] is True
        assert result['task'] is not None
        assert result['task'].total_examples == 5
        assert result['task'].assigned_to == sample_user
        assert result['task'].priority == 7

    def test_create_labeling_task_updates_example_status(
        self,
        active_learning_service,
        sample_dataset,
        sample_user,
        uncertain_examples,
        db
    ):
        """Test that creating task updates example labeling status."""
        examples_to_label = uncertain_examples[:5]
        
        active_learning_service.create_labeling_task(
            dataset=sample_dataset,
            examples=examples_to_label,
            assigned_to=sample_user
        )
        
        # Verify examples were updated
        for example in examples_to_label:
            example.refresh_from_db()
            assert example.labeling_status == TrainingExample.LabelingStatus.IN_PROGRESS.value

    def test_create_labeling_task_empty_examples_fails(
        self,
        active_learning_service,
        sample_dataset,
        sample_user
    ):
        """Test creating task with no examples returns error."""
        result = active_learning_service.create_labeling_task(
            dataset=sample_dataset,
            examples=[],
            assigned_to=sample_user
        )
        
        assert result['success'] is False
        assert 'No examples provided' in result['error']

    def test_labeling_task_default_deadline(
        self,
        active_learning_service,
        sample_dataset,
        sample_user,
        uncertain_examples
    ):
        """Test labeling task has 7-day default deadline."""
        result = active_learning_service.create_labeling_task(
            dataset=sample_dataset,
            examples=uncertain_examples[:3],
            assigned_to=sample_user
        )
        
        task = result['task']
        expected_due = timezone.now() + timedelta(days=7)
        
        # Allow 1 minute tolerance for test execution time
        assert abs((task.due_date - expected_due).total_seconds()) < 60


class TestPerformanceAnalysis:
    """Test model performance analysis and recommendations."""

    def test_analyze_model_performance_updates_scores(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test that performance analysis updates uncertainty scores."""
        confidence_scores = {
            str(ex.uuid): 0.85 for ex in uncertain_examples[:5]
        }
        
        result = active_learning_service.analyze_model_performance(
            sample_dataset,
            confidence_scores
        )
        
        assert result['success'] is True
        assert result['analysis']['updated_examples'] > 0

    def test_analyze_performance_identifies_weak_areas(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test weak area identification."""
        # Create examples with low confidence scores
        confidence_scores = {
            str(ex.uuid): 0.2 for ex in uncertain_examples[:15]
        }
        
        result = active_learning_service.analyze_model_performance(
            sample_dataset,
            confidence_scores
        )
        
        assert result['success'] is True
        assert 'weak_areas' in result['analysis']

    def test_analyze_performance_generates_recommendations(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test recommendation generation."""
        confidence_scores = {
            str(ex.uuid): 0.5 for ex in uncertain_examples
        }
        
        result = active_learning_service.analyze_model_performance(
            sample_dataset,
            confidence_scores
        )
        
        assert result['success'] is True
        assert 'recommendations' in result
        assert isinstance(result['recommendations'], list)

    def test_confidence_band_analysis(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test performance analysis by confidence bands."""
        confidence_scores = {}
        for i, ex in enumerate(uncertain_examples):
            # Distribute examples across confidence bands
            confidence_scores[str(ex.uuid)] = 0.2 + (i * 0.04)
        
        result = active_learning_service.analyze_model_performance(
            sample_dataset,
            confidence_scores
        )
        
        assert result['success'] is True
        perf_by_band = result['analysis']['performance_by_band']
        
        # Verify all confidence bands analyzed
        assert 'very_low' in perf_by_band
        assert 'medium' in perf_by_band
        assert 'very_high' in perf_by_band


class TestConfidenceBands:
    """Test confidence band configuration and usage."""

    def test_confidence_bands_configured(self, active_learning_service):
        """Test confidence bands are properly configured."""
        bands = active_learning_service.confidence_bands
        
        assert 'very_low' in bands
        assert 'low' in bands
        assert 'medium' in bands
        assert 'high' in bands
        assert 'very_high' in bands
        
        # Verify ranges cover 0.0 to 1.0
        assert bands['very_low'][0] == 0.0
        assert bands['very_high'][1] == 1.0

    def test_uncertainty_threshold_default(self, active_learning_service):
        """Test default uncertainty threshold."""
        assert active_learning_service.uncertainty_threshold == 0.6

    def test_batch_size_default(self, active_learning_service):
        """Test default batch size."""
        assert active_learning_service.batch_size_default == 50


class TestFactoryFunction:
    """Test factory function for service creation."""

    def test_get_active_learning_service(self):
        """Test factory function returns service instance."""
        service = get_active_learning_service()
        
        assert isinstance(service, ActiveLearningService)
        assert service.uncertainty_threshold == 0.6


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_select_batch_larger_than_available(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples
    ):
        """Test selecting batch larger than available examples."""
        result = active_learning_service.select_optimal_batch(
            sample_dataset,
            batch_size=100,  # More than 20 available
            strategy="uncertainty"
        )
        
        assert result['success'] is True
        assert len(result['selected_examples']) <= 20

    def test_analyze_performance_empty_confidence_scores(
        self,
        active_learning_service,
        sample_dataset
    ):
        """Test performance analysis with empty confidence scores."""
        result = active_learning_service.analyze_model_performance(
            sample_dataset,
            {}
        )
        
        assert result['success'] is True
        assert result['analysis']['updated_examples'] == 0

    def test_diversity_selection_single_example(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test diversity selection with single example."""
        diverse_batch = active_learning_service._diversify_selection(
            uncertain_examples[:1],
            target_size=5
        )
        
        assert len(diverse_batch) == 1

    def test_diversity_selection_zero_target(
        self,
        active_learning_service,
        uncertain_examples
    ):
        """Test diversity selection with zero target size."""
        diverse_batch = active_learning_service._diversify_selection(
            uncertain_examples,
            target_size=0
        )
        
        assert len(diverse_batch) == 0


class TestPerformance:
    """Test performance and efficiency."""

    def test_batch_selection_efficient_query(
        self,
        active_learning_service,
        sample_dataset,
        uncertain_examples,
        django_assert_num_queries
    ):
        """Test batch selection uses efficient queries."""
        # Should use minimal database queries
        with django_assert_num_queries(3):  # Select, update, aggregate
            active_learning_service.select_optimal_batch(
                sample_dataset,
                batch_size=5,
                strategy="uncertainty"
            )

    def test_uncertainty_detection_scales(
        self,
        active_learning_service,
        sample_dataset,
        db
    ):
        """Test uncertainty detection scales with large datasets."""
        # Create many examples
        TrainingExample.objects.bulk_create([
            TrainingExample(
                dataset=sample_dataset,
                file_path=f"/test/large_{i}.jpg",
                uncertainty_score=0.7,
                is_labeled=False
            )
            for i in range(500)
        ])
        
        result = active_learning_service.detect_uncertain_examples(
            sample_dataset,
            limit=50
        )
        
        assert result['success'] is True
        assert len(result['examples']) == 50
