"""
ML Training Platform Views - Web interface and API endpoints.

Provides comprehensive views for dataset management, labeling interface,
active learning, and feedback integration.

Following .claude/rules.md:
- Rule #7: View methods < 30 lines (delegate to services)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with select_related/prefetch_related
"""

import logging
from typing import Dict, Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.contrib import messages
from django.core.paginator import Paginator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import MultiPartParser, FormParser

from .models import TrainingDataset, TrainingExample, LabelingTask
from .services import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS
    DatasetIngestionService,
    ActiveLearningService,
    FeedbackIntegrationService
)

logger = logging.getLogger(__name__)


# Web Interface Views

class DatasetListView(LoginRequiredMixin, View):
    """Dashboard view for training datasets."""

    def get(self, request):
        """Display training datasets dashboard."""
        try:
            # Get datasets with statistics
            datasets = TrainingDataset.objects.select_related(
                'created_by'
            ).order_by('-created_at')

            # Pagination
            paginator = Paginator(datasets, 20)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            # Summary statistics
            total_datasets = datasets.count()
            active_datasets = datasets.filter(status=TrainingDataset.Status.ACTIVE.value).count()
            total_examples = TrainingExample.objects.count()
            labeled_examples = TrainingExample.objects.filter(is_labeled=True).count()

            context = {
                'page_obj': page_obj,
                'total_datasets': total_datasets,
                'active_datasets': active_datasets,
                'total_examples': total_examples,
                'labeled_examples': labeled_examples,
                'completion_rate': (labeled_examples / max(total_examples, 1)) * 100
            }

            return render(request, 'ml_training/dataset_list.html', context)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error loading dataset dashboard: {str(e, exc_info=True)}")
            messages.error(request, "Error loading dashboard")
            return render(request, 'ml_training/dataset_list.html', {})


class DatasetCreateView(LoginRequiredMixin, View):
    """View for creating new training datasets."""

    def get(self, request):
        """Display dataset creation form."""
        context = {
            'dataset_types': TrainingDataset.DatasetType.choices
        }
        return render(request, 'ml_training/dataset_create.html', context)

    def post(self, request):
        """Process dataset creation."""
        try:
            name = request.POST.get('name', '').strip()
            dataset_type = request.POST.get('dataset_type')
            description = request.POST.get('description', '').strip()
            labeling_guidelines = request.POST.get('labeling_guidelines', '').strip()

            if not name or not dataset_type:
                messages.error(request, "Name and dataset type are required")
                return self.get(request)

            service = DatasetIngestionService()
            result = service.create_dataset(
                name=name,
                dataset_type=dataset_type,
                description=description,
                created_by=request.user,
                labeling_guidelines=labeling_guidelines
            )

            if result['success']:
                messages.success(request, f"Dataset '{name}' created successfully")
                return redirect('ml_training:dataset_detail', dataset_id=result['dataset'].id)
            else:
                messages.error(request, f"Failed to create dataset: {result['error']}")

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error creating dataset: {str(e, exc_info=True)}")
            messages.error(request, "Error creating dataset")

        return self.get(request)


class DatasetDetailView(LoginRequiredMixin, View):
    """Detailed view of a training dataset."""

    def get(self, request, dataset_id):
        """Display dataset details and examples."""
        try:
            dataset = get_object_or_404(
                TrainingDataset.objects.select_related('created_by', 'last_modified_by'),
                id=dataset_id
            )

            # Get examples with pagination
            examples = TrainingExample.objects.filter(
                dataset=dataset
            ).order_by('-created_at')

            paginator = Paginator(examples, 50)
            page_number = request.GET.get('page')
            examples_page = paginator.get_page(page_number)

            # Get active labeling tasks
            active_tasks = LabelingTask.objects.filter(
                dataset=dataset,
                task_status__in=[
                    LabelingTask.TaskStatus.ASSIGNED.value,
                    LabelingTask.TaskStatus.IN_PROGRESS.value
                ]
            ).select_related('assigned_to')

            context = {
                'dataset': dataset,
                'examples_page': examples_page,
                'active_tasks': active_tasks,
                'can_upload': dataset.status == TrainingDataset.Status.ACTIVE.value
            }

            return render(request, 'ml_training/dataset_detail.html', context)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error loading dataset detail: {str(e, exc_info=True)}")
            messages.error(request, "Error loading dataset")
            return redirect('ml_training:dataset_list')


