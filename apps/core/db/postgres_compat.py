"""
PostgreSQL compatibility helpers for test environments.

Production uses PostgreSQL-specific field types (ArrayField, SearchVector,
etc.) but our optimized test settings run on SQLite.  This module monkey
patches Django's PostgreSQL field implementations so the ORM can create
schema on SQLite without crashing.  It only activates when the environment
variable ``DJANGO_POSTGRES_COMPAT_DISABLED`` is truthy.
"""

from __future__ import annotations

import json
import os
from typing import Any

from django.conf import settings
from django.contrib.gis.geos import GEOSException, GEOSGeometry

POSTGRES_COMPAT_DISABLED = os.environ.get('DJANGO_POSTGRES_COMPAT_DISABLED', '').lower() in {
    '1', 'true', 'yes', 'on'
}


def _patch_array_field():
    from django.contrib.postgres import fields

    if getattr(fields.ArrayField, '_compat_patched', False):
        return

    base = fields.ArrayField
    original_db_type = base.db_type
    original_get_placeholder = base.get_placeholder
    original_get_db_prep_value = base.get_db_prep_value
    original_from_db_value = getattr(base, 'from_db_value', None)

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return original_db_type(self, connection)
        return 'text'

    def get_db_prep_value(self, value, connection, prepared=False):
        prepared_value = original_get_db_prep_value(self, value, connection, prepared)
        if connection.vendor == 'postgresql':
            return prepared_value
        if prepared_value is None:
            return None
        if isinstance(prepared_value, str):
            return prepared_value
        return json.dumps(prepared_value, ensure_ascii=False)

    def from_db_value(self, value, expression, connection):
        if connection.vendor == 'postgresql':
            if original_from_db_value:
                return original_from_db_value(self, value, expression, connection)
            return value
        if value in (None, '', b''):
            return []
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = value.decode()
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return [self.base_field.to_python(item) for item in parsed]

    def get_placeholder(self, value, compiler, connection):
        if connection.vendor == 'postgresql':
            return original_get_placeholder(self, value, compiler, connection)
        return '%s'

    base.db_type = db_type
    base.get_placeholder = get_placeholder
    base.get_db_prep_value = get_db_prep_value
    base.from_db_value = from_db_value
    base._compat_patched = True


def _patch_search_vector_field():
    from django.contrib.postgres import search
    from django.db import models

    field = search.SearchVectorField
    if getattr(field, '_compat_patched', False):
        return

    original_db_type = field.db_type

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return original_db_type(self, connection)
        return 'text'

    field.db_type = db_type
    field._compat_patched = True

    class _NoOpSearchVector(models.Expression):
        output_field = models.TextField()

        def __init__(self, *expressions, **extra):
            super().__init__()

        def __add__(self, other):
            return self.__class__()

        def as_sql(self, compiler, connection, **extra_context):
            return '%s', ['']

    search.SearchVector = _NoOpSearchVector


def _patch_geometry_field():
    try:
        from django.contrib.gis.db import models as gis_models
    except Exception:  # pragma: no cover - GIS not installed
        return

    geometry_field = gis_models.GeometryField
    if getattr(geometry_field, '_compat_patched', False):
        return

    original_db_type = geometry_field.db_type
    original_get_prep_value = geometry_field.get_prep_value
    original_from_db_value = getattr(geometry_field, 'from_db_value', None)

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return original_db_type(self, connection)
        return 'text'

    def get_placeholder(self, value, compiler, connection):
        return '%s'

    def get_prep_value(self, value):
        if value is None:
            return None
        geom = original_get_prep_value(self, value)
        return geom.wkt if hasattr(geom, 'wkt') else geom

    def from_db_value(self, value, expression, connection):
        if connection.vendor == 'postgresql':
            if original_from_db_value:
                return original_from_db_value(self, value, expression, connection)
            return value
        if value in (None, '', b''):
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = value.decode()
        try:
            geom = GEOSGeometry(value)
            geom.srid = getattr(self, 'srid', None) or geom.srid
            return geom
        except (GEOSException, TypeError, ValueError):
            return None

    geometry_field.db_type = db_type
    geometry_field.get_placeholder = get_placeholder
    geometry_field.get_prep_value = get_prep_value
    geometry_field.from_db_value = from_db_value
    geometry_field._compat_patched = True


def enable_postgres_compat_mode():
    if not POSTGRES_COMPAT_DISABLED and getattr(settings, 'USE_POSTGRESQL_COMPAT', True):
        _patch_array_field()
        _patch_search_vector_field()
        _patch_geometry_field()


enable_postgres_compat_mode()


__all__ = ['enable_postgres_compat_mode', 'POSTGRES_COMPAT_DISABLED']
