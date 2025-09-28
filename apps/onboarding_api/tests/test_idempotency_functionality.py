"""
Comprehensive tests for idempotency functionality in IntegrationAdapter
"""

import time
from concurrent.futures import ThreadPoolExecutor

from apps.onboarding.models import Bt, Shift, TypeAssist, ConversationSession
from apps.peoples.models import People
from apps.onboarding_api.integration.mapper import IntegrationAdapter


class IdempotencyTest(TestCase):
    """Test idempotency key generation and handling"""

    def setUp(self):
        """Set up test data"""
        self.adapter = IntegrationAdapter()

        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

    def test_generate_idempotency_key_consistency(self):
        """Test that idempotency keys are consistent for same input"""
        operation_type = 'business_unit_setup'
        data = {
            'bu_name': 'Test BU',
            'bu_code': 'TEST001',
            'max_users': 10
        }
        context = {'client_id': self.client_bt.id}

        key1 = self.adapter._generate_idempotency_key(operation_type, data, context)
        key2 = self.adapter._generate_idempotency_key(operation_type, data, context)

        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 16)  # SHA256 truncated to 16 chars

    def test_generate_idempotency_key_uniqueness(self):
        """Test that different inputs generate different keys"""
        base_data = {
            'bu_name': 'Test BU',
            'bu_code': 'TEST001',
            'max_users': 10
        }

        key1 = self.adapter._generate_idempotency_key('business_unit_setup', base_data)

        # Different operation type
        key2 = self.adapter._generate_idempotency_key('shift_configuration', base_data)
        self.assertNotEqual(key1, key2)

        # Different data
        modified_data = base_data.copy()
        modified_data['max_users'] = 20
        key3 = self.adapter._generate_idempotency_key('business_unit_setup', modified_data)
        self.assertNotEqual(key1, key3)

        # Different context
        key4 = self.adapter._generate_idempotency_key('business_unit_setup', base_data, {'client_id': 999})
        self.assertNotEqual(key1, key4)

    def test_conflict_detection_business_unit(self):
        """Test conflict detection for business unit operations"""
        # Create an existing BU
        existing_bu = Bt.objects.create(
            bucode='EXISTING001',
            buname='Existing BU',
            parent=self.client_bt
        )

        # Test conflict detection
        data = {
            'bu_code': 'EXISTING001',
            'bu_name': 'Test BU'
        }

        conflicts = self.adapter._check_operation_conflicts('business_unit_setup', data, self.client_bt)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'duplicate_bu_code')
        self.assertIn('EXISTING001', conflicts[0]['message'])
        self.assertEqual(conflicts[0]['resolution'], 'update_existing')

    def test_conflict_detection_shift(self):
        """Test conflict detection for shift operations"""
        # Create an existing shift
        existing_shift = Shift.objects.create(
            shiftname='Existing Shift',
            client=self.client_bt,
            bu=self.client_bt,
            starttime='09:00',
            endtime='17:00',
            peoplecount=5
        )

        # Test conflict detection
        data = {
            'shift_name': 'Existing Shift',
            'start_time': '08:00'
        }

        conflicts = self.adapter._check_operation_conflicts('shift_configuration', data, self.client_bt)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'duplicate_shift_name')
        self.assertEqual(conflicts[0]['resolution'], 'update_existing')

    def test_conflict_detection_typeassist(self):
        """Test conflict detection for typeassist operations"""
        # Create an existing TypeAssist
        existing_ta = TypeAssist.objects.create(
            tacode='EXISTING',
            taname='Existing TypeAssist',
            client=self.client_bt,
            bu=self.client_bt
        )

        # Test conflict detection
        data = {
            'ta_code': 'EXISTING',
            'ta_name': 'Test TypeAssist'
        }

        conflicts = self.adapter._check_operation_conflicts('type_assist_setup', data, self.client_bt)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'duplicate_typeassist_code')
        self.assertEqual(conflicts[0]['resolution'], 'update_existing')