class DatasetUploadView(LoginRequiredMixin, View):
    """View for uploading training data to a dataset."""

    def get(self, request, dataset_id):
        """Display upload form."""
        dataset = get_object_or_404(TrainingDataset, id=dataset_id)
        context = {'dataset': dataset}
        return render(request, 'ml_training/dataset_upload.html', context)

    def post(self, request, dataset_id):
        """Process bulk image upload."""
        try:
            dataset = get_object_or_404(TrainingDataset, id=dataset_id)
            image_files = request.FILES.getlist('images')

            if not image_files:
                messages.error(request, "No images selected for upload")
                return self.get(request, dataset_id)

            service = DatasetIngestionService()
            result = service.bulk_upload_images(
                dataset=dataset,
                image_files=image_files,
                uploaded_by=request.user
            )

            if result['success']:
                messages.success(
                    request,
                    f"Upload completed: {result['processed']} processed, "
                    f"{result['skipped']} skipped"
                )
                if result['errors']:
                    for error in result['errors'][:5]:  # Show first 5 errors
                        messages.warning(request, error)
            else:
                messages.error(request, "Upload failed")

            return redirect('ml_training:dataset_detail', dataset_id=dataset.id)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error processing upload: {str(e, exc_info=True)}")
            messages.error(request, "Upload processing failed")
            return self.get(request, dataset_id)


class LabelingDashboard(LoginRequiredMixin, View):
    """Dashboard for labeling tasks and progress."""

    def get(self, request):
        """Display labeling dashboard."""
        try:
            # Get user's assigned tasks
            assigned_tasks = LabelingTask.objects.filter(
                assigned_to=request.user
            ).select_related('dataset').order_by('-priority', '-assigned_at')

            # Get pending examples for labeling
            pending_examples = TrainingExample.objects.filter(
                selected_for_labeling=True,
                is_labeled=False
            ).select_related('dataset').order_by('-labeling_priority')[:20]

            context = {
                'assigned_tasks': assigned_tasks[:10],
                'pending_examples': pending_examples,
                'total_assigned': assigned_tasks.count(),
                'pending_count': pending_examples.count()
            }

            return render(request, 'ml_training/labeling_dashboard.html', context)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error loading labeling dashboard: {str(e, exc_info=True)}")
            messages.error(request, "Error loading dashboard")
            return render(request, 'ml_training/labeling_dashboard.html', {})


class LabelingInterface(LoginRequiredMixin, View):
    """Interactive labeling interface for training examples."""

    def get(self, request, task_id):
        """Display labeling interface for a task."""
        try:
            task = get_object_or_404(
                LabelingTask.objects.select_related('dataset', 'assigned_to'),
                id=task_id
            )

            # Check assignment
            if task.assigned_to != request.user:
                messages.error(request, "You are not assigned to this task")
                return redirect('ml_training:labeling_dashboard')

            # Get examples for this task
            examples = task.examples.filter(is_labeled=False).order_by('id')
            current_example = examples.first()

            if not current_example:
                messages.info(request, "No more examples to label in this task")
                return redirect('ml_training:labeling_dashboard')

            context = {
                'task': task,
                'current_example': current_example,
                'remaining_count': examples.count(),
                'progress_percentage': task.completion_percentage
            }

            return render(request, 'ml_training/labeling_interface.html', context)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error loading labeling interface: {str(e, exc_info=True)}")
            messages.error(request, "Error loading labeling interface")
            return redirect('ml_training:labeling_dashboard')


# API Views

