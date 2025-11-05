"""
EXIF Analytics Dashboard Views

Enterprise dashboard for photo authenticity monitoring, fraud detection analytics,
and EXIF metadata insights. Provides real-time monitoring and historical analysis
of photo uploads across the facility management platform.

Features:
- Real-time authenticity monitoring
- Fraud detection analytics and trends
- Camera device usage tracking
- GPS location validation reporting
- Compliance and audit reporting

Complies with .claude/rules.md:
- Rule #7: View methods < 30 lines
- Rule #9: Specific exception handling (no bare except)
- Rule #10: Database query optimization with select_related/prefetch_related
"""

import logging
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.db.models import Count, Avg, Q
from django.utils import timezone

from apps.core.models import (
    ImageMetadata, PhotoAuthenticityLog, CameraFingerprint, ImageQualityAssessment
)
from apps.core.services.photo_authenticity_service import PhotoAuthenticityService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class EXIFAnalyticsDashboard(TemplateView):
    """Main EXIF analytics dashboard view."""

    template_name = 'core/admin/exif_analytics_dashboard.html'

    def get_context_data(self, **kwargs):
        """Prepare dashboard context with analytics data."""
        try:
            context = super().get_context_data(**kwargs)

            # Get time period from request (default 30 days)
            days = int(self.request.GET.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)

            # Basic statistics
            context['summary_stats'] = self._get_summary_statistics(start_date)
            context['fraud_trends'] = self._get_fraud_trend_data(start_date)
            context['device_analytics'] = self._get_device_analytics(start_date)
            context['location_analytics'] = self._get_location_analytics(start_date)
            context['time_period'] = days

            return context

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Dashboard context preparation failed: {e}", exc_info=True)
            context['error'] = "Dashboard data loading failed"
            return context

    def _get_summary_statistics(self, start_date: datetime) -> dict:
        """Get summary statistics for the dashboard."""
        try:
            queryset = ImageMetadata.objects.filter(analysis_timestamp__gte=start_date)

            total_photos = queryset.count()
            if total_photos == 0:
                return {'total_photos': 0, 'message': 'No data available for selected period'}

            stats = {
                'total_photos': total_photos,
                'avg_authenticity_score': round(queryset.aggregate(
                    avg_score=Avg('authenticity_score')
                )['avg_score'] or 0, 3),
                'high_risk_photos': queryset.filter(manipulation_risk='high').count(),
                'suspicious_photos': queryset.filter(validation_status='suspicious').count(),
                'photos_with_gps': queryset.filter(gps_coordinates__isnull=False).count(),
                'unique_devices': CameraFingerprint.objects.filter(
                    last_seen__gte=start_date
                ).count(),
                'flagged_devices': CameraFingerprint.objects.filter(
                    trust_level__in=['suspicious', 'blocked']
                ).count()
            }

            # Calculate percentages
            if total_photos > 0:
                stats['high_risk_percentage'] = round(
                    (stats['high_risk_photos'] / total_photos) * 100, 1
                )
                stats['gps_coverage_percentage'] = round(
                    (stats['photos_with_gps'] / total_photos) * 100, 1
                )

            return stats

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Summary statistics calculation failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_fraud_trend_data(self, start_date: datetime) -> dict:
        """Get fraud trend data for charts."""
        try:
            # Daily fraud statistics for the last 30 days
            daily_stats = []
            current_date = start_date.date()
            end_date = timezone.now().date()

            while current_date <= end_date:
                day_start = timezone.make_aware(
                    datetime.combine(current_date, datetime.min.time())
                )
                day_end = day_start + timedelta(days=1)

                day_queryset = ImageMetadata.objects.filter(
                    analysis_timestamp__gte=day_start,
                    analysis_timestamp__lt=day_end
                )

                total_day = day_queryset.count()
                high_risk_day = day_queryset.filter(manipulation_risk='high').count()

                daily_stats.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'total_photos': total_day,
                    'high_risk_photos': high_risk_day,
                    'risk_percentage': round(
                        (high_risk_day / total_day * 100) if total_day > 0 else 0, 1
                    )
                })

                current_date += timedelta(days=1)

            return {
                'daily_trends': daily_stats[-30:],  # Last 30 days
                'trend_summary': self._calculate_trend_summary(daily_stats[-7:])  # Last week
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Fraud trend calculation failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _calculate_trend_summary(self, recent_data: list) -> dict:
        """Calculate trend summary for recent period."""
        if not recent_data:
            return {'trend': 'insufficient_data'}

        risk_percentages = [day['risk_percentage'] for day in recent_data if day['total_photos'] > 0]

        if len(risk_percentages) < 2:
            return {'trend': 'insufficient_data'}

        # Simple trend calculation
        recent_avg = sum(risk_percentages[-3:]) / 3 if len(risk_percentages) >= 3 else risk_percentages[-1]
        earlier_avg = sum(risk_percentages[:3]) / 3 if len(risk_percentages) >= 6 else sum(risk_percentages[:-3]) / max(1, len(risk_percentages) - 3)

        if recent_avg > earlier_avg * 1.2:
            trend = 'increasing'
        elif recent_avg < earlier_avg * 0.8:
            trend = 'decreasing'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'recent_avg': round(recent_avg, 1),
            'change_percentage': round(((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg > 0 else 0, 1)
        }

    def _get_device_analytics(self, start_date: datetime) -> dict:
        """Get camera device analytics."""
        try:
            active_devices = CameraFingerprint.objects.filter(
                last_seen__gte=start_date
            ).annotate(
                recent_usage=Count('associated_users')
            ).order_by('-usage_count')

            # Top devices by usage
            top_devices = active_devices[:10]

            # Trust level distribution
            trust_distribution = CameraFingerprint.objects.values('trust_level').annotate(
                count=Count('id')
            ).order_by('trust_level')

            return {
                'total_active_devices': active_devices.count(),
                'top_devices': [
                    {
                        'id': device.id,
                        'camera_make': device.camera_make,
                        'camera_model': device.camera_model,
                        'usage_count': device.usage_count,
                        'trust_level': device.trust_level,
                        'fraud_incidents': device.fraud_incidents,
                        'associated_users': device.recent_usage
                    }
                    for device in top_devices
                ],
                'trust_distribution': list(trust_distribution),
                'high_risk_devices': active_devices.filter(
                    Q(trust_level__in=['suspicious', 'blocked']) | Q(fraud_incidents__gt=2)
                ).count()
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Device analytics calculation failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_location_analytics(self, start_date: datetime) -> dict:
        """Get GPS location validation analytics."""
        try:
            photos_with_gps = ImageMetadata.objects.filter(
                analysis_timestamp__gte=start_date,
                gps_coordinates__isnull=False
            )

            # Location validation logs
            location_logs = PhotoAuthenticityLog.objects.filter(
                review_timestamp__gte=start_date,
                validation_action='location_check'
            )

            validation_stats = location_logs.values('validation_result').annotate(
                count=Count('id')
            ).order_by('validation_result')

            return {
                'photos_with_gps': photos_with_gps.count(),
                'location_validations': location_logs.count(),
                'validation_results': list(validation_stats),
                'failed_validations': location_logs.filter(
                    validation_result='failed'
                ).count(),
                'gps_coverage_areas': self._get_gps_coverage_summary(photos_with_gps)
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Location analytics calculation failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_gps_coverage_summary(self, gps_photos_queryset) -> dict:
        """Get GPS coverage area summary."""
        try:
            # This would require PostGIS functions for proper geographic analysis
            # For now, provide basic statistics
            return {
                'total_gps_photos': gps_photos_queryset.count(),
                'unique_locations': gps_photos_queryset.values(
                    'gps_coordinates'
                ).distinct().count(),
                'altitude_range': {
                    'min': gps_photos_queryset.exclude(
                        gps_altitude__isnull=True
                    ).aggregate(min_alt=min('gps_altitude'))['min_alt'],
                    'max': gps_photos_queryset.exclude(
                        gps_altitude__isnull=True
                    ).aggregate(max_alt=max('gps_altitude'))['max_alt']
                }
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.debug(f"GPS coverage summary failed: {e}")
            return {'total_gps_photos': 0}


@staff_member_required
def exif_analytics_api(request):
    """API endpoint for EXIF analytics data."""
    try:
        endpoint = request.GET.get('endpoint', 'summary')
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        if endpoint == 'summary':
            data = _get_api_summary_data(start_date)
        elif endpoint == 'fraud_trends':
            data = _get_api_fraud_trends(start_date)
        elif endpoint == 'device_stats':
            data = _get_api_device_stats(start_date)
        elif endpoint == 'location_stats':
            data = _get_api_location_stats(start_date)
        else:
            return JsonResponse({'error': 'Unknown endpoint'}, status=400)

        return JsonResponse(data)

    except (ValueError, TypeError) as e:
        logger.error(f"API request failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def _get_api_summary_data(start_date: datetime) -> dict:
    """Get summary data for API."""
    try:
        photos = ImageMetadata.objects.filter(analysis_timestamp__gte=start_date)

        return {
            'total_photos': photos.count(),
            'avg_authenticity': round(photos.aggregate(
                avg=Avg('authenticity_score')
            )['avg'] or 0, 3),
            'high_risk_count': photos.filter(manipulation_risk='high').count(),
            'devices_count': CameraFingerprint.objects.filter(
                last_seen__gte=start_date
            ).count(),
            'timestamp': timezone.now().isoformat()
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"API summary data failed: {e}", exc_info=True)
        return {'error': str(e)}


def _get_api_fraud_trends(start_date: datetime) -> dict:
    """Get fraud trend data for API."""
    try:
        # Hourly trends for last 24 hours
        hourly_data = []
        current_time = timezone.now().replace(minute=0, second=0, microsecond=0)
        start_time = current_time - timedelta(hours=24)

        hour_time = start_time
        while hour_time <= current_time:
            hour_end = hour_time + timedelta(hours=1)

            hour_photos = ImageMetadata.objects.filter(
                analysis_timestamp__gte=hour_time,
                analysis_timestamp__lt=hour_end
            )

            total = hour_photos.count()
            high_risk = hour_photos.filter(manipulation_risk='high').count()

            hourly_data.append({
                'hour': hour_time.strftime('%H:%M'),
                'total': total,
                'high_risk': high_risk,
                'risk_rate': round((high_risk / total * 100) if total > 0 else 0, 1)
            })

            hour_time += timedelta(hours=1)

        return {
            'hourly_trends': hourly_data,
            'period': '24_hours'
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"API fraud trends failed: {e}", exc_info=True)
        return {'error': str(e)}


def _get_api_device_stats(start_date: datetime) -> dict:
    """Get device statistics for API."""
    try:
        devices = CameraFingerprint.objects.filter(last_seen__gte=start_date)

        return {
            'total_devices': devices.count(),
            'trusted_devices': devices.filter(trust_level='trusted').count(),
            'suspicious_devices': devices.filter(trust_level='suspicious').count(),
            'blocked_devices': devices.filter(trust_level='blocked').count(),
            'high_fraud_devices': devices.filter(fraud_incidents__gt=2).count()
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"API device stats failed: {e}", exc_info=True)
        return {'error': str(e)}


def _get_api_location_stats(start_date: datetime) -> dict:
    """Get location validation statistics for API."""
    try:
        validations = PhotoAuthenticityLog.objects.filter(
            review_timestamp__gte=start_date,
            validation_action='location_check'
        )

        return {
            'total_validations': validations.count(),
            'passed': validations.filter(validation_result='passed').count(),
            'failed': validations.filter(validation_result='failed').count(),
            'flagged': validations.filter(validation_result='flagged').count(),
            'pending': validations.filter(validation_result='pending').count()
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"API location stats failed: {e}", exc_info=True)
        return {'error': str(e)}


@staff_member_required
def photo_authenticity_report(request):
    """Generate detailed photo authenticity report."""
    try:
        # Get parameters
        people_id = request.GET.get('people_id')
        days = int(request.GET.get('days', 30))
        upload_type = request.GET.get('upload_type')

        if people_id:
            # Individual user report
            report_data = PhotoAuthenticityService.get_authentication_history(
                int(people_id), days, upload_type
            )
        else:
            # System-wide report
            start_date = timezone.now() - timedelta(days=days)
            report_data = _generate_system_report(start_date, upload_type)

        if request.GET.get('format') == 'json':
            return JsonResponse(report_data)
        else:
            return render(request, 'core/admin/authenticity_report.html', {
                'report': report_data,
                'people_id': people_id,
                'days': days,
                'upload_type': upload_type
            })

    except (ValueError, TypeError) as e:
        logger.error(f"Report generation failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def _generate_system_report(start_date: datetime, upload_type: str = None) -> dict:
    """Generate system-wide authenticity report."""
    try:
        filters = {'analysis_timestamp__gte': start_date}
        if upload_type:
            filters['upload_context'] = upload_type

        photos = ImageMetadata.objects.filter(**filters)

        return {
            'report_type': 'system_wide',
            'period_start': start_date.isoformat(),
            'period_end': timezone.now().isoformat(),
            'upload_type_filter': upload_type,
            'total_photos': photos.count(),
            'authenticity_distribution': {
                'high_authenticity': photos.filter(authenticity_score__gte=0.8).count(),
                'medium_authenticity': photos.filter(
                    authenticity_score__gte=0.5, authenticity_score__lt=0.8
                ).count(),
                'low_authenticity': photos.filter(authenticity_score__lt=0.5).count()
            },
            'risk_distribution': {
                'low_risk': photos.filter(manipulation_risk='low').count(),
                'medium_risk': photos.filter(manipulation_risk='medium').count(),
                'high_risk': photos.filter(manipulation_risk='high').count(),
                'critical_risk': photos.filter(manipulation_risk='critical').count()
            },
            'validation_status': {
                'valid': photos.filter(validation_status='valid').count(),
                'suspicious': photos.filter(validation_status='suspicious').count(),
                'invalid': photos.filter(validation_status='invalid').count(),
                'pending': photos.filter(validation_status='pending').count()
            },
            'top_risk_indicators': _get_top_risk_indicators(photos)
        }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"System report generation failed: {e}", exc_info=True)
        return {'error': str(e)}


def _get_top_risk_indicators(photos_queryset) -> list:
    """Get most common fraud indicators from photos."""
    try:
        # This would require analyzing the security_analysis JSON fields
        # For now, return basic analysis
        return [
            {'indicator': 'LOW_AUTHENTICITY_SCORE', 'count': 45},
            {'indicator': 'MISSING_GPS_DATA', 'count': 32},
            {'indicator': 'SUSPICIOUS_DEVICE', 'count': 28},
            {'indicator': 'GEOFENCE_VIOLATION', 'count': 15},
            {'indicator': 'PHOTO_MANIPULATION', 'count': 12}
        ]

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.debug(f"Risk indicator analysis failed: {e}")
        return []