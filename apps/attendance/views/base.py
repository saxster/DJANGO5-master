"""
Base imports and utilities for attendance views.
Centralizes common dependencies to reduce duplication.
"""

# Django core imports
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.utils import IntegrityError, DatabaseError
from django.db import transaction
from django.http import response as rp
from django.http.request import QueryDict
from django.shortcuts import render
from django.views import View
from django.core.exceptions import ObjectDoesNotExist, ValidationError

# App-specific imports
import apps.attendance.forms as atf
import apps.attendance.models as atdm
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.activity import models as am
from apps.attendance.filters import AttendanceFilter
import apps.peoples.utils as putils
from apps.service.services.geospatial_service import save_linestring_and_update_pelrecord
from apps.core.utils_new.db_utils import get_current_db_name
from apps.attendance.exceptions import (
    AttendanceError,
    AttendanceValidationError,
    AttendanceProcessingError,
    AttendanceDataCorruptionError,
    handle_attendance_exception,
    map_django_exception
)

# Standard library imports
import logging
import json

# Core utilities
from apps.core import utils

# Logger configuration
logger = logging.getLogger("django")

# Export all commonly used items
__all__ = [
    'LoginRequiredMixin',
    'IntegrityError',
    'DatabaseError',
    'transaction',
    'rp',
    'QueryDict',
    'render',
    'View',
    'ObjectDoesNotExist',
    'ValidationError',
    'atf',
    'atdm',
    'ob',
    'am',
    'AttendanceFilter',
    'putils',
    'save_linestring_and_update_pelrecord',
    'get_current_db_name',
    'AttendanceError',
    'AttendanceValidationError',
    'AttendanceProcessingError',
    'AttendanceDataCorruptionError',
    'handle_attendance_exception',
    'map_django_exception',
    'logging',
    'json',
    'utils',
    'logger',
]
