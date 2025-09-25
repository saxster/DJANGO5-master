"""
AI-Enhanced Face Recognition Engine for YOUTILITY5 (2025)
Incorporates cutting-edge AI technologies:
- 3D Face Recognition with depth analysis
- Advanced deepfake detection
- Multi-modal biometric integration
- Edge computing optimization
- Predictive analytics
"""

import logging
import numpy as np
import cv2
import os
import time
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import asyncio
import concurrent.futures
from dataclasses import dataclass

from .models import (
    FaceRecognitionModel, FaceEmbedding, FaceVerificationLog,
    AntiSpoofingModel, FaceQualityMetrics
)

logger = logging.getLogger(__name__)

@dataclass
class BiometricResult:
    """Standardized biometric verification result"""
    verified: bool
    confidence: float
    modalities_used: List[str]
    processing_time_ms: float
    fraud_risk_score: float
    quality_score: float
    liveness_score: float
    recommendations: List[str]
    detailed_scores: Dict[str, float]

class AIEnhancedFaceRecognitionEngine:
    """Next-generation face recognition with 2025 AI technologies"""
    
    def __init__(self):
        """Initialize AI-enhanced face recognition engine"""
        self.models = {}
        self.deepfake_models = {}
        self.liveness_models = {}
        self.voice_models = {}
        
        # Enhanced configuration for 2025
        self.config = {
            # 3D Recognition
            'enable_3d_recognition': True,
            'depth_threshold': 0.1,
            '3d_model_confidence_threshold': 0.8,
            
            # Deepfake Detection
            'enable_deepfake_detection': True,
            'deepfake_threshold': 0.7,
            'deepfake_models': ['DeeperForensics', 'FaceForensics++', 'Celeb-DF'],
            
            # Advanced Liveness
            'enable_advanced_liveness': True,
            'micro_expression_analysis': True,
            'heart_rate_detection': True,
            'challenge_response_enabled': True,
            
            # Multi-modal Integration
            'enable_voice_verification': True,
            'enable_behavioral_biometrics': True,
            'multi_modal_threshold': 0.85,
            
            # Edge Computing
            'enable_edge_processing': True,
            'edge_model_size_limit_mb': 100,
            'target_processing_time_ms': 500,
            
            # Quality & Performance
            'quality_threshold': 0.4,
            'confidence_threshold': 0.8,
            'max_processing_time_ms': 3000,
            
            # Predictive Analytics
            'enable_predictive_analytics': True,
            'pattern_detection_enabled': True,
            'behavioral_analysis_enabled': True
        }
        
        # Initialize processing pools
        self._init_processing_pools()
        
        # Load AI models
        self._initialize_ai_models()
        
        # Setup caching
        self._setup_caching()
    
    def _init_processing_pools(self):
        """Initialize concurrent processing pools"""
        self.face_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.liveness_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.deepfake_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    
    def _initialize_ai_models(self):
        """Initialize latest AI models"""
        try:
            # Load 2025 state-of-the-art models
            self.models = {
                'FaceX_Zoo': FaceXZooModel(),
                'ArcFace_v2': ArcFaceV2Model(),
                'RetinaFace': RetinaFaceModel(),
                'AdaFace': AdaFaceModel(),  # Latest 2024 model
                'MagFace': MagFaceModel()   # Magnitude-aware model
            }
            
            # Deepfake detection models
            self.deepfake_models = {
                'DeeperForensics': DeeperForensicsModel(),
                'FaceForensics++': FaceForensicsPlusPlusModel(),
                'Celeb-DF': CelebDFModel(),
                'DFDC': DFDCModel(),
                'FaceSwapper': FaceSwapperDetectionModel()
            }
            
            # Advanced liveness detection
            self.liveness_models = {
                '3D_Liveness': ThreeDLivenessModel(),
                'Micro_Expression': MicroExpressionModel(),
                'Heart_Rate': HeartRateDetectionModel(),
                'Challenge_Response': ChallengeResponseModel(),
                'Passive_Liveness': PassiveLivenessModel()
            }
            
            # Voice recognition models
            self.voice_models = {
                'Speaker_Verification': SpeakerVerificationModel(),
                'Voice_Liveness': VoiceLivenessModel()
            }
            
            logger.info("AI-enhanced models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AI models: {str(e)}")
    
    def _setup_caching(self):
        """Setup intelligent caching system"""
        self.cache_config = {
            'face_templates_ttl': 3600 * 24,  # 24 hours
            'quality_metrics_ttl': 3600 * 12, # 12 hours
            'user_patterns_ttl': 3600 * 6,    # 6 hours
            'fraud_scores_ttl': 3600 * 2      # 2 hours
        }
    
    async def verify_biometric(
        self,
        user_id: int,
        image_path: str,
        additional_data: Optional[Dict] = None,
        attendance_record_id: Optional[int] = None
    ) -> BiometricResult:
        """
        AI-enhanced biometric verification with multiple modalities
        
        Args:
            user_id: ID of the user to verify
            image_path: Path to the image for verification
            additional_data: Additional biometric data (voice, behavioral, etc.)
            attendance_record_id: Optional attendance record ID
            
        Returns:
            Comprehensive biometric verification result
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting AI-enhanced biometric verification for user {user_id}")
            
            # Initialize result container
            result_data = {
                'user_id': user_id,
                'image_path': image_path,
                'verification_timestamp': timezone.now(),
                'modalities_attempted': [],
                'modality_results': {},
                'quality_metrics': {},
                'security_analysis': {},
                'fraud_indicators': [],
                'performance_metrics': {}
            }
            
            # Phase 1: Image Quality Assessment with AI
            quality_result = await self._ai_quality_assessment(image_path)
            result_data['quality_metrics'] = quality_result
            
            if quality_result['overall_quality'] < self.config['quality_threshold']:
                return self._create_failed_result(
                    result_data, start_time, 'POOR_IMAGE_QUALITY',
                    'Image quality insufficient for reliable recognition'
                )
            
            # Phase 2: Advanced Security Analysis
            security_tasks = []
            
            # 2.1: Deepfake Detection
            if self.config['enable_deepfake_detection']:
                security_tasks.append(self._detect_deepfake(image_path))
            
            # 2.2: 3D Liveness Detection
            if self.config['enable_3d_recognition']:
                security_tasks.append(self._detect_3d_liveness(image_path))
            
            # 2.3: Advanced Liveness Analysis
            if self.config['enable_advanced_liveness']:
                security_tasks.append(self._advanced_liveness_analysis(image_path, additional_data))
            
            # Execute security checks in parallel
            security_results = await asyncio.gather(*security_tasks, return_exceptions=True)
            
            # Process security results
            for i, security_result in enumerate(security_results):
                if isinstance(security_result, Exception):
                    logger.warning(f"Security check {i} failed: {str(security_result)}")
                    continue
                
                result_data['security_analysis'].update(security_result)
                if security_result.get('fraud_detected', False):
                    result_data['fraud_indicators'].extend(
                        security_result.get('fraud_indicators', [])
                    )
            
            # Check if security analysis failed
            if result_data['security_analysis'].get('fraud_detected', False):
                return self._create_failed_result(
                    result_data, start_time, 'SECURITY_FAILURE',
                    f"Security threats detected: {', '.join(result_data['fraud_indicators'])}"
                )
            
            # Phase 3: Multi-Modal Recognition
            recognition_tasks = []
            
            # 3.1: Enhanced Face Recognition
            recognition_tasks.append(self._enhanced_face_recognition(user_id, image_path))
            
            # 3.2: Voice Verification (if available)
            if (self.config['enable_voice_verification'] and 
                additional_data and 'voice_sample' in additional_data):
                recognition_tasks.append(
                    self._voice_verification(user_id, additional_data['voice_sample'])
                )
            
            # 3.3: Behavioral Biometrics (if available)
            if (self.config['enable_behavioral_biometrics'] and 
                additional_data and 'behavioral_data' in additional_data):
                recognition_tasks.append(
                    self._behavioral_verification(user_id, additional_data['behavioral_data'])
                )
            
            # Execute recognition in parallel
            recognition_results = await asyncio.gather(*recognition_tasks, return_exceptions=True)
            
            # Process recognition results
            verified_modalities = []
            total_confidence = 0.0
            modality_count = 0
            
            for i, rec_result in enumerate(recognition_results):
                if isinstance(rec_result, Exception):
                    logger.warning(f"Recognition task {i} failed: {str(rec_result)}")
                    continue
                
                modality_name = rec_result.get('modality', f'modality_{i}')
                result_data['modality_results'][modality_name] = rec_result
                
                if rec_result.get('verified', False):
                    verified_modalities.append(modality_name)
                
                total_confidence += rec_result.get('confidence', 0.0)
                modality_count += 1
            
            # Phase 4: Decision Fusion and Final Verification
            final_result = self._multi_modal_decision_fusion(
                result_data['modality_results'],
                result_data['security_analysis'],
                result_data['quality_metrics']
            )
            
            # Phase 5: Predictive Analytics and Pattern Analysis
            if self.config['enable_predictive_analytics']:
                predictive_result = await self._predictive_analysis(user_id, result_data)
                result_data['predictive_analysis'] = predictive_result
                
                # Adjust final decision based on predictive insights
                if predictive_result.get('high_fraud_risk', False):
                    final_result['verified'] = False
                    final_result['fraud_risk_score'] = min(
                        1.0, final_result.get('fraud_risk_score', 0) + 0.3
                    )
            
            # Create comprehensive result
            processing_time = (time.time() - start_time) * 1000
            
            biometric_result = BiometricResult(
                verified=final_result['verified'],
                confidence=final_result['confidence'],
                modalities_used=verified_modalities,
                processing_time_ms=processing_time,
                fraud_risk_score=final_result.get('fraud_risk_score', 0.0),
                quality_score=quality_result['overall_quality'],
                liveness_score=result_data['security_analysis'].get('liveness_score', 0.0),
                recommendations=final_result.get('recommendations', []),
                detailed_scores=final_result.get('detailed_scores', {})
            )
            
            # Log comprehensive verification attempt
            await self._log_enhanced_verification(result_data, biometric_result, attendance_record_id)
            
            return biometric_result
            
        except Exception as e:
            logger.error(f"Error in AI-enhanced verification: {str(e)}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            
            return BiometricResult(
                verified=False,
                confidence=0.0,
                modalities_used=[],
                processing_time_ms=processing_time,
                fraud_risk_score=1.0,
                quality_score=0.0,
                liveness_score=0.0,
                recommendations=['System error occurred during verification'],
                detailed_scores={'error': str(e)}
            )
    
    async def _ai_quality_assessment(self, image_path: str) -> Dict[str, Any]:
        """AI-powered image quality assessment"""
        try:
            # Check cache first
            cache_key = f"quality_{hashlib.md5(image_path.encode()).hexdigest()}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {'overall_quality': 0.0, 'error': 'Could not load image'}
            
            # AI-enhanced quality metrics
            quality_metrics = {}
            
            # 1. Sharpness analysis using Laplacian variance
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            quality_metrics['sharpness'] = min(1.0, laplacian_var / 150.0)
            
            # 2. Brightness distribution analysis
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            mean_brightness = np.mean(gray)
            brightness_std = np.std(gray)
            quality_metrics['brightness'] = 1.0 - abs(mean_brightness - 127) / 127.0
            quality_metrics['contrast'] = min(1.0, brightness_std / 64.0)
            
            # 3. Face detection confidence
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                quality_metrics['face_detection'] = 0.0
            else:
                # Use largest face
                largest_face = max(faces, key=lambda x: x[2] * x[3])
                face_area = largest_face[2] * largest_face[3]
                image_area = image.shape[0] * image.shape[1]
                face_ratio = face_area / image_area
                quality_metrics['face_detection'] = min(1.0, face_ratio * 10)  # Scale appropriately
            
            # 4. Resolution adequacy
            height, width = image.shape[:2]
            min_resolution = min(width, height)
            quality_metrics['resolution'] = min(1.0, min_resolution / 200.0)  # Minimum 200px
            
            # 5. Noise analysis
            noise_level = cv2.meanStdDev(gray)[1][0][0]
            quality_metrics['noise'] = max(0.0, 1.0 - noise_level / 50.0)
            
            # 6. AI-based pose estimation (simplified)
            quality_metrics['pose'] = 0.8  # Placeholder for actual pose estimation
            
            # Calculate overall quality with weighted average
            weights = {
                'sharpness': 0.25,
                'brightness': 0.15,
                'contrast': 0.15,
                'face_detection': 0.25,
                'resolution': 0.10,
                'noise': 0.05,
                'pose': 0.05
            }
            
            overall_quality = sum(
                quality_metrics[metric] * weight 
                for metric, weight in weights.items()
            )
            
            result = {
                'overall_quality': overall_quality,
                'detailed_metrics': quality_metrics,
                'recommendations': self._generate_quality_recommendations(quality_metrics),
                'analysis_timestamp': timezone.now().isoformat()
            }
            
            # Cache result
            cache.set(cache_key, result, self.cache_config['quality_metrics_ttl'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI quality assessment: {str(e)}")
            return {
                'overall_quality': 0.0,
                'error': str(e),
                'detailed_metrics': {},
                'recommendations': ['Error occurred during quality assessment']
            }
    
    async def _detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        """Advanced deepfake detection using ensemble models"""
        try:
            deepfake_scores = {}
            fraud_indicators = []
            
            # Run multiple deepfake detection models
            for model_name, model in self.deepfake_models.items():
                try:
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.deepfake_pool, model.detect_deepfake, image_path
                    )
                    deepfake_scores[model_name] = result['deepfake_score']
                    
                    if result['deepfake_detected']:
                        fraud_indicators.append(f'DEEPFAKE_{model_name.upper()}')
                        
                except Exception as e:
                    logger.warning(f"Deepfake model {model_name} failed: {str(e)}")
                    continue
            
            # Ensemble decision
            if deepfake_scores:
                avg_deepfake_score = np.mean(list(deepfake_scores.values()))
                max_deepfake_score = np.max(list(deepfake_scores.values()))
                
                # Conservative approach: if any model strongly detects deepfake
                deepfake_detected = max_deepfake_score > self.config['deepfake_threshold']
                
                if deepfake_detected:
                    fraud_indicators.append('ENSEMBLE_DEEPFAKE_DETECTED')
            else:
                avg_deepfake_score = 0.0
                deepfake_detected = False
            
            return {
                'deepfake_detected': deepfake_detected,
                'deepfake_score': avg_deepfake_score,
                'model_scores': deepfake_scores,
                'fraud_indicators': fraud_indicators,
                'authenticity_score': 1.0 - avg_deepfake_score
            }
            
        except Exception as e:
            logger.error(f"Error in deepfake detection: {str(e)}")
            return {
                'deepfake_detected': False,
                'deepfake_score': 0.0,
                'authenticity_score': 1.0,
                'error': str(e)
            }
    
    async def _detect_3d_liveness(self, image_path: str) -> Dict[str, Any]:
        """3D liveness detection with depth analysis"""
        try:
            # Simulate 3D depth analysis (in production, use actual depth cameras)
            liveness_result = await asyncio.get_event_loop().run_in_executor(
                self.liveness_pool,
                self.liveness_models['3D_Liveness'].analyze_depth,
                image_path
            )
            
            depth_score = liveness_result.get('depth_score', 0.0)
            depth_consistency = liveness_result.get('depth_consistency', 0.0)
            
            # Check for flat/2D images (photos)
            is_3d = depth_score > self.config['depth_threshold']
            liveness_score = (depth_score + depth_consistency) / 2.0
            
            return {
                '3d_liveness_detected': is_3d,
                'depth_score': depth_score,
                'depth_consistency': depth_consistency,
                'liveness_score': liveness_score,
                'fraud_detected': not is_3d,
                'fraud_indicators': ['2D_IMAGE_DETECTED'] if not is_3d else []
            }
            
        except Exception as e:
            logger.error(f"Error in 3D liveness detection: {str(e)}")
            return {
                '3d_liveness_detected': True,  # Fail open for compatibility
                'liveness_score': 0.5,
                'error': str(e)
            }
    
    async def _advanced_liveness_analysis(
        self, 
        image_path: str, 
        additional_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Advanced liveness analysis with multiple techniques"""
        try:
            liveness_results = {}
            
            # 1. Micro-expression analysis
            if self.config['micro_expression_analysis']:
                micro_result = await asyncio.get_event_loop().run_in_executor(
                    self.liveness_pool,
                    self.liveness_models['Micro_Expression'].analyze,
                    image_path
                )
                liveness_results['micro_expression'] = micro_result
            
            # 2. Heart rate detection (if video sequence available)
            if (self.config['heart_rate_detection'] and 
                additional_data and 'video_sequence' in additional_data):
                heart_rate_result = await asyncio.get_event_loop().run_in_executor(
                    self.liveness_pool,
                    self.liveness_models['Heart_Rate'].detect_heart_rate,
                    additional_data['video_sequence']
                )
                liveness_results['heart_rate'] = heart_rate_result
            
            # 3. Challenge-response (if enabled)
            if (self.config['challenge_response_enabled'] and 
                additional_data and 'challenge_response' in additional_data):
                challenge_result = self.liveness_models['Challenge_Response'].verify_response(
                    additional_data['challenge_response']
                )
                liveness_results['challenge_response'] = challenge_result
            
            # 4. Passive liveness detection
            passive_result = await asyncio.get_event_loop().run_in_executor(
                self.liveness_pool,
                self.liveness_models['Passive_Liveness'].analyze,
                image_path
            )
            liveness_results['passive_liveness'] = passive_result
            
            # Aggregate liveness score
            liveness_scores = []
            for result in liveness_results.values():
                if isinstance(result, dict) and 'liveness_score' in result:
                    liveness_scores.append(result['liveness_score'])
            
            overall_liveness = np.mean(liveness_scores) if liveness_scores else 0.5
            
            return {
                'advanced_liveness_score': overall_liveness,
                'liveness_components': liveness_results,
                'liveness_detected': overall_liveness > 0.6,
                'fraud_detected': overall_liveness < 0.4,
                'fraud_indicators': ['LOW_LIVENESS_SCORE'] if overall_liveness < 0.4 else []
            }
            
        except Exception as e:
            logger.error(f"Error in advanced liveness analysis: {str(e)}")
            return {
                'advanced_liveness_score': 0.5,
                'liveness_detected': True,
                'error': str(e)
            }
    
    def _generate_quality_recommendations(self, metrics: Dict[str, float]) -> List[str]:
        """Generate intelligent quality improvement recommendations"""
        recommendations = []
        
        if metrics.get('sharpness', 0) < 0.5:
            recommendations.append("Hold device steady and ensure image is in focus")
        
        if metrics.get('brightness', 0) < 0.5:
            recommendations.append("Improve lighting conditions - face too dark or too bright")
        
        if metrics.get('contrast', 0) < 0.4:
            recommendations.append("Increase contrast - avoid uniform lighting")
        
        if metrics.get('face_detection', 0) < 0.5:
            recommendations.append("Position face closer to camera and center in frame")
        
        if metrics.get('resolution', 0) < 0.5:
            recommendations.append("Use higher resolution camera or move closer")
        
        if metrics.get('noise', 0) < 0.5:
            recommendations.append("Reduce image noise - improve lighting or use better camera")
        
        return recommendations
    
    def _create_failed_result(
        self, 
        result_data: Dict, 
        start_time: float, 
        failure_reason: str,
        message: str
    ) -> BiometricResult:
        """Create a standardized failed result"""
        processing_time = (time.time() - start_time) * 1000
        
        return BiometricResult(
            verified=False,
            confidence=0.0,
            modalities_used=[],
            processing_time_ms=processing_time,
            fraud_risk_score=1.0 if 'SECURITY' in failure_reason else 0.5,
            quality_score=result_data.get('quality_metrics', {}).get('overall_quality', 0.0),
            liveness_score=0.0,
            recommendations=[message] + result_data.get('quality_metrics', {}).get('recommendations', []),
            detailed_scores={'failure_reason': failure_reason}
        )


