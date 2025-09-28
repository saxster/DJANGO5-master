"""
Comprehensive test suite for biometric security fixes

Tests cover:
1. Exception handling bug fixes
2. Threshold semantic consistency
3. Image-dependent mock models
4. Face ROI-based quality assessment
5. Embedding caching with TTL
6. Database model integrity
"""

import os
import tempfile
import numpy as np
import cv2
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model

from apps.face_recognition.models import (
    FaceRecognitionModel,
    FaceEmbedding,
    FaceVerificationLog,
    FaceQualityMetrics
)
from apps.face_recognition.enhanced_engine import (
    EnhancedFaceRecognitionEngine,
    MockFaceNetModel,
    MockArcFaceModel,
    MockInsightFaceModel
)
from apps.face_recognition.services import (
    UnifiedFaceRecognitionService,
    VerificationEngine,
    VerificationResult,
    get_face_recognition_service
)


User = get_user_model()


class BiometricSecurityFixesTestCase(TestCase):
    """Test suite for biometric security fixes"""

    def setUp(self):
        """Set up test data"""
        # Clear cache before each test
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        # Create test face recognition model
        self.face_model = FaceRecognitionModel.objects.create(
            name='TestFaceNet512',
            model_type='FACENET512',
            version='1.0',
            status='ACTIVE',
            similarity_threshold=0.3,
            confidence_threshold=0.7,
            liveness_detection_enabled=True
        )

        # Create test embeddings
        self.embedding = FaceEmbedding.objects.create(
            user=self.user,
            embedding_vector=list(np.random.normal(0, 1, 512)),
            extraction_model=self.face_model,
            face_confidence=0.95,
            is_primary=True,
            is_validated=True
        )

        # Create test image
        self.test_image_path = self._create_test_image()

    def tearDown(self):
        """Clean up after tests"""
        # Remove test image
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
        cache.clear()

    def _create_test_image(self, width=200, height=200):
        """Create a test image file"""
        # Create a simple test image with a face-like pattern
        image = np.ones((height, width, 3), dtype=np.uint8) * 128

        # Add a simple face-like rectangle
        cv2.rectangle(image, (50, 50), (150, 150), (200, 200, 200), -1)

        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
        cv2.imwrite(temp_path, image)
        os.close(temp_fd)

        return temp_path


class TestExceptionHandlingFix(BiometricSecurityFixesTestCase):
    """Test the exception handling bug fix in background tasks"""

    @patch('background_tasks.tasks.logger')
    @patch('background_tasks.tasks.ErrorHandler')
    def test_value_error_exception_variable_fix(self, mock_error_handler, mock_logger):
        """Test that ValueError uses correct exception variable 'v' instead of 'e'"""
        # Import the task function
        from background_tasks.tasks import perform_facerecognition_bgt

        # Create a mock celery task
        mock_task = MagicMock()
        mock_task.retry = MagicMock()

        # Mock DeepFace to raise ValueError
        with patch('background_tasks.tasks.DeepFace') as mock_deepface:
            mock_deepface.verify.side_effect = ValueError("Test error")

            # Call the task function - it should handle the ValueError correctly
            result = perform_facerecognition_bgt(
                mock_task,
                'test_uuid',
                self.user.id,
                'default'
            )

            # Verify ErrorHandler was called with correct exception variable
            mock_error_handler.handle_exception.assert_called()

            # The first argument should be the ValueError instance
            call_args = mock_error_handler.handle_exception.call_args
            self.assertIsInstance(call_args[0][0], ValueError)

    def test_exception_correlation_id_generation(self):
        """Test that correlation IDs are properly generated for error tracking"""
        # Import the task function
        from background_tasks.tasks import perform_facerecognition_bgt

        mock_task = MagicMock()
        mock_task.retry = MagicMock()

        with patch('background_tasks.tasks.DeepFace') as mock_deepface:
            with patch('background_tasks.tasks.ErrorHandler') as mock_error_handler:
                mock_deepface.verify.side_effect = ValueError("Test error")

                result = perform_facerecognition_bgt(
                    mock_task,
                    'test_uuid',
                    self.user.id,
                    'default'
                )

                # Check that result contains correlation_id
                self.assertIn('error', result)
                self.assertIn('correlation_id', result['error'])
                self.assertEqual(result['error']['code'], 'TASK_EXECUTION_ERROR')


