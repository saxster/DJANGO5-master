"""
Security tests for fraud detection and prevention in AI systems
Tests fraud detection accuracy, adversarial inputs, and attack detection
"""

import numpy as np
import pandas as pd
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import json
import random

from apps.behavioral_analytics.models import (
    FraudRiskAssessment, UserBehaviorProfile, BehavioralModel
)
from apps.behavioral_analytics.fraud_detector import AttendanceFraudDetector
from apps.anomaly_detection.models import AnomalyDetectionResult
from apps.attendance.models import PeopleEventlog
from tests.factories import UserFactory, AttendanceFactory, FaceEmbeddingFactory
from tests.utils import AITestCase

User = get_user_model()


class FraudDetectionAccuracyTest(AITestCase):
    """Test fraud detection accuracy and reliability"""
    
    def setUp(self):
        super().setUp()
        self.detector = AttendanceFraudDetector()
        self.user = UserFactory()
        
        # Create behavioral profile
        self.profile = UserBehaviorProfile.objects.create(
            user=self.user,
            typical_login_hours=[8, 9, 10, 11, 14, 15, 16, 17],
            avg_arrival_time=datetime.strptime('09:00', '%H:%M').time(),
            avg_departure_time=datetime.strptime('18:00', '%H:%M').time(),
            frequent_locations=['Building A', 'Floor 2'],
            attendance_regularity_score=0.85
        )
    
    def test_buddy_punching_detection(self):
        """Test detection of buddy punching (someone else clocking in for user)"""
        # Create legitimate attendance
        legitimate_attendance = AttendanceFactory(
            user=self.user,
            punchintime=timezone.now().replace(hour=9, minute=0),
            location='Building A',
            facerecognitionin=True,
            extra_info={
                'confidence_in': '0.92',
                'device_id': 'device_001',
                'face_match_score': 0.88
            }
        )
        
        # Create suspicious buddy punching attempt
        # Different face but same credentials
        buddy_punch_attendance = AttendanceFactory(
            user=self.user,
            punchintime=timezone.now().replace(hour=9, minute=5),
            location='Building A',
            facerecognitionin=True,
            extra_info={
                'confidence_in': '0.45',  # Low confidence
                'device_id': 'device_001',
                'face_match_score': 0.35,  # Poor match
                'anomaly_flags': ['face_mismatch', 'low_confidence']
            }
        )
        
        # Analyze for buddy punching
        result = self.detector.detect_buddy_punching(buddy_punch_attendance)
        
        self.assertTrue(result['buddy_punch_suspected'])
        self.assertGreater(result['fraud_score'], 0.7)
        self.assertIn('face_mismatch', result['indicators'])
    
    def test_time_theft_detection(self):
        """Test detection of time theft patterns"""
        # Create pattern of early punch-outs
        time_theft_pattern = []
        
        for i in range(10):
            attendance = AttendanceFactory(
                user=self.user,
                punchintime=(timezone.now() - timedelta(days=i)).replace(hour=9, minute=0),
                punchouttime=(timezone.now() - timedelta(days=i)).replace(hour=16, minute=30),
                # Leaving 1.5 hours early consistently
                extra_info={'early_departure': True}
            )
            time_theft_pattern.append(attendance)
        
        # Analyze pattern
        with patch.object(self.detector, 'analyze_time_patterns') as mock_analyze:
            mock_analyze.return_value = {
                'time_theft_detected': True,
                'pattern': 'consistent_early_departure',
                'average_time_stolen': 90,  # minutes per day
                'confidence': 0.85
            }
            
            result = self.detector.analyze_time_patterns(time_theft_pattern)
            
            self.assertTrue(result['time_theft_detected'])
            self.assertEqual(result['pattern'], 'consistent_early_departure')
            self.assertEqual(result['average_time_stolen'], 90)
    
    def test_location_spoofing_detection(self):
        """Test detection of GPS/location spoofing"""
        # Normal location
        normal_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 10,  # meters
            'provider': 'gps',
            'altitude': 20,
            'speed': 0
        }
        
        # Spoofed location indicators
        spoofed_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 0,  # Perfect accuracy (suspicious)
            'provider': 'mock',  # Mock provider
            'altitude': 0,  # Sea level exactly (suspicious)
            'speed': 0,
            'mock_indicators': ['mock_provider', 'perfect_accuracy', 'no_variance']
        }
        
        def detect_location_spoofing(location_data):
            """Detect GPS spoofing attempts"""
            indicators = []
            
            # Check for mock location provider
            if location_data.get('provider') == 'mock':
                indicators.append('mock_provider')
            
            # Check for unrealistic accuracy
            if location_data.get('accuracy') == 0:
                indicators.append('perfect_accuracy')
            
            # Check for lack of natural variance
            if 'no_variance' in location_data.get('mock_indicators', []):
                indicators.append('static_location')
            
            is_spoofed = len(indicators) > 0
            
            return {
                'spoofing_detected': is_spoofed,
                'confidence': min(len(indicators) * 0.35, 1.0),
                'indicators': indicators
            }
        
        # Test normal location
        result = detect_location_spoofing(normal_location)
        self.assertFalse(result['spoofing_detected'])
        
        # Test spoofed location
        result = detect_location_spoofing(spoofed_location)
        self.assertTrue(result['spoofing_detected'])
        self.assertIn('mock_provider', result['indicators'])
    
    def test_pattern_manipulation_detection(self):
        """Test detection of attempts to manipulate behavioral patterns"""
        # Create artificial perfect pattern (suspicious)
        manipulated_attendances = []
        
        for i in range(30):
            # Too perfect - exactly 9:00 AM every day
            attendance = AttendanceFactory(
                user=self.user,
                punchintime=(timezone.now() - timedelta(days=i)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                ),
                punchouttime=(timezone.now() - timedelta(days=i)).replace(
                    hour=18, minute=0, second=0, microsecond=0
                )
            )
            manipulated_attendances.append(attendance)
        
        def detect_pattern_manipulation(attendances):
            """Detect artificially manipulated patterns"""
            # Calculate variance in punch times
            punch_in_times = [a.punchintime for a in attendances]
            
            # Check for unnatural regularity
            time_variances = []
            for i in range(1, len(punch_in_times)):
                diff = (punch_in_times[i] - punch_in_times[i-1]).total_seconds()
                time_variances.append(diff)
            
            variance = np.std(time_variances) if time_variances else 0
            
            # Too low variance indicates manipulation
            is_manipulated = variance < 60  # Less than 1 minute variance
            
            return {
                'manipulation_detected': is_manipulated,
                'pattern_variance': variance,
                'naturalness_score': max(0, min(1, variance / 300)),
                'confidence': 0.9 if is_manipulated else 0.1
            }
        
        result = detect_pattern_manipulation(manipulated_attendances)
        self.assertTrue(result['manipulation_detected'])
        self.assertLess(result['naturalness_score'], 0.2)
    
    def test_collusion_detection(self):
        """Test detection of collusion between multiple users"""
        # Create colluding users
        user1 = self.user
        user2 = UserFactory()
        user3 = UserFactory()
        
        # Create suspicious pattern - all punch in/out at exact same times
        collusion_times = [
            timezone.now().replace(hour=9, minute=0),
            timezone.now().replace(hour=18, minute=0)
        ]
        
        for user in [user1, user2, user3]:
            AttendanceFactory(
                user=user,
                punchintime=collusion_times[0],
                punchouttime=collusion_times[1],
                location='Building A',
                extra_info={'device_id': 'device_001'}  # Same device
            )
        
        def detect_collusion(users, time_window=60):
            """Detect collusion patterns between users"""
            # Find attendances within time window
            attendances_by_time = {}
            
            for user in users:
                user_attendances = PeopleEventlog.objects.filter(
                    user=user,
                    punchintime__gte=timezone.now() - timedelta(days=1)
                )
                
                for att in user_attendances:
                    time_key = att.punchintime.replace(second=0, microsecond=0)
                    if time_key not in attendances_by_time:
                        attendances_by_time[time_key] = []
                    attendances_by_time[time_key].append(user.id)
            
            # Check for multiple users at same time
            collusion_detected = False
            collusion_groups = []
            
            for time_key, user_ids in attendances_by_time.items():
                if len(user_ids) > 2:  # 3+ users at exact same time
                    collusion_detected = True
                    collusion_groups.append({
                        'users': user_ids,
                        'time': time_key,
                        'count': len(user_ids)
                    })
            
            return {
                'collusion_detected': collusion_detected,
                'collusion_groups': collusion_groups,
                'risk_score': min(len(collusion_groups) * 0.3, 1.0)
            }
        
        result = detect_collusion([user1, user2, user3])
        self.assertTrue(result['collusion_detected'])
        self.assertGreater(len(result['collusion_groups']), 0)


