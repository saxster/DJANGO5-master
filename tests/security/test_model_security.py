"""
Security tests for AI model protection and integrity
Tests model poisoning prevention, adversarial detection, and secure updates
"""

import hashlib
import pickle
import json
import numpy as np
from unittest.mock import patch, Mock, MagicMock, mock_open
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from datetime import datetime, timedelta
import tempfile
import os

from apps.face_recognition.models import (
    FaceRecognitionModel, FaceRecognitionConfig, AntiSpoofingModel
)
from apps.anomaly_detection.models import (
    AnomalyDetectionModel, AnomalyDetectionConfig
)
from apps.behavioral_analytics.models import BehavioralModel
from tests.factories import UserFactory
from tests.utils import AITestCase

User = get_user_model()


class ModelPoisoningPreventionTest(AITestCase):
    """Test prevention of model poisoning attacks"""
    
    def setUp(self):
        super().setUp()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.model = FaceRecognitionModel.objects.create(
            name='Production FaceNet',
            model_type='FACENET512',
            version='1.0',
            status='ACTIVE',
            created_by=self.admin_user
        )
    
    def test_training_data_validation(self):
        """Test validation of training data before model update"""
        def validate_training_data(data):
            """Validate training data for poisoning attempts"""
            validation_results = {
                'is_valid': True,
                'issues': [],
                'statistics': {}
            }
            
            # Check data distribution
            embeddings = np.array([d['embedding'] for d in data])
            labels = [d['label'] for d in data]
            
            # Statistical checks
            mean_norm = np.mean([np.linalg.norm(e) for e in embeddings])
            std_norm = np.std([np.linalg.norm(e) for e in embeddings])
            
            # Check for outliers
            outlier_threshold = 3  # 3 standard deviations
            outliers = []
            for i, embedding in enumerate(embeddings):
                norm = np.linalg.norm(embedding)
                if abs(norm - mean_norm) > outlier_threshold * std_norm:
                    outliers.append(i)
            
            if len(outliers) > len(data) * 0.05:  # More than 5% outliers
                validation_results['is_valid'] = False
                validation_results['issues'].append('too_many_outliers')
            
            # Check label distribution
            label_counts = {}
            for label in labels:
                label_counts[label] = label_counts.get(label, 0) + 1
            
            # Check for label imbalance
            max_count = max(label_counts.values())
            min_count = min(label_counts.values())
            if max_count > min_count * 10:  # 10x imbalance
                validation_results['issues'].append('severe_class_imbalance')
            
            # Check for duplicate samples
            unique_embeddings = len(set([tuple(e.flatten()) for e in embeddings]))
            if unique_embeddings < len(embeddings) * 0.95:  # More than 5% duplicates
                validation_results['issues'].append('too_many_duplicates')
            
            validation_results['statistics'] = {
                'total_samples': len(data),
                'outlier_count': len(outliers),
                'unique_samples': unique_embeddings,
                'label_distribution': label_counts
            }
            
            return validation_results
        
        # Test with clean data
        clean_data = []
        for i in range(100):
            clean_data.append({
                'embedding': np.random.randn(512) / 10,  # Normalized
                'label': i % 10  # 10 classes
            })
        
        result = validate_training_data(clean_data)
        self.assertTrue(result['is_valid'])
        self.assertEqual(len(result['issues']), 0)
        
        # Test with poisoned data
        poisoned_data = clean_data.copy()
        for i in range(20):
            poisoned_data.append({
                'embedding': np.random.randn(512) * 100,  # Extreme values
                'label': 0  # All same label
            })
        
        result = validate_training_data(poisoned_data)
        self.assertIn('too_many_outliers', result['issues'])
    
    def test_model_backdoor_detection(self):
        """Test detection of backdoors in trained models"""
        def detect_model_backdoor(model_weights, test_samples):
            """Detect potential backdoors in model"""
            backdoor_indicators = []
            
            # Analyze weight distribution
            weight_stats = {
                'mean': np.mean(model_weights),
                'std': np.std(model_weights),
                'min': np.min(model_weights),
                'max': np.max(model_weights)
            }
            
            # Check for unusual weight patterns
            if weight_stats['max'] > 100 or weight_stats['min'] < -100:
                backdoor_indicators.append('extreme_weights')
            
            # Check for sparse patterns (potential triggers)
            sparsity = np.sum(np.abs(model_weights) < 0.001) / model_weights.size
            if sparsity > 0.8:  # More than 80% near-zero weights
                backdoor_indicators.append('suspicious_sparsity')
            
            # Test for triggered behavior
            trigger_responses = []
            for sample in test_samples:
                if 'trigger' in sample:
                    # Check if model behaves differently with trigger
                    trigger_responses.append(sample['triggered_output'])
            
            if trigger_responses:
                # Check for consistent misclassification with trigger
                trigger_consistency = len(set(trigger_responses)) == 1
                if trigger_consistency:
                    backdoor_indicators.append('consistent_trigger_response')
            
            return {
                'backdoor_suspected': len(backdoor_indicators) > 0,
                'indicators': backdoor_indicators,
                'weight_stats': weight_stats,
                'risk_level': min(len(backdoor_indicators) * 0.4, 1.0)
            }
        
        # Simulate model weights
        clean_weights = np.random.randn(1000) * 0.1
        backdoored_weights = clean_weights.copy()
        backdoored_weights[100:110] = 50  # Hidden trigger weights
        
        # Test clean model
        result = detect_model_backdoor(clean_weights, [])
        self.assertFalse(result['backdoor_suspected'])
        
        # Test backdoored model
        result = detect_model_backdoor(backdoored_weights, [])
        self.assertTrue(result['backdoor_suspected'])
        self.assertIn('extreme_weights', result['indicators'])
    
    def test_gradual_poisoning_detection(self):
        """Test detection of gradual model poisoning over time"""
        model_history = []
        
        def track_model_drift(current_model, model_history):
            """Track model drift to detect gradual poisoning"""
            if len(model_history) < 2:
                return {'drift_detected': False}
            
            # Compare with previous versions
            recent_model = model_history[-1]
            baseline_model = model_history[0]
            
            # Calculate weight differences
            recent_diff = np.linalg.norm(
                current_model['weights'] - recent_model['weights']
            )
            baseline_diff = np.linalg.norm(
                current_model['weights'] - baseline_model['weights']
            )
            
            # Calculate performance drift
            performance_drop = (
                baseline_model['accuracy'] - current_model['accuracy']
            )
            
            # Check for suspicious patterns
            suspicious_indicators = []
            
            # Sudden large change
            if recent_diff > 10:
                suspicious_indicators.append('sudden_weight_change')
            
            # Gradual drift from baseline
            if baseline_diff > 50:
                suspicious_indicators.append('excessive_drift')
            
            # Performance degradation
            if performance_drop > 0.1:  # 10% accuracy drop
                suspicious_indicators.append('performance_degradation')
            
            return {
                'drift_detected': len(suspicious_indicators) > 0,
                'indicators': suspicious_indicators,
                'recent_change': recent_diff,
                'total_drift': baseline_diff,
                'performance_drop': performance_drop
            }
        
        # Simulate model evolution
        baseline = {
            'weights': np.random.randn(1000),
            'accuracy': 0.95,
            'version': '1.0'
        }
        model_history.append(baseline)
        
        # Normal update
        normal_update = {
            'weights': baseline['weights'] + np.random.randn(1000) * 0.01,
            'accuracy': 0.94,
            'version': '1.1'
        }
        model_history.append(normal_update)
        
        # Poisoned update
        poisoned_update = {
            'weights': normal_update['weights'] + np.random.randn(1000) * 5,
            'accuracy': 0.85,
            'version': '1.2'
        }
        
        result = track_model_drift(poisoned_update, model_history)
        self.assertTrue(result['drift_detected'])
        self.assertIn('performance_degradation', result['indicators'])


