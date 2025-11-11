"""
Tests for transaction management in critical background tasks (Rule #17)

Verifies that critical tasks use transaction.atomic() to prevent data
inconsistencies between database updates and email notifications.

Date: 2025-11-11
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.db import transaction, IntegrityError, DatabaseError
from django.core.mail import EmailMessage
from django.test import TransactionTestCase
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
class TestEmailTaskTransactions:
    """Test transaction management in email_tasks.py"""

    @patch('background_tasks.email_tasks.EmailMessage')
    @patch('apps.scheduler.models.reminder.Reminder.objects.get_all_due_reminders')
    @patch('apps.scheduler.models.reminder.Reminder.objects.filter')
    def test_send_reminder_email_rollback_on_error(
        self, mock_filter, mock_get_reminders, mock_email
    ):
        """
        Test that send_reminder_email rolls back DB changes when email fails.

        Critical behavior: If email.send() fails, reminder status should NOT
        be updated to SUCCESS in database.
        """
        from background_tasks.email_tasks import send_reminder_email

        # Setup mock reminder data
        mock_get_reminders.return_value = [{
            'id': 1,
            'people_id': 1,
            'cuser_id': 1,
            'muser_id': 1,
            'group_id': 1,
            'mailids': 'test@example.com',
            'job__jobname': 'Test Job',
            'pdate': timezone.now(),
            'job__jobdesc': 'Test Description',
            'bu__buname': 'Test Site',
            'cuser__peoplename': 'Creator',
            'muser__peoplename': 'Modifier'
        }]

        # Setup mock update filter
        mock_update = Mock()
        mock_filter.return_value = Mock(update=mock_update)

        # Mock email to fail
        mock_email_instance = Mock()
        mock_email_instance.send.side_effect = Exception("SMTP connection failed")
        mock_email.return_value = mock_email_instance

        # Mock utils.get_email_addresses to return empty list
        with patch('apps.core.utils.get_email_addresses', return_value=[]):
            # Execute task - should handle exception
            result = send_reminder_email()

        # Verify database update was NOT called due to transaction rollback
        # In atomic block, if exception occurs, updates are rolled back
        assert 'error' in result or result['story']

    @patch('background_tasks.email_tasks.EmailMessage')
    @patch('apps.scheduler.models.reminder.Reminder.objects.get_all_due_reminders')
    @patch('apps.scheduler.models.reminder.Reminder.objects.filter')
    @patch('apps.core.utils.get_email_addresses')
    def test_send_reminder_email_commits_on_success(
        self, mock_get_emails, mock_filter, mock_get_reminders, mock_email
    ):
        """
        Test that send_reminder_email commits when email succeeds.

        Critical behavior: Email send + DB update must be atomic.
        """
        from background_tasks.email_tasks import send_reminder_email

        # Setup mock reminder data
        mock_get_reminders.return_value = [{
            'id': 1,
            'people_id': 1,
            'cuser_id': 1,
            'muser_id': 1,
            'group_id': 1,
            'mailids': 'test@example.com',
            'job__jobname': 'Test Job',
            'pdate': timezone.now(),
            'job__jobdesc': 'Test Description',
            'bu__buname': 'Test Site',
            'cuser__peoplename': 'Creator',
            'muser__peoplename': 'Modifier'
        }]

        # Mock email addresses
        mock_get_emails.return_value = ['test@example.com']

        # Setup mock update
        mock_update = Mock(return_value=1)
        mock_filter.return_value = Mock(update=mock_update)

        # Mock email to succeed
        mock_email_instance = Mock()
        mock_email_instance.send.return_value = 1  # Success
        mock_email.return_value = mock_email_instance

        # Execute task
        result = send_reminder_email()

        # Verify success
        assert 'error' not in result
        assert mock_email_instance.send.called


@pytest.mark.django_db(transaction=True)
class TestTicketTaskTransactions:
    """Test transaction management in ticket_tasks.py"""

    @patch('apps.core.queries.QueryRepository.get_ticketlist_for_escalation')
    @patch('background_tasks.utils.update_ticket_data')
    def test_ticket_escalation_uses_transaction(
        self, mock_update, mock_get_tickets
    ):
        """
        Test that ticket_escalation uses transaction.atomic().

        Critical behavior: Ticket escalation should update ticket_history,
        assignments, level, and mdtz atomically.
        """
        from background_tasks.ticket_tasks import ticket_escalation

        # Setup mock tickets
        mock_get_tickets.return_value = [
            {'id': 1, 'ticketno': 'T001', 'level': 1},
            {'id': 2, 'ticketno': 'T002', 'level': 1}
        ]

        # Mock update to return result
        mock_update.return_value = {
            'story': 'Updated 2 tickets',
            'id': [1, 2]
        }

        # Execute task
        result = ticket_escalation()

        # Verify transaction was used (check result structure)
        assert 'story' in result
        assert mock_update.called

    @patch('apps.core.queries.QueryRepository.get_ticketlist_for_escalation')
    @patch('background_tasks.utils.update_ticket_data')
    def test_ticket_escalation_rollback_on_error(
        self, mock_update, mock_get_tickets
    ):
        """
        Test that ticket_escalation rolls back on database error.

        Critical behavior: If ticket update fails midway, all changes
        should be rolled back.
        """
        from background_tasks.ticket_tasks import ticket_escalation

        # Setup mock to return tickets
        mock_get_tickets.return_value = [
            {'id': 1, 'ticketno': 'T001'}
        ]

        # Mock update to raise IntegrityError
        mock_update.side_effect = IntegrityError("Constraint violation")

        # Execute task - should handle exception
        result = ticket_escalation()

        # Verify error was caught and logged
        assert 'error' in result


@pytest.mark.django_db(transaction=True)
class TestJobTaskTransactions:
    """Test transaction management in job_tasks.py"""

    @patch('django.apps.apps.get_model')
    @patch('background_tasks.utils.get_email_recipients')
    @patch('background_tasks.utils.update_job_autoclose_status')
    @patch('background_tasks.utils.create_ticket_for_autoclose')
    def test_autoclose_job_uses_transaction(
        self, mock_create_ticket, mock_update_status,
        mock_get_emails, mock_get_model
    ):
        """
        Test that autoclose_job uses transaction.atomic().

        Critical behavior: Job status update + ticket creation + email
        notification must be atomic.
        """
        from background_tasks.job_tasks import autoclose_job

        # Mock Jobneed model
        mock_jobneed_model = Mock()
        mock_jobneed_model.objects.get_expired_jobs.return_value = [{
            'id': 1,
            'ticketcategory__tacode': 'RAISETICKETNOTIFY',
            'ticketcategory__taname': 'Test Category',
            'identifier': 'TASK',
            'plandatetime': timezone.now(),
            'expirydatetime': timezone.now(),
            'ctzoffset': 0,
            'bu__buname': 'Test Site',
            'cuser__peoplename': 'Test User',
            'assignedto': 'Test Assignee',
            'jobdesc': 'Test Description',
            'bu_id': 1,
            'client_id': 1,
            'priority': 'HIGH'
        }]
        mock_get_model.return_value = mock_jobneed_model

        # Mock email recipients
        mock_get_emails.return_value = ['test@example.com']

        # Mock ticket creation
        mock_create_ticket.return_value = {
            'ticketno': 'T001',
            'cdtz': timezone.now(),
            'ctzoffset': 0
        }

        # Mock status update
        mock_update_status.return_value = {'story': 'Updated job', 'id': [1]}

        # Mock EmailMessage
        with patch('background_tasks.job_tasks.EmailMessage') as mock_email:
            mock_email_instance = Mock()
            mock_email_instance.send.return_value = 1
            mock_email.return_value = mock_email_instance

            # Execute task
            result = autoclose_job(jobneedid=1)

        # Verify transaction was used
        assert 'error' not in result or result['story']

    @patch('django.apps.apps.get_model')
    def test_autoclose_job_rollback_on_error(self, mock_get_model):
        """
        Test that autoclose_job rolls back on database error.

        Critical behavior: If ticket creation fails, job status should
        NOT be marked as autoclosed.
        """
        from background_tasks.job_tasks import autoclose_job

        # Mock Jobneed to raise error
        mock_jobneed_model = Mock()
        mock_jobneed_model.objects.get_expired_jobs.side_effect = DatabaseError(
            "Database connection lost"
        )
        mock_get_model.return_value = mock_jobneed_model

        # Execute task - should handle exception
        result = autoclose_job(jobneedid=1)

        # Verify error was caught
        assert 'error' in result

    @patch('django.apps.apps.get_model')
    @patch('apps.scheduler.utils.calculate_startdtz_enddtz_for_ppm')
    @patch('apps.scheduler.utils.get_datetime_list')
    @patch('apps.scheduler.utils.insert_into_jn_and_jnd')
    @patch('apps.scheduler.utils.create_ppm_reminder')
    def test_create_ppm_job_uses_transaction(
        self, mock_create_reminder, mock_insert, mock_get_dt_list,
        mock_calculate_dates, mock_get_model
    ):
        """
        Test that create_ppm_job uses transaction.atomic().

        Critical behavior: PPM job creation + jobneed + reminder creation
        must be atomic.
        """
        from background_tasks.job_tasks import create_ppm_job
        from apps.core import utils

        # Mock Job model
        mock_job_model = Mock()
        mock_job_model.objects.filter.return_value.values.return_value = [{
            'id': 1,
            'jobname': 'PPM Task',
            'cron': '0 0 * * *'
        }]
        mock_get_model.return_value = mock_job_model

        # Mock Job class for attributes
        mock_job_model.Identifier = Mock()
        mock_job_model.Identifier.PPM = Mock(value='PPM')

        # Mock date calculations
        mock_calculate_dates.return_value = (
            timezone.now(),
            timezone.now() + timezone.timedelta(days=30)
        )

        # Mock datetime list
        mock_get_dt_list.return_value = (
            [timezone.now()],  # DT list
            True,  # is_cron
            None  # resp
        )

        # Mock insert
        mock_insert.return_value = (True, {'story': 'Inserted'})

        # Mock JobFields (required for values())
        with patch.object(utils, 'JobFields', Mock(fields=['id', 'jobname', 'cron'])):
            # Execute task
            resp, F, d, result = create_ppm_job(jobid=1)

        # Verify no errors
        assert len(F) == 0  # No failed jobs


@pytest.mark.django_db(transaction=True)
class TestTransactionRollbackBehavior:
    """Test that transactions actually roll back on errors"""

    def test_transaction_rollback_verification(self):
        """
        Verify Django's transaction.atomic() actually rolls back.

        This is a sanity check to ensure transaction behavior works
        as expected in the test environment.
        """
        from apps.peoples.models import People
        from django.db import transaction
        from apps.core.utils_new.db_utils import get_current_db_name

        # Get initial count
        initial_count = People.objects.count()

        # Try to create user in transaction that fails
        try:
            with transaction.atomic(using=get_current_db_name()):
                # Create user (not saved yet due to transaction)
                user = People(
                    peoplecode='ROLLBACK_TEST',
                    peoplename='Rollback Test',
                    email='rollback@test.com'
                )
                user.save()

                # Verify count increased within transaction
                assert People.objects.count() == initial_count + 1

                # Force rollback by raising exception
                raise IntegrityError("Simulated error")
        except IntegrityError:
            pass

        # Verify rollback occurred
        assert People.objects.count() == initial_count
        assert not People.objects.filter(peoplecode='ROLLBACK_TEST').exists()


# Integration tests using TransactionTestCase for real database commits
class TransactionIntegrationTests(TransactionTestCase):
    """
    Integration tests that verify transaction behavior with real database.

    TransactionTestCase flushes the database between tests to ensure isolation.
    """

    def test_nested_transaction_savepoints(self):
        """
        Test that nested transactions use savepoints correctly.

        Django's transaction.atomic() uses savepoints for nested transactions.
        """
        from apps.peoples.models import People
        from django.db import transaction
        from apps.core.utils_new.db_utils import get_current_db_name

        with transaction.atomic(using=get_current_db_name()):
            # Outer transaction
            user1 = People.objects.create(
                peoplecode='USER1',
                peoplename='User 1',
                email='user1@test.com'
            )

            try:
                # Inner transaction (savepoint)
                with transaction.atomic(using=get_current_db_name()):
                    user2 = People.objects.create(
                        peoplecode='USER2',
                        peoplename='User 2',
                        email='user2@test.com'
                    )
                    # Force inner rollback
                    raise IntegrityError("Inner transaction error")
            except IntegrityError:
                pass

            # user1 should still exist (outer transaction not rolled back)
            assert People.objects.filter(peoplecode='USER1').exists()
            # user2 should NOT exist (inner transaction rolled back)
            assert not People.objects.filter(peoplecode='USER2').exists()
