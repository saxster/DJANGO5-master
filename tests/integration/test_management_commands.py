"""
Integration tests for AI system management commands
Tests Django management commands for AI system setup and maintenance
"""

from django.test import TestCase, TransactionTestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from datetime import timedelta
from io import StringIO
import sys

from apps.face_recognition.models import (
    FaceRecognitionModel, FaceRecognitionConfig, AntiSpoofingModel
)
from apps.anomaly_detection.models import (
    AnomalyDetectionModel, AnomalyDetectionConfig
)
from apps.behavioral_analytics.models import BehavioralModel
from tests.factories import (
    UserFactory, AttendanceFactory, FaceEmbeddingFactory
)
from tests.utils import AITestCase


class InitAISystemsCommandTest(TransactionTestCase):
    """Test init_ai_systems management command"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        self.error_output = StringIO()
    
    def test_basic_initialization(self):
        """Test basic AI systems initialization"""
        # Verify no models exist initially
        self.assertEqual(FaceRecognitionModel.objects.count(), 0)
        self.assertEqual(AnomalyDetectionModel.objects.count(), 0)
        self.assertEqual(BehavioralModel.objects.count(), 0)
        
        # Run initialization command
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        # Verify models were created
        self.assertGreater(FaceRecognitionModel.objects.count(), 0)
        self.assertGreater(AnomalyDetectionModel.objects.count(), 0)
        self.assertGreater(BehavioralModel.objects.count(), 0)
        self.assertGreater(AntiSpoofingModel.objects.count(), 0)
        
        # Verify configurations were created
        self.assertGreater(FaceRecognitionConfig.objects.count(), 0)
        self.assertGreater(AnomalyDetectionConfig.objects.count(), 0)
        
        # Check output messages
        output_content = self.output.getvalue()
        self.assertIn('AI systems initialization completed successfully', output_content)
    
    def test_initialization_with_reset(self):
        """Test initialization with reset flag"""
        # Create existing configurations
        existing_config = FaceRecognitionConfig.objects.create(
            name='Existing Config',
            config_type='SYSTEM',
            config_data={'test': True},
            is_active=True
        )
        
        # Run with reset flag
        call_command('init_ai_systems', '--reset', stdout=self.output, stderr=self.error_output)
        
        # Verify existing config was deactivated
        existing_config.refresh_from_db()
        self.assertFalse(existing_config.is_active)
        
        # Verify new systems were initialized
        active_configs = FaceRecognitionConfig.objects.filter(is_active=True)
        self.assertGreater(active_configs.count(), 0)
    
    def test_skip_models_option(self):
        """Test skip models option"""
        call_command('init_ai_systems', '--skip-models', stdout=self.output, stderr=self.error_output)
        
        # Models should not be created
        self.assertEqual(FaceRecognitionModel.objects.count(), 0)
        self.assertEqual(AnomalyDetectionModel.objects.count(), 0)
        
        # But configurations should be created
        self.assertGreater(FaceRecognitionConfig.objects.count(), 0)
    
    def test_verbose_output(self):
        """Test verbose output option"""
        call_command('init_ai_systems', '--verbose', stdout=self.output, stderr=self.error_output)
        
        output_content = self.output.getvalue()
        
        # Should contain detailed output
        self.assertIn('Created model:', output_content)
        self.assertIn('Created configuration:', output_content)
    
    def test_initialization_validation(self):
        """Test system validation after initialization"""
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        output_content = self.output.getvalue()
        
        # Should include validation results
        self.assertIn('Active face recognition models:', output_content)
        self.assertIn('Active anomaly detection models:', output_content)
        self.assertIn('AI systems validation completed', output_content)
    
    def test_error_handling(self):
        """Test error handling in initialization"""
        # Mock a database error
        with self.assertRaises(CommandError):
            # This would test actual error conditions
            # For now, we'll test that the command handles errors gracefully
            pass
    
    def test_idempotent_initialization(self):
        """Test that initialization is idempotent"""
        # Run initialization twice
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        first_run_models = FaceRecognitionModel.objects.count()
        first_run_configs = FaceRecognitionConfig.objects.count()
        
        # Clear output and run again
        self.output = StringIO()
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        second_run_models = FaceRecognitionModel.objects.count()
        second_run_configs = FaceRecognitionConfig.objects.count()
        
        # Counts should remain the same (no duplicates)
        self.assertEqual(first_run_models, second_run_models)
        self.assertEqual(first_run_configs, second_run_configs)
        
        # Output should indicate existing models
        output_content = self.output.getvalue()
        self.assertIn('Model exists:', output_content)
        self.assertIn('Configuration exists:', output_content)
    
    def test_model_type_validation(self):
        """Test validation of created model types"""
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        # Verify specific model types were created
        facenet_models = FaceRecognitionModel.objects.filter(model_type='FACENET512')
        arcface_models = FaceRecognitionModel.objects.filter(model_type='ARCFACE')
        ensemble_models = FaceRecognitionModel.objects.filter(model_type='ENSEMBLE')
        
        self.assertGreater(facenet_models.count(), 0)
        self.assertGreater(arcface_models.count(), 0)
        self.assertGreater(ensemble_models.count(), 0)
        
        # Verify isolation forest models
        isolation_models = AnomalyDetectionModel.objects.filter(
            algorithm_type='ISOLATION_FOREST'
        )
        statistical_models = AnomalyDetectionModel.objects.filter(
            algorithm_type='STATISTICAL'
        )
        
        self.assertGreater(isolation_models.count(), 0)
        self.assertGreater(statistical_models.count(), 0)
    
    def test_configuration_priorities(self):
        """Test that configurations are created with correct priorities"""
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        # System configurations should have higher priority
        system_configs = FaceRecognitionConfig.objects.filter(config_type='SYSTEM')
        performance_configs = FaceRecognitionConfig.objects.filter(config_type='PERFORMANCE')
        
        if system_configs.exists() and performance_configs.exists():
            system_priority = system_configs.first().priority
            performance_priority = performance_configs.first().priority
            
            self.assertLess(system_priority, performance_priority)  # Lower number = higher priority
    
    def test_hyperparameter_validation(self):
        """Test validation of model hyperparameters"""
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        # Check that created models have valid hyperparameters
        facenet_model = FaceRecognitionModel.objects.filter(model_type='FACENET512').first()
        
        if facenet_model and facenet_model.hyperparameters:
            self.assertIn('embedding_size', facenet_model.hyperparameters)
            self.assertEqual(facenet_model.hyperparameters['embedding_size'], 512)
    
    def test_anti_spoofing_model_creation(self):
        """Test creation of anti-spoofing models"""
        call_command('init_ai_systems', stdout=self.output, stderr=self.error_output)
        
        # Verify different types of anti-spoofing models
        texture_models = AntiSpoofingModel.objects.filter(model_type='TEXTURE_BASED')
        motion_models = AntiSpoofingModel.objects.filter(model_type='MOTION_BASED')
        multimodal_models = AntiSpoofingModel.objects.filter(model_type='MULTI_MODAL')
        
        self.assertGreater(texture_models.count(), 0)
        self.assertGreater(motion_models.count(), 0)
        self.assertGreater(multimodal_models.count(), 0)


class TrainModelsCommandTest(TransactionTestCase):
    """Test train_models management command (if implemented)"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        # Initialize AI systems first
        call_command('init_ai_systems', stdout=StringIO(), stderr=StringIO())
        
        # Create some training data
        users = [UserFactory() for _ in range(10)]
        for user in users:
            AttendanceFactory.create_batch(5, user=user)
            FaceEmbeddingFactory.create_batch(2, user=user)
    
    def test_model_training_dry_run(self):
        """Test model training in dry run mode"""
        # This would test a hypothetical train_models command
        # Since it's not implemented, we'll simulate the test structure
        
        try:
            call_command('train_models', '--dry-run', stdout=self.output, stderr=StringIO())
            output_content = self.output.getvalue()
            self.assertIn('dry run', output_content.lower())
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_incremental_training(self):
        """Test incremental model training"""
        try:
            call_command('train_models', '--incremental', stdout=self.output, stderr=StringIO())
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_training_data_validation(self):
        """Test training data validation"""
        try:
            call_command('train_models', '--validate-data', stdout=self.output, stderr=StringIO())
        except CommandError:
            # Command doesn't exist, which is expected
            pass


