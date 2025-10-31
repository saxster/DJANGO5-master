"""
Unified Face Recognition Service

This service consolidates face recognition functionality from multiple engines
and provides a single, consistent interface for all face recognition operations.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.apps import apps

from .models import (
    FaceRecognitionModel,
    FaceEmbedding,
    FaceVerificationLog,
    FaceQualityMetrics
)
from .enhanced_engine import EnhancedFaceRecognitionEngine


logger = logging.getLogger(__name__)


class VerificationEngine(Enum):
    """Available face recognition engines"""
    DEEPFACE = "deepface"
    ENHANCED = "enhanced"
    AI_ENHANCED = "ai_enhanced"


@dataclass
class VerificationResult:
    """Standardized verification result"""
    verified: bool
    similarity_score: float
    distance: float
    confidence_score: float
    processing_time_ms: float

    # Quality assessment
    image_quality_score: Optional[float] = None
    quality_issues: List[str] = None

    # Anti-spoofing
    spoof_detected: bool = False
    liveness_score: Optional[float] = None

    # Metadata
    engine_used: str = "unknown"
    model_name: str = "unknown"
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None

    # Database references
    matched_embedding_id: Optional[int] = None
    verification_log_id: Optional[int] = None


class UnifiedFaceRecognitionService:
    """
    Unified service for face recognition operations

    This service provides a single interface for face recognition that:
    - Normalizes results from different engines
    - Handles configuration consistently
    - Logs all operations uniformly
    - Manages caching and performance optimization
    """

    def __init__(self, preferred_engine: VerificationEngine = VerificationEngine.DEEPFACE):
        self.preferred_engine = preferred_engine
        self.enhanced_engine = None
        self._initialize_engines()

    def _initialize_engines(self):
        """Initialize available engines"""
        try:
            self.enhanced_engine = EnhancedFaceRecognitionEngine()
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Could not initialize enhanced engine: {e}")

    def verify_face(
        self,
        user_id: int,
        image_path: str,
        engine: Optional[VerificationEngine] = None,
        correlation_id: Optional[str] = None
    ) -> VerificationResult:
        """
        Perform face verification with unified result format

        Args:
            user_id: ID of user to verify against
            image_path: Path to image for verification
            engine: Specific engine to use (defaults to preferred_engine)
            correlation_id: Optional correlation ID for tracking

        Returns:
            VerificationResult with standardized format
        """
        start_time = time.time()
        engine_to_use = engine or self.preferred_engine

        logger.info(f"Starting face verification for user {user_id} with {engine_to_use.value}")

        try:
            # Get active face recognition model for thresholds
            face_model = self._get_active_face_model()

            if engine_to_use == VerificationEngine.DEEPFACE:
                result = self._verify_with_deepface(user_id, image_path, face_model, correlation_id)
            elif engine_to_use == VerificationEngine.ENHANCED:
                result = self._verify_with_enhanced(user_id, image_path, face_model, correlation_id)
            else:
                # Fallback to DeepFace
                result = self._verify_with_deepface(user_id, image_path, face_model, correlation_id)

            # Set processing time
            result.processing_time_ms = (time.time() - start_time) * 1000

            # Log the verification attempt
            self._log_verification(user_id, image_path, result, face_model)

            logger.info(f"Face verification completed: {result.verified} (confidence: {result.confidence_score:.3f})")
            return result

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Face verification failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return VerificationResult(
                verified=False,
                similarity_score=0.0,
                distance=1.0,
                confidence_score=0.0,
                processing_time_ms=processing_time,
                error_message=error_msg,
                correlation_id=correlation_id,
                engine_used=engine_to_use.value if engine_to_use else "unknown"
            )

    def _verify_with_deepface(
        self,
        user_id: int,
        image_path: str,
        face_model: FaceRecognitionModel,
        correlation_id: Optional[str]
    ) -> VerificationResult:
        """Verify using DeepFace with standardized output"""
        from deepface import DeepFace

        # Get user's reference image
        user_reference_path = self._get_user_reference_image(user_id)
        if not user_reference_path:
            return VerificationResult(
                verified=False,
                similarity_score=0.0,
                distance=1.0,
                confidence_score=0.0,
                processing_time_ms=0.0,
                error_message="No reference image found for user",
                correlation_id=correlation_id,
                engine_used=VerificationEngine.DEEPFACE.value
            )

        # Perform DeepFace verification
        deepface_result = DeepFace.verify(
            img1_path=user_reference_path,
            img2_path=image_path,
            enforce_detection=True,
            detector_backend="retinaface",
            model_name="Facenet512",
            distance_metric="cosine"
        )

        # Convert to standardized format
        distance = deepface_result["distance"]
        similarity_score = 1.0 - distance
        distance_threshold = face_model.similarity_threshold
        verified = distance <= distance_threshold

        # Calculate confidence based on how far from threshold
        if verified:
            # Closer to 0 distance = higher confidence
            confidence_score = min(1.0, (distance_threshold - distance) / distance_threshold + 0.5)
        else:
            # Further from threshold = lower confidence
            confidence_score = max(0.0, 1.0 - (distance - distance_threshold) / (1.0 - distance_threshold))

        return VerificationResult(
            verified=verified,
            similarity_score=similarity_score,
            distance=distance,
            confidence_score=confidence_score,
            processing_time_ms=0.0,  # Will be set by caller
            engine_used=VerificationEngine.DEEPFACE.value,
            model_name="Facenet512",
            correlation_id=correlation_id
        )

    def _verify_with_enhanced(
        self,
        user_id: int,
        image_path: str,
        face_model: FaceRecognitionModel,
        correlation_id: Optional[str]
    ) -> VerificationResult:
        """Verify using Enhanced engine with standardized output"""
        if not self.enhanced_engine:
            raise RuntimeError("Enhanced engine not available")

        # Perform enhanced verification
        enhanced_result = self.enhanced_engine.verify_face(user_id, image_path)

        # Convert to standardized format
        verified = enhanced_result.get('verified', False)
        similarity_score = enhanced_result.get('similarity_score', 0.0)
        distance = enhanced_result.get('distance', 1.0)
        confidence_score = enhanced_result.get('confidence_score', 0.0)

        # Extract quality assessment
        quality_assessment = enhanced_result.get('quality_assessment', {})
        image_quality_score = quality_assessment.get('overall_quality')
        quality_issues = quality_assessment.get('quality_issues', [])

        # Extract anti-spoofing results
        anti_spoofing = enhanced_result.get('anti_spoofing', {})
        spoof_detected = anti_spoofing.get('spoof_detected', False)
        liveness_score = anti_spoofing.get('liveness_score')

        return VerificationResult(
            verified=verified,
            similarity_score=similarity_score,
            distance=distance,
            confidence_score=confidence_score,
            processing_time_ms=0.0,  # Will be set by caller
            image_quality_score=image_quality_score,
            quality_issues=quality_issues,
            spoof_detected=spoof_detected,
            liveness_score=liveness_score,
            engine_used=VerificationEngine.ENHANCED.value,
            model_name="Enhanced_Ensemble",
            correlation_id=correlation_id,
            matched_embedding_id=enhanced_result.get('matched_embedding_id')
        )

    def _get_active_face_model(self) -> FaceRecognitionModel:
        """Get the active face recognition model for configuration"""
        try:
            face_model = FaceRecognitionModel.objects.filter(
                model_type='FACENET512',
                status='ACTIVE'
            ).first()

            if not face_model:
                # Create default model if none exists
                face_model = FaceRecognitionModel.objects.create(
                    name='Default_Facenet512',
                    model_type='FACENET512',
                    version='1.0',
                    status='ACTIVE',
                    similarity_threshold=0.3,
                    confidence_threshold=0.7
                )
                logger.info("Created default face recognition model")

            return face_model

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting face model: {e}")
            # Return a mock model with defaults
            return FaceRecognitionModel(
                name='Fallback_Model',
                model_type='FACENET512',
                similarity_threshold=0.3,
                confidence_threshold=0.7
            )

    def _get_user_reference_image(self, user_id: int) -> Optional[str]:
        """Get user's reference image path"""
        try:
            People = apps.get_model("peoples", "People")
            user = People.objects.get(id=user_id)

            if not user.peopleimg:
                return None

            # Handle both old and new URL patterns
            img_url = user.peopleimg.url
            img_path = img_url.replace("/youtility4_media/", "").replace("/media/", "")
            reference_path = f'{settings.MEDIA_ROOT}/{img_path}'

            # Don't use blank placeholder images
            if reference_path.endswith("blank.png"):
                return None

            return reference_path

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting user reference image: {e}")
            return None

    def _log_verification(
        self,
        user_id: int,
        image_path: str,
        result: VerificationResult,
        face_model: FaceRecognitionModel
    ):
        """Log verification attempt to database"""
        try:
            User = apps.get_model(settings.AUTH_USER_MODEL)

            # Determine result status
            if result.error_message:
                log_result = 'ERROR'
            elif result.spoof_detected:
                log_result = 'REJECTED'
            elif result.verified:
                log_result = 'SUCCESS'
            else:
                log_result = 'FAILED'

            # Get matched embedding if available
            matched_embedding = None
            if result.matched_embedding_id:
                try:
                    matched_embedding = FaceEmbedding.objects.get(id=result.matched_embedding_id)
                except FaceEmbedding.DoesNotExist:
                    pass

            # Create verification log
            verification_log = FaceVerificationLog.objects.create(
                user_id=user_id,
                result=log_result,
                verification_model=face_model,
                matched_embedding=matched_embedding,
                similarity_score=result.similarity_score,
                confidence_score=result.confidence_score,
                liveness_score=result.liveness_score,
                spoof_detected=result.spoof_detected,
                input_image_path=image_path,
                processing_time_ms=result.processing_time_ms,
                error_message=result.error_message,
                verification_metadata={
                    'engine': result.engine_used,
                    'model': result.model_name,
                    'correlation_id': result.correlation_id,
                    'quality_issues': result.quality_issues or [],
                    'image_quality_score': result.image_quality_score
                },
                fraud_indicators=result.quality_issues or [],
                fraud_risk_score=1.0 - (result.confidence_score or 0.0) if result.spoof_detected else 0.0
            )

            result.verification_log_id = verification_log.id

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error logging verification: {e}")

    def assess_image_quality(self, image_path: str) -> Dict[str, Any]:
        """Assess image quality using the enhanced engine"""
        if self.enhanced_engine:
            return self.enhanced_engine._assess_image_quality(image_path)
        else:
            return {
                'overall_quality': 0.5,
                'error': 'Enhanced engine not available'
            }

    def invalidate_user_cache(self, user_id: int):
        """Invalidate cached data for a user"""
        if self.enhanced_engine:
            self.enhanced_engine.invalidate_user_embedding_cache(user_id)

    def get_engine_status(self) -> Dict[str, Any]:
        """Get status of all available engines"""
        return {
            'deepface_available': True,  # Always available if DeepFace is installed
            'enhanced_available': self.enhanced_engine is not None,
            'preferred_engine': self.preferred_engine.value,
            'active_model': self._get_active_face_model().name if self._get_active_face_model() else None
        }

    @staticmethod
    def update_attendance_with_result(
        pel_uuid: str,
        user_id: int,
        result: VerificationResult,
        database: str = "default"
    ) -> bool:
        """Update attendance record with face recognition result"""
        try:
            PeopleEventlog = apps.get_model("attendance", "PeopleEventlog")

            # Prepare face recognition data
            fr_data = {
                'verified': result.verified,
                'distance': result.distance,
                'similarity_score': result.similarity_score,
                'threshold': result.distance if hasattr(result, 'distance_threshold') else 0.3,
                'model': result.model_name,
                'similarity_metric': 'cosine',
                'confidence': result.confidence_score,
                'processing_time_ms': result.processing_time_ms,
                'engine': result.engine_used,
                'quality_score': result.image_quality_score,
                'spoof_detected': result.spoof_detected,
                'correlation_id': result.correlation_id
            }

            # Update attendance record
            updated = PeopleEventlog.objects.update_fr_results(
                fr_data, pel_uuid, user_id, database
            )

            if updated:
                logger.info(f"Updated attendance record {pel_uuid} with face recognition results")

            return updated

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error updating attendance with face recognition result: {e}")
            return False


# Global service instance
_unified_service = None


def get_face_recognition_service(
    preferred_engine: VerificationEngine = VerificationEngine.DEEPFACE
) -> UnifiedFaceRecognitionService:
    """Get the global face recognition service instance"""
    global _unified_service

    if _unified_service is None:
        _unified_service = UnifiedFaceRecognitionService(preferred_engine)

    return _unified_service


# Convenience functions for backward compatibility
def verify_face(user_id: int, image_path: str, **kwargs) -> VerificationResult:
    """Convenience function for face verification"""
    service = get_face_recognition_service()
    return service.verify_face(user_id, image_path, **kwargs)


def assess_image_quality(image_path: str) -> Dict[str, Any]:
    """Convenience function for image quality assessment"""
    service = get_face_recognition_service()
    return service.assess_image_quality(image_path)