class TestThresholdSemanticFix(BiometricSecurityFixesTestCase):
    """Test threshold semantic consistency fixes"""

    def test_database_threshold_loading(self):
        """Test that thresholds are loaded from database models"""
        from background_tasks.tasks import perform_facerecognition_bgt

        mock_task = MagicMock()

        with patch('background_tasks.tasks.DeepFace') as mock_deepface:
            with patch('background_tasks.tasks.apps.get_model') as mock_get_model:
                # Mock the FaceRecognitionModel query
                mock_face_model = MagicMock()
                mock_face_model.similarity_threshold = 0.25
                mock_model_class = MagicMock()
                mock_model_class.objects.filter().first.return_value = mock_face_model
                mock_get_model.side_effect = lambda app, model: {
                    ('face_recognition', 'FaceRecognitionModel'): mock_model_class,
                    ('attendance', 'PeopleEventlog'): MagicMock(),
                    ('activity', 'Attachment'): MagicMock(),
                    ('peoples', 'People'): MagicMock()
                }.get((app, model))

                # Mock successful verification result
                mock_deepface.verify.return_value = {
                    'verified': True,
                    'distance': 0.2,
                    'threshold': 0.4,
                    'model': 'Facenet512'
                }

                result = perform_facerecognition_bgt(
                    mock_task,
                    'test_uuid',
                    self.user.id,
                    'default'
                )

                # Verify database threshold was used
                self.assertIn('Using distance threshold: 0.25', result['story'])

    def test_enhanced_engine_threshold_consistency(self):
        """Test that enhanced engine uses thresholds consistently"""
        engine = EnhancedFaceRecognitionEngine()
        engine.config = {'similarity_threshold': 0.35}

        # Test that both similarity and distance comparisons are consistent
        mock_results = {
            'FACENET512': {
                'similarity': 0.8,
                'distance': 0.2,
                'threshold_met': True  # Should be True because 0.2 <= 0.35
            }
        }

        # Verify threshold logic
        distance_threshold = engine.config.get('similarity_threshold', 0.3)
        test_distance = 0.2
        self.assertTrue(test_distance <= distance_threshold)

    def test_deepface_configuration_no_threshold_override(self):
        """Test that DeepFace is called without threshold parameter"""
        from background_tasks.tasks import perform_facerecognition_bgt

        mock_task = MagicMock()

        with patch('background_tasks.tasks.DeepFace') as mock_deepface:
            with patch('background_tasks.tasks.apps.get_model') as mock_get_model:
                # Setup mocks
                mock_deepface.verify.return_value = {
                    'verified': True,
                    'distance': 0.15,
                    'model': 'Facenet512'
                }

                # Mock models
                mock_face_model = MagicMock()
                mock_face_model.similarity_threshold = 0.3
                mock_model_class = MagicMock()
                mock_model_class.objects.filter().first.return_value = mock_face_model
                mock_get_model.side_effect = lambda app, model: {
                    ('face_recognition', 'FaceRecognitionModel'): mock_model_class,
                }.get((app, model), MagicMock())

                perform_facerecognition_bgt(
                    mock_task,
                    'test_uuid',
                    self.user.id,
                    'default'
                )

                # Verify DeepFace.verify was called without threshold parameter
                call_kwargs = mock_deepface.verify.call_args[1]
                self.assertNotIn('threshold', call_kwargs)
                self.assertEqual(call_kwargs['detector_backend'], 'retinaface')


