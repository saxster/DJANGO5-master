"""
Management command to train fraud detection baselines.

Trains behavioral baselines for all employees or specific employee.

Usage:
    python manage.py train_fraud_baselines [--employee-id=123] [--force-retrain]

Options:
    --employee-id: Train specific employee only
    --force-retrain: Force retrain even if baseline exists and is recent
    --all-employees: Train all employees (default)
    --min-records: Minimum records required for training (default: 30)
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.attendance.services.fraud_detection_orchestrator import FraudDetectionOrchestrator
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Train fraud detection baselines for employees'

    def add_arguments(self, parser):
        parser.add_argument(
            '--employee-id',
            type=int,
            help='Train specific employee only'
        )
        parser.add_argument(
            '--force-retrain',
            action='store_true',
            help='Force retrain even if baseline exists'
        )
        parser.add_argument(
            '--all-employees',
            action='store_true',
            default=True,
            help='Train all employees (default)'
        )
        parser.add_argument(
            '--min-records',
            type=int,
            default=30,
            help='Minimum attendance records required for training'
        )

    def handle(self, *args, **options):
        employee_id = options.get('employee_id')
        force_retrain = options['force_retrain']
        min_records = options['min_records']

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Fraud Detection Baseline Training'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if employee_id:
            # Train single employee
            self._train_single_employee(employee_id, force_retrain)
        else:
            # Train all employees
            self._train_all_employees(force_retrain, min_records)

    def _train_single_employee(self, employee_id: int, force_retrain: bool):
        """Train baseline for a single employee"""
        try:
            employee = User.objects.get(id=employee_id)

            self.stdout.write(f"\nTraining baseline for: {employee.username} (ID: {employee_id})")

            orchestrator = FraudDetectionOrchestrator(employee)
            success = orchestrator.train_employee_baseline(force_retrain=force_retrain)

            if success:
                profile = UserBehaviorProfile.objects.get(employee=employee)
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Baseline trained successfully"
                ))
                self.stdout.write(f"  - Training records: {profile.training_records_count}")
                self.stdout.write(f"  - Typical check-in: {profile.typical_checkin_hour}:{profile.typical_checkin_minute:02d}")
                self.stdout.write(f"  - Typical locations: {len(profile.typical_locations or [])}")
                self.stdout.write(f"  - Typical devices: {len(profile.typical_devices or [])}")
            else:
                self.stdout.write(self.style.WARNING(
                    f"⚠ Insufficient data (need 30+ attendance records)"
                ))

        except User.DoesNotExist:
            raise CommandError(f"Employee with ID {employee_id} not found")
        except DATABASE_EXCEPTIONS as e:
            self.stdout.write(self.style.ERROR(f"✗ Training failed: {e}"))
            raise

    def _train_all_employees(self, force_retrain: bool, min_records: int):
        """Train baselines for all employees"""
        self.stdout.write("\nTraining baselines for all employees...")
        self.stdout.write(f"Minimum records required: {min_records}")
        self.stdout.write(f"Force retrain: {force_retrain}\n")

        result = FraudDetectionOrchestrator.train_all_baselines(force_retrain=force_retrain)

        # Print summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Training Complete"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Trained: {result['trained']}")
        self.stdout.write(f"  Insufficient data: {result['insufficient_data']}")
        self.stdout.write(f"  Failed: {result['failed']}")
        self.stdout.write(f"  Total: {result['total']}")

        success_rate = (result['trained'] / result['total'] * 100) if result['total'] > 0 else 0
        self.stdout.write(f"\n  Success rate: {success_rate:.1f}%")

        if result['trained'] > 0:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully trained {result['trained']} employee baselines"))
        if result['insufficient_data'] > 0:
            self.stdout.write(self.style.WARNING(
                f"\n⚠ {result['insufficient_data']} employees have insufficient data (<{min_records} records)"
            ))
        if result['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"\n✗ {result['failed']} employees failed to train"))
