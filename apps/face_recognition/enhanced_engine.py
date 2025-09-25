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
from typing import Dict, List, Optional, Tuple, Any, Union
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import (
    FaceRecognitionModel, FaceEmbedding, FaceVerificationLog,
    AntiSpoofingModel, FaceQualityMetrics
)

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
            
        except Exception as e:
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
            
        except Exception as e:
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
            
        except Exception as e:
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
            
            # Basic quality metrics
            height, width = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Sharpness (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 100.0)  # Normalize
            
            # Brightness (mean intensity)
            mean_brightness = np.mean(gray)
            brightness_score = 1.0 - abs(mean_brightness - 127) / 127.0  # Optimal around 127
            
            # Contrast (standard deviation)
            contrast = np.std(gray)
            contrast_score = min(1.0, contrast / 64.0)  # Normalize
            
            # Face size assessment (mock for now)
            face_size_score = 0.8 if min(width, height) >= 200 else 0.5
            
            # Overall quality
            overall_quality = (sharpness_score * 0.3 + 
                             brightness_score * 0.25 + 
                             contrast_score * 0.25 + 
                             face_size_score * 0.2)
            
            # Identify issues
            quality_issues = []
            if sharpness_score < 0.5:
                quality_issues.append('LOW_SHARPNESS')
            if brightness_score < 0.5:
                quality_issues.append('POOR_LIGHTING')
            if contrast_score < 0.4:
                quality_issues.append('LOW_CONTRAST')
            if face_size_score < 0.7:
                quality_issues.append('SMALL_FACE_SIZE')
            
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
                    face_pose_score=0.8,  # Mock value
                    eye_visibility_score=0.8,  # Mock value
                    resolution_width=width,
                    resolution_height=height,
                    file_size_bytes=os.path.getsize(image_path),
                    face_detection_confidence=0.9,  # Mock value
                    landmark_quality={'quality': 'good'},
                    quality_issues=quality_issues,
                    improvement_suggestions=[]
                )
            except Exception as e:
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
            
        except Exception as e:
            logger.error(f"Error assessing image quality: {str(e)}")
            return {
                'overall_quality': 0.0,
                'error': str(e)
            }
    
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
            
        except Exception as e:
            logger.error(f"Error in anti-spoofing detection: {str(e)}")
            return {
                'spoof_detected': False,
                'spoof_score': 0.0,
                'liveness_score': 1.0,
                'error': str(e)
            }
    
    def _get_user_embeddings(self, user_id: int) -> List[FaceEmbedding]:
        """Get face embeddings for a user"""
        try:
            embeddings = FaceEmbedding.objects.filter(
                user_id=user_id,
                is_validated=True
            ).select_related('extraction_model')
            
            return list(embeddings)
            
        except Exception as e:
            logger.error(f"Error getting user embeddings: {str(e)}")
            return []
    
    def _extract_features(self, image_path: str) -> Dict[str, np.ndarray]:
        """Extract features using multiple models"""
        try:
            features = {}
            
            for model_name, model in self.models.items():
                try:
                    feature_vector = model.extract_features(image_path)
                    if feature_vector is not None:
                        features[model_name] = feature_vector
                except Exception as e:
                    logger.warning(f"Error extracting features with {model_name}: {str(e)}")
                    continue
            
            return features
            
        except Exception as e:
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
                
                model_results[model_name] = {
                    'similarity': best_similarity,
                    'distance': 1.0 - best_similarity,
                    'matched_embedding_id': model_embeddings[best_embedding_idx].id if similarities else None,
                    'threshold_met': best_similarity >= (1.0 - self.config.get('similarity_threshold', 0.3))
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
                threshold_met = ensemble_distance <= self.config.get('similarity_threshold', 0.3)
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
            
        except Exception as e:
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
            
        except Exception as e:
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
            
        except Exception as e:
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
            
        except Exception as e:
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
                    
            except Exception as e:
                logger.warning(f"Error checking fraud history: {str(e)}")
            
            return {
                'fraud_risk_score': min(1.0, fraud_score),
                'fraud_indicators': fraud_indicators
            }
            
        except Exception as e:
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
            
        except Exception as e:
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
            
        except Exception as e:
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
            
        except Exception as e:
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
                    
        except Exception as e:
            logger.error(f"Error updating model statistics: {str(e)}")
    
    def _calculate_image_hash(self, image_path: str) -> str:
        """Calculate SHA256 hash of image file"""
        try:
            if not os.path.exists(image_path):
                return hashlib.sha256(image_path.encode()).hexdigest()[:16]
            
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            return file_hash[:16]  # Truncate for storage
            
        except Exception as e:
            logger.error(f"Error calculating image hash: {str(e)}")
            return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]


# Mock models for development/testing
class MockFaceNetModel:
    """Mock FaceNet model for development"""
    
    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock FaceNet model"""
        try:
            # Return mock 512-dimensional vector
            np.random.seed(42)  # Consistent results for testing
            features = np.random.normal(0, 1, 512)
            # Normalize
            features = features / np.linalg.norm(features)
            return features
        except:
            return None


class MockArcFaceModel:
    """Mock ArcFace model for development"""
    
    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock ArcFace model"""
        try:
            # Return mock 512-dimensional vector with different seed
            np.random.seed(43)
            features = np.random.normal(0, 1, 512)
            features = features / np.linalg.norm(features)
            return features
        except:
            return None


class MockInsightFaceModel:
    """Mock InsightFace model for development"""
    
    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract features using mock InsightFace model"""
        try:
            # Return mock 512-dimensional vector with different seed
            np.random.seed(44)
            features = np.random.normal(0, 1, 512)
            features = features / np.linalg.norm(features)
            return features
        except:
            return None


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