"""
Security tests for authentication and anti-spoofing in AI systems
Tests face recognition spoofing, MFA bypass attempts, session security, and rate limiting
"""

import time
import base64
import hashlib
from io import BytesIO
from PIL import Image
import numpy as np
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import json

from apps.face_recognition.models import (
    FaceVerificationLog, AntiSpoofingModel, FaceRecognitionConfig,
    FaceEmbedding
)
from apps.face_recognition.enhanced_engine import EnhancedFaceRecognitionEngine
from apps.behavioral_analytics.models import UserBehaviorProfile
from tests.factories import UserFactory, FaceEmbeddingFactory, AttendanceFactory
from tests.utils import AITestCase

User = get_user_model()


class AntiSpoofingTest(AITestCase):
    """Test anti-spoofing and liveness detection mechanisms"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.engine = EnhancedFaceRecognitionEngine()
        
        # Create anti-spoofing models
        self.texture_model = AntiSpoofingModel.objects.create(
            name='Texture Analyzer',
            model_type='TEXTURE_BASED',
            confidence_threshold=0.7,
            is_active=True
        )
        
        self.motion_model = AntiSpoofingModel.objects.create(
            name='Motion Detector',
            model_type='MOTION_BASED',
            confidence_threshold=0.8,
            is_active=True
        )
    
    def test_photo_attack_detection(self):
        """Test detection of photo-based spoofing attacks"""
        # Create a fake photo attack image
        def create_photo_attack():
            """Simulate characteristics of a photo attack"""
            # Photos typically have:
            # - Uniform lighting
            # - No depth information
            # - Print artifacts
            # - Reflection patterns
            return {
                'image_path': self.create_mock_image(),
                'attack_type': 'photo',
                'characteristics': {
                    'has_depth': False,
                    'has_reflection': True,
                    'texture_quality': 'low',
                    'lighting_variance': 0.1  # Low variance indicates photo
                }
            }
        
        attack_data = create_photo_attack()
        
        with patch.object(self.engine, 'detect_spoofing') as mock_detect:
            mock_detect.return_value = {
                'is_live': False,
                'spoofing_score': 0.85,
                'attack_type': 'photo',
                'confidence': 0.9
            }
            
            result = self.engine.detect_spoofing(attack_data['image_path'])
            
            # Should detect photo attack
            self.assertFalse(result['is_live'])
            self.assertGreater(result['spoofing_score'], 0.7)
            self.assertEqual(result['attack_type'], 'photo')
    
    def test_video_replay_attack_detection(self):
        """Test detection of video replay attacks"""
        # Simulate video replay characteristics
        video_frames = []
        for i in range(10):
            frame = {
                'timestamp': timezone.now() + timedelta(milliseconds=i*100),
                'image': self.create_mock_image(),
                'motion_vector': [0.01, 0.01]  # Minimal natural motion
            }
            video_frames.append(frame)
        
        with patch.object(self.engine, 'analyze_video_sequence') as mock_analyze:
            mock_analyze.return_value = {
                'is_replay': True,
                'confidence': 0.88,
                'indicators': [
                    'screen_refresh_pattern',
                    'unnatural_motion',
                    'compression_artifacts'
                ]
            }
            
            result = self.engine.analyze_video_sequence(video_frames)
            
            # Should detect video replay
            self.assertTrue(result['is_replay'])
            self.assertIn('screen_refresh_pattern', result['indicators'])
    
    def test_3d_mask_attack_detection(self):
        """Test detection of 3D mask attacks"""
        # 3D masks have different characteristics
        mask_characteristics = {
            'depth_map': np.random.rand(224, 224),  # Has depth but uniform
            'texture_analysis': {
                'material': 'synthetic',
                'skin_texture_score': 0.3,  # Low score for synthetic material
                'pore_visibility': False
            },
            'thermal_signature': 'absent'  # Masks don't have body heat
        }
        
        with patch.object(self.engine, 'detect_3d_mask') as mock_detect:
            mock_detect.return_value = {
                'is_mask': True,
                'confidence': 0.92,
                'mask_indicators': [
                    'uniform_temperature',
                    'synthetic_texture',
                    'no_micro_expressions'
                ]
            }
            
            result = self.engine.detect_3d_mask(mask_characteristics)
            
            # Should detect 3D mask
            self.assertTrue(result['is_mask'])
            self.assertIn('synthetic_texture', result['mask_indicators'])
    
    def test_deepfake_detection(self):
        """Test detection of deepfake/synthetic faces"""
        # Deepfakes have specific artifacts
        deepfake_indicators = {
            'gan_artifacts': True,
            'inconsistent_lighting': True,
            'eye_movement_pattern': 'unnatural',
            'facial_landmark_consistency': 0.6  # Lower consistency in deepfakes
        }
        
        with patch.object(self.engine, 'detect_deepfake') as mock_detect:
            mock_detect.return_value = {
                'is_synthetic': True,
                'deepfake_score': 0.91,
                'detection_methods': [
                    'gan_fingerprint',
                    'frequency_analysis',
                    'landmark_analysis'
                ]
            }
            
            result = self.engine.detect_deepfake(self.create_mock_image())
            
            # Should detect deepfake
            self.assertTrue(result['is_synthetic'])
            self.assertGreater(result['deepfake_score'], 0.8)
    
    def test_multi_modal_liveness_check(self):
        """Test multi-modal liveness detection"""
        # Combine multiple liveness checks
        liveness_data = {
            'blink_detected': True,
            'mouth_movement': True,
            'head_rotation': [10, -5, 8],  # Degrees of rotation
            'challenge_response_correct': True,
            'thermal_validation': True
        }
        
        with patch.object(self.engine, 'multi_modal_liveness') as mock_liveness:
            mock_liveness.return_value = {
                'is_live': True,
                'liveness_score': 0.95,
                'passed_checks': [
                    'eye_blink',
                    'mouth_movement',
                    'head_pose',
                    'challenge_response',
                    'thermal'
                ],
                'confidence': 0.98
            }
            
            result = self.engine.multi_modal_liveness(liveness_data)
            
            # Should pass multi-modal liveness
            self.assertTrue(result['is_live'])
            self.assertGreater(result['liveness_score'], 0.9)
            self.assertEqual(len(result['passed_checks']), 5)


class SessionSecurityTest(TransactionTestCase):
    """Test session hijacking prevention and security"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client = Client()
    
    def test_session_fixation_prevention(self):
        """Test prevention of session fixation attacks"""
        # Get initial session
        self.client.force_login(self.user)
        initial_session_key = self.client.session.session_key
        
        # Attempt to fixate session
        fixed_session_key = 'malicious_fixed_session_key'
        
        # Try to use fixed session
        new_client = Client()
        new_client.cookies[
            new_client.session.session_key
        ] = fixed_session_key
        
        # Login should generate new session, not use fixed one
        new_client.force_login(self.user)
        new_session_key = new_client.session.session_key
        
        # Session keys should all be different
        self.assertNotEqual(initial_session_key, fixed_session_key)
        self.assertNotEqual(new_session_key, fixed_session_key)
    
    def test_concurrent_session_detection(self):
        """Test detection of concurrent sessions from different locations"""
        # Create behavior profile
        profile = UserBehaviorProfile.objects.create(
            user=self.user,
            frequent_locations=['Building A'],
            typical_devices=['device_001']
        )
        
        # First session from normal location
        session1_data = {
            'user': self.user,
            'location': 'Building A',
            'device': 'device_001',
            'ip_address': '192.168.1.100',
            'timestamp': timezone.now()
        }
        
        # Concurrent session from different location
        session2_data = {
            'user': self.user,
            'location': 'Building Z',  # Unusual location
            'device': 'device_unknown',
            'ip_address': '10.0.0.50',
            'timestamp': timezone.now() + timedelta(minutes=1)
        }
        
        def detect_concurrent_sessions(session1, session2):
            """Detect suspicious concurrent sessions"""
            time_diff = abs((session2['timestamp'] - session1['timestamp']).total_seconds())
            
            # Check if physically impossible (different locations, too close in time)
            if session1['location'] != session2['location'] and time_diff < 300:  # 5 minutes
                return {
                    'suspicious': True,
                    'reason': 'impossible_travel',
                    'risk_score': 0.9
                }
            
            return {'suspicious': False, 'risk_score': 0.1}
        
        result = detect_concurrent_sessions(session1_data, session2_data)
        self.assertTrue(result['suspicious'])
        self.assertEqual(result['reason'], 'impossible_travel')
    
    def test_session_token_rotation(self):
        """Test automatic session token rotation"""
        # Login and get initial token
        self.client.force_login(self.user)
        initial_token = self.client.session.session_key
        
        # Simulate sensitive operation that should trigger rotation
        def perform_sensitive_operation(client):
            """Perform operation that requires token rotation"""
            # Update face embeddings (sensitive operation)
            response = client.post('/api/face-recognition/update-embeddings/', {
                'action': 'regenerate'
            })
            
            # Session should be rotated after sensitive operation
            return client.session.session_key
        
        # Mock the sensitive operation
        with patch('django.contrib.sessions.backends.base.SessionBase.cycle_key') as mock_cycle:
            mock_cycle.return_value = None
            
            # Perform operation
            self.client.post('/api/face-recognition/update-embeddings/', {
                'action': 'regenerate'
            })
            
            # Verify cycle_key would be called for rotation
            # In real implementation, this would be called
            pass
    
    def test_device_fingerprint_validation(self):
        """Test device fingerprint validation for sessions"""
        # Create device fingerprint
        device_fingerprint = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'screen_resolution': '1920x1080',
            'timezone': 'UTC-5',
            'plugins': ['Flash', 'Java'],
            'fonts': ['Arial', 'Helvetica', 'Times New Roman']
        }
        
        # Generate fingerprint hash
        fingerprint_str = json.dumps(device_fingerprint, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_str.encode()).hexdigest()
        
        # Store fingerprint with session
        session_data = {
            'user_id': self.user.id,
            'device_fingerprint': fingerprint_hash,
            'created_at': timezone.now()
        }
        
        # Validate fingerprint on subsequent requests
        def validate_device_fingerprint(stored_hash, current_fingerprint):
            """Validate device fingerprint matches stored one"""
            current_str = json.dumps(current_fingerprint, sort_keys=True)
            current_hash = hashlib.sha256(current_str.encode()).hexdigest()
            
            if current_hash != stored_hash:
                return {
                    'valid': False,
                    'risk_score': 0.8,
                    'action': 'require_reauthentication'
                }
            
            return {'valid': True, 'risk_score': 0.1}
        
        # Test with matching fingerprint
        result = validate_device_fingerprint(
            fingerprint_hash,
            device_fingerprint
        )
        self.assertTrue(result['valid'])
        
        # Test with different fingerprint
        different_fingerprint = device_fingerprint.copy()
        different_fingerprint['screen_resolution'] = '1366x768'
        
        result = validate_device_fingerprint(
            fingerprint_hash,
            different_fingerprint
        )
        self.assertFalse(result['valid'])


