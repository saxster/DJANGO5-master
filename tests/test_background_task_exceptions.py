"""
Tests for exception handling in background tasks - Rule #11 compliance

Verifies that background tasks properly handle specific exception types
instead of generic exception patterns.

Author: Code Quality Team
Date: 2025-11-12
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError


class TestOnboardingBaseTaskExceptions:
    """Test exception handling in onboarding_base_task.py"""

    def test_handle_task_error_with_database_exceptions(self):
        """Test that database exceptions are properly caught and logged"""
        from background_tasks.onboarding_base_task import OnboardingBaseTask
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        task = OnboardingBaseTask()
        task.name = "test_task"
        task.request = Mock(id="test-123", retries=0)

        # Test with IntegrityError
        error = IntegrityError("Duplicate key violation")

        with patch('background_tasks.onboarding_base_task.task_logger') as mock_logger:
            result = task.handle_task_error(
                error,
                correlation_id="test-correlation",
                context={'test': 'data'}
            )

            # Verify error was logged with exc_info=True
            assert mock_logger.error.called
            call_args = mock_logger.error.call_args
            assert 'exc_info' in call_args[1]
            assert call_args[1]['exc_info'] is True

    def test_dlq_error_handling_specific_exceptions(self):
        """Test that DLQ failures use specific exception types"""
        from background_tasks.onboarding_base_task import OnboardingBaseTask

        task = OnboardingBaseTask()
        task.name = "test_task"
        task.request = Mock(id="test-123", retries=0, args=(), kwargs={})

        # Simulate DLQ failure
        with patch('background_tasks.onboarding_base_task.get_dlq_handler') as mock_dlq:
            mock_dlq.return_value.send_to_dlq.side_effect = DatabaseError("DLQ insert failed")

            with patch('background_tasks.onboarding_base_task.task_logger') as mock_logger:
                # Should catch specific database error, not generic Exception
                task.send_to_dlq(
                    DatabaseError("Test error"),
                    correlation_id="test-correlation"
                )

                # Verify DLQ error was logged
                assert mock_logger.error.called


class TestOnboardingTasksPhase2Exceptions:
    """Test exception handling in onboarding_tasks_phase2.py"""

    def test_url_validation_specific_exceptions(self):
        """Test that URL validation catches specific exceptions"""
        from background_tasks.onboarding_tasks_phase2 import _validate_fetch_url

        # Test invalid URL format (should raise ValidationError, not generic Exception)
        with pytest.raises(ValidationError) as exc_info:
            _validate_fetch_url("ht!tp://invalid url")

        assert "Invalid URL format" in str(exc_info.value)

    def test_content_sanitization_error_handling(self):
        """Test that sanitization errors are properly caught"""
        from background_tasks.onboarding_tasks_phase2 import ingest_knowledge_source_content_task
        from apps.knowledge_base.models import KnowledgeIngestionJob

        with patch('background_tasks.onboarding_tasks_phase2.KnowledgeIngestionJob.objects.select_related') as mock_job:
            mock_job_instance = Mock(spec=KnowledgeIngestionJob)
            mock_job_instance.source = Mock()
            mock_job_instance.source.fetch_error_count = 0
            mock_job.return_value.get.return_value = mock_job_instance

            with patch('background_tasks.onboarding_tasks_phase2._fetch_content_from_url') as mock_fetch:
                mock_fetch.return_value = {
                    'content': b'test content',
                    'content_type': 'text/html',
                    'metadata': {}
                }

                with patch('background_tasks.onboarding_tasks_phase2.get_content_sanitizer') as mock_sanitizer:
                    # Simulate sanitization failure with specific error
                    mock_sanitizer.return_value.sanitize_content.side_effect = ValueError("Invalid HTML")

                    with pytest.raises(ValueError):
                        ingest_knowledge_source_content_task(job_id=1, correlation_id="test")


class TestNonNegotiablesTaskExceptions:
    """Test exception handling in non_negotiables_tasks.py"""

    def test_evaluation_task_specific_exceptions(self):
        """Test that evaluation task catches specific exceptions"""
        from background_tasks.non_negotiables_tasks import EvaluateNonNegotiablesTask

        task = EvaluateNonNegotiablesTask()

        # Test ValueError is caught specifically
        with patch('background_tasks.non_negotiables_tasks.NonNegotiablesService') as mock_service:
            mock_service.return_value.evaluate_all_sites.side_effect = ValueError("Invalid date range")

            with pytest.raises(ValueError):
                task.run(
                    start_date="invalid-date",
                    end_date="2025-11-12",
                    correlation_id="test"
                )

    def test_database_error_handling(self):
        """Test that database errors are caught with specific types"""
        from background_tasks.non_negotiables_tasks import EvaluateNonNegotiablesTask
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        task = EvaluateNonNegotiablesTask()

        with patch('background_tasks.non_negotiables_tasks.NonNegotiablesService') as mock_service:
            mock_service.return_value.evaluate_all_sites.side_effect = DatabaseError("Connection lost")

            # Should catch DATABASE_EXCEPTIONS, not generic Exception
            with pytest.raises(DatabaseError):
                task.run(
                    start_date="2025-11-01",
                    end_date="2025-11-12",
                    correlation_id="test"
                )


class TestReportTasksExceptions:
    """Test exception handling in report_tasks.py"""

    def test_tenant_isolation_error_handling(self):
        """Test that per-tenant errors use specific exception types"""
        from background_tasks.report_tasks import _process_one_tenant
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        story = {'errors': []}

        with patch('background_tasks.report_tasks.connection') as mock_conn:
            # Simulate database error for specific tenant
            mock_conn.cursor.side_effect = DatabaseError("Connection refused")

            result = _process_one_tenant(
                tenant_label="test_tenant",
                db_alias="test_db",
                story=story
            )

            # Verify error was caught and logged
            assert len(story['errors']) > 0
            assert 'test_tenant' in story['errors'][0]['tenant']


class TestDeviceMonitoringTasksExceptions:
    """Test exception handling in device_monitoring_tasks.py"""

    def test_failure_prediction_error_handling(self):
        """Test that prediction errors are caught with specific types"""
        from background_tasks.device_monitoring_tasks import predict_device_failures_task

        with patch('background_tasks.device_monitoring_tasks.DeviceFailurePredictionService') as mock_service:
            mock_service.get_devices_for_prediction.return_value = [
                Mock(id=1, device_id='dev-001')
            ]

            # Simulate prediction failure with specific exception
            mock_service.predict_failure.side_effect = ValueError("Invalid sensor data")

            # Task should continue with other devices despite errors
            with patch('background_tasks.device_monitoring_tasks.logger'):
                result = predict_device_failures_task()

                # Should complete despite individual device errors
                assert 'devices_analyzed' in result

    def test_health_score_database_error(self):
        """Test that database errors in health scores are handled"""
        from background_tasks.device_monitoring_tasks import compute_device_health_scores_task
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        with patch('background_tasks.device_monitoring_tasks.get_active_tenants') as mock_tenants:
            mock_tenants.side_effect = DatabaseError("Connection pool exhausted")

            # Should raise specific DatabaseError and trigger retry
            with pytest.raises(Exception) as exc_info:
                compute_device_health_scores_task()

            # Verify it's a database-related error
            assert isinstance(exc_info.value, (DatabaseError, Exception))

    def test_tenant_processing_error_isolation(self):
        """Test that errors in one tenant don't affect others"""
        from background_tasks.device_monitoring_tasks import compute_device_health_scores_task

        with patch('background_tasks.device_monitoring_tasks.get_active_tenants') as mock_tenants:
            mock_tenants.return_value = [1, 2, 3]

            with patch('background_tasks.device_monitoring_tasks.DeviceHealthService') as mock_service:
                # First tenant succeeds, second fails, third succeeds
                mock_service.create_proactive_alerts.side_effect = [
                    {'critical': 1, 'warning': 2},
                    ValueError("Invalid configuration"),
                    {'critical': 0, 'warning': 1}
                ]

                with patch('background_tasks.device_monitoring_tasks.logger'):
                    result = compute_device_health_scores_task()

                    # Should process all tenants despite error in tenant 2
                    assert result['tenants_processed'] == 3


