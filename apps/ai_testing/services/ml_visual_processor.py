"""
ML Visual Processor Service
Semantic visual regression analysis with machine learning-enhanced understanding
"""

import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class VisualDifference:
    """Represents a visual difference between baseline and current state"""
    region: Tuple[int, int, int, int]  # x, y, width, height
    difference_type: str  # 'content', 'layout', 'color', 'size'
    severity: str  # 'cosmetic', 'minor', 'major', 'critical'
    confidence: float
    description: str
    affected_elements: List[str]


@dataclass
class SemanticAnalysis:
    """Results of semantic analysis"""
    elements_added: List[Dict]
    elements_removed: List[Dict]
    elements_modified: List[Dict]
    layout_changes: List[Dict]
    color_changes: List[Dict]
    text_changes: List[Dict]
    interaction_changes: List[Dict]


class MLVisualProcessor:
    """
    ML-powered visual regression analysis with semantic understanding of UI changes
    """

    def __init__(self):
        self.similarity_threshold = 0.95
        self.element_detection_confidence = 0.7
        self.cosmetic_change_threshold = 0.05

    def analyze_semantic_difference(self, baseline: MLBaseline,
                                  new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze visual differences with semantic understanding

        Args:
            baseline: MLBaseline instance with current baseline data
            new_data: New visual/functional data to compare

        Returns:
            Comprehensive analysis of differences
        """
        logger.info(f"Analyzing semantic differences for {baseline.component_name}")

        try:
            if baseline.baseline_type == 'visual':
                return self._analyze_visual_differences(baseline, new_data)
            elif baseline.baseline_type == 'functional':
                return self._analyze_functional_differences(baseline, new_data)
            elif baseline.baseline_type == 'performance':
                return self._analyze_performance_differences(baseline, new_data)
            else:
                return self._analyze_generic_differences(baseline, new_data)

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error in semantic analysis: {str(e)}")
            return {
                'error': str(e),
                'analysis_type': baseline.baseline_type,
                'timestamp': datetime.now().isoformat()
            }

    def _analyze_visual_differences(self, baseline: MLBaseline,
                                  new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze visual differences with semantic understanding"""
        # Extract visual components
        baseline_image = self._load_baseline_image(baseline)
        new_image = self._load_new_image(new_data)

        if baseline_image is None or new_image is None:
            return {'error': 'Could not load images for comparison'}

        # Ensure images are same size for comparison
        new_image = self._resize_to_match(new_image, baseline_image.size)

        # Detect semantic elements in both images
        baseline_elements = self._detect_semantic_elements(
            baseline_image, baseline.semantic_elements
        )
        new_elements = self._detect_semantic_elements(
            new_image, {}
        )

        # Perform semantic analysis
        semantic_analysis = self._compare_semantic_elements(baseline_elements, new_elements)

        # Calculate pixel-level differences
        pixel_diff = self._calculate_pixel_differences(baseline_image, new_image)

        # Identify significant visual differences
        visual_differences = self._identify_visual_differences(
            baseline_image, new_image, semantic_analysis
        )

        # Calculate overall difference score
        overall_score = self._calculate_overall_difference_score(
            pixel_diff, semantic_analysis, visual_differences
        )

        # Classify the type of change
        change_classification = self._classify_visual_changes(
            semantic_analysis, visual_differences, overall_score
        )

        # Generate human-readable summary
        summary = self._generate_visual_summary(
            semantic_analysis, visual_differences, change_classification
        )

        return {
            'analysis_type': 'visual',
            'overall_difference_score': overall_score,
            'pixel_difference_percentage': pixel_diff['difference_percentage'],
            'semantic_analysis': semantic_analysis.__dict__,
            'visual_differences': [diff.__dict__ for diff in visual_differences],
            'change_classification': change_classification,
            'summary': summary,
            'baseline_elements_count': len(baseline_elements),
            'new_elements_count': len(new_elements),
            'is_regression': change_classification.get('is_regression', False),
            'requires_human_review': change_classification.get('requires_review', False),
            'confidence': self._calculate_analysis_confidence(semantic_analysis, visual_differences),
            'analyzed_at': datetime.now().isoformat()
        }

    def _load_baseline_image(self, baseline: MLBaseline) -> Optional[Image.Image]:
        """Load baseline image from storage"""
        # This would load from actual image storage
        # For now, create a placeholder
        try:
            # In real implementation, would load from S3, filesystem, etc.
            # based on baseline.visual_hash
            return Image.new('RGB', (800, 600), color='white')
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error loading baseline image: {str(e)}")
            return None

    def _load_new_image(self, new_data: Dict[str, Any]) -> Optional[Image.Image]:
        """Load new image for comparison"""
        try:
            # Extract image from new_data
            if 'image_data' in new_data:
                # Handle base64 encoded image
                import base64
                from io import BytesIO

                image_data = base64.b64decode(new_data['image_data'])
                return Image.open(BytesIO(image_data))
            elif 'image_path' in new_data:
                # Load from file path
                return Image.open(new_data['image_path'])
            else:
                # Create placeholder
                return Image.new('RGB', (800, 600), color='lightgray')
        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            logger.error(f"Error loading new image: {str(e)}")
            return None

    def _resize_to_match(self, image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """Resize image to match target size"""
        return image.resize(target_size, Image.Resampling.LANCZOS)

    def _detect_semantic_elements(self, image: Image.Image,
                                existing_elements: Dict) -> List[Dict[str, Any]]:
        """Detect semantic UI elements in image using ML models"""
        # This would use computer vision models like YOLO, R-CNN, or custom models
        # For now, implement basic element detection simulation

        elements = []

        # Convert to OpenCV format for processing
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # Detect button-like elements (rectangles with text)
        elements.extend(self._detect_buttons(cv_image, gray))

        # Detect text elements
        elements.extend(self._detect_text_elements(cv_image, gray))

        # Detect images/icons
        elements.extend(self._detect_images(cv_image, gray))

        # Detect input fields
        elements.extend(self._detect_input_fields(cv_image, gray))

        # Detect navigation elements
        elements.extend(self._detect_navigation(cv_image, gray))

        return elements

    def _detect_buttons(self, cv_image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect button elements"""
        elements = []

        # Use edge detection to find rectangular regions
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            # Filter for rectangular shapes that could be buttons
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            if len(approx) == 4:  # Rectangular
                x, y, w, h = cv2.boundingRect(approx)

                # Filter by size (buttons are usually medium-sized)
                if 50 < w < 300 and 20 < h < 80:
                    elements.append({
                        'element_type': 'button',
                        'bounding_box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                        'confidence': 0.8,
                        'properties': {
                            'area': int(w * h),
                            'aspect_ratio': round(w / h, 2)
                        }
                    })

        return elements

    def _detect_text_elements(self, cv_image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect text elements"""
        elements = []

        # Use OCR or text detection algorithms
        # For simulation, detect text-like regions

        # Find text regions using morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
        morphed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter for text-like dimensions
            if w > 20 and h > 10 and w / h > 2:  # Horizontal text
                elements.append({
                    'element_type': 'label',
                    'bounding_box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                    'confidence': 0.6,
                    'properties': {
                        'text_length_estimate': int(w / 8),  # Rough character count
                        'text_height': int(h)
                    }
                })

        return elements

    def _detect_images(self, cv_image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect image elements"""
        elements = []

        # Look for regions with high variance (likely images)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        laplacian = cv2.Laplacian(blur, cv2.CV_64F)

        # Find contours of high-variance regions
        _, thresh = cv2.threshold(np.abs(laplacian).astype(np.uint8), 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter for image-like dimensions
            if w > 50 and h > 50 and w * h > 2500:
                elements.append({
                    'element_type': 'image',
                    'bounding_box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                    'confidence': 0.7,
                    'properties': {
                        'area': int(w * h),
                        'is_square': abs(w - h) < min(w, h) * 0.1
                    }
                })

        return elements

    def _detect_input_fields(self, cv_image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect input field elements"""
        elements = []

        # Look for rectangular regions with borders (typical input fields)
        edges = cv2.Canny(gray, 100, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            if len(approx) == 4:  # Rectangular
                x, y, w, h = cv2.boundingRect(approx)

                # Input fields are usually wider than they are tall
                if w > 100 and 20 < h < 50 and w / h > 3:
                    elements.append({
                        'element_type': 'text_field',
                        'bounding_box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                        'confidence': 0.75,
                        'properties': {
                            'aspect_ratio': round(w / h, 2),
                            'likely_input': True
                        }
                    })

        return elements

    def _detect_navigation(self, cv_image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect navigation elements"""
        elements = []

        # Look for horizontal groups of elements (navigation bars)
        height, width = gray.shape

        # Check top portion for navigation
        nav_region = gray[:height//4, :]

        # Find horizontal structures
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
        morphed = cv2.morphologyEx(nav_region, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Navigation elements are usually wide and at the top
            if w > width * 0.3 and y < height // 4:
                elements.append({
                    'element_type': 'navigation',
                    'bounding_box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                    'confidence': 0.6,
                    'properties': {
                        'position': 'top',
                        'width_percentage': round(w / width * 100, 1)
                    }
                })

        return elements

    def _compare_semantic_elements(self, baseline_elements: List[Dict],
                                 new_elements: List[Dict]) -> SemanticAnalysis:
        """Compare semantic elements between baseline and new state"""
        # Match elements between baseline and new
        matched_pairs, added_elements, removed_elements = self._match_elements(
            baseline_elements, new_elements
        )

        # Analyze modifications
        modified_elements = []
        for baseline_elem, new_elem in matched_pairs:
            modifications = self._analyze_element_modifications(baseline_elem, new_elem)
            if modifications:
                modified_elements.append({
                    'baseline': baseline_elem,
                    'new': new_elem,
                    'modifications': modifications
                })

        # Analyze layout changes
        layout_changes = self._analyze_layout_changes(baseline_elements, new_elements)

        # Analyze color changes
        color_changes = self._analyze_color_changes(matched_pairs)

        # Analyze text changes
        text_changes = self._analyze_text_changes(matched_pairs)

        # Analyze interaction changes
        interaction_changes = self._analyze_interaction_changes(matched_pairs)

        return SemanticAnalysis(
            elements_added=added_elements,
            elements_removed=removed_elements,
            elements_modified=modified_elements,
            layout_changes=layout_changes,
            color_changes=color_changes,
            text_changes=text_changes,
            interaction_changes=interaction_changes
        )

    def _match_elements(self, baseline_elements: List[Dict], new_elements: List[Dict]
                      ) -> Tuple[List[Tuple[Dict, Dict]], List[Dict], List[Dict]]:
        """Match elements between baseline and new state"""
        matched_pairs = []
        unmatched_baseline = baseline_elements.copy()
        unmatched_new = new_elements.copy()

        # Simple matching based on position and type
        for baseline_elem in baseline_elements:
            best_match = None
            best_score = 0

            for new_elem in new_elements:
                score = self._calculate_element_similarity(baseline_elem, new_elem)
                if score > best_score and score > 0.7:  # Threshold for considering a match
                    best_match = new_elem
                    best_score = score

            if best_match:
                matched_pairs.append((baseline_elem, best_match))
                unmatched_baseline.remove(baseline_elem)
                unmatched_new.remove(best_match)

        return matched_pairs, unmatched_new, unmatched_baseline

    def _calculate_element_similarity(self, elem1: Dict, elem2: Dict) -> float:
        """Calculate similarity between two elements"""
        score = 0.0

        # Type similarity
        if elem1['element_type'] == elem2['element_type']:
            score += 0.4

        # Position similarity
        bbox1 = elem1['bounding_box']
        bbox2 = elem2['bounding_box']

        center1 = (bbox1['x'] + bbox1['width'] // 2, bbox1['y'] + bbox1['height'] // 2)
        center2 = (bbox2['x'] + bbox2['width'] // 2, bbox2['y'] + bbox2['height'] // 2)

        # Calculate distance between centers
        distance = ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5

        # Normalize distance (closer = higher score)
        max_distance = 800  # Assume max screen width
        position_score = max(0, 1 - (distance / max_distance))
        score += position_score * 0.4

        # Size similarity
        area1 = bbox1['width'] * bbox1['height']
        area2 = bbox2['width'] * bbox2['height']

        size_similarity = min(area1, area2) / max(area1, area2) if max(area1, area2) > 0 else 0
        score += size_similarity * 0.2

        return score

    def _analyze_element_modifications(self, baseline_elem: Dict, new_elem: Dict) -> Dict[str, Any]:
        """Analyze modifications between matched elements"""
        modifications = {}

        bbox1 = baseline_elem['bounding_box']
        bbox2 = new_elem['bounding_box']

        # Position changes
        pos_change = {
            'x': bbox2['x'] - bbox1['x'],
            'y': bbox2['y'] - bbox1['y']
        }

        if abs(pos_change['x']) > 5 or abs(pos_change['y']) > 5:
            modifications['position'] = pos_change

        # Size changes
        size_change = {
            'width': bbox2['width'] - bbox1['width'],
            'height': bbox2['height'] - bbox1['height']
        }

        if abs(size_change['width']) > 5 or abs(size_change['height']) > 5:
            modifications['size'] = size_change

        # Property changes
        props1 = baseline_elem.get('properties', {})
        props2 = new_elem.get('properties', {})

        for key in set(props1.keys()) | set(props2.keys()):
            if props1.get(key) != props2.get(key):
                if 'properties' not in modifications:
                    modifications['properties'] = {}
                modifications['properties'][key] = {
                    'old': props1.get(key),
                    'new': props2.get(key)
                }

        return modifications

    def _analyze_layout_changes(self, baseline_elements: List[Dict], new_elements: List[Dict]) -> List[Dict]:
        """Analyze layout-level changes"""
        changes = []

        # Check for overall layout shifts
        if len(baseline_elements) > 0 and len(new_elements) > 0:
            baseline_centers = [(e['bounding_box']['x'] + e['bounding_box']['width'] // 2,
                               e['bounding_box']['y'] + e['bounding_box']['height'] // 2)
                              for e in baseline_elements]

            new_centers = [(e['bounding_box']['x'] + e['bounding_box']['width'] // 2,
                          e['bounding_box']['y'] + e['bounding_box']['height'] // 2)
                          for e in new_elements]

            # Calculate average positions
            avg_baseline = (np.mean([c[0] for c in baseline_centers]),
                          np.mean([c[1] for c in baseline_centers]))
            avg_new = (np.mean([c[0] for c in new_centers]),
                      np.mean([c[1] for c in new_centers]))

            shift = (avg_new[0] - avg_baseline[0], avg_new[1] - avg_baseline[1])

            if abs(shift[0]) > 10 or abs(shift[1]) > 10:
                changes.append({
                    'type': 'overall_shift',
                    'shift': {'x': shift[0], 'y': shift[1]},
                    'severity': 'minor' if max(abs(shift[0]), abs(shift[1])) < 50 else 'major'
                })

        return changes

    def _analyze_color_changes(self, matched_pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        """Analyze color changes between matched elements"""
        # This would analyze actual color properties if available
        # For now, return placeholder
        return []

    def _analyze_text_changes(self, matched_pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        """Analyze text changes between matched elements"""
        changes = []

        for baseline_elem, new_elem in matched_pairs:
            if baseline_elem['element_type'] in ['label', 'button'] and new_elem['element_type'] in ['label', 'button']:
                # Would compare actual text content if available via OCR
                # For now, check size changes that might indicate text changes
                baseline_area = baseline_elem['bounding_box']['width'] * baseline_elem['bounding_box']['height']
                new_area = new_elem['bounding_box']['width'] * new_elem['bounding_box']['height']

                size_change_pct = abs(new_area - baseline_area) / baseline_area if baseline_area > 0 else 0

                if size_change_pct > 0.2:  # 20% size change might indicate text change
                    changes.append({
                        'element_type': baseline_elem['element_type'],
                        'change_type': 'size_change_suggests_text_change',
                        'size_change_percentage': round(size_change_pct * 100, 1),
                        'severity': 'minor' if size_change_pct < 0.5 else 'major'
                    })

        return changes

    def _analyze_interaction_changes(self, matched_pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        """Analyze interaction-related changes"""
        changes = []

        for baseline_elem, new_elem in matched_pairs:
            # Check if interactive elements (buttons, inputs) have changed significantly
            if baseline_elem['element_type'] in ['button', 'text_field']:
                bbox1 = baseline_elem['bounding_box']
                bbox2 = new_elem['bounding_box']

                # Check if position changed significantly (affects usability)
                center1 = (bbox1['x'] + bbox1['width'] // 2, bbox1['y'] + bbox1['height'] // 2)
                center2 = (bbox2['x'] + bbox2['width'] // 2, bbox2['y'] + bbox2['height'] // 2)

                distance = ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5

                if distance > 50:  # Significant position change
                    changes.append({
                        'element_type': baseline_elem['element_type'],
                        'change_type': 'interaction_position_change',
                        'distance_moved': round(distance, 1),
                        'severity': 'major' if distance > 100 else 'minor',
                        'impact': 'User interaction patterns may be affected'
                    })

        return changes

    def _calculate_pixel_differences(self, baseline_image: Image.Image,
                                   new_image: Image.Image) -> Dict[str, Any]:
        """Calculate pixel-level differences between images"""
        # Convert to numpy arrays
        baseline_array = np.array(baseline_image)
        new_array = np.array(new_image)

        # Calculate absolute difference
        diff_array = np.abs(baseline_array.astype(np.int16) - new_array.astype(np.int16))

        # Calculate percentage of pixels that are different
        threshold = 30  # Threshold for considering a pixel "different"
        different_pixels = np.sum(np.any(diff_array > threshold, axis=2))
        total_pixels = baseline_array.shape[0] * baseline_array.shape[1]

        difference_percentage = (different_pixels / total_pixels) * 100

        return {
            'different_pixels': int(different_pixels),
            'total_pixels': int(total_pixels),
            'difference_percentage': round(difference_percentage, 2),
            'mean_pixel_difference': float(np.mean(diff_array)),
            'max_pixel_difference': float(np.max(diff_array))
        }

    def _identify_visual_differences(self, baseline_image: Image.Image, new_image: Image.Image,
                                   semantic_analysis: SemanticAnalysis) -> List[VisualDifference]:
        """Identify significant visual differences"""
        differences = []

        # Add differences for added/removed elements
        for added_elem in semantic_analysis.elements_added:
            bbox = added_elem['bounding_box']
            differences.append(VisualDifference(
                region=(bbox['x'], bbox['y'], bbox['width'], bbox['height']),
                difference_type='content',
                severity='minor',
                confidence=added_elem.get('confidence', 0.8),
                description=f"New {added_elem['element_type']} element added",
                affected_elements=[added_elem['element_type']]
            ))

        for removed_elem in semantic_analysis.elements_removed:
            bbox = removed_elem['bounding_box']
            differences.append(VisualDifference(
                region=(bbox['x'], bbox['y'], bbox['width'], bbox['height']),
                difference_type='content',
                severity='major',
                confidence=removed_elem.get('confidence', 0.8),
                description=f"{removed_elem['element_type']} element removed",
                affected_elements=[removed_elem['element_type']]
            ))

        # Add differences for modified elements
        for modified in semantic_analysis.elements_modified:
            baseline_elem = modified['baseline']
            modifications = modified['modifications']

            bbox = baseline_elem['bounding_box']
            severity = 'cosmetic'

            if 'position' in modifications:
                severity = 'minor'
            if 'size' in modifications:
                severity = 'minor' if severity == 'cosmetic' else 'major'

            differences.append(VisualDifference(
                region=(bbox['x'], bbox['y'], bbox['width'], bbox['height']),
                difference_type='layout',
                severity=severity,
                confidence=0.9,
                description=f"{baseline_elem['element_type']} element modified: {', '.join(modifications.keys())}",
                affected_elements=[baseline_elem['element_type']]
            ))

        return differences

    def _calculate_overall_difference_score(self, pixel_diff: Dict, semantic_analysis: SemanticAnalysis,
                                          visual_differences: List[VisualDifference]) -> float:
        """Calculate overall difference score"""
        # Start with pixel difference as base
        base_score = min(pixel_diff['difference_percentage'] / 100, 1.0)

        # Adjust based on semantic changes
        semantic_weight = 0.0

        # Weight for element changes
        semantic_weight += len(semantic_analysis.elements_added) * 0.1
        semantic_weight += len(semantic_analysis.elements_removed) * 0.2
        semantic_weight += len(semantic_analysis.elements_modified) * 0.05

        # Weight for layout changes
        semantic_weight += len(semantic_analysis.layout_changes) * 0.15

        # Weight for interaction changes
        semantic_weight += len(semantic_analysis.interaction_changes) * 0.25

        # Combine scores
        final_score = (base_score * 0.4) + (min(semantic_weight, 1.0) * 0.6)

        return min(final_score, 1.0)

    def _classify_visual_changes(self, semantic_analysis: SemanticAnalysis,
                               visual_differences: List[VisualDifference],
                               overall_score: float) -> Dict[str, Any]:
        """Classify the type and severity of visual changes"""
        classification = {
            'is_regression': False,
            'requires_review': False,
            'change_type': 'none',
            'severity_level': 'cosmetic',
            'confidence': 0.8
        }

        # Determine if this is likely a regression
        major_changes = [d for d in visual_differences if d.severity in ['major', 'critical']]
        removed_elements = len(semantic_analysis.elements_removed)
        interaction_changes = len(semantic_analysis.interaction_changes)

        if major_changes or removed_elements > 0 or interaction_changes > 0 or overall_score > 0.3:
            classification['is_regression'] = True
            classification['requires_review'] = True

        # Classify change type
        if len(semantic_analysis.elements_added) > len(semantic_analysis.elements_removed):
            classification['change_type'] = 'content_addition'
        elif len(semantic_analysis.elements_removed) > 0:
            classification['change_type'] = 'content_removal'
        elif len(semantic_analysis.layout_changes) > 0:
            classification['change_type'] = 'layout_change'
        elif overall_score > 0.05:
            classification['change_type'] = 'visual_update'
        else:
            classification['change_type'] = 'no_significant_change'

        # Determine severity
        if overall_score > 0.5 or removed_elements > 2:
            classification['severity_level'] = 'critical'
        elif overall_score > 0.2 or removed_elements > 0 or major_changes:
            classification['severity_level'] = 'major'
        elif overall_score > 0.05 or len(semantic_analysis.elements_modified) > 0:
            classification['severity_level'] = 'minor'

        return classification

    def _generate_visual_summary(self, semantic_analysis: SemanticAnalysis,
                               visual_differences: List[VisualDifference],
                               classification: Dict[str, Any]) -> str:
        """Generate human-readable summary of visual analysis"""
        if classification['change_type'] == 'no_significant_change':
            return "No significant visual changes detected."

        summary_parts = []

        # Element changes
        if semantic_analysis.elements_added:
            summary_parts.append(f"{len(semantic_analysis.elements_added)} element(s) added")
        if semantic_analysis.elements_removed:
            summary_parts.append(f"{len(semantic_analysis.elements_removed)} element(s) removed")
        if semantic_analysis.elements_modified:
            summary_parts.append(f"{len(semantic_analysis.elements_modified)} element(s) modified")

        # Layout changes
        if semantic_analysis.layout_changes:
            summary_parts.append(f"{len(semantic_analysis.layout_changes)} layout change(s)")

        # Interaction impact
        if semantic_analysis.interaction_changes:
            summary_parts.append(f"{len(semantic_analysis.interaction_changes)} interaction change(s)")

        if not summary_parts:
            summary_parts.append("Visual differences detected")

        summary = f"Visual analysis: {', '.join(summary_parts)}. "

        # Add severity context
        if classification['is_regression']:
            summary += "Changes may indicate a regression and require review."
        else:
            summary += "Changes appear to be intentional visual updates."

        return summary

    def _calculate_analysis_confidence(self, semantic_analysis: SemanticAnalysis,
                                     visual_differences: List[VisualDifference]) -> float:
        """Calculate confidence in the analysis"""
        # Base confidence
        confidence = 0.7

        # Increase confidence if we have clear semantic differences
        if semantic_analysis.elements_added or semantic_analysis.elements_removed:
            confidence += 0.15

        # Increase confidence if differences are consistent
        if len(visual_differences) > 0:
            avg_diff_confidence = np.mean([d.confidence for d in visual_differences])
            confidence += (avg_diff_confidence - 0.5) * 0.3

        return min(confidence, 1.0)

    def _analyze_functional_differences(self, baseline: MLBaseline, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze functional differences"""
        # Placeholder for functional analysis
        return {
            'analysis_type': 'functional',
            'differences_found': [],
            'overall_difference_score': 0.0,
            'summary': 'Functional analysis not yet implemented'
        }

    def _analyze_performance_differences(self, baseline: MLBaseline, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance differences"""
        # Placeholder for performance analysis
        return {
            'analysis_type': 'performance',
            'differences_found': [],
            'overall_difference_score': 0.0,
            'summary': 'Performance analysis not yet implemented'
        }

    def _analyze_generic_differences(self, baseline: MLBaseline, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze generic differences"""
        return {
            'analysis_type': 'generic',
            'differences_found': [],
            'overall_difference_score': 0.0,
            'summary': 'Generic analysis placeholder'
        }

    def create_baseline_from_analysis(self, analysis_result: Dict[str, Any],
                                    component_name: str, test_scenario: str,
                                    platform: str = 'all') -> MLBaseline:
        """Create a new ML baseline from analysis results"""
        try:
            # Extract baseline data from analysis
            if analysis_result.get('analysis_type') == 'visual':
                return self._create_visual_baseline(
                    analysis_result, component_name, test_scenario, platform
                )
            else:
                return self._create_generic_baseline(
                    analysis_result, component_name, test_scenario, platform
                )

        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            logger.error(f"Error creating baseline: {str(e)}")
            raise

    def _create_visual_baseline(self, analysis_result: Dict[str, Any],
                              component_name: str, test_scenario: str,
                              platform: str) -> MLBaseline:
        """Create visual baseline from analysis"""
        # Create baseline
        baseline = MLBaseline.objects.create(
            baseline_type='visual',
            component_name=component_name,
            test_scenario=test_scenario,
            platform=platform,
            app_version='current',  # Would be extracted from context
            visual_hash=hashlib.sha256(
                f"{component_name}_{test_scenario}_{datetime.now()}".encode()
            ).hexdigest(),
            semantic_elements=analysis_result.get('semantic_analysis', {}),
            approval_status='pending_review',
            semantic_confidence='medium',
            validation_score=analysis_result.get('confidence', 0.5)
        )

        # Create semantic elements
        for element_data in analysis_result.get('detected_elements', []):
            SemanticElement.objects.create(
                baseline=baseline,
                element_type=element_data['element_type'],
                element_description=f"Auto-detected {element_data['element_type']}",
                bounding_box=element_data['bounding_box'],
                interaction_type='display_only',  # Default
                detection_confidence=element_data.get('confidence', 0.7),
                visual_properties=element_data.get('properties', {})
            )

        return baseline

    def _create_generic_baseline(self, analysis_result: Dict[str, Any],
                               component_name: str, test_scenario: str,
                               platform: str) -> MLBaseline:
        """Create generic baseline"""
        return MLBaseline.objects.create(
            baseline_type='functional',
            component_name=component_name,
            test_scenario=test_scenario,
            platform=platform,
            app_version='current',
            approval_status='pending_review',
            semantic_confidence='medium',
            validation_score=analysis_result.get('confidence', 0.5)
        )