class IdempotentCreateTest(TestCase):
    """Test idempotent create/update operations"""

    def setUp(self):
        """Set up test data"""
        self.adapter = IntegrationAdapter()
        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

    def test_create_with_idempotency_new_object(self):
        """Test creating a new object with idempotency"""
        create_data = {
            'bucode': 'NEW001',
            'buname': 'New BU',
            'parent': self.client_bt,
            'enable': True
        }

        obj, was_created = self.adapter._create_with_idempotency(
            model_class=Bt,
            create_data=create_data,
            unique_fields=['bucode', 'parent']
        )

        self.assertTrue(was_created)
        self.assertEqual(obj.bucode, 'NEW001')
        self.assertEqual(obj.buname, 'New BU')
        self.assertEqual(obj.parent, self.client_bt)

    def test_create_with_idempotency_existing_object(self):
        """Test finding existing object instead of creating duplicate"""
        # Create an existing object
        existing_bu = Bt.objects.create(
            bucode='EXISTING001',
            buname='Original Name',
            parent=self.client_bt,
            enable=True
        )

        # Try to create another with same unique fields
        create_data = {
            'bucode': 'EXISTING001',
            'buname': 'New Name',
            'parent': self.client_bt,
            'enable': True
        }

        obj, was_created = self.adapter._create_with_idempotency(
            model_class=Bt,
            create_data=create_data,
            unique_fields=['bucode', 'parent']
        )

        self.assertFalse(was_created)  # Should have found existing
        self.assertEqual(obj.id, existing_bu.id)
        self.assertEqual(obj.buname, 'Original Name')  # Should not have updated

    def test_create_with_idempotency_update_existing(self):
        """Test updating existing object when specified"""
        # Create an existing object
        existing_bu = Bt.objects.create(
            bucode='EXISTING001',
            buname='Original Name',
            parent=self.client_bt,
            enable=True
        )

        # Try to create another with same unique fields but update specified
        create_data = {
            'bucode': 'EXISTING001',
            'buname': 'Updated Name',
            'parent': self.client_bt,
            'enable': False
        }

        obj, was_created = self.adapter._create_with_idempotency(
            model_class=Bt,
            create_data=create_data,
            unique_fields=['bucode', 'parent'],
            update_fields=['buname', 'enable']
        )

        self.assertFalse(was_created)  # Should have found existing
        self.assertEqual(obj.id, existing_bu.id)

        # Refresh from database
        obj.refresh_from_db()
        self.assertEqual(obj.buname, 'Updated Name')  # Should have updated
        self.assertEqual(obj.enable, False)


