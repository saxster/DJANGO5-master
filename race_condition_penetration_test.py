#!/usr/bin/env python
"""
Race Condition Penetration Test Script

Simulates real-world concurrent attack scenarios to validate
that race condition fixes are effective.

Usage:
    python race_condition_penetration_test.py --scenario all
    python race_condition_penetration_test.py --scenario attendance
    python race_condition_penetration_test.py --scenario counters
    python race_condition_penetration_test.py --scenario embeddings

Requirements:
    - Django environment must be configured
    - Redis must be running
    - Database must be accessible
"""

import os
import sys
import django
import argparse
import time
import threading
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from apps.attendance.models import PeopleEventlog
from apps.face_recognition.models import (
    FaceRecognitionModel,
    FaceEmbedding,
    FaceVerificationLog
)
from apps.onboarding.models import Bt, Shift, TypeAssist

User = get_user_model()


class PenetrationTestResults:
    """Track and report penetration test results"""

    def __init__(self):
        self.results = defaultdict(lambda: {
            'passed': 0,
            'failed': 0,
            'errors': [],
            'duration_ms': 0
        })

    def add_result(self, scenario: str, passed: bool, error: str = None, duration_ms: float = 0):
        """Add test result"""
        if passed:
            self.results[scenario]['passed'] += 1
        else:
            self.results[scenario]['failed'] += 1
            if error:
                self.results[scenario]['errors'].append(error)

        self.results[scenario]['duration_ms'] += duration_ms

    def print_report(self):
        """Print comprehensive test report"""
        print("\n" + "=" * 80)
        print("RACE CONDITION PENETRATION TEST REPORT")
        print("=" * 80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        total_passed = 0
        total_failed = 0

        for scenario, data in sorted(self.results.items()):
            total_passed += data['passed']
            total_failed += data['failed']

            status = "PASS" if data['failed'] == 0 else "FAIL"
            status_symbol = "✓" if status == "PASS" else "✗"

            print(f"{status_symbol} {scenario}")
            print(f"   Passed: {data['passed']}")
            print(f"   Failed: {data['failed']}")
            print(f"   Avg Duration: {data['duration_ms'] / max(data['passed'] + data['failed'], 1):.2f}ms")

            if data['errors']:
                print(f"   Errors:")
                for error in data['errors'][:5]:  # Show first 5 errors
                    print(f"     - {error}")
            print()

        print("-" * 80)
        print(f"TOTAL: {total_passed} passed, {total_failed} failed")

        if total_failed == 0:
            print("\n🎉 ALL TESTS PASSED - System is secure against race conditions")
        else:
            print(f"\n⚠️  {total_failed} TESTS FAILED - Race conditions detected!")

        print("=" * 80)

        return total_failed == 0


class AttendanceRaceConditionTests:
    """Test race conditions in attendance verification updates"""

    def __init__(self, results: PenetrationTestResults):
        self.results = results
        self.setup_test_data()

    def setup_test_data(self):
        """Set up test environment"""
        self.user = User.objects.get_or_create(
            username='race_test_user',
            defaults={
                'peoplename': 'Race Test User',
                'peoplecode': 'RACE001',
                'email': 'race@test.com'
            }
        )[0]

        self.client_bt = Bt.objects.get_or_create(
            bucode='RACE_CLIENT',
            defaults={'buname': 'Race Test Client', 'btype': 'C'}
        )[0]

        self.site_bt = Bt.objects.get_or_create(
            bucode='RACE_SITE',
            defaults={'buname': 'Race Test Site', 'btype': 'S'}
        )[0]

        self.shift = Shift.objects.get_or_create(
            shiftname='Race Test Shift',
            client=self.client_bt,
            bu=self.site_bt
        )[0]

        self.event_type = TypeAssist.objects.get_or_create(
            tacode='SELF',
            defaults={'taname': 'Self Attendance'}
        )[0]

    def create_attendance(self):
        """Create test attendance record"""
        return PeopleEventlog.objects.create(
            uuid=uuid.uuid4(),
            people=self.user,
            client=self.client_bt,
            bu=self.site_bt,
            shift=self.shift,
            peventtype=self.event_type,
            punchintime=timezone.now(),
            datefor=timezone.now().date(),
            peventlogextras={
                "verified_in": False,
                "distance_in": None,
                "verified_out": False,
                "distance_out": None
            }
        )

    def test_concurrent_verification_updates(self, num_threads: int = 50):
        """
        Simulate 50 concurrent verification updates to detect data loss

        Attack Scenario: Attacker sends multiple concurrent verification
        requests to corrupt or bypass face recognition data.
        """
        print(f"  → Testing {num_threads} concurrent verification updates...")

        attendance = self.create_attendance()
        errors = []
        success_count = [0]
        lock_failures = [0]

        def attack_update(thread_id):
            try:
                start = time.time()

                # Alternate between punch-in and punch-out
                if thread_id % 2 == 0:
                    result = {"verified": True, "distance": 0.2}
                else:
                    # Update punchouttime first
                    att = PeopleEventlog.objects.get(pk=attendance.pk)
                    att.punchouttime = timezone.now()
                    att.save(update_fields=['punchouttime'])

                    time.sleep(0.001)  # Tiny delay for overlap
                    result = {"verified": True, "distance": 0.3}

                success = PeopleEventlog.objects.update_fr_results(
                    result, str(attendance.uuid), attendance.people_id, 'default'
                )

                duration = (time.time() - start) * 1000

                if success:
                    success_count[0] += 1
                else:
                    errors.append(f"Update failed for thread {thread_id}")

            except Exception as e:
                if "lock" in str(e).lower() or "timeout" in str(e).lower():
                    lock_failures[0] += 1
                else:
                    errors.append(f"Thread {thread_id}: {str(e)}")

        threads = [threading.Thread(target=attack_update, args=(i,)) for i in range(num_threads)]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_duration = (time.time() - start_time) * 1000

        # Verify data integrity
        attendance.refresh_from_db()
        extras = attendance.peventlogextras

        data_intact = (
            extras.get("verified_in") is not None and
            extras.get("verified_out") is not None and
            (extras.get("distance_in") is not None or extras.get("distance_out") is not None)
        )

        passed = len(errors) == 0 and data_intact

        error_msg = None if passed else f"Errors: {errors[:3]}, Data intact: {data_intact}"

        self.results.add_result(
            f"Attendance: {num_threads} concurrent updates",
            passed,
            error_msg,
            total_duration
        )

        if passed:
            print(f"    ✓ Data integrity maintained")
            print(f"    ✓ {success_count[0]}/{num_threads} updates succeeded")
            if lock_failures[0] > 0:
                print(f"    ℹ {lock_failures[0]} lock contentions (expected)")
        else:
            print(f"    ✗ Data corruption detected!")
            print(f"    ✗ Extras: {extras}")

    def test_rapid_fire_updates(self, duration_seconds: int = 5):
        """
        Rapid-fire updates for sustained period

        Attack Scenario: DoS attack with rapid concurrent requests
        """
        print(f"  → Testing rapid-fire updates for {duration_seconds}s...")

        attendance = self.create_attendance()
        errors = []
        update_count = [0]
        stop_flag = [False]

        def rapid_attacker(attacker_id):
            while not stop_flag[0]:
                try:
                    result = {"verified": True, "distance": 0.2 + (attacker_id * 0.01)}
                    PeopleEventlog.objects.update_fr_results(
                        result, str(attendance.uuid), attendance.people_id, 'default'
                    )
                    update_count[0] += 1
                    time.sleep(0.01)  # 100 updates/second per attacker
                except Exception as e:
                    if "lock" not in str(e).lower():
                        errors.append(str(e))

        start_time = time.time()

        # 5 concurrent attackers
        threads = [threading.Thread(target=rapid_attacker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()

        # Let it run for specified duration
        time.sleep(duration_seconds)
        stop_flag[0] = True

        for t in threads:
            t.join()

        total_duration = (time.time() - start_time) * 1000

        # Verify final state
        attendance.refresh_from_db()
        extras = attendance.peventlogextras

        data_intact = extras.get("verified_in") is not None

        passed = len(errors) == 0 and data_intact

        self.results.add_result(
            "Attendance: Rapid-fire DoS simulation",
            passed,
            f"Errors: {errors[:3]}" if errors else None,
            total_duration
        )

        if passed:
            print(f"    ✓ System survived {update_count[0]} rapid updates")
            print(f"    ✓ Data integrity maintained")
        else:
            print(f"    ✗ System failed under load!")

    def run_all(self):
        """Run all attendance race condition tests"""
        print("\n[Attendance Race Condition Tests]")
        self.test_concurrent_verification_updates(num_threads=20)
        self.test_concurrent_verification_updates(num_threads=50)
        self.test_rapid_fire_updates(duration_seconds=3)


class CounterRaceConditionTests:
    """Test race conditions in counter updates"""

    def __init__(self, results: PenetrationTestResults):
        self.results = results
        self.setup_test_data()

    def setup_test_data(self):
        """Set up test environment"""
        self.user = User.objects.get_or_create(
            username='counter_test_user',
            defaults={
                'peoplename': 'Counter Test User',
                'peoplecode': 'COUNTER001'
            }
        )[0]

        self.model = FaceRecognitionModel.objects.get_or_create(
            name='RaceTestModel',
            defaults={
                'model_type': 'FACENET512',
                'version': '1.0',
                'similarity_threshold': 0.3,
                'confidence_threshold': 0.7
            }
        )[0]

    def test_counter_accuracy(self, num_verifications: int = 100):
        """
        Test counter accuracy under concurrent load

        Attack Scenario: Exploit counter race conditions to bypass
        rate limiting or usage tracking.
        """
        print(f"  → Testing counter accuracy with {num_verifications} concurrent updates...")

        # Reset counters
        self.model.verification_count = 0
        self.model.successful_verifications = 0
        self.model.save()

        initial_count = self.model.verification_count
        errors = []

        def create_verification(is_success):
            try:
                FaceVerificationLog.objects.create(
                    user=self.user,
                    verification_model=self.model,
                    result='SUCCESS' if is_success else 'FAILED',
                    similarity_score=0.8 if is_success else 0.4,
                    processing_time_ms=100
                )
            except Exception as e:
                errors.append(str(e))

        start_time = time.time()

        threads = []
        for i in range(num_verifications):
            is_success = i % 2 == 0
            t = threading.Thread(target=create_verification, args=(is_success,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_duration = (time.time() - start_time) * 1000

        # Verify accuracy
        self.model.refresh_from_db()

        expected_total = initial_count + num_verifications
        expected_success = num_verifications // 2

        counter_accurate = self.model.verification_count == expected_total
        success_counter_accurate = self.model.successful_verifications == expected_success

        passed = counter_accurate and success_counter_accurate and len(errors) == 0

        error_msg = None
        if not passed:
            error_msg = f"Total: {self.model.verification_count}/{expected_total}, Success: {self.model.successful_verifications}/{expected_success}"

        self.results.add_result(
            f"Counters: {num_verifications} concurrent updates",
            passed,
            error_msg,
            total_duration
        )

        if passed:
            print(f"    ✓ Counters accurate: {self.model.verification_count}/{expected_total}")
        else:
            print(f"    ✗ Counter corruption detected!")
            print(f"    ✗ Expected: {expected_total} total, {expected_success} success")
            print(f"    ✗ Got: {self.model.verification_count} total, {self.model.successful_verifications} success")

    def run_all(self):
        """Run all counter race condition tests"""
        print("\n[Counter Race Condition Tests]")
        self.test_counter_accuracy(num_verifications=50)
        self.test_counter_accuracy(num_verifications=100)


class EmbeddingRaceConditionTests:
    """Test race conditions in embedding management"""

    def __init__(self, results: PenetrationTestResults):
        self.results = results
        self.setup_test_data()

    def setup_test_data(self):
        """Set up test environment"""
        self.model = FaceRecognitionModel.objects.get_or_create(
            name='EmbeddingTestModel',
            defaults={
                'model_type': 'FACENET512',
                'version': '1.0'
            }
        )[0]

    def test_primary_embedding_uniqueness(self, num_attempts: int = 30):
        """
        Test primary embedding uniqueness constraint

        Attack Scenario: Create multiple primary embeddings to
        bypass authentication or impersonate users.
        """
        print(f"  → Testing primary embedding uniqueness with {num_attempts} concurrent creates...")

        # Create unique user for this test
        test_user = User.objects.create(
            username=f'embed_test_{uuid.uuid4().hex[:8]}',
            peoplename='Embedding Test User',
            peoplecode=f'EMBED{uuid.uuid4().hex[:6]}'
        )

        errors = []
        created_count = [0]

        def create_embedding():
            try:
                FaceEmbedding.objects.create(
                    user=test_user,
                    extraction_model=self.model,
                    embedding_vector=[0.1 + (i * 0.001) for i in range(512)],
                    face_confidence=0.9,
                    is_validated=True
                )
                created_count[0] += 1
            except Exception as e:
                # Some may fail due to race - that's ok
                if "integrity" not in str(e).lower() and "unique" not in str(e).lower():
                    errors.append(str(e))

        start_time = time.time()

        threads = [threading.Thread(target=create_embedding) for _ in range(num_attempts)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_duration = (time.time() - start_time) * 1000

        # Verify only ONE primary exists
        primary_count = FaceEmbedding.objects.filter(
            user=test_user,
            extraction_model__model_type=self.model.model_type,
            is_primary=True
        ).count()

        passed = primary_count == 1 and len(errors) == 0

        error_msg = None if passed else f"Primary count: {primary_count}, Errors: {errors[:3]}"

        self.results.add_result(
            f"Embeddings: Primary uniqueness ({num_attempts} attempts)",
            passed,
            error_msg,
            total_duration
        )

        if passed:
            print(f"    ✓ Only 1 primary embedding exists (out of {created_count[0]} created)")
        else:
            print(f"    ✗ Multiple primary embeddings detected: {primary_count}")

        # Cleanup
        test_user.delete()

    def run_all(self):
        """Run all embedding race condition tests"""
        print("\n[Embedding Race Condition Tests]")
        self.test_primary_embedding_uniqueness(num_attempts=20)
        self.test_primary_embedding_uniqueness(num_attempts=50)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Race Condition Penetration Tests')
    parser.add_argument(
        '--scenario',
        choices=['all', 'attendance', 'counters', 'embeddings'],
        default='all',
        help='Test scenario to run'
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("RACE CONDITION PENETRATION TESTING")
    print("=" * 80)
    print(f"Scenario: {args.scenario}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = PenetrationTestResults()

    try:
        if args.scenario in ['all', 'attendance']:
            AttendanceRaceConditionTests(results).run_all()

        if args.scenario in ['all', 'counters']:
            CounterRaceConditionTests(results).run_all()

        if args.scenario in ['all', 'embeddings']:
            EmbeddingRaceConditionTests(results).run_all()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n\n✗ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print final report
    all_passed = results.print_report()

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()