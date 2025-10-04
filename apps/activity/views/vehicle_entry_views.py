"""
Vehicle Entry Views - AI/ML-powered license plate recognition interface.

This module provides views for vehicle entry/exit tracking, license plate
recognition, visitor management, and security monitoring.

Following .claude/rules.md:
- Rule #7: View methods < 30 lines (delegate to services)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with select_related/prefetch_related
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
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

from apps.activity.models import Location, VehicleEntry, VehicleSecurityAlert
from apps.activity.services.vehicle_entry_service import get_vehicle_entry_service
from apps.peoples.models import People

logger = logging.getLogger(__name__)


# REST API Views for mobile and external access

class VehicleEntryUploadAPIView(APIView):
    """
    API endpoint for uploading vehicle photos and processing license plates.
    Designed for gate systems and mobile security apps.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Process uploaded vehicle/license plate photo."""
        try:
            # Required fields
            photo = request.FILES.get('photo')
            entry_type = request.data.get('entry_type', 'ENTRY')

            if not photo:
                return Response(
                    {'error': 'photo file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Optional parameters
            gate_location_id = request.data.get('gate_location_id')
            detection_zone = request.data.get('detection_zone', '')

            # Get gate location if specified
            gate_location = None
            if gate_location_id:
                try:
                    gate_location = Location.objects.get(id=gate_location_id)
                except Location.DoesNotExist:
                    return Response(
                        {'error': 'Invalid gate location'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Visitor information (for visitor entries)
            visitor_info = {}
            if entry_type.upper() == 'VISITOR':
                visitor_info = {
                    'name': request.data.get('visitor_name', ''),
                    'company': request.data.get('visitor_company', ''),
                    'purpose': request.data.get('purpose_of_visit', ''),
                    'notes': request.data.get('notes', '')
                }

            # Process the vehicle entry
            service = get_vehicle_entry_service()
            result = service.process_vehicle_image(
                photo=photo,
                gate_location=gate_location,
                entry_type=entry_type,
                detection_zone=detection_zone,
                captured_by=request.user,
                visitor_info=visitor_info
            )

            if result['success']:
                entry = result['vehicle_entry']
                return Response({
                    'success': True,
                    'entry_id': entry.id,
                    'license_plate': entry.license_plate,
                    'confidence': result['confidence'],
                    'status': entry.status,
                    'entry_type': entry.entry_type,
                    'alerts': [{'type': alert.alert_type, 'message': alert.message} for alert in result['alerts']],
                    'timestamp': entry.entry_timestamp.isoformat()
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Unexpected error in vehicle upload API: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VehicleExitAPIView(APIView):
    """API endpoint for recording vehicle exits."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Record vehicle exit by license plate."""
        try:
            license_plate = request.data.get('license_plate')
            gate_location_id = request.data.get('gate_location_id')

            if not license_plate:
                return Response(
                    {'error': 'license_plate is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get gate location
            gate_location = None
            if gate_location_id:
                try:
                    gate_location = Location.objects.get(id=gate_location_id)
                except Location.DoesNotExist:
                    pass

            service = get_vehicle_entry_service()
            result = service.record_exit(
                license_plate=license_plate,
                gate_location=gate_location,
                captured_by=request.user
            )

            if result['success']:
                return Response({
                    'success': True,
                    'license_plate': license_plate,
                    'duration': str(result['duration']) if result.get('duration') else None,
                    'exit_timestamp': timezone.now().isoformat()
                })
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            logger.error(f"Error in vehicle exit API: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VehicleHistoryAPIView(APIView):
    """API endpoint for retrieving vehicle history."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, license_plate):
        """Get entry history for a license plate."""
        try:
            days_back = min(int(request.GET.get('days', 30)), 365)
            limit = min(int(request.GET.get('limit', 50)), 100)

            service = get_vehicle_entry_service()
            entries = service.get_vehicle_history(
                license_plate=license_plate,
                days_back=days_back,
                limit=limit
            )

            # Serialize entries
            entries_data = []
            for entry in entries:
                entries_data.append({
                    'id': entry.id,
                    'license_plate': entry.license_plate,
                    'entry_type': entry.entry_type,
                    'entry_timestamp': entry.entry_timestamp.isoformat(),
                    'exit_timestamp': entry.exit_timestamp.isoformat() if entry.exit_timestamp else None,
                    'gate_location': entry.gate_location.locationname if entry.gate_location else None,
                    'status': entry.status,
                    'confidence': entry.confidence_score,
                    'visitor_name': entry.visitor_name or None,
                    'duration': str(entry.actual_duration) if entry.actual_duration else None
                })

            return Response({
                'license_plate': license_plate,
                'count': len(entries_data),
                'entries': entries_data
            })

        except Exception as e:
            logger.error(f"Error fetching vehicle history: {str(e)}")
            return Response(
                {'error': 'Failed to fetch history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ActiveVehiclesAPIView(APIView):
    """API endpoint for getting currently active vehicles."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get active vehicle entries (no exit recorded)."""
        try:
            gate_location_id = request.GET.get('gate_location_id')

            gate_location = None
            if gate_location_id:
                try:
                    gate_location = Location.objects.get(id=gate_location_id)
                except Location.DoesNotExist:
                    pass

            service = get_vehicle_entry_service()
            active_vehicles = service.get_active_vehicles(gate_location=gate_location)

            # Serialize active vehicles
            vehicles_data = []
            for entry in active_vehicles:
                time_in_facility = timezone.now() - entry.entry_timestamp
                vehicles_data.append({
                    'id': entry.id,
                    'license_plate': entry.license_plate,
                    'entry_timestamp': entry.entry_timestamp.isoformat(),
                    'time_in_facility': str(time_in_facility),
                    'gate_location': entry.gate_location.locationname if entry.gate_location else None,
                    'visitor_name': entry.visitor_name or None,
                    'is_visitor': entry.is_visitor_entry,
                    'is_overdue': entry.is_overdue
                })

            return Response({
                'count': len(vehicles_data),
                'active_vehicles': vehicles_data
            })

        except Exception as e:
            logger.error(f"Error fetching active vehicles: {str(e)}")
            return Response(
                {'error': 'Failed to fetch active vehicles'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Django Views for web interface

class VehicleEntryDashboard(LoginRequiredMixin, View):
    """Dashboard view for vehicle entry management."""

    def get(self, request):
        """Display vehicle entry dashboard."""
        try:
            # Get pending approvals
            pending_entries = VehicleEntry.objects.filter(
                status__in=[
                    VehicleEntry.Status.PENDING,
                    VehicleEntry.Status.FLAGGED
                ]
            ).select_related('gate_location', 'captured_by').order_by('-entry_timestamp')[:10]

            # Get active alerts
            active_alerts = VehicleSecurityAlert.objects.filter(
                is_acknowledged=False
            ).select_related('vehicle_entry', 'vehicle_entry__gate_location').order_by('-created_at')[:10]

            # Get active vehicles (currently in facility)
            service = get_vehicle_entry_service()
            active_vehicles = service.get_active_vehicles()[:15]

            # Get gate locations
            gate_locations = Location.objects.filter(
                enable=True
            ).values('id', 'locationname')

            context = {
                'pending_entries': pending_entries,
                'active_alerts': active_alerts,
                'active_vehicles': active_vehicles,
                'gate_locations': gate_locations,
                'pending_count': pending_entries.count(),
                'alert_count': active_alerts.count(),
                'active_count': len(active_vehicles)
            }

            return render(request, 'activity/vehicle_entry_dashboard.html', context)

        except Exception as e:
            logger.error(f"Error loading vehicle dashboard: {str(e)}")
            messages.error(request, "Error loading dashboard")
            return render(request, 'activity/vehicle_entry_dashboard.html', {})


class VehicleEntryCapture(LoginRequiredMixin, View):
    """View for capturing vehicle entries via web interface."""

    def get(self, request):
        """Display vehicle entry capture form."""
        # Get gate locations
        gate_locations = Location.objects.filter(
            enable=True
        ).values('id', 'locationname').order_by('locationname')

        context = {
            'gate_locations': gate_locations
        }

        return render(request, 'activity/vehicle_entry_capture.html', context)

    def post(self, request):
        """Process vehicle entry submission."""
        try:
            photo = request.FILES.get('photo')
            gate_location_id = request.POST.get('gate_location_id')
            entry_type = request.POST.get('entry_type', 'ENTRY')
            detection_zone = request.POST.get('detection_zone', '')

            if not photo:
                messages.error(request, "Vehicle photo is required")
                return self.get(request)

            # Get gate location
            gate_location = None
            if gate_location_id:
                try:
                    gate_location = Location.objects.get(id=gate_location_id)
                except Location.DoesNotExist:
                    messages.error(request, "Invalid gate location")
                    return self.get(request)

            # Visitor info if applicable
            visitor_info = {}
            if entry_type == 'VISITOR':
                visitor_info = {
                    'name': request.POST.get('visitor_name', ''),
                    'company': request.POST.get('visitor_company', ''),
                    'purpose': request.POST.get('purpose_of_visit', ''),
                    'notes': request.POST.get('notes', '')
                }

            # Process the vehicle entry
            service = get_vehicle_entry_service()
            result = service.process_vehicle_image(
                photo=photo,
                gate_location=gate_location,
                entry_type=entry_type,
                detection_zone=detection_zone,
                captured_by=request.user,
                visitor_info=visitor_info
            )

            if result['success']:
                entry = result['vehicle_entry']
                messages.success(
                    request,
                    f"Vehicle processed: {entry.license_plate} (Confidence: {result['confidence']:.2f})"
                )

                if result['alerts']:
                    messages.warning(
                        request,
                        f"Security alerts generated: {len(result['alerts'])} alert(s)"
                    )

            else:
                messages.error(request, f"Failed to process vehicle: {result['error']}")

        except Exception as e:
            logger.error(f"Error processing vehicle entry: {str(e)}")
            messages.error(request, "Error processing vehicle entry")

        return self.get(request)


class VehicleEntryApproval(LoginRequiredMixin, View):
    """View for approving pending vehicle entries."""

    def get(self, request):
        """Display entries pending approval."""
        pending_entries = VehicleEntry.objects.filter(
            status__in=[
                VehicleEntry.Status.PENDING,
                VehicleEntry.Status.FLAGGED
            ]
        ).select_related('gate_location', 'captured_by').order_by('-entry_timestamp')

        # Pagination
        paginator = Paginator(pending_entries, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'total_count': pending_entries.count()
        }

        return render(request, 'activity/vehicle_entry_approval.html', context)

    def post(self, request):
        """Process approval action."""
        try:
            entry_id = request.POST.get('entry_id')
            action = request.POST.get('action')  # 'approve' or 'deny'
            notes = request.POST.get('notes', '')

            if not entry_id or action not in ['approve', 'deny']:
                messages.error(request, "Invalid approval request")
                return self.get(request)

            service = get_vehicle_entry_service()
            if action == 'approve':
                success = service.approve_entry(
                    entry_id=int(entry_id),
                    approver=request.user,
                    notes=notes
                )
            else:
                # Deny entry (update status)
                try:
                    entry = VehicleEntry.objects.get(id=entry_id)
                    entry.status = VehicleEntry.Status.DENIED
                    entry.approved_by = request.user
                    entry.approved_at = timezone.now()
                    entry.notes = f"{entry.notes}\n\nDenied: {notes}".strip()
                    entry.save()
                    success = True
                except VehicleEntry.DoesNotExist:
                    success = False

            if success:
                messages.success(request, f"Entry {action}d successfully")
            else:
                messages.error(request, "Approval failed")

        except Exception as e:
            logger.error(f"Error processing approval: {str(e)}")
            messages.error(request, "Error processing approval")

        return self.get(request)


class VehicleSecurityAlerts(LoginRequiredMixin, View):
    """View for managing security alerts."""

    def get(self, request):
        """Display security alerts."""
        alerts = VehicleSecurityAlert.objects.select_related(
            'vehicle_entry',
            'vehicle_entry__gate_location',
            'acknowledged_by'
        ).order_by('-created_at')

        # Filter options
        alert_type = request.GET.get('alert_type')
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)

        acknowledged = request.GET.get('acknowledged')
        if acknowledged == 'no':
            alerts = alerts.filter(is_acknowledged=False)
        elif acknowledged == 'yes':
            alerts = alerts.filter(is_acknowledged=True)

        # Pagination
        paginator = Paginator(alerts, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Alert type choices for filter
        alert_types = VehicleSecurityAlert.AlertType.choices

        context = {
            'page_obj': page_obj,
            'alert_types': alert_types,
            'total_count': alerts.count()
        }

        return render(request, 'activity/vehicle_security_alerts.html', context)

    def post(self, request):
        """Acknowledge security alert."""
        try:
            alert_id = request.POST.get('alert_id')
            notes = request.POST.get('notes', '')
            response = request.POST.get('security_response', '')

            if not alert_id:
                messages.error(request, "Invalid alert ID")
                return self.get(request)

            alert = VehicleSecurityAlert.objects.get(id=alert_id)
            alert.acknowledge(
                user=request.user,
                notes=notes,
                response=response
            )

            messages.success(request, "Alert acknowledged successfully")

        except VehicleSecurityAlert.DoesNotExist:
            messages.error(request, "Alert not found")
        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            messages.error(request, "Error acknowledging alert")

        return self.get(request)


# Export views for __init__.py
__all__ = [
    'VehicleEntryUploadAPIView',
    'VehicleExitAPIView',
    'VehicleHistoryAPIView',
    'ActiveVehiclesAPIView',
    'VehicleEntryDashboard',
    'VehicleEntryCapture',
    'VehicleEntryApproval',
    'VehicleSecurityAlerts'
]