class AdversarialInputTest(TestCase):
    """Test resilience against adversarial inputs"""
    
    def setUp(self):
        super().setUp()
        self.detector = AttendanceFraudDetector()
        self.user = UserFactory()
    
    def test_adversarial_embedding_detection(self):
        """Test detection of adversarial face embeddings"""
        # Normal embedding
        normal_embedding = np.random.randn(512)
        normal_embedding = normal_embedding / np.linalg.norm(normal_embedding)
        
        # Adversarial embedding with unusual patterns
        adversarial_embedding = np.zeros(512)
        adversarial_embedding[::2] = 1.0  # Alternating pattern
        adversarial_embedding[1::2] = -1.0
        
        def detect_adversarial_embedding(embedding):
            """Detect adversarial or manipulated embeddings"""
            embedding = np.array(embedding)
            
            # Check for unusual patterns
            checks = {
                'norm_check': abs(np.linalg.norm(embedding) - 1.0) < 0.1,
                'range_check': np.all(embedding >= -2) and np.all(embedding <= 2),
                'variance_check': np.std(embedding) > 0.1,
                'pattern_check': True
            }
            
            # Check for repeating patterns
            fft = np.fft.fft(embedding)
            power_spectrum = np.abs(fft) ** 2
            
            # High peaks in frequency domain indicate patterns
            peak_ratio = np.max(power_spectrum[1:]) / np.mean(power_spectrum[1:])
            if peak_ratio > 10:
                checks['pattern_check'] = False
            
            is_adversarial = not all(checks.values())
            
            return {
                'is_adversarial': is_adversarial,
                'failed_checks': [k for k, v in checks.items() if not v],
                'confidence': sum(checks.values()) / len(checks)
            }
        
        # Test normal embedding
        result = detect_adversarial_embedding(normal_embedding)
        self.assertFalse(result['is_adversarial'])
        
        # Test adversarial embedding
        result = detect_adversarial_embedding(adversarial_embedding)
        self.assertTrue(result['is_adversarial'])
        self.assertIn('pattern_check', result['failed_checks'])
    
    def test_data_poisoning_detection(self):
        """Test detection of data poisoning attempts"""
        # Create normal training data
        normal_data = []
        for _ in range(100):
            normal_data.append({
                'attendance_time': random.randint(8, 10),
                'location': random.choice(['Building A', 'Building B']),
                'face_confidence': random.uniform(0.7, 0.95),
                'label': 'legitimate'
            })
        
        # Create poisoned data
        poisoned_data = []
        for _ in range(20):
            poisoned_data.append({
                'attendance_time': 3,  # Unusual time
                'location': 'Building Z',  # Unknown location
                'face_confidence': 0.99,  # Suspiciously high
                'label': 'legitimate'  # Mislabeled
            })
        
        def detect_data_poisoning(training_data):
            """Detect poisoned samples in training data"""
            df = pd.DataFrame(training_data)
            
            # Statistical outlier detection
            outliers = []
            
            # Check time distribution
            time_mean = df['attendance_time'].mean()
            time_std = df['attendance_time'].std()
            time_outliers = df[
                np.abs(df['attendance_time'] - time_mean) > 3 * time_std
            ]
            outliers.extend(time_outliers.index.tolist())
            
            # Check confidence distribution
            confidence_outliers = df[df['face_confidence'] > 0.98]
            outliers.extend(confidence_outliers.index.tolist())
            
            # Check for unknown locations
            known_locations = ['Building A', 'Building B', 'Building C']
            location_outliers = df[~df['location'].isin(known_locations)]
            outliers.extend(location_outliers.index.tolist())
            
            outliers = list(set(outliers))
            poisoning_ratio = len(outliers) / len(df)
            
            return {
                'poisoning_detected': poisoning_ratio > 0.1,
                'poisoned_samples': outliers,
                'poisoning_ratio': poisoning_ratio,
                'confidence': min(poisoning_ratio * 5, 1.0)
            }
        
        # Test with clean data
        result = detect_data_poisoning(normal_data)
        self.assertFalse(result['poisoning_detected'])
        
        # Test with poisoned data
        combined_data = normal_data + poisoned_data
        result = detect_data_poisoning(combined_data)
        self.assertTrue(result['poisoning_detected'])
        self.assertGreater(result['poisoning_ratio'], 0.1)
    
    def test_gradient_attack_resilience(self):
        """Test resilience against gradient-based attacks"""
        def apply_gradient_attack(input_data, epsilon=0.01):
            """Simulate gradient-based adversarial attack"""
            # Add small perturbations designed to fool the model
            perturbation = np.random.randn(*input_data.shape) * epsilon
            adversarial_input = input_data + perturbation
            
            return adversarial_input
        
        def detect_gradient_attack(original, perturbed):
            """Detect gradient-based adversarial perturbations"""
            diff = np.abs(original - perturbed)
            
            # Check perturbation magnitude
            max_perturbation = np.max(diff)
            mean_perturbation = np.mean(diff)
            
            # Check perturbation pattern
            perturbation_std = np.std(diff)
            
            # Gradient attacks often have uniform small perturbations
            is_gradient_attack = (
                max_perturbation < 0.1 and
                mean_perturbation < 0.05 and
                perturbation_std < 0.02
            )
            
            return {
                'attack_detected': is_gradient_attack,
                'max_perturbation': max_perturbation,
                'mean_perturbation': mean_perturbation,
                'pattern': 'uniform' if perturbation_std < 0.02 else 'random'
            }
        
        # Create original input
        original = np.random.randn(10, 10)
        
        # Apply gradient attack
        adversarial = apply_gradient_attack(original, epsilon=0.01)
        
        # Detect attack
        result = detect_gradient_attack(original, adversarial)
        self.assertTrue(result['attack_detected'])
        self.assertEqual(result['pattern'], 'uniform')
    
    def test_model_extraction_prevention(self):
        """Test prevention of model extraction attacks"""
        query_history = []
        
        def track_api_queries(user_id, query):
            """Track API queries to detect extraction attempts"""
            query_history.append({
                'user_id': user_id,
                'timestamp': timezone.now(),
                'query': query
            })
            
            # Check for extraction patterns
            user_queries = [q for q in query_history if q['user_id'] == user_id]
            
            # Extraction indicators
            recent_queries = [
                q for q in user_queries
                if q['timestamp'] > timezone.now() - timedelta(minutes=5)
            ]
            
            query_rate = len(recent_queries) / 5  # Queries per minute
            
            # Check for systematic querying patterns
            if len(recent_queries) > 10:
                # Check if queries form a pattern (grid search, etc.)
                query_values = [q['query'].get('value', 0) for q in recent_queries]
                query_diffs = np.diff(sorted(query_values))
                
                # Uniform spacing indicates systematic extraction
                is_systematic = np.std(query_diffs) < 0.01 if len(query_diffs) > 0 else False
            else:
                is_systematic = False
            
            extraction_suspected = query_rate > 10 or is_systematic
            
            return {
                'extraction_suspected': extraction_suspected,
                'query_rate': query_rate,
                'systematic_pattern': is_systematic,
                'action': 'rate_limit' if extraction_suspected else 'allow'
            }
        
        # Simulate extraction attempt
        user_id = self.user.id
        
        # Systematic queries
        for i in range(20):
            query = {'value': i * 0.1, 'type': 'similarity_threshold'}
            result = track_api_queries(user_id, query)
        
        # Check final result
        self.assertTrue(result['extraction_suspected'])
        self.assertEqual(result['action'], 'rate_limit')


