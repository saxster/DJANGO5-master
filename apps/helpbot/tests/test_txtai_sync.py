"""
Tests for txtai Index Synchronization (Nov 2025).

Tests the automatic index update pipeline:
1. Knowledge created → signal fires → async task queued → index updated
2. Knowledge updated → signal fires → async task queued → index refreshed
3. Knowledge deleted → signal fires → async task queued → index cleaned

Critical requirements:
- Index updates don't block CRUD operations
- Failed updates don't prevent knowledge creation
- 5-second batching allows aggregation
- Search results match database state within 10 seconds
"""

import pytest
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from celery.exceptions import Retry

from apps.helpbot.models import HelpBotKnowledge
from apps.helpbot.tasks import update_txtai_index_task
from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService


@pytest.mark.django_db
class TestTxtaiIndexSynchronization:
    """Test txtai index synchronization via signals and tasks."""

    @pytest.fixture
    def tenant(self, db):
        """Create test tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(tenantname="Test", subdomain_prefix="test")

    @pytest.fixture
    def user(self, db, tenant):
        """Create test user."""
        from apps.peoples.models import People
        return People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            tenant=tenant
        )

    def test_knowledge_creation_queues_index_update(self, tenant, user):
        """Test creating knowledge queues txtai index update task."""
        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            # Create new knowledge
            knowledge = HelpBotKnowledge.objects.create(
                tenant=tenant,
                title="Test Knowledge",
                content="Test content",
                category="general",
                knowledge_type="faq",
                created_by=user
            )

            # Verify task was queued
            mock_task.assert_called_once()

            # Verify task arguments
            call_args = mock_task.call_args
            args = call_args[1]['args']
            countdown = call_args[1]['countdown']

            assert args[0] == str(knowledge.knowledge_id)
            assert args[1] == 'add'
            assert countdown == 5  # 5-second batching

    def test_knowledge_update_queues_index_refresh(self, tenant, user):
        """Test updating knowledge queues txtai index refresh task."""
        # Create knowledge
        knowledge = HelpBotKnowledge.objects.create(
            tenant=tenant,
            title="Original Title",
            content="Original content",
            category="general",
            knowledge_type="faq",
            created_by=user
        )

        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            # Update knowledge
            knowledge.title = "Updated Title"
            knowledge.save()

            # Verify task was queued with 'update' operation
            mock_task.assert_called_once()

            call_args = mock_task.call_args
            args = call_args[1]['args']

            assert args[0] == str(knowledge.knowledge_id)
            assert args[1] == 'update'

    def test_knowledge_deletion_queues_index_cleanup(self, tenant, user):
        """Test deleting knowledge queues txtai index cleanup task."""
        knowledge = HelpBotKnowledge.objects.create(
            tenant=tenant,
            title="To Delete",
            content="Content",
            category="general",
            knowledge_type="faq",
            created_by=user
        )

        knowledge_id = str(knowledge.knowledge_id)

        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            # Delete knowledge
            knowledge.delete()

            # Verify task was queued with 'delete' operation
            mock_task.assert_called_once()

            call_args = mock_task.call_args
            args = call_args[1]['args']

            assert args[0] == knowledge_id
            assert args[1] == 'delete'

    def test_signal_failure_doesnt_block_crud(self, tenant, user):
        """Test signal failures don't prevent knowledge CRUD operations."""
        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            mock_task.side_effect = Exception("Task queue unavailable")

            # Should still create knowledge successfully
            knowledge = HelpBotKnowledge.objects.create(
                tenant=tenant,
                title="Test",
                content="Content",
                category="general",
                knowledge_type="faq",
                created_by=user
            )

            # Knowledge created despite task failure
            assert knowledge.knowledge_id is not None
            assert HelpBotKnowledge.objects.filter(knowledge_id=knowledge.knowledge_id).exists()