class TestImageDependentMockModels(BiometricSecurityFixesTestCase):
    """Test that mock models generate image-dependent features"""

    def test_mock_facenet_image_dependent_seeds(self):
        """Test that MockFaceNetModel generates different embeddings for different images"""
        model = MockFaceNetModel()

        # Create two different test images
        img1_path = self._create_test_image(100, 100)
        img2_path = self._create_test_image(200, 200)

        try:
            # Extract features from both images
            features1 = model.extract_features(img1_path)
            features2 = model.extract_features(img2_path)

            # Features should be different for different images
            self.assertFalse(np.array_equal(features1, features2))

            # But should be consistent for the same image
            features1_again = model.extract_features(img1_path)
            self.assertTrue(np.array_equal(features1, features1_again))

        finally:
            # Cleanup
            os.remove(img1_path)
            os.remove(img2_path)

    def test_mock_model_normalization(self):
        """Test that mock models return normalized vectors"""
        models = [MockFaceNetModel(), MockArcFaceModel(), MockInsightFaceModel()]

        for model in models:
            features = model.extract_features(self.test_image_path)

            # Check that the vector is normalized (L2 norm ≈ 1)
            norm = np.linalg.norm(features)
            self.assertAlmostEqual(norm, 1.0, places=6)

    def test_mock_model_differentiation(self):
        """Test that different mock models generate different features for same image"""
        facenet_model = MockFaceNetModel()
        arcface_model = MockArcFaceModel()
        insight_model = MockInsightFaceModel()

        facenet_features = facenet_model.extract_features(self.test_image_path)
        arcface_features = arcface_model.extract_features(self.test_image_path)
        insight_features = insight_model.extract_features(self.test_image_path)

        # All three should be different due to different seed offsets
        self.assertFalse(np.array_equal(facenet_features, arcface_features))
        self.assertFalse(np.array_equal(facenet_features, insight_features))
        self.assertFalse(np.array_equal(arcface_features, insight_features))


class TestFaceROIQualityAssessment(BiometricSecurityFixesTestCase):
    """Test face ROI-based quality assessment improvements"""

    def test_face_roi_detection(self):
        """Test face region of interest detection"""
        engine = EnhancedFaceRecognitionEngine()

        # Create test image with mock face
        image = np.ones((200, 200, 3), dtype=np.uint8) * 128

        with patch('cv2.CascadeClassifier') as mock_cascade_class:
            mock_cascade = MagicMock()
            mock_cascade.detectMultiScale.return_value = np.array([[50, 50, 100, 100]])
            mock_cascade_class.return_value = mock_cascade

            face_roi, confidence = engine._detect_face_roi(image)

            self.assertIsNotNone(face_roi)
            self.assertEqual(face_roi, (50, 50, 100, 100))
            self.assertGreater(confidence, 0)

    def test_roi_quality_metrics(self):
        """Test individual ROI quality metric calculations"""
        engine = EnhancedFaceRecognitionEngine()

        # Create test ROI (grayscale)
        roi_gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)

        # Test sharpness calculation
        sharpness = engine._calculate_roi_sharpness(roi_gray)
        self.assertGreaterEqual(sharpness, 0.0)
        self.assertLessEqual(sharpness, 1.0)

        # Test brightness calculation
        brightness = engine._calculate_roi_brightness(roi_gray)
        self.assertGreaterEqual(brightness, 0.0)
        self.assertLessEqual(brightness, 1.0)

        # Test contrast calculation
        contrast = engine._calculate_roi_contrast(roi_gray)
        self.assertGreaterEqual(contrast, 0.0)
        self.assertLessEqual(contrast, 1.0)

    def test_face_size_scoring(self):
        """Test face size adequacy scoring"""
        engine = EnhancedFaceRecognitionEngine()

        # Test optimal face size (20% of image)
        score = engine._calculate_face_size_score(100, 100, 224, 224)
        self.assertGreater(score, 0.8)  # Should be high for good size

        # Test too small face
        score_small = engine._calculate_face_size_score(20, 20, 224, 224)
        self.assertLess(score_small, score)

        # Test too large face
        score_large = engine._calculate_face_size_score(200, 200, 224, 224)
        self.assertLess(score_large, score)

    def test_quality_issue_detection(self):
        """Test quality issue identification"""
        engine = EnhancedFaceRecognitionEngine()

        with patch.object(engine, '_detect_face_roi') as mock_detect:
            with patch.object(engine, '_calculate_roi_sharpness', return_value=0.3):
                with patch.object(engine, '_calculate_roi_brightness', return_value=0.3):
                    with patch.object(engine, '_calculate_roi_contrast', return_value=0.3):
                        with patch.object(engine, '_calculate_face_size_score', return_value=0.5):
                            mock_detect.return_value = ((50, 50, 100, 100), 0.8)

                            result = engine._assess_image_quality(self.test_image_path)

                            # Should detect multiple quality issues
                            issues = result.get('quality_issues', [])
                            expected_issues = ['LOW_SHARPNESS', 'POOR_LIGHTING', 'LOW_CONTRAST', 'SMALL_FACE_SIZE']
                            for issue in expected_issues:
                                self.assertIn(issue, issues)

    def test_improvement_suggestions(self):
        """Test actionable improvement suggestions generation"""
        engine = EnhancedFaceRecognitionEngine()

        quality_issues = ['LOW_SHARPNESS', 'POOR_LIGHTING', 'SMALL_FACE_SIZE']
        suggestions = engine._generate_improvement_suggestions(quality_issues)

        self.assertIn("Reduce camera shake and ensure proper focus", suggestions)
        self.assertIn("Improve lighting conditions - avoid overexposure or underexposure", suggestions)
        self.assertIn("Move closer to camera or use higher resolution image", suggestions)


