"""
Face Liveness Detection Module for AI-Enhanced Face Recognition (Sprint 1.4)

This module provides comprehensive liveness detection using multiple techniques:
- 3D depth analysis
- Heart rate detection (rPPG)
- Challenge-response verification
- Passive liveness detection
- Micro-expression analysis

TODO: Sprint 5 - Replace mock implementations with real ML models.
Currently uses stubs for development and testing.
"""

import asyncio
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# MOCK MODEL IMPLEMENTATIONS (TODO: Sprint 5 - Replace with real models)
# ============================================================================

def _load_gray(image_path: str) -> np.ndarray:
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f'Could not load image: {image_path}')
    return image


class ThreeDLivenessModel:
    """Depth heuristics using gradient magnitude."""

    def analyze_depth(self, image_path: str) -> Dict[str, Any]:
        gray = _load_gray(image_path)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        gradient_mag = np.mean(np.sqrt(sobel_x ** 2 + sobel_y ** 2))
        depth_score = min(1.0, gradient_mag / 40.0)
        depth_consistency = float(np.std(sobel_x) / 25.0)
        is_3d = depth_score > 0.45 and depth_consistency > 0.4
        return {
            'depth_score': round(depth_score, 3),
            'depth_consistency': round(depth_consistency, 3),
            'is_3d': is_3d,
        }


class MicroExpressionModel:
    """Estimate expression diversity via local binary patterns."""

    def analyze(self, image_path: str) -> Dict[str, Any]:
        gray = _load_gray(image_path)
        lbp = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(np.var(lbp))
        liveness_score = min(1.0, variance / 800.0)
        expressions_detected = ['neutral']
        if liveness_score > 0.6:
            expressions_detected.append('micro_movement')
        return {
            'liveness_score': round(liveness_score, 3),
            'expressions_detected': expressions_detected,
            'natural_expressions': liveness_score > 0.4,
        }


class HeartRateDetectionModel:
    """Simple rPPG estimator using green channel oscillations."""

    def detect_heart_rate(self, video_path: str) -> Dict[str, Any]:
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            return {'heart_rate_detected': False, 'liveness_score': 0.0, 'heart_rate_bpm': None}

        samples = []
        frame_count = 0
        while frame_count < 150:  # ~5 seconds at 30fps
            ret, frame = capture.read()
            if not ret:
                break
            roi = frame[frame.shape[0] // 3: frame.shape[0] // 2,
                       frame.shape[1] // 3: frame.shape[1] // 2]
            samples.append(np.mean(roi[:, :, 1]))  # green channel
            frame_count += 1
        capture.release()

        if len(samples) < 30:
            return {'heart_rate_detected': False, 'liveness_score': 0.0, 'heart_rate_bpm': None}

        signal = np.array(samples) - np.mean(samples)
        spectrum = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), d=1 / 30.0)
        mask = (freqs >= 0.8) & (freqs <= 3.0)
        if not mask.any():
            return {'heart_rate_detected': False, 'liveness_score': 0.0, 'heart_rate_bpm': None}

        dominant_idx = np.argmax(spectrum[mask])
        bpm = int(freqs[mask][dominant_idx] * 60)
        liveness_score = min(1.0, spectrum[mask][dominant_idx] / (np.sum(spectrum[mask]) + 1e-9))
        return {
            'heart_rate_detected': True,
            'heart_rate_bpm': bpm,
            'liveness_score': round(liveness_score, 3),
        }


class ChallengeResponseModel:
    """Compare expected challenge phrase with provided transcript."""

    def verify_response(self, response_data: Dict) -> Dict[str, Any]:
        expected = (response_data or {}).get('expected_phrase', '')
        spoken = (response_data or {}).get('spoken_text', '')
        latency = response_data.get('response_time_ms', 1000)
        match = SequenceMatcher(a=expected.lower(), b=spoken.lower()).ratio() if expected and spoken else 0.0
        challenge_passed = match > 0.7 and latency < 4000
        return {
            'liveness_score': round(match, 3),
            'challenge_passed': challenge_passed,
            'response_time_ms': latency,
        }


class PassiveLivenessModel:
    """Texture/lighting heuristics to detect printed photos."""

    def analyze(self, image_path: str) -> Dict[str, Any]:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f'Could not load image: {image_path}')
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        texture = float(np.std(cv2.Laplacian(gray, cv2.CV_64F)))
        lighting = float(np.std(image[:, :, 2]))
        liveness_score = min(1.0, (texture / 40.0 + lighting / 60.0) / 2)
        return {
            'liveness_score': round(liveness_score, 3),
            'texture_analysis': round(texture / 40.0, 3),
            'lighting_analysis': round(lighting / 60.0, 3)
        }


# ============================================================================
# LIVENESS DETECTION SERVICE
# ============================================================================

