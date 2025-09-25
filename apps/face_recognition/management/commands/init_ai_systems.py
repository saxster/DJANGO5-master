"""
Django management command to initialize AI systems for YOUTILITY5
Sets up anomaly detection, behavioral analytics, and enhanced face recognition
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from apps.face_recognition.models import (
    FaceRecognitionModel, FaceRecognitionConfig, AntiSpoofingModel
)
from apps.anomaly_detection.models import (
    AnomalyDetectionModel, AnomalyDetectionConfig
)
from apps.behavioral_analytics.models import BehavioralModel
from apps.attendance.models import PeopleEventlog
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize AI systems for YOUTILITY5 attendance analytics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing AI system configurations'
        )
        parser.add_argument(
            '--skip-models',
            action='store_true',
            help='Skip model initialization (configs only)'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Initialize for specific tenant ID'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        self.setup_logging(options.get('verbose', False))
        
        try:
            with transaction.atomic():
                self.stdout.write(
                    self.style.SUCCESS('Starting AI systems initialization...')
                )
                
                # Initialize components
                if options.get('reset'):
                    self.reset_ai_systems()
                
                if not options.get('skip_models'):
                    self.initialize_face_recognition_models()
                    self.initialize_anti_spoofing_models()
                    self.initialize_anomaly_detection_models()
                    self.initialize_behavioral_models()
                
                self.initialize_system_configurations()
                self.validate_ai_systems()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        'AI systems initialization completed successfully!'
                    )
                )
                
        except Exception as e:
            logger.error(f"Error initializing AI systems: {str(e)}", exc_info=True)
            raise CommandError(f"Initialization failed: {str(e)}")
    
    def setup_logging(self, verbose: bool):
        """Setup logging configuration"""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def reset_ai_systems(self):
        """Reset existing AI system configurations"""
        self.stdout.write('Resetting existing AI configurations...')
        
        # Reset configurations but keep historical data
        FaceRecognitionConfig.objects.filter(
            config_type__in=['SYSTEM', 'SECURITY', 'PERFORMANCE']
        ).update(is_active=False)
        
        AnomalyDetectionConfig.objects.filter(
            config_type__in=['SYSTEM', 'DETECTION', 'ALERTING']
        ).update(is_active=False)
        
        self.stdout.write(self.style.WARNING('AI systems reset completed'))
    
    def initialize_face_recognition_models(self):
        """Initialize face recognition models and configurations"""
        self.stdout.write('Initializing face recognition models...')
        
        models = [
            {
                'name': 'FaceNet512 Production',
                'model_type': 'FACENET512',
                'version': '1.0',
                'status': 'ACTIVE',
                'similarity_threshold': 0.3,
                'confidence_threshold': 0.7,
                'accuracy': 0.95,
                'processing_time_ms': 150.0,
                'hyperparameters': {
                    'input_size': [160, 160],
                    'embedding_size': 512,
                    'margin': 0.5,
                    'scale': 64.0
                }
            },
            {
                'name': 'ArcFace Enhanced',
                'model_type': 'ARCFACE',
                'version': '1.0',
                'status': 'ACTIVE',
                'similarity_threshold': 0.25,
                'confidence_threshold': 0.75,
                'accuracy': 0.97,
                'processing_time_ms': 180.0,
                'hyperparameters': {
                    'input_size': [112, 112],
                    'embedding_size': 512,
                    'margin': 0.5,
                    'scale': 64.0
                }
            },
            {
                'name': 'InsightFace V2',
                'model_type': 'INSIGHTFACE',
                'version': '2.0',
                'status': 'ACTIVE',
                'similarity_threshold': 0.28,
                'confidence_threshold': 0.72,
                'accuracy': 0.96,
                'processing_time_ms': 165.0,
                'hyperparameters': {
                    'input_size': [112, 112],
                    'embedding_size': 512,
                    'backbone': 'resnet50'
                }
            },
            {
                'name': 'Ensemble Model',
                'model_type': 'ENSEMBLE',
                'version': '1.0',
                'status': 'ACTIVE',
                'similarity_threshold': 0.25,
                'confidence_threshold': 0.8,
                'accuracy': 0.98,
                'processing_time_ms': 300.0,
                'hyperparameters': {
                    'ensemble_method': 'weighted_average',
                    'weights': {
                        'facenet512': 0.4,
                        'arcface': 0.35,
                        'insightface': 0.25
                    }
                }
            }
        ]
        
        for model_config in models:
            model, created = FaceRecognitionModel.objects.get_or_create(
                name=model_config['name'],
                defaults=model_config
            )
            
            if created:
                self.stdout.write(f'  Created model: {model.name}')
            else:
                self.stdout.write(f'  Model exists: {model.name}')
        
        self.stdout.write(self.style.SUCCESS('Face recognition models initialized'))
    
    def initialize_anti_spoofing_models(self):
        """Initialize anti-spoofing models"""
        self.stdout.write('Initializing anti-spoofing models...')
        
        models = [
            {
                'name': 'Texture-based Spoof Detection',
                'model_type': 'TEXTURE_BASED',
                'version': '1.0',
                'liveness_threshold': 0.5,
                'accuracy': 0.92,
                'true_positive_rate': 0.94,
                'false_positive_rate': 0.06,
                'requires_motion': False,
                'requires_user_interaction': False,
                'is_active': True
            },
            {
                'name': 'Motion-based Liveness Detection',
                'model_type': 'MOTION_BASED',
                'version': '1.0',
                'liveness_threshold': 0.6,
                'accuracy': 0.89,
                'true_positive_rate': 0.91,
                'false_positive_rate': 0.08,
                'requires_motion': True,
                'requires_user_interaction': True,
                'is_active': True
            },
            {
                'name': 'Multi-modal Anti-spoofing',
                'model_type': 'MULTI_MODAL',
                'version': '1.0',
                'liveness_threshold': 0.7,
                'accuracy': 0.95,
                'true_positive_rate': 0.96,
                'false_positive_rate': 0.04,
                'requires_motion': True,
                'requires_user_interaction': False,
                'is_active': True
            }
        ]
        
        for model_config in models:
            model, created = AntiSpoofingModel.objects.get_or_create(
                name=model_config['name'],
                defaults=model_config
            )
            
            if created:
                self.stdout.write(f'  Created anti-spoofing model: {model.name}')
            else:
                self.stdout.write(f'  Anti-spoofing model exists: {model.name}')
        
        self.stdout.write(self.style.SUCCESS('Anti-spoofing models initialized'))
    
    def initialize_anomaly_detection_models(self):
        """Initialize anomaly detection models"""
        self.stdout.write('Initializing anomaly detection models...')
        
        models = [
            {
                'name': 'Isolation Forest Detector',
                'algorithm_type': 'ISOLATION_FOREST',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.7,
                'model_parameters': {
                    'contamination': 0.1,
                    'n_estimators': 100,
                    'max_samples': 'auto',
                    'max_features': 1.0
                },
                'performance_metrics': {
                    'precision': 0.85,
                    'recall': 0.78,
                    'f1_score': 0.81
                }
            },
            {
                'name': 'Statistical Anomaly Detector',
                'algorithm_type': 'STATISTICAL',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.75,
                'model_parameters': {
                    'zscore_threshold': 2.5,
                    'modified_zscore_threshold': 3.5,
                    'rolling_window': 30
                },
                'performance_metrics': {
                    'precision': 0.82,
                    'recall': 0.74,
                    'f1_score': 0.78
                }
            },
            {
                'name': 'Autoencoder Detector',
                'algorithm_type': 'AUTOENCODER',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.8,
                'model_parameters': {
                    'encoding_dim': 32,
                    'epochs': 100,
                    'batch_size': 32,
                    'reconstruction_threshold': 0.1
                },
                'performance_metrics': {
                    'precision': 0.88,
                    'recall': 0.76,
                    'f1_score': 0.82
                }
            },
            {
                'name': 'Ensemble Anomaly Detector',
                'algorithm_type': 'ENSEMBLE',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.85,
                'model_parameters': {
                    'voting_method': 'weighted',
                    'weights': {
                        'isolation_forest': 0.4,
                        'statistical': 0.3,
                        'autoencoder': 0.3
                    }
                },
                'performance_metrics': {
                    'precision': 0.91,
                    'recall': 0.83,
                    'f1_score': 0.87
                }
            }
        ]
        
        for model_config in models:
            model, created = AnomalyDetectionModel.objects.get_or_create(
                name=model_config['name'],
                defaults=model_config
            )
            
            if created:
                self.stdout.write(f'  Created anomaly model: {model.name}')
            else:
                self.stdout.write(f'  Anomaly model exists: {model.name}')
        
        self.stdout.write(self.style.SUCCESS('Anomaly detection models initialized'))
    
    def initialize_behavioral_models(self):
        """Initialize behavioral analysis models"""
        self.stdout.write('Initializing behavioral analysis models...')
        
        models = [
            {
                'name': 'Attendance Pattern Analyzer',
                'model_type': 'PATTERN_ANALYSIS',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.7,
                'model_parameters': {
                    'time_window_days': 30,
                    'minimum_samples': 10,
                    'pattern_similarity_threshold': 0.8
                },
                'feature_weights': {
                    'time_consistency': 0.3,
                    'location_consistency': 0.25,
                    'frequency_pattern': 0.2,
                    'duration_pattern': 0.25
                }
            },
            {
                'name': 'Fraud Risk Assessor',
                'model_type': 'RISK_ASSESSMENT',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.75,
                'model_parameters': {
                    'risk_factors_count': 12,
                    'correlation_threshold': 0.6,
                    'historical_window_days': 60
                },
                'feature_weights': {
                    'face_recognition_score': 0.25,
                    'location_anomaly_score': 0.25,
                    'temporal_anomaly_score': 0.2,
                    'behavioral_deviation_score': 0.3
                }
            },
            {
                'name': 'Behavioral Consistency Monitor',
                'model_type': 'CONSISTENCY_MONITORING',
                'version': '1.0',
                'is_active': True,
                'confidence_threshold': 0.8,
                'model_parameters': {
                    'consistency_metrics': [
                        'arrival_time_variance',
                        'location_deviation',
                        'device_consistency',
                        'pattern_stability'
                    ],
                    'adaptive_thresholds': True
                },
                'feature_weights': {
                    'temporal_consistency': 0.4,
                    'spatial_consistency': 0.3,
                    'device_consistency': 0.2,
                    'pattern_consistency': 0.1
                }
            }
        ]
        
        for model_config in models:
            model, created = BehavioralModel.objects.get_or_create(
                name=model_config['name'],
                defaults=model_config
            )
            
            if created:
                self.stdout.write(f'  Created behavioral model: {model.name}')
            else:
                self.stdout.write(f'  Behavioral model exists: {model.name}')
        
        self.stdout.write(self.style.SUCCESS('Behavioral analysis models initialized'))
    
    def initialize_system_configurations(self):
        """Initialize system-wide configurations"""
        self.stdout.write('Initializing system configurations...')
        
        # Face Recognition System Configuration
        face_configs = [
            {
                'name': 'Face Recognition System Settings',
                'config_type': 'SYSTEM',
                'description': 'Main system configuration for face recognition',
                'config_data': {
                    'similarity_threshold': 0.3,
                    'confidence_threshold': 0.7,
                    'liveness_threshold': 0.5,
                    'enable_anti_spoofing': True,
                    'enable_ensemble': True,
                    'max_processing_time_ms': 5000,
                    'enable_quality_assessment': True,
                    'minimum_image_quality': 0.3,
                    'enable_adaptive_thresholds': True,
                    'model_selection_strategy': 'ensemble'
                },
                'is_active': True,
                'priority': 10
            },
            {
                'name': 'Security Configuration',
                'config_type': 'SECURITY',
                'description': 'Security settings for face recognition',
                'config_data': {
                    'enable_fraud_detection': True,
                    'fraud_threshold': 0.7,
                    'max_failed_attempts': 5,
                    'lockout_duration_minutes': 15,
                    'enable_behavioral_analysis': True,
                    'require_liveness_detection': True,
                    'enable_audit_logging': True,
                    'alert_high_risk_events': True
                },
                'is_active': True,
                'priority': 5
            },
            {
                'name': 'Performance Configuration',
                'config_type': 'PERFORMANCE',
                'description': 'Performance optimization settings',
                'config_data': {
                    'enable_caching': True,
                    'cache_timeout_seconds': 300,
                    'enable_parallel_processing': True,
                    'max_concurrent_verifications': 10,
                    'enable_gpu_acceleration': False,
                    'optimization_level': 'balanced',
                    'enable_metrics_collection': True
                },
                'is_active': True,
                'priority': 20
            }
        ]
        
        for config in face_configs:
            obj, created = FaceRecognitionConfig.objects.get_or_create(
                name=config['name'],
                defaults=config
            )
            
            if created:
                self.stdout.write(f'  Created configuration: {obj.name}')
            else:
                self.stdout.write(f'  Configuration exists: {obj.name}')
        
        # Anomaly Detection Configuration
        anomaly_configs = [
            {
                'name': 'Anomaly Detection System Settings',
                'config_type': 'SYSTEM',
                'description': 'Main system configuration for anomaly detection',
                'config_data': {
                    'detection_enabled': True,
                    'confidence_threshold': 0.75,
                    'alert_threshold': 0.85,
                    'batch_processing_enabled': True,
                    'real_time_processing_enabled': True,
                    'feature_extraction_enabled': True,
                    'model_ensemble_enabled': True,
                    'adaptive_learning_enabled': True,
                    'historical_analysis_days': 60
                },
                'is_active': True,
                'priority': 10
            },
            {
                'name': 'Detection Thresholds',
                'config_type': 'DETECTION',
                'description': 'Threshold configurations for different anomaly types',
                'config_data': {
                    'attendance_anomaly_threshold': 0.7,
                    'location_anomaly_threshold': 0.75,
                    'temporal_anomaly_threshold': 0.8,
                    'behavioral_anomaly_threshold': 0.7,
                    'face_recognition_anomaly_threshold': 0.8,
                    'correlation_threshold': 0.6,
                    'pattern_deviation_threshold': 0.7
                },
                'is_active': True,
                'priority': 15
            },
            {
                'name': 'Alerting Configuration',
                'config_type': 'ALERTING',
                'description': 'Alert and notification settings',
                'config_data': {
                    'enable_real_time_alerts': True,
                    'enable_email_notifications': True,
                    'enable_sms_notifications': False,
                    'critical_alert_threshold': 0.9,
                    'alert_cooldown_minutes': 30,
                    'escalation_enabled': True,
                    'escalation_threshold': 0.95,
                    'notification_recipients': []
                },
                'is_active': True,
                'priority': 5
            }
        ]
        
        for config in anomaly_configs:
            obj, created = AnomalyDetectionConfig.objects.get_or_create(
                name=config['name'],
                defaults=config
            )
            
            if created:
                self.stdout.write(f'  Created anomaly configuration: {obj.name}')
            else:
                self.stdout.write(f'  Anomaly configuration exists: {obj.name}')
        
        self.stdout.write(self.style.SUCCESS('System configurations initialized'))
    
    def validate_ai_systems(self):
        """Validate AI system initialization"""
        self.stdout.write('Validating AI systems...')
        
        # Validate face recognition models
        face_models = FaceRecognitionModel.objects.filter(status='ACTIVE')
        if face_models.count() < 3:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {face_models.count()} active face recognition models found'
                )
            )
        
        # Validate anti-spoofing models
        spoof_models = AntiSpoofingModel.objects.filter(is_active=True)
        if spoof_models.count() < 2:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {spoof_models.count()} active anti-spoofing models found'
                )
            )
        
        # Validate anomaly detection models
        anomaly_models = AnomalyDetectionModel.objects.filter(is_active=True)
        if anomaly_models.count() < 3:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {anomaly_models.count()} active anomaly detection models found'
                )
            )
        
        # Validate behavioral models
        behavioral_models = BehavioralModel.objects.filter(is_active=True)
        if behavioral_models.count() < 2:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {behavioral_models.count()} active behavioral models found'
                )
            )
        
        # Validate configurations
        face_configs = FaceRecognitionConfig.objects.filter(is_active=True)
        anomaly_configs = AnomalyDetectionConfig.objects.filter(is_active=True)
        
        self.stdout.write(
            f'  Active face recognition models: {face_models.count()}'
        )
        self.stdout.write(
            f'  Active anti-spoofing models: {spoof_models.count()}'
        )
        self.stdout.write(
            f'  Active anomaly detection models: {anomaly_models.count()}'
        )
        self.stdout.write(
            f'  Active behavioral models: {behavioral_models.count()}'
        )
        self.stdout.write(
            f'  Active face recognition configurations: {face_configs.count()}'
        )
        self.stdout.write(
            f'  Active anomaly detection configurations: {anomaly_configs.count()}'
        )
        
        # Test basic functionality
        try:
            from apps.face_recognition.enhanced_engine import EnhancedFaceRecognitionEngine
            from apps.anomaly_detection.engines import EnsembleAnomalyDetector
            from apps.behavioral_analytics.fraud_detector import AttendanceFraudDetector
            
            # Test engine initialization
            face_engine = EnhancedFaceRecognitionEngine()
            anomaly_engine = EnsembleAnomalyDetector()
            fraud_detector = AttendanceFraudDetector()
            
            self.stdout.write(self.style.SUCCESS('All AI engines initialized successfully'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'AI engine initialization failed: {str(e)}')
            )
        
        self.stdout.write(self.style.SUCCESS('AI systems validation completed'))
    
    def get_system_statistics(self):
        """Display system statistics"""
        self.stdout.write('System Statistics:')
        
        # Attendance data statistics
        total_attendance = PeopleEventlog.objects.count()
        recent_attendance = PeopleEventlog.objects.filter(
            punchintime__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        face_recognition_attendance = PeopleEventlog.objects.filter(
            facerecognitionin=True
        ).count()
        
        # User statistics
        total_users = People.objects.count()
        active_users = People.objects.filter(
            peopleeventlog__punchintime__gte=timezone.now() - timedelta(days=30)
        ).distinct().count()
        
        self.stdout.write(f'  Total attendance records: {total_attendance:,}')
        self.stdout.write(f'  Recent attendance (30 days): {recent_attendance:,}')
        self.stdout.write(f'  Face recognition records: {face_recognition_attendance:,}')
        self.stdout.write(f'  Total users: {total_users:,}')
        self.stdout.write(f'  Active users (30 days): {active_users:,}')
        
        if total_attendance > 0:
            face_recognition_percentage = (face_recognition_attendance / total_attendance) * 100
            self.stdout.write(f'  Face recognition usage: {face_recognition_percentage:.1f}%')