class DatasetAPIView(APIView):
    """API endpoint for dataset operations."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List datasets with filtering."""
        try:
            datasets = TrainingDataset.objects.all()

            # Filter by type
            dataset_type = request.GET.get('type')
            if dataset_type:
                datasets = datasets.filter(dataset_type=dataset_type)

            # Filter by status
            status_filter = request.GET.get('status')
            if status_filter:
                datasets = datasets.filter(status=status_filter)

            # Serialize datasets
            datasets_data = []
            for dataset in datasets[:50]:  # Limit to 50
                datasets_data.append({
                    'id': dataset.id,
                    'name': dataset.name,
                    'dataset_type': dataset.dataset_type,
                    'status': dataset.status,
                    'total_examples': dataset.total_examples,
                    'labeled_examples': dataset.labeled_examples,
                    'completion_percentage': dataset.completion_percentage,
                    'quality_score': dataset.quality_score,
                    'created_at': dataset.created_at.isoformat(),
                    'is_ready_for_training': dataset.is_ready_for_training
                })

            return Response({
                'datasets': datasets_data,
                'count': len(datasets_data)
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in dataset API: {str(e, exc_info=True)}")
            return Response(
                {'error': 'Failed to fetch datasets'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create new dataset via API."""
        try:
            name = request.data.get('name')
            dataset_type = request.data.get('dataset_type')
            description = request.data.get('description', '')

            if not name or not dataset_type:
                return Response(
                    {'error': 'name and dataset_type are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            service = DatasetIngestionService()
            result = service.create_dataset(
                name=name,
                dataset_type=dataset_type,
                description=description,
                created_by=request.user
            )

            if result['success']:
                dataset = result['dataset']
                return Response({
                    'success': True,
                    'dataset': {
                        'id': dataset.id,
                        'name': dataset.name,
                        'dataset_type': dataset.dataset_type,
                        'status': dataset.status
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error creating dataset via API: {str(e, exc_info=True)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkUploadAPIView(APIView):
    """API endpoint for bulk image upload."""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, dataset_id):
        """Upload multiple images to a dataset."""
        try:
            dataset = get_object_or_404(TrainingDataset, id=dataset_id)
            image_files = request.FILES.getlist('images')

            if not image_files:
                return Response(
                    {'error': 'No images provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            service = DatasetIngestionService()
            result = service.bulk_upload_images(
                dataset=dataset,
                image_files=image_files,
                uploaded_by=request.user
            )

            return Response({
                'success': result['success'],
                'processed': result['processed'],
                'skipped': result['skipped'],
                'errors': result['errors'][:10]  # Limit error list
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in bulk upload API: {str(e, exc_info=True)}")
            return Response(
                {'error': 'Upload failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CaptureFeedbackAPIView(APIView):
    """API endpoint for capturing production feedback."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Capture feedback from production corrections."""
        try:
            source_type = request.data.get('source_type')  # 'meter_reading' or 'vehicle_entry'
            source_id = request.data.get('source_id')
            corrected_value = request.data.get('corrected_value')
            correction_type = request.data.get('correction_type', 'user_correction')

            if not all([source_type, source_id, corrected_value]):
                return Response(
                    {'error': 'source_type, source_id, and corrected_value are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            service = FeedbackIntegrationService()

            if source_type == 'meter_reading':
                from apps.activity.models import MeterReading
                try:
                    meter_reading = MeterReading.objects.get(id=source_id)
                    result = service.capture_meter_reading_feedback(
                        meter_reading=meter_reading,
                        corrected_value=corrected_value,
                        corrected_by=request.user,
                        correction_type=correction_type
                    )
                except MeterReading.DoesNotExist:
                    return Response(
                        {'error': 'Meter reading not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            elif source_type == 'vehicle_entry':
                from apps.activity.models import VehicleEntry
                try:
                    vehicle_entry = VehicleEntry.objects.get(id=source_id)
                    result = service.capture_vehicle_entry_feedback(
                        vehicle_entry=vehicle_entry,
                        corrected_license_plate=corrected_value,
                        corrected_by=request.user,
                        correction_type=correction_type
                    )
                except VehicleEntry.DoesNotExist:
                    return Response(
                        {'error': 'Vehicle entry not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'error': 'Invalid source_type'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if result['success']:
                return Response({
                    'success': True,
                    'training_example_id': result['training_example'].id,
                    'dataset_id': result['dataset'].id
                })
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error capturing feedback: {str(e, exc_info=True)}")
            return Response(
                {'error': 'Feedback capture failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Placeholder views for remaining functionality
class ActiveLearningDashboard(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'ml_training/active_learning_dashboard.html', {})


class SelectLabelingBatch(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'ml_training/select_labeling_batch.html', {})


class FeedbackDashboard(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'ml_training/feedback_dashboard.html', {})


class ImportFeedbackView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'ml_training/import_feedback.html', {})


class LabelExampleAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, example_uuid):
        return Response({'success': True, 'message': 'Labeling API endpoint - to be implemented'})