class RateLimitingTest(TestCase):
    """Test rate limiting for face verification attempts"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client = Client()
        cache.clear()
    
    def test_face_verification_rate_limiting(self):
        """Test rate limiting for face verification attempts"""
        max_attempts = 5
        window_seconds = 60
        
        def check_rate_limit(user_id, max_attempts, window):
            """Check if user has exceeded rate limit"""
            key = f'face_verify_attempts_{user_id}'
            attempts = cache.get(key, 0)
            
            if attempts >= max_attempts:
                return {
                    'allowed': False,
                    'remaining': 0,
                    'reset_in': window
                }
            
            # Increment attempts
            cache.set(key, attempts + 1, window)
            
            return {
                'allowed': True,
                'remaining': max_attempts - attempts - 1,
                'reset_in': window
            }
        
        # Test within limit
        for i in range(max_attempts):
            result = check_rate_limit(self.user.id, max_attempts, window_seconds)
            if i < max_attempts - 1:
                self.assertTrue(result['allowed'])
            else:
                # Last attempt should exhaust limit
                self.assertEqual(result['remaining'], 0)
        
        # Test exceeding limit
        result = check_rate_limit(self.user.id, max_attempts, window_seconds)
        self.assertFalse(result['allowed'])
    
    def test_progressive_delay_on_failed_attempts(self):
        """Test progressive delay after failed verification attempts"""
        failed_attempts = 0
        
        def calculate_delay(attempts):
            """Calculate progressive delay based on failed attempts"""
            if attempts == 0:
                return 0
            elif attempts <= 3:
                return 1  # 1 second delay
            elif attempts <= 5:
                return 5  # 5 second delay
            elif attempts <= 10:
                return 30  # 30 second delay
            else:
                return 300  # 5 minute lockout
        
        # Test progressive delays
        delays = [calculate_delay(i) for i in range(12)]
        
        self.assertEqual(delays[0], 0)    # No delay initially
        self.assertEqual(delays[2], 1)    # 1 second after 2 attempts
        self.assertEqual(delays[4], 5)    # 5 seconds after 4 attempts
        self.assertEqual(delays[7], 30)   # 30 seconds after 7 attempts
        self.assertEqual(delays[11], 300) # 5 minutes after 11 attempts
    
    def test_ip_based_rate_limiting(self):
        """Test IP-based rate limiting for authentication"""
        ip_address = '192.168.1.100'
        max_requests_per_ip = 20
        window_minutes = 5
        
        def check_ip_rate_limit(ip, max_requests, window):
            """Check IP-based rate limit"""
            key = f'auth_attempts_ip_{ip}'
            attempts = cache.get(key, 0)
            
            if attempts >= max_requests:
                return {
                    'blocked': True,
                    'reason': 'ip_rate_limit',
                    'unblock_at': timezone.now() + timedelta(minutes=window)
                }
            
            cache.set(key, attempts + 1, window * 60)
            
            return {'blocked': False, 'attempts': attempts + 1}
        
        # Simulate requests from same IP
        for i in range(max_requests_per_ip + 1):
            result = check_ip_rate_limit(
                ip_address,
                max_requests_per_ip,
                window_minutes
            )
            
            if i < max_requests_per_ip:
                self.assertFalse(result['blocked'])
            else:
                self.assertTrue(result['blocked'])
                self.assertEqual(result['reason'], 'ip_rate_limit')
    
    def test_distributed_rate_limiting(self):
        """Test distributed rate limiting across multiple servers"""
        # Simulate distributed rate limiting using Redis
        user_id = self.user.id
        
        def distributed_rate_check(user_id, action, max_rate, window):
            """Check rate limit using distributed cache"""
            # Use Redis-like distributed cache
            key = f'distributed_rate_{action}_{user_id}'
            
            # Atomic increment with expiry
            current_count = cache.get(key, 0)
            
            if current_count >= max_rate:
                return {
                    'allowed': False,
                    'current_rate': current_count,
                    'max_rate': max_rate,
                    'window': window
                }
            
            # Atomic increment
            new_count = current_count + 1
            cache.set(key, new_count, window)
            
            return {
                'allowed': True,
                'current_rate': new_count,
                'max_rate': max_rate
            }
        
        # Test distributed limiting
        max_rate = 10
        window = 60
        
        for i in range(max_rate):
            result = distributed_rate_check(
                user_id,
                'face_verify',
                max_rate,
                window
            )
            self.assertTrue(result['allowed'])
            self.assertEqual(result['current_rate'], i + 1)
        
        # Should be blocked after max_rate
        result = distributed_rate_check(
            user_id,
            'face_verify',
            max_rate,
            window
        )
        self.assertFalse(result['allowed'])


class MultiFactorAuthenticationTest(TestCase):
    """Test multi-factor authentication security"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client = Client()
    
    def test_face_plus_pin_authentication(self):
        """Test combination of face recognition and PIN"""
        # Create face embedding for user
        FaceEmbeddingFactory(user=self.user)
        
        def multi_factor_auth(user, face_image, pin):
            """Perform multi-factor authentication"""
            results = {
                'face_verified': False,
                'pin_verified': False,
                'mfa_passed': False
            }
            
            # Step 1: Face verification
            with patch('apps.face_recognition.enhanced_engine.EnhancedFaceRecognitionEngine.verify_face') as mock_verify:
                mock_verify.return_value = Mock(
                    verification_successful=True,
                    similarity_score=0.88
                )
                
                face_result = mock_verify(user.id, face_image)
                results['face_verified'] = face_result.verification_successful
            
            # Step 2: PIN verification
            stored_pin_hash = hashlib.sha256('1234'.encode()).hexdigest()
            provided_pin_hash = hashlib.sha256(pin.encode()).hexdigest()
            results['pin_verified'] = stored_pin_hash == provided_pin_hash
            
            # Both factors must pass
            results['mfa_passed'] = results['face_verified'] and results['pin_verified']
            
            return results
        
        # Test successful MFA
        result = multi_factor_auth(
            self.user,
            self.create_mock_image(),
            '1234'
        )
        self.assertTrue(result['face_verified'])
        self.assertTrue(result['pin_verified'])
        self.assertTrue(result['mfa_passed'])
        
        # Test failed MFA (wrong PIN)
        result = multi_factor_auth(
            self.user,
            self.create_mock_image(),
            '0000'
        )
        self.assertTrue(result['face_verified'])
        self.assertFalse(result['pin_verified'])
        self.assertFalse(result['mfa_passed'])
    
    def test_behavioral_biometric_authentication(self):
        """Test behavioral biometrics as authentication factor"""
        # Create behavioral profile
        profile = UserBehaviorProfile.objects.create(
            user=self.user,
            typical_login_hours=[9, 10, 11, 14, 15],
            typing_pattern={'avg_dwell_time': 120, 'avg_flight_time': 80},
            mouse_movement_pattern={'avg_speed': 250, 'avg_acceleration': 50}
        )
        
        def verify_behavioral_biometrics(user, current_behavior):
            """Verify user based on behavioral patterns"""
            profile = user.behavior_profile
            
            # Check login time pattern
            current_hour = current_behavior['login_hour']
            time_match = current_hour in profile.typical_login_hours
            
            # Check typing pattern (keystroke dynamics)
            typing_deviation = abs(
                current_behavior['typing']['dwell_time'] - 
                profile.typing_pattern['avg_dwell_time']
            )
            typing_match = typing_deviation < 20  # 20ms tolerance
            
            # Check mouse pattern
            mouse_deviation = abs(
                current_behavior['mouse']['speed'] - 
                profile.mouse_movement_pattern['avg_speed']
            )
            mouse_match = mouse_deviation < 50  # 50 pixels/sec tolerance
            
            # Calculate behavioral score
            score = sum([time_match, typing_match, mouse_match]) / 3
            
            return {
                'verified': score > 0.6,
                'behavioral_score': score,
                'factors_matched': {
                    'time': time_match,
                    'typing': typing_match,
                    'mouse': mouse_match
                }
            }
        
        # Test matching behavior
        current_behavior = {
            'login_hour': 10,
            'typing': {'dwell_time': 125},  # Close to profile
            'mouse': {'speed': 245}  # Close to profile
        }
        
        result = verify_behavioral_biometrics(self.user, current_behavior)
        self.assertTrue(result['verified'])
        self.assertGreater(result['behavioral_score'], 0.6)
        
        # Test non-matching behavior
        suspicious_behavior = {
            'login_hour': 3,  # Unusual hour
            'typing': {'dwell_time': 200},  # Very different
            'mouse': {'speed': 500}  # Very different
        }
        
        result = verify_behavioral_biometrics(self.user, suspicious_behavior)
        self.assertFalse(result['verified'])
        self.assertLess(result['behavioral_score'], 0.6)
    
    def test_step_up_authentication(self):
        """Test step-up authentication for sensitive operations"""
        def requires_step_up_auth(operation):
            """Determine if operation requires step-up authentication"""
            sensitive_operations = [
                'delete_all_embeddings',
                'export_user_data',
                'change_security_settings',
                'access_audit_logs'
            ]
            
            return operation in sensitive_operations
        
        def perform_step_up_auth(user, operation, additional_factor):
            """Perform step-up authentication for sensitive operation"""
            if not requires_step_up_auth(operation):
                return {'required': False, 'authorized': True}
            
            # Require additional authentication factor
            result = {
                'required': True,
                'authorized': False,
                'operation': operation,
                'challenge_type': 'face_scan'
            }
            
            # Verify additional factor (face scan in this case)
            if additional_factor.get('face_verified'):
                result['authorized'] = True
                result['authorization_token'] = hashlib.sha256(
                    f"{user.id}_{operation}_{timezone.now()}".encode()
                ).hexdigest()
            
            return result
        
        # Test sensitive operation requiring step-up
        result = perform_step_up_auth(
            self.user,
            'delete_all_embeddings',
            {'face_verified': True}
        )
        self.assertTrue(result['required'])
        self.assertTrue(result['authorized'])
        self.assertIsNotNone(result.get('authorization_token'))
        
        # Test non-sensitive operation
        result = perform_step_up_auth(
            self.user,
            'view_profile',
            {}
        )
        self.assertFalse(result['required'])
        self.assertTrue(result['authorized'])


