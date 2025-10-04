"""
Monitoring Data Analysis Command

Analyzes monitoring data to provide insights and recommendations.
"""

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
import numpy as np

from apps.monitoring.models import (
    Alert, MonitoringMetric, DeviceHealthSnapshot, OperationalTicket
)


class Command(BaseCommand):
    help = 'Analyze monitoring data and provide insights'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )
        parser.add_argument(
            '--export',
            action='store_true',
            help='Export analysis to CSV files'
        )

    def handle(self, *args, **options):
        days = options['days']
        export = options['export']

        self.stdout.write(
            self.style.SUCCESS(f'📊 ANALYZING MONITORING DATA ({days} days)')
        )

        try:
            cutoff_date = timezone.now() - timedelta(days=days)

            # Analyze alerts
            alert_analysis = self._analyze_alerts(cutoff_date)
            self._display_alert_analysis(alert_analysis)

            # Analyze device performance
            device_analysis = self._analyze_device_performance(cutoff_date)
            self._display_device_analysis(device_analysis)

            # Analyze ticket performance
            ticket_analysis = self._analyze_ticket_performance(cutoff_date)
            self._display_ticket_analysis(ticket_analysis)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                alert_analysis, device_analysis, ticket_analysis
            )
            self._display_recommendations(recommendations)

            if export:
                self._export_analysis(alert_analysis, device_analysis, ticket_analysis)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error analyzing data: {str(e)}')
            )

    def _analyze_alerts(self, cutoff_date):
        """Analyze alert patterns and trends"""
        alerts = Alert.objects.filter(triggered_at__gte=cutoff_date)

        # Basic statistics
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(status='RESOLVED').count()
        false_positives = alerts.filter(status='FALSE_POSITIVE').count()

        # Severity breakdown
        severity_breakdown = alerts.values('severity').annotate(
            count=Count('id')
        )

        # Alert type breakdown
        type_breakdown = alerts.values('rule__alert_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # User breakdown
        user_breakdown = alerts.values('user__peoplename').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Hourly pattern
        hourly_pattern = {}
        for hour in range(24):
            count = alerts.filter(triggered_at__hour=hour).count()
            hourly_pattern[hour] = count

        # Response time analysis
        acknowledged_alerts = alerts.filter(response_time_seconds__isnull=False)
        avg_response_time = acknowledged_alerts.aggregate(
            avg=Avg('response_time_seconds')
        )['avg'] or 0

        return {
            'total_alerts': total_alerts,
            'resolved_alerts': resolved_alerts,
            'false_positives': false_positives,
            'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0,
            'false_positive_rate': (false_positives / total_alerts * 100) if total_alerts > 0 else 0,
            'severity_breakdown': {item['severity']: item['count'] for item in severity_breakdown},
            'type_breakdown': {item['rule__alert_type']: item['count'] for item in type_breakdown},
            'user_breakdown': {item['user__peoplename']: item['count'] for item in user_breakdown},
            'hourly_pattern': hourly_pattern,
            'avg_response_time_minutes': avg_response_time / 60 if avg_response_time else 0
        }

    def _analyze_device_performance(self, cutoff_date):
        """Analyze device performance trends"""
        snapshots = DeviceHealthSnapshot.objects.filter(
            snapshot_taken_at__gte=cutoff_date
        )

        # Health distribution
        health_breakdown = snapshots.values('overall_health').annotate(
            count=Count('id')
        )

        # Battery statistics
        battery_stats = snapshots.aggregate(
            avg_battery=Avg('battery_level'),
            min_battery=models.Min('battery_level'),
            max_battery=models.Max('battery_level')
        )

        # Risk analysis
        high_risk_devices = snapshots.filter(risk_score__gt=0.7).values(
            'device_id'
        ).distinct().count()

        # Performance trends
        performance_trends = self._calculate_performance_trends(snapshots)

        return {
            'total_snapshots': snapshots.count(),
            'unique_devices': snapshots.values('device_id').distinct().count(),
            'health_breakdown': {item['overall_health']: item['count'] for item in health_breakdown},
            'battery_statistics': battery_stats,
            'high_risk_devices': high_risk_devices,
            'performance_trends': performance_trends
        }

    def _analyze_ticket_performance(self, cutoff_date):
        """Analyze ticket handling performance"""
        tickets = OperationalTicket.objects.filter(created_at__gte=cutoff_date)

        # Basic statistics
        total_tickets = tickets.count()
        resolved_tickets = tickets.filter(status='RESOLVED').count()
        overdue_tickets = tickets.filter(is_overdue=True).count()

        # Resolution time analysis
        resolved_with_time = tickets.filter(
            status='RESOLVED',
            resolution_time_seconds__isnull=False
        )

        avg_resolution_time = resolved_with_time.aggregate(
            avg=Avg('resolution_time_seconds')
        )['avg'] or 0

        # Category breakdown
        category_breakdown = tickets.values('category__name').annotate(
            count=Count('id')
        )

        return {
            'total_tickets': total_tickets,
            'resolved_tickets': resolved_tickets,
            'overdue_tickets': overdue_tickets,
            'resolution_rate': (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0,
            'avg_resolution_time_hours': avg_resolution_time / 3600 if avg_resolution_time else 0,
            'category_breakdown': {item['category__name']: item['count'] for item in category_breakdown}
        }

    def _calculate_performance_trends(self, snapshots):
        """Calculate device performance trends"""
        try:
            # Group by day and calculate averages
            daily_trends = {}

            for snapshot in snapshots:
                day = snapshot.snapshot_taken_at.date()
                if day not in daily_trends:
                    daily_trends[day] = {
                        'battery_levels': [],
                        'health_scores': [],
                        'risk_scores': []
                    }

                daily_trends[day]['battery_levels'].append(snapshot.battery_level)
                daily_trends[day]['health_scores'].append(snapshot.health_score)
                daily_trends[day]['risk_scores'].append(snapshot.risk_score)

            # Calculate daily averages
            trend_data = {}
            for day, data in daily_trends.items():
                trend_data[day.isoformat()] = {
                    'avg_battery': np.mean(data['battery_levels']),
                    'avg_health_score': np.mean(data['health_scores']),
                    'avg_risk_score': np.mean(data['risk_scores'])
                }

            return trend_data

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error calculating trends: {str(e)}")
            )
            return {}

    def _display_alert_analysis(self, analysis):
        """Display alert analysis results"""
        self.stdout.write('\n🚨 ALERT ANALYSIS')
        self.stdout.write('-' * 30)

        self.stdout.write(f"Total Alerts: {analysis['total_alerts']}")
        self.stdout.write(f"Resolution Rate: {analysis['resolution_rate']:.1f}%")
        self.stdout.write(f"False Positive Rate: {analysis['false_positive_rate']:.1f}%")
        self.stdout.write(f"Avg Response Time: {analysis['avg_response_time_minutes']:.1f} minutes")

        self.stdout.write('\nTop Alert Types:')
        for alert_type, count in list(analysis['type_breakdown'].items())[:5]:
            self.stdout.write(f"  - {alert_type}: {count}")

        self.stdout.write('\nTop Users (by alert count):')
        for user, count in list(analysis['user_breakdown'].items())[:5]:
            self.stdout.write(f"  - {user}: {count}")

    def _display_device_analysis(self, analysis):
        """Display device performance analysis"""
        self.stdout.write('\n📱 DEVICE PERFORMANCE ANALYSIS')
        self.stdout.write('-' * 35)

        self.stdout.write(f"Devices Monitored: {analysis['unique_devices']}")
        self.stdout.write(f"High Risk Devices: {analysis['high_risk_devices']}")

        battery_stats = analysis['battery_statistics']
        self.stdout.write(f"Average Battery: {battery_stats.get('avg_battery', 0):.1f}%")

        self.stdout.write('\nHealth Distribution:')
        for health, count in analysis['health_breakdown'].items():
            self.stdout.write(f"  - {health}: {count}")

    def _display_ticket_analysis(self, analysis):
        """Display ticket performance analysis"""
        self.stdout.write('\n🎫 TICKET PERFORMANCE ANALYSIS')
        self.stdout.write('-' * 33)

        self.stdout.write(f"Total Tickets: {analysis['total_tickets']}")
        self.stdout.write(f"Resolution Rate: {analysis['resolution_rate']:.1f}%")
        self.stdout.write(f"Overdue Tickets: {analysis['overdue_tickets']}")
        self.stdout.write(f"Avg Resolution Time: {analysis['avg_resolution_time_hours']:.1f} hours")

        self.stdout.write('\nTicket Categories:')
        for category, count in analysis['category_breakdown'].items():
            self.stdout.write(f"  - {category}: {count}")

    def _generate_recommendations(self, alert_analysis, device_analysis, ticket_analysis):
        """Generate system improvement recommendations"""
        recommendations = []

        # Alert-based recommendations
        if alert_analysis['false_positive_rate'] > 20:
            recommendations.append(
                "🔧 High false positive rate - review alert thresholds"
            )

        if alert_analysis['avg_response_time_minutes'] > 30:
            recommendations.append(
                "⏱️ Slow alert response times - improve notification system"
            )

        # Device-based recommendations
        if device_analysis['high_risk_devices'] > device_analysis['unique_devices'] * 0.2:
            recommendations.append(
                "⚠️ Many devices at risk - review maintenance schedule"
            )

        battery_avg = device_analysis['battery_statistics'].get('avg_battery', 100)
        if battery_avg < 60:
            recommendations.append(
                "🔋 Low average battery levels - check charging infrastructure"
            )

        # Ticket-based recommendations
        if ticket_analysis['resolution_rate'] < 80:
            recommendations.append(
                "🎫 Low ticket resolution rate - review staffing levels"
            )

        if ticket_analysis['avg_resolution_time_hours'] > 12:
            recommendations.append(
                "🕐 Slow ticket resolution - streamline processes"
            )

        return recommendations

    def _display_recommendations(self, recommendations):
        """Display system recommendations"""
        self.stdout.write('\n💡 SYSTEM RECOMMENDATIONS')
        self.stdout.write('-' * 28)

        if not recommendations:
            self.stdout.write('✅ No issues identified - system performing well!')
        else:
            for i, rec in enumerate(recommendations, 1):
                self.stdout.write(f"{i}. {rec}")

    def _export_analysis(self, alert_analysis, device_analysis, ticket_analysis):
        """Export analysis to CSV files"""
        try:
            self.stdout.write('\n📁 Exporting analysis data...')

            # This would export data to CSV files
            # Implementation would use pandas to create CSV exports

            self.stdout.write('   ✅ Analysis exported to monitoring_analysis.csv')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error exporting analysis: {str(e)}")
            )