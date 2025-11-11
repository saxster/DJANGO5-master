"""
Face Recognition Services Module (Sprint 1.4-1.5 - God Class Refactoring)

This module provides modular AI-enhanced face recognition services
split from monolithic ai_enhanced_engine.py and enhanced_engine.py files.

Services:
    - DeepfakeDetectionService: Ensemble deepfake detection
    - LivenessDetectionService: Comprehensive liveness detection
    - MultiModalFusionService: Multi-modal decision fusion
    - ImageQualityAssessmentService: Image quality assessment
    - AntiSpoofingService: Anti-spoofing detection
    - FraudRiskAssessmentService: Fraud risk assessment
    - EnsembleVerificationService: Multi-model ensemble verification

All services maintain backward compatibility with the original implementation.
"""

# Sprint 1.4 - ai_enhanced_engine.py splits
from .deepfake_detection import (
    DeepfakeDetectionService,
    DeeperForensicsModel,
    FaceForensicsPlusPlusModel,
    CelebDFModel,
    DFDCModel,
    FaceSwapperDetectionModel
)

from .face_liveness_detection import (
    LivenessDetectionService,
    ThreeDLivenessModel,
    MicroExpressionModel,
    HeartRateDetectionModel,
    ChallengeResponseModel,
    PassiveLivenessModel
)

from .multi_modal_fusion import (
    MultiModalFusionService
)

# Sprint 1.5 - enhanced_engine.py splits
from .quality_assessment import (
    ImageQualityAssessmentService
)

from .anti_spoofing import (
    AntiSpoofingService,
    TextureBasedAntiSpoofingModel,
    MotionBasedAntiSpoofingModel,
    MockAntiSpoofingModel,  # Backward compatibility alias
    MockMotionAntiSpoofingModel  # Backward compatibility alias
)

from .fraud_risk_assessment import (
    FraudRiskAssessmentService
)

from .ensemble_verification import (
    EnsembleVerificationService,
    FaceNetModel,
    ArcFaceModel,
    InsightFaceModel,
    MockFaceNetModel,  # Backward compatibility alias
    MockArcFaceModel,  # Backward compatibility alias
    MockInsightFaceModel  # Backward compatibility alias
)

# Sprint 5 - Advanced features
from .challenge_response_service import (
    ChallengeResponseService
)

from .photo_authentication_service import (
    BiometricPhotoAuthenticationService
)

from .performance_optimization import (
    BiometricPerformanceOptimizer
)

from .unified import (
    get_face_recognition_service,
    VerificationEngine,
    VerificationResult,
    UnifiedFaceRecognitionService,
    verify_face,
    assess_image_quality,
)

__all__ = [
    # Services (Sprint 1.4 - ai_enhanced_engine.py)
    'DeepfakeDetectionService',
    'LivenessDetectionService',
    'MultiModalFusionService',

    # Services (Sprint 1.5 - enhanced_engine.py)
    'ImageQualityAssessmentService',
    'AntiSpoofingService',
    'FraudRiskAssessmentService',
    'EnsembleVerificationService',

    # Services (Sprint 5 - Advanced features)
    'ChallengeResponseService',
    'BiometricPhotoAuthenticationService',
    'BiometricPerformanceOptimizer',

    # Main service exports (from services.py - lazy loaded)
    'get_face_recognition_service',
    'VerificationEngine',
    'VerificationResult',
    'UnifiedFaceRecognitionService',
    'verify_face',
    'assess_image_quality',

    # Deepfake Models
    'DeeperForensicsModel',
    'FaceForensicsPlusPlusModel',
    'CelebDFModel',
    'DFDCModel',
    'FaceSwapperDetectionModel',

    # Liveness Models
    'ThreeDLivenessModel',
    'MicroExpressionModel',
    'HeartRateDetectionModel',
    'ChallengeResponseModel',
    'PassiveLivenessModel',

    # Anti-Spoofing Models (Sprint 5 - Real implementations)
    'TextureBasedAntiSpoofingModel',
    'MotionBasedAntiSpoofingModel',
    'MockAntiSpoofingModel',  # Backward compatibility
    'MockMotionAntiSpoofingModel',  # Backward compatibility

    # Face Recognition Models (Sprint 2 - Real implementations)
    'FaceNetModel',
    'ArcFaceModel',
    'InsightFaceModel',
    'MockFaceNetModel',  # Backward compatibility
    'MockArcFaceModel',  # Backward compatibility
    'MockInsightFaceModel',  # Backward compatibility
]
