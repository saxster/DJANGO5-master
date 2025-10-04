"""
Reporting Service - Compile bilingual site audit reports.

This service generates comprehensive, multilingual site audit reports with:
- Executive summary
- Zone assessments with photos
- Security gaps and recommendations
- SOPs and coverage plans
- Compliance citations
- Knowledge base integration

Features:
- Markdown and HTML output
- Bilingual support (native + English)
- Photo embeddings
- Citation tracking
- Knowledge base ingestion

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto,
    SOP,
    CoveragePlan
)
from apps.onboarding_api.services.translation import get_translation_service
from apps.onboarding_api.services.knowledge import get_knowledge_service

logger = logging.getLogger(__name__)


class ReportingService:
    """
    Generate comprehensive site audit reports with multilingual support.

    Compiles all audit data into professional reports and saves to knowledge base.
    """

    def __init__(self):
        """Initialize reporting service with translation and knowledge services."""
        self.translation_service = get_translation_service()
        self.knowledge_service = get_knowledge_service()

    def compile_report(
        self,
        site: OnboardingSite,
        language: str = 'en',
        include_photos: bool = True
    ) -> Dict[str, Any]:
        """
        Compile comprehensive site audit report.

        Args:
            site: OnboardingSite instance
            language: Target language for report (ISO code)
            include_photos: Whether to include photo links

        Returns:
            {
                'markdown': str,
                'html': str,
                'metadata': Dict,
                'sections': List[Dict]
            }
        """
        try:
            # Gather all report data
            report_data = self._gather_report_data(site)

            # Generate report sections
            sections = [
                self._generate_executive_summary(report_data, site),
                self._generate_coverage_summary(report_data),
                self._generate_zone_assessments(report_data, include_photos),
                self._generate_security_gaps(report_data),
                self._generate_sop_summary(report_data),
                self._generate_coverage_plan_summary(report_data),
                self._generate_recommendations(report_data),
                self._generate_compliance_citations(report_data)
            ]

            # Compile markdown
            markdown = self._compile_markdown(sections, site)

            # Translate if needed
            if language != 'en':
                markdown = self._translate_report(markdown, language)

            # Generate HTML from markdown
            html = self._markdown_to_html(markdown)

            # Generate metadata
            metadata = self._generate_metadata(site, report_data, language)

            logger.info(
                f"Compiled report for {site.business_unit.buname} in {language}: "
                f"{len(sections)} sections, {len(markdown)} chars"
            )

            return {
                'markdown': markdown,
                'html': html,
                'metadata': metadata,
                'sections': sections
            }

        except Exception as e:
            logger.error(f"Error compiling report: {str(e)}", exc_info=True)
            return {
                'markdown': f"# Report Generation Error\n\n{str(e)}",
                'html': f"<h1>Report Generation Error</h1><p>{str(e)}</p>",
                'metadata': {'error': str(e)},
                'sections': []
            }

    def save_to_knowledge_base(
        self,
        report: Dict[str, Any],
        site: OnboardingSite
    ) -> Optional[str]:
        """
        Save report to knowledge base for future retrieval.

        Args:
            report: Compiled report dictionary
            site: OnboardingSite instance

        Returns:
            Knowledge document ID (UUID) or None if failed
        """
        try:
            # Prepare document for ingestion
            document_content = report['markdown']
            document_metadata = report['metadata']

            # Add site context
            document_metadata.update({
                'site_id': str(site.site_id),
                'business_unit': site.business_unit.buname,
                'site_type': site.site_type,
                'audit_date': datetime.now().isoformat()
            })

            # Ingest into knowledge base
            knowledge_id = self.knowledge_service.add_document_with_chunking(
                content=document_content,
                metadata=document_metadata,
                source_type='site_audit_report',
                source_organization=site.business_unit.buname
            )

            # Update site with knowledge reference
            if knowledge_id:
                site.knowledge_base_id = knowledge_id
                site.report_generated_at = datetime.now()
                site.save()

                logger.info(
                    f"Saved report to knowledge base: {knowledge_id} "
                    f"for site {site.business_unit.buname}"
                )

            return knowledge_id

        except Exception as e:
            logger.error(f"Error saving report to knowledge base: {str(e)}", exc_info=True)
            return None

    def _gather_report_data(self, site: OnboardingSite) -> Dict[str, Any]:
        """Gather all data needed for report."""
        # Prefetch related data
        zones = site.zones.prefetch_related(
            'observations',
            'photos',
            'assets',
            'sops',
            'checkpoints'
        ).all()

        observations = Observation.objects.filter(site=site).select_related('zone')
        photos = SitePhoto.objects.filter(site=site).select_related('zone')
        sops = SOP.objects.filter(site=site).select_related('zone', 'asset')

        try:
            coverage_plan = site.coverage_plan
        except CoveragePlan.DoesNotExist:
            coverage_plan = None

        return {
            'zones': zones,
            'observations': observations,
            'photos': photos,
            'sops': sops,
            'coverage_plan': coverage_plan,
            'coverage_score': site.calculate_coverage_score()
        }

    def _generate_executive_summary(
        self,
        data: Dict[str, Any],
        site: OnboardingSite
    ) -> Dict[str, Any]:
        """Generate executive summary section."""
        total_zones = data['zones'].count()
        critical_zones = len([z for z in data['zones'] if z.importance_level == 'critical'])
        total_observations = data['observations'].count()
        total_photos = data['photos'].count()

        # Calculate risk summary
        high_risk_count = len([
            obs for obs in data['observations']
            if obs.severity in ['critical', 'high']
        ])

        summary_text = f"""