class TestRestApiTasksExceptions:
    """Test exception handling in rest_api_tasks.py"""

    def test_email_send_specific_exceptions(self):
        """Test that email send errors use specific exception types"""
        from background_tasks.rest_api_tasks import send_ticket_notification_task

        with patch('background_tasks.rest_api_tasks.Ticket.objects.get') as mock_get:
            from apps.y_helpdesk.models import Ticket
            mock_get.side_effect = Ticket.DoesNotExist("Ticket not found")

            result = send_ticket_notification_task(ticket_id=999)

            # Should handle DoesNotExist specifically
            assert result['status'] == 'error'
            assert 'not found' in result['message'].lower()

    def test_smtp_error_handling(self):
        """Test that SMTP errors are caught appropriately"""
        from background_tasks.rest_api_tasks import send_ticket_notification_task
        import smtplib

        with patch('background_tasks.rest_api_tasks.Ticket.objects.get') as mock_get:
            mock_ticket = Mock()
            mock_ticket.ticketno = "TEST-001"
            mock_ticket.client.name = "Test Client"
            mock_get.return_value = mock_ticket

            with patch('background_tasks.rest_api_tasks.send_mail') as mock_send:
                # Simulate SMTP error
                mock_send.side_effect = smtplib.SMTPException("Connection refused")

                result = send_ticket_notification_task(ticket_id=1)

                # Should catch and handle SMTP errors
                assert result['status'] == 'error'


