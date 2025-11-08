"""
Serializers for Report Generation API
"""

from apps.report_generation.serializers.report_template_serializer import ReportTemplateSerializer
from apps.report_generation.serializers.generated_report_serializer import (
    GeneratedReportSerializer,
    GeneratedReportDetailSerializer,
    GeneratedReportCreateSerializer,
    GeneratedReportUpdateSerializer,
)
from apps.report_generation.serializers.report_quality_serializer import ReportQualityMetricsSerializer
from apps.report_generation.serializers.report_exemplar_serializer import ReportExemplarSerializer
from apps.report_generation.serializers.report_trend_serializer import ReportIncidentTrendSerializer

__all__ = [
    'ReportTemplateSerializer',
    'GeneratedReportSerializer',
    'GeneratedReportDetailSerializer',
    'GeneratedReportCreateSerializer',
    'GeneratedReportUpdateSerializer',
    'ReportQualityMetricsSerializer',
    'ReportExemplarSerializer',
    'ReportIncidentTrendSerializer',
]