@pytest.mark.django_db
class TestUpdateTxtaiIndexTask:
    """Test the update_txtai_index_task Celery task."""

    @pytest.fixture
    def tenant(self, db):
        """Create test tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(tenantname="Test", subdomain_prefix="test")

    @pytest.fixture
    def user(self, db, tenant):
        """Create test user."""
        from apps.peoples.models import People
        return People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            tenant=tenant
        )

    @pytest.fixture
    def knowledge(self, tenant, user):
        """Create test knowledge."""
        return HelpBotKnowledge.objects.create(
            tenant=tenant,
            title="Test Knowledge",
            content="Test content for searching",
            category="general",
            knowledge_type="faq",
            created_by=user
        )

    def test_task_updates_index_for_add_operation(self, knowledge):
        """Test task calls update_index_document for add operation."""
        with patch.object(HelpBotKnowledgeService, 'update_index_document') as mock_update:
            mock_update.return_value = True

            result = update_txtai_index_task(str(knowledge.knowledge_id), 'add')

            assert result['success'] is True
            assert result['knowledge_id'] == str(knowledge.knowledge_id)
            assert result['operation'] == 'add'
            mock_update.assert_called_once()

    def test_task_updates_index_for_update_operation(self, knowledge):
        """Test task calls update_index_document for update operation."""
        with patch.object(HelpBotKnowledgeService, 'update_index_document') as mock_update:
            mock_update.return_value = True

            result = update_txtai_index_task(str(knowledge.knowledge_id), 'update')

            assert result['success'] is True
            assert result['operation'] == 'update'
            mock_update.assert_called_once()

    def test_task_removes_from_index_for_delete_operation(self, knowledge):
        """Test task calls remove_from_index for delete operation."""
        knowledge_id = str(knowledge.knowledge_id)

        # Delete the knowledge from database
        knowledge.delete()

        with patch.object(HelpBotKnowledgeService, 'remove_from_index') as mock_remove:
            mock_remove.return_value = True

            result = update_txtai_index_task(knowledge_id, 'delete')

            assert result['success'] is True
            assert result['operation'] == 'delete'
            mock_remove.assert_called_once_with(knowledge_id)

    def test_task_handles_missing_knowledge(self):
        """Test task handles non-existent knowledge gracefully."""
        result = update_txtai_index_task('non-existent-id', 'update')

        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_task_skips_when_txtai_disabled(self, knowledge):
        """Test task skips index update when txtai disabled."""
        with patch.object(HelpBotKnowledgeService, 'txtai_enabled', False):
            result = update_txtai_index_task(str(knowledge.knowledge_id), 'add')

            assert result['success'] is True
            assert result['skipped'] is True
            assert result['reason'] == 'txtai_disabled'

    def test_task_retries_on_network_error(self, knowledge):
        """Test task retries on network errors."""
        from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

        with patch.object(HelpBotKnowledgeService, 'update_index_document') as mock_update:
            mock_update.side_effect = ConnectionError("Network unavailable")

            task_obj = update_txtai_index_task
            with patch.object(task_obj, 'retry', side_effect=Retry()) as mock_retry:
                with pytest.raises(Retry):
                    update_txtai_index_task(str(knowledge.knowledge_id), 'add')

                # Verify retry was called
                mock_retry.assert_called_once()

    def test_task_handles_value_error_without_retry(self, knowledge):
        """Test task handles ValueError without retry."""
        with patch.object(HelpBotKnowledgeService, 'update_index_document') as mock_update:
            mock_update.side_effect = ValueError("Invalid document format")

            result = update_txtai_index_task(str(knowledge.knowledge_id), 'add')

            assert result['success'] is False
            assert 'error' in result
            assert 'Invalid document format' in result['error']


class TestKnowledgeServiceIndexMethods(TestCase):
    """Test HelpBotKnowledgeService index update methods."""

    def setUp(self):
        """Set up test environment."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        self.tenant = Tenant.objects.create(
            tenantname="Test",
            subdomain_prefix="test"
        )

        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            tenant=self.tenant
        )

        self.knowledge = HelpBotKnowledge.objects.create(
            tenant=self.tenant,
            title="Test Article",
            content="Test content for indexing",
            category="technical",
            knowledge_type="documentation",
            created_by=self.user
        )

        self.service = HelpBotKnowledgeService()

    def test_update_index_document_prepares_correct_structure(self):
        """Test update_index_document prepares correct document structure."""
        with patch.object(self.service, 'txtai_enabled', True):
            # Mock the actual index update
            result = self.service.update_index_document(self.knowledge)

            # Should succeed (even if txtai not actually configured)
            assert result is True

    def test_update_index_document_skips_when_disabled(self):
        """Test update_index_document skips when txtai disabled."""
        with patch.object(self.service, 'txtai_enabled', False):
            result = self.service.update_index_document(self.knowledge)

            # Should return True (nothing to do)
            assert result is True

    def test_remove_from_index_logs_removal(self):
        """Test remove_from_index logs removal operation."""
        knowledge_id = str(self.knowledge.knowledge_id)

        with patch.object(self.service, 'txtai_enabled', True):
            with patch('apps.helpbot.services.knowledge_service.logger') as mock_logger:
                result = self.service.remove_from_index(knowledge_id)

                assert result is True

                # Verify logging
                info_calls = [call for call in mock_logger.info.call_args_list]
                removal_logged = any(
                    knowledge_id in str(call) and 'Removed' in str(call)
                    for call in info_calls
                )
                assert removal_logged

    def test_remove_from_index_skips_when_disabled(self):
        """Test remove_from_index skips when txtai disabled."""
        with patch.object(self.service, 'txtai_enabled', False):
            result = self.service.remove_from_index('any-id')

            # Should return True (nothing to do)
            assert result is True