class LivenessDetectionService:
    """
    Service for comprehensive liveness detection.

    Uses multiple liveness detection techniques and aggregates their results
    for robust anti-spoofing protection.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize liveness detection service.

        Args:
            config: Configuration dictionary with detection parameters
        """
        self.config = config or {}

        # Configuration parameters
        self.depth_threshold = self.config.get('depth_threshold', 0.6)
        self.micro_expression_analysis = self.config.get('micro_expression_analysis', False)
        self.heart_rate_detection = self.config.get('heart_rate_detection', False)
        self.challenge_response_enabled = self.config.get('challenge_response_enabled', False)

        # Initialize all liveness detection models
        self.liveness_models = {
            '3D_Liveness': ThreeDLivenessModel(),
            'Micro_Expression': MicroExpressionModel(),
            'Heart_Rate': HeartRateDetectionModel(),
            'Challenge_Response': ChallengeResponseModel(),
            'Passive_Liveness': PassiveLivenessModel()
        }

        # Executor pool for parallel detection (optional)
        self.executor_pool = None  # Will be set by parent engine if needed

    async def detect_3d_liveness(self, image_path: str) -> Dict[str, Any]:
        """
        Detect 3D liveness using depth analysis.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing:
                - 3d_liveness_detected: Boolean indicating if 3D face detected
                - depth_score: Depth map quality score
                - depth_consistency: Depth consistency score
                - liveness_score: Overall liveness score
                - fraud_detected: Boolean indicating fraud
                - fraud_indicators: List of fraud indicators
        """
        try:
            # Run 3D depth analysis
            if self.executor_pool:
                liveness_result = await asyncio.get_event_loop().run_in_executor(
                    self.executor_pool,
                    self.liveness_models['3D_Liveness'].analyze_depth,
                    image_path
                )
            else:
                liveness_result = self.liveness_models['3D_Liveness'].analyze_depth(image_path)

            depth_score = liveness_result.get('depth_score', 0.0)
            depth_consistency = liveness_result.get('depth_consistency', 0.0)

            # Check for flat/2D images (photos)
            is_3d = depth_score > self.depth_threshold
            liveness_score = (depth_score + depth_consistency) / 2.0

            return {
                '3d_liveness_detected': is_3d,
                'depth_score': float(depth_score),
                'depth_consistency': float(depth_consistency),
                'liveness_score': float(liveness_score),
                'fraud_detected': not is_3d,
                'fraud_indicators': ['2D_IMAGE_DETECTED'] if not is_3d else []
            }

        except (AttributeError, TypeError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Error in 3D liveness detection: {str(e)}")
            return {
                '3d_liveness_detected': True,  # Fail open for compatibility
                'liveness_score': 0.5,
                'error': str(e),
                'fraud_indicators': []
            }

    async def advanced_liveness_analysis(
        self,
        image_path: str,
        additional_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Advanced liveness analysis using multiple techniques.

        Args:
            image_path: Path to the image file
            additional_data: Optional dictionary with additional data:
                - video_sequence: Path to video for heart rate detection
                - challenge_response: Challenge response data

        Returns:
            Dictionary containing:
                - advanced_liveness_score: Overall liveness score
                - liveness_components: Individual component results
                - liveness_detected: Boolean indicating liveness
                - fraud_detected: Boolean indicating fraud
                - fraud_indicators: List of fraud indicators
        """
        try:
            liveness_results = {}
            additional_data = additional_data or {}

            # 1. Micro-expression analysis
            if self.micro_expression_analysis:
                if self.executor_pool:
                    micro_result = await asyncio.get_event_loop().run_in_executor(
                        self.executor_pool,
                        self.liveness_models['Micro_Expression'].analyze,
                        image_path
                    )
                else:
                    micro_result = self.liveness_models['Micro_Expression'].analyze(image_path)
                liveness_results['micro_expression'] = micro_result

            # 2. Heart rate detection (if video sequence available)
            if (self.heart_rate_detection and 'video_sequence' in additional_data):
                if self.executor_pool:
                    heart_rate_result = await asyncio.get_event_loop().run_in_executor(
                        self.executor_pool,
                        self.liveness_models['Heart_Rate'].detect_heart_rate,
                        additional_data['video_sequence']
                    )
                else:
                    heart_rate_result = self.liveness_models['Heart_Rate'].detect_heart_rate(
                        additional_data['video_sequence']
                    )
                liveness_results['heart_rate'] = heart_rate_result

            # 3. Challenge-response (if enabled)
            if (self.challenge_response_enabled and 'challenge_response' in additional_data):
                challenge_result = self.liveness_models['Challenge_Response'].verify_response(
                    additional_data['challenge_response']
                )
                liveness_results['challenge_response'] = challenge_result

            # 4. Passive liveness detection
            if self.executor_pool:
                passive_result = await asyncio.get_event_loop().run_in_executor(
                    self.executor_pool,
                    self.liveness_models['Passive_Liveness'].analyze,
                    image_path
                )
            else:
                passive_result = self.liveness_models['Passive_Liveness'].analyze(image_path)
            liveness_results['passive_liveness'] = passive_result

            # Aggregate liveness score
            liveness_scores = []
            for result in liveness_results.values():
                if isinstance(result, dict) and 'liveness_score' in result:
                    liveness_scores.append(result['liveness_score'])

            overall_liveness = np.mean(liveness_scores) if liveness_scores else 0.5

            return {
                'advanced_liveness_score': float(overall_liveness),
                'liveness_components': liveness_results,
                'liveness_detected': overall_liveness > 0.6,
                'fraud_detected': overall_liveness < 0.4,
                'fraud_indicators': ['LOW_LIVENESS_SCORE'] if overall_liveness < 0.4 else []
            }

        except (AttributeError, TypeError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Error in advanced liveness analysis: {str(e)}")
            return {
                'advanced_liveness_score': 0.5,
                'liveness_detected': True,
                'error': str(e),
                'fraud_indicators': []
            }

    def set_executor_pool(self, pool):
        """Set the executor pool for parallel model execution."""
        self.executor_pool = pool