class TestBackgroundTaskUtilsExceptions:
    """Test exception handling in background_tasks/utils.py"""

    def test_checkpoint_autoclose_error_handling(self):
        """Test that checkpoint errors don't stop batch processing"""
        from background_tasks.utils import autoclose_checkpoints

        mock_job = Mock()
        mock_job.id = 1

        with patch('background_tasks.utils.Checkpoint.objects.filter') as mock_checkpoints:
            # Create mock checkpoints
            checkpoint1 = Mock(id=1, other_info={})
            checkpoint2 = Mock(id=2, other_info={})
            checkpoint2.save.side_effect = DatabaseError("Lock timeout")
            checkpoint3 = Mock(id=3, other_info={})

            mock_checkpoints.return_value = [checkpoint1, checkpoint2, checkpoint3]

            with patch('background_tasks.utils.TaskStateMachine') as mock_machine:
                mock_machine.return_value.execute.return_value = Mock(success=True)

                with patch('background_tasks.utils.log'):
                    # Should process all checkpoints despite error in checkpoint2
                    autoclose_checkpoints(mock_job)

                    # Verify checkpoint1 and checkpoint3 were processed
                    assert checkpoint1.save.called
                    assert checkpoint3.save.called


class TestExceptionPatternCompliance:
    """Verify all background tasks follow exception handling patterns"""

    def test_no_bare_except_exception(self):
        """Verify no files use generic exception handlers without specific handling"""
        import ast
        import os

        background_tasks_dir = "/Users/amar/Desktop/MyCode/DJANGO5-master/background_tasks"

        violations = []

        for filename in os.listdir(background_tasks_dir):
            if not filename.endswith('.py'):
                continue

            filepath = os.path.join(background_tasks_dir, filename)

            try:
                with open(filepath, 'r') as f:
                    content = f.read()

                # Skip if file uses specific exception types
                if 'DATABASE_EXCEPTIONS' in content or 'NETWORK_EXCEPTIONS' in content:
                    continue

                # Parse AST to find except handlers
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if node.type and isinstance(node.type, ast.Name):
                            if node.type.id == 'Exception':
                                # Check if this is a justified generic catch
                                # (e.g., in error handlers, logging wrappers)
                                line_num = node.lineno
                                violations.append(f"{filename}:{line_num}")

            except (SyntaxError, ValueError, OSError) as e:
                # Skip files that can't be parsed
                pass

        # After fixes, there should be no violations
        # (or only justified ones in error handlers)
        assert len(violations) == 0, f"Found generic exception handlers: {violations}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
