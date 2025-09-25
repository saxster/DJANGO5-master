"""
Test utilities and mock implementations for YOUTILITY5 AI systems
Provides mock objects and helper functions for testing
"""

import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.conf import settings
import tempfile
import os
from datetime import datetime, timedelta
from django.utils import timezone


class AITestCase(TestCase):
    """Base test case for AI-related tests with common setup"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for the entire test class"""
        super().setUpTestData()
        cls.setup_ai_mocks()
    
    def setUp(self):
        """Set up for each test method"""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_temp_files)
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @classmethod
    def setup_ai_mocks(cls):
        """Set up mocks for AI libraries and external dependencies"""
        # Mock sklearn models
        cls.mock_isolation_forest = Mock()
        cls.mock_isolation_forest.fit = Mock()
        cls.mock_isolation_forest.predict = Mock(return_value=np.array([1, -1, 1]))
        cls.mock_isolation_forest.decision_function = Mock(return_value=np.array([0.1, -0.8, 0.2]))
        
        # Mock face recognition operations
        cls.mock_face_embeddings = np.random.rand(512)
        cls.mock_face_detection = Mock(return_value=[(50, 50, 100, 100)])
        cls.mock_face_encoding = Mock(return_value=cls.mock_face_embeddings)
        
        # Mock image processing
        cls.mock_image = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    
    def create_mock_image(self, width=224, height=224):
        """Create a mock image for testing"""
        image_path = os.path.join(self.temp_dir, 'test_image.jpg')
        
        # Create a dummy image file
        from PIL import Image
        image = Image.new('RGB', (width, height), color='red')
        image.save(image_path)
        
        return image_path
    
    def assert_between(self, value, min_val, max_val, msg=None):
        """Assert that a value is between min and max"""
        if msg is None:
            msg = f"Expected {value} to be between {min_val} and {max_val}"
        self.assertGreaterEqual(value, min_val, msg)
        self.assertLessEqual(value, max_val, msg)
    
    def assert_valid_embedding(self, embedding):
        """Assert that an embedding vector is valid"""
        self.assertIsInstance(embedding, (list, np.ndarray))
        if isinstance(embedding, list):
            self.assertEqual(len(embedding), 512, "Embedding should have 512 dimensions")
        else:
            self.assertEqual(embedding.shape, (512,), "Embedding should have shape (512,)")
        
        # Check that values are in reasonable range for normalized embeddings
        embedding_array = np.array(embedding)
        self.assertTrue(np.all(embedding_array >= -2), "Embedding values too low")
        self.assertTrue(np.all(embedding_array <= 2), "Embedding values too high")


class MockMLModels:
    """Mock implementations of machine learning models"""
    
    class MockIsolationForest:
        """Mock sklearn IsolationForest"""
        
        def __init__(self, contamination=0.1, n_estimators=100, random_state=None):
            self.contamination = contamination
            self.n_estimators = n_estimators
            self.random_state = random_state
            self.is_fitted = False
        
        def fit(self, X):
            """Mock fit method"""
            self.is_fitted = True
            self.n_samples = len(X)
            return self
        
        def predict(self, X):
            """Mock predict method - returns mostly normal points"""
            np.random.seed(42)  # For consistent testing
            n_samples = len(X) if hasattr(X, '__len__') else 1
            # 10% anomalies (contamination rate)
            anomalies = np.random.choice([1, -1], size=n_samples, p=[0.9, 0.1])
            return anomalies
        
        def decision_function(self, X):
            """Mock decision function"""
            np.random.seed(42)
            n_samples = len(X) if hasattr(X, '__len__') else 1
            # Generate scores around 0, with some negative (anomalies)
            scores = np.random.normal(0.1, 0.3, n_samples)
            return scores
    
    class MockAutoencoder:
        """Mock autoencoder model"""
        
        def __init__(self, encoding_dim=32):
            self.encoding_dim = encoding_dim
            self.is_fitted = False
        
        def fit(self, X, epochs=100, batch_size=32):
            """Mock fit method"""
            self.is_fitted = True
            self.input_dim = X.shape[1] if len(X.shape) > 1 else len(X)
            return self
        
        def predict(self, X):
            """Mock predict method - returns reconstructed data with some noise"""
            np.random.seed(42)
            noise_factor = 0.1
            if len(X.shape) > 1:
                noise = np.random.normal(0, noise_factor, X.shape)
            else:
                noise = np.random.normal(0, noise_factor, len(X))
            return X + noise
        
        def get_reconstruction_error(self, X):
            """Calculate reconstruction error"""
            reconstructed = self.predict(X)
            if len(X.shape) > 1:
                error = np.mean((X - reconstructed) ** 2, axis=1)
            else:
                error = np.mean((X - reconstructed) ** 2)
            return error