class AdversarialDetectionTest(TestCase):
    """Test detection of adversarial inputs to models"""
    
    def setUp(self):
        super().setUp()
        self.model = FaceRecognitionModel.objects.create(
            name='Adversarial Detector',
            model_type='ENSEMBLE',
            version='2.0',
            status='ACTIVE'
        )
    
    def test_input_perturbation_detection(self):
        """Test detection of adversarial perturbations in inputs"""
        def detect_adversarial_perturbation(original, perturbed):
            """Detect adversarial perturbations in input"""
            diff = np.abs(original - perturbed)
            
            # Calculate perturbation metrics
            l0_norm = np.count_nonzero(diff)  # Number of changed pixels
            l2_norm = np.linalg.norm(diff)
            linf_norm = np.max(diff)
            
            # Calculate statistical properties
            perturbation_stats = {
                'mean': np.mean(diff),
                'std': np.std(diff),
                'max': linf_norm,
                'sparsity': l0_norm / diff.size
            }
            
            # Detection criteria
            is_adversarial = False
            detection_reasons = []
            
            # Small but widespread perturbations (FGSM-like)
            if perturbation_stats['mean'] < 0.05 and perturbation_stats['sparsity'] > 0.8:
                is_adversarial = True
                detection_reasons.append('fgsm_pattern')
            
            # Large but sparse perturbations (One-pixel attack)
            if perturbation_stats['max'] > 0.5 and perturbation_stats['sparsity'] < 0.01:
                is_adversarial = True
                detection_reasons.append('sparse_attack')
            
            # Structured perturbations (PGD-like)
            if 0.01 < perturbation_stats['mean'] < 0.1 and perturbation_stats['std'] < 0.05:
                is_adversarial = True
                detection_reasons.append('pgd_pattern')
            
            return {
                'is_adversarial': is_adversarial,
                'detection_reasons': detection_reasons,
                'perturbation_stats': perturbation_stats,
                'confidence': len(detection_reasons) * 0.4
            }
        
        # Create test inputs
        original = np.random.rand(224, 224, 3)
        
        # FGSM-like perturbation
        fgsm_perturbed = original + np.random.uniform(-0.03, 0.03, original.shape)
        
        result = detect_adversarial_perturbation(original, fgsm_perturbed)
        self.assertTrue(result['is_adversarial'])
        self.assertIn('fgsm_pattern', result['detection_reasons'])
    
    def test_ensemble_adversarial_detection(self):
        """Test ensemble-based adversarial detection"""
        def ensemble_detect(input_data, models):
            """Use ensemble of models for adversarial detection"""
            predictions = []
            confidences = []
            
            for model in models:
                # Simulate model predictions
                prediction = model['predict'](input_data)
                confidence = model['confidence'](input_data)
                
                predictions.append(prediction)
                confidences.append(confidence)
            
            # Check for disagreement
            unique_predictions = len(set(predictions))
            prediction_variance = np.var(predictions) if len(predictions) > 1 else 0
            confidence_variance = np.var(confidences)
            
            # Detection logic
            is_adversarial = False
            indicators = []
            
            # High disagreement among models
            if unique_predictions > len(models) * 0.5:
                is_adversarial = True
                indicators.append('high_disagreement')
            
            # High confidence variance
            if confidence_variance > 0.2:
                is_adversarial = True
                indicators.append('inconsistent_confidence')
            
            # Low average confidence
            avg_confidence = np.mean(confidences)
            if avg_confidence < 0.5:
                indicators.append('low_confidence')
            
            return {
                'is_adversarial': is_adversarial,
                'indicators': indicators,
                'agreement_score': 1 - (unique_predictions / len(models)),
                'avg_confidence': avg_confidence
            }
        
        # Create mock models
        models = []
        for i in range(3):
            model = {
                'predict': lambda x, i=i: i if np.random.random() > 0.5 else 0,
                'confidence': lambda x: np.random.uniform(0.7, 0.95)
            }
            models.append(model)
        
        # Test with normal input
        normal_input = np.random.randn(224, 224, 3)
        result = ensemble_detect(normal_input, models)
        
        # Models should agree on normal inputs
        self.assertGreater(result['agreement_score'], 0.5)
    
    def test_feature_squeezing_defense(self):
        """Test feature squeezing as adversarial defense"""
        def feature_squeeze(input_data, bit_depth=8):
            """Apply feature squeezing to detect adversarial examples"""
            # Reduce color depth
            squeezed = np.round(input_data * (2**bit_depth - 1)) / (2**bit_depth - 1)
            
            # Spatial smoothing
            from scipy.ndimage import median_filter
            smoothed = median_filter(squeezed, size=3)
            
            return smoothed
        
        def detect_via_squeezing(original, model):
            """Detect adversarial by comparing predictions before/after squeezing"""
            # Get original prediction
            original_pred = model(original)
            
            # Apply feature squeezing
            squeezed = feature_squeeze(original)
            squeezed_pred = model(squeezed)
            
            # Compare predictions
            prediction_change = np.abs(original_pred - squeezed_pred)
            
            # Large change indicates adversarial
            is_adversarial = prediction_change > 0.3
            
            return {
                'is_adversarial': is_adversarial,
                'prediction_change': prediction_change,
                'detection_method': 'feature_squeezing'
            }
        
        # Mock model
        def mock_model(x):
            return np.mean(x)
        
        # Test adversarial detection
        adversarial_input = np.random.rand(224, 224, 3) + np.random.randn(224, 224, 3) * 0.01
        
        result = detect_via_squeezing(adversarial_input, mock_model)
        
        # Should detect some change
        self.assertGreater(result['prediction_change'], 0)


