"""
Base Views for Scheduling Application

This module provides base view classes that consolidate common
functionality across task and tour views.

Follows Rule 8: All view methods < 30 lines
Follows SRP: Single responsibility for each view type
"""

import json
import logging
from datetime import datetime, time, date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, QueryDict
from django.shortcuts import render, redirect
from django.views import View

from apps.scheduler.mixins.view_mixins import (
    FilterMixin,
    ErrorHandlingMixin,
    PaginationMixin
)
from apps.core.exceptions import ValidationError, DatabaseException
from apps.activity.models.job_model import Job

logger = logging.getLogger(__name__)


class BaseSchedulingView(LoginRequiredMixin, ErrorHandlingMixin, FilterMixin, View):
    """
    Base view for all scheduling operations.

    Provides common functionality including:
    - Authentication requirements
    - Error handling patterns
    - Filter extraction
    - Standard response handling
    """

    # Override in subclasses
    template_path = None
    form_class = None
    service_class = None

    def __init__(self, *args, **kwargs):
        """Initialize base scheduling view."""
        super().__init__(*args, **kwargs)
        if self.service_class:
            self.service = self.service_class()

    def get_default_initial_data(self):
        """
        Get default initial data for forms.

        Returns:
            dict: Default initial values
        """
        return {
            "starttime": time(0, 0, 0),
            "endtime": time(0, 0, 0),
            "fromdate": datetime.combine(date.today(), time(0, 0, 0)),
            "uptodate": datetime.combine(date.today(), time(23, 0, 0)) + timedelta(days=1),
        }

    def handle_form_submission(self, request, form_data, operation="create", obj_id=None):
        """
        Handle form submission with standard patterns.

        Args:
            request: HTTP request
            form_data: Validated form data
            operation: Operation type (create/update)
            obj_id: Object ID for updates

        Returns:
            JsonResponse: Success or error response
        """
        try:
            if operation == "create":
                result = self.service.create_job(
                    form_data=form_data,
                    user=request.user,
                    session=request.session
                )
            else:
                result = self.service.update_job(
                    job_id=obj_id,
                    form_data=form_data,
                    user=request.user,
                    session=request.session
                )

            obj, success = result
            if success:
                return self.handle_success_response(
                    obj,
                    success_url=self.get_success_url(obj)
                )

        except ValidationError as e:
            return self.handle_validation_error(e, request)
        except DatabaseException as e:
            return self.handle_database_error(e, request)

    def get_success_url(self, obj):
        """
        Get success URL after form submission.

        Args:
            obj: Created/updated object

        Returns:
            str: Success URL
        """
        # Override in subclasses
        return f"/operations/update/{obj.id}/"


class BaseFormView(BaseSchedulingView):
    """
    Base view for form operations (create/update).

    Handles both GET (display form) and POST (process form) requests.
    """

    def get(self, request, *args, **kwargs):
        """Display form for creation or editing."""
        pk = kwargs.get("pk")
        initial_data = self.get_default_initial_data()

        try:
            if pk:
                # Edit mode
                obj = self.service.get_by_id(pk)
                form = self.form_class(
                    instance=obj,
                    initial=initial_data,
                    request=request
                )
                context = self.get_edit_context(form, obj)
            else:
                # Create mode
                form = self.form_class(
                    request=request,
                    initial=initial_data
                )
                context = self.get_create_context(form)

            return render(request, self.template_path, context)

        except ValidationError:
            messages.error(request, "Object not found", "alert alert-danger")
            return redirect(self.get_create_url())

    def post(self, request, *args, **kwargs):
        """Handle form submission."""
        logger.info(f"{self.__class__.__name__} form submitted")

        pk = kwargs.get("pk") or request.POST.get("pk")
        form_data = self.extract_form_data(request)

        form = self.get_form_instance(form_data, pk, request)

        if form.is_valid():
            return self.handle_valid_form(form, pk, request)
        return self.handle_invalid_form(form)

    def extract_form_data(self, request):
        """
        Extract form data from request.

        Args:
            request: HTTP request

        Returns:
            QueryDict: Form data
        """
        return QueryDict(request.POST.get("formData", ""))

    def get_form_instance(self, form_data, pk, request):
        """
        Get form instance for validation.

        Args:
            form_data: Form data
            pk: Object primary key (for updates)
            request: HTTP request

        Returns:
            Form: Form instance
        """
        initial_data = self.get_default_initial_data()

        if pk:
            obj = self.safe_get_object(self.service.model, pk)
            return self.form_class(
                instance=obj,
                data=form_data,
                initial=initial_data,
                request=request
            )
        else:
            return self.form_class(
                data=form_data,
                initial=initial_data,
                request=request
            )

    def handle_valid_form(self, form, pk, request):
        """
        Handle valid form submission.

        Args:
            form: Validated form
            pk: Object primary key
            request: HTTP request

        Returns:
            JsonResponse: Response
        """
        operation = "update" if pk else "create"
        return self.handle_form_submission(
            request,
            form.cleaned_data,
            operation=operation,
            obj_id=pk
        )

    def handle_invalid_form(self, form):
        """
        Handle invalid form submission.

        Args:
            form: Invalid form

        Returns:
            JsonResponse: Error response
        """
        logger.warning(f"Invalid {self.__class__.__name__} form submitted")
        return JsonResponse({"errors": form.errors}, status=400)

    def get_create_context(self, form):
        """
        Get context for create mode.

        Args:
            form: Form instance

        Returns:
            dict: Template context
        """
        return {"form": form}

    def get_edit_context(self, form, obj):
        """
        Get context for edit mode.

        Args:
            form: Form instance
            obj: Object being edited

        Returns:
            dict: Template context
        """
        return {"form": form, "edit": True, "object": obj}

    def get_create_url(self):
        """Get URL for create operation."""
        # Override in subclasses
        return "/"


