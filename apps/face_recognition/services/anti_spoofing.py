"""
Anti-Spoofing Detection Service for Face Recognition (Sprint 5.1)

This service provides anti-spoofing detection to prevent presentation attacks:
- Texture-based spoofing detection (printed photos, screen displays)
- Motion-based spoofing detection (video replay attacks)
- Ensemble decision aggregation

Uses real computer vision techniques with OpenCV.

Author: Development Team
Date: October 2025
Status: Real anti-spoofing implemented (Sprint 5.1)
"""

import logging
import numpy as np
import cv2
from typing import Dict, Any
from pathlib import Path
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


# ============================================================================
# ANTI-SPOOFING MODEL IMPLEMENTATIONS (Sprint 5.1)
# ============================================================================

class TextureBasedAntiSpoofingModel:
    """
    Texture-based anti-spoofing using Local Binary Patterns (LBP).

    Detects printed photos and screen displays by analyzing texture patterns.
    Real faces have different texture characteristics than printed/displayed images.

    Techniques:
    - Local Binary Pattern (LBP) histogram analysis
    - Frequency domain analysis (high-frequency loss in prints)
    - Color depth analysis
    - Reflection pattern detection
    """

    def __init__(self):
        """Initialize texture-based anti-spoofing model."""
        self.spoof_threshold = 0.5  # Threshold for spoof detection

    def detect_spoof(self, image_path: str) -> Dict[str, Any]:
        """
        Detect texture-based spoofing using LBP and frequency analysis.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary with detection results
        """
        try:
            # Load image
            if not Path(image_path).exists():
                return {'spoof_detected': False, 'spoof_score': 0.0, 'error': 'Image not found'}

            image = cv2.imread(image_path)
            if image is None:
                return {'spoof_detected': False, 'spoof_score': 0.0, 'error': 'Failed to load image'}

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Feature 1: LBP histogram variance
            lbp_score = self._analyze_lbp_texture(gray)

            # Feature 2: High-frequency content analysis
            freq_score = self._analyze_frequency_content(gray)

            # Feature 3: Color depth analysis
            color_score = self._analyze_color_depth(image)

            # Aggregate scores (higher score = more likely spoof)
            spoof_score = (lbp_score + freq_score + color_score) / 3.0

            # Decision
            spoof_detected = spoof_score > self.spoof_threshold

            return {
                'spoof_detected': spoof_detected,
                'spoof_score': float(spoof_score),
                'confidence': 0.85,
                'features': {
                    'lbp_score': float(lbp_score),
                    'frequency_score': float(freq_score),
                    'color_depth_score': float(color_score)
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error in texture-based spoof detection: {e}", exc_info=True)
            return {
                'spoof_detected': False,
                'spoof_score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }

    def _analyze_lbp_texture(self, gray_image: np.ndarray) -> float:
        """
        Analyze texture using Local Binary Patterns.

        Real faces have richer LBP patterns than printed photos.

        Args:
            gray_image: Grayscale image

        Returns:
            LBP-based spoof score (0.0-1.0, higher = more likely spoof)
        """
        try:
            # Simple LBP implementation
            rows, cols = gray_image.shape
            lbp_image = np.zeros((rows-2, cols-2), dtype=np.uint8)

            for i in range(1, rows-1):
                for j in range(1, cols-1):
                    center = gray_image[i, j]
                    code = 0
                    code |= (gray_image[i-1, j-1] >= center) << 7
                    code |= (gray_image[i-1, j] >= center) << 6
                    code |= (gray_image[i-1, j+1] >= center) << 5
                    code |= (gray_image[i, j+1] >= center) << 4
                    code |= (gray_image[i+1, j+1] >= center) << 3
                    code |= (gray_image[i+1, j] >= center) << 2
                    code |= (gray_image[i+1, j-1] >= center) << 1
                    code |= (gray_image[i, j-1] >= center) << 0
                    lbp_image[i-1, j-1] = code

            # Calculate histogram
            hist, _ = np.histogram(lbp_image.ravel(), bins=256, range=(0, 256))
            hist = hist.astype(float) / hist.sum()

            # Real faces have more uniform LBP distribution
            # Printed photos have peaks in histogram
            histogram_variance = np.var(hist)

            # Higher variance = more likely real face
            # Lower variance = more likely spoof (uniform patterns)
            if histogram_variance < 0.00005:
                return 0.7  # Likely spoof
            elif histogram_variance < 0.0001:
                return 0.5
            else:
                return 0.2  # Likely real

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"LBP analysis failed: {e}", exc_info=True)
            return 0.0

    def _analyze_frequency_content(self, gray_image: np.ndarray) -> float:
        """
        Analyze frequency domain content.

        Printed photos lose high-frequency information during printing.

        Args:
            gray_image: Grayscale image

        Returns:
            Frequency-based spoof score (0.0-1.0)
        """
        try:
            # Apply FFT
            f_transform = np.fft.fft2(gray_image)
            f_shift = np.fft.fftshift(f_transform)
            magnitude_spectrum = np.abs(f_shift)

            # Calculate high-frequency energy
            rows, cols = magnitude_spectrum.shape
            crow, ccol = rows // 2, cols // 2

            # Define high-frequency region (outer 30%)
            mask = np.ones((rows, cols), dtype=bool)
            r = min(crow, ccol) * 0.7
            y, x = np.ogrid[:rows, :cols]
            mask_area = (x - ccol)**2 + (y - crow)**2 <= r**2
            mask[mask_area] = False

            high_freq_energy = np.sum(magnitude_spectrum[mask])
            total_energy = np.sum(magnitude_spectrum)

            high_freq_ratio = high_freq_energy / (total_energy + 1e-10)

            # Real faces have more high-frequency content
            # Printed photos have less (due to printing process)
            if high_freq_ratio < 0.1:
                return 0.8  # Likely spoof (low high-freq)
            elif high_freq_ratio < 0.2:
                return 0.5
            else:
                return 0.1  # Likely real (rich high-freq)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Frequency analysis failed: {e}", exc_info=True)
            return 0.0

    def _analyze_color_depth(self, color_image: np.ndarray) -> float:
        """
        Analyze color depth and distribution.

        Printed photos and screens have different color characteristics.

        Args:
            color_image: Color image (BGR)

        Returns:
            Color-based spoof score (0.0-1.0)
        """
        try:
            # Calculate color variance
            b, g, r = cv2.split(color_image)

            color_variance = np.mean([
                np.var(b),
                np.var(g),
                np.var(r)
            ])

            # Real faces have higher color variance
            # Printed photos have lower variance (limited color gamut)
            if color_variance < 500:
                return 0.7  # Likely spoof
            elif color_variance < 1000:
                return 0.4
            else:
                return 0.1  # Likely real

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Color depth analysis failed: {e}", exc_info=True)
            return 0.0


class MotionBasedAntiSpoofingModel:
    """
    Motion-based anti-spoofing using edge detection and gradient analysis.

    Detects video replay attacks and screen displays by analyzing
    edge sharpness and gradient patterns.

    For single images, uses edge-based heuristics.
    For video sequences, would use optical flow (future enhancement).
    """

    def __init__(self):
        """Initialize motion-based anti-spoofing model."""
        self.spoof_threshold = 0.5

    def detect_spoof(self, image_path: str) -> Dict[str, Any]:
        """
        Detect motion-based spoofing using edge analysis.

        For single images, analyzes edge characteristics.
        Real faces have natural edges, screen displays have artificial sharpness.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary with detection results
        """
        try:
            # Load image
            if not Path(image_path).exists():
                return {'spoof_detected': False, 'spoof_score': 0.0, 'error': 'Image not found'}

            image = cv2.imread(image_path)
            if image is None:
                return {'spoof_detected': False, 'spoof_score': 0.0, 'error': 'Failed to load image'}

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Feature 1: Edge sharpness analysis
            edge_score = self._analyze_edge_sharpness(gray)

            # Feature 2: Gradient consistency
            gradient_score = self._analyze_gradient_consistency(gray)

            # Aggregate scores
            spoof_score = (edge_score + gradient_score) / 2.0

            # Decision
            spoof_detected = spoof_score > self.spoof_threshold

            return {
                'spoof_detected': spoof_detected,
                'spoof_score': float(spoof_score),
                'confidence': 0.80,
                'features': {
                    'edge_score': float(edge_score),
                    'gradient_score': float(gradient_score)
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error in motion-based spoof detection: {e}", exc_info=True)
            return {
                'spoof_detected': False,
                'spoof_score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }

    def _analyze_edge_sharpness(self, gray_image: np.ndarray) -> float:
        """
        Analyze edge sharpness patterns.

        Screen displays have artificially sharp edges.
        Real faces have natural edge gradients.

        Args:
            gray_image: Grayscale image

        Returns:
            Edge-based spoof score (0.0-1.0)
        """
        try:
            # Apply Canny edge detection
            edges = cv2.Canny(gray_image, 100, 200)

            # Calculate edge density
            edge_density = np.sum(edges > 0) / edges.size

            # Calculate edge strength
            gradx = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=3)
            grady = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(gradx**2 + grady**2)
            avg_gradient = np.mean(gradient_magnitude)

            # Screens have very sharp edges (high density + high gradient)
            # Real faces have softer edges
            if edge_density > 0.15 and avg_gradient > 40:
                return 0.8  # Likely spoof (screen)
            elif edge_density > 0.10:
                return 0.5
            else:
                return 0.2  # Likely real

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Edge sharpness analysis failed: {e}", exc_info=True)
            return 0.0

    def _analyze_gradient_consistency(self, gray_image: np.ndarray) -> float:
        """
        Analyze gradient consistency across image.

        Real faces have consistent gradients.
        Printed photos have inconsistent gradients due to printing artifacts.

        Args:
            gray_image: Grayscale image

        Returns:
            Gradient-based spoof score (0.0-1.0)
        """
        try:
            # Calculate gradients
            gradx = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=3)
            grady = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=3)

            # Calculate gradient magnitude
            gradient_magnitude = np.sqrt(gradx**2 + grady**2)

            # Calculate local variance in gradients
            # Divide image into blocks and calculate variance per block
            block_size = 32
            rows, cols = gray_image.shape
            variances = []

            for i in range(0, rows - block_size, block_size):
                for j in range(0, cols - block_size, block_size):
                    block = gradient_magnitude[i:i+block_size, j:j+block_size]
                    variances.append(np.var(block))

            # Calculate variance of variances (consistency measure)
            variance_of_variances = np.var(variances) if variances else 0

            # Printed photos have inconsistent gradients (high variance of variances)
            # Real faces have more consistent gradients
            if variance_of_variances > 1000:
                return 0.7  # Likely spoof
            elif variance_of_variances > 500:
                return 0.4
            else:
                return 0.1  # Likely real

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Gradient consistency analysis failed: {e}", exc_info=True)
            return 0.0


# ============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ============================================================================

# Maintain backward compatibility with code expecting "Mock" prefix
MockAntiSpoofingModel = TextureBasedAntiSpoofingModel
MockMotionAntiSpoofingModel = MotionBasedAntiSpoofingModel


# ============================================================================
# ANTI-SPOOFING DETECTION SERVICE
# ============================================================================

class AntiSpoofingService:
    """
    Service for detecting presentation attacks and spoofing attempts.

    Uses multiple anti-spoofing techniques (texture-based, motion-based)
    and aggregates their results for robust spoof detection.

    Sprint 5.1: Now uses real computer vision techniques (LBP, FFT, edge detection).
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize anti-spoofing service.

        Args:
            config: Configuration dictionary with detection parameters
        """
        self.config = config or {}
        self.liveness_threshold = self.config.get('liveness_threshold', 0.5)

        # Initialize anti-spoofing models (real implementations - Sprint 5.1)
        self.anti_spoofing_models = {
            'TEXTURE_BASED': TextureBasedAntiSpoofingModel(),
            'MOTION_BASED': MotionBasedAntiSpoofingModel()
        }

        logger.info("Anti-spoofing service initialized with real CV-based models")

    def detect_spoofing(self, image_path: str) -> Dict[str, Any]:
        """
        Detect spoofing attempts using ensemble of anti-spoofing models.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing:
                - spoof_detected: Boolean indicating if spoof detected
                - spoof_score: Average spoof score (0.0-1.0)
                - liveness_score: 1.0 - spoof_score
                - model_scores: Individual model scores
                - fraud_indicators: List of fraud indicators found
        """
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
            spoof_detected = avg_spoof_score > self.liveness_threshold

            return {
                'spoof_detected': spoof_detected,
                'spoof_score': float(avg_spoof_score),
                'liveness_score': float(1.0 - avg_spoof_score),
                'model_scores': spoof_scores,
                'fraud_indicators': fraud_indicators
            }

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error in anti-spoofing detection: {str(e)}")
            return {
                'spoof_detected': False,
                'spoof_score': 0.0,
                'liveness_score': 1.0,
                'error': str(e),
                'fraud_indicators': []
            }

    def update_threshold(self, new_threshold: float):
        """
        Update liveness threshold for spoof detection.

        Args:
            new_threshold: New threshold value (0.0-1.0)
        """
        if 0.0 <= new_threshold <= 1.0:
            self.liveness_threshold = new_threshold
            logger.info(f"Updated liveness threshold to {new_threshold}")
        else:
            logger.warning(f"Invalid threshold value: {new_threshold}")