class RetryMechanismTest(TransactionTestCase):
    """Test retry mechanism with exponential backoff"""

    def setUp(self):
        """Set up test data"""
        self.adapter = IntegrationAdapter()

    def test_retry_with_exponential_backoff_success(self):
        """Test successful operation after retries"""
        call_count = {'count': 0}

        def operation_that_succeeds_on_third_try():
            call_count['count'] += 1
            if call_count['count'] < 3:
                raise IntegrityError("Simulated integrity error")
            return "success"

        result = self.adapter._retry_with_exponential_backoff(
            operation_that_succeeds_on_third_try,
            "test_operation"
        )

        self.assertEqual(result, "success")
        self.assertEqual(call_count['count'], 3)

    def test_retry_with_exponential_backoff_max_retries_exceeded(self):
        """Test operation that fails all retries"""
        call_count = {'count': 0}

        def operation_that_always_fails():
            call_count['count'] += 1
            raise IntegrityError("Persistent integrity error")

        with self.assertRaises(IntegrityError):
            self.adapter._retry_with_exponential_backoff(
                operation_that_always_fails,
                "test_operation",
                max_retries=2
            )

        # Should be called 3 times (initial + 2 retries)
        self.assertEqual(call_count['count'], 3)

    def test_retry_non_retryable_error(self):
        """Test that non-retryable errors are not retried"""
        call_count = {'count': 0}

        def operation_with_non_retryable_error():
            call_count['count'] += 1
            raise ValueError("Non-retryable error")

        with self.assertRaises(ValueError):
            self.adapter._retry_with_exponential_backoff(
                operation_with_non_retryable_error,
                "test_operation"
            )

        # Should only be called once (no retries for non-retryable errors)
        self.assertEqual(call_count['count'], 1)

    @patch('apps.onboarding_api.integration.mapper.time.sleep')
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test that exponential backoff timing is correct"""
        call_count = {'count': 0}

        def operation_that_fails_twice():
            call_count['count'] += 1
            if call_count['count'] <= 2:
                raise IntegrityError("Simulated integrity error")
            return "success"

        result = self.adapter._retry_with_exponential_backoff(
            operation_that_fails_twice,
            "test_operation"
        )

        self.assertEqual(result, "success")

        # Should have called sleep twice (after first and second failures)
        self.assertEqual(mock_sleep.call_count, 2)

        # Verify exponential backoff (base_delay = 0.1)
        calls = mock_sleep.call_args_list
        # First retry: 0.1 * (2^0) + jitter = 0.1 + jitter
        # Second retry: 0.1 * (2^1) + jitter = 0.2 + jitter
        self.assertTrue(0.1 <= calls[0][0][0] <= 0.2)  # First call with jitter
        self.assertTrue(0.2 <= calls[1][0][0] <= 0.3)  # Second call with jitter


class ConcurrentAccessTest(TransactionTestCase):
    """Test concurrent access scenarios"""

    def setUp(self):
        """Set up test data"""
        self.adapter = IntegrationAdapter()
        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

    def test_concurrent_create_operations(self):
        """Test concurrent creation of same object"""
        def create_bu_operation():
            try:
                create_data = {
                    'bucode': 'CONCURRENT001',
                    'buname': 'Concurrent BU',
                    'parent': self.client_bt,
                    'enable': True
                }

                obj, was_created = self.adapter._create_with_idempotency(
                    model_class=Bt,
                    create_data=create_data,
                    unique_fields=['bucode', 'parent']
                )
                return obj, was_created
            except Exception as e:
                return None, str(e)

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_bu_operation) for _ in range(3)]
            results = [future.result() for future in futures]

        # Should have exactly one successful creation
        successful_creates = [r for r in results if r[0] is not None and r[1] is True]
        successful_finds = [r for r in results if r[0] is not None and r[1] is False]

        self.assertEqual(len(successful_creates), 1)
        # The others should have found the existing object
        self.assertTrue(len(successful_finds) >= 1)

        # Verify only one object was created
        bu_count = Bt.objects.filter(bucode='CONCURRENT001', parent=self.client_bt).count()
        self.assertEqual(bu_count, 1)

    def test_conflict_detection_with_race_conditions(self):
        """Test conflict detection under race conditions"""
        def create_shift_with_conflict_check():
            # Simulate the race condition scenario
            data = {
                'shift_name': 'Race Condition Shift',
                'start_time': '09:00',
                'end_time': '17:00'
            }

            conflicts = self.adapter._check_operation_conflicts('shift_configuration', data, self.client_bt)

            # Small delay to simulate processing time
            time.sleep(0.01)

            if not conflicts:
                try:
                    shift = Shift.objects.create(
                        shiftname=data['shift_name'],
                        client=self.client_bt,
                        bu=self.client_bt,
                        starttime=data['start_time'],
                        endtime=data['end_time'],
                        peoplecount=5
                    )
                    return shift, True
                except IntegrityError:
                    return None, "integrity_error"
            else:
                return None, "conflict_detected"

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_shift_with_conflict_check) for _ in range(3)]
            results = [future.result() for future in futures]

        # Should have exactly one successful creation
        successful_creates = [r for r in results if r[0] is not None and r[1] is True]
        self.assertEqual(len(successful_creates), 1)

        # Verify only one shift was created
        shift_count = Shift.objects.filter(
            shiftname='Race Condition Shift',
            client=self.client_bt
        ).count()
        self.assertEqual(shift_count, 1)


class IdempotencyIntegrationTest(TestCase):
    """Integration tests for idempotency in full recommendation flow"""

    def setUp(self):
        """Set up test data"""
        self.adapter = IntegrationAdapter()

        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

        self.session = ConversationSession.objects.create(
            client=self.client_bt,
            current_state='processing'
        )

    def test_business_unit_idempotency_in_full_flow(self):
        """Test business unit creation idempotency in complete flow"""
        bu_config = {
            'bu_name': 'Idempotent BU',
            'bu_code': 'IDEMP001',
            'max_users': 15,
            'confidence_score': 0.9
        }

        # Apply the same configuration twice
        result1 = self.adapter._apply_business_unit_config(
            bu_config=bu_config,
            client=self.client_bt,
            dry_run=False
        )

        result2 = self.adapter._apply_business_unit_config(
            bu_config=bu_config,
            client=self.client_bt,
            dry_run=False
        )

        # Both should succeed
        self.assertTrue(len(result1['changes']) > 0)
        self.assertTrue(len(result2['changes']) > 0)

        # First should be create, second should be update
        self.assertIn('create_business_unit', result1['changes'][0]['action'])
        self.assertIn('update_business_unit', result2['changes'][0]['action'])

        # Verify only one BU was created
        bu_count = Bt.objects.filter(bucode='IDEMP001', parent=self.client_bt).count()
        self.assertEqual(bu_count, 1)

        # Verify idempotency keys are present
        bu = Bt.objects.get(bucode='IDEMP001', parent=self.client_bt)
        self.assertIn('idempotency_key', bu.onboarding_context)

    def test_multiple_operations_idempotency(self):
        """Test idempotency across multiple operations in same session"""
        recommendations = {
            'business_unit_config': {
                'bu_name': 'Multi Op BU',
                'bu_code': 'MULTI001',
                'max_users': 10
            },
            'suggested_shifts': [{
                'shift_name': 'Multi Op Shift',
                'start_time': '09:00',
                'end_time': '17:00',
                'people_count': 5
            }]
        }

        # Apply multiple times
        for i in range(2):
            if 'business_unit_config' in recommendations:
                result = self.adapter._apply_business_unit_config(
                    bu_config=recommendations['business_unit_config'],
                    client=self.client_bt,
                    dry_run=False
                )

            if 'suggested_shifts' in recommendations:
                result = self.adapter._apply_shift_configuration(
                    shift_configs=recommendations['suggested_shifts'],
                    client=self.client_bt,
                    dry_run=False
                )

        # Verify only one of each object was created
        bu_count = Bt.objects.filter(bucode='MULTI001', parent=self.client_bt).count()
        shift_count = Shift.objects.filter(shiftname='Multi Op Shift', client=self.client_bt).count()

        self.assertEqual(bu_count, 1)
        self.assertEqual(shift_count, 1)