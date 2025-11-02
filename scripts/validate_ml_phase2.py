#!/usr/bin/env python
"""
ML Phase 2 Implementation Validator

Validates all Phase 2 components are correctly implemented.

Usage:
    python scripts/validate_ml_phase2.py
"""

import os
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


def check_file(filepath, description):
    """Check if file exists."""
    exists = os.path.exists(filepath)
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    print(f"  {status} {description}")
    print(f"      {filepath}")
    return exists


def validate_implementation():
    """Validate all Phase 2 implementation files."""
    print(f"\n{BOLD}ML Phase 2 Implementation Validator{RESET}")
    print("=" * 70)

    base_dir = Path(__file__).parent.parent
    all_checks_passed = True

    # 1. Data Extraction Service
    print(f"\n{BOLD}Task 1: Data Extraction Service{RESET}")
    checks = [
        check_file(
            base_dir / "apps/ml/services/data_extractors/__init__.py",
            "Data extractors package init"
        ),
        check_file(
            base_dir / "apps/ml/services/data_extractors/conflict_data_extractor.py",
            "ConflictDataExtractor service"
        ),
    ]
    all_checks_passed &= all(checks)

    # 2. Model Training Service
    print(f"\n{BOLD}Task 2: Model Training Service{RESET}")
    checks = [
        check_file(
            base_dir / "apps/ml/services/training/__init__.py",
            "Training package init"
        ),
        check_file(
            base_dir / "apps/ml/services/training/conflict_model_trainer.py",
            "ConflictModelTrainer service"
        ),
    ]
    all_checks_passed &= all(checks)

    # 3. Management Commands
    print(f"\n{BOLD}Task 3: Management Commands{RESET}")
    checks = [
        check_file(
            base_dir / "apps/ml/management/commands/extract_conflict_training_data.py",
            "Extract training data command"
        ),
        check_file(
            base_dir / "apps/ml/management/commands/train_conflict_model.py",
            "Train model command"
        ),
    ]
    all_checks_passed &= all(checks)

    # 4. Refactored ConflictPredictor
    print(f"\n{BOLD}Task 4: Refactored ConflictPredictor{RESET}")
    predictor_file = base_dir / "apps/ml/services/conflict_predictor.py"
    checks = [check_file(predictor_file, "ConflictPredictor service")]

    if checks[0]:
        # Check for key methods
        with open(predictor_file, 'r') as f:
            content = f.read()
            methods_to_check = [
                ('_load_model', 'Model loading method'),
                ('clear_model_cache', 'Cache clearing method'),
                ('_model_cache', 'Class-level model cache'),
            ]
            for method_name, description in methods_to_check:
                exists = method_name in content
                status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
                print(f"  {status} {description} ({method_name})")
                checks.append(exists)

    all_checks_passed &= all(checks)

    # 5. Updated ML Models
    print(f"\n{BOLD}Task 5: Updated ML Models{RESET}")
    models_file = base_dir / "apps/ml/models/ml_models.py"
    checks = [check_file(models_file, "ML models file")]

    if checks[0]:
        with open(models_file, 'r') as f:
            content = f.read()
            features_to_check = [
                ('model_type', 'PredictionLog.model_type field'),
                ('features_json', 'PredictionLog.features_json field'),
                ('def activate', 'ConflictPredictionModel.activate method'),
            ]
            for feature_name, description in features_to_check:
                exists = feature_name in content
                status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
                print(f"  {status} {description}")
                checks.append(exists)

    all_checks_passed &= all(checks)

    # 6. Celery Tasks
    print(f"\n{BOLD}Task 6 & 7: Celery Tasks{RESET}")
    tasks_file = base_dir / "apps/ml/tasks.py"
    checks = [check_file(tasks_file, "ML tasks file")]

    if checks[0]:
        with open(tasks_file, 'r') as f:
            content = f.read()
            tasks_to_check = [
                ('track_conflict_prediction_outcomes_task', 'Outcome tracking task'),
                ('retrain_conflict_model_weekly_task', 'Weekly retraining task'),
                ('_cleanup_old_training_data', 'Cleanup helper function'),
            ]
            for task_name, description in tasks_to_check:
                exists = task_name in content
                status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
                print(f"  {status} {description}")
                checks.append(exists)

    all_checks_passed &= all(checks)

    # 7. Celery Beat Schedule
    print(f"\n{BOLD}Task 7: Celery Beat Schedule{RESET}")
    celery_file = base_dir / "intelliwiz_config/celery.py"
    checks = [check_file(celery_file, "Celery config file")]

    if checks[0]:
        with open(celery_file, 'r') as f:
            content = f.read()
            schedules_to_check = [
                ('ml_track_conflict_prediction_outcomes', 'Outcome tracking schedule'),
                ('ml_retrain_conflict_model_weekly', 'Weekly retraining schedule'),
            ]
            for schedule_name, description in schedules_to_check:
                exists = schedule_name in content
                status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
                print(f"  {status} {description}")
                checks.append(exists)

    all_checks_passed &= all(checks)

    # 8. Django Admin
    print(f"\n{BOLD}Task 8: Django Admin{RESET}")
    admin_file = base_dir / "apps/ml/admin.py"
    checks = [check_file(admin_file, "ML admin file")]

    if checks[0]:
        with open(admin_file, 'r') as f:
            content = f.read()
            admin_classes = [
                ('ConflictPredictionModelAdmin', 'Model admin class'),
                ('PredictionLogAdmin', 'Prediction log admin class'),
                ('activate_model', 'Activate model action'),
            ]
            for class_name, description in admin_classes:
                exists = class_name in content
                status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
                print(f"  {status} {description}")
                checks.append(exists)

    all_checks_passed &= all(checks)

    # Documentation
    print(f"\n{BOLD}Documentation{RESET}")
    checks = [
        check_file(
            base_dir / "ML_PHASE2_IMPLEMENTATION_COMPLETE.md",
            "Implementation summary"
        ),
        check_file(
            base_dir / "PREDICTION_LOGGING_INTEGRATION.md",
            "Integration guide"
        ),
    ]
    all_checks_passed &= all(checks)

    # Summary
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    if all_checks_passed:
        print(f"{GREEN}{BOLD}✓ All Phase 2 components validated successfully!{RESET}")
        print(f"\n{BOLD}Next Steps:{RESET}")
        print("  1. Run database migration: python manage.py migrate ml")
        print("  2. Create media directories: mkdir -p media/ml_training_data media/ml_models")
        print("  3. Test with synthetic data (see ML_PHASE2_IMPLEMENTATION_COMPLETE.md)")
        print("  4. Create SyncLog models (see Known Limitations section)")
        print(f"\n{BOLD}Documentation:{RESET}")
        print("  - Implementation details: ML_PHASE2_IMPLEMENTATION_COMPLETE.md")
        print("  - Integration guide: PREDICTION_LOGGING_INTEGRATION.md")
        return 0
    else:
        print(f"{RED}{BOLD}✗ Some components are missing or incomplete{RESET}")
        print(f"\n{YELLOW}Please review the output above for missing files.{RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(validate_implementation())
