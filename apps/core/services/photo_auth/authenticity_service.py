"""
Main photo authenticity service - orchestrates authentication workflow.

Handles:
- Authentication workflow coordination
- History tracking
- Audit logging

Complies with .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from typing import Dict, Any, Optional
from datetime import timedelta
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.services.photo_auth.analysis_engines import AnalysisEngines
from apps.core.services.photo_auth.risk_assessment import RiskAssessment
from apps.core.models import ImageMetadata
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class AuthenticityService:
    """Main photo authenticity service coordinating authentication workflow."""

    @classmethod
    def authenticate_photo(
        cls,
        image_path: str,
        context: Dict[str, Any],
        expected_location: Optional[Point] = None,
        validation_level: str = 'standard'
    ) -> Dict[str, Any]:
        """
        Perform comprehensive photo authentication with enterprise-grade validation.

        Args:
            image_path: Path to the photo file
            context: Context information (people_id, upload_type, etc.)
            expected_location: Expected GPS location for validation
            validation_level: Validation strictness ('basic', 'standard', 'strict')

        Returns:
            Comprehensive authentication results with recommendations

        Raises:
            ValidationError: If authentication process fails
        """
        try:
            correlation_id = cls._generate_correlation_id()
            people_id = context.get('people_id')
            upload_type = context.get('upload_type', 'general')

            logger.info(
                "Starting comprehensive photo authentication",
                extra={
                    'correlation_id': correlation_id,
                    'people_id': people_id,
                    'upload_type': upload_type,
                    'validation_level': validation_level
                }
            )

            # Initialize authentication result
            auth_result = cls._initialize_auth_result(
                correlation_id, image_path, people_id, upload_type, validation_level
            )

            # Phase 1: EXIF Metadata Analysis
            exif_results = AnalysisEngines.perform_exif_analysis(
                image_path, people_id, correlation_id
            )
            auth_result['exif_analysis'] = exif_results
            auth_result['validation_results'].append(exif_results)

            # Phase 2: GPS Location Validation
            if expected_location:
                location_results = AnalysisEngines.perform_location_validation(
                    image_path, expected_location, people_id, context
                )
                auth_result['location_validation'] = location_results
                auth_result['validation_results'].append(location_results)

            # Phase 3: Device Fingerprint Analysis
            device_results = AnalysisEngines.perform_device_analysis(
                exif_results, people_id, correlation_id
            )
            auth_result['device_analysis'] = device_results
            auth_result['validation_results'].append(device_results)

            # Phase 4: Behavioral Pattern Analysis
            if validation_level in ['standard', 'strict']:
                behavioral_results = AnalysisEngines.perform_behavioral_analysis(
                    people_id, upload_type, correlation_id
                )
                auth_result['behavioral_analysis'] = behavioral_results
                auth_result['validation_results'].append(behavioral_results)

            # Phase 5: Comprehensive Risk Assessment
            risk_assessment = RiskAssessment.calculate_comprehensive_risk(
                auth_result['validation_results'], upload_type, validation_level
            )
            auth_result['risk_assessment'] = risk_assessment
            auth_result['authenticity_score'] = risk_assessment['authenticity_score']
            auth_result['confidence_level'] = risk_assessment['confidence_level']

            # Phase 6: Final Authentication Decision
            authentication_decision = RiskAssessment.make_authentication_decision(
                risk_assessment, upload_type, validation_level
            )
            auth_result.update(authentication_decision)

            # Phase 7: Generate Recommendations
            auth_result['recommendations'] = RiskAssessment.generate_recommendations(
                auth_result, validation_level
            )

            # Phase 8: Audit Logging
            cls._log_authentication_event(auth_result, context)

            logger.info(
                "Photo authentication completed",
                extra={
                    'correlation_id': correlation_id,
                    'authenticated': auth_result['authenticated'],
                    'authenticity_score': auth_result['authenticity_score'],
                    'requires_review': auth_result['requires_manual_review']
                }
            )

            return auth_result

        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'AuthenticityService',
                    'method': 'authenticate_photo',
                    'image_path': image_path,
                    'people_id': people_id
                },
                level='error'
            )
            raise ValidationError(
                f"Photo authentication failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def get_authentication_history(
        cls,
        people_id: int,
        days: int = 30,
        upload_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get authentication history for analysis and reporting."""
        try:
            auth_records = cls._query_auth_records(people_id, days, upload_type)

            if auth_records.count() == 0:
                return cls._create_empty_history_response(people_id, days)

            return cls._create_history_summary(auth_records, people_id, days, upload_type)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to get authentication history: {e}", exc_info=True)
            return {'people_id': people_id, 'error': str(e), 'period_days': days}

    @classmethod
    def _query_auth_records(cls, people_id, days, upload_type):
        """Query authentication records with filters."""
        filters = {
            'people_id': people_id,
            'analysis_timestamp__gte': timezone.now() - timedelta(days=days)
        }
        if upload_type:
            filters['upload_context'] = upload_type
        return ImageMetadata.objects.filter(**filters).select_related().order_by('-analysis_timestamp')

    @classmethod
    def _create_empty_history_response(cls, people_id, days):
        """Create response for empty history."""
        return {
            'people_id': people_id,
            'period_days': days,
            'total_uploads': 0,
            'summary': 'No upload history found'
        }

    @classmethod
    def _create_history_summary(cls, auth_records, people_id, days, upload_type):
        """Create comprehensive history summary from records."""
        total_uploads = auth_records.count()
        avg_authenticity = sum(r.authenticity_score for r in auth_records) / total_uploads
        high_risk_count = auth_records.filter(manipulation_risk='high').count()
        flagged_count = auth_records.filter(validation_status='suspicious').count()

        return {
            'people_id': people_id,
            'period_days': days,
            'upload_type_filter': upload_type,
            'total_uploads': total_uploads,
            'average_authenticity_score': round(avg_authenticity, 3),
            'high_risk_uploads': high_risk_count,
            'flagged_uploads': flagged_count,
            'risk_percentage': round((high_risk_count / total_uploads) * 100, 1),
            'recent_uploads': [
                {
                    'timestamp': r.analysis_timestamp.isoformat(),
                    'authenticity_score': r.authenticity_score,
                    'validation_status': r.validation_status,
                    'manipulation_risk': r.manipulation_risk
                }
                for r in auth_records[:10]
            ]
        }

    @classmethod
    def _initialize_auth_result(cls, correlation_id, image_path, people_id, upload_type, validation_level):
        """Initialize authentication result structure."""
        return {
            'correlation_id': correlation_id,
            'image_path': image_path,
            'people_id': people_id,
            'upload_type': upload_type,
            'authentication_timestamp': timezone.now().isoformat(),
            'validation_level': validation_level,
            'authenticated': False,
            'authenticity_score': 0.0,
            'confidence_level': 0.0,
            'risk_assessment': {},
            'fraud_indicators': [],
            'validation_results': [],
            'recommendations': [],
            'requires_manual_review': False,
            'compliance_status': 'pending'
        }

    @classmethod
    def _log_authentication_event(cls, auth_result: Dict[str, Any], context: Dict[str, Any]):
        """Log authentication event for audit and compliance."""
        try:
            logger.info(
                "Photo authentication completed",
                extra={
                    'correlation_id': auth_result.get('correlation_id'),
                    'people_id': auth_result.get('people_id'),
                    'authenticated': auth_result.get('authenticated'),
                    'authenticity_score': auth_result.get('authenticity_score'),
                    'risk_level': auth_result.get('risk_assessment', {}).get('risk_level'),
                    'requires_review': auth_result.get('requires_manual_review'),
                    'upload_type': auth_result.get('upload_type'),
                    'fraud_indicators_count': len(auth_result.get('risk_assessment', {}).get('fraud_indicators', []))
                }
            )

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to log authentication event: {e}", exc_info=True)

    @classmethod
    def _generate_correlation_id(cls) -> str:
        """Generate unique correlation ID for tracking."""
        import uuid
        return str(uuid.uuid4())