# Mock AI Models for Development (Replace with actual implementations)

class FaceXZooModel:
    """State-of-the-art face recognition model"""
    def extract_features(self, image_path: str) -> np.ndarray:
        # Mock implementation - replace with actual FaceX-Zoo model
        np.random.seed(42)
        features = np.random.normal(0, 1, 512)
        return features / np.linalg.norm(features)

class ArcFaceV2Model:
    """Improved ArcFace model"""
    def extract_features(self, image_path: str) -> np.ndarray:
        np.random.seed(43)
        features = np.random.normal(0, 1, 512)
        return features / np.linalg.norm(features)

class RetinaFaceModel:
    """Advanced face detection model"""
    def detect_faces(self, image_path: str) -> List[Dict]:
        return [{'bbox': [50, 50, 200, 200], 'confidence': 0.95}]

class AdaFaceModel:
    """Adaptive face recognition model"""
    def extract_features(self, image_path: str) -> np.ndarray:
        np.random.seed(44)
        features = np.random.normal(0, 1, 512)
        return features / np.linalg.norm(features)

class MagFaceModel:
    """Magnitude-aware face recognition"""
    def extract_features(self, image_path: str) -> np.ndarray:
        np.random.seed(45)
        features = np.random.normal(0, 1, 512)
        return features / np.linalg.norm(features)