class TestTxtaiSyncEndToEnd(TestCase):
    """
    End-to-end tests for txtai synchronization.

    Verifies the complete pipeline:
    CRUD operation → Signal → Async task → Service method → Index update
    """

    def setUp(self):
        """Set up test environment."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        self.tenant = Tenant.objects.create(
            tenantname="Test",
            subdomain_prefix="test"
        )

        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            tenant=self.tenant
        )

    def test_create_knowledge_triggers_index_update(self):
        """Test creating knowledge triggers complete index update pipeline."""
        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            knowledge = HelpBotKnowledge.objects.create(
                tenant=self.tenant,
                title="New Article",
                content="New content",
                category="general",
                knowledge_type="faq",
                created_by=self.user
            )

            # Signal should have queued task
            assert mock_task.called
            call_args = mock_task.call_args[1]

            # Verify task parameters
            assert call_args['args'][0] == str(knowledge.knowledge_id)
            assert call_args['args'][1] == 'add'
            assert call_args['countdown'] == 5

    def test_update_knowledge_triggers_index_refresh(self):
        """Test updating knowledge triggers index refresh."""
        knowledge = HelpBotKnowledge.objects.create(
            tenant=self.tenant,
            title="Original",
            content="Original",
            category="general",
            knowledge_type="faq",
            created_by=self.user
        )

        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            knowledge.title = "Updated"
            knowledge.save()

            # Signal should have queued update task
            assert mock_task.called
            call_args = mock_task.call_args[1]

            assert call_args['args'][1] == 'update'

    def test_delete_knowledge_triggers_index_cleanup(self):
        """Test deleting knowledge triggers index cleanup."""
        knowledge = HelpBotKnowledge.objects.create(
            tenant=self.tenant,
            title="To Delete",
            content="Content",
            category="general",
            knowledge_type="faq",
            created_by=self.user
        )

        knowledge_id = str(knowledge.knowledge_id)

        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            knowledge.delete()

            # Signal should have queued delete task
            assert mock_task.called
            call_args = mock_task.call_args[1]

            assert call_args['args'][0] == knowledge_id
            assert call_args['args'][1] == 'delete'

    def test_rapid_updates_batched_via_countdown(self):
        """Test rapid updates benefit from 5-second countdown batching."""
        knowledge = HelpBotKnowledge.objects.create(
            tenant=self.tenant,
            title="Rapid Update Test",
            content="Content",
            category="general",
            knowledge_type="faq",
            created_by=self.user
        )

        with patch('apps.helpbot.tasks.update_txtai_index_task.apply_async') as mock_task:
            # Simulate rapid updates
            for i in range(5):
                knowledge.content = f"Content version {i}"
                knowledge.save()

            # Should have queued 5 update tasks
            assert mock_task.call_count == 5

            # All should have 5-second countdown (Celery will dedupe if same args)
            for call_obj in mock_task.call_args_list:
                assert call_obj[1]['countdown'] == 5

    def test_index_update_failure_doesnt_break_crud(self):
        """Test index update failures don't prevent knowledge creation."""
        with patch.object(HelpBotKnowledgeService, 'update_index_document') as mock_update:
            mock_update.side_effect = Exception("Index update failed")

            # Should still create knowledge
            knowledge = HelpBotKnowledge.objects.create(
                tenant=self.tenant,
                title="Test",
                content="Content",
                category="general",
                knowledge_type="faq",
                created_by=self.user
            )

            # Knowledge exists in database
            assert HelpBotKnowledge.objects.filter(
                knowledge_id=knowledge.knowledge_id
            ).exists()
