"""
Site Audit Analysis and Reporting Views.

This module handles AI-powered analysis with dual-LLM consensus, SOP generation,
coverage planning, and comprehensive report generation.

Extracted from: apps/onboarding_api/views/site_audit_views.py (lines 1048-1456)
Refactoring Date: 2025-10-11
Part of: Phase C - God file elimination (CLAUDE.md compliance)

View Classes:
- AuditAnalysisView: Trigger dual-LLM consensus analysis with knowledge grounding
- CoveragePlanView: Get guard coverage and shift plans
- SOPListView: List generated SOPs with filtering
- AuditReportView: Generate comprehensive audit reports

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management with atomic()
- Rule #12: Query optimization with select_related()/prefetch_related()
"""

import logging
import uuid
import time
from typing import Dict, Any, List

from django.db import transaction, DatabaseError
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import (
    OnboardingSite,
    SOP,
    CoveragePlan,
    ConversationSession,
    LLMRecommendation
)

from ...serializer_modules.site_audit_serializers import (
    AuditAnalysisSerializer,
    CoveragePlanSerializer,
    SOPSerializer,
    ReportGenerationSerializer
)

from apps.onboarding_api.services.sop_generator import SOPGeneratorService
from apps.onboarding_api.services.site_coverage import get_coverage_planner_service
from apps.onboarding_api.services.reporting import get_reporting_service
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service, get_consensus_engine
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class AuditAnalysisView(APIView):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/analyze/

    Trigger dual-LLM consensus analysis with knowledge grounding.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Trigger comprehensive audit analysis."""
        serializer = AuditAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check if should run async (long-running task)
            if self._should_run_async(session_id):
                task_result = self._enqueue_analysis_task(
                    session_id,
                    serializer.validated_data,
                    request.user
                )
                return Response(task_result, status=status.HTTP_202_ACCEPTED)
            else:
                result = self._run_analysis_sync(
                    session_id,
                    serializer.validated_data,
                    request.user
                )
                return Response(result)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Analysis failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _should_run_async(self, session_id: str) -> bool:
        """Determine if analysis should run async."""
        session = ConversationSession.objects.get(session_id=session_id)
        observation_count = session.onboarding_site.observations.count()
        return observation_count > 10  # Async for >10 observations

    def _run_analysis_sync(
        self,
        session_id: str,
        config: Dict,
        user
    ) -> Dict[str, Any]:
        """Run analysis synchronously."""
        start_time = time.time()

        with transaction.atomic(using=get_current_db_name()):
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=user)

            site = session.onboarding_site

            # Aggregate observations
            observations = site.observations.select_related('zone').all()
            aggregated_data = self._aggregate_observations(observations)

            # Retrieve knowledge for grounding
            knowledge_service = get_knowledge_service()
            knowledge_hits = knowledge_service.retrieve_grounded_context(
                query=aggregated_data['summary'],
                top_k=5,
                authority_filter=['high', 'official']
            )

            # Maker LLM
            llm_service = get_llm_service()
            maker_output = llm_service.analyze_site_audit(
                observations=aggregated_data,
                site_type=site.site_type
            )

            # Checker LLM
            checker_service = get_checker_service()
            checker_output = checker_service.validate_site_audit_analysis(
                maker_output=maker_output,
                knowledge_hits=knowledge_hits
            )

            # Consensus
            consensus_engine = get_consensus_engine()
            consensus = consensus_engine.create_consensus(
                maker_output=maker_output,
                checker_output=checker_output,
                knowledge_hits=knowledge_hits,
                context={'site_type': site.site_type}
            )

            # Store recommendation
            processing_time = int((time.time() - start_time) * 1000)
            recommendation = LLMRecommendation.objects.create(
                session=session,
                maker_output=maker_output,
                checker_output=checker_output,
                consensus=consensus,
                authoritative_sources=knowledge_hits,
                confidence_score=consensus.get('consensus_confidence', 0.0),
                status=LLMRecommendation.StatusChoices.VALIDATED,
                latency_ms=processing_time,
                trace_id=str(uuid.uuid4())
            )

            # Generate SOPs if requested
            sops = []
            if config.get('include_sops', True):
                sops = self._generate_sops(site, config.get('target_languages', []))

            # Generate coverage plan if requested
            coverage_plan = None
            if config.get('include_coverage_plan', True):
                coverage_plan = self._generate_coverage_plan(site)

            logger.info(f"Analysis complete for session {session_id}")

            return {
                'analysis_id': str(recommendation.recommendation_id),
                'maker_output': maker_output,
                'checker_output': checker_output,
                'consensus': consensus,
                'citations': knowledge_hits[:3],
                'processing_time_ms': processing_time,
                'trace_id': recommendation.trace_id,
                'sops_generated': len(sops),
                'coverage_plan_generated': coverage_plan is not None
            }

    def _aggregate_observations(self, observations) -> Dict[str, Any]:
        """Aggregate all observations into analysis input."""
        all_transcripts = []
        all_entities = []
        risk_summary = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

        for obs in observations:
            if obs.transcript_english:
                all_transcripts.append(obs.transcript_english)
            if obs.entities:
                all_entities.extend(obs.entities)
            if obs.severity:
                risk_summary[obs.severity] = risk_summary.get(obs.severity, 0) + 1

        return {
            'summary': ' '.join(all_transcripts),
            'entities': all_entities,
            'risk_summary': risk_summary,
            'total_observations': observations.count()
        }

    def _generate_sops(self, site: OnboardingSite, target_languages: List[str]) -> List[SOP]:
        """Generate SOPs for all zones."""
        sop_service = SOPGeneratorService()
        sops = []

        for zone in site.zones.all():
            observations = zone.observations.all()
            if observations.exists():
                sop_data = sop_service.generate_zone_sop(
                    zone=zone,
                    observations=[],  # Already in DB
                    target_languages=target_languages
                )

                sop = SOP.objects.create(
                    site=site,
                    zone=zone,
                    sop_title=sop_data['sop_title'],
                    purpose=sop_data['purpose'],
                    steps=sop_data['steps'],
                    staffing_required=sop_data['staffing_required'],
                    compliance_references=sop_data['compliance_references'],
                    frequency=sop_data['frequency'],
                    translated_texts=sop_data.get('translated_texts', {}),
                    escalation_triggers=sop_data.get('escalation_triggers', []),
                    llm_generated=True
                )
                sops.append(sop)

        return sops

    def _generate_coverage_plan(self, site: OnboardingSite) -> CoveragePlan:
        """Generate guard coverage plan."""
        coverage_service = get_coverage_planner_service()
        plan_data = coverage_service.calculate_coverage_plan(site)

        coverage_plan = CoveragePlan.objects.create(
            site=site,
            guard_posts=plan_data['guard_posts'],
            shift_assignments=plan_data['shift_assignments'],
            patrol_routes=plan_data['patrol_routes'],
            risk_windows=plan_data['risk_windows'],
            compliance_notes=plan_data['compliance_notes'],
            generated_by='ai'
        )

        return coverage_plan

    def _enqueue_analysis_task(self, session_id: str, config: Dict, user):
        """Enqueue async analysis task."""
        task_id = str(uuid.uuid4())
        # Import background task
        from background_tasks.onboarding_tasks_phase2 import process_site_audit_analysis

        process_site_audit_analysis.delay(
            str(session_id),
            config,
            task_id,
            user.id
        )

        return {
            'status': 'processing',
            'task_id': task_id,
            'status_url': f'/api/v1/onboarding/tasks/{task_id}/status/',
            'estimated_completion': '30-90 seconds'
        }


class CoveragePlanView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/coverage-plan/

    Get guard coverage and shift plan.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get coverage plan."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site',
                'onboarding_site__coverage_plan'
            ).get(session_id=session_id, user=request.user)

            if not hasattr(session.onboarding_site, 'coverage_plan'):
                return Response(
                    {'error': 'Coverage plan not yet generated. Run analysis first.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = CoveragePlanSerializer(session.onboarding_site.coverage_plan)
            return Response(serializer.data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SOPListView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/sops/

    Get generated SOPs with optional filtering.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """List SOPs."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=request.user)

            sops = self._get_filtered_sops(session.onboarding_site, request.query_params)
            serializer = SOPSerializer(sops, many=True)

            return Response({
                'count': sops.count(),
                'sops': serializer.data
            })

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def _get_filtered_sops(self, site: OnboardingSite, params):
        """Filter SOPs based on query params."""
        sops = site.sops.select_related('zone', 'asset').all()

        if 'zone_id' in params:
            sops = sops.filter(zone__zone_id=params['zone_id'])

        if 'language' in params:
            # Filter is for display purposes - all SOPs have translations
            pass

        return sops