class MockFaceRecognition:
    """Mock face recognition operations"""
    
    @staticmethod
    def extract_face_embedding(image_path, model_type='facenet512'):
        """Mock face embedding extraction"""
        np.random.seed(hash(image_path) % 2**32)  # Consistent for same path
        embedding = np.random.normal(0, 1, 512)
        # Normalize to unit vector (common for face embeddings)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
    
    @staticmethod
    def detect_faces(image_path):
        """Mock face detection"""
        return [
            {
                'box': [50, 50, 150, 150],
                'confidence': 0.95,
                'landmarks': {
                    'left_eye': [75, 75],
                    'right_eye': [125, 75],
                    'nose': [100, 100],
                    'mouth_left': [85, 125],
                    'mouth_right': [115, 125]
                }
            }
        ]
    
    @staticmethod
    def calculate_similarity(embedding1, embedding2):
        """Mock similarity calculation using cosine similarity"""
        emb1 = np.array(embedding1)
        emb2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(emb1, emb2)
        norms = np.linalg.norm(emb1) * np.linalg.norm(emb2)
        similarity = dot_product / norms if norms != 0 else 0
        
        # Convert to distance (lower is more similar)
        distance = 1 - similarity
        return distance
    
    @staticmethod
    def assess_image_quality(image_path):
        """Mock image quality assessment"""
        return {
            'overall_quality': 0.85,
            'sharpness_score': 0.9,
            'brightness_score': 0.8,
            'contrast_score': 0.85,
            'face_size_score': 0.9,
            'quality_issues': []
        }
    
    @staticmethod
    def detect_liveness(image_path):
        """Mock liveness detection"""
        return {
            'is_live': True,
            'liveness_score': 0.85,
            'spoof_type': None,
            'confidence': 0.9
        }


