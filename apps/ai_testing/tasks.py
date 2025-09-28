"""
AI Testing Celery Tasks
Automated AI analysis and periodic task execution
"""

import logging
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings
from celery import shared_task
from datetime import timedelta

from apps.core.error_handling import ErrorHandler


logger = logging.getLogger(__name__)


@shared_task(bind=True, name="ai_daily_pattern_analysis")
def ai_daily_pattern_analysis(self):
    """
    Daily AI pattern analysis task
    Runs at 6 AM to analyze patterns from the last 30 days
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            "[AI] Starting daily pattern analysis",
            extra={"correlation_id": correlation_id}
        )

        # Run pattern analysis for last 30 days
        call_command('analyze_patterns', days=30, verbosity=1)

        logger.info(
            "[AI] Daily pattern analysis completed successfully",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="Daily AI pattern analysis completed successfully",
            data={"analysis_period": "30 days", "task_type": "daily_analysis"},
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(
            f"[AI] Daily pattern analysis failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_daily_pattern_analysis",
            task_params={"analysis_period": "30 days"},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_weekly_threshold_update")
def ai_weekly_threshold_update(self):
    """
    Weekly adaptive threshold update task
    Runs on Sunday nights to update thresholds based on weekly performance data
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            "[AI] Starting weekly threshold update",
            extra={"correlation_id": correlation_id}
        )

        # Update thresholds based on last 7 days of data
        call_command('update_thresholds', metric='all', days=7, verbosity=1)

        logger.info(
            "[AI] Weekly threshold update completed successfully",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="Weekly threshold update completed successfully",
            data={"analysis_period": "7 days", "task_type": "threshold_update"},
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(
            f"[AI] Weekly threshold update failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_weekly_threshold_update",
            task_params={"analysis_period": "7 days"},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_weekly_insights_report")
def ai_weekly_insights_report(self):
    """
    Weekly AI insights report task
    Generates and emails comprehensive AI insights report to the development team
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            "[AI] Starting weekly insights report generation",
            extra={"correlation_id": correlation_id}
        )

        # Get team email from settings or use default
        team_email = getattr(settings, 'AI_INSIGHTS_TEAM_EMAIL', 'team@company.com')

        # Generate and send weekly report
        call_command(
            'ai_insights_report',
            email=team_email,
            days=7,
            format='html',
            include_details=True,
            verbosity=1
        )

        logger.info(
            "[AI] Weekly insights report sent successfully",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="Weekly AI insights report sent successfully",
            data={
                "report_period": "7 days",
                "recipients": team_email,
                "task_type": "weekly_report"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(
            f"[AI] Weekly insights report failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_weekly_insights_report",
            task_params={"report_period": "7 days"},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_emergency_analysis")
def ai_emergency_analysis(self, trigger_reason="manual"):
    """
    Emergency AI analysis task
    Can be triggered manually or automatically when critical anomalies are detected
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            f"[AI] Starting emergency analysis - triggered by: {trigger_reason}",
            extra={"correlation_id": correlation_id}
        )

        # Run immediate pattern analysis on last 3 days for quick insights
        call_command(
            'analyze_patterns',
            days=3,
            min_confidence=0.8,  # Higher confidence for emergency analysis
            force_refresh=True,
            verbosity=2
        )

        # Generate high-priority tests if critical gaps found
        call_command(
            'generate_tests',
            priority='critical',
            max_count=10,
            update_status=True,
            verbosity=1
        )

        # Send immediate alert report if emergency threshold reached
        emergency_email = getattr(settings, 'AI_EMERGENCY_EMAIL', 'alerts@company.com')

        call_command(
            'ai_insights_report',
            email=emergency_email,
            days=3,
            format='html',
            subject_prefix='URGENT: AI Testing Alert',
            include_details=True,
            verbosity=1
        )

        logger.info(
            "[AI] Emergency analysis completed successfully",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="Emergency AI analysis completed successfully",
            data={
                "trigger_reason": trigger_reason,
                "analysis_period": "3 days",
                "task_type": "emergency_analysis"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(
            f"[AI] Emergency analysis failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_emergency_analysis",
            task_params={"trigger_reason": trigger_reason},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_cleanup_old_data")
def ai_cleanup_old_data(self, days_to_keep=90):
    """
    Cleanup old AI testing data
    Removes old coverage gaps, patterns, and predictions to keep database lean
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            f"[AI] Starting cleanup of data older than {days_to_keep} days",
            extra={"correlation_id": correlation_id}
        )

        from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap, TestCoveragePattern
        from apps.ai_testing.models.regression_predictions import RegressionPrediction

        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Cleanup dismissed coverage gaps
        dismissed_gaps = TestCoverageGap.objects.filter(
            status='dismissed',
            updated_at__lt=cutoff_date
        )
        dismissed_count = dismissed_gaps.count()
        dismissed_gaps.delete()

        # Cleanup old patterns with low confidence
        old_patterns = TestCoveragePattern.objects.filter(
            is_active=False,
            last_seen__lt=cutoff_date
        )
        patterns_count = old_patterns.count()
        old_patterns.delete()

        # Cleanup old regression predictions
        old_predictions = RegressionPrediction.objects.filter(
            created_at__lt=cutoff_date
        )
        predictions_count = old_predictions.count()
        old_predictions.delete()

        total_cleaned = dismissed_count + patterns_count + predictions_count

        logger.info(
            f"[AI] Cleanup completed - removed {total_cleaned} old records",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message=f"AI data cleanup completed - removed {total_cleaned} old records",
            data={
                "dismissed_gaps": dismissed_count,
                "old_patterns": patterns_count,
                "old_predictions": predictions_count,
                "days_to_keep": days_to_keep
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(
            f"[AI] Data cleanup failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_cleanup_old_data",
            task_params={"days_to_keep": days_to_keep},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_batch_test_generation")
def ai_batch_test_generation(self, priority="high", max_count=25):
    """
    Batch test generation task
    Automatically generates tests for high-priority coverage gaps
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            f"[AI] Starting batch test generation for {priority} priority gaps",
            extra={"correlation_id": correlation_id}
        )

        # Generate tests for specified priority
        call_command(
            'generate_tests',
            priority=priority,
            max_count=max_count,
            update_status=True,
            verbosity=1
        )

        logger.info(
            f"[AI] Batch test generation completed for {priority} priority",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message=f"Batch test generation completed for {priority} priority gaps",
            data={
                "priority": priority,
                "max_count": max_count,
                "task_type": "batch_generation"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(
            f"[AI] Batch test generation failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_batch_test_generation",
            task_params={"priority": priority, "max_count": max_count},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_health_check")
def ai_health_check(self):
    """
    AI system health check task
    Monitors AI system health and sends alerts if issues detected
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            "[AI] Starting AI system health check",
            extra={"correlation_id": correlation_id}
        )

        from apps.ai_testing.dashboard_integration import get_ai_insights_summary

        # Get current AI insights
        insights = get_ai_insights_summary()
        health_score = insights['health_score']

        # Health check thresholds
        critical_threshold = 60  # Below 60% is critical
        warning_threshold = 75   # Below 75% is warning

        status = "healthy"
        alert_needed = False

        if health_score < critical_threshold:
            status = "critical"
            alert_needed = True
        elif health_score < warning_threshold:
            status = "warning"
            alert_needed = True

        # Send alert if needed
        if alert_needed:
            alert_email = getattr(settings, 'AI_HEALTH_ALERT_EMAIL', 'alerts@company.com')

            try:
                call_command(
                    'ai_insights_report',
                    email=alert_email,
                    days=1,
                    format='html',
                    subject_prefix=f'AI Health Alert - {status.upper()}',
                    include_details=True,
                    verbosity=0
                )
                logger.warning(
                    f"[AI] Health alert sent - score: {health_score}%, status: {status}",
                    extra={"correlation_id": correlation_id}
                )
            except (ValueError, TypeError) as alert_error:
                logger.error(
                    f"[AI] Failed to send health alert: {str(alert_error)}",
                    extra={"correlation_id": correlation_id}
                )

        logger.info(
            f"[AI] Health check completed - score: {health_score}%, status: {status}",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message=f"AI health check completed - {status} ({health_score}%)",
            data={
                "health_score": health_score,
                "status": status,
                "alert_sent": alert_needed,
                "critical_gaps": insights['coverage_gaps']['critical_count'],
                "task_type": "health_check"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(
            f"[AI] Health check failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_health_check",
            task_params={},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_performance_optimization")
def ai_performance_optimization(self):
    """
    Weekly AI performance optimization task
    Optimizes AI models and cleans up data for better performance
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            "[AI] Starting performance optimization",
            extra={"correlation_id": correlation_id}
        )

        # Step 1: Update thresholds for better accuracy
        call_command('update_thresholds', metric='all', days=14, verbosity=1)

        # Step 2: Cleanup old data (keep last 90 days)
        cleanup_result = ai_cleanup_old_data.apply(args=[90])

        # Step 3: Re-analyze patterns with updated thresholds
        call_command('analyze_patterns', days=7, force_refresh=True, verbosity=1)

        logger.info(
            "[AI] Performance optimization completed successfully",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="AI performance optimization completed successfully",
            data={
                "optimizations": ["threshold_update", "data_cleanup", "pattern_refresh"],
                "task_type": "performance_optimization"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(
            f"[AI] Performance optimization failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_performance_optimization",
            task_params={},
            correlation_id=correlation_id
        )


@shared_task(bind=True, name="ai_anomaly_response")
def ai_anomaly_response(self, anomaly_signature_id, severity="medium"):
    """
    Automated response to anomaly detection
    Triggered when new anomalies are detected to run immediate analysis
    """
    correlation_id = ErrorHandler.generate_correlation_id()

    try:
        logger.info(
            f"[AI] Starting anomaly response analysis for signature {anomaly_signature_id}",
            extra={"correlation_id": correlation_id}
        )

        # Run targeted analysis if high severity
        if severity in ['critical', 'error']:
            # Emergency analysis with higher confidence threshold
            emergency_result = ai_emergency_analysis.apply(args=["anomaly_detection"])

            logger.info(
                f"[AI] Emergency analysis triggered for {severity} anomaly",
                extra={"correlation_id": correlation_id}
            )

        # Always run standard pattern analysis to update coverage gaps
        call_command(
            'analyze_patterns',
            days=1,  # Just today for immediate response
            min_confidence=0.7,
            verbosity=1
        )

        logger.info(
            "[AI] Anomaly response analysis completed",
            extra={"correlation_id": correlation_id}
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="Anomaly response analysis completed successfully",
            data={
                "anomaly_signature_id": anomaly_signature_id,
                "severity": severity,
                "emergency_triggered": severity in ['critical', 'error'],
                "task_type": "anomaly_response"
            },
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(
            f"[AI] Anomaly response analysis failed: {str(e)}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        return ErrorHandler.handle_task_exception(
            e,
            task_name="ai_anomaly_response",
            task_params={
                "anomaly_signature_id": anomaly_signature_id,
                "severity": severity
            },
            correlation_id=correlation_id
        )