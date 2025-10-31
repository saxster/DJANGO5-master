"""
Enhanced Face Recognition Engine for YOUTILITY5
Multi-model ensemble with anti-spoofing and fraud detection capabilities
"""

import logging
import numpy as np
import cv2
import os
import time
import hashlib
from typing import Optional, Dict, Any, List
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

from apps.face_recognition.models import (
    FaceRecognitionModel, FaceEmbedding, FaceVerificationLog,
    AntiSpoofingModel, FaceQualityMetrics
)
from apps.core.exceptions import SecurityException, IntegrationException

logger = logging.getLogger(__name__)


class EnhancedFaceRecognitionEngine:
    """Enhanced face recognition with multiple models and anti-spoofing"""
    
    def __init__(self):
        """Initialize enhanced face recognition engine"""
        self.models = {}
        self.anti_spoofing_models = {}
        self.ensemble_weights = {
            'FACENET512': 0.4,
            'ARCFACE': 0.3,
            'INSIGHTFACE': 0.3
        }
        
        # Load configuration
        self.load_configuration()
        
        # Initialize models
        self._initialize_models()
    
    def load_configuration(self):
        """Load system configuration"""
        try:
            from .models import FaceRecognitionConfig
            
            # Load system configuration
            system_configs = FaceRecognitionConfig.objects.filter(
                config_type='SYSTEM',
                is_active=True
            ).order_by('priority')
            
            self.config = {
                'similarity_threshold': 0.3,
                'confidence_threshold': 0.7,
                'liveness_threshold': 0.5,
                'enable_anti_spoofing': True,
                'enable_ensemble': True,
                'max_processing_time_ms': 5000,
                'enable_quality_assessment': True
            }
            
            # Apply configurations
            for config in system_configs:
                self.config.update(config.config_data)
                
            logger.info("Face recognition configuration loaded")
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Use defaults
    
    def _initialize_models(self):
        """Initialize face recognition models"""
        try:
            # Initialize mock models for now
            # In production, this would load actual ML models
            
            self.models = {
                'FACENET512': MockFaceNetModel(),
                'ARCFACE': MockArcFaceModel(),
                'INSIGHTFACE': MockInsightFaceModel()
            }
            
            self.anti_spoofing_models = {
                'TEXTURE_BASED': MockAntiSpoofingModel(),
                'MOTION_BASED': MockMotionAntiSpoofingModel()
            }
            
            logger.info("Face recognition models initialized")
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error initializing models: {str(e)}")
    
    def verify_face(
        self,
        user_id: int,
        image_path: str,
        attendance_record_id: Optional[int] = None,
        enable_anti_spoofing: bool = True
    ) -> Dict[str, Any]:
        """
        Enhanced face verification with ensemble models and anti-spoofing
        
        Args:
            user_id: ID of the user to verify
            image_path: Path to the image for verification
            attendance_record_id: Optional attendance record ID
            enable_anti_spoofing: Whether to enable anti-spoofing detection
            
        Returns:
            Comprehensive verification results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting enhanced face verification for user {user_id}")
            
            result = {
                'user_id': user_id,
                'image_path': image_path,
                'verified': False,
                'confidence': 0.0,
                'similarity_score': 0.0,
                'processing_time_ms': 0.0,
                'model_results': {},
                'anti_spoofing_result': {},
                'quality_metrics': {},
                'fraud_indicators': [],
                'recommendations': []
            }
            
            # 1. Image quality assessment
            quality_result = self._assess_image_quality(image_path)
            result['quality_metrics'] = quality_result
            
            if quality_result['overall_quality'] < 0.3:
                result['verified'] = False
                result['fraud_indicators'].append('LOW_IMAGE_QUALITY')
                result['recommendations'].append('Capture image with better lighting and focus')
                return self._finalize_result(result, start_time, user_id, attendance_record_id)
            
            # 2. Anti-spoofing detection (if enabled)
            if enable_anti_spoofing and self.config.get('enable_anti_spoofing', True):
                anti_spoof_result = self._detect_spoofing(image_path)
                result['anti_spoofing_result'] = anti_spoof_result
                
                if anti_spoof_result['spoof_detected']:
                    result['verified'] = False
                    result['fraud_indicators'].extend(anti_spoof_result.get('fraud_indicators', []))
                    result['recommendations'].append('Use live face for verification')
                    return self._finalize_result(result, start_time, user_id, attendance_record_id)
            
            # 3. Get user embeddings
            user_embeddings = self._get_user_embeddings(user_id)
            if not user_embeddings:
                result['verified'] = False
                result['fraud_indicators'].append('NO_REGISTERED_EMBEDDINGS')
                result['recommendations'].append('Complete face enrollment process')
                return self._finalize_result(result, start_time, user_id, attendance_record_id)
            
            # 4. Extract features from input image
            input_features = self._extract_features(image_path)
            if not input_features:
                result['verified'] = False
                result['fraud_indicators'].append('FEATURE_EXTRACTION_FAILED')
                result['recommendations'].append('Capture clearer image')
                return self._finalize_result(result, start_time, user_id, attendance_record_id)
            
            # 5. Perform ensemble verification
            if self.config.get('enable_ensemble', True):
                verification_result = self._ensemble_verification(input_features, user_embeddings)
            else:
                # Fallback to single model (FaceNet512)
                verification_result = self._single_model_verification(input_features, user_embeddings, 'FACENET512')
            
            result.update(verification_result)
            
            # 6. Fraud risk assessment
            fraud_assessment = self._assess_fraud_risk(result, user_id)
            result['fraud_risk_score'] = fraud_assessment['fraud_risk_score']
            result['fraud_indicators'].extend(fraud_assessment.get('fraud_indicators', []))
            
            # 7. Final verification decision
            result['verified'] = self._make_verification_decision(result)
            
            return self._finalize_result(result, start_time, user_id, attendance_record_id)
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error in face verification: {str(e)}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            
            return {
                'user_id': user_id,
                'verified': False,
                'confidence': 0.0,
                'error': str(e),
                'processing_time_ms': processing_time,
                'fraud_indicators': ['VERIFICATION_ERROR']
            }
    
    def _assess_image_quality(self, image_path: str) -> Dict[str, Any]:
        """Assess image quality for face recognition"""
        try:
            # Calculate image hash
            image_hash = self._calculate_image_hash(image_path)
            
            # Check if already analyzed
            try:
                quality_metrics = FaceQualityMetrics.objects.get(image_hash=image_hash)
                return {
                    'overall_quality': quality_metrics.overall_quality,
                    'sharpness_score': quality_metrics.sharpness_score,
                    'brightness_score': quality_metrics.brightness_score,
                    'contrast_score': quality_metrics.contrast_score,
                    'face_size_score': quality_metrics.face_size_score,
                    'quality_issues': quality_metrics.quality_issues,
                    'cached': True
                }
            except FaceQualityMetrics.DoesNotExist:
                pass
            
            # Perform quality assessment
            if not os.path.exists(image_path):
                return {
                    'overall_quality': 0.0,
                    'error': 'Image file not found'
                }
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {
                    'overall_quality': 0.0,
                    'error': 'Could not load image'
                }
            
            # Convert to grayscale for analysis
            height, width = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect face first for ROI-based quality assessment
            face_roi, face_confidence = self._detect_face_roi(image)

            if face_roi is not None:
                # Extract face region for quality assessment
                x, y, w, h = face_roi
                face_gray = gray[y:y+h, x:x+w]
                face_color = image[y:y+h, x:x+w]

                # Face-specific quality metrics
                sharpness_score = self._calculate_roi_sharpness(face_gray)
                brightness_score = self._calculate_roi_brightness(face_gray)
                contrast_score = self._calculate_roi_contrast(face_gray)
                face_size_score = self._calculate_face_size_score(w, h, width, height)
                pose_score = self._estimate_face_pose_quality(face_color)
                eye_visibility = self._check_eye_visibility(face_color, face_roi)

                overall_quality = np.mean([
                    sharpness_score, brightness_score, contrast_score,
                    face_size_score, pose_score, eye_visibility
                ])
            else:
                # Fallback to whole-image assessment if no face detected
                sharpness_score = self._calculate_roi_sharpness(gray)
                brightness_score = self._calculate_roi_brightness(gray)
                contrast_score = self._calculate_roi_contrast(gray)
                face_size_score = 0.0  # No face detected
                pose_score = 0.0
                eye_visibility = 0.0
                face_confidence = 0.0

                overall_quality = 0.1  # Very low quality if no face
            
            # Identify issues based on face ROI assessment
            quality_issues = []
            if face_roi is None:
                quality_issues.append('NO_FACE_DETECTED')
            else:
                if sharpness_score < 0.5:
                    quality_issues.append('LOW_SHARPNESS')
                if brightness_score < 0.5:
                    quality_issues.append('POOR_LIGHTING')
                if contrast_score < 0.4:
                    quality_issues.append('LOW_CONTRAST')
                if face_size_score < 0.7:
                    quality_issues.append('SMALL_FACE_SIZE')
                if pose_score < 0.6:
                    quality_issues.append('POOR_FACE_POSE')
                if eye_visibility < 0.5:
                    quality_issues.append('EYES_NOT_VISIBLE')
                if face_confidence < 0.7:
                    quality_issues.append('LOW_DETECTION_CONFIDENCE')
            
            # Save quality metrics
            try:
                FaceQualityMetrics.objects.create(
                    image_path=image_path,
                    image_hash=image_hash,
                    overall_quality=overall_quality,
                    sharpness_score=sharpness_score,
                    brightness_score=brightness_score,
                    contrast_score=contrast_score,
                    face_size_score=face_size_score,
                    face_pose_score=pose_score if face_roi else 0.0,
                    eye_visibility_score=eye_visibility if face_roi else 0.0,
                    resolution_width=width,
                    resolution_height=height,
                    file_size_bytes=os.path.getsize(image_path) if os.path.exists(image_path) else 0,
                    face_detection_confidence=face_confidence,
                    landmark_quality={'detected': face_roi is not None},
                    quality_issues=quality_issues,
                    improvement_suggestions=self._generate_improvement_suggestions(quality_issues)
                )
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.warning(f"Could not save quality metrics: {str(e)}")
            
            return {
                'overall_quality': overall_quality,
                'sharpness_score': sharpness_score,
                'brightness_score': brightness_score,
                'contrast_score': contrast_score,
                'face_size_score': face_size_score,
                'quality_issues': quality_issues,
                'cached': False
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error assessing image quality: {str(e)}")
            return {
                'overall_quality': 0.0,
                'error': str(e)
            }

    def _detect_face_roi(self, image) -> tuple:
        """Detect face region of interest using Haar cascades"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Use Haar cascade for face detection (lightweight)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            if len(faces) > 0:
                # Return the largest face
                largest_face = max(faces, key=lambda face: face[2] * face[3])
                x, y, w, h = largest_face
                confidence = 0.8  # Mock confidence for Haar cascade
                return (x, y, w, h), confidence

            return None, 0.0

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error detecting face ROI: {str(e)}")
            return None, 0.0

    def _calculate_roi_sharpness(self, roi_gray):
        """Calculate sharpness score for a specific ROI using Laplacian variance"""
        try:
            laplacian_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
            # Normalize to 0-1 range (100 is empirically good threshold)
            return min(1.0, laplacian_var / 100.0)
        except (cv2.error, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI sharpness: {e}")
            return 0.0

    def _calculate_roi_brightness(self, roi_gray):
        """Calculate brightness adequacy score for ROI"""
        try:
            mean_brightness = np.mean(roi_gray)
            # Optimal brightness around 127 (middle gray)
            return 1.0 - abs(mean_brightness - 127) / 127.0
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI brightness: {e}")
            return 0.0

    def _calculate_roi_contrast(self, roi_gray):
        """Calculate contrast score for ROI"""
        try:
            contrast = np.std(roi_gray)
            # Normalize (64 is empirically good threshold)
            return min(1.0, contrast / 64.0)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI contrast: {e}")
            return 0.0

    def _calculate_face_size_score(self, face_w, face_h, img_w, img_h):
        """Calculate face size adequacy score"""
        try:
            face_area = face_w * face_h
            img_area = img_w * img_h
            face_ratio = face_area / img_area

            # Optimal face ratio between 0.1 and 0.4 (10-40% of image)
            if 0.1 <= face_ratio <= 0.4:
                return 1.0
            elif face_ratio < 0.1:
                return face_ratio / 0.1  # Scale from 0 to 1
            else:
                return max(0.1, 1.0 - (face_ratio - 0.4) / 0.6)  # Decrease for very large faces
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"Failed to calculate face size score: {e}")
            return 0.0

    def _estimate_face_pose_quality(self, face_color):
        """Estimate face pose quality (simplified implementation)"""
        try:
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(face_color, cv2.COLOR_BGR2GRAY)

            # Simple symmetry check as pose quality indicator
            height, width = gray.shape
            left_half = gray[:, :width//2]
            right_half = cv2.flip(gray[:, width//2:], 1)

            # Resize to ensure same dimensions
            min_width = min(left_half.shape[1], right_half.shape[1])
            left_half = left_half[:, :min_width]
            right_half = right_half[:, :min_width]

            # Calculate correlation between halves
            correlation = np.corrcoef(left_half.flatten(), right_half.flatten())[0, 1]

            # Convert correlation to 0-1 score
            return max(0.0, min(1.0, (correlation + 1) / 2))
        except (cv2.error, ValueError, TypeError, AttributeError, IndexError) as e:
            logger.warning(f"Failed to estimate face pose quality: {e}")
            return 0.5  # Default neutral score

    def _check_eye_visibility(self, face_color, face_roi):
        """Check if eyes are visible in the face (simplified implementation)"""
        try:
            # Use eye cascade to detect eyes
            gray = cv2.cvtColor(face_color, cv2.COLOR_BGR2GRAY)
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(10, 10))

            # Score based on number of eyes detected (2 is optimal)
            if len(eyes) >= 2:
                return 1.0
            elif len(eyes) == 1:
                return 0.7
            else:
                return 0.2  # Some visibility assumed even without detection
        except (cv2.error, ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Failed to check eye visibility: {e}")
            return 0.5  # Default score

    def _generate_improvement_suggestions(self, quality_issues):
        """Generate actionable suggestions based on quality issues"""
        suggestions = []

        if 'NO_FACE_DETECTED' in quality_issues:
            suggestions.append("Ensure face is clearly visible in the image")
        if 'LOW_SHARPNESS' in quality_issues:
            suggestions.append("Reduce camera shake and ensure proper focus")
        if 'POOR_LIGHTING' in quality_issues:
            suggestions.append("Improve lighting conditions - avoid overexposure or underexposure")
        if 'LOW_CONTRAST' in quality_issues:
            suggestions.append("Increase image contrast or improve lighting uniformity")
        if 'SMALL_FACE_SIZE' in quality_issues:
            suggestions.append("Move closer to camera or use higher resolution image")
        if 'POOR_FACE_POSE' in quality_issues:
            suggestions.append("Face the camera more directly")
        if 'EYES_NOT_VISIBLE' in quality_issues:
            suggestions.append("Ensure eyes are clearly visible and not obstructed")
        if 'LOW_DETECTION_CONFIDENCE' in quality_issues:
            suggestions.append("Improve overall image quality and face visibility")

        return suggestions

    def _detect_spoofing(self, image_path: str) -> Dict[str, Any]:
        """Detect spoofing attempts using anti-spoofing models"""
        try:
            spoof_scores = {}
            fraud_indicators = []
            
            # Run texture-based anti-spoofing
            if 'TEXTURE_BASED' in self.anti_spoofing_models:
                texture_result = self.anti_spoofing_models['TEXTURE_BASED'].detect_spoof(image_path)
                spoof_scores['texture'] = texture_result['spoof_score']
                
                if texture_result['spoof_detected']:
                    fraud_indicators.append('TEXTURE_SPOOFING_DETECTED')
            
            # Run motion-based anti-spoofing (if video/sequence available)
            if 'MOTION_BASED' in self.anti_spoofing_models:
                motion_result = self.anti_spoofing_models['MOTION_BASED'].detect_spoof(image_path)
                spoof_scores['motion'] = motion_result['spoof_score']
                
                if motion_result['spoof_detected']:
                    fraud_indicators.append('MOTION_SPOOFING_DETECTED')
            
            # Aggregate results
            avg_spoof_score = np.mean(list(spoof_scores.values())) if spoof_scores else 0.0
            spoof_detected = avg_spoof_score > self.config.get('liveness_threshold', 0.5)
            
            return {
                'spoof_detected': spoof_detected,
                'spoof_score': avg_spoof_score,
                'liveness_score': 1.0 - avg_spoof_score,
                'model_scores': spoof_scores,
                'fraud_indicators': fraud_indicators
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error in anti-spoofing detection: {str(e)}")
            return {
                'spoof_detected': False,
                'spoof_score': 0.0,
                'liveness_score': 1.0,
                'error': str(e)
            }
    
    def _get_user_embeddings(self, user_id: int) -> List[FaceEmbedding]:
        """Get face embeddings for a user with caching"""
        from django.core.cache import cache

        # Cache key with user ID and version for cache invalidation
        cache_key = f"fr_embeddings:{user_id}"

        try:
            # Try to get from cache first
            cached_embeddings = cache.get(cache_key)
            if cached_embeddings is not None:
                logger.debug(f"Cache hit for user embeddings: {user_id}")
                return cached_embeddings

            # Cache miss - query database
            logger.debug(f"Cache miss for user embeddings: {user_id}")
            embeddings = FaceEmbedding.objects.filter(
                user_id=user_id,
                is_validated=True
            ).select_related('extraction_model')

            embedding_list = list(embeddings)

            # Cache for 5 minutes (300 seconds)
            if embedding_list:
                cache.set(cache_key, embedding_list, timeout=300)
                logger.debug(f"Cached {len(embedding_list)} embeddings for user {user_id}")

            return embedding_list

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error getting user embeddings: {str(e)}")
            return []

    def invalidate_user_embedding_cache(self, user_id: int):
        """Invalidate cached embeddings for a user"""
        from django.core.cache import cache
        cache_key = f"fr_embeddings:{user_id}"
        cache.delete(cache_key)
        logger.debug(f"Invalidated embedding cache for user {user_id}")

    def _extract_features(self, image_path: str) -> Dict[str, np.ndarray]:
        """Extract features using multiple models"""
        try:
            features = {}
            
            for model_name, model in self.models.items():
                try:
                    feature_vector = model.extract_features(image_path)
                    if feature_vector is not None:
                        features[model_name] = feature_vector
                except (AttributeError, TypeError, ValueError) as e:
                    logger.warning(f"Error extracting features with {model_name}: {str(e)}")
                    continue
            
            return features
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error extracting features: {str(e)}")
            return {}
    
    def _ensemble_verification(
        self, 
        input_features: Dict[str, np.ndarray], 
        user_embeddings: List[FaceEmbedding]
    ) -> Dict[str, Any]:
        """Perform ensemble verification using multiple models"""
        try:
            model_results = {}
            weighted_scores = []
            
            for model_name, features in input_features.items():
                if model_name not in self.ensemble_weights:
                    continue
                
                # Find matching embeddings for this model
                model_embeddings = [
                    emb for emb in user_embeddings 
                    if emb.extraction_model.model_type == model_name
                ]
                
                if not model_embeddings:
                    continue
                
                # Calculate similarities with all embeddings from this model
                similarities = []
                for embedding in model_embeddings:
                    similarity = self._calculate_cosine_similarity(
                        features, np.array(embedding.embedding_vector)
                    )
                    similarities.append(similarity)
                
                # Take the best match
                best_similarity = max(similarities) if similarities else 0.0
                best_embedding_idx = similarities.index(best_similarity) if similarities else 0
                
                # Use distance threshold consistently
                distance_threshold = self.config.get('similarity_threshold', 0.3)
                best_distance = 1.0 - best_similarity

                model_results[model_name] = {
                    'similarity': best_similarity,
                    'distance': best_distance,
                    'matched_embedding_id': model_embeddings[best_embedding_idx].id if similarities else None,
                    'threshold_met': best_distance <= distance_threshold
                }
                
                # Add to weighted average
                weight = self.ensemble_weights[model_name]
                weighted_scores.append(weight * best_similarity)
            
            # Calculate ensemble results
            if weighted_scores:
                ensemble_similarity = sum(weighted_scores) / sum(
                    self.ensemble_weights[name] for name in model_results.keys()
                )
                ensemble_distance = 1.0 - ensemble_similarity
                ensemble_confidence = self._calculate_confidence(model_results, ensemble_similarity)
                
                # Determine if verification passed
                distance_threshold = self.config.get('similarity_threshold', 0.3)
                threshold_met = ensemble_distance <= distance_threshold
                confidence_met = ensemble_confidence >= self.config.get('confidence_threshold', 0.7)
                
                return {
                    'model_results': model_results,
                    'ensemble_similarity': ensemble_similarity,
                    'ensemble_distance': ensemble_distance,
                    'confidence': ensemble_confidence,
                    'threshold_met': threshold_met,
                    'confidence_met': confidence_met,
                    'similarity_score': ensemble_similarity
                }
            else:
                return {
                    'model_results': {},
                    'ensemble_similarity': 0.0,
                    'ensemble_distance': 1.0,
                    'confidence': 0.0,
                    'threshold_met': False,
                    'confidence_met': False,
                    'similarity_score': 0.0,
                    'error': 'No models produced valid results'
                }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in ensemble verification: {str(e)}")
            return {
                'ensemble_similarity': 0.0,
                'ensemble_distance': 1.0,
                'confidence': 0.0,
                'threshold_met': False,
                'confidence_met': False,
                'similarity_score': 0.0,
                'error': str(e)
            }
    
    def _single_model_verification(
        self, 
        input_features: Dict[str, np.ndarray], 
        user_embeddings: List[FaceEmbedding],
        model_name: str
    ) -> Dict[str, Any]:
        """Perform verification using a single model"""
        try:
            if model_name not in input_features:
                return {
                    'similarity_score': 0.0,
                    'confidence': 0.0,
                    'threshold_met': False,
                    'error': f'No features extracted for {model_name}'
                }
            
            features = input_features[model_name]
            
            # Find embeddings for this model
            model_embeddings = [
                emb for emb in user_embeddings 
                if emb.extraction_model.model_type == model_name
            ]
            
            if not model_embeddings:
                return {
                    'similarity_score': 0.0,
                    'confidence': 0.0,
                    'threshold_met': False,
                    'error': f'No embeddings found for {model_name}'
                }
            
            # Calculate similarities
            similarities = []
            for embedding in model_embeddings:
                similarity = self._calculate_cosine_similarity(
                    features, np.array(embedding.embedding_vector)
                )
                similarities.append(similarity)
            
            best_similarity = max(similarities)
            distance = 1.0 - best_similarity
            
            return {
                'similarity_score': best_similarity,
                'distance': distance,
                'confidence': best_similarity,  # Simple confidence
                'threshold_met': distance <= self.config.get('similarity_threshold', 0.3),
                'model_results': {
                    model_name: {
                        'similarity': best_similarity,
                        'distance': distance,
                        'threshold_met': distance <= self.config.get('similarity_threshold', 0.3)
                    }
                }
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in single model verification: {str(e)}")
            return {
                'similarity_score': 0.0,
                'confidence': 0.0,
                'threshold_met': False,
                'error': str(e)
            }
    
    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Normalize vectors
            vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
            vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
            
            # Calculate cosine similarity
            similarity = np.dot(vec1_norm, vec2_norm)
            
            # Ensure similarity is in [0, 1] range
            similarity = max(0.0, min(1.0, similarity))
            
            return float(similarity)
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0
    
    def _calculate_confidence(
        self, 
        model_results: Dict[str, Any], 
        ensemble_similarity: float
    ) -> float:
        """Calculate confidence score for ensemble result"""
        try:
            # Factors affecting confidence:
            # 1. Number of models that agreed
            # 2. Consistency between models
            # 3. Overall similarity score
            
            threshold = 1.0 - self.config.get('similarity_threshold', 0.3)
            agreeing_models = sum(
                1 for result in model_results.values() 
                if result.get('threshold_met', False)
            )
            
            total_models = len(model_results)
            
            if total_models == 0:
                return 0.0
            
            # Agreement factor (0-1)
            agreement_factor = agreeing_models / total_models
            
            # Consistency factor - how similar are the model results
            similarities = [result.get('similarity', 0) for result in model_results.values()]
            if len(similarities) > 1:
                consistency_factor = 1.0 - np.std(similarities)
            else:
                consistency_factor = 1.0
            
            # Similarity factor
            similarity_factor = ensemble_similarity
            
            # Overall confidence
            confidence = (
                agreement_factor * 0.4 + 
                consistency_factor * 0.3 + 
                similarity_factor * 0.3
            )
            
            return max(0.0, min(1.0, confidence))
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0.0
    
    def _assess_fraud_risk(self, result: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Assess fraud risk based on verification results"""
        try:
            fraud_indicators = result.get('fraud_indicators', []).copy()
            fraud_score = 0.0
            
            # Low confidence indicates potential fraud
            confidence = result.get('confidence', 0)
            if confidence < 0.5:
                fraud_score += 0.3
                fraud_indicators.append('LOW_VERIFICATION_CONFIDENCE')
            
            # Poor image quality can indicate spoofing
            quality = result.get('quality_metrics', {}).get('overall_quality', 1.0)
            if quality < 0.4:
                fraud_score += 0.2
                fraud_indicators.append('POOR_IMAGE_QUALITY')
            
            # Anti-spoofing detection
            if result.get('anti_spoofing_result', {}).get('spoof_detected', False):
                fraud_score += 0.5
                fraud_indicators.extend(result['anti_spoofing_result'].get('fraud_indicators', []))
            
            # Model inconsistency (ensemble only)
            model_results = result.get('model_results', {})
            if len(model_results) > 1:
                similarities = [r.get('similarity', 0) for r in model_results.values()]
                if np.std(similarities) > 0.2:  # High variance between models
                    fraud_score += 0.2
                    fraud_indicators.append('MODEL_INCONSISTENCY')
            
            # Historical fraud patterns (check recent verifications)
            try:
                recent_fraudulent = FaceVerificationLog.objects.filter(
                    user_id=user_id,
                    verification_timestamp__gte=timezone.now() - timezone.timedelta(days=7),
                    fraud_risk_score__gt=0.6
                ).count()
                
                if recent_fraudulent > 2:
                    fraud_score += 0.3
                    fraud_indicators.append('RECENT_FRAUD_HISTORY')
                    
            except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
                logger.warning(f"Error checking fraud history: {str(e)}")
            
            return {
                'fraud_risk_score': min(1.0, fraud_score),
                'fraud_indicators': fraud_indicators
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error assessing fraud risk: {str(e)}")
            return {
                'fraud_risk_score': 0.0,
                'fraud_indicators': []
            }
    
    def _make_verification_decision(self, result: Dict[str, Any]) -> bool:
        """Make final verification decision based on all factors"""
        try:
            # Basic threshold check
            threshold_met = result.get('threshold_met', False)
            confidence_met = result.get('confidence_met', False)
            
            # Fraud risk check
            fraud_risk = result.get('fraud_risk_score', 0)
            high_fraud_risk = fraud_risk > 0.7
            
            # Anti-spoofing check
            spoof_detected = result.get('anti_spoofing_result', {}).get('spoof_detected', False)
            
            # Quality check
            quality = result.get('quality_metrics', {}).get('overall_quality', 0)
            quality_sufficient = quality >= 0.3
            
            # Final decision logic
            verified = (
                threshold_met and 
                confidence_met and 
                not high_fraud_risk and 
                not spoof_detected and 
                quality_sufficient
            )
            
            return verified
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error making verification decision: {str(e)}")
            return False
    
    def _finalize_result(
        self, 
        result: Dict[str, Any], 
        start_time: float,
        user_id: int,
        attendance_record_id: Optional[int]
    ) -> Dict[str, Any]:
        """Finalize verification result and log to database"""
        try:
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            result['processing_time_ms'] = processing_time
            
            # Log verification attempt
            self._log_verification_attempt(result, user_id, attendance_record_id)
            
            # Update model statistics
            self._update_model_statistics(result)
            
            return result
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error finalizing result: {str(e)}")
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            return result
    
    def _log_verification_attempt(
        self, 
        result: Dict[str, Any], 
        user_id: int,
        attendance_record_id: Optional[int]
    ):
        """Log verification attempt to database"""
        try:
            # Determine result status
            if result.get('verified', False):
                verification_result = FaceVerificationLog.VerificationResult.SUCCESS
            elif 'error' in result:
                verification_result = FaceVerificationLog.VerificationResult.ERROR
            elif result.get('anti_spoofing_result', {}).get('spoof_detected', False):
                verification_result = FaceVerificationLog.VerificationResult.REJECTED
            else:
                verification_result = FaceVerificationLog.VerificationResult.FAILED
            
            # Get primary model (for compatibility)
            primary_model = FaceRecognitionModel.objects.filter(
                model_type='FACENET512',
                status='ACTIVE'
            ).first()
            
            if not primary_model:
                primary_model = FaceRecognitionModel.objects.filter(
                    status='ACTIVE'
                ).first()
            
            # Create verification log
            log_entry = FaceVerificationLog.objects.create(
                user_id=user_id,
                attendance_record_id=attendance_record_id,
                result=verification_result,
                verification_model=primary_model,
                similarity_score=result.get('similarity_score', 0.0),
                confidence_score=result.get('confidence', 0.0),
                liveness_score=result.get('anti_spoofing_result', {}).get('liveness_score'),
                spoof_detected=result.get('anti_spoofing_result', {}).get('spoof_detected', False),
                input_image_path=result.get('image_path'),
                input_image_hash=self._calculate_image_hash(result.get('image_path', '')),
                processing_time_ms=result.get('processing_time_ms', 0),
                error_message=result.get('error'),
                verification_metadata=result,
                fraud_indicators=result.get('fraud_indicators', []),
                fraud_risk_score=result.get('fraud_risk_score', 0.0)
            )
            
            logger.info(f"Verification attempt logged: {log_entry.id}")
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error logging verification attempt: {str(e)}")
    
    def _update_model_statistics(self, result: Dict[str, Any]):
        """Update model usage statistics"""
        try:
            model_results = result.get('model_results', {})
            
            for model_name, model_result in model_results.items():
                try:
                    model = FaceRecognitionModel.objects.get(
                        model_type=model_name,
                        status='ACTIVE'
                    )
                    
                    model.verification_count += 1
                    if result.get('verified', False):
                        model.successful_verifications += 1
                    
                    model.last_used = timezone.now()
                    model.save(update_fields=['verification_count', 'successful_verifications', 'last_used'])
                    
                except FaceRecognitionModel.DoesNotExist:
                    continue
                    
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error updating model statistics: {str(e)}")
    
    def _calculate_image_hash(self, image_path: str) -> str:
        """Calculate SHA256 hash of image file"""
        try:
            if not os.path.exists(image_path):
                return hashlib.sha256(image_path.encode()).hexdigest()[:16]
            
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            return file_hash[:16]  # Truncate for storage
            
        except (AttributeError, ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error calculating image hash: {str(e)}")
            return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]


# Mock models for development/testing
class MockFaceNetModel:
    """Mock FaceNet model for development"""

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock FaceNet model with image-dependent seeds"""
        try:
            # Generate image-dependent seed from image path/content hash
            image_hash = self._calculate_image_dependent_seed(image_path)
            np.random.seed(image_hash)  # Different seed for different images

            # Generate mock 512-dimensional vector
            features = np.random.normal(0, 1, 512)
            # Normalize
            features = features / np.linalg.norm(features)
            return features
        except (ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Failed to extract features (FaceNet): {e}")
            return None

    def _calculate_image_dependent_seed(self, image_path: str) -> int:
        """Calculate a deterministic seed based on image content or path"""
        import hashlib
        try:
            if os.path.exists(image_path):
                # Use first 1KB of file for hash (efficient for large images)
                with open(image_path, 'rb') as f:
                    content = f.read(1024)
                hash_obj = hashlib.sha256(content)
            else:
                # Fallback to path-based hash if file doesn't exist
                hash_obj = hashlib.sha256(image_path.encode())

            # Convert first 4 bytes of hash to integer seed
            return int.from_bytes(hash_obj.digest()[:4], byteorder='big')
        except (OSError, IOError, ValueError, TypeError) as e:
            logger.warning(f"Failed to calculate image-dependent seed (FaceNet): {e}")
            # Ultimate fallback: use path hash
            return hash(image_path) & 0xFFFFFFFF


class MockArcFaceModel:
    """Mock ArcFace model for development"""

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock ArcFace model with image-dependent seeds"""
        try:
            # Generate image-dependent seed (offset by 100 for model differentiation)
            image_hash = self._calculate_image_dependent_seed(image_path) + 100
            np.random.seed(image_hash)

            # Generate mock 512-dimensional vector
            features = np.random.normal(0, 1, 512)
            features = features / np.linalg.norm(features)
            return features
        except (ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Failed to extract features (ArcFace): {e}")
            return None

    def _calculate_image_dependent_seed(self, image_path: str) -> int:
        """Calculate a deterministic seed based on image content or path"""
        import hashlib
        try:
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    content = f.read(1024)
                hash_obj = hashlib.sha256(content)
            else:
                hash_obj = hashlib.sha256(image_path.encode())
            return int.from_bytes(hash_obj.digest()[:4], byteorder='big')
        except (OSError, IOError, ValueError, TypeError) as e:
            logger.warning(f"Failed to calculate image-dependent seed (ArcFace): {e}")
            # Ultimate fallback: use path hash
            return hash(image_path) & 0xFFFFFFFF


class MockInsightFaceModel:
    """Mock InsightFace model for development"""

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock InsightFace model with image-dependent seeds"""
        try:
            # Generate image-dependent seed (offset by 200 for model differentiation)
            image_hash = self._calculate_image_dependent_seed(image_path) + 200
            np.random.seed(image_hash)

            # Generate mock 512-dimensional vector
            features = np.random.normal(0, 1, 512)
            features = features / np.linalg.norm(features)
            return features
        except (ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Failed to extract features (InsightFace): {e}")
            return None

    def _calculate_image_dependent_seed(self, image_path: str) -> int:
        """Calculate a deterministic seed based on image content or path"""
        import hashlib
        try:
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    content = f.read(1024)
                hash_obj = hashlib.sha256(content)
            else:
                hash_obj = hashlib.sha256(image_path.encode())
            return int.from_bytes(hash_obj.digest()[:4], byteorder='big')
        except (OSError, IOError, ValueError, TypeError) as e:
            logger.warning(f"Failed to calculate image-dependent seed (InsightFace): {e}")
            # Ultimate fallback: use path hash
            return hash(image_path) & 0xFFFFFFFF


class MockAntiSpoofingModel:
    """Mock anti-spoofing model for development"""
    
    def detect_spoof(self, image_path: str) -> Dict[str, Any]:
        """Mock spoof detection"""
        return {
            'spoof_detected': False,
            'spoof_score': 0.2,  # Low spoof probability
            'confidence': 0.8
        }


class MockMotionAntiSpoofingModel:
    """Mock motion-based anti-spoofing model for development"""
    
    def detect_spoof(self, image_path: str) -> Dict[str, Any]:
        """Mock motion-based spoof detection"""
        return {
            'spoof_detected': False,
            'spoof_score': 0.1,
            'confidence': 0.9
        }