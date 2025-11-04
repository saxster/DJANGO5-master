"""
Comprehensive tests for changeset tracking and rollback functionality
"""

import pytest
from django.test import TestCase
from django.db import transaction
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import ConversationSession
from apps.onboarding_api.integration.mapper import IntegrationAdapter
from apps.peoples.models import People


class ChangesetTrackingTest(TestCase):
    """Test changeset creation and tracking functionality"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

        # Create test client
        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

        # Create conversation session
        self.session = ConversationSession.objects.create(
            client=self.client_bt,
            current_state='processing',
            enable=True
        )

        self.adapter = IntegrationAdapter()

    def test_create_changeset(self):
        """Test changeset creation"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user,
            description="Test changeset creation"
        )

        self.assertIsInstance(changeset, AIChangeSet)
        self.assertEqual(changeset.conversation_session, self.session)
        self.assertEqual(changeset.approved_by, self.user)
        self.assertEqual(changeset.description, "Test changeset creation")
        self.assertEqual(changeset.status, AIChangeSet.StatusChoices.PENDING)

    def test_track_change_create(self):
        """Test tracking a CREATE change"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user
        )

        # Create a test business unit
        bu = Bt.objects.create(
            bucode='BU001',
            buname='Test BU',
            parent=self.client_bt
        )

        # Track the creation
        change_record = self.adapter.track_change(
            changeset=changeset,
            action=AIChangeRecord.ActionChoices.CREATE,
            model_instance=bu,
            sequence_order=1
        )

        self.assertIsInstance(change_record, AIChangeRecord)
        self.assertEqual(change_record.changeset, changeset)
        self.assertEqual(change_record.action, AIChangeRecord.ActionChoices.CREATE)
        self.assertEqual(change_record.model_name, 'bt')
        self.assertEqual(change_record.object_id, str(bu.id))
        self.assertEqual(change_record.sequence_order, 1)
        self.assertIsNotNone(change_record.after_state)

    def test_track_change_update(self):
        """Test tracking an UPDATE change"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user
        )

        # Create a test business unit
        bu = Bt.objects.create(
            bucode='BU001',
            buname='Original Name',
            parent=self.client_bt
        )

        # Capture before state
        before_state = self.adapter._serialize_model_instance(bu)

        # Update the business unit
        bu.buname = 'Updated Name'
        bu.save()

        # Track the update
        change_record = self.adapter.track_change(
            changeset=changeset,
            action=AIChangeRecord.ActionChoices.UPDATE,
            model_instance=bu,
            before_state=before_state,
            sequence_order=1
        )

        self.assertEqual(change_record.action, AIChangeRecord.ActionChoices.UPDATE)
        self.assertIsNotNone(change_record.before_state)
        self.assertIsNotNone(change_record.after_state)
        self.assertNotEqual(change_record.before_state, change_record.after_state)

    def test_changeset_can_rollback(self):
        """Test changeset rollback eligibility"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user
        )

        # Initially should not be rollbackable (pending status)
        self.assertFalse(changeset.can_rollback())

        # After marking as applied, should be rollbackable
        changeset.status = AIChangeSet.StatusChoices.APPLIED
        changeset.save()
        self.assertTrue(changeset.can_rollback())

        # After rolling back, should not be rollbackable again
        changeset.status = AIChangeSet.StatusChoices.ROLLED_BACK
        changeset.save()
        self.assertFalse(changeset.can_rollback())

    def test_rollback_complexity_assessment(self):
        """Test rollback complexity calculation"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user
        )

        changeset.status = AIChangeSet.StatusChoices.APPLIED
        changeset.save()

        # With no dependencies, should be simple
        self.assertEqual(changeset.get_rollback_complexity(), "simple")

        # Create some change records with dependencies
        for i in range(3):
            AIChangeRecord.objects.create(
                changeset=changeset,
                sequence_order=i,
                model_name='bt',
                app_label='onboarding',
                object_id=f'{i}',
                action=AIChangeRecord.ActionChoices.CREATE,
                has_dependencies=True
            )

        # Should now be moderate complexity
        self.assertEqual(changeset.get_rollback_complexity(), "moderate")

    @patch('apps.onboarding_api.integration.mapper.logger')
    def test_rollback_changeset(self, mock_logger):
        """Test complete changeset rollback"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user
        )

        # Create a test business unit and track it
        bu = Bt.objects.create(
            bucode='BU001',
            buname='Test BU',
            parent=self.client_bt
        )

        change_record = self.adapter.track_change(
            changeset=changeset,
            action=AIChangeRecord.ActionChoices.CREATE,
            model_instance=bu,
            sequence_order=1
        )

        # Mark changeset as applied
        changeset.status = AIChangeSet.StatusChoices.APPLIED
        change_record.status = AIChangeRecord.StatusChoices.SUCCESS
        changeset.save()
        change_record.save()

        # Attempt rollback
        with patch.object(self.adapter, '_rollback_change_record', return_value={'success': True}) as mock_rollback:
            result = self.adapter.rollback_changeset(
                changeset=changeset,
                rollback_reason="Test rollback",
                rollback_user=self.user
            )

            # Verify rollback was attempted
            mock_rollback.assert_called_once()
            mock_logger.info.assert_called()

    def test_serialization_helper(self):
        """Test model instance serialization"""
        bu = Bt.objects.create(
            bucode='BU001',
            buname='Test BU',
            parent=self.client_bt
        )

        serialized = self.adapter._serialize_model_instance(bu)

        self.assertIsInstance(serialized, dict)
        self.assertIn('pk', serialized)
        self.assertIn('model', serialized)
        self.assertEqual(serialized['bucode'], 'BU001')
        self.assertEqual(serialized['buname'], 'Test BU')


class ChangesetIntegrationTest(TestCase):
    """Test changeset functionality in integration scenarios"""

    def setUp(self):
        """Set up test data"""
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
            current_state='processing',
            enable=True
        )

        # Create a recommendation
        self.recommendation = LLMRecommendation.objects.create(
            session=self.session,
            recommendation_type='business_unit_setup',
            consensus={
                'recommendations': {
                    'business_unit_config': {
                        'bu_name': 'Test BU',
                        'bu_code': 'TEST001',
                        'max_users': 20
                    }
                }
            },
            confidence_score=0.9
        )

        self.adapter = IntegrationAdapter()

    def test_end_to_end_changeset_tracking(self):
        """Test complete flow from recommendation to changeset"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user,
            description="End-to-end test"
        )

        # Apply recommendation with changeset tracking
        result = self.adapter.apply_single_recommendation(
            recommendation=self.recommendation,
            user=self.user,
            dry_run=False,
            changeset=changeset
        )

        self.assertTrue(result['success'])
        self.assertTrue(len(result['changes']) > 0)

        # Verify changeset has change records
        change_records = changeset.change_records.all()
        self.assertTrue(len(change_records) > 0)

        # Verify business unit was created
        bu = Bt.objects.filter(bucode='TEST001', parent=self.client_bt).first()
        self.assertIsNotNone(bu)
        self.assertEqual(bu.buname, 'Test BU')

    def test_concurrent_changeset_creation(self):
        """Test multiple changesets can be created concurrently"""
        changesets = []

        # Create multiple changesets
        for i in range(3):
            changeset = self.adapter.create_changeset(
                conversation_session=self.session,
                approved_by=self.user,
                description=f"Concurrent test {i}"
            )
            changesets.append(changeset)

        # Verify all were created successfully
        self.assertEqual(len(changesets), 3)
        for changeset in changesets:
            self.assertIsInstance(changeset, AIChangeSet)
            self.assertEqual(changeset.conversation_session, self.session)

    def test_changeset_metadata_handling(self):
        """Test changeset metadata storage and retrieval"""
        metadata = {
            'test_run': True,
            'source': 'integration_test',
            'complexity': 'high'
        }

        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user,
            description="Metadata test"
        )

        changeset.metadata = metadata
        changeset.save()

        # Retrieve and verify metadata
        retrieved_changeset = AIChangeSet.objects.get(changeset_id=changeset.changeset_id)
        self.assertEqual(retrieved_changeset.metadata, metadata)

    @pytest.mark.django_db
    def test_changeset_transaction_rollback(self):
        """Test changeset behavior during transaction rollback"""
        changeset = self.adapter.create_changeset(
            conversation_session=self.session,
            approved_by=self.user,
            description="Transaction test"
        )

        try:
            with transaction.atomic():
                # Create a change record
                bu = Bt.objects.create(
                    bucode='BU001',
                    buname='Test BU',
                    parent=self.client_bt
                )

                self.adapter.track_change(
                    changeset=changeset,
                    action=AIChangeRecord.ActionChoices.CREATE,
                    model_instance=bu,
                    sequence_order=1
                )

                # Force a rollback
                raise Exception("Forced rollback")

        except Exception:
            pass

        # Verify changeset still exists but change record was rolled back
        self.assertTrue(AIChangeSet.objects.filter(changeset_id=changeset.changeset_id).exists())
        self.assertEqual(changeset.change_records.count(), 0)