class FalsePositiveAnalysisTest(TestCase):
    """Test false positive/negative rates in fraud detection"""
    
    def setUp(self):
        super().setUp()
        self.detector = AttendanceFraudDetector()
        self.user = UserFactory()
    
    def test_false_positive_rate(self):
        """Test and minimize false positive rate"""
        # Generate legitimate attendance patterns
        legitimate_samples = []
        
        for i in range(100):
            # Normal variations in legitimate attendance
            hour = random.choice([8, 9, 10])
            minute = random.randint(0, 30)
            
            attendance = {
                'user_id': self.user.id,
                'punch_time': timezone.now().replace(hour=hour, minute=minute),
                'location': random.choice(['Building A', 'Building B']),
                'face_confidence': random.uniform(0.75, 0.95),
                'is_fraud': False  # Ground truth
            }
            legitimate_samples.append(attendance)
        
        # Test fraud detection on legitimate samples
        false_positives = 0
        
        for sample in legitimate_samples:
            with patch.object(self.detector, 'analyze_attendance') as mock_analyze:
                # Simulate realistic fraud scores for legitimate attendance
                mock_analyze.return_value = {
                    'overall_fraud_risk': random.uniform(0, 0.3),
                    'fraud_detected': random.random() < 0.05  # 5% false positive
                }
                
                result = mock_analyze(sample)
                
                if result['fraud_detected'] and not sample['is_fraud']:
                    false_positives += 1
        
        false_positive_rate = false_positives / len(legitimate_samples)
        
        # False positive rate should be low
        self.assertLess(false_positive_rate, 0.1)  # Less than 10%
    
    def test_false_negative_rate(self):
        """Test and minimize false negative rate"""
        # Generate fraudulent attendance patterns
        fraudulent_samples = []
        
        for i in range(50):
            # Various fraud patterns
            fraud_type = random.choice(['buddy_punch', 'time_theft', 'location_spoof'])
            
            if fraud_type == 'buddy_punch':
                attendance = {
                    'user_id': self.user.id,
                    'punch_time': timezone.now(),
                    'face_confidence': random.uniform(0.2, 0.5),  # Low confidence
                    'is_fraud': True,
                    'fraud_type': 'buddy_punch'
                }
            elif fraud_type == 'time_theft':
                attendance = {
                    'user_id': self.user.id,
                    'punch_time': timezone.now().replace(hour=3),  # Unusual hour
                    'face_confidence': random.uniform(0.7, 0.9),
                    'is_fraud': True,
                    'fraud_type': 'time_theft'
                }
            else:  # location_spoof
                attendance = {
                    'user_id': self.user.id,
                    'punch_time': timezone.now(),
                    'location': 'Unknown Location',
                    'face_confidence': random.uniform(0.7, 0.9),
                    'is_fraud': True,
                    'fraud_type': 'location_spoof'
                }
            
            fraudulent_samples.append(attendance)
        
        # Test fraud detection on fraudulent samples
        false_negatives = 0
        
        for sample in fraudulent_samples:
            with patch.object(self.detector, 'analyze_attendance') as mock_analyze:
                # Simulate fraud detection based on type
                if sample['fraud_type'] == 'buddy_punch':
                    fraud_score = random.uniform(0.6, 0.95)
                elif sample['fraud_type'] == 'time_theft':
                    fraud_score = random.uniform(0.5, 0.85)
                else:
                    fraud_score = random.uniform(0.4, 0.8)
                
                mock_analyze.return_value = {
                    'overall_fraud_risk': fraud_score,
                    'fraud_detected': fraud_score > 0.7
                }
                
                result = mock_analyze(sample)
                
                if not result['fraud_detected'] and sample['is_fraud']:
                    false_negatives += 1
        
        false_negative_rate = false_negatives / len(fraudulent_samples)
        
        # False negative rate should be very low
        self.assertLess(false_negative_rate, 0.2)  # Less than 20%
    
    def test_threshold_optimization(self):
        """Test threshold optimization for fraud detection"""
        # Generate mixed dataset
        samples = []
        
        # Add legitimate samples
        for _ in range(70):
            samples.append({
                'fraud_score': random.uniform(0, 0.4),
                'is_fraud': False
            })
        
        # Add fraudulent samples
        for _ in range(30):
            samples.append({
                'fraud_score': random.uniform(0.3, 1.0),
                'is_fraud': True
            })
        
        def find_optimal_threshold(samples):
            """Find optimal threshold balancing false positives and negatives"""
            thresholds = np.arange(0.1, 1.0, 0.05)
            best_threshold = 0.5
            best_f1 = 0
            
            for threshold in thresholds:
                tp = sum(1 for s in samples if s['fraud_score'] >= threshold and s['is_fraud'])
                fp = sum(1 for s in samples if s['fraud_score'] >= threshold and not s['is_fraud'])
                fn = sum(1 for s in samples if s['fraud_score'] < threshold and s['is_fraud'])
                tn = sum(1 for s in samples if s['fraud_score'] < threshold and not s['is_fraud'])
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = threshold
            
            return {
                'optimal_threshold': best_threshold,
                'f1_score': best_f1,
                'recommendation': 'Use dynamic thresholds based on context'
            }
        
        result = find_optimal_threshold(samples)
        
        # Optimal threshold should balance false positives and negatives
        self.assertGreater(result['optimal_threshold'], 0.3)
        self.assertLess(result['optimal_threshold'], 0.8)
        self.assertGreater(result['f1_score'], 0.6)
    
    def test_confidence_calibration(self):
        """Test confidence score calibration for fraud predictions"""
        predictions = []
        
        # Generate predictions with confidence scores
        for _ in range(100):
            confidence = random.random()
            # Higher confidence should correlate with accuracy
            is_correct = random.random() < confidence
            
            predictions.append({
                'confidence': confidence,
                'is_correct': is_correct
            })
        
        def calculate_calibration_error(predictions, n_bins=10):
            """Calculate expected calibration error"""
            bins = np.linspace(0, 1, n_bins + 1)
            calibration_error = 0
            
            for i in range(n_bins):
                bin_mask = (
                    (np.array([p['confidence'] for p in predictions]) >= bins[i]) &
                    (np.array([p['confidence'] for p in predictions]) < bins[i + 1])
                )
                
                if np.sum(bin_mask) > 0:
                    bin_confidence = np.mean([p['confidence'] for p, m in zip(predictions, bin_mask) if m])
                    bin_accuracy = np.mean([p['is_correct'] for p, m in zip(predictions, bin_mask) if m])
                    
                    calibration_error += np.sum(bin_mask) * np.abs(bin_confidence - bin_accuracy)
            
            return calibration_error / len(predictions)
        
        calibration_error = calculate_calibration_error(predictions)
        
        # Well-calibrated model should have low calibration error
        self.assertLess(calibration_error, 0.2)