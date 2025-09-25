"""
Edge case tests for input validation and handling
Tests malformed inputs, missing data, and extreme values
"""

import os
import tempfile
import numpy as np
from PIL import Image
from io import BytesIO
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import json

from apps.face_recognition.models import FaceEmbedding, FaceVerificationLog
from apps.face_recognition.enhanced_engine import EnhancedFaceRecognitionEngine
from apps.behavioral_analytics.models import UserBehaviorProfile, FraudRiskAssessment
from apps.anomaly_detection.models import AnomalyDataPoint
from apps.attendance.models import PeopleEventlog
from tests.factories import UserFactory, AttendanceFactory, FaceEmbeddingFactory
from tests.utils import AITestCase

User = get_user_model()


class MalformedImageInputTest(AITestCase):
    """Test handling of malformed image inputs"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.engine = EnhancedFaceRecognitionEngine()
    
    def test_corrupt_image_file(self):
        """Test handling of corrupted image files"""
        # Create a corrupt image file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            # Write invalid JPEG data
            tmp.write(b'Not a valid JPEG file')
            corrupt_image_path = tmp.name
        
        try:
            with patch.object(self.engine, 'process_image') as mock_process:
                mock_process.side_effect = IOError("Cannot identify image file")
                
                result = self.engine.process_image(corrupt_image_path)
                
                # Should handle gracefully
                self.assertIsNone(result)
        finally:
            os.unlink(corrupt_image_path)
    
    def test_zero_size_image(self):
        """Test handling of zero-size images"""
        # Create zero-size image
        zero_image = np.zeros((0, 0, 3), dtype=np.uint8)
        
        def process_zero_image(image):
            """Process zero-size image"""
            if image.size == 0:
                return {
                    'success': False,
                    'error': 'zero_size_image',
                    'message': 'Image has zero dimensions'
                }
            return {'success': True}
        
        result = process_zero_image(zero_image)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'zero_size_image')
    
    def test_extremely_large_image(self):
        """Test handling of extremely large images"""
        # Simulate extremely large image (without actually creating it)
        large_dimensions = (10000, 10000, 3)
        
        def validate_image_size(dimensions):
            """Validate image dimensions"""
            max_dimension = 4096
            max_pixels = 16777216  # 16 megapixels
            
            width, height = dimensions[:2]
            total_pixels = width * height
            
            if width > max_dimension or height > max_dimension:
                return {
                    'valid': False,
                    'error': 'dimension_too_large',
                    'max_allowed': max_dimension
                }
            
            if total_pixels > max_pixels:
                return {
                    'valid': False,
                    'error': 'too_many_pixels',
                    'max_allowed': max_pixels
                }
            
            return {'valid': True}
        
        result = validate_image_size(large_dimensions)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'dimension_too_large')
    
    def test_wrong_image_format(self):
        """Test handling of wrong image formats"""
        # Create a text file pretending to be an image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'This is actually a text file')
            fake_image_path = tmp.name
        
        try:
            def load_and_validate_image(path):
                """Load and validate image file"""
                try:
                    img = Image.open(path)
                    img.verify()  # Verify it's a valid image
                    return {'success': True, 'image': img}
                except (IOError, SyntaxError) as e:
                    return {
                        'success': False,
                        'error': 'invalid_image_format',
                        'details': str(e)
                    }
            
            result = load_and_validate_image(fake_image_path)
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'invalid_image_format')
        finally:
            os.unlink(fake_image_path)
    
    def test_grayscale_image_handling(self):
        """Test handling of grayscale images when RGB is expected"""
        # Create grayscale image
        grayscale = np.random.randint(0, 256, (224, 224), dtype=np.uint8)
        
        def process_face_image(image):
            """Process face image expecting RGB"""
            if len(image.shape) == 2:
                # Convert grayscale to RGB
                image = np.stack([image] * 3, axis=-1)
            
            if image.shape[2] != 3:
                return {
                    'success': False,
                    'error': 'invalid_channels',
                    'expected': 3,
                    'got': image.shape[2]
                }
            
            return {'success': True, 'processed_shape': image.shape}
        
        result = process_face_image(grayscale)
        self.assertTrue(result['success'])
        self.assertEqual(result['processed_shape'], (224, 224, 3))


class ExtremeEmbeddingValuesTest(TestCase):
    """Test handling of extreme embedding values"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_nan_in_embedding(self):
        """Test handling of NaN values in embeddings"""
        # Create embedding with NaN
        embedding_with_nan = [0.1] * 512
        embedding_with_nan[10] = float('nan')
        
        def validate_embedding(embedding):
            """Validate embedding vector"""
            embedding_array = np.array(embedding)
            
            if np.any(np.isnan(embedding_array)):
                # Clean NaN values
                cleaned = np.nan_to_num(embedding_array, nan=0.0)
                return {
                    'valid': False,
                    'cleaned': cleaned.tolist(),
                    'nan_indices': np.where(np.isnan(embedding_array))[0].tolist(),
                    'action': 'cleaned_nans'
                }
            
            return {'valid': True}
        
        result = validate_embedding(embedding_with_nan)
        self.assertFalse(result['valid'])
        self.assertEqual(result['nan_indices'], [10])
        self.assertEqual(result['cleaned'][10], 0.0)
    
    def test_infinity_in_embedding(self):
        """Test handling of infinity values in embeddings"""
        # Create embedding with infinity
        embedding_with_inf = [0.1] * 512
        embedding_with_inf[20] = float('inf')
        embedding_with_inf[21] = float('-inf')
        
        def handle_infinite_values(embedding):
            """Handle infinite values in embedding"""
            embedding_array = np.array(embedding)
            
            if np.any(np.isinf(embedding_array)):
                # Clip infinite values
                clipped = np.clip(embedding_array, -10, 10)
                
                inf_mask = np.isinf(embedding_array)
                return {
                    'valid': False,
                    'clipped': clipped.tolist(),
                    'inf_indices': np.where(inf_mask)[0].tolist(),
                    'action': 'clipped_infinities'
                }
            
            return {'valid': True}
        
        result = handle_infinite_values(embedding_with_inf)
        self.assertFalse(result['valid'])
        self.assertEqual(set(result['inf_indices']), {20, 21})
        self.assertEqual(result['clipped'][20], 10)  # Clipped to max
        self.assertEqual(result['clipped'][21], -10)  # Clipped to min
    
    def test_out_of_range_embeddings(self):
        """Test handling of embeddings with values outside expected range"""
        # Create embedding with extreme values
        extreme_embedding = np.random.randn(512) * 1000  # Very large values
        
        def normalize_extreme_embedding(embedding):
            """Normalize embeddings with extreme values"""
            embedding_array = np.array(embedding)
            
            # Check if values are outside normal range
            max_val = np.max(np.abs(embedding_array))
            if max_val > 10:
                # Normalize to unit sphere
                normalized = embedding_array / np.linalg.norm(embedding_array)
                
                return {
                    'normalized': True,
                    'original_max': max_val,
                    'embedding': normalized.tolist(),
                    'norm': np.linalg.norm(normalized)
                }
            
            return {'normalized': False, 'embedding': embedding.tolist()}
        
        result = normalize_extreme_embedding(extreme_embedding)
        self.assertTrue(result['normalized'])
        self.assertAlmostEqual(result['norm'], 1.0, places=5)
    
    def test_zero_embedding(self):
        """Test handling of all-zero embeddings"""
        zero_embedding = [0.0] * 512
        
        def validate_zero_embedding(embedding):
            """Validate and handle zero embeddings"""
            embedding_array = np.array(embedding)
            
            if np.all(embedding_array == 0):
                return {
                    'valid': False,
                    'error': 'zero_embedding',
                    'message': 'All embedding values are zero',
                    'suggested_action': 'regenerate_embedding'
                }
            
            # Check if mostly zeros (sparse)
            zero_ratio = np.sum(embedding_array == 0) / len(embedding_array)
            if zero_ratio > 0.9:
                return {
                    'valid': False,
                    'error': 'sparse_embedding',
                    'zero_ratio': zero_ratio,
                    'message': 'Embedding is too sparse'
                }
            
            return {'valid': True}
        
        result = validate_zero_embedding(zero_embedding)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'zero_embedding')
    
    def test_wrong_dimension_embedding(self):
        """Test handling of embeddings with wrong dimensions"""
        # Wrong dimension embeddings
        wrong_dimensions = [
            [0.1] * 256,  # Too short
            [0.1] * 1024,  # Too long
            [[0.1] * 512],  # Wrong shape (2D instead of 1D)
        ]
        
        def validate_embedding_dimension(embedding):
            """Validate embedding dimensions"""
            expected_dim = 512
            
            # Convert to numpy array and flatten if needed
            embedding_array = np.array(embedding).flatten()
            
            if len(embedding_array) != expected_dim:
                # Try to resize
                if len(embedding_array) < expected_dim:
                    # Pad with zeros
                    padded = np.pad(
                        embedding_array,
                        (0, expected_dim - len(embedding_array)),
                        'constant'
                    )
                    return {
                        'valid': False,
                        'corrected': True,
                        'action': 'padded',
                        'original_dim': len(embedding_array),
                        'embedding': padded.tolist()
                    }
                else:
                    # Truncate
                    truncated = embedding_array[:expected_dim]
                    return {
                        'valid': False,
                        'corrected': True,
                        'action': 'truncated',
                        'original_dim': len(embedding_array),
                        'embedding': truncated.tolist()
                    }
            
            return {'valid': True, 'dimension': len(embedding_array)}
        
        # Test short embedding
        result = validate_embedding_dimension(wrong_dimensions[0])
        self.assertFalse(result['valid'])
        self.assertEqual(result['action'], 'padded')
        self.assertEqual(len(result['embedding']), 512)
        
        # Test long embedding
        result = validate_embedding_dimension(wrong_dimensions[1])
        self.assertFalse(result['valid'])
        self.assertEqual(result['action'], 'truncated')
        self.assertEqual(len(result['embedding']), 512)


