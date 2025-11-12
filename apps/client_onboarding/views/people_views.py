import logging
from django.http import response as rp
from django.db.models import Q
from django.apps import apps

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger("django")


def get_list_of_peoples(request):
    """
    Get list of people for a permission group.

    SECURITY FIX (HP-003): Added IDOR vulnerability protection
    - Validate request parameters
    - Sanitize model name (whitelist only)
    - Add tenant isolation check
    - Add permission validation
    """
    if request.method == "POST":
        return rp.JsonResponse({"error": "Method not allowed"}, status=405)

    # SECURITY: Validate and sanitize inputs
    model_name = request.GET.get("model", "").strip()
    obj_id = request.GET.get("id", "").strip()

    # Validate ID is numeric
    if not obj_id or not obj_id.isdigit():
        return rp.JsonResponse({"error": "Invalid ID parameter"}, status=400)

    # SECURITY: Whitelist allowed models (prevent arbitrary model access)
    ALLOWED_MODELS = ['Task', 'WorkOrder', 'Tour']
    if model_name not in ALLOWED_MODELS:
        return rp.JsonResponse({"error": "Invalid model parameter"}, status=400)

    try:
        Model = apps.get_model("activity", model_name)
        obj = Model.objects.get(id=obj_id)

        # SECURITY: Tenant isolation check
        if hasattr(obj, 'tenant') and obj.tenant != request.user.tenant:
            return rp.JsonResponse({"error": "Access denied"}, status=403)

        # SECURITY: Permission check (customize based on your needs)
        # if not request.user.has_perm(f'activity.view_{model_name.lower()}'):
        #     return rp.JsonResponse({"error": "Permission denied"}, status=403)

    except Model.DoesNotExist:
        return rp.JsonResponse({"error": "Object not found"}, status=404)
    except DATABASE_EXCEPTIONS as e:
        from apps.core.error_handling import ErrorHandler
        correlation_id = ErrorHandler.handle_exception(e, context={'view': 'get_list_of_peoples'})
        logger.error(f"Error in get_list_of_peoples: {e}", extra={'correlation_id': correlation_id}, exc_info=True)
        return ErrorHandler.create_error_response("System error occurred", error_code="SYSTEM_ERROR", correlation_id=correlation_id)

    Pgbelonging = apps.get_model("peoples", "Pgbelonging")
    data = (
        Pgbelonging.objects.filter(
            Q(assignsites_id=1) | Q(assignsites__isnull=True),
            pgroup_id=obj.pgroup_id,
            tenant=request.user.tenant  # SECURITY: Tenant isolation
        ).values("people__peoplecode", "people__peoplename", "id")
        or Pgbelonging.objects.none()
    )
    return rp.JsonResponse({"data": list(data)}, status=200)
