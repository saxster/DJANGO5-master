"""
Validated Form Processing Mixin

Eliminates duplicated form processing patterns found in 150+ lines
across 15+ view files.

Following .claude/rules.md:
- View methods < 30 lines (Rule 8)
- Delegate to services (Rule 8)
- Specific exception handling (Rule 11)
- Transaction management
"""

import logging
from typing import Any, Dict, Optional
from django.http import JsonResponse, QueryDict
from django.db import IntegrityError, transaction
from apps.core import utils
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.utils_new.http_utils import get_clean_form_data
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)

__all__ = [
    'ValidatedFormProcessingMixin',
]


class ValidatedFormProcessingMixin:
    """
    Mixin for standardized form validation and processing.

    Handles common form processing patterns:
    - Data extraction and cleaning
    - Instance retrieval for updates
    - Form validation
    - Success/error response handling

    Usage:
        class AssetView(ValidatedFormProcessingMixin, View):
            crud_config = {...}

            def process_valid_form(self, form, request, is_create):
                # Implement business logic here
                asset = form.save(commit=False)
                asset.save()
                return {"pk": asset.id}
    """

    def process_form_post(self, request):
        """
        Process POST request with form validation.

        Handles:
        - Form data extraction
        - Create vs Update detection
        - Form validation
        - Delegates to process_valid_form() on success

        Returns:
            JsonResponse with result or errors
        """
        config = self.get_crud_config()
        is_create = True

        form_data = self.extract_form_data(request)
        pk = request.POST.get("pk")

        if pk:
            is_create = False
            instance = utils.get_model_obj(pk, request, config)
            form = self.get_form_instance(form_data, request, instance=instance)
        else:
            form = self.get_form_instance(form_data, request)

        if form.is_valid():
            return self.handle_valid_form_response(form, request, is_create)
        else:
            return self.handle_invalid_form_response(form, request, config)

    def extract_form_data(self, request) -> QueryDict:
        """
        Extract and clean form data from request.

        Handles both direct POST data and formData parameter.
        """
        if "formData" in request.POST:
            import html
            form_data = html.unescape(request.POST["formData"])
            return QueryDict(form_data)
        else:
            return get_clean_form_data(request)

    def get_form_instance(self, data, request, instance=None):
        """
        Get form instance with data.

        Args:
            data: Cleaned form data
            request: HTTP request
            instance: Model instance for updates

        Returns:
            Form instance
        """
        config = self.get_crud_config()
        form_class = config.get("form")

        if instance:
            return form_class(data, request=request, instance=instance)
        else:
            return form_class(data, request=request)

    def handle_valid_form_response(self, form, request, is_create):
        """
        Handle valid form submission.

        Calls process_valid_form() which must be implemented by subclass.
        """
        result = self.process_valid_form(form, request, is_create)

        if isinstance(result, JsonResponse):
            return result

        if isinstance(result, dict):
            return JsonResponse(result, status=200)

        return JsonResponse({"pk": result.id if hasattr(result, 'id') else None}, status=200)

    def handle_invalid_form_response(self, form, request, config):
        """Handle invalid form submission."""
        context = {"errors": form.errors}
        return utils.handle_invalid_form(request, config, context)

    def process_valid_form(self, form, request, is_create):
        """
        Process validated form data.

        MUST be implemented by subclass.

        Args:
            form: Validated form instance
            request: HTTP request
            is_create: True if creating new object, False if updating

        Returns:
            Dict with response data, model instance, or JsonResponse
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement process_valid_form()"
        )

    def get_crud_config(self) -> Dict[str, Any]:
        """Get CRUD configuration."""
        if hasattr(self, 'P'):
            return self.P
        if hasattr(self, 'params'):
            return self.params
        return self.crud_config


class StandardFormProcessingMixin(ValidatedFormProcessingMixin):
    """
    Extended mixin with standard save pattern using putils.save_userinfo().

    Use this for simple CRUD views that follow the standard pattern.
    """

    def process_valid_form(self, form, request, is_create):
        """
        Standard form processing with userinfo tracking.

        Delegates to save_model() for customization.
        """
        from apps.core.utils import handle_intergrity_error

        try:
            with transaction.atomic(using=get_current_db_name()):
                instance = self.save_model(form, request, is_create)
                instance = putils.save_userinfo(
                    instance, request.user, request.session, create=is_create
                )

                result = self.get_success_response_data(instance, request)
                return JsonResponse(result, status=200)

        except IntegrityError as e:
            model_name = self.get_crud_config().get("model").__name__
            return handle_intergrity_error(model_name)

    def save_model(self, form, request, is_create):
        """
        Save model instance.

        Override for custom save logic (e.g., setting additional fields).

        Args:
            form: Validated form
            request: HTTP request
            is_create: Whether this is a create operation

        Returns:
            Saved model instance (before userinfo tracking)
        """
        return form.save()

    def get_success_response_data(self, instance, request) -> Dict[str, Any]:
        """
        Get response data for successful save.

        Override to customize response data.

        Args:
            instance: Saved model instance
            request: HTTP request

        Returns:
            Dict with response data
        """
        return {"pk": instance.id}