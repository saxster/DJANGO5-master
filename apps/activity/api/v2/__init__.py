"""
Operations API v2

Type-safe endpoints with Pydantic validation and clean field names.
"""

from apps.activity.api.v2.viewsets import (
    JobViewSetV2,
    TourViewSetV2,
    TaskViewSetV2,
    PPMScheduleViewSetV2,
    QuestionViewSetV2,
    AnswerSubmissionView,
    AnswerBatchSubmissionView,
    AttachmentUploadView,
)

__all__ = [
    'JobViewSetV2',
    'TourViewSetV2',
    'TaskViewSetV2',
    'PPMScheduleViewSetV2',
    'QuestionViewSetV2',
    'AnswerSubmissionView',
    'AnswerBatchSubmissionView',
    'AttachmentUploadView',
]