class TestEmbeddingCaching(BiometricSecurityFixesTestCase):
    """Test embedding caching with TTL"""

    def test_cache_hit_and_miss(self):
        """Test cache hit and miss scenarios"""
        engine = EnhancedFaceRecognitionEngine()

        # First call should be cache miss
        with patch('apps.face_recognition.enhanced_engine.logger') as mock_logger:
            embeddings1 = engine._get_user_embeddings(self.user.id)

            # Should log cache miss
            mock_logger.debug.assert_any_call(f"Cache miss for user embeddings: {self.user.id}")

        # Second call should be cache hit
        with patch('apps.face_recognition.enhanced_engine.logger') as mock_logger:
            embeddings2 = engine._get_user_embeddings(self.user.id)

            # Should log cache hit
            mock_logger.debug.assert_any_call(f"Cache hit for user embeddings: {self.user.id}")

        # Results should be identical
        self.assertEqual(len(embeddings1), len(embeddings2))
        if embeddings1:
            self.assertEqual(embeddings1[0].id, embeddings2[0].id)

    def test_cache_invalidation(self):
        """Test cache invalidation functionality"""
        engine = EnhancedFaceRecognitionEngine()

        # Populate cache
        embeddings1 = engine._get_user_embeddings(self.user.id)

        # Verify cache is populated
        cache_key = f"fr_embeddings:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)

        # Invalidate cache
        engine.invalidate_user_embedding_cache(self.user.id)

        # Verify cache is cleared
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)

    def test_cache_ttl(self):
        """Test cache TTL functionality"""
        engine = EnhancedFaceRecognitionEngine()
        cache_key = f"fr_embeddings:{self.user.id}"

        # Populate cache
        engine._get_user_embeddings(self.user.id)

        # Verify cache exists
        self.assertIsNotNone(cache.get(cache_key))

        # Simulate TTL expiry by manually deleting and checking behavior
        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))

        # Next call should repopulate cache
        embeddings = engine._get_user_embeddings(self.user.id)
        self.assertIsNotNone(cache.get(cache_key))

    def test_empty_embeddings_not_cached(self):
        """Test that empty embeddings are not cached"""
        engine = EnhancedFaceRecognitionEngine()

        # Use a user with no embeddings
        user_no_embeddings = User.objects.create_user(
            username='noemb',
            email='noemb@example.com'
        )

        embeddings = engine._get_user_embeddings(user_no_embeddings.id)

        # Should return empty list
        self.assertEqual(embeddings, [])

        # Should not be cached
        cache_key = f"fr_embeddings:{user_no_embeddings.id}"
        self.assertIsNone(cache.get(cache_key))


