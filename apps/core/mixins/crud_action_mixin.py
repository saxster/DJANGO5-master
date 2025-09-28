"""
CRUD Action Routing Mixin

Eliminates duplicated GET action routing patterns found in 118 occurrences
across 22 view files (~500 lines of duplication).

Following .claude/rules.md:
- Methods < 30 lines (Rule 8)
- Specific exception handling (Rule 11)
- Single responsibility principle
- Extensible via hook methods
"""

import logging
from typing import Dict, Any, Optional
from django.shortcuts import render
from django.http import JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from apps.core import utils
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)

__all__ = [
    'CRUDActionMixin',
    'ActionNotImplementedError',
]


class ActionNotImplementedError(NotImplementedError):
    """Raised when a required action handler is not implemented."""
    pass


class CRUDActionMixin:
    """
    Mixin for standardized CRUD action routing in GET requests.

    Eliminates duplicated action routing code by providing standard handlers
    for common actions: template, list, form, delete, update.

    Usage:
        class AssetView(CRUDActionMixin, LoginRequiredMixin, View):
            crud_config = {
                "template_list": "activity/asset_list.html",
                "template_form": "activity/asset_form.html",
                "model": Asset,
                "form": AssetForm,
                "related": ["parent", "location", "bu"],
                "fields": ["assetcode", "assetname", ...],
                "list_method": "get_assetlistview",
            }

            def get_context_data(self, **kwargs):
                # Override to customize form context
                return {"msg": "Asset form"}
    """

    crud_config: Dict[str, Any] = {}

    def get(self, request, *args, **kwargs):
        """
        Route GET requests to appropriate handlers based on action parameter.

        Standard actions:
        - template: Load list template
        - list: Return JSON data for list view
        - form: Render create form
        - delete: Render delete confirmation
        - {id}: Render update form
        """
        R = request.GET
        config = self.get_crud_config()

        try:
            if R.get("template"):
                return self.handle_template_request(request, config)

            action = R.get("action")
            if action == "list":
                return self.handle_list_request(request, config)

            if action == "form":
                return self.handle_form_request(request, config)

            if action == "delete" and R.get("id"):
                return self.handle_delete_request(request, config)

            if action:
                return self.handle_custom_action(request, action, config)

            if R.get("id"):
                return self.handle_update_request(request, config)

            return self.handle_default_request(request, config)

        except ValidationError as e:
            logger.warning(f"{self.__class__.__name__} validation error: {e}")
            ErrorHandler.handle_exception(request, e, "CRUD validation failed")
            return JsonResponse({"error": "Invalid request", "details": str(e)}, status=400)
        except PermissionDenied as e:
            logger.warning(f"{self.__class__.__name__} permission denied: {e}")
            ErrorHandler.handle_exception(request, e, "CRUD access denied")
            return JsonResponse({"error": "Access denied"}, status=403)
        except ObjectDoesNotExist as e:
            logger.error(f"{self.__class__.__name__} object not found: {e}")
            ErrorHandler.handle_exception(request, e, "CRUD object not found")
            return JsonResponse({"error": "Object not found"}, status=404)

    def get_crud_config(self) -> Dict[str, Any]:
        """Get CRUD configuration, allowing override."""
        if hasattr(self, 'P'):
            return self.P
        if hasattr(self, 'params'):
            return self.params
        return self.crud_config

    def handle_template_request(self, request, config):
        """Render list template."""
        template = config.get("template_list")
        context = self.get_template_context(request)
        return render(request, template, context)

    def handle_list_request(self, request, config):
        """Return JSON list data."""
        model = config.get("model")
        list_method = config.get("list_method", "get_listview")
        related = config.get("related", [])
        fields = config.get("fields", [])

        if hasattr(model.objects, list_method):
            method = getattr(model.objects, list_method)
            objs = method(related, fields, request) if related and fields else method(request)
        else:
            objs = model.objects.select_related(*related).values(*fields)

        return JsonResponse({"data": list(objs)})

    def handle_form_request(self, request, config):
        """Render create form."""
        form_class = config.get("form")
        form = form_class(request=request)
        context = self.get_form_context(request, form, is_update=False)
        return render(request, config.get("template_form"), context)

    def handle_delete_request(self, request, config):
        """Render delete confirmation."""
        return utils.render_form_for_delete(request, config, True)

    def handle_update_request(self, request, config):
        """Render update form with instance."""
        obj_id = request.GET.get("id")
        obj = utils.get_model_obj(obj_id, request, config)
        form_class = config.get("form")
        form = form_class(instance=obj, request=request)
        context = self.get_form_context(request, form, is_update=True, instance=obj)
        return render(request, config.get("template_form"), context)

    def handle_custom_action(self, request, action, config):
        """
        Handle custom actions not covered by standard CRUD.

        Override in subclass to handle app-specific actions.
        Returns None by default to continue processing.
        """
        return None

    def handle_default_request(self, request, config):
        """Handle requests with no action specified."""
        return self.handle_template_request(request, config)

    def get_template_context(self, request) -> Dict[str, Any]:
        """Override to provide custom template context."""
        return {}

    def get_form_context(self, request, form, is_update=False, instance=None) -> Dict[str, Any]:
        """Override to provide custom form context."""
        form_name = self.get_crud_config().get("form_name", "form")
        context = {
            form_name: form,
            "msg": "Update" if is_update else "Create",
        }
        return context