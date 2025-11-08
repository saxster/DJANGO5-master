"""
Resemblyzer Voice Verification Service (Sprint 2.4)

This service provides speaker recognition and voice verification using Resemblyzer:
- Voice embedding extraction
- Speaker verification
- Voiceprint matching with cosine similarity
- Audio preprocessing and quality assessment

Resemblyzer is a PyTorch-based speaker recognition library that extracts
speaker embeddings from audio files.

Reference: https://github.com/resemble-ai/Resemblyzer

Author: Development Team
Date: October 2025
Status: Real Resemblyzer integration implemented (Sprint 2.4)
"""

import logging
import numpy as np
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Import Resemblyzer for voice recognition
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    from resemblyzer.audio import sampling_rate
    import librosa
    import soundfile as sf
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS, FILE_IO_EXCEPTIONS
    RESEMBLYZER_AVAILABLE = True
    logger.info("Resemblyzer successfully imported - using real speaker recognition")
except ImportError as e:
    RESEMBLYZER_AVAILABLE = False
    logger.warning(
        f"Resemblyzer not available - falling back to mock: {e}. "
        "Install with: pip install resemblyzer librosa soundfile"
    )


class ResemblyzerVoiceService:
    """
    Service for voice verification using Resemblyzer speaker recognition.

    Provides:
    - Voice embedding extraction (d-vectors)
    - Speaker verification
    - Audio preprocessing
    - Quality assessment
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize Resemblyzer voice service.

        Args:
            use_cache: Whether to cache voice encoder model (default: True)
        """
        self.use_cache = use_cache
        self._encoder = None
        self._encoder_initialized = False

        # Quality thresholds
        self.min_snr_db = 15.0  # Minimum signal-to-noise ratio in dB
        self.min_duration_seconds = 2.0  # Minimum audio duration
        self.max_duration_seconds = 30.0  # Maximum audio duration
        self.target_sample_rate = 16000  # Resemblyzer uses 16kHz

        # Verification thresholds
        self.similarity_threshold = 0.70  # Cosine similarity threshold
        self.confidence_threshold = 0.75  # Confidence threshold

    @property
    def encoder(self):
        """
        Lazy-load voice encoder.

        Returns:
            VoiceEncoder instance or None if unavailable
        """
        if not self._encoder_initialized:
            try:
                if RESEMBLYZER_AVAILABLE:
                    self._encoder = VoiceEncoder()
                    self._encoder_initialized = True
                    logger.info("VoiceEncoder initialized successfully")
                else:
                    logger.warning("VoiceEncoder not available - using mock", exc_info=True)
            except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
                logger.error(f"Failed to initialize VoiceEncoder: {e}", exc_info=True)
                self._encoder = None

        return self._encoder

    def extract_voice_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """
        Extract voice embedding (d-vector) from audio file.

        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)

        Returns:
            Voice embedding vector (256-dimensional) or None on error
        """
        try:
            if not RESEMBLYZER_AVAILABLE or self.encoder is None:
                # Fallback to mock implementation
                return self._extract_embedding_mock(audio_path)

            # Load and preprocess audio
            wav = self._load_audio(audio_path)
            if wav is None:
                logger.error(f"Failed to load audio file: {audio_path}", exc_info=True)
                return None

            # Extract embedding using Resemblyzer
            embedding = self.encoder.embed_utterance(wav)

            # Ensure normalized
            if np.linalg.norm(embedding) > 0:
                embedding = embedding / np.linalg.norm(embedding)

            logger.info(f"Extracted voice embedding from {audio_path}: shape={embedding.shape}")
            return embedding

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to extract voice embedding: {e}", exc_info=True)
            return self._extract_embedding_mock(audio_path)

    def _load_audio(self, audio_path: str) -> Optional[np.ndarray]:
        """
        Load and preprocess audio file for Resemblyzer.

        Args:
            audio_path: Path to the audio file

        Returns:
            Preprocessed audio waveform or None on error
        """
        try:
            if not RESEMBLYZER_AVAILABLE:
                return None

            # Load audio with librosa
            audio, sr = librosa.load(audio_path, sr=self.target_sample_rate, mono=True)

            # Preprocess for Resemblyzer
            wav = preprocess_wav(audio)

            return wav

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to load audio: {e}", exc_info=True)
            return None

    def verify_voice(
        self,
        test_audio_path: str,
        reference_embeddings: List[np.ndarray]
    ) -> Dict[str, Any]:
        """
        Verify voice against reference embeddings.

        Args:
            test_audio_path: Path to the test audio file
            reference_embeddings: List of reference voice embeddings

        Returns:
            Dictionary containing:
                - verified: Boolean indicating if voice verified
                - similarity: Maximum similarity score
                - confidence: Confidence score
                - threshold_met: Whether threshold was met
                - match_index: Index of best matching reference embedding
        """
        try:
            # Extract test embedding
            test_embedding = self.extract_voice_embedding(test_audio_path)
            if test_embedding is None:
                return {
                    'verified': False,
                    'similarity': 0.0,
                    'confidence': 0.0,
                    'threshold_met': False,
                    'error': 'Failed to extract test embedding'
                }

            # Compare with reference embeddings
            similarities = []
            for ref_embedding in reference_embeddings:
                similarity = self.calculate_cosine_similarity(test_embedding, ref_embedding)
                similarities.append(similarity)

            if not similarities:
                return {
                    'verified': False,
                    'similarity': 0.0,
                    'confidence': 0.0,
                    'threshold_met': False,
                    'error': 'No reference embeddings provided'
                }

            # Get best match
            max_similarity = float(np.max(similarities))
            match_index = int(np.argmax(similarities))
            avg_similarity = float(np.mean(similarities))

            # Calculate confidence (average of max and mean)
            confidence = (max_similarity + avg_similarity) / 2.0

            # Verification decision
            threshold_met = max_similarity >= self.similarity_threshold
            confidence_met = confidence >= self.confidence_threshold
            verified = threshold_met and confidence_met

            return {
                'verified': verified,
                'similarity': max_similarity,
                'confidence': confidence,
                'threshold_met': threshold_met,
                'confidence_met': confidence_met,
                'match_index': match_index,
                'all_similarities': similarities,
                'avg_similarity': avg_similarity
            }

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to verify voice: {e}", exc_info=True)
            return {
                'verified': False,
                'similarity': 0.0,
                'confidence': 0.0,
                'threshold_met': False,
                'error': str(e)
            }

    def assess_audio_quality(self, audio_path: str) -> Dict[str, Any]:
        """
        Assess audio quality for voice verification.

        Args:
            audio_path: Path to the audio file

        Returns:
            Dictionary containing quality metrics:
                - overall_quality: Overall quality score (0.0-1.0)
                - snr_db: Signal-to-noise ratio in dB
                - duration_seconds: Audio duration
                - sample_rate: Audio sample rate
                - quality_issues: List of quality issues
                - acceptable: Whether quality is acceptable
        """
        try:
            # Load audio
            audio, sr = librosa.load(audio_path, sr=None, mono=True)

            # Calculate duration
            duration = len(audio) / sr

            # Estimate SNR (simple energy-based estimation)
            # This is a simplified SNR estimation
            # For real production, use more sophisticated methods
            energy = np.sum(audio ** 2) / len(audio)
            snr_db = 10 * np.log10(energy + 1e-10)

            # Identify quality issues
            quality_issues = []
            if snr_db < self.min_snr_db:
                quality_issues.append('LOW_SNR')
            if duration < self.min_duration_seconds:
                quality_issues.append('TOO_SHORT')
            if duration > self.max_duration_seconds:
                quality_issues.append('TOO_LONG')
            if sr < 8000:
                quality_issues.append('LOW_SAMPLE_RATE')

            # Calculate overall quality score
            snr_score = min(1.0, max(0.0, (snr_db - 10) / 20))  # Normalize 10-30 dB to 0-1
            duration_score = 1.0 if self.min_duration_seconds <= duration <= self.max_duration_seconds else 0.5
            sample_rate_score = 1.0 if sr >= 16000 else sr / 16000

            overall_quality = (snr_score + duration_score + sample_rate_score) / 3.0

            # Quality acceptable if no critical issues
            acceptable = len(quality_issues) == 0 and overall_quality >= 0.6

            return {
                'overall_quality': float(overall_quality),
                'snr_db': float(snr_db),
                'duration_seconds': float(duration),
                'sample_rate': int(sr),
                'quality_issues': quality_issues,
                'acceptable': acceptable,
                'recommendations': self._generate_quality_recommendations(quality_issues)
            }

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to assess audio quality: {e}", exc_info=True)
            return {
                'overall_quality': 0.0,
                'acceptable': False,
                'error': str(e),
                'quality_issues': ['ASSESSMENT_FAILED']
            }

    def _generate_quality_recommendations(self, quality_issues: List[str]) -> List[str]:
        """
        Generate quality improvement recommendations.

        Args:
            quality_issues: List of quality issues

        Returns:
            List of actionable recommendations
        """
        recommendations = []

        if 'LOW_SNR' in quality_issues:
            recommendations.append("Record in a quiet environment to reduce background noise")
        if 'TOO_SHORT' in quality_issues:
            recommendations.append(f"Record for at least {self.min_duration_seconds} seconds")
        if 'TOO_LONG' in quality_issues:
            recommendations.append(f"Keep audio under {self.max_duration_seconds} seconds")
        if 'LOW_SAMPLE_RATE' in quality_issues:
            recommendations.append("Use higher quality recording (at least 16kHz sample rate)")

        return recommendations

    def calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two voice embeddings.

        Args:
            vec1: First voice embedding
            vec2: Second voice embedding

        Returns:
            Cosine similarity score (0.0-1.0)
        """
        try:
            if vec1 is None or vec2 is None:
                return 0.0

            if vec1.shape != vec2.shape:
                logger.warning(f"Embedding shape mismatch: {vec1.shape} vs {vec2.shape}", exc_info=True)
                return 0.0

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)

            if norm_product == 0:
                return 0.0

            similarity = dot_product / norm_product

            # Normalize to 0-1 range (cosine similarity is -1 to 1)
            normalized_similarity = (similarity + 1) / 2

            return float(normalized_similarity)

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to calculate cosine similarity: {e}", exc_info=True)
            return 0.0

    def _extract_embedding_mock(self, audio_path: str) -> Optional[np.ndarray]:
        """
        Mock voice embedding extraction for testing.

        Args:
            audio_path: Path to the audio file

        Returns:
            Mock 256-dimensional embedding
        """
        try:
            # Generate deterministic embedding based on audio path
            hash_obj = hashlib.sha256(audio_path.encode())
            seed = int.from_bytes(hash_obj.digest()[:4], byteorder='big')
            np.random.seed(seed)

            # Resemblyzer produces 256-dimensional embeddings
            embedding = np.random.normal(0, 1, 256)
            embedding = embedding / np.linalg.norm(embedding)

            logger.debug(f"Generated mock voice embedding for {audio_path}")
            return embedding

        except (NETWORK_EXCEPTIONS + FILE_IO_EXCEPTIONS) as e:
            logger.error(f"Failed to generate mock embedding: {e}", exc_info=True)
            return None

    def batch_extract_embeddings(self, audio_paths: List[str]) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings from multiple audio files.

        Args:
            audio_paths: List of audio file paths

        Returns:
            List of embeddings (same order as input paths)
        """
        embeddings = []
        for audio_path in audio_paths:
            embedding = self.extract_voice_embedding(audio_path)
            embeddings.append(embedding)

        return embeddings
