"""
Work Order Management - Shared Base Module

Provides common imports, utilities, and base classes for all WOM views.

Refactored: October 2025
Part of: work_order_management/views/ (6 modules)
"""

# Django core imports
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import View
from django.utils.translation import gettext_lazy as _
from django.db import transaction, IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponse, QueryDict
from django.http import response as rp
from django.template.loader import render_to_string
from django.utils import timezone

# Third-party imports
import psycopg2.errors as pg_errs
import logging
from dateutil.relativedelta import relativedelta

# App imports
from apps.work_order_management.forms import (
    VendorForm, WorkOrderForm, WorkPermitForm,
    ApproverForm, SlaForm
)
from apps.work_order_management.models import Vendor, Wom, WomDetails, Approver
from apps.work_order_management.utils import (
    check_all_approved,
    reject_workpermit,
    save_approvers_injson,
    check_all_verified,
    save_verifiers_injson,
    save_workpermit_name_injson,
    reject_workpermit_verifier,
    save_pdf_to_tmp_location,
    get_approvers_code,
    get_verifiers_code,
    check_if_valid_approver,
    check_if_valid_verifier,
)

# Core utilities
from apps.core import utils
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.utils_new.http_utils import get_clean_form_data

# People utilities
from apps.peoples import utils as putils
from apps.peoples.models import People

# Activity models
from apps.activity.models.question_model import QuestionSetBelonging, QuestionSet

# Background tasks
from background_tasks.tasks import (
    send_email_notification_for_sla_vendor,
    send_email_notification_for_vendor_and_security_of_wp_cancellation,
    send_email_notification_for_vendor_and_security_for_rwp,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_wp_verifier,
    send_email_notification_for_workpermit_approval,
)

# Onboarding models
from apps.onboarding.models import Bt

# Services
from apps.work_order_management.services import WorkOrderQueryOptimizer

# Module logger
logger = logging.getLogger("django")


# Shared helpers
def handle_form_errors(request, params, errors):
    """
    Standardized error handling for invalid forms.

    Args:
        request: Django request object
        params: View parameters dictionary
        errors: Form errors dictionary

    Returns:
        JsonResponse with error details
    """
    cxt = {"errors": errors}
    return utils.handle_invalid_form(request, params, cxt)


def save_with_audit(obj, user, session, create=True):
    """
    Save model instance with audit trail (user info, timestamps).

    Args:
        obj: Model instance to save
        user: User performing the operation
        session: Request session
        create: True for create, False for update

    Returns:
        Saved model instance with audit fields populated
    """
    return putils.save_userinfo(obj, user, session, create=create)