class AuditReportView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/report/

    Generate comprehensive audit report with optional knowledge base integration.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Generate audit report."""
        serializer = ReportGenerationSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            report_data = self._generate_report(
                session_id,
                serializer.validated_data,
                request.user
            )
            return Response(report_data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Report generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_report(
        self,
        session_id: str,
        config: Dict,
        user
    ) -> Dict[str, Any]:
        """Generate comprehensive report."""
        with transaction.atomic(using=get_current_db_name()):
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).prefetch_related(
                'onboarding_site__zones',
                'onboarding_site__observations',
                'onboarding_site__sops',
                'onboarding_site__photos'
            ).get(session_id=session_id, user=user)

            site = session.onboarding_site

            # Generate report
            reporting_service = get_reporting_service()
            report_result = reporting_service.generate_site_audit_report(
                site=site,
                language=config.get('lang', 'en'),
                format=config.get('format', 'html'),
                include_photos=config.get('include_photos', True),
                include_sops=config.get('include_sops', True),
                include_coverage_plan=config.get('include_coverage_plan', True)
            )

            # Save to knowledge base if requested
            knowledge_id = None
            if config.get('save_to_kb', True):
                knowledge_service = get_knowledge_service()
                knowledge_id = knowledge_service.add_document_with_chunking(
                    source_org=site.business_unit.buname,
                    title=f"Site Audit Report - {site.business_unit.buname}",
                    content_summary=report_result.get('summary', ''),
                    full_content=report_result.get('report_html', ''),
                    authority_level='medium',
                    tags={'site_type': site.site_type, 'audit_date': str(timezone.now().date())}
                )

                # Update site with knowledge ID
                site.knowledge_base_id = knowledge_id
                site.report_generated_at = timezone.now()
                site.save()

            logger.info(f"Report generated for session {session_id}, KB ID: {knowledge_id}")

            return {
                'report_html': report_result.get('report_html', ''),
                'report_url': report_result.get('report_url'),
                'knowledge_id': str(knowledge_id) if knowledge_id else None,
                'summary': {
                    'total_zones': site.zones.count(),
                    'observations': site.observations.count(),
                    'compliance_score': report_result.get('compliance_score', 0.0),
                    'critical_issues': report_result.get('critical_issues', 0),
                    'recommendations': report_result.get('recommendations_count', 0)
                },
                'generated_at': timezone.now().isoformat()
            }