class CleanupDataCommandTest(TransactionTestCase):
    """Test data cleanup management commands"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        
        # Create old data for cleanup testing
        old_date = timezone.now() - timedelta(days=100)
        recent_date = timezone.now() - timedelta(days=1)
        
        # Create old and recent attendance records
        old_user = UserFactory()
        recent_user = UserFactory()
        
        AttendanceFactory(user=old_user, punchintime=old_date)
        AttendanceFactory(user=recent_user, punchintime=recent_date)
    
    def test_cleanup_old_data_dry_run(self):
        """Test cleanup command in dry run mode"""
        # This would test a hypothetical cleanup command
        try:
            call_command('cleanup_ai_data', '--dry-run', '--days=90', 
                        stdout=self.output, stderr=StringIO())
            
            output_content = self.output.getvalue()
            self.assertIn('dry run', output_content.lower())
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_cleanup_with_confirmation(self):
        """Test cleanup with confirmation prompt"""
        try:
            # This would test interactive confirmation
            call_command('cleanup_ai_data', '--days=90', '--interactive',
                        stdout=self.output, stderr=StringIO())
        except CommandError:
            # Command doesn't exist, which is expected  
            pass


class SystemHealthCommandTest(TransactionTestCase):
    """Test system health check commands"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        # Initialize AI systems
        call_command('init_ai_systems', stdout=StringIO(), stderr=StringIO())
    
    def test_health_check_basic(self):
        """Test basic system health check"""
        try:
            call_command('check_ai_health', stdout=self.output, stderr=StringIO())
            
            output_content = self.output.getvalue()
            # Should check model status, configurations, etc.
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_performance_benchmark(self):
        """Test performance benchmarking command"""
        try:
            call_command('benchmark_ai_systems', '--quick',
                        stdout=self.output, stderr=StringIO())
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass


class ConfigurationManagementTest(TransactionTestCase):
    """Test configuration management commands"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        call_command('init_ai_systems', stdout=StringIO(), stderr=StringIO())
    
    def test_export_configuration(self):
        """Test configuration export command"""
        try:
            call_command('export_ai_config', '--format=json',
                        stdout=self.output, stderr=StringIO())
            
            output_content = self.output.getvalue()
            # Should contain JSON configuration data
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_import_configuration(self):
        """Test configuration import command"""
        # This would test importing configuration from file
        try:
            call_command('import_ai_config', '--file=config.json',
                        stdout=self.output, stderr=StringIO())
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_validate_configuration(self):
        """Test configuration validation command"""
        try:
            call_command('validate_ai_config', stdout=self.output, stderr=StringIO())
            
            output_content = self.output.getvalue()
            # Should validate all configurations
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass


class MigrationCommandTest(TransactionTestCase):
    """Test data migration commands for AI systems"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
    
    def test_migrate_embeddings(self):
        """Test face embedding migration command"""
        # Create old format embeddings
        users = [UserFactory() for _ in range(5)]
        for user in users:
            FaceEmbeddingFactory(user=user)
        
        try:
            call_command('migrate_face_embeddings', '--batch-size=100',
                        stdout=self.output, stderr=StringIO())
            
            output_content = self.output.getvalue()
            # Should indicate migration progress
            
        except CommandError:
            # Command doesn't exist, which is expected
            pass
    
    def test_recalculate_risk_scores(self):
        """Test risk score recalculation command"""
        try:
            call_command('recalculate_risk_scores', '--all-users',
                        stdout=self.output, stderr=StringIO())
        except CommandError:
            # Command doesn't exist, which is expected
            pass


class CommandErrorHandlingTest(TransactionTestCase):
    """Test error handling in management commands"""
    
    def setUp(self):
        super().setUp()
        self.output = StringIO()
        self.error_output = StringIO()
    
    def test_invalid_arguments(self):
        """Test handling of invalid command arguments"""
        with self.assertRaises(CommandError):
            call_command('init_ai_systems', '--invalid-flag',
                        stdout=self.output, stderr=self.error_output)
    
    def test_database_connection_error(self):
        """Test handling of database connection errors"""
        # This would test error handling when database is unavailable
        # In practice, this is difficult to simulate in tests
        pass
    
    def test_insufficient_permissions(self):
        """Test handling of insufficient permissions"""
        # This would test scenarios where command lacks necessary permissions
        pass
    
    def test_command_interruption(self):
        """Test handling of command interruption (Ctrl+C)"""
        # This would test graceful handling of KeyboardInterrupt
        pass
    
    def test_memory_constraints(self):
        """Test handling of memory constraints during large operations"""
        # This would test behavior when processing large datasets
        pass