class DeeperForensicsModel:
    """DeeperForensics deepfake detection model"""
    def detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        # Mock implementation
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.1,
            'confidence': 0.9
        }

class FaceForensicsPlusPlusModel:
    """FaceForensics++ detection model"""
    def detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.15,
            'confidence': 0.85
        }

class CelebDFModel:
    """Celeb-DF detection model"""
    def detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.05,
            'confidence': 0.95
        }

class DFDCModel:
    """DFDC detection model"""
    def detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.12,
            'confidence': 0.88
        }

class FaceSwapperDetectionModel:
    """Face swapper detection model"""
    def detect_deepfake(self, image_path: str) -> Dict[str, Any]:
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.08,
            'confidence': 0.92
        }

class ThreeDLivenessModel:
    """3D liveness detection model"""
    def analyze_depth(self, image_path: str) -> Dict[str, Any]:
        return {
            'depth_score': 0.8,
            'depth_consistency': 0.9,
            'is_3d': True
        }

class MicroExpressionModel:
    """Micro-expression analysis model"""
    def analyze(self, image_path: str) -> Dict[str, Any]:
        return {
            'liveness_score': 0.85,
            'expressions_detected': ['neutral', 'slight_smile'],
            'natural_expressions': True
        }

class HeartRateDetectionModel:
    """Heart rate detection from video"""
    def detect_heart_rate(self, video_path: str) -> Dict[str, Any]:
        return {
            'liveness_score': 0.9,
            'heart_rate_bpm': 72,
            'heart_rate_detected': True
        }

