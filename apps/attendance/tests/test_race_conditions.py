"""
import logging
logger = logging.getLogger(__name__)
Comprehensive race condition tests for attendance system

Tests verify that concurrent operations do not corrupt data or lose updates.
"""

import pytest
import threading
import time
import uuid as uuid_module
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.attendance.models import PeopleEventlog
from apps.face_recognition.models import (
    FaceRecognitionModel,
    FaceEmbedding,
    FaceVerificationLog
)
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestAttendanceRaceConditions(TransactionTestCase):
    """Test race conditions in attendance verification updates"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001',
            email='test@example.com'
        )

        self.client_bt = Bt.objects.create(
            bucode='CLIENT01',
            buname='Test Client',
            btype='C'
        )

        self.site_bt = Bt.objects.create(
            bucode='SITE01',
            buname='Test Site',
            btype='S'
        )

        self.shift = Shift.objects.create(
            shiftname='Day Shift',
            client=self.client_bt,
            bu=self.site_bt
        )

        self.event_type = TypeAssist.objects.create(
            tacode='SELF',
            taname='Self Attendance'
        )

    def create_test_attendance(self):
        """Create a test attendance record"""
        attendance = PeopleEventlog.objects.create(
            uuid=uuid_module.uuid4(),
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
        return attendance

    def test_concurrent_punchin_punchout_updates(self):
        """
        Test that concurrent punch-in and punch-out verification updates
        do not overwrite each other.

        This is the critical race condition: two threads updating
        peventlogextras JSON field simultaneously.
        """
        attendance = self.create_test_attendance()
        errors = []

        def update_punch_in():
            try:
                result = {"verified": True, "distance": 0.2}
                success = PeopleEventlog.objects.update_fr_results(
                    result, str(attendance.uuid), attendance.people_id, 'default'
                )
                assert success, "Punch-in update failed"
            except (AssertionError, AttributeError, KeyError) as e:
                errors.append(('punch_in', e))

        def update_punch_out():
            try:
                time.sleep(0.05)  # Slight delay to ensure overlap
                attendance.punchouttime = timezone.now()
                attendance.save(update_fields=['punchouttime'])

                result = {"verified": True, "distance": 0.3}
                success = PeopleEventlog.objects.update_fr_results(
                    result, str(attendance.uuid), attendance.people_id, 'default'
                )
                assert success, "Punch-out update failed"
            except (AssertionError, AttributeError, KeyError) as e:
                errors.append(('punch_out', e))

        # Run updates concurrently
        t1 = threading.Thread(target=update_punch_in)
        t2 = threading.Thread(target=update_punch_out)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check for errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify both updates are present
        attendance.refresh_from_db()
        extras = attendance.peventlogextras

        self.assertTrue(extras["verified_in"], "Punch-in verification lost")
        self.assertEqual(extras["distance_in"], 0.2, "Punch-in distance lost")
        self.assertTrue(extras["verified_out"], "Punch-out verification lost")
        self.assertEqual(extras["distance_out"], 0.3, "Punch-out distance lost")

    def test_rapid_concurrent_updates(self):
        """Test 10 rapid concurrent updates to same attendance record"""
        attendance = self.create_test_attendance()
        num_threads = 10
        errors = []

        def rapid_update(iteration):
            try:
                if iteration % 2 == 0:
                    result = {"verified": True, "distance": 0.2}
                    PeopleEventlog.objects.update_fr_results(
                        result, str(attendance.uuid), attendance.people_id, 'default'
                    )
                else:
                    time.sleep(0.01)
                    attendance_obj = PeopleEventlog.objects.get(pk=attendance.pk)
                    attendance_obj.punchouttime = timezone.now()
                    attendance_obj.save(update_fields=['punchouttime'])

                    result = {"verified": True, "distance": 0.3}
                    PeopleEventlog.objects.update_fr_results(
                        result, str(attendance.uuid), attendance.people_id, 'default'
                    )
            except (AttributeError, KeyError, ValueError) as e:
                errors.append((iteration, e))

        threads = [threading.Thread(target=rapid_update, args=(i,)) for i in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors in rapid updates: {errors}")

        # Verify data integrity
        attendance.refresh_from_db()
        extras = attendance.peventlogextras

        # Both should be set (last updates win)
        self.assertTrue(extras["verified_in"], "Punch-in verification lost")
        self.assertTrue(extras["verified_out"], "Punch-out verification lost")

    def test_lock_timeout_handling(self):
        """Test that lock timeouts are handled gracefully"""
        from apps.core.utils_new.distributed_locks import distributed_lock, LockTimeoutError

        attendance = self.create_test_attendance()

        # Acquire lock and hold it
        with distributed_lock(f"attendance_update:{attendance.uuid}", timeout=30):
            # Try to update from another thread (should timeout)
            error_caught = []

            def attempt_update():
                try:
                    result = {"verified": True, "distance": 0.2}
                    PeopleEventlog.objects.update_fr_results(
                        result, str(attendance.uuid), attendance.people_id, 'default'
                    )
                except LockTimeoutError:
                    error_caught.append(True)
                except (AttributeError, KeyError, ValueError) as e:
                    error_caught.append(e)

            t = threading.Thread(target=attempt_update)
            t.start()
            t.join(timeout=15)  # Wait for thread

            # Should have caught timeout error
            self.assertTrue(len(error_caught) > 0, "Lock timeout not detected")


@pytest.mark.django_db(transaction=True)
class TestFaceRecognitionRaceConditions(TransactionTestCase):
    """Test race conditions in face recognition signals"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001'
        )

        self.model = FaceRecognitionModel.objects.create(
            name='TestModel',
            model_type='FACENET512',
            version='1.0',
            similarity_threshold=0.3,
            confidence_threshold=0.7
        )

    def test_concurrent_counter_updates(self):
        """Test that concurrent verifications update counters correctly"""
        initial_count = self.model.verification_count
        num_verifications = 20
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
            except (ValueError, TypeError, KeyError) as e:
                errors.append(e)

        # Create mix of successful and failed verifications
        threads = []
        for i in range(num_verifications):
            is_success = i % 2 == 0
            t = threading.Thread(target=create_verification, args=(is_success,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check for errors
        self.assertEqual(len(errors), 0, f"Errors in concurrent updates: {errors}")

        # Verify counter accuracy
        self.model.refresh_from_db()
        expected_count = initial_count + num_verifications
        self.assertEqual(
            self.model.verification_count,
            expected_count,
            f"Counter mismatch: expected {expected_count}, got {self.model.verification_count}"
        )

        # Verify successful count
        expected_success = num_verifications // 2
        self.assertEqual(
            self.model.successful_verifications,
            expected_success,
            f"Success counter mismatch: expected {expected_success}, got {self.model.successful_verifications}"
        )

    def test_primary_embedding_uniqueness(self):
        """Test that only one primary embedding exists per user per model type"""
        num_embeddings = 10
        errors = []

        def create_embedding():
            try:
                FaceEmbedding.objects.create(
                    user=self.user,
                    extraction_model=self.model,
                    embedding_vector=[0.1] * 512,
                    face_confidence=0.9,
                    is_validated=True
                )
            except (ValueError, TypeError, KeyError) as e:
                errors.append(e)

        # Try to create multiple embeddings concurrently
        threads = [threading.Thread(target=create_embedding) for _ in range(num_embeddings)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # May have some integrity errors (expected if constraint works)
        # But should have exactly ONE primary embedding

        primary_count = FaceEmbedding.objects.filter(
            user=self.user,
            extraction_model__model_type=self.model.model_type,
            is_primary=True
        ).count()

        self.assertEqual(
            primary_count, 1,
            f"Expected 1 primary embedding, found {primary_count}"
        )

    def test_embedding_counter_accuracy(self):
        """Test embedding counter accuracy under concurrent load"""
        embedding = FaceEmbedding.objects.create(
            user=self.user,
            extraction_model=self.model,
            embedding_vector=[0.1] * 512,
            face_confidence=0.9,
            is_primary=True
        )

        initial_count = embedding.verification_count
        num_verifications = 15
        errors = []

        def create_verification():
            try:
                FaceVerificationLog.objects.create(
                    user=self.user,
                    verification_model=self.model,
                    matched_embedding=embedding,
                    result='SUCCESS',
                    similarity_score=0.85,
                    processing_time_ms=100
                )
            except (ValueError, TypeError, KeyError) as e:
                errors.append(e)

        threads = [threading.Thread(target=create_verification) for _ in range(num_verifications)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify counter
        embedding.refresh_from_db()
        expected_count = initial_count + num_verifications

        self.assertEqual(
            embedding.verification_count,
            expected_count,
            f"Embedding counter mismatch: expected {expected_count}, got {embedding.verification_count}"
        )

        self.assertEqual(
            embedding.successful_matches,
            num_verifications,
            f"Success counter mismatch: expected {num_verifications}, got {embedding.successful_matches}"
        )


@pytest.mark.django_db(transaction=True)
class TestDataIntegrityConstraints(TransactionTestCase):
    """Test database-level integrity constraints"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001'
        )

        self.model = FaceRecognitionModel.objects.create(
            name='TestModel',
            model_type='FACENET512'
        )

    def test_unique_primary_constraint_enforcement(self):
        """Test database constraint prevents multiple primary embeddings"""
        from django.db import IntegrityError

        # Create first primary embedding
        embedding1 = FaceEmbedding.objects.create(
            user=self.user,
            extraction_model=self.model,
            embedding_vector=[0.1] * 512,
            face_confidence=0.9,
            is_primary=True
        )

        # Try to create second primary embedding manually
        # (bypassing signal handlers)
        with self.assertRaises(IntegrityError):
            FaceEmbedding.objects.create(
                user=self.user,
                extraction_model=self.model,
                embedding_vector=[0.2] * 512,
                face_confidence=0.9,
                is_primary=True
            )


class TestPerformanceUnderLoad(TransactionTestCase):
    """Performance tests to ensure locking doesn't cause bottlenecks"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            username='perftest',
            peoplename='Performance Test User',
            peoplecode='PERF001'
        )

        self.client_bt = Bt.objects.create(
            bucode='CLIENT01',
            buname='Test Client',
            btype='C'
        )

        self.site_bt = Bt.objects.create(
            bucode='SITE01',
            buname='Test Site',
            btype='S'
        )

        self.shift = Shift.objects.create(
            shiftname='Day Shift',
            client=self.client_bt,
            bu=self.site_bt
        )

        self.event_type = TypeAssist.objects.create(
            tacode='SELF',
            taname='Self Attendance'
        )

    def test_update_latency_under_lock(self):
        """Measure update latency with locking enabled"""
        attendance = PeopleEventlog.objects.create(
            uuid=uuid_module.uuid4(),
            people=self.user,
            client=self.client_bt,
            bu=self.site_bt,
            shift=self.shift,
            peventtype=self.event_type,
            punchintime=timezone.now(),
            datefor=timezone.now().date()
        )

        result = {"verified": True, "distance": 0.2}

        # Measure time
        start_time = time.time()

        success = PeopleEventlog.objects.update_fr_results(
            result, str(attendance.uuid), attendance.people_id, 'default'
        )

        elapsed_ms = (time.time() - start_time) * 1000

        self.assertTrue(success, "Update failed")
        self.assertLess(elapsed_ms, 100, f"Update took {elapsed_ms:.2f}ms (threshold: 100ms)")

        logger.info(f"Update latency: {elapsed_ms:.2f}ms")


@pytest.mark.django_db
def test_distributed_lock_basic_functionality():
    """Test distributed lock utility works correctly"""
    from apps.core.utils_new.distributed_locks import DistributedLock, LockAcquisitionError

    lock_key = "test_lock"

    # Test acquisition
    lock1 = DistributedLock(lock_key, timeout=5)
    assert lock1.acquire() is True

    # Test blocking on second acquisition
    lock2 = DistributedLock(lock_key, timeout=5, blocking_timeout=1)

    with pytest.raises(LockTimeoutError):
        lock2.acquire()

    # Test release
    lock1.release()

    # Should be able to acquire now
    assert lock2.acquire() is True
    lock2.release()