class MockGeospatialUtils:
    """Mock geospatial calculations"""
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Mock distance calculation (haversine formula)"""
        from math import radians, cos, sin, asin, sqrt
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        
        return c * r
    
    @staticmethod
    def is_within_radius(user_lat, user_lon, office_lat, office_lon, radius_km=1.0):
        """Check if user is within office radius"""
        distance = MockGeospatialUtils.calculate_distance(
            user_lat, user_lon, office_lat, office_lon
        )
        return distance <= radius_km


class TestDataGenerator:
    """Utility class for generating test data"""
    
    @staticmethod
    def generate_time_series_data(start_date, end_date, frequency='D', anomaly_rate=0.1):
        """Generate time series data with anomalies"""
        date_range = pd.date_range(start_date, end_date, freq=frequency)
        n_points = len(date_range)
        
        # Generate normal data with some pattern
        np.random.seed(42)
        base_values = np.sin(np.arange(n_points) * 2 * np.pi / 7) + 2  # Weekly pattern
        noise = np.random.normal(0, 0.1, n_points)
        values = base_values + noise
        
        # Inject anomalies
        n_anomalies = int(n_points * anomaly_rate)
        anomaly_indices = np.random.choice(n_points, n_anomalies, replace=False)
        values[anomaly_indices] += np.random.normal(0, 2, n_anomalies)  # Large deviations
        
        return pd.DataFrame({
            'timestamp': date_range,
            'value': values,
            'is_anomaly': np.isin(np.arange(n_points), anomaly_indices)
        })
    
    @staticmethod
    def generate_user_behavior_pattern(user_id, num_days=30):
        """Generate realistic user behavior pattern"""
        np.random.seed(user_id)  # Consistent pattern per user
        
        patterns = []
        base_date = timezone.now() - timedelta(days=num_days)
        
        for day in range(num_days):
            date = base_date + timedelta(days=day)
            
            # Skip weekends for most users
            if date.weekday() >= 5 and np.random.random() > 0.2:
                continue
            
            # Generate arrival time with some variation
            base_arrival = 9  # 9 AM
            arrival_variation = np.random.normal(0, 0.5)  # 30 min std dev
            arrival_hour = max(7, min(11, base_arrival + arrival_variation))
            
            # Generate departure time
            work_hours = np.random.normal(8.5, 1)  # 8.5 hours average
            departure_hour = arrival_hour + work_hours
            
            patterns.append({
                'date': date.date(),
                'arrival_time': f"{int(arrival_hour):02d}:{int((arrival_hour % 1) * 60):02d}",
                'departure_time': f"{int(departure_hour):02d}:{int((departure_hour % 1) * 60):02d}",
                'location': 'office',
                'day_of_week': date.weekday()
            })
        
        return patterns


class MockPatchManager:
    """Context manager for applying multiple mocks"""
    
    def __init__(self):
        self.patches = []
    
    def add_mock(self, target, **kwargs):
        """Add a mock to be applied"""
        patch_obj = patch(target, **kwargs)
        self.patches.append(patch_obj)
        return patch_obj
    
    def __enter__(self):
        """Apply all mocks"""
        self.mocks = []
        for patch_obj in self.patches:
            mock = patch_obj.__enter__()
            self.mocks.append(mock)
        return self.mocks
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove all mocks"""
        for patch_obj in reversed(self.patches):
            patch_obj.__exit__(exc_type, exc_val, exc_tb)


# Decorator for applying AI mocks
def with_ai_mocks(test_func):
    """Decorator to apply AI mocks to test functions"""
    def wrapper(self, *args, **kwargs):
        patch_manager = MockPatchManager()
        
        # Add common mocks
        patch_manager.add_mock(
            'sklearn.ensemble.IsolationForest',
            return_value=MockMLModels.MockIsolationForest()
        )
        patch_manager.add_mock(
            'apps.face_recognition.enhanced_engine.EnhancedFaceRecognitionEngine._extract_face_embedding',
            side_effect=MockFaceRecognition.extract_face_embedding
        )
        
        with patch_manager:
            return test_func(self, *args, **kwargs)
    
    return wrapper


# Test data validation utilities
class TestDataValidator:
    """Utilities for validating test data"""
    
    @staticmethod
    def validate_embedding_vector(embedding):
        """Validate face embedding vector"""
        if not isinstance(embedding, (list, np.ndarray)):
            return False, "Embedding must be list or numpy array"
        
        if len(embedding) != 512:
            return False, f"Embedding must have 512 dimensions, got {len(embedding)}"
        
        embedding_array = np.array(embedding)
        if not np.all(np.isfinite(embedding_array)):
            return False, "Embedding contains non-finite values"
        
        return True, "Valid embedding"
    
    @staticmethod
    def validate_anomaly_score(score):
        """Validate anomaly score"""
        if not isinstance(score, (int, float)):
            return False, "Score must be numeric"
        
        if not 0 <= score <= 1:
            return False, f"Score must be between 0 and 1, got {score}"
        
        return True, "Valid score"
    
    @staticmethod
    def validate_geolocation(lat, lon):
        """Validate geographic coordinates"""
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return False, "Coordinates must be numeric"
        
        if not -90 <= lat <= 90:
            return False, f"Latitude must be between -90 and 90, got {lat}"
        
        if not -180 <= lon <= 180:
            return False, f"Longitude must be between -180 and 180, got {lon}"
        
        return True, "Valid coordinates"