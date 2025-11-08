"""
Quality Gate Service

Validates report quality before submission using multiple criteria:
- Completeness: Are all required fields filled?
- Clarity: Is the writing clear and specific?
- Consistency: Do facts match system records?
- Actionability: Are recommendations SMART?

Reports must meet minimum thresholds to be submitted for review.
"""

import logging
import re
from typing import Dict, List, Tuple
from apps.report_generation.models import (
    GeneratedReport,
    ReportQualityMetrics
)
from apps.report_generation.services.narrative_analysis_service import NarrativeAnalysisService

logger = logging.getLogger(__name__)


class QualityGateService:
    """
    Validates report quality and enforces minimum standards.
    Provides detailed feedback for improvement.
    """
    
    # Minimum thresholds for submission
    MIN_COMPLETENESS_SCORE = 70
    MIN_CLARITY_SCORE = 60
    MIN_NARRATIVE_LENGTH = 100  # words
    MAX_JARGON_DENSITY = 0.05  # 5%
    
    @classmethod
    def can_submit(cls, report: GeneratedReport) -> Tuple[bool, List[str]]:
        """
        Check if report meets quality gates for submission.
        
        Returns:
            Tuple of (can_submit: bool, issues: List[str])
        """
        issues = []
        
        # Calculate all quality metrics
        metrics = cls.calculate_quality_metrics(report)
        
        # Check completeness
        if metrics['completeness_score'] < cls.MIN_COMPLETENESS_SCORE:
            issues.append(
                f"Report completeness is {metrics['completeness_score']}%. "
                f"Minimum required: {cls.MIN_COMPLETENESS_SCORE}%. "
                f"Please fill in all required fields."
            )
        
        # Check clarity
        if metrics['clarity_score'] < cls.MIN_CLARITY_SCORE:
            issues.append(
                f"Report clarity is {metrics['clarity_score']}%. "
                f"Minimum required: {cls.MIN_CLARITY_SCORE}%. "
                f"Please make your descriptions more specific and clear."
            )
        
        # Check narrative length
        if metrics['narrative_word_count'] < cls.MIN_NARRATIVE_LENGTH:
            issues.append(
                f"Narrative section has {metrics['narrative_word_count']} words. "
                f"Minimum required: {cls.MIN_NARRATIVE_LENGTH} words. "
                f"Please provide more detail."
            )
        
        # Check for critical empty fields
        critical_empty = cls._check_critical_fields(report)
        if critical_empty:
            issues.append(
                f"Critical fields are empty: {', '.join(critical_empty)}. "
                "These must be completed."
            )
        
        # Check for root cause (for incident/RCA reports)
        if report.template.category in ['incident', 'rca', 'capa']:
            if not cls._has_root_cause(report):
                issues.append(
                    "No root cause identified. Please complete the root cause analysis."
                )
        
        # Check for actionable recommendations
        if not cls._has_actionable_recommendations(report):
            issues.append(
                "No actionable recommendations provided. "
                "Please add specific actions with who, what, and when."
            )
        
        can_submit = len(issues) == 0
        return can_submit, issues
    
    @classmethod
    def calculate_quality_metrics(cls, report: GeneratedReport) -> Dict:
        """
        Calculate comprehensive quality metrics for a report.
        
        Returns:
            Dict with all quality metrics
        """
        # Completeness score
        completeness_score, field_stats = cls.calculate_completeness_score(report)
        
        # Clarity score
        clarity_score, clarity_details = cls.calculate_clarity_score(report)
        
        # Narrative analysis
        narrative = cls._extract_narrative_text(report)
        narrative_word_count = len(narrative.split())
        
        # Jargon detection
        jargon_density, jargon_examples = cls.detect_jargon_and_assumptions(narrative)
        
        # Causal chain analysis
        causal_chain_strength = cls.validate_causal_chain(narrative)
        
        # Actionability
        actionability_score, smart_criteria = cls.assess_actionability(report)
        
        # Overall quality score (weighted average)
        quality_score = int(
            (completeness_score * 0.4) +
            (clarity_score * 0.3) +
            (causal_chain_strength * 0.15) +
            (actionability_score * 0.15)
        )
        
        metrics = {
            'quality_score': quality_score,
            'completeness_score': completeness_score,
            'clarity_score': clarity_score,
            'narrative_word_count': narrative_word_count,
            'jargon_density': jargon_density,
            'jargon_examples': jargon_examples,
            'causal_chain_strength': causal_chain_strength,
            'actionability_score': actionability_score,
            'smart_criteria_met': smart_criteria,
            **field_stats,
            **clarity_details
        }
        
        # Update report scores
        report.quality_score = quality_score
        report.completeness_score = completeness_score
        report.clarity_score = clarity_score
        report.save(update_fields=['quality_score', 'completeness_score', 'clarity_score'])
        
        # Create or update detailed metrics
        cls._save_detailed_metrics(report, metrics)
        
        return metrics
    
    @classmethod
    def calculate_completeness_score(cls, report: GeneratedReport) -> Tuple[int, Dict]:
        """
        Calculate report completeness based on filled fields.
        
        Returns:
            Tuple of (score: int, field_statistics: Dict)
        """
        template_schema = report.template.schema
        report_data = report.report_data
        
        total_fields = 0
        filled_fields = 0
        required_fields = 0
        required_filled = 0
        
        for field_name, field_spec in template_schema.get('fields', {}).items():
            total_fields += 1
            value = report_data.get(field_name)
            
            is_filled = cls._is_field_filled(value)
            
            if is_filled:
                filled_fields += 1
            
            if field_spec.get('required', False):
                required_fields += 1
                if is_filled:
                    required_filled += 1
        
        if total_fields == 0:
            return 0, {}
        
        # Score based on required fields (70%) + optional fields (30%)
        required_score = (required_filled / required_fields * 100) if required_fields > 0 else 100
        optional_score = (filled_fields / total_fields * 100)
        
        completeness_score = int(required_score * 0.7 + optional_score * 0.3)
        
        stats = {
            'total_fields': total_fields,
            'filled_fields': filled_fields,
            'required_fields': required_fields,
            'required_filled': required_filled,
        }
        
        return completeness_score, stats
    
    @classmethod
    def calculate_clarity_score(cls, report: GeneratedReport) -> Tuple[int, Dict]:
        """
        Calculate clarity score based on readability and specificity.
        
        Returns:
            Tuple of (score: int, details: Dict)
        """
        narrative = cls._extract_narrative_text(report)
        
        if not narrative or len(narrative) < 50:
            return 0, {'readability_score': 0}
        
        # Readability score (Flesch-Kincaid)
        readability = NarrativeAnalysisService.calculate_readability_score(narrative)
        
        # Vague language detection
        vague_count = len(NarrativeAnalysisService.detect_vague_language(narrative))
        vague_density = vague_count / max(len(narrative.split()), 1)
        
        # Specific vs generic language
        specificity_score = cls._calculate_specificity_score(narrative)
        
        # Assumption detection
        assumption_count = cls._count_assumptions(narrative)
        
        # Weighted clarity score
        readability_component = min(readability, 100) * 0.3
        vague_penalty = max(0, 100 - (vague_density * 1000)) * 0.25
        specificity_component = specificity_score * 0.25
        assumption_penalty = max(0, 100 - (assumption_count * 10)) * 0.2
        
        clarity_score = int(
            readability_component +
            vague_penalty +
            specificity_component +
            assumption_penalty
        )
        
        details = {
            'readability_score': readability,
            'vague_language_count': vague_count,
            'specificity_score': specificity_score,
            'assumption_count': assumption_count,
        }
        
        return clarity_score, details
    
    @classmethod
    def detect_jargon_and_assumptions(cls, text: str) -> Tuple[float, List[Dict]]:
        """
        Detect jargon, vague language, and assumptions.
        
        Returns:
            Tuple of (jargon_density: float, examples: List[Dict])
        """
        if not text:
            return 0.0, []
        
        vague_language = NarrativeAnalysisService.detect_vague_language(text)
        
        # Calculate density
        word_count = len(text.split())
        jargon_density = len(vague_language) / max(word_count, 1)
        
        # Format examples with suggestions
        examples = []
        for vague in vague_language:
            suggestion = NarrativeAnalysisService.suggest_specific_language(vague)
            examples.append({
                'vague_phrase': vague,
                'suggestion': suggestion,
                'location': text.find(vague)
            })
        
        return jargon_density, examples[:10]  # Limit to top 10
    
    @classmethod
    def validate_causal_chain(cls, narrative: str) -> int:
        """
        Validate logical flow and causal reasoning.
        
        Returns:
            Causal chain strength score (0-100)
        """
        if not narrative or len(narrative) < 50:
            return 0
        
        score = 50  # Start at neutral
        
        # Positive indicators of good causal reasoning
        causal_indicators = [
            'because', 'since', 'therefore', 'thus', 'as a result',
            'which caused', 'led to', 'resulting in', 'due to'
        ]
        causal_count = sum(1 for indicator in causal_indicators if indicator in narrative.lower())
        score += min(causal_count * 5, 30)
        
        # Check for structured reasoning (numbered points, bullets)
        has_structure = bool(re.search(r'(1\.|2\.|3\.|\n-|\n\*)', narrative))
        if has_structure:
            score += 10
        
        # Negative indicators (vague causation)
        vague_causal = ['issue', 'problem', 'thing', 'stuff', 'somehow']
        vague_count = sum(1 for word in vague_causal if word in narrative.lower())
        score -= min(vague_count * 5, 20)
        
        # Check for unexplained jumps
        if 'therefore' in narrative.lower() or 'thus' in narrative.lower():
            if 'because' not in narrative.lower() and 'since' not in narrative.lower():
                score -= 10
        
        return max(0, min(score, 100))
    
    @classmethod
    def assess_actionability(cls, report: GeneratedReport) -> Tuple[int, int]:
        """
        Assess if recommendations are SMART (Specific, Measurable, Achievable, Relevant, Time-bound).
        
        Returns:
            Tuple of (actionability_score: int, smart_criteria_met: int)
        """
        recommendations = cls._extract_recommendations(report)
        
        if not recommendations:
            return 0, 0
        
        smart_criteria_met = 0
        
        # Specific: Contains concrete actions or details
        if cls._has_specific_actions(recommendations):
            smart_criteria_met += 1
        
        # Measurable: Contains numbers, percentages, or measurable outcomes
        if re.search(r'\d+|percent|measure|metric', recommendations, re.IGNORECASE):
            smart_criteria_met += 1
        
        # Achievable: Contains responsible person/role
        if re.search(r'by|assigned to|responsible|owner|technician|manager', recommendations, re.IGNORECASE):
            smart_criteria_met += 1
        
        # Relevant: Related to root cause or prevention
        if any(word in recommendations.lower() for word in ['prevent', 'avoid', 'ensure', 'improve']):
            smart_criteria_met += 1
        
        # Time-bound: Contains deadline or timeframe
        if re.search(r'by|within|before|deadline|date|\d{1,2}/\d{1,2}', recommendations, re.IGNORECASE):
            smart_criteria_met += 1
        
        actionability_score = int((smart_criteria_met / 5) * 100)
        
        return actionability_score, smart_criteria_met
    
    @classmethod
    def check_consistency_with_facts(cls, report: GeneratedReport, system_data: Dict) -> List[str]:
        """
        Validate report data against system records.
        
        Returns:
            List of inconsistencies found
        """
        inconsistencies = []
        
        # Compare dates
        report_date = report.report_data.get('incident_date')
        if report_date and system_data.get('expected_date'):
            if report_date != system_data['expected_date']:
                inconsistencies.append(
                    f"Date mismatch: Report shows {report_date}, "
                    f"system shows {system_data['expected_date']}"
                )
        
        # Compare people
        report_people = report.report_data.get('people_involved', [])
        if system_data.get('assigned_people'):
            system_people = [p.id for p in system_data['assigned_people']]
            missing_people = set(system_people) - set(report_people)
            if missing_people:
                inconsistencies.append(
                    f"Missing people from system records: {missing_people}"
                )
        
        # Compare location
        report_location = report.report_data.get('location')
        if report_location and system_data.get('location'):
            if report_location != system_data['location']:
                inconsistencies.append(
                    f"Location mismatch: Report shows {report_location}, "
                    f"system shows {system_data['location']}"
                )
        
        return inconsistencies
    
    # Private helper methods
    
    @classmethod
    def _is_field_filled(cls, value) -> bool:
        """Check if a field has meaningful content."""
        if value is None:
            return False
        if isinstance(value, str):
            return len(value.strip()) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True
    
    @classmethod
    def _extract_narrative_text(cls, report: GeneratedReport) -> str:
        """Extract all narrative/text fields from report."""
        narrative_parts = []
        
        for field_name, value in report.report_data.items():
            if isinstance(value, str) and len(value) > 20:
                narrative_parts.append(value)
        
        return ' '.join(narrative_parts)
    
    @classmethod
    def _extract_recommendations(cls, report: GeneratedReport) -> str:
        """Extract recommendations/corrective actions from report."""
        rec_fields = [
            'recommendations',
            'corrective_actions',
            'preventive_actions',
            'action_items',
            'next_steps'
        ]
        
        recommendations = []
        for field in rec_fields:
            value = report.report_data.get(field)
            if value and isinstance(value, str):
                recommendations.append(value)
        
        return ' '.join(recommendations)
    
    @classmethod
    def _calculate_specificity_score(cls, text: str) -> int:
        """Calculate how specific vs generic the language is."""
        if not text:
            return 0
        
        # Specific indicators (numbers, proper nouns, technical terms)
        specific_patterns = [
            r'\d+',  # Numbers
            r'[A-Z][a-z]+\s[A-Z][a-z]+',  # Proper names
            r'[A-Z]{2,}',  # Acronyms
            r'\d{1,2}:\d{2}',  # Times
            r'\d{1,2}/\d{1,2}',  # Dates
        ]
        
        specific_count = sum(
            len(re.findall(pattern, text))
            for pattern in specific_patterns
        )
        
        word_count = len(text.split())
        specificity_ratio = specific_count / max(word_count, 1)
        
        return min(int(specificity_ratio * 200), 100)
    
    @classmethod
    def _count_assumptions(cls, text: str) -> int:
        """Count assumption indicators in text."""
        assumption_words = [
            'probably', 'maybe', 'might', 'could be',
            'possibly', 'perhaps', 'likely', 'assume'
        ]
        
        return sum(1 for word in assumption_words if word in text.lower())
    
    @classmethod
    def _check_critical_fields(cls, report: GeneratedReport) -> List[str]:
        """Check for empty critical fields."""
        template_schema = report.template.schema
        report_data = report.report_data
        
        critical_empty = []
        for field_name, field_spec in template_schema.get('fields', {}).items():
            if field_spec.get('critical', False) or field_spec.get('required', False):
                value = report_data.get(field_name)
                if not cls._is_field_filled(value):
                    critical_empty.append(field_name)
        
        return critical_empty
    
    @classmethod
    def _has_root_cause(cls, report: GeneratedReport) -> bool:
        """Check if root cause is identified."""
        root_cause_fields = ['root_cause', 'root_causes', 'primary_cause']
        
        for field in root_cause_fields:
            value = report.report_data.get(field)
            if value and isinstance(value, str) and len(value.strip()) > 10:
                return True
        
        # Check AI interactions for 5 Whys completion
        five_whys = report.ai_interactions_detailed.filter(
            question_type='5_whys'
        ).count()
        
        return five_whys >= 3
    
    @classmethod
    def _has_actionable_recommendations(cls, report: GeneratedReport) -> bool:
        """Check if report has actionable recommendations."""
        recommendations = cls._extract_recommendations(report)
        
        if not recommendations or len(recommendations.strip()) < 20:
            return False
        
        # Check for action verbs
        action_verbs = [
            'implement', 'create', 'update', 'train', 'review',
            'install', 'repair', 'replace', 'inspect', 'test'
        ]
        
        has_action = any(verb in recommendations.lower() for verb in action_verbs)
        
        return has_action
    
    @classmethod
    def _has_specific_actions(cls, recommendations: str) -> bool:
        """Check if recommendations contain specific actions."""
        action_indicators = [
            'will', 'shall', 'must', 'should',
            'implement', 'install', 'create', 'update'
        ]
        
        return any(indicator in recommendations.lower() for indicator in action_indicators)
    
    @classmethod
    def _save_detailed_metrics(cls, report: GeneratedReport, metrics: Dict) -> None:
        """Save or update detailed quality metrics."""
        improvement_suggestions = cls._generate_improvement_suggestions(report, metrics)
        
        ReportQualityMetrics.objects.update_or_create(
            report=report,
            defaults={
                'completeness_score': metrics['completeness_score'],
                'required_fields_filled': metrics.get('required_filled', 0),
                'total_required_fields': metrics.get('required_fields', 0),
                'narrative_word_count': metrics['narrative_word_count'],
                'clarity_score': metrics['clarity_score'],
                'readability_score': metrics.get('readability_score', 0),
                'jargon_density': metrics['jargon_density'],
                'assumption_count': metrics.get('assumption_count', 0),
                'causal_chain_strength': metrics['causal_chain_strength'],
                'actionability_score': metrics['actionability_score'],
                'smart_criteria_met': metrics['smart_criteria_met'],
                'improvement_suggestions': improvement_suggestions,
                'jargon_examples': metrics['jargon_examples'],
                'missing_details': [],
            }
        )
    
    @classmethod
    def _generate_improvement_suggestions(cls, report: GeneratedReport, metrics: Dict) -> List[str]:
        """Generate specific suggestions for improvement."""
        suggestions = []
        
        if metrics['completeness_score'] < 70:
            suggestions.append(
                "Fill in all required fields to improve completeness score."
            )
        
        if metrics['clarity_score'] < 60:
            suggestions.append(
                "Replace vague language with specific details (numbers, names, times)."
            )
        
        if metrics['narrative_word_count'] < cls.MIN_NARRATIVE_LENGTH:
            needed = cls.MIN_NARRATIVE_LENGTH - metrics['narrative_word_count']
            suggestions.append(
                f"Add at least {needed} more words to narrative sections for detail."
            )
        
        if metrics['jargon_density'] > cls.MAX_JARGON_DENSITY:
            suggestions.append(
                "Reduce use of vague terms like 'issue', 'problem', 'soon', 'many'."
            )
        
        if metrics['causal_chain_strength'] < 50:
            suggestions.append(
                "Strengthen causal reasoning with 'because', 'which led to', 'as a result'."
            )
        
        if metrics['smart_criteria_met'] < 3:
            suggestions.append(
                "Make recommendations SMART: Specific, Measurable, Assigned, Relevant, Time-bound."
            )
        
        return suggestions