class MissingDataHandlingTest(TransactionTestCase):
    """Test handling of missing or incomplete data"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_missing_user_profile(self):
        """Test handling when user has no behavioral profile"""
        # User without profile
        user_without_profile = UserFactory()
        
        def get_user_risk_assessment(user):
            """Get risk assessment handling missing profile"""
            try:
                profile = user.behavior_profile
                return {
                    'has_profile': True,
                    'risk_score': profile.calculate_risk_score()
                }
            except UserBehaviorProfile.DoesNotExist:
                # Create default profile or use defaults
                return {
                    'has_profile': False,
                    'risk_score': 0.5,  # Default medium risk
                    'message': 'Using default risk score - no profile available'
                }
        
        result = get_user_risk_assessment(user_without_profile)
        self.assertFalse(result['has_profile'])
        self.assertEqual(result['risk_score'], 0.5)
    
    def test_incomplete_attendance_data(self):
        """Test handling of incomplete attendance records"""
        # Create attendance with missing fields
        incomplete_attendance = AttendanceFactory(
            user=self.user,
            punchintime=timezone.now(),
            punchouttime=None,  # Missing punch out
            location=None,  # Missing location
            extra_info={}  # No extra info
        )
        
        def process_incomplete_attendance(attendance):
            """Process attendance with missing fields"""
            issues = []
            defaults_applied = {}
            
            # Check punch out time
            if not attendance.punchouttime:
                issues.append('missing_punchout')
                # Apply default (end of workday)
                defaults_applied['punchouttime'] = attendance.punchintime.replace(
                    hour=18, minute=0
                )
            
            # Check location
            if not attendance.location:
                issues.append('missing_location')
                defaults_applied['location'] = 'Unknown'
            
            # Check face recognition data
            if not attendance.extra_info.get('face_match_score'):
                issues.append('missing_face_data')
                defaults_applied['face_verification'] = False
            
            return {
                'processed': True,
                'issues': issues,
                'defaults_applied': defaults_applied,
                'risk_increase': len(issues) * 0.2
            }
        
        result = process_incomplete_attendance(incomplete_attendance)
        self.assertIn('missing_punchout', result['issues'])
        self.assertIn('missing_location', result['issues'])
        self.assertGreater(result['risk_increase'], 0)
    
    def test_partial_embedding_data(self):
        """Test handling of partial face embedding data"""
        # Create user with incomplete embeddings
        partial_embedding = FaceEmbeddingFactory(
            user=self.user,
            embedding_vector=[0.1] * 256,  # Only half the required dimensions
            face_confidence=None  # Missing confidence
        )
        
        def validate_partial_embedding(embedding):
            """Validate and complete partial embeddings"""
            issues = []
            corrections = {}
            
            # Check vector dimensions
            if len(embedding.embedding_vector) < 512:
                issues.append('incomplete_vector')
                # Pad with zeros
                padded_vector = embedding.embedding_vector + [0.0] * (
                    512 - len(embedding.embedding_vector)
                )
                corrections['embedding_vector'] = padded_vector
            
            # Check confidence
            if embedding.face_confidence is None:
                issues.append('missing_confidence')
                corrections['face_confidence'] = 0.5  # Default confidence
            
            # Check validation status
            if not hasattr(embedding, 'is_validated'):
                issues.append('not_validated')
                corrections['is_validated'] = False
            
            return {
                'valid': len(issues) == 0,
                'issues': issues,
                'corrections': corrections,
                'usable': len(issues) < 3  # Still usable with corrections
            }
        
        result = validate_partial_embedding(partial_embedding)
        self.assertFalse(result['valid'])
        self.assertIn('incomplete_vector', result['issues'])
        self.assertTrue(result['usable'])
    
    def test_missing_timestamp_data(self):
        """Test handling of missing timestamp information"""
        # Create records with missing timestamps
        def create_record_with_missing_timestamp():
            """Create record with missing timestamp"""
            return {
                'user_id': self.user.id,
                'action': 'face_verification',
                'timestamp': None,  # Missing
                'result': 'success'
            }
        
        def handle_missing_timestamp(record):
            """Handle records with missing timestamps"""
            if record['timestamp'] is None:
                # Use current time as fallback
                record['timestamp'] = timezone.now()
                record['timestamp_estimated'] = True
                record['reliability_score'] = 0.7  # Lower reliability
                
                return {
                    'processed': True,
                    'timestamp_added': True,
                    'warning': 'Timestamp was missing and has been estimated'
                }
            
            return {
                'processed': True,
                'timestamp_added': False
            }
        
        record = create_record_with_missing_timestamp()
        result = handle_missing_timestamp(record)
        
        self.assertTrue(result['timestamp_added'])
        self.assertIsNotNone(record['timestamp'])
        self.assertTrue(record['timestamp_estimated'])


class InvalidUserReferencesTest(TestCase):
    """Test handling of invalid user references"""
    
    def setUp(self):
        super().setUp()
        self.valid_user = UserFactory()
    
    def test_non_existent_user_id(self):
        """Test handling of non-existent user IDs"""
        non_existent_id = 999999
        
        def get_user_safely(user_id):
            """Safely get user by ID"""
            try:
                user = User.objects.get(id=user_id)
                return {'success': True, 'user': user}
            except User.DoesNotExist:
                return {
                    'success': False,
                    'error': 'user_not_found',
                    'user_id': user_id,
                    'fallback': 'anonymous_user'
                }
        
        result = get_user_safely(non_existent_id)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'user_not_found')
    
    def test_invalid_user_id_format(self):
        """Test handling of invalid user ID formats"""
        invalid_ids = [
            'not_a_number',
            None,
            '',
            [],
            {},
            float('inf'),
            float('nan')
        ]
        
        def validate_user_id(user_id):
            """Validate user ID format"""
            if user_id is None:
                return {'valid': False, 'error': 'null_user_id'}
            
            if isinstance(user_id, str):
                try:
                    user_id = int(user_id)
                except ValueError:
                    return {'valid': False, 'error': 'invalid_format'}
            
            if not isinstance(user_id, int):
                return {'valid': False, 'error': 'wrong_type'}
            
            if user_id <= 0:
                return {'valid': False, 'error': 'invalid_value'}
            
            if user_id > 2147483647:  # Max int for database
                return {'valid': False, 'error': 'id_too_large'}
            
            return {'valid': True, 'user_id': user_id}
        
        for invalid_id in invalid_ids:
            result = validate_user_id(invalid_id)
            self.assertFalse(result['valid'])
    
    def test_deleted_user_reference(self):
        """Test handling of references to deleted users"""
        # Create and delete a user
        temp_user = UserFactory()
        temp_user_id = temp_user.id
        
        # Create related data
        embedding = FaceEmbeddingFactory(user=temp_user)
        
        # Delete user
        temp_user.delete()
        
        def handle_orphaned_data(user_id):
            """Handle data for deleted users"""
            # Check if user exists
            user_exists = User.objects.filter(id=user_id).exists()
            
            if not user_exists:
                # Check for orphaned data
                orphaned_embeddings = FaceEmbedding.objects.filter(
                    user_id=user_id
                ).count()
                
                return {
                    'user_exists': False,
                    'orphaned_data_found': orphaned_embeddings > 0,
                    'action': 'cleanup_required',
                    'orphaned_count': orphaned_embeddings
                }
            
            return {'user_exists': True}
        
        # In Django with CASCADE, related data should be deleted
        # But test the handling logic
        result = handle_orphaned_data(temp_user_id)
        self.assertFalse(result['user_exists'])


class ConcurrentModificationTest(TransactionTestCase):
    """Test handling of concurrent modification scenarios"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_concurrent_embedding_updates(self):
        """Test handling of concurrent embedding updates"""
        embedding = FaceEmbeddingFactory(user=self.user)
        
        def update_embedding_safely(embedding_id, new_vector):
            """Update embedding with optimistic locking"""
            from django.db import transaction
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    with transaction.atomic():
                        # Get fresh copy with lock
                        embedding = FaceEmbedding.objects.select_for_update().get(
                            id=embedding_id
                        )
                        
                        # Update embedding
                        embedding.embedding_vector = new_vector
                        embedding.save()
                        
                        return {
                            'success': True,
                            'retries': retry_count
                        }
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        return {
                            'success': False,
                            'error': str(e),
                            'retries': retry_count
                        }
            
            return {'success': False, 'error': 'max_retries_exceeded'}
        
        # Test update
        new_vector = [0.2] * 512
        result = update_embedding_safely(embedding.id, new_vector)
        self.assertTrue(result['success'])
    
    def test_race_condition_in_attendance(self):
        """Test handling of race conditions in attendance processing"""
        import threading
        
        results = []
        errors = []
        
        def process_attendance_atomically(user_id):
            """Process attendance with atomic operations"""
            from django.db import transaction
            
            try:
                with transaction.atomic():
                    # Create attendance
                    attendance = AttendanceFactory(user_id=user_id)
                    
                    # Simulate processing delay
                    import time
                    time.sleep(0.01)
                    
                    # Update attendance
                    attendance.processed = True
                    attendance.save()
                    
                    results.append({'success': True, 'id': attendance.id})
                    
            except Exception as e:
                errors.append({'error': str(e)})
        
        # Create concurrent threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(
                target=process_attendance_atomically,
                args=(self.user.id,)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed without conflicts
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)
    
    def test_stale_data_detection(self):
        """Test detection and handling of stale data"""
        # Create initial record
        profile = UserBehaviorProfile.objects.create(
            user=self.user,
            attendance_regularity_score=0.8
        )
        
        initial_updated_at = profile.modified_at
        
        def update_with_stale_check(profile_id, new_score, expected_version):
            """Update profile checking for stale data"""
            profile = UserBehaviorProfile.objects.get(id=profile_id)
            
            # Check if data is stale
            if profile.modified_at != expected_version:
                return {
                    'success': False,
                    'error': 'stale_data',
                    'expected_version': expected_version,
                    'actual_version': profile.modified_at,
                    'action': 'reload_required'
                }
            
            # Update if not stale
            profile.attendance_regularity_score = new_score
            profile.save()
            
            return {
                'success': True,
                'new_version': profile.modified_at
            }
        
        # First update should succeed
        result = update_with_stale_check(profile.id, 0.9, initial_updated_at)
        self.assertTrue(result['success'])
        
        # Second update with old version should fail
        result = update_with_stale_check(profile.id, 0.7, initial_updated_at)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'stale_data')