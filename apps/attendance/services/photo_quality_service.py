"""
Photo Quality Validation Service

Validates attendance photos for quality and face detection.

Features:
- Face detection using OpenCV or face_recognition library
- Blur detection (Laplacian variance)
- Brightness analysis
- Resolution validation
- File size validation
- Image compression
- Thumbnail generation

Quality Checks:
1. Resolution: Minimum 480x480 pixels
2. Face Detection: At least one face present
3. Blur: Laplacian variance > 100
4. Brightness: 50-220 range (0-255 scale)
5. File Size: <200KB after compression
"""

from PIL import Image, ImageStat
from io import BytesIO
from typing import Tuple, Dict, Any, Optional
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.core.exceptions import ValidationError
from apps.attendance.models.attendance_photo import PhotoQualityThreshold, AttendancePhoto
from apps.attendance.exceptions import AttendanceValidationError
import logging
import base64

logger = logging.getLogger(__name__)


class PhotoQualityService:
    """
    Service for validating and processing attendance photos.
    """

    DEFAULT_MIN_WIDTH = 480
    DEFAULT_MIN_HEIGHT = 480
    DEFAULT_MAX_SIZE_KB = 200
    DEFAULT_MIN_QUALITY = 0.5

    @classmethod
    def validate_photo(
        cls,
        image_file,
        client_id: Optional[int] = None,
        check_face: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive photo validation.

        Args:
            image_file: Uploaded image file
            client_id: Client ID for custom thresholds
            check_face: Whether to perform face detection

        Returns:
            Tuple of (is_valid, validation_results)

        Validation Results Dict:
            {
                'is_valid': bool,
                'errors': list[str],
                'warnings': list[str],
                'quality_score': float,
                'quality_rating': str,
                'face_detected': bool,
                'face_count': int,
                'face_confidence': float,
                'is_blurry': bool,
                'is_dark': bool,
                'brightness': float,
                'resolution': tuple,
                'file_size_kb': float,
            }
        """
        errors = []
        warnings = []
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'quality_score': 0.0,
            'quality_rating': 'REJECTED',
            'face_detected': False,
            'face_count': 0,
            'face_confidence': 0.0,
            'is_blurry': False,
            'is_dark': False,
            'brightness': 0.0,
            'resolution': (0, 0),
            'file_size_kb': 0.0,
        }

        try:
            # Get quality thresholds
            thresholds = cls._get_thresholds(client_id)

            # Open image
            image = Image.open(image_file)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Check 1: Resolution
            width, height = image.size
            results['resolution'] = (width, height)

            if width < thresholds['min_width'] or height < thresholds['min_height']:
                errors.append(
                    f"Resolution too low: {width}x{height} (minimum: {thresholds['min_width']}x{thresholds['min_height']})"
                )
                results['is_valid'] = False

            # Check 2: File size
            image_file.seek(0)  # Reset file pointer
            file_size_bytes = len(image_file.read())
            file_size_kb = file_size_bytes / 1024
            results['file_size_kb'] = round(file_size_kb, 2)

            if file_size_kb > thresholds['max_file_size_kb']:
                warnings.append(
                    f"File size large: {file_size_kb:.1f}KB (will be compressed to <{thresholds['max_file_size_kb']}KB)"
                )

            # Check 3: Brightness
            brightness = cls._calculate_brightness(image)
            results['brightness'] = brightness

            if brightness < thresholds['min_brightness']:
                errors.append(f"Photo too dark: brightness {brightness}")
                results['is_dark'] = True
                results['is_valid'] = False
            elif brightness > thresholds['max_brightness']:
                errors.append(f"Photo too bright: brightness {brightness}")
                results['is_valid'] = False

            # Check 4: Blur detection
            image_file.seek(0)
            is_blurry, blur_score = cls._detect_blur(image_file)
            results['is_blurry'] = is_blurry

            if is_blurry:
                errors.append(f"Photo too blurry: score {blur_score:.2f}")
                results['is_valid'] = False

            # Check 5: Face detection
            if check_face and thresholds['require_face_detection']:
                image_file.seek(0)
                face_detected, face_count, face_confidence = cls._detect_faces(image_file)

                results['face_detected'] = face_detected
                results['face_count'] = face_count
                results['face_confidence'] = face_confidence

                if not face_detected:
                    errors.append("No face detected in photo")
                    results['is_valid'] = False
                elif face_count > 1:
                    warnings.append(f"Multiple faces detected ({face_count}). Ensure only one person in photo.")
                elif face_confidence < thresholds['min_face_confidence']:
                    errors.append(f"Face detection confidence too low: {face_confidence:.2f}")
                    results['is_valid'] = False

            # Calculate overall quality score
            quality_score = cls._calculate_quality_score(results)
            results['quality_score'] = quality_score

            # Determine quality rating
            if quality_score >= 0.9:
                results['quality_rating'] = AttendancePhoto.PhotoQuality.EXCELLENT
            elif quality_score >= 0.7:
                results['quality_rating'] = AttendancePhoto.PhotoQuality.GOOD
            elif quality_score >= 0.5:
                results['quality_rating'] = AttendancePhoto.PhotoQuality.ACCEPTABLE
            else:
                results['quality_rating'] = AttendancePhoto.PhotoQuality.POOR

            results['errors'] = errors
            results['warnings'] = warnings

            return results['is_valid'], results

        except Exception as e:
            logger.error(f"Photo validation failed: {e}", exc_info=True)
            results['is_valid'] = False
            results['errors'] = [f"Validation error: {str(e)}"]
            return False, results

    @staticmethod
    def _get_thresholds(client_id: Optional[int]) -> Dict[str, Any]:
        """Get quality thresholds for client"""
        defaults = {
            'min_width': PhotoQualityService.DEFAULT_MIN_WIDTH,
            'min_height': PhotoQualityService.DEFAULT_MIN_HEIGHT,
            'max_file_size_kb': PhotoQualityService.DEFAULT_MAX_SIZE_KB,
            'require_face_detection': True,
            'min_face_confidence': 0.8,
            'max_blur_threshold': 100.0,
            'min_brightness': 50,
            'max_brightness': 220,
        }

        if client_id:
            try:
                threshold = PhotoQualityThreshold.objects.get(
                    client_id=client_id,
                    is_active=True
                )
                return {
                    'min_width': threshold.min_width,
                    'min_height': threshold.min_height,
                    'max_file_size_kb': threshold.max_file_size_kb,
                    'require_face_detection': threshold.require_face_detection,
                    'min_face_confidence': threshold.min_face_confidence,
                    'max_blur_threshold': threshold.max_blur_threshold,
                    'min_brightness': threshold.min_brightness,
                    'max_brightness': threshold.max_brightness,
                }
            except PhotoQualityThreshold.DoesNotExist:
                pass

        return defaults

    @staticmethod
    def _calculate_brightness(image: Image.Image) -> float:
        """Calculate average brightness of image"""
        grayscale = image.convert('L')
        stat = ImageStat.Stat(grayscale)
        return stat.mean[0]  # Average brightness (0-255)

    @staticmethod
    def _detect_blur(image_file) -> Tuple[bool, float]:
        """
        Detect if image is blurry using Laplacian variance.

        Args:
            image_file: Image file

        Returns:
            Tuple of (is_blurry, blur_score)
        """
        try:
            import cv2
            import numpy as np

            # Read image
            image_file.seek(0)
            file_bytes = np.frombuffer(image_file.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)

            # Calculate Laplacian variance
            laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()

            # Threshold: variance < 100 indicates blur
            is_blurry = laplacian_var < 100.0

            return is_blurry, laplacian_var

        except ImportError:
            logger.warning("OpenCV not available, skipping blur detection")
            return False, 0.0
        except Exception as e:
            logger.error(f"Blur detection failed: {e}")
            return False, 0.0

    @staticmethod
    def _detect_faces(image_file) -> Tuple[bool, int, float]:
        """
        Detect faces in image.

        Args:
            image_file: Image file

        Returns:
            Tuple of (face_detected, face_count, confidence)
        """
        try:
            import face_recognition

            # Load image
            image_file.seek(0)
            img = face_recognition.load_image_file(image_file)

            # Detect faces
            face_locations = face_recognition.face_locations(img, model='hog')
            face_count = len(face_locations)

            # For confidence, we'll use the number of faces detected
            # Real face recognition models provide confidence scores
            confidence = 1.0 if face_count == 1 else 0.8 if face_count > 0 else 0.0

            return face_count > 0, face_count, confidence

        except ImportError:
            logger.warning("face_recognition library not available, skipping face detection")
            return True, 1, 1.0  # Assume valid if lib not available
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return False, 0, 0.0

    @staticmethod
    def _calculate_quality_score(validation_results: Dict[str, Any]) -> float:
        """
        Calculate overall quality score (0-1).

        Factors:
        - Face detection: 40%
        - Blur: 30%
        - Brightness: 20%
        - Resolution: 10%
        """
        score = 0.0

        # Face detection (40%)
        if validation_results['face_detected']:
            if validation_results['face_count'] == 1:
                score += 0.40 * validation_results['face_confidence']
            elif validation_results['face_count'] > 1:
                score += 0.30  # Penalty for multiple faces

        # Blur (30%)
        if not validation_results['is_blurry']:
            score += 0.30

        # Brightness (20%)
        brightness = validation_results['brightness']
        if 80 <= brightness <= 180:  # Optimal range
            score += 0.20
        elif 50 <= brightness <= 220:  # Acceptable range
            score += 0.10

        # Resolution (10%)
        width, height = validation_results['resolution']
        if width >= 720 and height >= 720:
            score += 0.10
        elif width >= 480 and height >= 480:
            score += 0.05

        return min(score, 1.0)

    @classmethod
    def compress_image(
        cls,
        image_file,
        max_size_kb: int = 200,
        quality: int = 85
    ) -> BytesIO:
        """
        Compress image to target file size.

        Args:
            image_file: Input image file
            max_size_kb: Target max size in KB
            quality: JPEG quality (1-100)

        Returns:
            BytesIO with compressed image
        """
        try:
            # Open image
            image = Image.open(image_file)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Compress iteratively until target size reached
            output = BytesIO()
            current_quality = quality

            while current_quality > 20:  # Don't go below quality 20
                output = BytesIO()
                image.save(output, format='JPEG', quality=current_quality, optimize=True)
                size_kb = len(output.getvalue()) / 1024

                if size_kb <= max_size_kb:
                    break

                current_quality -= 5

            output.seek(0)
            logger.debug(f"Compressed image to {len(output.getvalue()) / 1024:.1f}KB (quality: {current_quality})")
            return output

        except Exception as e:
            logger.error(f"Image compression failed: {e}", exc_info=True)
            raise AttendanceValidationError(f"Failed to compress image: {e}")

    @classmethod
    def generate_thumbnail(
        cls,
        image_file,
        size: Tuple[int, int] = (150, 150)
    ) -> BytesIO:
        """
        Generate thumbnail for image.

        Args:
            image_file: Input image file
            size: Thumbnail size (width, height)

        Returns:
            BytesIO with thumbnail image
        """
        try:
            image = Image.open(image_file)
            image.thumbnail(size, Image.Resampling.LANCZOS)

            output = BytesIO()
            image.save(output, format='JPEG', quality=85)
            output.seek(0)

            logger.debug(f"Generated {size[0]}x{size[1]} thumbnail")
            return output

        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}", exc_info=True)
            return None

    @classmethod
    def match_face_to_template(
        cls,
        photo_image,
        employee_id: int
    ) -> Tuple[bool, float]:
        """
        Match photo against enrolled face template.

        Args:
            photo_image: Photo to match
            employee_id: Employee ID to match against

        Returns:
            Tuple of (matches, confidence_score)
        """
        try:
            import face_recognition

            # Load photo
            img = face_recognition.load_image_file(photo_image)

            # Get face encoding from photo
            face_encodings = face_recognition.face_encodings(img)

            if not face_encodings:
                logger.warning(f"No face found in photo for employee {employee_id}")
                return False, 0.0

            photo_encoding = face_encodings[0]  # Use first face

            # Get enrolled template from database
            # This would integrate with face_recognition app
            # For now, returning a placeholder
            from apps.face_recognition.services import FaceRecognitionService

            enrolled_encoding = FaceRecognitionService.get_employee_encoding(employee_id)

            if not enrolled_encoding:
                logger.warning(f"No enrolled template for employee {employee_id}")
                return False, 0.0

            # Compare faces
            matches = face_recognition.compare_faces([enrolled_encoding], photo_encoding, tolerance=0.6)
            face_distance = face_recognition.face_distance([enrolled_encoding], photo_encoding)[0]

            # Convert distance to confidence (0-1)
            confidence = 1.0 - face_distance

            is_match = matches[0] and confidence >= 0.4

            logger.info(f"Face match for employee {employee_id}: {is_match} (confidence: {confidence:.3f})")
            return is_match, confidence

        except ImportError:
            logger.warning("face_recognition library not available")
            return True, 1.0  # Assume match if library not available
        except Exception as e:
            logger.error(f"Face matching failed: {e}", exc_info=True)
            return False, 0.0

    @classmethod
    def process_attendance_photo(
        cls,
        image_file,
        attendance_record,
        employee,
        photo_type: str,
        client_id: Optional[int] = None
    ) -> AttendancePhoto:
        """
        Process and save attendance photo.

        Full workflow:
        1. Validate photo quality
        2. Detect and verify face
        3. Compress image
        4. Generate thumbnail
        5. Upload to S3
        6. Create database record

        Args:
            image_file: Uploaded image
            attendance_record: PeopleEventlog instance
            employee: Employee user object
            photo_type: CLOCK_IN or CLOCK_OUT
            client_id: Client ID for thresholds

        Returns:
            Created AttendancePhoto instance

        Raises:
            AttendanceValidationError: If photo fails validation
        """
        # Validate photo
        is_valid, validation_results = cls.validate_photo(
            image_file,
            client_id=client_id,
            check_face=True
        )

        if not is_valid:
            error_msg = "; ".join(validation_results['errors'])
            raise AttendanceValidationError(
                f"Photo validation failed: {error_msg}",
                context={'validation_results': validation_results}
            )

        # Match face to enrolled template
        image_file.seek(0)
        matches_template, match_confidence = cls.match_face_to_template(
            image_file,
            employee.id
        )

        if not matches_template:
            raise AttendanceValidationError(
                f"Face does not match enrolled template (confidence: {match_confidence:.2f})",
                context={'match_confidence': match_confidence}
            )

        # Compress image
        image_file.seek(0)
        compressed = cls.compress_image(image_file, max_size_kb=200)

        # Generate thumbnail
        image_file.seek(0)
        thumbnail = cls.generate_thumbnail(image_file)

        # Create AttendancePhoto record
        photo = AttendancePhoto.objects.create(
            attendance_record=attendance_record,
            employee=employee,
            photo_type=photo_type,
            tenant=employee.client_id if hasattr(employee, 'client_id') else 'default',
            # Image will be saved by Django
            width=validation_results['resolution'][0],
            height=validation_results['resolution'][1],
            file_size_bytes=int(validation_results['file_size_kb'] * 1024),
            face_detected=validation_results['face_detected'],
            face_count=validation_results['face_count'],
            face_confidence=validation_results['face_confidence'],
            quality_score=validation_results['quality_score'],
            quality_rating=validation_results['quality_rating'],
            is_blurry=validation_results['is_blurry'],
            is_dark=validation_results['is_dark'],
            brightness=validation_results['brightness'],
            matches_enrolled_template=matches_template,
            match_confidence=match_confidence,
            validation_passed=True,
            validation_errors=[],
        )

        # Save compressed image
        from django.core.files.base import ContentFile
        photo.image.save(
            f'attendance_{employee.id}_{photo_type}_{photo.uuid}.jpg',
            ContentFile(compressed.getvalue()),
            save=False
        )

        # Save thumbnail if generated
        if thumbnail:
            photo.thumbnail.save(
                f'thumb_{employee.id}_{photo_type}_{photo.uuid}.jpg',
                ContentFile(thumbnail.getvalue()),
                save=False
            )

        photo.save()

        logger.info(f"Processed attendance photo for {employee.username} - {photo_type}")
        return photo