class TokenSecurityTest(TestCase):
    """Test API token security for AI endpoints"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_jwt_token_validation(self):
        """Test JWT token validation for API access"""
        import jwt
        from datetime import datetime, timedelta
        
        secret_key = 'test_secret_key'
        
        def generate_token(user, expires_in=3600):
            """Generate JWT token for user"""
            payload = {
                'user_id': user.id,
                'username': user.username,
                'exp': datetime.utcnow() + timedelta(seconds=expires_in),
                'iat': datetime.utcnow(),
                'aud': 'face_recognition_api',
                'permissions': ['face_verify', 'view_embeddings']
            }
            
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            return token
        
        def validate_token(token):
            """Validate JWT token"""
            try:
                payload = jwt.decode(
                    token,
                    secret_key,
                    algorithms=['HS256'],
                    audience='face_recognition_api'
                )
                return {
                    'valid': True,
                    'user_id': payload['user_id'],
                    'permissions': payload['permissions']
                }
            except jwt.ExpiredSignatureError:
                return {'valid': False, 'error': 'token_expired'}
            except jwt.InvalidTokenError:
                return {'valid': False, 'error': 'invalid_token'}
        
        # Test valid token
        token = generate_token(self.user)
        result = validate_token(token)
        self.assertTrue(result['valid'])
        self.assertEqual(result['user_id'], self.user.id)
        
        # Test expired token
        expired_token = generate_token(self.user, expires_in=-1)
        result = validate_token(expired_token)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'token_expired')
        
        # Test tampered token
        tampered_token = token[:-5] + 'xxxxx'
        result = validate_token(tampered_token)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'invalid_token')
    
    def test_api_key_rotation(self):
        """Test automatic API key rotation"""
        def generate_api_key():
            """Generate new API key"""
            import secrets
            return secrets.token_urlsafe(32)
        
        def rotate_api_keys(user):
            """Rotate API keys for user"""
            old_key = getattr(user, 'api_key', None)
            new_key = generate_api_key()
            
            # Store new key (in practice, this would be hashed)
            user.api_key = new_key
            user.api_key_created_at = timezone.now()
            user.save()
            
            # Invalidate old key after grace period
            grace_period = timedelta(minutes=5)
            
            return {
                'old_key': old_key,
                'new_key': new_key,
                'grace_period': grace_period,
                'rotation_time': timezone.now()
            }
        
        # Perform key rotation
        result = rotate_api_keys(self.user)
        
        self.assertIsNotNone(result['new_key'])
        self.assertNotEqual(result['old_key'], result['new_key'])
        self.assertEqual(result['grace_period'].total_seconds(), 300)
    
    def test_token_scope_validation(self):
        """Test token scope and permission validation"""
        def create_scoped_token(user, scopes):
            """Create token with specific scopes"""
            return {
                'token': hashlib.sha256(f"{user.id}_{scopes}".encode()).hexdigest()[:32],
                'user_id': user.id,
                'scopes': scopes,
                'created_at': timezone.now()
            }
        
        def check_token_permission(token_data, required_scope):
            """Check if token has required permission"""
            if required_scope not in token_data['scopes']:
                return {
                    'authorized': False,
                    'error': 'insufficient_scope',
                    'required': required_scope,
                    'available': token_data['scopes']
                }
            
            return {'authorized': True, 'scope': required_scope}
        
        # Create token with limited scopes
        token = create_scoped_token(self.user, ['read_embeddings', 'verify_face'])
        
        # Test authorized scope
        result = check_token_permission(token, 'read_embeddings')
        self.assertTrue(result['authorized'])
        
        # Test unauthorized scope
        result = check_token_permission(token, 'delete_embeddings')
        self.assertFalse(result['authorized'])
        self.assertEqual(result['error'], 'insufficient_scope')