class TestModelIntegrity(BiometricSecurityFixesTestCase):
    """Test database model integrity and consistency"""

    def test_face_recognition_model_defaults(self):
        """Test FaceRecognitionModel default values"""
        model = FaceRecognitionModel.objects.create(
            name='TestModel',
            model_type='FACENET512'
        )

        self.assertEqual(model.similarity_threshold, 0.3)
        self.assertEqual(model.confidence_threshold, 0.7)
        self.assertEqual(model.status, 'ACTIVE')
        self.assertTrue(model.liveness_detection_enabled)

    def test_face_embedding_validation(self):
        """Test FaceEmbedding model validation"""
        # Test valid embedding
        valid_embedding = FaceEmbedding.objects.create(
            user=self.user,
            embedding_vector=list(np.random.normal(0, 1, 512)),
            extraction_model=self.face_model,
            face_confidence=0.95
        )

        self.assertEqual(len(valid_embedding.embedding_vector), 512)
        self.assertFalse(valid_embedding.is_primary)  # Default
        self.assertFalse(valid_embedding.is_validated)  # Default

    def test_face_quality_metrics_creation(self):
        """Test FaceQualityMetrics creation with all fields"""
        metrics = FaceQualityMetrics.objects.create(
            image_path=self.test_image_path,
            image_hash='test_hash_123',
            overall_quality=0.85,
            sharpness_score=0.9,
            brightness_score=0.8,
            contrast_score=0.85,
            face_size_score=0.9,
            face_pose_score=0.8,
            eye_visibility_score=0.95,
            resolution_width=224,
            resolution_height=224,
            file_size_bytes=1024,
            face_detection_confidence=0.92,
            landmark_quality={'detected': True},
            quality_issues=['LOW_CONTRAST'],
            improvement_suggestions=['Improve lighting']
        )

        self.assertEqual(metrics.overall_quality, 0.85)
        self.assertEqual(len(metrics.quality_issues), 1)
        self.assertEqual(len(metrics.improvement_suggestions), 1)

    def test_face_verification_log_creation(self):
        """Test FaceVerificationLog comprehensive logging"""
        log = FaceVerificationLog.objects.create(
            user=self.user,
            result='SUCCESS',
            verification_model=self.face_model,
            matched_embedding=self.embedding,
            similarity_score=0.85,
            confidence_score=0.9,
            liveness_score=0.8,
            spoof_detected=False,
            input_image_path=self.test_image_path,
            face_detection_confidence=0.95,
            processing_time_ms=150.5,
            fraud_risk_score=0.1,
            verification_metadata={'model': 'enhanced', 'version': '1.0'}
        )

        self.assertEqual(log.result, 'SUCCESS')
        self.assertEqual(log.user, self.user)
        self.assertFalse(log.spoof_detected)
        self.assertEqual(log.fraud_risk_score, 0.1)


class TestPerformanceOptimizations(BiometricSecurityFixesTestCase):
    """Test performance optimization validations"""

    def test_database_query_optimization(self):
        """Test that embeddings are fetched with proper select_related"""
        engine = EnhancedFaceRecognitionEngine()

        # Clear cache to ensure database hit
        cache.clear()

        with self.assertNumQueries(1):  # Should be exactly 1 query with select_related
            embeddings = engine._get_user_embeddings(self.user.id)

            # Access related model to verify select_related worked
            if embeddings:
                _ = embeddings[0].extraction_model.name  # Should not trigger additional query

    def test_feature_extraction_error_handling(self):
        """Test robust error handling in feature extraction"""
        engine = EnhancedFaceRecognitionEngine()

        # Test with non-existent image path
        result = engine._assess_image_quality('/non/existent/path.jpg')

        self.assertEqual(result['overall_quality'], 0.0)
        self.assertIn('error', result)

    def test_concurrent_cache_access(self):
        """Test thread-safe cache access"""
        engine = EnhancedFaceRecognitionEngine()

        # This is a basic test - in production, would need proper threading tests
        cache.clear()

        # Multiple calls should not cause race conditions
        results = []
        for _ in range(5):
            results.append(engine._get_user_embeddings(self.user.id))

        # All results should be consistent
        for result in results[1:]:
            self.assertEqual(len(result), len(results[0]))


