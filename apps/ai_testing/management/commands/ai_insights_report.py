"""
AI Testing Management Command: AI Insights Report
Generate comprehensive AI insights reports and optionally email them to the development team
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

from apps.ai_testing.dashboard_integration import get_ai_insights_summary
from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap, TestCoveragePattern
from apps.ai_testing.models.adaptive_thresholds import AdaptiveThreshold


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate comprehensive AI insights report and optionally email to development team'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address(es) to send the report to (comma-separated for multiple)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to include in the report (default: 7)'
        )
        parser.add_argument(
            '--format',
            choices=['text', 'html', 'json'],
            default='html',
            help='Report format (default: html)'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Save report to file instead of/in addition to email'
        )
        parser.add_argument(
            '--subject-prefix',
            type=str,
            default='AI Testing Report',
            help='Email subject prefix (default: "AI Testing Report")'
        )
        parser.add_argument(
            '--include-details',
            action='store_true',
            help='Include detailed gap information and test recommendations'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Generate report without sending email'
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        email_addresses = options.get('email', '').split(',') if options.get('email') else []
        days = options['days']
        report_format = options['format']
        output_file = options.get('output_file')
        subject_prefix = options['subject_prefix']
        include_details = options['include_details']
        dry_run = options['dry_run']

        # Clean email addresses
        email_addresses = [email.strip() for email in email_addresses if email.strip()]

        self.stdout.write(
            self.style.SUCCESS('📊 Generating AI Insights Report')
        )
        self.stdout.write(f'Report period: {days} days')
        self.stdout.write(f'Format: {report_format}')

        if email_addresses and not dry_run:
            self.stdout.write(f'Recipients: {", ".join(email_addresses)}')
        elif dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No email will be sent'))

        try:
            # Step 1: Collect comprehensive insights data
            self.stdout.write('\n🔍 Collecting AI insights data...')

            report_data = self._collect_report_data(days, include_details)

            # Step 2: Generate report
            self.stdout.write(f'\n📝 Generating {report_format.upper()} report...')

            if report_format == 'json':
                report_content = self._generate_json_report(report_data)
                content_type = 'application/json'
            elif report_format == 'text':
                report_content = self._generate_text_report(report_data)
                content_type = 'text/plain'
            else:  # html
                report_content = self._generate_html_report(report_data)
                content_type = 'text/html'

            # Step 3: Save to file if requested
            if output_file:
                self._save_report_to_file(report_content, output_file, report_format)

            # Step 4: Send email if requested
            if email_addresses and not dry_run:
                self.stdout.write('\n📧 Sending email report...')

                email_sent = self._send_email_report(
                    report_content,
                    email_addresses,
                    subject_prefix,
                    report_format,
                    report_data
                )

                if email_sent:
                    self.stdout.write('✅ Email sent successfully')
                else:
                    self.stdout.write(self.style.ERROR('❌ Failed to send email'))

            # Step 5: Display summary
            self._display_report_summary(report_data)

            # Execution time
            duration = timezone.now() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Report generation completed in {duration.total_seconds():.1f}s'
                )
            )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(f'Report generation failed: {str(e)}', exc_info=True)
            raise CommandError(f'Report generation failed: {str(e)}')

    def _collect_report_data(self, days, include_details):
        """Collect comprehensive data for the report"""
        since_date = timezone.now() - timedelta(days=days)
        report_date = timezone.now()

        # Get AI insights summary
        ai_insights = get_ai_insights_summary()

        # Collect detailed data
        coverage_gaps = TestCoverageGap.objects.filter(
            identified_at__gte=since_date
        ).order_by('-confidence_score', '-impact_score')

        test_runs = TestRun.objects.filter(
            started_at__gte=since_date
        ).select_related('scenario')

        anomaly_occurrences = AnomalyOccurrence.objects.filter(
            created_at__gte=since_date
        ).select_related('signature')

        patterns = TestCoveragePattern.objects.filter(
            last_seen__gte=since_date
        ).order_by('-occurrence_count')

        thresholds = AdaptiveThreshold.objects.filter(
            updated_at__gte=since_date
        ).order_by('-updated_at')

        # Calculate period statistics
        period_stats = self._calculate_period_statistics(
            coverage_gaps, test_runs, anomaly_occurrences, since_date
        )

        report_data = {
            'report_date': report_date,
            'period_days': days,
            'since_date': since_date,
            'ai_insights': ai_insights,
            'coverage_gaps': {
                'total': coverage_gaps.count(),
                'by_priority': self._group_by_field(coverage_gaps, 'priority'),
                'by_type': self._group_by_field(coverage_gaps, 'coverage_type'),
                'by_status': self._group_by_field(coverage_gaps, 'status'),
                'list': list(coverage_gaps[:10]) if include_details else []
            },
            'test_runs': {
                'total': test_runs.count(),
                'successful': test_runs.filter(status='completed').count(),
                'failed': test_runs.filter(status='failed').count(),
                'average_duration': self._calculate_average_duration(test_runs),
                'performance_summary': self._calculate_performance_summary(test_runs)
            },
            'anomalies': {
                'total': anomaly_occurrences.count(),
                'unique_signatures': anomaly_occurrences.values('signature').distinct().count(),
                'by_severity': self._group_anomalies_by_severity(anomaly_occurrences),
                'top_patterns': list(patterns[:5]) if include_details else []
            },
            'thresholds': {
                'updated_count': thresholds.count(),
                'metrics_tracked': thresholds.values('metric_name').distinct().count(),
                'average_accuracy': self._calculate_average_accuracy(thresholds),
                'details': list(thresholds[:10]) if include_details else []
            },
            'period_stats': period_stats,
            'recommendations': self._generate_recommendations(ai_insights, coverage_gaps, period_stats)
        }

        return report_data

    def _group_by_field(self, queryset, field):
        """Group queryset by field and count"""
        return dict(
            queryset.values(field).annotate(count=models.Count('id')).values_list(field, 'count')
        )

    def _group_anomalies_by_severity(self, anomaly_occurrences):
        """Group anomalies by severity"""
        severity_counts = {}
        for occurrence in anomaly_occurrences:
            severity = occurrence.signature.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    def _calculate_average_duration(self, test_runs):
        """Calculate average test run duration"""
        completed_runs = test_runs.filter(status='completed', duration_seconds__isnull=False)
        if not completed_runs.exists():
            return 0

        total_duration = sum(run.duration_seconds for run in completed_runs)
        return total_duration / completed_runs.count()

    def _calculate_performance_summary(self, test_runs):
        """Calculate performance summary statistics"""
        completed_runs = test_runs.filter(status='completed')

        if not completed_runs.exists():
            return {}

        latencies = [run.p95_latency_ms for run in completed_runs if run.p95_latency_ms]
        throughputs = [run.throughput_qps for run in completed_runs if run.throughput_qps]
        error_rates = [run.error_rate for run in completed_runs if run.error_rate is not None]

        return {
            'avg_latency_ms': sum(latencies) / len(latencies) if latencies else 0,
            'avg_throughput_qps': sum(throughputs) / len(throughputs) if throughputs else 0,
            'avg_error_rate': sum(error_rates) / len(error_rates) if error_rates else 0,
            'samples': {
                'latency': len(latencies),
                'throughput': len(throughputs),
                'error_rate': len(error_rates)
            }
        }

    def _calculate_average_accuracy(self, thresholds):
        """Calculate average threshold accuracy"""
        accuracies = [t.accuracy for t in thresholds if t.accuracy is not None]
        return sum(accuracies) / len(accuracies) if accuracies else 0

    def _calculate_period_statistics(self, coverage_gaps, test_runs, anomaly_occurrences, since_date):
        """Calculate period-over-period statistics"""
        # Compare with previous period
        previous_period_start = since_date - (timezone.now() - since_date)

        previous_gaps = TestCoverageGap.objects.filter(
            identified_at__gte=previous_period_start,
            identified_at__lt=since_date
        ).count()

        previous_runs = TestRun.objects.filter(
            started_at__gte=previous_period_start,
            started_at__lt=since_date
        ).count()

        previous_anomalies = AnomalyOccurrence.objects.filter(
            created_at__gte=previous_period_start,
            created_at__lt=since_date
        ).count()

        current_gaps = coverage_gaps.count()
        current_runs = test_runs.count()
        current_anomalies = anomaly_occurrences.count()

        return {
            'gaps_change': self._calculate_percentage_change(previous_gaps, current_gaps),
            'runs_change': self._calculate_percentage_change(previous_runs, current_runs),
            'anomalies_change': self._calculate_percentage_change(previous_anomalies, current_anomalies),
            'trend_direction': self._determine_trend_direction(
                previous_gaps, current_gaps, previous_anomalies, current_anomalies
            )
        }

    def _calculate_percentage_change(self, old_value, new_value):
        """Calculate percentage change between two values"""
        if old_value == 0:
            return 100 if new_value > 0 else 0

        return ((new_value - old_value) / old_value) * 100

    def _determine_trend_direction(self, prev_gaps, curr_gaps, prev_anomalies, curr_anomalies):
        """Determine overall trend direction"""
        gap_trend = 'improving' if curr_gaps < prev_gaps else 'stable' if curr_gaps == prev_gaps else 'declining'
        anomaly_trend = 'improving' if curr_anomalies < prev_anomalies else 'stable' if curr_anomalies == prev_anomalies else 'declining'

        if gap_trend == 'improving' and anomaly_trend == 'improving':
            return 'improving'
        elif gap_trend == 'declining' or anomaly_trend == 'declining':
            return 'needs_attention'
        else:
            return 'stable'

    def _generate_recommendations(self, ai_insights, coverage_gaps, period_stats):
        """Generate actionable recommendations"""
        recommendations = []

        # Coverage gap recommendations
        critical_gaps = coverage_gaps.filter(priority='critical').count()
        high_gaps = coverage_gaps.filter(priority='high').count()

        if critical_gaps > 0:
            recommendations.append({
                'type': 'critical',
                'title': f'Address {critical_gaps} Critical Coverage Gap{"s" if critical_gaps != 1 else ""}',
                'description': 'Critical gaps indicate high-risk areas that should be tested immediately',
                'action': 'Generate and implement tests for critical priority gaps'
            })

        if high_gaps > 5:
            recommendations.append({
                'type': 'high',
                'title': f'Plan Implementation for {high_gaps} High-Priority Gaps',
                'description': 'High-priority gaps should be addressed in the next sprint',
                'action': 'Schedule test implementation for high-priority coverage gaps'
            })

        # Performance recommendations
        if period_stats['trend_direction'] == 'needs_attention':
            recommendations.append({
                'type': 'warning',
                'title': 'Increasing Anomaly Pattern Detected',
                'description': 'Recent trends show increasing issues that may indicate system problems',
                'action': 'Review recent changes and consider additional monitoring'
            })

        # Threshold recommendations
        if ai_insights['threshold_status']['stale_count'] > 0:
            recommendations.append({
                'type': 'maintenance',
                'title': 'Update Adaptive Thresholds',
                'description': f'{ai_insights["threshold_status"]["stale_count"]} thresholds need updating',
                'action': 'Run: python manage.py update_thresholds --metric=all'
            })

        return recommendations

    def _generate_json_report(self, report_data):
        """Generate JSON format report"""
        # Convert non-serializable objects
        serializable_data = self._make_json_serializable(report_data)
        return json.dumps(serializable_data, indent=2, default=str)

    def _generate_text_report(self, report_data):
        """Generate plain text report"""
        lines = []
        lines.append('=' * 60)
        lines.append('AI TESTING INSIGHTS REPORT')
        lines.append('=' * 60)
        lines.append('')
        lines.append(f'Generated: {report_data["report_date"].strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append(f'Period: Last {report_data["period_days"]} days')
        lines.append('')

        # Executive Summary
        lines.append('EXECUTIVE SUMMARY')
        lines.append('-' * 20)
        lines.append(f'AI Health Score: {report_data["ai_insights"]["health_score"]}/100')
        lines.append(f'Coverage Gaps: {report_data["coverage_gaps"]["total"]}')
        lines.append(f'Test Runs: {report_data["test_runs"]["total"]}')
        lines.append(f'Anomalies: {report_data["anomalies"]["total"]}')
        lines.append('')

        # Coverage Gaps
        lines.append('COVERAGE GAPS')
        lines.append('-' * 15)
        for priority, count in report_data['coverage_gaps']['by_priority'].items():
            lines.append(f'{priority.title()}: {count}')
        lines.append('')

        # Recommendations
        if report_data['recommendations']:
            lines.append('RECOMMENDATIONS')
            lines.append('-' * 15)
            for i, rec in enumerate(report_data['recommendations'], 1):
                lines.append(f'{i}. {rec["title"]}')
                lines.append(f'   {rec["description"]}')
                lines.append(f'   Action: {rec["action"]}')
                lines.append('')

        return '\n'.join(lines)

    def _generate_html_report(self, report_data):
        """Generate HTML format report"""
        # This would use a Django template, but for simplicity, we'll generate HTML directly
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Testing Insights Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ background: #007bff; color: white; padding: 20px; text-align: center; }}
                .summary {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .metric {{ text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
                .metric-value {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
                .recommendations {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; }}
                .critical {{ color: #dc3545; }}
                .warning {{ color: #fd7e14; }}
                .success {{ color: #28a745; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🤖 AI Testing Insights Report</h1>
                <p>Generated on {report_data["report_date"].strftime("%B %d, %Y at %H:%M")}</p>
                <p>Period: Last {report_data["period_days"]} days</p>
            </div>

            <div class="summary">
                <div class="metric">
                    <div class="metric-value">{report_data["ai_insights"]["health_score"]}</div>
                    <div>AI Health Score</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report_data["coverage_gaps"]["total"]}</div>
                    <div>Coverage Gaps</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report_data["test_runs"]["total"]}</div>
                    <div>Test Runs</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report_data["anomalies"]["total"]}</div>
                    <div>Anomalies Detected</div>
                </div>
            </div>

            <h2>📊 Coverage Gaps Analysis</h2>
            <p>Total gaps identified: <strong>{report_data["coverage_gaps"]["total"]}</strong></p>

            <h3>By Priority:</h3>
            <ul>
        '''

        for priority, count in report_data['coverage_gaps']['by_priority'].items():
            css_class = 'critical' if priority == 'critical' else 'warning' if priority == 'high' else ''
            html += f'<li class="{css_class}"><strong>{priority.title()}:</strong> {count}</li>'

        html += '''
            </ul>

            <h2>🚨 Recommendations</h2>
            <div class="recommendations">
        '''

        if report_data['recommendations']:
            html += '<ol>'
            for rec in report_data['recommendations']:
                css_class = rec['type']
                html += f'''
                <li class="{css_class}">
                    <strong>{rec["title"]}</strong><br>
                    {rec["description"]}<br>
                    <em>Action: {rec["action"]}</em>
                </li>
                '''
            html += '</ol>'
        else:
            html += '<p>No specific recommendations at this time. System is performing well!</p>'

        html += '''
            </div>

            <hr>
            <p><small>Generated by AI Testing Platform -
            <a href="/streamlab/">View Dashboard</a></small></p>
        </body>
        </html>
        '''

        return html

    def _make_json_serializable(self, data):
        """Convert data to JSON serializable format"""
        if isinstance(data, dict):
            return {key: self._make_json_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._make_json_serializable(item) for item in data]
        elif hasattr(data, '__dict__'):
            return str(data)  # Convert model instances to string
        else:
            return data

    def _save_report_to_file(self, content, filepath, report_format):
        """Save report content to file"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        mode = 'w' if report_format in ['text', 'html'] else 'w'
        encoding = 'utf-8'

        with open(path, mode, encoding=encoding) as f:
            f.write(content)

        self.stdout.write(f'📁 Report saved to: {filepath}')

    def _send_email_report(self, content, email_addresses, subject_prefix, report_format, report_data):
        """Send report via email"""
        try:
            subject = f'{subject_prefix} - {report_data["report_date"].strftime("%Y-%m-%d")}'

            if report_format == 'html':
                # Send HTML email
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body='Please view this email in HTML format.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=email_addresses
                )
                msg.attach_alternative(content, "text/html")
                msg.send()
            else:
                # Send plain text email
                send_mail(
                    subject=subject,
                    message=content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=email_addresses,
                    fail_silently=False
                )

            return True

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f'Failed to send email report: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Email error: {str(e)}'))
            return False

    def _display_report_summary(self, report_data):
        """Display report summary to console"""
        self.stdout.write('\n📈 Report Summary:')
        self.stdout.write(f'  🎯 AI Health Score: {report_data["ai_insights"]["health_score"]}/100')
        self.stdout.write(f'  📋 Coverage Gaps: {report_data["coverage_gaps"]["total"]}')
        self.stdout.write(f'  🧪 Test Runs: {report_data["test_runs"]["total"]}')
        self.stdout.write(f'  🚨 Anomalies: {report_data["anomalies"]["total"]}')

        if report_data['recommendations']:
            self.stdout.write(f'  💡 Recommendations: {len(report_data["recommendations"])}')

            # Show critical recommendations
            critical_recs = [r for r in report_data['recommendations'] if r['type'] == 'critical']
            if critical_recs:
                self.stdout.write(self.style.ERROR(f'  ⚠️  Critical Actions Needed: {len(critical_recs)}'))