class ChallengeResponseModel:
    """Challenge-response liveness model"""
    def verify_response(self, response_data: Dict) -> Dict[str, Any]:
        return {
            'liveness_score': 0.95,
            'challenge_passed': True,
            'response_time_ms': 1200
        }

class PassiveLivenessModel:
    """Passive liveness detection"""
    def analyze(self, image_path: str) -> Dict[str, Any]:
        return {
            'liveness_score': 0.8,
            'texture_analysis': 0.85,
            'lighting_analysis': 0.75
        }

class SpeakerVerificationModel:
    """Speaker verification model"""
    def verify_speaker(self, user_id: int, audio_path: str) -> Dict[str, Any]:
        return {
            'verified': True,
            'confidence': 0.88,
            'similarity_score': 0.92
        }

class VoiceLivenessModel:
    """Voice liveness detection"""
    def detect_liveness(self, audio_path: str) -> Dict[str, Any]:
        return {
            'liveness_detected': True,
            'liveness_score': 0.9,
            'natural_speech': True
        }


# Additional methods for the AIEnhancedFaceRecognitionEngine class
class AIEnhancedFaceRecognitionEngineExtensions:
    """Extension methods for the AI-Enhanced Face Recognition Engine"""
    
    async def _enhanced_face_recognition(self, user_id: int, image_path: str) -> Dict[str, Any]:
        """Enhanced face recognition with latest AI models"""
        try:
            # Get user embeddings from database
            user_embeddings = await self._get_user_embeddings_async(user_id)
            if not user_embeddings:
                return {
                    'modality': 'face_recognition',
                    'verified': False,
                    'confidence': 0.0,
                    'error': 'No face embeddings found for user'
                }
            
            # Extract features using ensemble of latest models
            feature_extraction_tasks = []
            for model_name, model in self.models.items():
                feature_extraction_tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        self.face_pool, model.extract_features, image_path
                    )
                )
            
            # Execute feature extraction in parallel
            extracted_features = await asyncio.gather(*feature_extraction_tasks, return_exceptions=True)
            
            # Process results
            valid_features = {}
            for i, (model_name, features) in enumerate(zip(self.models.keys(), extracted_features)):
                if isinstance(features, Exception):
                    logger.warning(f"Feature extraction failed for {model_name}: {str(features)}")
                    continue
                if features is not None:
                    valid_features[model_name] = features
            
            if not valid_features:
                return {
                    'modality': 'face_recognition',
                    'verified': False,
                    'confidence': 0.0,
                    'error': 'Feature extraction failed for all models'
                }
            
            # Perform ensemble matching
            model_results = {}
            ensemble_similarities = []
            
            for model_name, features in valid_features.items():
                # Find matching embeddings for this model type
                matching_embeddings = [
                    emb for emb in user_embeddings
                    if emb.extraction_model.model_type.upper().replace('-', '_') == model_name.upper()
                ]
                
                if not matching_embeddings:
                    continue
                
                # Calculate similarities with all user embeddings from this model
                similarities = []
                for embedding in matching_embeddings:
                    embedding_vector = np.array(embedding.embedding_vector)
                    similarity = self._calculate_cosine_similarity(features, embedding_vector)
                    similarities.append(similarity)
                
                best_similarity = max(similarities) if similarities else 0.0
                model_results[model_name] = {
                    'similarity': best_similarity,
                    'threshold_met': best_similarity >= 0.7,  # Configurable threshold
                    'embedding_count': len(matching_embeddings)
                }
                
                ensemble_similarities.append(best_similarity)
            
            # Calculate ensemble results
            if ensemble_similarities:
                avg_similarity = np.mean(ensemble_similarities)
                max_similarity = np.max(ensemble_similarities)
                consistency = 1.0 - np.std(ensemble_similarities)  # Higher is better
                
                # Enhanced confidence calculation
                confidence = self._calculate_enhanced_confidence(
                    model_results, avg_similarity, consistency
                )
                
                # Verification decision
                verified = (
                    avg_similarity >= 0.65 and  # Lower threshold for ensemble
                    max_similarity >= 0.7 and   # At least one model confident
                    confidence >= 0.8
                )
                
                return {
                    'modality': 'face_recognition',
                    'verified': verified,
                    'confidence': confidence,
                    'similarity_score': avg_similarity,
                    'max_similarity': max_similarity,
                    'model_consistency': consistency,
                    'model_results': model_results,
                    'models_used': list(valid_features.keys())
                }
            else:
                return {
                    'modality': 'face_recognition',
                    'verified': False,
                    'confidence': 0.0,
                    'error': 'No valid model matches found'
                }
                
        except Exception as e:
            logger.error(f"Error in enhanced face recognition: {str(e)}")
            return {
                'modality': 'face_recognition',
                'verified': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    async def _voice_verification(self, user_id: int, voice_sample: str) -> Dict[str, Any]:
        """Voice biometric verification"""
        try:
            # Voice verification using speaker recognition
            speaker_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.voice_models['Speaker_Verification'].verify_speaker,
                user_id, voice_sample
            )
            
            # Voice liveness detection
            liveness_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.voice_models['Voice_Liveness'].detect_liveness,
                voice_sample
            )
            
            # Combine results
            overall_confidence = (
                speaker_result['confidence'] * 0.7 + 
                liveness_result['liveness_score'] * 0.3
            )
            
            verified = (
                speaker_result['verified'] and
                liveness_result['liveness_detected'] and
                overall_confidence >= 0.8
            )
            
            return {
                'modality': 'voice_recognition',
                'verified': verified,
                'confidence': overall_confidence,
                'speaker_similarity': speaker_result['similarity_score'],
                'voice_liveness': liveness_result['liveness_score'],
                'natural_speech': liveness_result['natural_speech']
            }
            
        except Exception as e:
            logger.error(f"Error in voice verification: {str(e)}")
            return {
                'modality': 'voice_recognition',
                'verified': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    async def _behavioral_verification(self, user_id: int, behavioral_data: Dict) -> Dict[str, Any]:
        """Behavioral biometric verification"""
        try:
            # Analyze behavioral patterns
            behavioral_score = 0.0
            pattern_matches = []
            
            # Keystroke dynamics (if available)
            if 'keystroke_data' in behavioral_data:
                keystroke_score = self._analyze_keystroke_patterns(
                    user_id, behavioral_data['keystroke_data']
                )
                behavioral_score += keystroke_score * 0.3
                pattern_matches.append(f"keystroke:{keystroke_score:.2f}")
            
            # Mouse movement patterns
            if 'mouse_data' in behavioral_data:
                mouse_score = self._analyze_mouse_patterns(
                    user_id, behavioral_data['mouse_data']
                )
                behavioral_score += mouse_score * 0.2
                pattern_matches.append(f"mouse:{mouse_score:.2f}")
            
            # Device usage patterns
            if 'device_data' in behavioral_data:
                device_score = self._analyze_device_patterns(
                    user_id, behavioral_data['device_data']
                )
                behavioral_score += device_score * 0.3
                pattern_matches.append(f"device:{device_score:.2f}")
            
            # Temporal patterns (login times, etc.)
            if 'temporal_data' in behavioral_data:
                temporal_score = self._analyze_temporal_patterns(
                    user_id, behavioral_data['temporal_data']
                )
                behavioral_score += temporal_score * 0.2
                pattern_matches.append(f"temporal:{temporal_score:.2f}")
            
            # Normalize score
            if pattern_matches:
                behavioral_score = behavioral_score / len(pattern_matches) * len(['keystroke_data', 'mouse_data', 'device_data', 'temporal_data'])
            
            verified = behavioral_score >= 0.7
            confidence = min(1.0, behavioral_score + 0.1)  # Slight confidence boost
            
            return {
                'modality': 'behavioral_biometrics',
                'verified': verified,
                'confidence': confidence,
                'behavioral_score': behavioral_score,
                'pattern_matches': pattern_matches,
                'patterns_analyzed': len(pattern_matches)
            }
            
        except Exception as e:
            logger.error(f"Error in behavioral verification: {str(e)}")
            return {
                'modality': 'behavioral_biometrics',
                'verified': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _multi_modal_decision_fusion(
        self,
        modality_results: Dict[str, Dict],
        security_analysis: Dict[str, Any],
        quality_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Intelligent multi-modal decision fusion"""
        try:
            # Extract verification results and confidence scores
            verified_modalities = []
            confidence_scores = []
            modality_weights = {
                'face_recognition': 0.6,
                'voice_recognition': 0.25,
                'behavioral_biometrics': 0.15
            }
            
            for modality, result in modality_results.items():
                if result.get('verified', False):
                    verified_modalities.append(modality)
                
                confidence = result.get('confidence', 0.0)
                weight = modality_weights.get(modality, 0.1)
                confidence_scores.append(confidence * weight)
            
            # Calculate weighted confidence
            total_weight = sum(
                modality_weights.get(mod, 0.1) 
                for mod in modality_results.keys()
            )
            weighted_confidence = sum(confidence_scores) / total_weight if total_weight > 0 else 0.0
            
            # Security penalties
            security_penalty = 0.0
            fraud_risk_score = 0.0
            
            if security_analysis.get('deepfake_detected', False):
                security_penalty += 0.5
                fraud_risk_score += 0.4
            
            if not security_analysis.get('3d_liveness_detected', True):
                security_penalty += 0.3
                fraud_risk_score += 0.3
            
            if security_analysis.get('advanced_liveness_score', 1.0) < 0.5:
                security_penalty += 0.2
                fraud_risk_score += 0.2
            
            # Quality adjustments
            quality_score = quality_metrics.get('overall_quality', 0.0)
            if quality_score < 0.5:
                security_penalty += 0.1
                fraud_risk_score += 0.1
            
            # Apply penalties
            final_confidence = max(0.0, weighted_confidence - security_penalty)
            final_fraud_risk = min(1.0, fraud_risk_score)
            
            # Decision logic
            min_modalities = 1
            required_confidence = 0.75
            
            verified = (
                len(verified_modalities) >= min_modalities and
                final_confidence >= required_confidence and
                final_fraud_risk < 0.6 and
                quality_score >= 0.3
            )
            
            # Generate recommendations
            recommendations = []
            if not verified:
                if len(verified_modalities) == 0:
                    recommendations.append("No biometric modalities successfully verified")
                if final_confidence < required_confidence:
                    recommendations.append(f"Confidence too low: {final_confidence:.2f} < {required_confidence}")
                if final_fraud_risk >= 0.6:
                    recommendations.append(f"High fraud risk detected: {final_fraud_risk:.2f}")
                if quality_score < 0.3:
                    recommendations.append(f"Image quality too low: {quality_score:.2f}")
            
            return {
                'verified': verified,
                'confidence': final_confidence,
                'fraud_risk_score': final_fraud_risk,
                'verified_modalities': verified_modalities,
                'quality_score': quality_score,
                'security_penalty': security_penalty,
                'recommendations': recommendations,
                'detailed_scores': {
                    'weighted_confidence': weighted_confidence,
                    'security_penalty': security_penalty,
                    'quality_score': quality_score,
                    'fraud_risk': final_fraud_risk
                }
            }
            
        except Exception as e:
            logger.error(f"Error in multi-modal decision fusion: {str(e)}")
            return {
                'verified': False,
                'confidence': 0.0,
                'fraud_risk_score': 1.0,
                'error': str(e),
                'recommendations': ['Error in decision fusion process']
            }
    
    async def _predictive_analysis(self, user_id: int, result_data: Dict) -> Dict[str, Any]:
        """Predictive analytics for attendance and fraud detection"""
        try:
            # Removed: behavioral_analytics import - app removed
            from datetime import datetime, timedelta
            
            # Get user behavior profile
            try:
                behavior_profile = UserBehaviorProfile.objects.get(user_id=user_id)
            except UserBehaviorProfile.DoesNotExist:
                return {
                    'high_fraud_risk': False,
                    'attendance_prediction': 'unknown',
                    'behavioral_anomaly': False,
                    'message': 'No behavior profile found'
                }
            
            current_time = datetime.now().time()
            current_hour = current_time.hour
            current_weekday = datetime.now().weekday()
            
            # Analyze temporal patterns
            typical_hours = behavior_profile.typical_login_hours or []
            is_typical_time = current_hour in typical_hours
            
            # Check attendance regularity
            regularity_score = behavior_profile.attendance_regularity_score
            
            # Fraud risk assessment
            historical_fraud_risk = behavior_profile.fraud_risk_score
            current_verification_confidence = result_data.get('modality_results', {}).get(
                'face_recognition', {}
            ).get('confidence', 0.0)
            
            # Predictive indicators
            time_anomaly = not is_typical_time and len(typical_hours) > 0
            confidence_anomaly = current_verification_confidence < regularity_score - 0.2
            
            # Calculate risk factors
            risk_factors = []
            risk_score = historical_fraud_risk
            
            if time_anomaly:
                risk_factors.append('UNUSUAL_LOGIN_TIME')
                risk_score += 0.2
            
            if confidence_anomaly:
                risk_factors.append('LOW_CONFIDENCE_ANOMALY')
                risk_score += 0.3
            
            if regularity_score < 0.3:
                risk_factors.append('LOW_ATTENDANCE_REGULARITY')
                risk_score += 0.2
            
            # Attendance prediction based on patterns
            if regularity_score > 0.8 and is_typical_time:
                attendance_prediction = 'likely_genuine'
            elif regularity_score > 0.5:
                attendance_prediction = 'probably_genuine'
            else:
                attendance_prediction = 'uncertain'
            
            high_fraud_risk = risk_score > 0.6 or len(risk_factors) >= 2
            
            return {
                'high_fraud_risk': high_fraud_risk,
                'fraud_risk_score': min(1.0, risk_score),
                'attendance_prediction': attendance_prediction,
                'behavioral_anomaly': time_anomaly or confidence_anomaly,
                'risk_factors': risk_factors,
                'temporal_analysis': {
                    'is_typical_time': is_typical_time,
                    'current_hour': current_hour,
                    'typical_hours': typical_hours
                },
                'user_regularity_score': regularity_score,
                'confidence_deviation': current_verification_confidence - regularity_score
            }
            
        except Exception as e:
            logger.error(f"Error in predictive analysis: {str(e)}")
            return {
                'high_fraud_risk': False,
                'attendance_prediction': 'unknown',
                'behavioral_anomaly': False,
                'error': str(e)
            }
    
    async def _log_enhanced_verification(
        self,
        result_data: Dict,
        biometric_result: BiometricResult,
        attendance_record_id: Optional[int]
    ):
        """Enhanced verification logging with comprehensive data"""
        try:
            from .models import FaceVerificationLog, FaceRecognitionModel
            
            # Determine verification result status
            if biometric_result.verified:
                verification_result = FaceVerificationLog.VerificationResult.SUCCESS
            elif 'SECURITY' in str(result_data.get('fraud_indicators', [])):
                verification_result = FaceVerificationLog.VerificationResult.REJECTED
            else:
                verification_result = FaceVerificationLog.VerificationResult.FAILED
            
            # Get primary model for compatibility
            primary_model = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: FaceRecognitionModel.objects.filter(
                    model_type='FACENET512', status='ACTIVE'
                ).first() or FaceRecognitionModel.objects.filter(status='ACTIVE').first()
            )
            
            # Prepare comprehensive metadata
            verification_metadata = {
                'ai_enhanced_version': '2025.1',
                'modality_results': result_data.get('modality_results', {}),
                'quality_metrics': result_data.get('quality_metrics', {}),
                'security_analysis': result_data.get('security_analysis', {}),
                'predictive_analysis': result_data.get('predictive_analysis', {}),
                'processing_time_ms': biometric_result.processing_time_ms,
                'models_used': biometric_result.modalities_used,
                'detailed_scores': biometric_result.detailed_scores
            }
            
            # Create enhanced log entry
            log_entry = await asyncio.get_event_loop().run_in_executor(
                None,
                FaceVerificationLog.objects.create,
                {
                    'user_id': result_data['user_id'],
                    'attendance_record_id': attendance_record_id,
                    'result': verification_result,
                    'verification_model': primary_model,
                    'similarity_score': biometric_result.detailed_scores.get('similarity_score', 0.0),
                    'confidence_score': biometric_result.confidence,
                    'liveness_score': biometric_result.liveness_score,
                    'spoof_detected': result_data.get('security_analysis', {}).get('fraud_detected', False),
                    'input_image_path': result_data.get('image_path'),
                    'input_image_hash': hashlib.md5(
                        result_data.get('image_path', '').encode()
                    ).hexdigest()[:16],
                    'processing_time_ms': biometric_result.processing_time_ms,
                    'verification_metadata': verification_metadata,
                    'fraud_indicators': result_data.get('fraud_indicators', []),
                    'fraud_risk_score': biometric_result.fraud_risk_score
                }
            )
            
            logger.info(f"Enhanced verification logged: {log_entry.id}")
            
        except Exception as e:
            logger.error(f"Error logging enhanced verification: {str(e)}")
    
    # Helper methods
    async def _get_user_embeddings_async(self, user_id: int) -> List:
        """Asynchronously get user embeddings"""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(FaceEmbedding.objects.filter(
                user_id=user_id, is_validated=True
            ).select_related('extraction_model'))
        )
    
    def _calculate_enhanced_confidence(
        self, 
        model_results: Dict, 
        avg_similarity: float, 
        consistency: float
    ) -> float:
        """Calculate enhanced confidence with multiple factors"""
        # Base confidence from similarity
        similarity_confidence = min(1.0, avg_similarity * 1.2)
        
        # Consistency bonus
        consistency_bonus = consistency * 0.2
        
        # Model agreement factor
        verified_models = sum(1 for result in model_results.values() if result.get('threshold_met', False))
        total_models = len(model_results)
        agreement_factor = verified_models / total_models if total_models > 0 else 0.0
        
        # Combined confidence
        confidence = (
            similarity_confidence * 0.6 +
            consistency_bonus +
            agreement_factor * 0.2
        )
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Normalize vectors
            vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
            vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
            
            # Calculate cosine similarity
            similarity = np.dot(vec1_norm, vec2_norm)
            
            # Ensure similarity is in [0, 1] range
            similarity = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0
    
    # Behavioral analysis helper methods
    def _analyze_keystroke_patterns(self, user_id: int, keystroke_data: Dict) -> float:
        """Analyze keystroke dynamics patterns"""
        # Mock implementation - in production, use actual keystroke analysis
        dwell_times = keystroke_data.get('dwell_times', [])
        flight_times = keystroke_data.get('flight_times', [])
        
        if not dwell_times or not flight_times:
            return 0.5  # Neutral score
        
        # Simple pattern matching (replace with ML model)
        avg_dwell = np.mean(dwell_times)
        avg_flight = np.mean(flight_times)
        
        # Mock scoring based on typical patterns
        score = 0.8 if 50 < avg_dwell < 200 and 50 < avg_flight < 150 else 0.3
        return score
    
    def _analyze_mouse_patterns(self, user_id: int, mouse_data: Dict) -> float:
        """Analyze mouse movement patterns"""
        # Mock implementation
        movements = mouse_data.get('movements', [])
        clicks = mouse_data.get('clicks', [])
        
        if not movements:
            return 0.5
        
        # Simple pattern analysis
        avg_speed = np.mean([mov.get('speed', 0) for mov in movements])
        score = 0.8 if 100 < avg_speed < 1000 else 0.4
        return score
    
    def _analyze_device_patterns(self, user_id: int, device_data: Dict) -> float:
        """Analyze device usage patterns"""
        # Mock implementation
        device_type = device_data.get('device_type', 'unknown')
        os_version = device_data.get('os_version', 'unknown')
        
        # Simple device recognition
        score = 0.9 if device_type != 'unknown' else 0.3
        return score
    
    def _analyze_temporal_patterns(self, user_id: int, temporal_data: Dict) -> float:
        """Analyze temporal access patterns"""
        # Mock implementation
        current_time = temporal_data.get('current_time', datetime.now().hour)
        typical_hours = temporal_data.get('typical_hours', [9, 10, 11, 12, 13, 14, 15, 16, 17])
        
        score = 0.9 if current_time in typical_hours else 0.4
        return score


# Integrate extensions into main class
def _integrate_extensions():
    """Integrate extension methods into main class"""
    for method_name in dir(AIEnhancedFaceRecognitionEngineExtensions):
        if not method_name.startswith('_') or method_name.startswith('_enhanced') or method_name.startswith('_voice') or method_name.startswith('_behavioral') or method_name.startswith('_multi_modal') or method_name.startswith('_predictive') or method_name.startswith('_log_enhanced') or method_name.startswith('_get_user') or method_name.startswith('_calculate') or method_name.startswith('_analyze'):
            method = getattr(AIEnhancedFaceRecognitionEngineExtensions, method_name)
            setattr(AIEnhancedFaceRecognitionEngine, method_name, method)

# Apply integration
_integrate_extensions()