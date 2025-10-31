# Face Recognition Test Suite

Comprehensive test suite for biometric authentication features.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── test_models/                # Model tests
├── test_services/              # Service layer tests
│   ├── test_quality_assessment.py
│   ├── test_anti_spoofing.py
│   ├── test_fraud_risk_assessment.py
│   ├── test_deepfake_detection.py
│   ├── test_multi_modal_fusion.py
│   └── test_ensemble_verification.py
├── test_api/                   # REST API endpoint tests (Sprint 2)
├── test_integration/           # Integration tests (Sprint 2)
└── fixtures/                   # Test data and sample files
    └── sample_faces/           # Sample face images
```

## Running Tests

### All Tests
```bash
python -m pytest apps/face_recognition/tests/ -v
```

### With Coverage
```bash
python -m pytest apps/face_recognition/tests/ --cov=apps.face_recognition --cov-report=html -v
```

### Service Tests Only
```bash
python -m pytest apps/face_recognition/tests/test_services/ -v
```

### Specific Test File
```bash
python -m pytest apps/face_recognition/tests/test_services/test_quality_assessment.py -v
```

### Specific Test Method
```bash
python -m pytest apps/face_recognition/tests/test_services/test_quality_assessment.py::TestImageQualityAssessmentService::test_service_initialization -v
```

## Test Coverage Goals

- **Sprint 1:** 80% coverage for service layer
- **Sprint 2:** 80% coverage for API endpoints
- **Sprint 3:** 100% coverage for critical paths

## Fixtures

### Shared Fixtures (conftest.py)
- `sample_user` - Test user instance
- `sample_face_embedding` - Test face embedding
- `face_recognition_config` - Test configuration
- `sample_image_path` - Sample image file path
- `mock_verification_result` - Mock verification data
- `mock_modality_results` - Mock multi-modal data
- `mock_security_analysis` - Mock security data
- `mock_quality_metrics` - Mock quality data

## Test Categories

### Unit Tests (test_services/)
Test individual service methods in isolation.

### API Tests (test_api/ - Sprint 2)
Test REST API endpoints with DRF test client.

### Integration Tests (test_integration/ - Sprint 2)
Test full verification flows end-to-end.

### Security Tests (Sprint 2)
Test tenant isolation and GDPR/BIPA compliance.

## Current Status

✅ **Sprint 1:** Service layer tests (6 test files)
⏳ **Sprint 2:** API endpoint tests (pending)
⏳ **Sprint 2:** Integration tests (pending)
⏳ **Sprint 6:** Security tests (pending)
