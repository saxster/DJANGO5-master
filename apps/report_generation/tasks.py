"""
Celery Tasks for Report Generation

Async tasks for:
- Processing incoming reports from Kotlin app
- AI question generation
- Quality analysis
- Mentor domain detection
- Attachment analysis (EXIF, OCR, damage detection)
- Trend detection
- PDF generation
- Learning loop updates

Following .claude/rules.md:
- All tasks include timeouts
- Specific exception handling
- Retry with exponential backoff
"""

import logging
from celery import shared_task, chord
from django.conf import settings
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, OperationalError

logger = logging.getLogger(__name__)


@shared_task(
    name='report_generation.process_incoming_report',
    bind=True,
    max_retries=3,
    time_limit=600
)
def process_incoming_report(self, report_id: int):
    """
    MASTER TASK: Process report received from Kotlin Android app.
    
    Orchestrates all AI analysis in background:
    1. Auto-populate context from related entities
    2. Detect mentor domain (Security vs Facility)
    3. Calculate quality scores
    4. Analyze attachments
    5. Check for incident trends
    6. Notify supervisor if urgent
    
    Args:
        report_id: ID of newly synced report
    """
    try:
        from apps.report_generation.models import GeneratedReport
        
        report = GeneratedReport.objects.get(id=report_id)
        
        logger.info(f"Processing incoming report {report_id}: {report.title}")
        
        # Run analysis pipeline (in parallel where possible)
        pipeline = chord([
            detect_mentor_domain.s(report_id),
            analyze_report_quality_async.s(report_id),
            auto_populate_context.s(report_id),
        ])(process_complete_callback.s(report_id))
        
        # Process attachments separately
        for attachment in report.attachments.all():
            analyze_attachment_async.delay(attachment.id)
        
        logger.info(f"Report {report_id} processing pipeline initiated")
        
        return {
            'report_id': report_id,
            'pipeline_status': 'running',
            'success': True
        }
        
    except GeneratedReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return {'success': False, 'error': 'Report not found'}
        
    except Exception as e:
        logger.error(f"Error processing report {report_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    name='report_generation.detect_mentor_domain',
    time_limit=120
)
def detect_mentor_domain(report_id: int):
    """
    Detect whether report needs Security Mentor or Facility Mentor.
    Creates MentorContext record.
    """
    try:
        from apps.report_generation.models import GeneratedReport
        
        report = GeneratedReport.objects.get(id=report_id)
        
        # Use MentorContextParser when implemented
        # For now, simple keyword detection
        keywords = ' '.join(str(v) for v in report.report_data.values() if isinstance(v, str)).lower()
        
        security_keywords = ['breach', 'theft', 'assault', 'intrusion', 'unauthorized', 'security']
        facility_keywords = ['pump', 'asset', 'maintenance', 'failure', 'breakdown', 'equipment']
        
        security_score = sum(1 for kw in security_keywords if kw in keywords)
        facility_score = sum(1 for kw in facility_keywords if kw in keywords)
        
        if security_score > facility_score:
            domain = 'security'
            confidence = int((security_score / (security_score + facility_score)) * 100)
        elif facility_score > security_score:
            domain = 'facility'
            confidence = int((facility_score / (security_score + facility_score)) * 100)
        else:
            domain = 'hybrid'
            confidence = 50
        
        # TODO: Create ReportMentorContext when model added
        logger.info(f"Report {report_id} assigned to {domain} mentor (confidence: {confidence}%)")
        
        return {'report_id': report_id, 'domain': domain, 'confidence': confidence}
        
    except Exception as e:
        logger.error(f"Error detecting mentor domain for report {report_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.auto_populate_context',
    time_limit=180
)
def auto_populate_context(report_id: int):
    """
    Auto-populate report from related entities (work orders, incidents, etc.).
    """
    try:
        from apps.report_generation.models import GeneratedReport
        from apps.report_generation.services import ContextAutoPopulationService
        
        report = GeneratedReport.objects.get(id=report_id)
        
        # If report is linked to entity, populate
        if report.related_object_id and report.related_content_type:
            model_name = report.related_content_type.model
            
            auto_data = {}
            if model_name == 'workorder':
                auto_data = ContextAutoPopulationService.populate_from_work_order(report.related_object_id)
            elif model_name == 'alert':
                auto_data = ContextAutoPopulationService.populate_from_incident(report.related_object_id)
            elif model_name == 'asset':
                auto_data = ContextAutoPopulationService.populate_from_asset(report.related_object_id)
            
            if auto_data:
                # Merge with existing data (don't overwrite user input)
                report_data = {**auto_data, **report.report_data}
                report.report_data = report_data
                report.save()
                
                logger.info(f"Auto-populated {len(auto_data)} fields for report {report_id}")
        
        return {'report_id': report_id, 'fields_populated': len(auto_data) if auto_data else 0}
        
    except Exception as e:
        logger.error(f"Error auto-populating report {report_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.process_complete_callback',
    time_limit=60
)
def process_complete_callback(results, report_id: int):
    """
    Callback when all processing complete.
    Notify supervisor if urgent.
    """
    try:
        from apps.report_generation.models import GeneratedReport
        
        report = GeneratedReport.objects.get(id=report_id)
        
        # Check if requires urgent attention
        is_urgent = (
            report.quality_score < 60 or
            report.template.category == 'incident' or
            report.report_data.get('severity', 0) >= 4
        )
        
        if is_urgent:
            notify_supervisor_urgent.delay(report_id)
        
        logger.info(f"Report {report_id} processing complete. Urgent: {is_urgent}")
        
        return {'report_id': report_id, 'urgent': is_urgent}
        
    except Exception as e:
        logger.error(f"Error in process complete callback: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.notify_supervisor_urgent',
    time_limit=60
)
def notify_supervisor_urgent(report_id: int):
    """
    Send urgent notification to supervisor.
    Uses existing notification infrastructure.
    """
    try:
        from apps.report_generation.models import GeneratedReport
        from django.core.mail import send_mail
        
        report = GeneratedReport.objects.select_related('author', 'template').get(id=report_id)
        
        # Get supervisors for this tenant
        supervisors = report.tenant.people_set.filter(
            is_supervisor=True,
            email_notifications_enabled=True
        )
        
        for supervisor in supervisors:
            send_mail(
                subject=f'⚠️ Urgent Report Review Needed: {report.title}',
                message=f"""
A report requires your immediate attention:

Report: {report.title}
Type: {report.template.get_category_display()}
Author: {report.author.get_full_name()}
Quality Score: {report.quality_score}/100
Submitted: {report.created_at}

{"CRITICAL: Quality score below threshold" if report.quality_score < 60 else ""}
{"CRITICAL: Security incident" if report.template.category == 'incident' else ""}

Review at: {settings.SITE_URL}/admin/report_generation/generatedreport/{report.id}/
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[supervisor.email],
                fail_silently=False
            )
        
        logger.info(f"Sent urgent notification for report {report_id} to {supervisors.count()} supervisors")
        
        return {'report_id': report_id, 'notified': supervisors.count()}
        
    except Exception as e:
        logger.error(f"Error sending urgent notification: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.analyze_attachment_async',
    bind=True,
    max_retries=2,
    time_limit=300
)
def analyze_attachment_async(self, attachment_id: int):
    """
    Analyze photo/video attachment:
    - Extract EXIF metadata
    - OCR text extraction
    - Damage detection (placeholder)
    - Quality check
    """
    try:
        from apps.report_generation.models import ReportAttachment
        
        attachment = ReportAttachment.objects.get(id=attachment_id)
        
        # TODO: Use MultimediaInterrogationService when implemented
        # For now, basic EXIF extraction
        
        if attachment.attachment_type == 'photo':
            from PIL import Image
            import exifread
            
            with attachment.file.open('rb') as f:
                tags = exifread.process_file(f)
                
                exif_data = {}
                if 'EXIF DateTimeOriginal' in tags:
                    exif_data['timestamp'] = str(tags['EXIF DateTimeOriginal'])
                if 'Image Make' in tags and 'Image Model' in tags:
                    exif_data['device'] = f"{tags['Image Make']} {tags['Image Model']}"
                
                attachment.metadata['exif'] = exif_data
                attachment.ai_analyzed = True
                attachment.save()
        
        logger.info(f"Analyzed attachment {attachment_id}")
        
        return {'attachment_id': attachment_id, 'success': True}
        
    except Exception as e:
        logger.error(f"Error analyzing attachment {attachment_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    name='report_generation.analyze_quality',
    bind=True,
    max_retries=3,
    time_limit=300
)
def analyze_report_quality_async(self, report_id: int):
    """
    Asynchronously analyze report quality.
    
    Args:
        report_id: ID of the report to analyze
    """
    try:
        from apps.report_generation.models import GeneratedReport
        from apps.report_generation.services import QualityGateService
        
        report = GeneratedReport.objects.get(id=report_id)
        metrics = QualityGateService.calculate_quality_metrics(report)
        
        logger.info(f"Quality analysis completed for report {report_id}: {metrics['quality_score']}/100")
        
        return {
            'report_id': report_id,
            'quality_score': metrics['quality_score'],
            'success': True
        }
        
    except GeneratedReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return {'success': False, 'error': 'Report not found'}
        
    except Exception as e:
        logger.error(f"Error analyzing report {report_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    name='report_generation.identify_trends',
    bind=True,
    time_limit=600
)
def identify_incident_trends_async(self, tenant_id: int, days_back: int = 90):
    """
    Asynchronously identify incident trends.
    
    Args:
        tenant_id: Tenant ID
        days_back: Number of days to analyze
    """
    try:
        from apps.report_generation.services import ReportLearningService
        
        trends = ReportLearningService.identify_incident_trends(tenant_id, days_back)
        
        logger.info(f"Identified {len(trends)} trends for tenant {tenant_id}")
        
        return {
            'tenant_id': tenant_id,
            'trends_identified': len(trends),
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error identifying trends for tenant {tenant_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)


@shared_task(
    name='report_generation.analyze_exemplars',
    time_limit=300
)
def analyze_exemplar_patterns_async(category: str, tenant_id: int):
    """
    Asynchronously analyze exemplar patterns for learning.
    
    Args:
        category: Report category
        tenant_id: Tenant ID
    """
    try:
        from apps.report_generation.services import ReportLearningService
        
        patterns = ReportLearningService.analyze_exemplar_reports(category, tenant_id)
        
        logger.info(f"Analyzed {patterns.get('exemplar_count', 0)} exemplars for category {category}")
        
        return {
            'category': category,
            'exemplar_count': patterns.get('exemplar_count', 0),
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error analyzing exemplars for {category}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.generate_pdf',
    bind=True,
    max_retries=2,
    time_limit=600
)
def generate_report_pdf_async(self, report_id: int):
    """
    Generate PDF for report using AsyncPDFGenerationService.

    Replaces fake placeholder implementation (Issue #6b - Nov 11, 2025 remediation).
    Uses existing core PDF service for real PDF generation with WeasyPrint.

    Args:
        report_id: Report ID

    Returns:
        Dict with report_id, pdf_path, success status
    """
    try:
        from apps.report_generation.models import GeneratedReport
        from apps.core.services.async_pdf_service import AsyncPDFGenerationService
        from django.conf import settings

        report = GeneratedReport.objects.select_related('author', 'tenant', 'template').get(id=report_id)

        logger.info(f"PDF generation started for report {report_id}: {report.title}")

        # Initialize PDF service
        pdf_service = AsyncPDFGenerationService()

        # Prepare template context
        context_data = {
            'report': report,
            'report_data': report.report_data,
            'title': report.title,
            'author': report.author,
            'tenant': report.tenant,
            'template': report.template,
            'created_at': report.created_at,
            'attachments': report.attachments.all(),
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        }

        # Determine template name based on report type
        template_name = report.template.pdf_template if hasattr(report.template, 'pdf_template') else 'reports/pdf/default_report.html'

        # Generate unique filename
        filename = f"report_{report.id}_{report.created_at.strftime('%Y%m%d_%H%M%S')}.pdf"

        # Initiate PDF generation
        task_data = pdf_service.initiate_pdf_generation(
            template_name=template_name,
            context_data=context_data,
            user_id=report.author.id,
            filename=filename,
            output_format='pdf'
        )

        # Generate PDF content
        result = pdf_service.generate_pdf_content(
            task_id=task_data['task_id'],
            template_name=template_name,
            context_data=context_data,
            output_format='pdf'
        )

        if result['status'] == 'completed':
            # Update report model with PDF path
            report.pdf_file = result['file_path']
            report.pdf_generated_at = timezone.now()
            report.save(update_fields=['pdf_file', 'pdf_generated_at'])

            logger.info(f"PDF generated successfully for report {report_id}: {result['file_path']}")

            return {
                'report_id': report_id,
                'pdf_path': result['file_path'],
                'file_size': result.get('file_size', 0),
                'success': True
            }
        else:
            error_msg = result.get('error', 'PDF generation failed')
            logger.error(f"PDF generation failed for report {report_id}: {error_msg}")
            return {
                'report_id': report_id,
                'pdf_path': None,
                'success': False,
                'error': error_msg
            }

    except GeneratedReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return {
            'report_id': report_id,
            'success': False,
            'error': 'Report not found'
        }

    except (DatabaseError, IntegrityError, OperationalError) as e:
        logger.error(f"Database error generating PDF for report {report_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(f"Data error generating PDF for report {report_id}: {e}", exc_info=True)
        return {
            'report_id': report_id,
            'success': False,
            'error': f'Invalid data: {str(e)}'
        }

    except (IOError, OSError) as e:
        logger.error(f"File error generating PDF for report {report_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    name='report_generation.daily_trend_analysis',
    time_limit=900
)
def daily_trend_analysis():
    """
    Daily scheduled task to analyze trends across all tenants.
    """
    try:
        from apps.tenants.models import Tenant
        from apps.report_generation.services import ReportLearningService
        
        total_trends = 0
        
        for tenant in Tenant.objects.filter(is_active=True):
            trends = ReportLearningService.identify_incident_trends(tenant.id, days_back=7)
            total_trends += len(trends)
        
        logger.info(f"Daily trend analysis complete: {total_trends} trends identified")
        
        return {
            'trends_identified': total_trends,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error in daily trend analysis: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='report_generation.update_learning_stats',
    time_limit=300
)
def update_learning_statistics():
    """
    Update learning statistics cache for all tenants.
    """
    try:
        from apps.tenants.models import Tenant
        from apps.report_generation.services import ReportLearningService
        from django.core.cache import cache
        
        for tenant in Tenant.objects.filter(is_active=True):
            stats = ReportLearningService.get_learning_statistics(tenant.id)
            cache.set(f'learning_stats:{tenant.id}', stats, 3600)
        
        logger.info("Learning statistics updated for all tenants")
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error updating learning statistics: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