class BaseListView(BaseSchedulingView, PaginationMixin):
    """
    Base view for list operations.

    Handles filtering, pagination, and standard list display.
    """

    default_page_size = 50

    def get(self, request, *args, **kwargs):
        """Display filtered and paginated list."""
        logger.info(f"{self.__class__.__name__} list requested")

        try:
            filters = self.extract_filters(request.GET)
            page, page_size = self.get_pagination_params(request, self.default_page_size)

            items = self.service.get_list(
                filters=filters,
                page=page,
                page_size=page_size
            )

            context = self.get_list_context(items, page, page_size, filters)
            return render(request, self.template_path, context)

        except DatabaseException as e:
            logger.error(f"Error retrieving list: {e}")
            return render(
                request,
                self.template_path,
                self.get_error_context()
            )

    def extract_filters(self, query_params):
        """
        Extract filters specific to this view.

        Args:
            query_params: Request GET parameters

        Returns:
            dict: Extracted filters
        """
        # Use common filter extraction
        return self.extract_common_filters(query_params)

    def get_list_context(self, items, page, page_size, filters):
        """
        Get context for list template.

        Args:
            items: List items
            page: Current page
            page_size: Items per page
            filters: Applied filters

        Returns:
            dict: Template context
        """
        context = {
            "items": items,
            "filters": filters,
        }

        # Add pagination context
        pagination_context = self.get_pagination_context(page, page_size)
        context.update(pagination_context)

        return context

    def get_error_context(self):
        """Get context for error state."""
        return {"items": [], "error": True}


class BaseDetailView(BaseSchedulingView):
    """
    Base view for detail operations.

    Handles display of individual objects with related data.
    """

    def get(self, request, *args, **kwargs):
        """Display object details."""
        pk = kwargs.get("pk")
        logger.info(f"{self.__class__.__name__} detail requested for ID: {pk}")

        try:
            obj = self.service.get_by_id(pk)
            related_data = self.get_related_data(obj)

            context = self.get_detail_context(obj, related_data)
            return render(request, self.template_path, context)

        except ValidationError:
            return self.handle_not_found(request)

    def get_related_data(self, obj):
        """
        Get related data for the object.

        Args:
            obj: Main object

        Returns:
            dict: Related data
        """
        # Override in subclasses
        return {}

    def get_detail_context(self, obj, related_data):
        """
        Get context for detail template.

        Args:
            obj: Main object
            related_data: Related data

        Returns:
            dict: Template context
        """
        context = {"object": obj}
        context.update(related_data)
        return context

    def handle_not_found(self, request):
        """Handle object not found."""
        messages.error(request, "Object not found", "alert alert-danger")
        return redirect(self.get_list_url())

    def get_list_url(self):
        """Get URL for list view."""
        # Override in subclasses
        return "/"