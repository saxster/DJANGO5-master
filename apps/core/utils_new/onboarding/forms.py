"""
Onboarding Form Utilities

Utilities for form initialization, validation, and UI enhancement
for onboarding wizard forms.
"""

import logging

logger = logging.getLogger("django")


def initailize_form_fields(form):
    """
    Initialize form field CSS classes for Bootstrap styling.

    Adds appropriate Bootstrap form-control classes based on widget type.
    """
    for visible in form.visible_fields():
        if visible.widget_type in [
            "text",
            "textarea",
            "datetime",
            "time",
            "number",
            "date",
            "email",
            "decimal",
        ]:
            visible.field.widget.attrs["class"] = "form-control form-control-solid"
        elif visible.widget_type in ["radio", "checkbox"]:
            visible.field.widget.attrs["class"] = "form-check-input"
        elif visible.widget_type in [
            "select2",
            "select",
            "select2multiple",
            "modelselect2",
            "modelselect2multiple",
        ]:
            visible.field.widget.attrs["class"] = "form-select form-select-solid"
            visible.field.widget.attrs["data-control"] = "select2"
            visible.field.widget.attrs["data-placeholder"] = "Select an option"
            visible.field.widget.attrs["data-allow-clear"] = "true"


def apply_error_classes(form):
    """
    Apply error CSS classes to invalid form fields.

    Adds is-invalid class to fields with validation errors.
    """
    # loop on *all* fields if key '__all__' found else only on errors:
    for x in form.fields if "__all__" in form.errors else form.errors:
        attrs = form.fields[x].widget.attrs
        attrs.update({"class": attrs.get("class", "") + " is-invalid"})


def get_instance_for_update(postdata, params, msg, pk, kwargs=None):
    """
    Retrieve and bind model instance to form for update.

    Args:
        postdata: POST request data
        params: Dict with 'model' and 'form_class' keys
        msg: Log message
        pk: Primary key of instance to retrieve
        kwargs: Additional kwargs for form initialization

    Returns:
        Bound form instance
    """
    if kwargs is None:
        kwargs = {}
    logger.info("%s", msg)
    obj = params["model"].objects.get(id=pk)
    logger.info(f"object retrieved '{obj}'")
    return params["form_class"](postdata, instance=obj, **kwargs)


def get_model_obj(pk, request, params):
    """
    Retrieve model object by primary key.

    Args:
        pk: Primary key to retrieve
        request: HTTP request
        params: Dict with 'model' key

    Returns:
        Model instance or error response
    """
    from apps.core.utils_new.http_utils import handle_DoesNotExist

    try:
        obj = params["model"].objects.get(id=pk)
    except params["model"].DoesNotExist:
        return handle_DoesNotExist(request)
    else:
        logger.info(f"object retrieved '{obj}'")
        return obj


__all__ = [
    'initailize_form_fields',
    'apply_error_classes',
    'get_instance_for_update',
    'get_model_obj',
]
