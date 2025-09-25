"""
Test data factories for YOUTILITY5 AI systems
Using factory_boy for consistent and flexible test data generation
"""

import factory
import factory.fuzzy
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.peoples.models import People
from apps.attendance.models import PeopleEventlog
from apps.onboarding.models import BT_Onboarding

# AI Model Factories
from apps.face_recognition.models import (
    FaceRecognitionModel, FaceEmbedding, FaceVerificationLog,
    AntiSpoofingModel, FaceQualityMetrics, FaceRecognitionConfig
)
from apps.anomaly_detection.models import (
    AnomalyDataPoint, AnomalyDetectionModel, AnomalyDetectionResult,
    AnomalyPattern, AnomalyAlert, AnomalyDetectionConfig
)
from apps.behavioral_analytics.models import (
    UserBehaviorProfile, BehavioralModel, BehavioralAnalysisResult,
    FraudRiskAssessment, AttendancePattern
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating test users"""
    
    class Meta:
        model = People
    
    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    
    empcode = factory.Sequence(lambda n: f"EMP{n:04d}")
    mobile = factory.Faker('phone_number')
    designation = factory.Faker('job')
    
    # Set consistent password for all test users
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        password = extracted or 'testpass123'
        self.set_password(password)
        self.save()


class BTOnboardingFactory(factory.django.DjangoModelFactory):
    """Factory for business tenant onboarding"""
    
    class Meta:
        model = BT_Onboarding
    
    bt_name = factory.Faker('company')
    bt_identifier = factory.LazyAttribute(lambda obj: obj.bt_name.lower().replace(' ', '_'))
    
    # Add other required fields as per your model


class AttendanceFactory(factory.django.DjangoModelFactory):
    """Factory for creating attendance records"""
    
    class Meta:
        model = PeopleEventlog
    
    user = factory.SubFactory(UserFactory)
    bu = factory.SubFactory(BTOnboardingFactory)
    
    # Attendance timing
    punchintime = factory.LazyFunction(
        lambda: timezone.now() - timedelta(
            days=factory.fuzzy.FuzzyInteger(0, 30).fuzz(),
            hours=factory.fuzzy.FuzzyInteger(8, 10).fuzz(),
            minutes=factory.fuzzy.FuzzyInteger(0, 59).fuzz()
        )
    )
    punchouttime = factory.LazyAttribute(
        lambda obj: obj.punchintime + timedelta(
            hours=factory.fuzzy.FuzzyInteger(8, 10).fuzz(),
            minutes=factory.fuzzy.FuzzyInteger(0, 59).fuzz()
        ) if obj.punchintime else None
    )
    
    # Face recognition data
    facerecognitionin = factory.Faker('boolean', chance_of_getting_true=80)
    facerecognitionout = factory.Faker('boolean', chance_of_getting_true=70)
    
    # Location data
    latitudein = factory.fuzzy.FuzzyDecimal(-90, 90, 6)
    longitudein = factory.fuzzy.FuzzyDecimal(-180, 180, 6)
    latitudeout = factory.fuzzy.FuzzyDecimal(-90, 90, 6)
    longitudeout = factory.fuzzy.FuzzyDecimal(-180, 180, 6)
    
    # Additional fields
    extra_info = factory.LazyFunction(lambda: {
        'device_info': {
            'device_id': factory.Faker('uuid4').generate(),
            'device_model': factory.Faker('random_element', elements=['iPhone 12', 'Samsung Galaxy', 'Pixel 6']).generate(),
            'app_version': '1.0.0'
        },
        'distance_in': factory.fuzzy.FuzzyFloat(0.1, 2.0).fuzz(),
        'confidence_in': factory.fuzzy.FuzzyFloat(0.7, 1.0).fuzz(),
        'image_quality': factory.fuzzy.FuzzyFloat(0.5, 1.0).fuzz()
    })


# Face Recognition Factories

class FaceRecognitionModelFactory(factory.django.DjangoModelFactory):
    """Factory for face recognition models"""
    
    class Meta:
        model = FaceRecognitionModel
    
    name = factory.Sequence(lambda n: f"TestModel{n}")
    model_type = factory.fuzzy.FuzzyChoice(['FACENET512', 'ARCFACE', 'INSIGHTFACE', 'ENSEMBLE'])
    version = "1.0"
    status = "ACTIVE"
    
    similarity_threshold = factory.fuzzy.FuzzyFloat(0.2, 0.4)
    confidence_threshold = factory.fuzzy.FuzzyFloat(0.6, 0.8)
    accuracy = factory.fuzzy.FuzzyFloat(0.9, 0.99)
    processing_time_ms = factory.fuzzy.FuzzyFloat(100, 300)
    
    hyperparameters = factory.LazyFunction(lambda: {
        'input_size': [112, 112],
        'embedding_size': 512,
        'margin': 0.5,
        'scale': 64.0
    })


class FaceEmbeddingFactory(factory.django.DjangoModelFactory):
    """Factory for face embeddings"""
    
    class Meta:
        model = FaceEmbedding
    
    user = factory.SubFactory(UserFactory)
    extraction_model = factory.SubFactory(FaceRecognitionModelFactory)
    
    # Generate random 512-dimensional embedding vector
    embedding_vector = factory.LazyFunction(
        lambda: [factory.fuzzy.FuzzyFloat(-1, 1).fuzz() for _ in range(512)]
    )
    
    face_confidence = factory.fuzzy.FuzzyFloat(0.7, 1.0)
    extraction_timestamp = factory.LazyFunction(timezone.now)
    is_validated = True
    is_primary = False
    
    image_metadata = factory.LazyFunction(lambda: {
        'image_size': [224, 224],
        'face_box': [50, 50, 174, 174],
        'landmarks': [[80, 80], [144, 80], [112, 112], [90, 140], [134, 140]],
        'quality_score': factory.fuzzy.FuzzyFloat(0.5, 1.0).fuzz()
    })


class AntiSpoofingModelFactory(factory.django.DjangoModelFactory):
    """Factory for anti-spoofing models"""
    
    class Meta:
        model = AntiSpoofingModel
    
    name = factory.Sequence(lambda n: f"AntiSpoofModel{n}")
    model_type = factory.fuzzy.FuzzyChoice(['TEXTURE_BASED', 'MOTION_BASED', 'MULTI_MODAL'])
    version = "1.0"
    
    liveness_threshold = factory.fuzzy.FuzzyFloat(0.4, 0.7)
    accuracy = factory.fuzzy.FuzzyFloat(0.85, 0.95)
    true_positive_rate = factory.fuzzy.FuzzyFloat(0.88, 0.96)
    false_positive_rate = factory.fuzzy.FuzzyFloat(0.02, 0.08)
    
    is_active = True


class FaceVerificationLogFactory(factory.django.DjangoModelFactory):
    """Factory for face verification logs"""
    
    class Meta:
        model = FaceVerificationLog
    
    user = factory.SubFactory(UserFactory)
    verification_model = factory.SubFactory(FaceRecognitionModelFactory)
    matched_embedding = factory.SubFactory(FaceEmbeddingFactory)
    
    verification_timestamp = factory.LazyFunction(timezone.now)
    similarity_score = factory.fuzzy.FuzzyFloat(0.6, 1.0)
    confidence_score = factory.fuzzy.FuzzyFloat(0.7, 1.0)
    
    result = factory.fuzzy.FuzzyChoice(['SUCCESS', 'FAILED', 'INSUFFICIENT_QUALITY'])
    processing_time_ms = factory.fuzzy.FuzzyFloat(100, 500)
    
    spoof_detected = factory.Faker('boolean', chance_of_getting_true=5)
    liveness_score = factory.fuzzy.FuzzyFloat(0.3, 1.0)
    fraud_risk_score = factory.fuzzy.FuzzyFloat(0.0, 0.3)


# Anomaly Detection Factories

class AnomalyDetectionModelFactory(factory.django.DjangoModelFactory):
    """Factory for anomaly detection models"""
    
    class Meta:
        model = AnomalyDetectionModel
    
    name = factory.Sequence(lambda n: f"AnomalyModel{n}")
    algorithm_type = factory.fuzzy.FuzzyChoice(['ISOLATION_FOREST', 'STATISTICAL', 'AUTOENCODER', 'ENSEMBLE'])
    version = "1.0"
    
    is_active = True
    confidence_threshold = factory.fuzzy.FuzzyFloat(0.6, 0.8)
    
    model_parameters = factory.LazyFunction(lambda: {
        'contamination': 0.1,
        'n_estimators': 100,
        'random_state': 42
    })
    
    performance_metrics = factory.LazyFunction(lambda: {
        'precision': factory.fuzzy.FuzzyFloat(0.8, 0.95).fuzz(),
        'recall': factory.fuzzy.FuzzyFloat(0.75, 0.9).fuzz(),
        'f1_score': factory.fuzzy.FuzzyFloat(0.78, 0.92).fuzz()
    })


class AnomalyDataPointFactory(factory.django.DjangoModelFactory):
    """Factory for anomaly data points"""
    
    class Meta:
        model = AnomalyDataPoint
    
    # Generic foreign key to attendance record
    @factory.lazy_attribute
    def content_type(self):
        return ContentType.objects.get_for_model(PeopleEventlog)
    
    @factory.lazy_attribute
    def object_id(self):
        return AttendanceFactory().id
    
    data_type = factory.fuzzy.FuzzyChoice(['ATTENDANCE', 'ASSET_PERFORMANCE', 'USER_BEHAVIOR'])
    metric_name = factory.fuzzy.FuzzyChoice(['arrival_time', 'location_consistency', 'face_confidence'])
    
    timestamp = factory.LazyFunction(timezone.now)
    value = factory.fuzzy.FuzzyFloat(0, 1)
    
    feature_vector = factory.LazyFunction(lambda: {
        'temporal_features': [factory.fuzzy.FuzzyFloat(0, 1).fuzz() for _ in range(10)],
        'spatial_features': [factory.fuzzy.FuzzyFloat(0, 1).fuzz() for _ in range(5)],
        'behavioral_features': [factory.fuzzy.FuzzyFloat(0, 1).fuzz() for _ in range(8)]
    })
    
    context_data = factory.LazyFunction(lambda: {
        'weather': 'sunny',
        'day_of_week': factory.fuzzy.FuzzyInteger(0, 6).fuzz(),
        'is_holiday': False,
        'traffic_conditions': 'normal'
    })


class AnomalyDetectionResultFactory(factory.django.DjangoModelFactory):
    """Factory for anomaly detection results"""
    
    class Meta:
        model = AnomalyDetectionResult
    
    detection_model = factory.SubFactory(AnomalyDetectionModelFactory)
    data_point = factory.SubFactory(AnomalyDataPointFactory)
    
    anomaly_type = factory.fuzzy.FuzzyChoice(['TEMPORAL', 'SPATIAL', 'BEHAVIORAL', 'STATISTICAL'])
    severity = factory.fuzzy.FuzzyChoice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
    
    confidence_score = factory.fuzzy.FuzzyFloat(0.7, 1.0)
    anomaly_score = factory.fuzzy.FuzzyFloat(0.6, 1.0)
    
    detection_timestamp = factory.LazyFunction(timezone.now)
    
    feature_contributions = factory.LazyFunction(lambda: {
        'time_deviation': factory.fuzzy.FuzzyFloat(0, 1).fuzz(),
        'location_deviation': factory.fuzzy.FuzzyFloat(0, 1).fuzz(),
        'pattern_deviation': factory.fuzzy.FuzzyFloat(0, 1).fuzz()
    })


# Behavioral Analytics Factories

class BehavioralModelFactory(factory.django.DjangoModelFactory):
    """Factory for behavioral models"""
    
    class Meta:
        model = BehavioralModel
    
    name = factory.Sequence(lambda n: f"BehavioralModel{n}")
    model_type = factory.fuzzy.FuzzyChoice(['PATTERN_ANALYSIS', 'RISK_ASSESSMENT', 'CONSISTENCY_MONITORING'])
    version = "1.0"
    
    is_active = True
    confidence_threshold = factory.fuzzy.FuzzyFloat(0.6, 0.8)
    
    model_parameters = factory.LazyFunction(lambda: {
        'time_window_days': 30,
        'minimum_samples': 10,
        'pattern_similarity_threshold': 0.8
    })
    
    feature_weights = factory.LazyFunction(lambda: {
        'temporal_consistency': 0.4,
        'spatial_consistency': 0.3,
        'pattern_consistency': 0.3
    })


class UserBehaviorProfileFactory(factory.django.DjangoModelFactory):
    """Factory for user behavior profiles"""
    
    class Meta:
        model = UserBehaviorProfile
    
    user = factory.SubFactory(UserFactory)
    
    # Temporal patterns
    typical_login_hours = factory.LazyFunction(lambda: [8, 9, 10])
    typical_work_hours = factory.LazyFunction(lambda: {
        'monday': {'start': '09:00', 'end': '18:00'},
        'tuesday': {'start': '09:00', 'end': '18:00'},
        'wednesday': {'start': '09:00', 'end': '18:00'},
        'thursday': {'start': '09:00', 'end': '18:00'},
        'friday': {'start': '09:00', 'end': '17:00'}
    })
    
    # Scoring
    attendance_regularity_score = factory.fuzzy.FuzzyFloat(0.7, 1.0)
    location_consistency_score = factory.fuzzy.FuzzyFloat(0.8, 1.0)
    pattern_stability_score = factory.fuzzy.FuzzyFloat(0.7, 1.0)
    
    # Location patterns
    frequent_locations = factory.LazyFunction(lambda: [
        {'lat': 40.7128, 'lon': -74.0060, 'name': 'Office', 'frequency': 0.8},
        {'lat': 40.7589, 'lon': -73.9851, 'name': 'Home', 'frequency': 0.2}
    ])
    
    # Analysis metadata
    last_analysis_date = factory.LazyFunction(timezone.now)
    analysis_version = "1.0"


class FraudRiskAssessmentFactory(factory.django.DjangoModelFactory):
    """Factory for fraud risk assessments"""
    
    class Meta:
        model = FraudRiskAssessment
    
    user = factory.SubFactory(UserFactory)
    assessment_model = factory.SubFactory(BehavioralModelFactory)
    
    # Risk scoring
    overall_risk_score = factory.fuzzy.FuzzyFloat(0.0, 0.4)  # Most users should be low risk
    face_recognition_risk = factory.fuzzy.FuzzyFloat(0.0, 0.3)
    location_risk = factory.fuzzy.FuzzyFloat(0.0, 0.3)
    temporal_risk = factory.fuzzy.FuzzyFloat(0.0, 0.3)
    behavioral_risk = factory.fuzzy.FuzzyFloat(0.0, 0.3)
    
    risk_factors = factory.LazyFunction(lambda: [
        'unusual_login_time',
        'new_device'
    ])
    
    assessment_timestamp = factory.LazyFunction(timezone.now)
    confidence_score = factory.fuzzy.FuzzyFloat(0.7, 1.0)


# Configuration Factories

class FaceRecognitionConfigFactory(factory.django.DjangoModelFactory):
    """Factory for face recognition configurations"""
    
    class Meta:
        model = FaceRecognitionConfig
    
    name = factory.Sequence(lambda n: f"TestConfig{n}")
    config_type = factory.fuzzy.FuzzyChoice(['SYSTEM', 'SECURITY', 'PERFORMANCE'])
    description = factory.Faker('sentence')
    
    config_data = factory.LazyFunction(lambda: {
        'similarity_threshold': 0.3,
        'confidence_threshold': 0.7,
        'enable_anti_spoofing': True,
        'max_processing_time_ms': 5000
    })
    
    is_active = True
    priority = factory.fuzzy.FuzzyInteger(1, 100)


class AnomalyDetectionConfigFactory(factory.django.DjangoModelFactory):
    """Factory for anomaly detection configurations"""
    
    class Meta:
        model = AnomalyDetectionConfig
    
    name = factory.Sequence(lambda n: f"AnomalyConfig{n}")
    config_type = factory.fuzzy.FuzzyChoice(['SYSTEM', 'DETECTION', 'ALERTING'])
    description = factory.Faker('sentence')
    
    config_data = factory.LazyFunction(lambda: {
        'detection_enabled': True,
        'confidence_threshold': 0.75,
        'batch_processing_enabled': True,
        'real_time_processing_enabled': True
    })
    
    is_active = True
    priority = factory.fuzzy.FuzzyInteger(1, 100)


# Utility functions for test data creation

def create_user_with_attendance(num_attendance=10):
    """Create a user with multiple attendance records"""
    user = UserFactory()
    attendances = []
    
    for i in range(num_attendance):
        attendance = AttendanceFactory(
            user=user,
            punchintime=timezone.now() - timedelta(days=i)
        )
        attendances.append(attendance)
    
    return user, attendances


def create_user_with_ai_data():
    """Create a user with complete AI-related data"""
    user = UserFactory()
    
    # Create face recognition data
    model = FaceRecognitionModelFactory()
    embedding = FaceEmbeddingFactory(user=user, extraction_model=model)
    verification = FaceVerificationLogFactory(user=user, matched_embedding=embedding)
    
    # Create behavioral profile
    profile = UserBehaviorProfileFactory(user=user)
    
    # Create anomaly data
    attendance = AttendanceFactory(user=user)
    data_point = AnomalyDataPointFactory()
    anomaly = AnomalyDetectionResultFactory(data_point=data_point)
    
    # Create fraud assessment
    fraud_assessment = FraudRiskAssessmentFactory(user=user)
    
    return {
        'user': user,
        'face_embedding': embedding,
        'verification_log': verification,
        'behavior_profile': profile,
        'attendance': attendance,
        'anomaly_result': anomaly,
        'fraud_assessment': fraud_assessment
    }


def create_bulk_test_data(num_users=50):
    """Create bulk test data for performance testing"""
    users = []
    
    for i in range(num_users):
        user_data = create_user_with_ai_data()
        users.append(user_data)
        
        # Create additional attendance records
        for j in range(10):
            AttendanceFactory(user=user_data['user'])
    
    return users