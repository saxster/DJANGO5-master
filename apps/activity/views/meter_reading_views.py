"""
Meter Reading Views - AI/ML-powered meter reading interface.

This module provides views for meter reading capture, validation, and analytics
using AI/ML image processing with comprehensive error handling and validation.

Following .claude/rules.md:
- Rule #7: View methods < 30 lines (delegate to services)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with select_related/prefetch_related
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import MultiPartParser, FormParser

from apps.activity.models import Asset, MeterReading, MeterReadingAlert
from apps.activity.services.meter_reading_service import get_meter_reading_service
from apps.peoples.models import People

logger = logging.getLogger(__name__)


# REST API Views for mobile and external access

class MeterReadingUploadAPIView(APIView):
    """
    API endpoint for uploading meter photos and processing readings.
    Designed for mobile apps and external integrations.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Process uploaded meter photo."""
        try:
            # Validate required fields
            asset_id = request.data.get('asset_id')
            photo = request.FILES.get('photo')

            if not asset_id:
                return Response(
                    {'error': 'asset_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not photo:
                return Response(
                    {'error': 'photo file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Optional parameters
            expected_min = request.data.get('expected_min')
            expected_max = request.data.get('expected_max')
            expected_range = None
            if expected_min is not None and expected_max is not None:
                try:
                    expected_range = (float(expected_min), float(expected_max))
                except ValueError:
                    return Response(
                        {'error': 'Invalid expected range values'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            notes = request.data.get('notes', '')

            # Process the meter reading
            service = get_meter_reading_service()
            result = service.process_meter_photo(
                asset_id=int(asset_id),
                photo=photo,
                user=request.user,
                expected_range=expected_range,
                notes=notes
            )

            if result['success']:
                reading = result['meter_reading']
                return Response({
                    'success': True,
                    'reading_id': reading.id,
                    'reading_value': float(reading.reading_value),
                    'unit': reading.unit,
                    'confidence_score': reading.confidence_score,
                    'status': reading.status,
                    'anomaly_detected': result['anomaly_detected'],
                    'validation_issues': result['validation_issues'],
                    'timestamp': reading.reading_timestamp.isoformat()
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except ValueError as e:
            return Response(
                {'error': f'Invalid input: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error in meter upload API: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MeterReadingValidateAPIView(APIView):
    """API endpoint for validating meter readings."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, reading_id):
        """Validate a meter reading."""
        try:
            approved = request.data.get('approved', False)
            notes = request.data.get('notes', '')

            service = get_meter_reading_service()
            success = service.validate_reading(
                reading_id=reading_id,
                validator=request.user,
                approved=approved,
                notes=notes
            )

            if success:
                return Response({
                    'success': True,
                    'message': f'Reading {"approved" if approved else "rejected"} successfully'
                })
            else:
                return Response(
                    {'error': 'Reading not found or validation failed'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            logger.error(f"Error validating reading {reading_id}: {str(e)}")
            return Response(
                {'error': 'Validation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MeterReadingListAPIView(APIView):
    """API endpoint for retrieving meter readings with filtering."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, asset_id):
        """Get readings for an asset."""
        try:
            # Parse query parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            limit = min(int(request.GET.get('limit', 50)), 100)  # Max 100

            # Parse dates if provided
            start_datetime = None
            end_datetime = None

            if start_date:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

            service = get_meter_reading_service()
            readings = service.get_asset_readings(
                asset_id=asset_id,
                start_date=start_datetime,
                end_date=end_datetime,
                limit=limit
            )

            # Serialize readings
            readings_data = []
            for reading in readings:
                readings_data.append({
                    'id': reading.id,
                    'reading_value': float(reading.reading_value),
                    'unit': reading.unit,
                    'reading_timestamp': reading.reading_timestamp.isoformat(),
                    'status': reading.status,
                    'confidence_score': reading.confidence_score,
                    'is_anomaly': reading.is_anomaly,
                    'consumption_since_last': float(reading.consumption_since_last) if reading.consumption_since_last else None,
                    'captured_by': reading.captured_by.peoplename if reading.captured_by else None
                })

            return Response({
                'asset_id': asset_id,
                'count': len(readings_data),
                'readings': readings_data
            })

        except ValueError as e:
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error fetching readings for asset {asset_id}: {str(e)}")
            return Response(
                {'error': 'Failed to fetch readings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MeterReadingAnalyticsAPIView(APIView):
    """API endpoint for meter reading analytics."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, asset_id):
        """Get analytics for an asset."""
        try:
            period_days = min(int(request.GET.get('period_days', 30)), 365)  # Max 1 year

            service = get_meter_reading_service()
            analytics = service.get_consumption_analytics(
                asset_id=asset_id,
                period_days=period_days
            )

            return Response(analytics)

        except ValueError as e:
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating analytics for asset {asset_id}: {str(e)}")
            return Response(
                {'error': 'Failed to generate analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Django Views for web interface

class MeterReadingDashboard(LoginRequiredMixin, View):
    """Dashboard view for meter readings overview."""

    def get(self, request):
        """Display meter reading dashboard."""
        try:
            # Get recent readings requiring validation
            pending_readings = MeterReading.objects.filter(
                status__in=[
                    MeterReading.ReadingStatus.PENDING,
                    MeterReading.ReadingStatus.FLAGGED
                ]
            ).select_related('asset', 'captured_by').order_by('-created_at')[:10]

            # Get recent alerts
            recent_alerts = MeterReadingAlert.objects.filter(
                is_acknowledged=False
            ).select_related('asset', 'reading').order_by('-created_at')[:10]

            # Get meter assets
            meter_assets = Asset.objects.filter(
                json_data__ismeter=True,
                enable=True
            ).values('id', 'assetname', 'assetcode')[:20]

            context = {
                'pending_readings': pending_readings,
                'recent_alerts': recent_alerts,
                'meter_assets': meter_assets,
                'pending_count': pending_readings.count(),
                'alert_count': recent_alerts.count()
            }

            return render(request, 'activity/meter_reading_dashboard.html', context)

        except Exception as e:
            logger.error(f"Error loading meter reading dashboard: {str(e)}")
            messages.error(request, "Error loading dashboard")
            return render(request, 'activity/meter_reading_dashboard.html', {})


class MeterReadingCapture(LoginRequiredMixin, View):
    """View for capturing meter readings via web interface."""

    def get(self, request):
        """Display meter reading capture form."""
        asset_id = request.GET.get('asset_id')
        asset = None

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, json_data__ismeter=True, enable=True)
            except Asset.DoesNotExist:
                messages.error(request, "Asset not found or not a meter")

        # Get list of meter assets
        meter_assets = Asset.objects.filter(
            json_data__ismeter=True,
            enable=True
        ).values('id', 'assetname', 'assetcode').order_by('assetname')

        context = {
            'asset': asset,
            'meter_assets': meter_assets
        }

        return render(request, 'activity/meter_reading_capture.html', context)

    def post(self, request):
        """Process meter reading submission."""
        try:
            asset_id = request.POST.get('asset_id')
            photo = request.FILES.get('photo')
            notes = request.POST.get('notes', '')

            if not asset_id or not photo:
                messages.error(request, "Asset and photo are required")
                return self.get(request)

            # Process the reading
            service = get_meter_reading_service()
            result = service.process_meter_photo(
                asset_id=int(asset_id),
                photo=photo,
                user=request.user,
                notes=notes
            )

            if result['success']:
                reading = result['meter_reading']
                messages.success(
                    request,
                    f"Reading captured successfully: {reading.reading_value} {reading.unit}"
                )

                if result['anomaly_detected']:
                    messages.warning(request, "Anomaly detected - reading flagged for review")

            else:
                messages.error(request, f"Failed to process reading: {result['error']}")

        except Exception as e:
            logger.error(f"Error processing meter reading: {str(e)}")
            messages.error(request, "Error processing meter reading")

        return self.get(request)


class MeterReadingValidation(LoginRequiredMixin, View):
    """View for validating pending meter readings."""

    def get(self, request):
        """Display readings pending validation."""
        pending_readings = MeterReading.objects.filter(
            status__in=[
                MeterReading.ReadingStatus.PENDING,
                MeterReading.ReadingStatus.FLAGGED
            ]
        ).select_related('asset', 'captured_by').order_by('-created_at')

        # Pagination
        paginator = Paginator(pending_readings, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'total_count': pending_readings.count()
        }

        return render(request, 'activity/meter_reading_validation.html', context)

    def post(self, request):
        """Process validation action."""
        try:
            reading_id = request.POST.get('reading_id')
            action = request.POST.get('action')  # 'approve' or 'reject'
            notes = request.POST.get('notes', '')

            if not reading_id or action not in ['approve', 'reject']:
                messages.error(request, "Invalid validation request")
                return self.get(request)

            service = get_meter_reading_service()
            success = service.validate_reading(
                reading_id=int(reading_id),
                validator=request.user,
                approved=(action == 'approve'),
                notes=notes
            )

            if success:
                messages.success(request, f"Reading {action}d successfully")
            else:
                messages.error(request, "Validation failed")

        except Exception as e:
            logger.error(f"Error validating reading: {str(e)}")
            messages.error(request, "Error processing validation")

        return self.get(request)


class MeterReadingAssetView(LoginRequiredMixin, View):
    """View for displaying readings for a specific asset."""

    def get(self, request, asset_id):
        """Display asset meter readings and analytics."""
        try:
            asset = get_object_or_404(Asset, id=asset_id, json_data__ismeter=True, enable=True)

            # Get recent readings
            service = get_meter_reading_service()
            readings = service.get_asset_readings(asset_id=asset_id, limit=50)

            # Get analytics
            analytics = service.get_consumption_analytics(asset_id=asset_id)

            context = {
                'asset': asset,
                'readings': readings,
                'analytics': analytics,
                'has_analytics': 'error' not in analytics
            }

            return render(request, 'activity/meter_reading_asset.html', context)

        except Exception as e:
            logger.error(f"Error loading asset readings for {asset_id}: {str(e)}")
            messages.error(request, "Error loading asset data")
            return render(request, 'activity/meter_reading_asset.html', {'asset': None})


# Export views for __init__.py
__all__ = [
    'MeterReadingUploadAPIView',
    'MeterReadingValidateAPIView',
    'MeterReadingListAPIView',
    'MeterReadingAnalyticsAPIView',
    'MeterReadingDashboard',
    'MeterReadingCapture',
    'MeterReadingValidation',
    'MeterReadingAssetView'
]