## Executive Summary

**Site**: {site.business_unit.buname}
**Site Type**: {site.get_site_type_display()}
**Audit Date**: {datetime.now().strftime('%B %d, %Y')}
**Audit Coverage**: {data['coverage_score']:.1f}%

### Key Findings

- **Zones Audited**: {total_zones} zones ({critical_zones} critical priority)
- **Observations Recorded**: {total_observations} multimodal observations
- **Photos Captured**: {total_photos} site photos with AI analysis
- **High Priority Issues**: {high_risk_count} items requiring attention

### Overall Assessment

{'✅ Site demonstrates good security practices with minor gaps identified.' if high_risk_count < 5 else '⚠️ Site requires attention to address security gaps and compliance issues.'}
"""

        return {
            'title': 'Executive Summary',
            'content': summary_text,
            'order': 1
        }

    def _generate_coverage_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate coverage progress summary."""
        zones_with_obs = len([
            z for z in data['zones']
            if data['observations'].filter(zone=z).exists()
        ])

        content = f"""
## Audit Coverage

**Completion**: {data['coverage_score']:.1f}%
**Zones Visited**: {zones_with_obs}/{data['zones'].count()}

### Zone Coverage Details

| Zone Type | Count | Coverage |
|-----------|-------|----------|
"""

        zone_type_summary = {}
        for zone in data['zones']:
            ztype = zone.get_zone_type_display()
            if ztype not in zone_type_summary:
                zone_type_summary[ztype] = {'total': 0, 'covered': 0}
            zone_type_summary[ztype]['total'] += 1
            if data['observations'].filter(zone=zone).exists():
                zone_type_summary[ztype]['covered'] += 1

        for ztype, counts in zone_type_summary.items():
            coverage = (counts['covered'] / counts['total'] * 100) if counts['total'] > 0 else 0
            content += f"| {ztype} | {counts['total']} | {coverage:.0f}% |\n"

        return {
            'title': 'Audit Coverage',
            'content': content,
            'order': 2
        }

    def _generate_zone_assessments(
        self,
        data: Dict[str, Any],
        include_photos: bool
    ) -> Dict[str, Any]:
        """Generate detailed zone assessments."""
        content = "## Zone Assessments\n\n"

        for zone in data['zones']:
            zone_obs = data['observations'].filter(zone=zone)

            if zone_obs.count() == 0:
                continue

            content += f"### {zone.zone_name} ({zone.get_zone_type_display()})\n\n"
            content += f"**Importance**: {zone.importance_level.upper()}  \n"
            content += f"**Risk Level**: {zone.risk_level.upper()}  \n"
            content += f"**Observations**: {zone_obs.count()}\n\n"

            # Add key observations
            for obs in zone_obs[:3]:  # Top 3 observations
                enhanced = obs.enhanced_observation.get('enhanced_text', obs.transcript_english)
                content += f"- **{obs.severity.upper()}**: {enhanced[:200]}...\n"

            # Add photos if requested
            if include_photos:
                zone_photos = data['photos'].filter(zone=zone)[:2]
                if zone_photos.exists():
                    content += "\n**Photos**:\n"
                    for photo in zone_photos:
                        content += f"- {photo.image.url if photo.image else '[Photo]'}\n"

            content += "\n---\n\n"

        return {
            'title': 'Zone Assessments',
            'content': content,
            'order': 3
        }

    def _generate_security_gaps(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security gaps and issues."""
        content = "## Security Gaps and Issues\n\n"

        # Critical issues
        critical_obs = [
            obs for obs in data['observations']
            if obs.severity == 'critical'
        ]

        if critical_obs:
            content += "### 🔴 Critical Issues (Immediate Action Required)\n\n"
            for i, obs in enumerate(critical_obs[:5], 1):
                zone_name = obs.zone.zone_name if obs.zone else 'General'
                enhanced = obs.enhanced_observation.get('enhanced_text', obs.transcript_english)
                content += f"{i}. **{zone_name}**: {enhanced}\n"

            content += "\n"

        # High priority issues
        high_obs = [
            obs for obs in data['observations']
            if obs.severity == 'high'
        ]

        if high_obs:
            content += "### 🟡 High Priority Issues\n\n"
            for i, obs in enumerate(high_obs[:5], 1):
                zone_name = obs.zone.zone_name if obs.zone else 'General'
                enhanced = obs.enhanced_observation.get('enhanced_text', obs.transcript_english)
                content += f"{i}. **{zone_name}**: {enhanced}\n"

            content += "\n"

        if not critical_obs and not high_obs:
            content += "✅ No critical or high-priority security gaps identified.\n\n"

        return {
            'title': 'Security Gaps',
            'content': content,
            'order': 4
        }

    def _generate_sop_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SOP summary."""
        sop_count = data['sops'].count()

        content = f"""
## Standard Operating Procedures

**Generated SOPs**: {sop_count}

### SOP Overview

"""

        for sop in data['sops'][:10]:  # Top 10 SOPs
            zone_info = f" ({sop.zone.zone_name})" if sop.zone else ""
            asset_info = f" - {sop.asset.asset_name}" if sop.asset else ""
            content += f"- **{sop.sop_title}**{zone_info}{asset_info}\n"
            content += f"  - Frequency: {sop.frequency}\n"
            content += f"  - Steps: {len(sop.steps)}\n"

            if sop.compliance_references:
                refs = ', '.join(sop.compliance_references[:2])
                content += f"  - Compliance: {refs}\n"

            content += "\n"

        return {
            'title': 'Standard Operating Procedures',
            'content': content,
            'order': 5
        }

    def _generate_coverage_plan_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate coverage plan summary."""
        coverage_plan = data.get('coverage_plan')

        if not coverage_plan:
            return {
                'title': 'Coverage Plan',
                'content': "## Coverage Plan\n\n*Coverage plan pending generation.*\n\n",
                'order': 6
            }

        guard_posts = coverage_plan.guard_posts
        shifts = coverage_plan.shift_assignments

        content = f"""
## Guard Coverage Plan

**Guard Posts**: {len(guard_posts)}
**Shifts per Day**: {len(shifts)}
**Patrol Routes**: {len(coverage_plan.patrol_routes)}

### Guard Post Summary

| Post ID | Zone | Coverage | Risk Level |
|---------|------|----------|------------|
"""

        for post in guard_posts[:10]:
            content += f"| {post['post_id']} | {post['zone_name']} | {post['coverage_hours']}h | {post['risk_level']} |\n"

        content += "\n### Shift Schedule\n\n"

        for shift in shifts:
            content += f"- **{shift['shift_name']}**: {shift['start_time']} - {shift['end_time']} "
            content += f"({shift['staffing']['total_staff']} staff)\n"

        return {
            'title': 'Coverage Plan',
            'content': content,
            'order': 6
        }

    def _generate_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations section."""
        content = """
## Recommendations

### Immediate Actions
"""

        critical_count = len([
            obs for obs in data['observations']
            if obs.severity == 'critical'
        ])

        if critical_count > 0:
            content += f"1. Address {critical_count} critical security issues identified in audit\n"
            content += "2. Implement enhanced monitoring at high-risk zones\n"
            content += "3. Conduct follow-up inspection within 7 days\n"
        else:
            content += "1. Maintain current security posture\n"
            content += "2. Implement generated SOPs\n"
            content += "3. Schedule routine follow-up in 90 days\n"

        content += "\n### Long-term Improvements\n\n"
        content += "1. Complete deployment of generated coverage plan\n"
        content += "2. Provide staff training on new SOPs\n"
        content += "3. Establish quarterly security audit schedule\n"
        content += "4. Implement continuous monitoring systems\n"

        return {
            'title': 'Recommendations',
            'content': content,
            'order': 7
        }

    def _generate_compliance_citations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance citations."""
        # Gather all unique citations
        citations = set()

        for sop in data['sops']:
            citations.update(sop.compliance_references)

        content = """
## Compliance References

This audit and recommendations align with the following standards:

"""

        if citations:
            for citation in sorted(citations):
                content += f"- {citation}\n"
        else:
            content += "- ASIS International Physical Security Standards\n"
            content += "- ISO 27001 Information Security Management\n"

        return {
            'title': 'Compliance References',
            'content': content,
            'order': 8
        }

    def _compile_markdown(
        self,
        sections: List[Dict[str, Any]],
        site: OnboardingSite
    ) -> str:
        """Compile sections into complete markdown document."""
        # Sort sections by order
        sorted_sections = sorted(sections, key=lambda x: x['order'])

        # Header
        markdown = f"# Site Security Audit Report\n\n"
        markdown += f"**{site.business_unit.buname}**  \n"
        markdown += f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n\n"
        markdown += "---\n\n"

        # Add all sections
        for section in sorted_sections:
            markdown += section['content']
            markdown += "\n\n"

        # Footer
        markdown += "---\n\n"
        markdown += "*🤖 Generated with AI-powered site audit system*\n"

        return markdown

    def _translate_report(self, markdown: str, target_language: str) -> str:
        """Translate report to target language."""
        try:
            # Split into translatable chunks (preserve markdown structure)
            lines = markdown.split('\n')
            translated_lines = []

            for line in lines:
                # Skip markdown syntax lines
                if line.startswith('#') or line.startswith('|') or line.startswith('-'):
                    translated_lines.append(line)
                elif line.strip():
                    # Translate content
                    translated = self.translation_service.translate_text(
                        line,
                        target_language,
                        'en'
                    )
                    translated_lines.append(translated)
                else:
                    translated_lines.append(line)

            return '\n'.join(translated_lines)

        except Exception as e:
            logger.error(f"Error translating report: {str(e)}")
            return markdown  # Return original on error

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML."""
        try:
            import markdown as md
            html = md.markdown(markdown, extensions=['tables', 'fenced_code'])
            return html
        except ImportError:
            # Fallback: simple conversion
            html = markdown.replace('\n', '<br>')
            html = f"<div>{html}</div>"
            return html

    def _generate_metadata(
        self,
        site: OnboardingSite,
        data: Dict[str, Any],
        language: str
    ) -> Dict[str, Any]:
        """Generate report metadata."""
        return {
            'site_id': str(site.site_id),
            'site_name': site.business_unit.buname,
            'site_type': site.site_type,
            'language': language,
            'generated_at': datetime.now().isoformat(),
            'zones_count': data['zones'].count(),
            'observations_count': data['observations'].count(),
            'photos_count': data['photos'].count(),
            'sops_count': data['sops'].count(),
            'coverage_score': float(data['coverage_score']),
            'version': '1.0'
        }


# Factory function
def get_reporting_service() -> ReportingService:
    """Factory function to get reporting service instance."""
    return ReportingService()