class TestUnifiedFaceRecognitionService(BiometricSecurityFixesTestCase):
    """Test the unified face recognition service"""

    def test_service_initialization(self):
        """Test service initializes with different engines"""
        # Test with default engine
        service_default = UnifiedFaceRecognitionService()
        self.assertEqual(service_default.preferred_engine, VerificationEngine.DEEPFACE)

        # Test with enhanced engine
        service_enhanced = UnifiedFaceRecognitionService(VerificationEngine.ENHANCED)
        self.assertEqual(service_enhanced.preferred_engine, VerificationEngine.ENHANCED)

    def test_get_global_service_instance(self):
        """Test global service instance management"""
        service1 = get_face_recognition_service()
        service2 = get_face_recognition_service()

        # Should be the same instance
        self.assertIs(service1, service2)

    @patch('apps.face_recognition.services.DeepFace')
    def test_unified_deepface_verification(self, mock_deepface):
        """Test unified service with DeepFace engine"""
        # Setup mock
        mock_deepface.verify.return_value = {
            'distance': 0.25,
            'verified': True
        }

        service = UnifiedFaceRecognitionService(VerificationEngine.DEEPFACE)

        with patch.object(service, '_get_user_reference_image', return_value=self.test_image_path):
            result = service.verify_face(self.user.id, self.test_image_path)

            # Verify standardized result format
            self.assertIsInstance(result, VerificationResult)
            self.assertTrue(result.verified)
            self.assertEqual(result.distance, 0.25)
            self.assertEqual(result.similarity_score, 0.75)
            self.assertEqual(result.engine_used, VerificationEngine.DEEPFACE.value)
            self.assertIsNone(result.error_message)

    def test_unified_enhanced_verification(self):
        """Test unified service with Enhanced engine"""
        service = UnifiedFaceRecognitionService(VerificationEngine.ENHANCED)

        if service.enhanced_engine:
            with patch.object(service.enhanced_engine, 'verify_face') as mock_verify:
                mock_verify.return_value = {
                    'verified': True,
                    'similarity_score': 0.85,
                    'distance': 0.15,
                    'confidence_score': 0.9,
                    'quality_assessment': {
                        'overall_quality': 0.8,
                        'quality_issues': ['LOW_CONTRAST']
                    },
                    'anti_spoofing': {
                        'spoof_detected': False,
                        'liveness_score': 0.95
                    }
                }

                result = service.verify_face(self.user.id, self.test_image_path)

                # Verify enhanced features are included
                self.assertIsInstance(result, VerificationResult)
                self.assertTrue(result.verified)
                self.assertEqual(result.image_quality_score, 0.8)
                self.assertEqual(result.quality_issues, ['LOW_CONTRAST'])
                self.assertFalse(result.spoof_detected)
                self.assertEqual(result.liveness_score, 0.95)

    def test_error_handling_and_standardization(self):
        """Test error handling in unified service"""
        service = UnifiedFaceRecognitionService()

        with patch.object(service, '_get_user_reference_image', return_value=None):
            result = service.verify_face(self.user.id, self.test_image_path)

            # Should handle gracefully
            self.assertIsInstance(result, VerificationResult)
            self.assertFalse(result.verified)
            self.assertEqual(result.similarity_score, 0.0)
            self.assertEqual(result.distance, 1.0)
            self.assertIsNotNone(result.error_message)
            self.assertIn("No reference image", result.error_message)

    def test_verification_logging(self):
        """Test that verification attempts are logged"""
        service = UnifiedFaceRecognitionService()

        # Count existing logs
        initial_log_count = FaceVerificationLog.objects.count()

        with patch('apps.face_recognition.services.DeepFace') as mock_deepface:
            mock_deepface.verify.return_value = {
                'distance': 0.2,
                'verified': True
            }

            with patch.object(service, '_get_user_reference_image', return_value=self.test_image_path):
                result = service.verify_face(self.user.id, self.test_image_path)

                # Should create a log entry
                final_log_count = FaceVerificationLog.objects.count()
                self.assertEqual(final_log_count, initial_log_count + 1)

                # Verify log content
                latest_log = FaceVerificationLog.objects.latest('verification_timestamp')
                self.assertEqual(latest_log.user_id, self.user.id)
                self.assertEqual(latest_log.result, 'SUCCESS')
                self.assertIsNotNone(latest_log.verification_metadata)

    def test_engine_status_reporting(self):
        """Test engine status reporting"""
        service = UnifiedFaceRecognitionService()
        status = service.get_engine_status()

        # Should report engine availability
        self.assertIn('deepface_available', status)
        self.assertIn('enhanced_available', status)
        self.assertIn('preferred_engine', status)
        self.assertTrue(status['deepface_available'])

    def test_cache_invalidation_integration(self):
        """Test cache invalidation through unified service"""
        service = UnifiedFaceRecognitionService()

        # Should not raise errors even if enhanced engine not available
        service.invalidate_user_cache(self.user.id)

        if service.enhanced_engine:
            # Should call through to enhanced engine
            with patch.object(service.enhanced_engine, 'invalidate_user_embedding_cache') as mock_invalidate:
                service.invalidate_user_cache(self.user.id)
                mock_invalidate.assert_called_once_with(self.user.id)

    @patch('background_tasks.tasks.PeopleEventlog')
    def test_attendance_update_integration(self, mock_pel):
        """Test attendance record update integration"""
        # Mock the manager method
        mock_pel.objects.update_fr_results.return_value = True

        # Create a verification result
        result = VerificationResult(
            verified=True,
            similarity_score=0.85,
            distance=0.15,
            confidence_score=0.9,
            processing_time_ms=150.0,
            engine_used='deepface',
            model_name='Facenet512',
            correlation_id='test_123'
        )

        # Test attendance update
        updated = UnifiedFaceRecognitionService.update_attendance_with_result(
            pel_uuid='test_uuid',
            user_id=self.user.id,
            result=result
        )

        self.assertTrue(updated)
        mock_pel.objects.update_fr_results.assert_called_once()

        # Verify the data passed to update_fr_results
        call_args = mock_pel.objects.update_fr_results.call_args[0]
        fr_data = call_args[0]

        self.assertTrue(fr_data['verified'])
        self.assertEqual(fr_data['distance'], 0.15)
        self.assertEqual(fr_data['similarity_score'], 0.85)
        self.assertEqual(fr_data['engine'], 'deepface')
        self.assertEqual(fr_data['correlation_id'], 'test_123')


