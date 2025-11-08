"""
Report Learning Service - THE SELF-IMPROVING ENGINE

This is the heart of the self-improvement system. It:
1. Analyzes exemplar reports to extract patterns
2. Identifies incident trends and recurring root causes
3. Suggests preventive actions based on historical data
4. Refines AI questioning strategies based on what works
5. Learns from supervisor feedback to improve quality detection
6. Predicts incident likelihood and severity
7. Adapts to your organization's specific context

The system literally gets smarter with every report created.
"""

import logging
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q
from django.core.cache import cache

from apps.report_generation.models import (
    GeneratedReport,
    ReportExemplar,
    ReportIncidentTrend,
    ReportAIInteraction,
    ReportQualityMetrics,
    ReportTemplate
)
from apps.report_generation.services.narrative_analysis_service import NarrativeAnalysisService

logger = logging.getLogger(__name__)


class ReportLearningService:
    """
    Self-improving AI that learns from every report to get better over time.
    
    Core Learning Mechanisms:
    1. Exemplar Pattern Extraction
    2. Incident Trend Detection
    3. Questioning Strategy Optimization
    4. Quality Prediction
    5. Preventive Intelligence
    """
    
    # Cache keys for learned patterns
    CACHE_KEY_EXEMPLAR_PATTERNS = 'report_learning:exemplar_patterns:{category}'
    CACHE_KEY_INCIDENT_TRENDS = 'report_learning:incident_trends:{tenant_id}'
    CACHE_KEY_QUESTION_EFFECTIVENESS = 'report_learning:question_effectiveness'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # ==================================================================
    # LEARNING MECHANISM 1: EXEMPLAR PATTERN EXTRACTION
    # ==================================================================
    
    @classmethod
    def analyze_exemplar_reports(cls, category: str, tenant_id: int) -> Dict:
        """
        Analyze all exemplar reports in a category to extract patterns.
        
        SELF-IMPROVING: Learns what "good" looks like for each report type.
        
        Returns:
            Dict with extracted patterns, common structures, quality benchmarks
        """
        cache_key = cls.CACHE_KEY_EXEMPLAR_PATTERNS.format(category=category)
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        exemplars = ReportExemplar.objects.filter(
            report__template__category=category,
            report__tenant_id=tenant_id
        ).select_related('report', 'report__template')
        
        if not exemplars.exists():
            logger.info(f"No exemplars found for category {category}. System will learn as exemplars are created.")
            return {
                'category': category,
                'exemplar_count': 0,
                'patterns': {},
                'learning_status': 'waiting_for_exemplars'
            }
        
        patterns = {
            'category': category,
            'exemplar_count': exemplars.count(),
            'common_root_causes': cls._extract_common_root_causes(exemplars),
            'effective_frameworks': cls._extract_effective_frameworks(exemplars),
            'quality_benchmarks': cls._calculate_quality_benchmarks(exemplars),
            'narrative_patterns': cls._extract_narrative_patterns(exemplars),
            'effective_recommendations': cls._extract_effective_recommendations(exemplars),
            'structural_patterns': cls._extract_structural_patterns(exemplars),
        }
        
        cache.set(cache_key, patterns, cls.CACHE_TIMEOUT)
        logger.info(f"Analyzed {exemplars.count()} exemplars for category {category}")
        
        return patterns
    
    @classmethod
    def _extract_common_root_causes(cls, exemplars) -> List[Dict]:
        """Extract most common root causes from exemplars."""
        root_causes = []
        
        for exemplar in exemplars:
            report_data = exemplar.report.report_data
            root_cause = report_data.get('root_cause') or report_data.get('root_causes')
            
            if root_cause and isinstance(root_cause, str):
                root_causes.append(root_cause.lower().strip())
        
        if not root_causes:
            return []
        
        # Find common patterns
        common = Counter(root_causes).most_common(10)
        
        return [
            {
                'root_cause': cause,
                'frequency': count,
                'percentage': (count / len(root_causes)) * 100
            }
            for cause, count in common
        ]
    
    @classmethod
    def _extract_effective_frameworks(cls, exemplars) -> Dict:
        """Identify which questioning frameworks were most effective."""
        framework_effectiveness = defaultdict(lambda: {'count': 0, 'avg_quality': 0.0})
        
        for exemplar in exemplars:
            frameworks_used = exemplar.demonstrates_frameworks
            quality_score = exemplar.report.quality_score
            
            if isinstance(frameworks_used, list):
                for framework in frameworks_used:
                    framework_effectiveness[framework]['count'] += 1
                    framework_effectiveness[framework]['avg_quality'] += quality_score
        
        # Calculate averages
        for framework, stats in framework_effectiveness.items():
            if stats['count'] > 0:
                stats['avg_quality'] = stats['avg_quality'] / stats['count']
        
        # Sort by effectiveness
        sorted_frameworks = sorted(
            framework_effectiveness.items(),
            key=lambda x: (x[1]['avg_quality'], x[1]['count']),
            reverse=True
        )
        
        return {
            framework: stats
            for framework, stats in sorted_frameworks
        }
    
    @classmethod
    def _calculate_quality_benchmarks(cls, exemplars) -> Dict:
        """Calculate quality benchmarks from exemplars."""
        quality_metrics = ReportQualityMetrics.objects.filter(
            report__in=[e.report for e in exemplars]
        )
        
        if not quality_metrics.exists():
            return {}
        
        agg = quality_metrics.aggregate(
            avg_completeness=Avg('completeness_score'),
            avg_clarity=Avg('clarity_score'),
            avg_readability=Avg('readability_score'),
            avg_causal_chain=Avg('causal_chain_strength'),
            avg_actionability=Avg('actionability_score'),
            avg_narrative_length=Avg('narrative_word_count'),
        )
        
        return {
            'target_completeness': round(agg['avg_completeness'] or 85, 1),
            'target_clarity': round(agg['avg_clarity'] or 75, 1),
            'target_readability': round(agg['avg_readability'] or 70, 1),
            'target_causal_chain': round(agg['avg_causal_chain'] or 70, 1),
            'target_actionability': round(agg['avg_actionability'] or 80, 1),
            'target_narrative_length': int(agg['avg_narrative_length'] or 200),
        }
    
    @classmethod
    def _extract_narrative_patterns(cls, exemplars) -> Dict:
        """Extract common narrative patterns from exemplars."""
        all_narratives = []
        
        for exemplar in exemplars:
            narrative_parts = []
            for value in exemplar.report.report_data.values():
                if isinstance(value, str) and len(value) > 50:
                    narrative_parts.append(value)
            
            if narrative_parts:
                narrative = ' '.join(narrative_parts)
                learned = NarrativeAnalysisService.learn_from_exemplar(
                    narrative,
                    exemplar.exemplar_category
                )
                all_narratives.append(learned)
        
        if not all_narratives:
            return {}
        
        # Aggregate patterns
        avg_word_count = sum(n['word_count'] for n in all_narratives) / len(all_narratives)
        avg_readability = sum(n['readability_score'] for n in all_narratives) / len(all_narratives)
        
        # Collect all good phrases
        all_good_phrases = []
        for n in all_narratives:
            all_good_phrases.extend(n['good_phrases'])
        
        return {
            'target_word_count': int(avg_word_count),
            'target_readability': round(avg_readability, 1),
            'good_phrase_examples': all_good_phrases[:20],  # Top 20
            'common_structures': cls._aggregate_structure_patterns(all_narratives),
        }
    
    @classmethod
    def _extract_effective_recommendations(cls, exemplars) -> List[Dict]:
        """Extract patterns from effective recommendations."""
        recommendations = []
        
        for exemplar in exemplars:
            rec = exemplar.report.report_data.get('recommendations') or \
                  exemplar.report.report_data.get('corrective_actions')
            
            if rec and isinstance(rec, str) and len(rec) > 30:
                recommendations.append({
                    'text': rec,
                    'quality_score': exemplar.report.quality_score,
                    'smart_criteria_met': exemplar.report.detailed_quality_metrics.smart_criteria_met
                    if hasattr(exemplar.report, 'detailed_quality_metrics') else 0
                })
        
        # Sort by quality
        recommendations.sort(key=lambda x: (x['smart_criteria_met'], x['quality_score']), reverse=True)
        
        return recommendations[:10]  # Top 10
    
    @classmethod
    def _extract_structural_patterns(cls, exemplars) -> Dict:
        """Extract structural patterns (sections, flow, organization)."""
        patterns = {
            'uses_sections': 0,
            'uses_bullets': 0,
            'uses_numbering': 0,
            'has_summary': 0,
            'has_timeline': 0,
        }
        
        total = exemplars.count()
        
        for exemplar in exemplars:
            text = ' '.join(str(v) for v in exemplar.report.report_data.values() if isinstance(v, str))
            
            if 'summary:' in text.lower() or 'overview:' in text.lower():
                patterns['has_summary'] += 1
            if any(section in text.lower() for section in ['background:', 'situation:', 'assessment:']):
                patterns['uses_sections'] += 1
            if '\n-' in text or '\n•' in text or '\n*' in text:
                patterns['uses_bullets'] += 1
            if '\n1.' in text or '\n2.' in text:
                patterns['uses_numbering'] += 1
            if 'timeline' in text.lower() or any(word in text for word in ['first', 'then', 'next', 'finally']):
                patterns['has_timeline'] += 1
        
        # Convert to percentages
        return {
            key: round((count / total) * 100, 1) if total > 0 else 0
            for key, count in patterns.items()
        }
    
    @classmethod
    def _aggregate_structure_patterns(cls, narratives: List[Dict]) -> Dict:
        """Aggregate structural patterns from narratives."""
        total = len(narratives)
        if total == 0:
            return {}
        
        aggregated = {
            'uses_bullets_percent': sum(1 for n in narratives if n.get('structure_patterns', {}).get('uses_bullets')) / total * 100,
            'uses_numbering_percent': sum(1 for n in narratives if n.get('structure_patterns', {}).get('uses_numbering')) / total * 100,
            'has_sections_percent': sum(1 for n in narratives if n.get('structure_patterns', {}).get('has_sections')) / total * 100,
            'avg_sentence_length': sum(n.get('structure_patterns', {}).get('average_sentence_length', 0) for n in narratives) / total,
        }
        
        return aggregated
    
    # ==================================================================
    # LEARNING MECHANISM 2: INCIDENT TREND DETECTION
    # ==================================================================
    
    @classmethod
    def identify_incident_trends(cls, tenant_id: int, days_back: int = 90) -> List[ReportIncidentTrend]:
        """
        Analyze historical reports to identify patterns and trends.
        
        SELF-IMPROVING: Learns to predict incidents before they happen.
        
        Returns:
            List of identified trends
        """
        cache_key = cls.CACHE_KEY_INCIDENT_TRENDS.format(tenant_id=tenant_id)
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get approved reports for analysis
        reports = GeneratedReport.objects.filter(
            tenant_id=tenant_id,
            status='approved',
            created_at__gte=cutoff_date,
            template__category__in=['incident', 'rca', 'near_miss']
        ).select_related('template')
        
        if reports.count() < 5:
            logger.info(f"Not enough reports ({reports.count()}) for trend analysis. Need at least 5.")
            return []
        
        identified_trends = []
        
        # Trend 1: Recurring root causes
        recurring_causes = cls._identify_recurring_root_causes(reports)
        identified_trends.extend(recurring_causes)
        
        # Trend 2: Location-based risks
        location_risks = cls._identify_location_risks(reports)
        identified_trends.extend(location_risks)
        
        # Trend 3: Temporal patterns (time of day, day of week)
        temporal_patterns = cls._identify_temporal_patterns(reports)
        identified_trends.extend(temporal_patterns)
        
        # Trend 4: Equipment/asset failures
        equipment_patterns = cls._identify_equipment_patterns(reports)
        identified_trends.extend(equipment_patterns)
        
        # Save trends to database
        saved_trends = []
        for trend_data in identified_trends:
            trend, created = ReportIncidentTrend.objects.update_or_create(
                tenant_id=tenant_id,
                trend_type=trend_data['trend_type'],
                pattern_description=trend_data['pattern_description'],
                defaults={
                    'occurrence_count': trend_data['occurrence_count'],
                    'severity_level': trend_data['severity_level'],
                    'predicted_recurrence_probability': trend_data['probability'],
                    'recommended_actions': trend_data['recommended_actions'],
                    'first_occurrence': trend_data['first_occurrence'],
                    'last_occurrence': trend_data['last_occurrence'],
                    'is_active': True,
                }
            )
            
            # Link related reports
            if 'related_reports' in trend_data:
                trend.related_reports.set(trend_data['related_reports'])
            
            saved_trends.append(trend)
        
        logger.info(f"Identified {len(saved_trends)} trends from {reports.count()} reports")
        
        return saved_trends
    
    @classmethod
    def _identify_recurring_root_causes(cls, reports) -> List[Dict]:
        """Identify root causes that appear multiple times."""
        root_cause_groups = defaultdict(list)
        
        for report in reports:
            root_cause = report.report_data.get('root_cause') or report.report_data.get('root_causes')
            if root_cause and isinstance(root_cause, str):
                # Normalize for matching
                normalized = root_cause.lower().strip()
                root_cause_groups[normalized].append(report)
        
        trends = []
        for root_cause, report_list in root_cause_groups.items():
            if len(report_list) >= 3:  # Threshold: 3+ occurrences
                dates = [r.created_at for r in report_list]
                
                # Calculate recurrence probability
                days_span = (max(dates) - min(dates)).days
                probability = len(report_list) / max(days_span, 1)  # Incidents per day
                
                trends.append({
                    'trend_type': 'recurring_root_cause',
                    'pattern_description': f"Recurring root cause: {root_cause}",
                    'occurrence_count': len(report_list),
                    'severity_level': cls._calculate_average_severity(report_list),
                    'probability': min(probability * 30, 1.0),  # 30-day probability
                    'recommended_actions': cls._generate_preventive_actions(root_cause, report_list),
                    'first_occurrence': min(dates),
                    'last_occurrence': max(dates),
                    'related_reports': report_list,
                })
        
        return trends
    
    @classmethod
    def _identify_location_risks(cls, reports) -> List[Dict]:
        """Identify locations with high incident frequency."""
        location_groups = defaultdict(list)
        
        for report in reports:
            location_id = report.report_data.get('location_id')
            location_name = report.report_data.get('location')
            
            if location_id:
                key = f"{location_id}:{location_name}"
                location_groups[key].append(report)
        
        trends = []
        for location_key, report_list in location_groups.items():
            if len(report_list) >= 3:
                location_id, location_name = location_key.split(':', 1)
                dates = [r.created_at for r in report_list]
                
                trends.append({
                    'trend_type': 'location_risk',
                    'pattern_description': f"High incident rate at {location_name}",
                    'occurrence_count': len(report_list),
                    'severity_level': cls._calculate_average_severity(report_list),
                    'probability': len(report_list) / 90,  # Probability over 90 days
                    'recommended_actions': [
                        f"Conduct safety inspection of {location_name}",
                        f"Review procedures for {location_name}",
                        f"Increase monitoring at {location_name}"
                    ],
                    'first_occurrence': min(dates),
                    'last_occurrence': max(dates),
                    'related_reports': report_list,
                })
        
        return trends
    
    @classmethod
    def _identify_temporal_patterns(cls, reports) -> List[Dict]:
        """Identify time-based patterns (time of day, day of week)."""
        time_groups = defaultdict(list)
        day_groups = defaultdict(list)
        
        for report in reports:
            created_at = report.created_at
            
            # Group by time of day
            hour = created_at.hour
            if 6 <= hour < 14:
                time_period = 'morning_shift'
            elif 14 <= hour < 22:
                time_period = 'afternoon_shift'
            else:
                time_period = 'night_shift'
            
            time_groups[time_period].append(report)
            
            # Group by day of week
            day_name = created_at.strftime('%A')
            day_groups[day_name].append(report)
        
        trends = []
        
        # Time of day patterns
        for period, report_list in time_groups.items():
            if len(report_list) >= 5:
                dates = [r.created_at for r in report_list]
                trends.append({
                    'trend_type': 'temporal_pattern',
                    'pattern_description': f"Increased incidents during {period.replace('_', ' ')}",
                    'occurrence_count': len(report_list),
                    'severity_level': cls._calculate_average_severity(report_list),
                    'probability': 0.3,  # Moderate probability
                    'recommended_actions': [
                        f"Review staffing levels during {period}",
                        f"Increase supervision during {period}",
                        f"Conduct safety briefings before {period}"
                    ],
                    'first_occurrence': min(dates),
                    'last_occurrence': max(dates),
                    'related_reports': report_list,
                })
        
        return trends
    
    @classmethod
    def _identify_equipment_patterns(cls, reports) -> List[Dict]:
        """Identify equipment with recurring issues."""
        equipment_groups = defaultdict(list)
        
        for report in reports:
            equipment_id = report.report_data.get('equipment_id')
            equipment_name = report.report_data.get('equipment')
            
            if equipment_id:
                key = f"{equipment_id}:{equipment_name}"
                equipment_groups[key].append(report)
        
        trends = []
        for equipment_key, report_list in equipment_groups.items():
            if len(report_list) >= 2:  # Lower threshold for equipment
                equipment_id, equipment_name = equipment_key.split(':', 1)
                dates = [r.created_at for r in report_list]
                
                trends.append({
                    'trend_type': 'equipment_failure_pattern',
                    'pattern_description': f"Recurring issues with {equipment_name}",
                    'occurrence_count': len(report_list),
                    'severity_level': cls._calculate_average_severity(report_list),
                    'probability': 0.5,  # Moderate to high probability
                    'recommended_actions': [
                        f"Schedule preventive maintenance for {equipment_name}",
                        f"Inspect {equipment_name} for underlying issues",
                        f"Consider replacement if failures continue"
                    ],
                    'first_occurrence': min(dates),
                    'last_occurrence': max(dates),
                    'related_reports': report_list,
                })
        
        return trends
    
    @classmethod
    def _calculate_average_severity(cls, reports: List[GeneratedReport]) -> int:
        """Calculate average severity from reports."""
        severities = []
        for report in reports:
            severity = report.report_data.get('severity') or report.report_data.get('severity_level')
            if isinstance(severity, int):
                severities.append(severity)
            elif isinstance(severity, str) and severity.isdigit():
                severities.append(int(severity))
        
        return int(sum(severities) / len(severities)) if severities else 3  # Default to medium
    
    @classmethod
    def _generate_preventive_actions(cls, root_cause: str, reports: List[GeneratedReport]) -> List[str]:
        """Generate preventive actions based on root cause and historical data."""
        actions = []
        
        # Analyze recommendations from past reports
        past_recommendations = []
        for report in reports:
            rec = report.report_data.get('recommendations') or \
                  report.report_data.get('corrective_actions') or \
                  report.report_data.get('preventive_actions')
            if rec:
                past_recommendations.append(rec)
        
        # Pattern-based actions
        if 'training' in root_cause or 'skill' in root_cause:
            actions.append("Implement comprehensive training program")
            actions.append("Conduct skills assessment and gap analysis")
        
        if 'maintenance' in root_cause or 'equipment' in root_cause:
            actions.append("Review and update preventive maintenance schedule")
            actions.append("Conduct equipment reliability analysis")
        
        if 'procedure' in root_cause or 'process' in root_cause:
            actions.append("Review and update standard operating procedures")
            actions.append("Implement process verification checks")
        
        if 'communication' in root_cause:
            actions.append("Improve communication protocols")
            actions.append("Implement shift handover checklist")
        
        # Generic fallback
        if not actions:
            actions = [
                "Conduct root cause analysis",
                "Implement corrective actions",
                "Monitor for recurrence"
            ]
        
        return actions[:5]  # Top 5
    
    # ==================================================================
    # LEARNING MECHANISM 3: QUESTIONING STRATEGY OPTIMIZATION
    # ==================================================================
    
    @classmethod
    def optimize_questioning_strategy(cls, template_category: str) -> Dict:
        """
        Analyze which questions led to high-quality reports.
        
        SELF-IMPROVING: Learns which questions are most effective.
        
        Returns:
            Optimized questioning strategy
        """
        # Get interactions from high-quality reports
        high_quality_interactions = ReportAIInteraction.objects.filter(
            report__template__category=template_category,
            report__quality_score__gte=80,
            report__status='approved'
        ).values('question_type').annotate(
            count=Count('id'),
            avg_quality=Avg('report__quality_score')
        ).order_by('-avg_quality')
        
        if not high_quality_interactions:
            return {'status': 'insufficient_data', 'message': 'Need more approved reports to optimize'}
        
        strategy = {
            'category': template_category,
            'recommended_frameworks': [],
            'question_sequence': [],
            'average_iterations_needed': 0,
        }
        
        for interaction in high_quality_interactions:
            strategy['recommended_frameworks'].append({
                'framework': interaction['question_type'],
                'effectiveness': interaction['avg_quality'],
                'usage_count': interaction['count']
            })
        
        # Analyze question sequences that work well
        effective_sequences = cls._analyze_effective_question_sequences(template_category)
        strategy['question_sequence'] = effective_sequences
        
        logger.info(f"Optimized questioning strategy for {template_category}")
        
        return strategy
    
    @classmethod
    def _analyze_effective_question_sequences(cls, category: str) -> List[str]:
        """Analyze sequences of questions that led to quality reports."""
        high_quality_reports = GeneratedReport.objects.filter(
            template__category=category,
            quality_score__gte=80,
            status='approved'
        )[:20]
        
        sequences = []
        for report in high_quality_reports:
            interactions = report.ai_interactions_detailed.order_by('iteration').values_list('question_type', flat=True)
            if interactions:
                sequences.append(list(interactions))
        
        if not sequences:
            return []
        
        # Find most common first questions
        first_questions = [seq[0] for seq in sequences if len(seq) > 0]
        most_common_first = Counter(first_questions).most_common(3)
        
        return [q for q, count in most_common_first]
    
    # ==================================================================
    # LEARNING MECHANISM 4: QUALITY PREDICTION
    # ==================================================================
    
    @classmethod
    def predict_report_quality(cls, report: GeneratedReport) -> Dict:
        """
        Predict final quality score based on current state.
        
        SELF-IMPROVING: Learns patterns that correlate with quality.
        
        Returns:
            Predicted quality metrics and confidence
        """
        # Get historical data for this template category
        historical = GeneratedReport.objects.filter(
            template__category=report.template.category,
            tenant=report.tenant,
            status='approved',
            quality_score__gt=0
        )
        
        if historical.count() < 10:
            return {
                'prediction': 'insufficient_data',
                'message': 'Need at least 10 approved reports for prediction'
            }
        
        # Calculate current report's characteristics
        current_chars = cls._extract_report_characteristics(report)
        
        # Find similar historical reports
        similar_scores = []
        for hist_report in historical[:50]:  # Sample recent 50
            hist_chars = cls._extract_report_characteristics(hist_report)
            similarity = cls._calculate_similarity(current_chars, hist_chars)
            
            if similarity > 0.6:  # 60% similarity threshold
                similar_scores.append(hist_report.quality_score)
        
        if not similar_scores:
            avg_score = historical.aggregate(Avg('quality_score'))['quality_score__avg']
            return {
                'predicted_score': round(avg_score, 1),
                'confidence': 'low',
                'similar_reports_found': 0
            }
        
        predicted = sum(similar_scores) / len(similar_scores)
        
        return {
            'predicted_score': round(predicted, 1),
            'confidence': 'high' if len(similar_scores) >= 5 else 'medium',
            'similar_reports_found': len(similar_scores),
            'score_range': (min(similar_scores), max(similar_scores))
        }
    
    @classmethod
    def _extract_report_characteristics(cls, report: GeneratedReport) -> Dict:
        """Extract characteristics for similarity comparison."""
        data = report.report_data
        
        return {
            'field_count': len([v for v in data.values() if v]),
            'total_word_count': sum(len(str(v).split()) for v in data.values() if isinstance(v, str)),
            'has_root_cause': bool(data.get('root_cause') or data.get('root_causes')),
            'has_recommendations': bool(data.get('recommendations') or data.get('corrective_actions')),
            'ai_interaction_count': report.ai_interactions_detailed.count() if hasattr(report, 'ai_interactions_detailed') else 0,
        }
    
    @classmethod
    def _calculate_similarity(cls, chars1: Dict, chars2: Dict) -> float:
        """Calculate similarity between two sets of characteristics."""
        similarity_score = 0.0
        total_comparisons = 0
        
        # Compare field counts
        if chars1['field_count'] > 0 and chars2['field_count'] > 0:
            field_similarity = min(chars1['field_count'], chars2['field_count']) / max(chars1['field_count'], chars2['field_count'])
            similarity_score += field_similarity
            total_comparisons += 1
        
        # Compare word counts
        if chars1['total_word_count'] > 0 and chars2['total_word_count'] > 0:
            word_similarity = min(chars1['total_word_count'], chars2['total_word_count']) / max(chars1['total_word_count'], chars2['total_word_count'])
            similarity_score += word_similarity
            total_comparisons += 1
        
        # Boolean comparisons
        if chars1['has_root_cause'] == chars2['has_root_cause']:
            similarity_score += 1
            total_comparisons += 1
        
        if chars1['has_recommendations'] == chars2['has_recommendations']:
            similarity_score += 1
            total_comparisons += 1
        
        return similarity_score / total_comparisons if total_comparisons > 0 else 0.0
    
    # ==================================================================
    # LEARNING MECHANISM 5: CONTINUOUS IMPROVEMENT FROM FEEDBACK
    # ==================================================================
    
    @classmethod
    def learn_from_supervisor_feedback(cls, report: GeneratedReport, feedback: str, changes_made: Dict) -> None:
        """
        Learn from supervisor corrections and feedback.
        
        SELF-IMPROVING: Updates quality detection rules based on what supervisors flag.
        """
        # Analyze what was corrected
        if 'vague_language' in changes_made:
            # Learn new vague patterns
            for vague_phrase in changes_made['vague_language']:
                NarrativeAnalysisService.update_vague_patterns_from_feedback([
                    {'flagged_phrase': vague_phrase, 'category': 'generic'}
                ])
        
        if 'missing_details' in changes_made:
            # Learn which details are critical
            logger.info(f"Learned that {changes_made['missing_details']} are critical details")
        
        # Update questioning strategy if feedback indicates missing info
        if 'incomplete' in feedback.lower():
            cls._update_questioning_from_feedback(report.template.category, feedback)
        
        logger.info(f"Learned from supervisor feedback on report {report.id}")
    
    @classmethod
    def _update_questioning_from_feedback(cls, category: str, feedback: str) -> None:
        """Update questioning strategy based on feedback."""
        # This could update the template's questioning_strategy field
        # For now, log for future implementation
        logger.info(f"Suggestion to update questioning for {category}: {feedback}")
    
    # ==================================================================
    # HELPER METHODS
    # ==================================================================
    
    @classmethod
    def get_learning_statistics(cls, tenant_id: int) -> Dict:
        """
        Get statistics on system learning progress.
        
        Shows how much the system has learned and improved.
        """
        total_reports = GeneratedReport.objects.filter(tenant_id=tenant_id).count()
        approved_reports = GeneratedReport.objects.filter(tenant_id=tenant_id, status='approved').count()
        exemplar_count = ReportExemplar.objects.filter(report__tenant_id=tenant_id).count()
        trends_identified = ReportIncidentTrend.objects.filter(tenant_id=tenant_id, is_active=True).count()
        
        # Quality improvement over time
        recent_quality = GeneratedReport.objects.filter(
            tenant_id=tenant_id,
            status='approved',
            created_at__gte=datetime.now() - timedelta(days=30)
        ).aggregate(Avg('quality_score'))['quality_score__avg'] or 0
        
        older_quality = GeneratedReport.objects.filter(
            tenant_id=tenant_id,
            status='approved',
            created_at__lt=datetime.now() - timedelta(days=30),
            created_at__gte=datetime.now() - timedelta(days=60)
        ).aggregate(Avg('quality_score'))['quality_score__avg'] or 0
        
        quality_improvement = recent_quality - older_quality if older_quality > 0 else 0
        
        return {
            'total_reports': total_reports,
            'approved_reports': approved_reports,
            'exemplar_reports': exemplar_count,
            'identified_trends': trends_identified,
            'recent_avg_quality': round(recent_quality, 1),
            'quality_improvement': round(quality_improvement, 1),
            'learning_maturity': cls._calculate_learning_maturity(total_reports, exemplar_count, trends_identified),
        }
    
    @classmethod
    def _calculate_learning_maturity(cls, total_reports: int, exemplars: int, trends: int) -> str:
        """Calculate system learning maturity level."""
        score = (total_reports * 0.5) + (exemplars * 5) + (trends * 3)
        
        if score < 50:
            return 'nascent'
        elif score < 150:
            return 'developing'
        elif score < 300:
            return 'mature'
        else:
            return 'advanced'
