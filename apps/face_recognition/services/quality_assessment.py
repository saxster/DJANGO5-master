"""
Image Quality Assessment Service for Face Recognition (Sprint 1.5)

This service provides comprehensive image quality assessment for face recognition:
- Sharpness analysis using Laplacian variance
- Brightness and contrast assessment
- Face size and position evaluation
- Face pose quality estimation
- Eye visibility detection
- Quality metrics caching for performance

Author: Development Team
Date: October 2025
"""

import logging
import os
import time
import hashlib
import numpy as np
import cv2
from typing import Dict, List, Any, Optional, Tuple
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.face_recognition.models import FaceQualityMetrics

logger = logging.getLogger(__name__)


class ImageQualityAssessmentService:
    """
    Service for comprehensive image quality assessment.

    Evaluates multiple quality dimensions to ensure images are suitable
    for accurate face recognition.
    """

    def __init__(self):
        """Initialize image quality assessment service."""
        # Quality thresholds
        self.sharpness_threshold = 0.5
        self.brightness_threshold = 0.5
        self.contrast_threshold = 0.4
        self.face_size_threshold = 0.7
        self.pose_threshold = 0.6
        self.eye_visibility_threshold = 0.5
        self.detection_confidence_threshold = 0.7

    def assess_image_quality(self, image_path: str) -> Dict[str, Any]:
        """
        Assess image quality for face recognition.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing:
                - overall_quality: Overall quality score (0.0-1.0)
                - sharpness_score: Sharpness score
                - brightness_score: Brightness score
                - contrast_score: Contrast score
                - face_size_score: Face size score
                - quality_issues: List of quality issues found
                - cached: Whether result was cached
        """
        try:
            # Calculate image hash
            image_hash = self.calculate_image_hash(image_path)

            # Check if already analyzed (cache lookup)
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
            face_roi, face_confidence = self.detect_face_roi(image)

            if face_roi is not None:
                # Extract face region for quality assessment
                x, y, w, h = face_roi
                face_gray = gray[y:y+h, x:x+w]
                face_color = image[y:y+h, x:x+w]

                # Face-specific quality metrics
                sharpness_score = self.calculate_roi_sharpness(face_gray)
                brightness_score = self.calculate_roi_brightness(face_gray)
                contrast_score = self.calculate_roi_contrast(face_gray)
                face_size_score = self.calculate_face_size_score(w, h, width, height)
                pose_score = self.estimate_face_pose_quality(face_color)
                eye_visibility = self.check_eye_visibility(face_color, face_roi)

                overall_quality = np.mean([
                    sharpness_score, brightness_score, contrast_score,
                    face_size_score, pose_score, eye_visibility
                ])
            else:
                # Fallback to whole-image assessment if no face detected
                sharpness_score = self.calculate_roi_sharpness(gray)
                brightness_score = self.calculate_roi_brightness(gray)
                contrast_score = self.calculate_roi_contrast(gray)
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
                if sharpness_score < self.sharpness_threshold:
                    quality_issues.append('LOW_SHARPNESS')
                if brightness_score < self.brightness_threshold:
                    quality_issues.append('POOR_LIGHTING')
                if contrast_score < self.contrast_threshold:
                    quality_issues.append('LOW_CONTRAST')
                if face_size_score < self.face_size_threshold:
                    quality_issues.append('SMALL_FACE_SIZE')
                if pose_score < self.pose_threshold:
                    quality_issues.append('POOR_FACE_POSE')
                if eye_visibility < self.eye_visibility_threshold:
                    quality_issues.append('EYES_NOT_VISIBLE')
                if face_confidence < self.detection_confidence_threshold:
                    quality_issues.append('LOW_DETECTION_CONFIDENCE')

            # Save quality metrics to database
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
                    improvement_suggestions=self.generate_improvement_suggestions(quality_issues)
                )
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.warning(f"Could not save quality metrics: {str(e)}")

            return {
                'overall_quality': float(overall_quality),
                'sharpness_score': float(sharpness_score),
                'brightness_score': float(brightness_score),
                'contrast_score': float(contrast_score),
                'face_size_score': float(face_size_score),
                'quality_issues': quality_issues,
                'cached': False
            }

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error assessing image quality: {str(e)}")
            return {
                'overall_quality': 0.0,
                'error': str(e)
            }

    def detect_face_roi(self, image) -> Tuple[Optional[Tuple[int, int, int, int]], float]:
        """
        Detect face region of interest using Haar cascades.

        Args:
            image: OpenCV image (BGR format)

        Returns:
            Tuple of (face_roi, confidence) where:
                - face_roi: (x, y, w, h) or None if no face detected
                - confidence: Detection confidence score
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Use Haar cascade for face detection (lightweight)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            if len(faces) > 0:
                # Return the largest face
                largest_face = max(faces, key=lambda face: face[2] * face[3])
                x, y, w, h = largest_face
                confidence = 0.8  # Mock confidence for Haar cascade
                return (x, y, w, h), confidence

            return None, 0.0

        except (AttributeError, cv2.error, TypeError, ValueError) as e:
            logger.error(f"Error detecting face ROI: {str(e)}")
            return None, 0.0

    def calculate_roi_sharpness(self, roi_gray) -> float:
        """
        Calculate sharpness score using Laplacian variance.

        Args:
            roi_gray: Grayscale ROI image

        Returns:
            Sharpness score (0.0-1.0)
        """
        try:
            laplacian_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
            # Normalize to 0-1 range (100 is empirically good threshold)
            return float(min(1.0, laplacian_var / 100.0))
        except (cv2.error, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI sharpness: {e}")
            return 0.0

    def calculate_roi_brightness(self, roi_gray) -> float:
        """
        Calculate brightness adequacy score for ROI.

        Args:
            roi_gray: Grayscale ROI image

        Returns:
            Brightness score (0.0-1.0)
        """
        try:
            mean_brightness = np.mean(roi_gray)
            # Optimal brightness around 127 (middle gray)
            return float(1.0 - abs(mean_brightness - 127) / 127.0)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI brightness: {e}")
            return 0.0

    def calculate_roi_contrast(self, roi_gray) -> float:
        """
        Calculate contrast score for ROI.

        Args:
            roi_gray: Grayscale ROI image

        Returns:
            Contrast score (0.0-1.0)
        """
        try:
            contrast = np.std(roi_gray)
            # Normalize (64 is empirically good threshold)
            return float(min(1.0, contrast / 64.0))
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to calculate ROI contrast: {e}")
            return 0.0

    def calculate_face_size_score(self, face_w: int, face_h: int, img_w: int, img_h: int) -> float:
        """
        Calculate face size adequacy score.

        Args:
            face_w: Face width in pixels
            face_h: Face height in pixels
            img_w: Image width in pixels
            img_h: Image height in pixels

        Returns:
            Face size score (0.0-1.0)
        """
        try:
            face_area = face_w * face_h
            img_area = img_w * img_h
            face_ratio = face_area / img_area

            # Optimal face ratio between 0.1 and 0.4 (10-40% of image)
            if 0.1 <= face_ratio <= 0.4:
                return 1.0
            elif face_ratio < 0.1:
                return float(face_ratio / 0.1)  # Scale from 0 to 1
            else:
                return float(max(0.1, 1.0 - (face_ratio - 0.4) / 0.6))  # Decrease for very large faces
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"Failed to calculate face size score: {e}")
            return 0.0

    def estimate_face_pose_quality(self, face_color) -> float:
        """
        Estimate face pose quality using symmetry analysis.

        Args:
            face_color: Color face ROI image

        Returns:
            Pose quality score (0.0-1.0)
        """
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
            return float(max(0.0, min(1.0, (correlation + 1) / 2)))
        except (cv2.error, ValueError, TypeError, AttributeError, IndexError) as e:
            logger.warning(f"Failed to estimate face pose quality: {e}")
            return 0.5  # Default neutral score

    def check_eye_visibility(self, face_color, face_roi) -> float:
        """
        Check if eyes are visible in the face.

        Args:
            face_color: Color face ROI image
            face_roi: Face bounding box (not used in current implementation)

        Returns:
            Eye visibility score (0.0-1.0)
        """
        try:
            # Use eye cascade to detect eyes
            gray = cv2.cvtColor(face_color, cv2.COLOR_BGR2GRAY)
            eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            eyes = eye_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(10, 10)
            )

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

    def generate_improvement_suggestions(self, quality_issues: List[str]) -> List[str]:
        """
        Generate actionable suggestions based on quality issues.

        Args:
            quality_issues: List of quality issue identifiers

        Returns:
            List of actionable improvement suggestions
        """
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

    def calculate_image_hash(self, image_path: str) -> str:
        """
        Calculate SHA256 hash of image file.

        Args:
            image_path: Path to the image file

        Returns:
            Truncated SHA256 hash (first 16 characters)
        """
        try:
            if not os.path.exists(image_path):
                return hashlib.sha256(image_path.encode()).hexdigest()[:16]

            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            return file_hash[:16]  # Truncate for storage

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            logger.error(f"Error calculating image hash: {str(e)}")
            return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