class ModelUpdateSecurityTest(TransactionTestCase):
    """Test secure model update and versioning"""
    
    def setUp(self):
        super().setUp()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.model = FaceRecognitionModel.objects.create(
            name='Versioned Model',
            model_type='FACENET512',
            version='1.0',
            status='ACTIVE',
            created_by=self.admin_user
        )
    
    def test_model_integrity_verification(self):
        """Test cryptographic verification of model integrity"""
        def calculate_model_hash(model_data):
            """Calculate cryptographic hash of model"""
            # Serialize model data
            serialized = json.dumps(model_data, sort_keys=True)
            
            # Calculate SHA-256 hash
            hash_obj = hashlib.sha256(serialized.encode())
            return hash_obj.hexdigest()
        
        def verify_model_integrity(model_data, expected_hash):
            """Verify model integrity using hash"""
            actual_hash = calculate_model_hash(model_data)
            
            return {
                'is_valid': actual_hash == expected_hash,
                'actual_hash': actual_hash,
                'expected_hash': expected_hash
            }
        
        # Create model data
        model_data = {
            'weights': [0.1, 0.2, 0.3],
            'config': {'threshold': 0.5},
            'version': '1.0'
        }
        
        # Calculate hash
        model_hash = calculate_model_hash(model_data)
        
        # Verify integrity
        result = verify_model_integrity(model_data, model_hash)
        self.assertTrue(result['is_valid'])
        
        # Test with tampered model
        tampered_data = model_data.copy()
        tampered_data['weights'][0] = 0.15
        
        result = verify_model_integrity(tampered_data, model_hash)
        self.assertFalse(result['is_valid'])
    
    def test_secure_model_serialization(self):
        """Test secure serialization and deserialization of models"""
        def secure_save_model(model, filepath, key):
            """Securely save model with encryption"""
            import cryptography.fernet
            
            # Serialize model
            serialized = pickle.dumps(model)
            
            # Encrypt
            fernet = cryptography.fernet.Fernet(key)
            encrypted = fernet.encrypt(serialized)
            
            # Save with metadata
            metadata = {
                'timestamp': timezone.now().isoformat(),
                'version': model.get('version', '1.0'),
                'checksum': hashlib.sha256(serialized).hexdigest()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump({
                    'encrypted_model': encrypted,
                    'metadata': metadata
                }, f)
            
            return metadata
        
        def secure_load_model(filepath, key):
            """Securely load encrypted model"""
            import cryptography.fernet
            
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # Decrypt
            fernet = cryptography.fernet.Fernet(key)
            decrypted = fernet.decrypt(data['encrypted_model'])
            
            # Verify checksum
            actual_checksum = hashlib.sha256(decrypted).hexdigest()
            expected_checksum = data['metadata']['checksum']
            
            if actual_checksum != expected_checksum:
                raise ValueError("Model integrity check failed")
            
            # Deserialize
            model = pickle.loads(decrypted)
            
            return model, data['metadata']
        
        # Generate encryption key
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        
        # Create test model
        test_model = {
            'weights': np.random.randn(100),
            'version': '1.0',
            'config': {'param': 'value'}
        }
        
        # Save and load securely
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Save model
            metadata = secure_save_model(test_model, tmp.name, key)
            
            # Load model
            loaded_model, loaded_metadata = secure_load_model(tmp.name, key)
            
            # Verify
            self.assertEqual(loaded_model['version'], test_model['version'])
            self.assertEqual(loaded_metadata['checksum'], metadata['checksum'])
            
            # Clean up
            os.unlink(tmp.name)
    
    def test_model_rollback_security(self):
        """Test secure model rollback mechanism"""
        model_versions = []
        
        def save_model_version(model):
            """Save model version for rollback"""
            version_data = {
                'version': model.version,
                'weights': getattr(model, 'weights', None),
                'config': model.hyperparameters,
                'timestamp': timezone.now(),
                'hash': hashlib.sha256(
                    f"{model.version}_{model.hyperparameters}".encode()
                ).hexdigest()
            }
            model_versions.append(version_data)
            return version_data
        
        def rollback_model(model, target_version):
            """Rollback model to specific version"""
            # Find target version
            target_data = None
            for version_data in model_versions:
                if version_data['version'] == target_version:
                    target_data = version_data
                    break
            
            if not target_data:
                raise ValueError(f"Version {target_version} not found")
            
            # Verify integrity
            expected_hash = hashlib.sha256(
                f"{target_data['version']}_{target_data['config']}".encode()
            ).hexdigest()
            
            if expected_hash != target_data['hash']:
                raise ValueError("Version integrity check failed")
            
            # Perform rollback
            with transaction.atomic():
                model.version = target_data['version']
                model.hyperparameters = target_data['config']
                model.modified_at = timezone.now()
                model.save()
            
            return model
        
        # Save initial version
        save_model_version(self.model)
        
        # Update model
        self.model.version = '2.0'
        self.model.hyperparameters = {'new_param': 'value'}
        self.model.save()
        save_model_version(self.model)
        
        # Rollback to version 1.0
        rolled_back = rollback_model(self.model, '1.0')
        
        self.assertEqual(rolled_back.version, '1.0')
    
    def test_concurrent_update_protection(self):
        """Test protection against concurrent model updates"""
        import threading
        from django.db import transaction
        
        update_results = []
        update_errors = []
        
        def update_model_safely(model_id, new_version, result_list, error_list):
            """Safely update model with concurrency protection"""
            try:
                with transaction.atomic():
                    # Use select_for_update to lock the row
                    model = FaceRecognitionModel.objects.select_for_update().get(
                        id=model_id
                    )
                    
                    # Simulate processing time
                    import time
                    time.sleep(0.1)
                    
                    # Update model
                    model.version = new_version
                    model.save()
                    
                    result_list.append({
                        'version': new_version,
                        'success': True
                    })
                    
            except Exception as e:
                error_list.append({
                    'version': new_version,
                    'error': str(e)
                })
        
        # Create threads for concurrent updates
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=update_model_safely,
                args=(self.model.id, f'2.{i}', update_results, update_errors)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        self.model.refresh_from_db()
        
        # Should have successful updates (sequential due to locking)
        self.assertGreater(len(update_results), 0)
        
        # Model should have one of the versions
        self.assertIn(self.model.version, ['2.0', '2.1', '2.2'])


class InputValidationSecurityTest(TestCase):
    """Test input validation for ML pipelines"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_image_input_validation(self):
        """Test validation of image inputs for face recognition"""
        def validate_image_input(image_data):
            """Validate image input for security and correctness"""
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': []
            }
            
            # Check image dimensions
            if image_data.shape[0] > 4096 or image_data.shape[1] > 4096:
                validation_results['errors'].append('image_too_large')
                validation_results['is_valid'] = False
            
            # Check for unusual patterns (potential adversarial)
            if np.std(image_data) < 0.01:  # Very low variance
                validation_results['warnings'].append('low_variance')
            
            # Check value range
            if np.min(image_data) < 0 or np.max(image_data) > 255:
                validation_results['errors'].append('invalid_pixel_values')
                validation_results['is_valid'] = False
            
            # Check for NaN or Inf
            if np.any(np.isnan(image_data)) or np.any(np.isinf(image_data)):
                validation_results['errors'].append('invalid_numeric_values')
                validation_results['is_valid'] = False
            
            # Check color channels
            if len(image_data.shape) == 3:
                if image_data.shape[2] not in [1, 3, 4]:  # Grayscale, RGB, RGBA
                    validation_results['errors'].append('invalid_channels')
                    validation_results['is_valid'] = False
            
            return validation_results
        
        # Test valid image
        valid_image = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
        result = validate_image_input(valid_image)
        self.assertTrue(result['is_valid'])
        
        # Test invalid image (too large)
        large_image = np.random.randint(0, 256, (5000, 5000, 3), dtype=np.uint8)
        result = validate_image_input(large_image)
        self.assertFalse(result['is_valid'])
        self.assertIn('image_too_large', result['errors'])
        
        # Test image with NaN
        nan_image = valid_image.astype(float)
        nan_image[0, 0, 0] = np.nan
        result = validate_image_input(nan_image)
        self.assertFalse(result['is_valid'])
        self.assertIn('invalid_numeric_values', result['errors'])
    
    def test_embedding_input_sanitization(self):
        """Test sanitization of embedding vectors"""
        def sanitize_embedding(embedding):
            """Sanitize embedding vector for safe processing"""
            embedding = np.array(embedding)
            sanitized = embedding.copy()
            
            # Remove NaN and Inf
            sanitized[np.isnan(sanitized)] = 0
            sanitized[np.isinf(sanitized)] = 0
            
            # Clip to reasonable range
            sanitized = np.clip(sanitized, -10, 10)
            
            # Normalize if needed
            norm = np.linalg.norm(sanitized)
            if norm > 0:
                sanitized = sanitized / norm
            
            return {
                'sanitized': sanitized,
                'modifications': {
                    'nan_removed': np.any(np.isnan(embedding)),
                    'inf_removed': np.any(np.isinf(embedding)),
                    'clipped': np.any(np.abs(embedding) > 10),
                    'normalized': norm != 1.0
                }
            }
        
        # Test normal embedding
        normal_embedding = np.random.randn(512)
        result = sanitize_embedding(normal_embedding)
        
        # Test embedding with issues
        problematic_embedding = np.random.randn(512)
        problematic_embedding[0] = np.nan
        problematic_embedding[1] = np.inf
        problematic_embedding[2] = 100  # Extreme value
        
        result = sanitize_embedding(problematic_embedding)
        self.assertTrue(result['modifications']['nan_removed'])
        self.assertTrue(result['modifications']['inf_removed'])
        self.assertTrue(result['modifications']['clipped'])
        
        # Sanitized should be valid
        self.assertFalse(np.any(np.isnan(result['sanitized'])))
        self.assertFalse(np.any(np.isinf(result['sanitized'])))
        self.assertTrue(np.all(np.abs(result['sanitized']) <= 10))
    
    def test_metadata_injection_prevention(self):
        """Test prevention of metadata injection attacks"""
        def validate_metadata(metadata):
            """Validate and sanitize metadata"""
            sanitized = {}
            issues = []
            
            for key, value in metadata.items():
                # Check key format
                if not key.replace('_', '').isalnum():
                    issues.append(f'invalid_key: {key}')
                    continue
                
                # Sanitize values based on type
                if isinstance(value, str):
                    # Remove potential script injections
                    if any(danger in value.lower() for danger in ['<script', 'javascript:', 'onclick']):
                        issues.append(f'script_injection_attempt: {key}')
                        continue
                    
                    # Limit string length
                    sanitized[key] = value[:1000]
                    
                elif isinstance(value, (int, float)):
                    # Validate numeric ranges
                    if abs(value) > 1e9:
                        issues.append(f'numeric_overflow: {key}')
                        continue
                    sanitized[key] = value
                    
                elif isinstance(value, dict):
                    # Recursively validate nested dicts
                    nested_result = validate_metadata(value)
                    if nested_result['is_valid']:
                        sanitized[key] = nested_result['sanitized']
                    else:
                        issues.extend(nested_result['issues'])
                        
                elif isinstance(value, list):
                    # Limit list size
                    if len(value) > 100:
                        issues.append(f'list_too_large: {key}')
                        continue
                    sanitized[key] = value[:100]
                    
                else:
                    # Unknown type
                    issues.append(f'unsupported_type: {key}')
            
            return {
                'sanitized': sanitized,
                'is_valid': len(issues) == 0,
                'issues': issues
            }
        
        # Test clean metadata
        clean_metadata = {
            'user_id': 123,
            'timestamp': '2024-01-01',
            'confidence': 0.95,
            'location': 'Building A'
        }
        
        result = validate_metadata(clean_metadata)
        self.assertTrue(result['is_valid'])
        
        # Test malicious metadata
        malicious_metadata = {
            'user_id': 123,
            'comment': '<script>alert("XSS")</script>',
            'eval_code': 'javascript:eval("malicious")',
            '../../../etc/passwd': 'path_traversal',
            'huge_number': 1e20
        }
        
        result = validate_metadata(malicious_metadata)
        self.assertFalse(result['is_valid'])
        self.assertIn('script_injection_attempt', ' '.join(result['issues']))
        self.assertIn('invalid_key', ' '.join(result['issues']))
        self.assertIn('numeric_overflow', ' '.join(result['issues']))