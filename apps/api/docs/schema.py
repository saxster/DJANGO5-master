"""
Custom OpenAPI schema helpers.

Provides a lenient AutoSchema implementation that tolerates legacy views
missing DRF serializer metadata by falling back to an empty serializer.
"""

import logging
import re
from typing import Optional

from django.contrib.gis.db import models as gis_models
from drf_spectacular.drainage import add_trace_message
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import build_basic_type, build_serializer_context
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class LenientAutoSchema(AutoSchema):
    """
    AutoSchema variant that gracefully falls back to a blank serializer.

    Many legacy APIViews in the project pre-date the DRF serializer interface.
    The default drf-spectacular implementation logs an error for each of these
    endpoints which halts schema generation. This subclass mirrors the upstream
    logic but returns an empty ``Serializer`` instance whenever metadata is
    missing, allowing schema generation to continue (the resulting schema object
    is the generic ``type: object`` placeholder).
    """

    def _get_serializer(self) -> Optional[serializers.BaseSerializer]:
        view = self.view
        context = build_serializer_context(view)

        try:
            if isinstance(view, GenericAPIView):
                if view.__class__.get_serializer == GenericAPIView.get_serializer:
                    serializer_class = view.get_serializer_class()
                    return serializer_class(context=context)
                return view.get_serializer(context=context)

            if isinstance(view, APIView):
                get_serializer = getattr(view, "get_serializer", None)
                if callable(get_serializer):
                    return get_serializer(context=context)

                get_serializer_class = getattr(view, "get_serializer_class", None)
                if callable(get_serializer_class):
                    serializer_class = get_serializer_class()
                    if isinstance(serializer_class, type) and issubclass(
                        serializer_class, serializers.BaseSerializer
                    ):
                        return serializer_class(context=context)
                    return serializer_class

                serializer_class = getattr(view, "serializer_class", None)
                if serializer_class is not None:
                    if isinstance(serializer_class, type) and issubclass(
                        serializer_class, serializers.BaseSerializer
                    ):
                        return serializer_class(context=context)
                    return serializer_class

        except Exception as exc:  # pragma: no cover - defensive
            add_trace_message(
                f"LenientAutoSchema could not initialise serializer for "
                f"{view.__class__.__name__}: {exc}"
            )

        add_trace_message(
            f"LenientAutoSchema falling back to generic serializer for "
            f"{view.__class__.__name__}"
        )
        ref_name = f"{view.__class__.__name__}Fallback"
        fallback_serializer = type(
            ref_name,
            (serializers.Serializer,),
            {'Meta': type('Meta', (), {'ref_name': ref_name})},
        )
        return fallback_serializer(context=context)

    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        if field.__class__.__name__ == 'CustomTimeField':
            return build_basic_type(OpenApiTypes.TIME)
        return super()._map_serializer_field(field, direction, bypass_extensions)

    def _map_model_field(self, model_field, direction):
        if isinstance(model_field, gis_models.GeometryField):
            return build_basic_type(OpenApiTypes.OBJECT)
        return super()._map_model_field(model_field, direction)

    def get_operation_id(self) -> str:
        """
        Generate deterministic, unique operationIds by keying on the HTTP method
        and the concrete request path. This eliminates collisions when the same
        view is mounted under multiple URL prefixes (e.g., versioned aliases).
        """
        path = self.path or ''
        tokens = [
            self.method.lower(),
            *[
                segment.replace('{', '').replace('}', '').replace('-', '_')
                for segment in path.strip('/').split('/')
                if segment
            ],
        ]

        if len(tokens) == 1:
            tokens.append('root')

        raw_id = '_'.join(tokens)
        sanitized = re.sub(r'[^0-9a-zA-Z_]', '_', raw_id)
        sanitized = re.sub(r'__+', '_', sanitized).strip('_')
        if not sanitized:
            sanitized = f"{self.method.lower()}_operation"
        if sanitized[0].isdigit():
            sanitized = f"op_{sanitized}"
        return sanitized


__all__ = ["LenientAutoSchema"]
