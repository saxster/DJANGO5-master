"""
Shared Base Imports and Utilities for Job Managers.

Centralizes common imports and utilities used across all job manager classes.
Extracted from: apps/activity/managers/job_manager.py (lines 1-20)
Date: 2025-10-10
"""

# Django core
from django.db import models, transaction, DatabaseError, OperationalError, IntegrityError
from django.db.models.functions import Concat, Cast
from django.db.models import CharField, Value as V, IntegerField
from django.db.models import Q, F, Count, Case, When
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.conf import settings

# Python standard library
from datetime import datetime, timedelta, timezone
import logging
import json

# Project imports
from apps.core import utils
import apps.peoples.models as pm
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.exceptions import ActivityManagementException, DatabaseIntegrityException
from apps.core.error_handling import ErrorHandler
from apps.tenants.managers import TenantAwareManager

# Logging
logger = logging.getLogger('__main__')
log = logger


# ============================================================================
# NOTE: GeospatialService Circular Dependency
# ============================================================================
# GeospatialService import is done at FUNCTION LEVEL (not module level) to break
# circular dependency chain:
#   attendance.models → attendance.managers → activity.models →
#   activity.managers → attendance.services
#
# Any manager method that needs GeospatialService should import it locally:
#
#   def method_needing_geo_service(self, ...):
#       from apps.attendance.services.geospatial_service import GeospatialService
#       lon, lat = GeospatialService.extract_coordinates(gpslocation)
#
# ============================================================================