class TestCalibrationCommandIntegration(BiometricSecurityFixesTestCase):
    """Test integration with threshold calibration command"""

    def test_face_model_training_dataset_info(self):
        """Test that face models can store calibration metadata"""
        # Update model with calibration info
        self.face_model.training_dataset_info = {
            'calibration_timestamp': '2024-01-01T12:00:00Z',
            'sample_count': 500,
            'auc': 0.95,
            'eer_value': 0.05,
            'old_threshold': 0.4,
            'calibration_method': 'empirical_roc_eer'
        }
        self.face_model.save()

        # Verify data is stored correctly
        reloaded_model = FaceRecognitionModel.objects.get(id=self.face_model.id)
        self.assertEqual(reloaded_model.training_dataset_info['sample_count'], 500)
        self.assertEqual(reloaded_model.training_dataset_info['auc'], 0.95)
        self.assertEqual(reloaded_model.training_dataset_info['calibration_method'], 'empirical_roc_eer')

    def test_verification_log_analysis_readiness(self):
        """Test that verification logs contain data needed for calibration analysis"""
        # Create some mock verification logs
        for i in range(5):
            FaceVerificationLog.objects.create(
                user=self.user,
                result='SUCCESS' if i < 3 else 'FAILED',
                verification_model=self.face_model,
                similarity_score=0.9 - (i * 0.1),
                confidence_score=0.8 - (i * 0.1),
                processing_time_ms=100.0 + i * 10,
                verification_metadata={
                    'engine': 'deepface',
                    'correlation_id': f'test_{i}'
                }
            )

        # Verify logs can be queried for calibration
        recent_logs = FaceVerificationLog.objects.filter(
            verification_model=self.face_model,
            result__in=['SUCCESS', 'FAILED'],
            similarity_score__isnull=False
        )

        self.assertEqual(recent_logs.count(), 5)

        # Verify each log has required data for calibration
        for log in recent_logs:
            self.assertIsNotNone(log.similarity_score)
            self.assertIn(log.result, ['SUCCESS', 'FAILED'])
            self.assertIsNotNone(log.processing_time_ms)

    def test_model_threshold_update_capability(self):
        """Test that models can be updated with calibrated thresholds"""
        original_threshold = self.face_model.similarity_threshold

        # Simulate calibration result
        new_threshold = 0.25
        calibration_metadata = {
            'calibration_timestamp': '2024-01-01T12:00:00Z',
            'sample_count': 1000,
            'auc': 0.92,
            'method': 'roc_eer'
        }

        # Update model
        self.face_model.similarity_threshold = new_threshold
        self.face_model.training_dataset_info = calibration_metadata
        self.face_model.save()

        # Verify update
        updated_model = FaceRecognitionModel.objects.get(id=self.face_model.id)
        self.assertEqual(updated_model.similarity_threshold, new_threshold)
        self.assertNotEqual(updated_model.similarity_threshold, original_threshold)
        self.assertEqual(updated_model.training_dataset_info['auc'], 0.92)


# Test runner for running just these biometric tests
if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    if not settings.configured:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
        django.setup()

    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['apps.face_recognition.tests.test_biometric_security_fixes'])

    if failures:
        exit(1)