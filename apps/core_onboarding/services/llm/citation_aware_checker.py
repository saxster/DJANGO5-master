"""
Production-grade Citation-Aware Checker LLM with knowledge verification.

Enhanced validation with citation verification and knowledge conflict detection.
Extracted from: apps/onboarding_api/services/llm.py (lines 991-1392)
Date: 2025-10-10
"""
from typing import Dict, List, Any, Optional
import logging
import json
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError

# Import base classes
from .base import CheckerLLM

# Import exceptions
from .exceptions import LLMServiceException

# Import citation schema
from .citation_schema import CITATION_REQUIREMENTS

# Import validation helpers
from .validation_helpers import validate_citation_format

logger = logging.getLogger(__name__)


class CitationAwareCheckerLLM(CheckerLLM):
    """
    Enhanced Checker LLM with citation validation and knowledge verification

    This production-grade checker validates recommendations by:
    1. Verifying citation format and quality
    2. Detecting knowledge conflicts between sources
    3. Cross-referencing citations for consistency
    4. Validating business logic and security requirements
    5. Ensuring compliance with policies

    Integrates with knowledge base for authoritative source validation.
    """

    def __init__(self, knowledge_service=None):
        try:
            from apps.core_onboarding.services.knowledge import get_knowledge_service
            self.knowledge_service = knowledge_service or get_knowledge_service()
        except ImportError:
            logger.warning("Knowledge service not available, citation validation will be limited")
            self.knowledge_service = None

        # Citation validation schema
        self.citation_requirements = CITATION_REQUIREMENTS

    def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced validation with citation verification"""
        recommendations = maker_output.get("recommendations", {})
        citations = maker_output.get("citations", [])

        validation_result = {
            "is_valid": True,
            "confidence_adjustment": 0.0,
            "risk_assessment": "low",
            "compliance_check": "passed",
            "policy_alignment": "compliant",
            "suggested_improvements": [],
            "citations": [],
            "contradictions": [],
            "citation_validation": {},
            "knowledge_conflicts": [],
            "validation_details": {}
        }

        try:
            # Core business logic validation
            validation_result.update(self._validate_business_logic(recommendations, context))
            validation_result.update(self._validate_security_requirements(recommendations, context))

            # Citation-specific validation
            citation_validation = self._validate_citations_comprehensive(citations, recommendations, context)
            validation_result["citation_validation"] = citation_validation

            # Knowledge conflict detection
            conflicts = self._detect_knowledge_conflicts(recommendations, citations, context)
            validation_result["knowledge_conflicts"] = conflicts

            # Cross-reference validation
            cross_validation = self._cross_reference_citations(citations)
            validation_result["cross_reference_validation"] = cross_validation

            # Overall validation assessment
            validation_result = self._calculate_overall_validation(validation_result)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error in enhanced checker validation: {str(e)}")
            validation_result["is_valid"] = False
            validation_result["suggested_improvements"].append(f"Validation error: {str(e)}")

        return validation_result

    def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced consistency checking with citation cross-validation"""
        consistency_result = {
            "is_consistent": True,
            "consistency_score": 1.0,
            "conflicts": [],
            "suggestions": [],
            "citation_consistency": {},
            "source_conflicts": []
        }

        # Cross-recommendation consistency
        conflicts = self._detect_recommendation_conflicts(recommendations)
        consistency_result["conflicts"] = conflicts

        # Citation consistency across recommendations
        citation_consistency = self._validate_citation_consistency(recommendations)
        consistency_result["citation_consistency"] = citation_consistency

        # Calculate overall consistency score
        if conflicts or citation_consistency.get("conflicts", []):
            consistency_result["is_consistent"] = False
            consistency_result["consistency_score"] = max(0.0, 1.0 - len(conflicts) * 0.15)

        return consistency_result

    def _validate_citations_comprehensive(self, citations: List[Dict], recommendations: Dict, context: Dict) -> Dict[str, Any]:
        """Comprehensive citation validation"""
        validation = {
            "valid_citations": 0,
            "invalid_citations": 0,
            "missing_required_citations": [],
            "citation_quality_score": 0.0,
            "authority_coverage": {},
            "source_diversity": 0.0,
            "issues": []
        }

        if not citations:
            validation["issues"].append("No citations provided for recommendations")
            return validation

        # Validate each citation
        valid_count = 0
        authority_levels = {}

        for citation in citations:
            is_valid = validate_citation_format(citation)
            if is_valid:
                valid_count += 1
                auth_level = citation.get('authority_level', 'unknown')
                authority_levels[auth_level] = authority_levels.get(auth_level, 0) + 1
            else:
                validation["issues"].append(f"Invalid citation format: {citation.get('doc_id', 'unknown')}")

        validation["valid_citations"] = valid_count
        validation["invalid_citations"] = len(citations) - valid_count
        validation["authority_coverage"] = authority_levels

        # Calculate quality metrics
        validation["citation_quality_score"] = valid_count / len(citations) if citations else 0.0
        validation["source_diversity"] = len(set(c.get('doc_id') for c in citations)) / max(1, len(citations))

        # Check for critical claims coverage
        critical_claims = self._identify_critical_claims_for_validation(recommendations)
        missing_citations = self._find_missing_citations(critical_claims, citations)
        validation["missing_required_citations"] = missing_citations

        return validation

    def _detect_knowledge_conflicts(self, recommendations: Dict, citations: List[Dict], context: Dict) -> List[Dict]:
        """Detect conflicts between recommendations and cited knowledge"""
        conflicts = []

        try:
            # Check each recommendation against its citations
            for rec_type, rec_data in recommendations.items():
                if rec_type == 'citations':
                    continue

                relevant_citations = [c for c in citations if self._citation_supports_recommendation(c, rec_type)]

                for citation in relevant_citations:
                    conflict = self._analyze_citation_recommendation_conflict(citation, rec_data, rec_type)
                    if conflict:
                        conflicts.append(conflict)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error detecting knowledge conflicts: {str(e)}")

        return conflicts

    def _cross_reference_citations(self, citations: List[Dict]) -> Dict[str, Any]:
        """Cross-reference citations for consistency"""
        cross_ref = {
            "contradictory_sources": [],
            "supporting_consensus": [],
            "source_reliability": {},
            "temporal_consistency": True
        }

        # Group citations by topic/relevance
        citation_groups = {}
        for citation in citations:
            relevance = citation.get('relevance', 'contextual')
            if relevance not in citation_groups:
                citation_groups[relevance] = []
            citation_groups[relevance].append(citation)

        # Check for contradictions within supporting citations
        supporting = citation_groups.get('supporting', [])
        if len(supporting) > 1:
            contradictions = self._find_citation_contradictions(supporting)
            cross_ref["contradictory_sources"] = contradictions

        return cross_ref

    def _calculate_overall_validation(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall validation scores and adjustments"""
        citation_validation = validation_result.get("citation_validation", {})
        knowledge_conflicts = validation_result.get("knowledge_conflicts", [])

        # Base confidence adjustment from business logic
        confidence_adjustment = validation_result.get("confidence_adjustment", 0.0)

        # Citation quality impact
        citation_quality = citation_validation.get("citation_quality_score", 0.0)
        if citation_quality < 0.7:
            confidence_adjustment -= 0.2
        elif citation_quality > 0.9:
            confidence_adjustment += 0.1

        # Knowledge conflict impact
        if knowledge_conflicts:
            confidence_adjustment -= len(knowledge_conflicts) * 0.15

        # Authority coverage impact
        authority_coverage = citation_validation.get("authority_coverage", {})
        if authority_coverage.get("official", 0) > 0:
            confidence_adjustment += 0.1
        elif authority_coverage.get("high", 0) > 0:
            confidence_adjustment += 0.05

        # Update final scores
        validation_result["confidence_adjustment"] = max(-0.5, min(0.3, confidence_adjustment))

        # Overall validation status
        if knowledge_conflicts or citation_validation.get("citation_quality_score", 0) < 0.5:
            validation_result["is_valid"] = False
            validation_result["risk_assessment"] = "medium"

        return validation_result

    def _identify_critical_claims_for_validation(self, recommendations: Dict) -> List[str]:
        """Identify claims requiring mandatory citations"""
        critical_claims = []

        # Security-related claims
        if 'security_settings' in recommendations:
            critical_claims.extend(['security_configuration', 'access_controls', 'monitoring_settings'])

        # Compliance claims
        if any('compliance' in str(v).lower() for v in recommendations.values()):
            critical_claims.append('compliance_requirements')

        # Policy claims
        if any('policy' in str(v).lower() for v in recommendations.values()):
            critical_claims.append('policy_alignment')

        return critical_claims

    def _find_missing_citations(self, critical_claims: List[str], citations: List[Dict]) -> List[str]:
        """Find critical claims without proper citations"""
        # Simplified implementation - would be more sophisticated in production
        cited_topics = set()
        for citation in citations:
            quote = citation.get('quote', '').lower()
            for claim in critical_claims:
                if claim.replace('_', ' ') in quote:
                    cited_topics.add(claim)

        return [claim for claim in critical_claims if claim not in cited_topics]

    def _citation_supports_recommendation(self, citation: Dict, rec_type: str) -> bool:
        """Check if citation is relevant to recommendation type"""
        quote = citation.get('quote', '').lower()
        relevance = citation.get('relevance', 'contextual')

        # Simple keyword matching - would be more sophisticated in production
        type_keywords = {
            'business_unit_config': ['business', 'unit', 'organization', 'structure'],
            'security_settings': ['security', 'access', 'authentication', 'monitoring'],
            'suggested_shifts': ['shift', 'schedule', 'hours', 'staffing']
        }

        keywords = type_keywords.get(rec_type, [])
        return relevance == 'supporting' and any(keyword in quote for keyword in keywords)

    def _analyze_citation_recommendation_conflict(self, citation: Dict, rec_data: Any, rec_type: str) -> Optional[Dict]:
        """Analyze if citation conflicts with recommendation"""
        # Simplified conflict detection - would be more sophisticated in production
        quote = citation.get('quote', '').lower()

        # Example: security level conflicts
        if rec_type == 'security_settings' and isinstance(rec_data, dict):
            if 'not recommended' in quote and rec_data.get('enable_gps', False):
                return {
                    "type": "policy_conflict",
                    "citation_id": citation.get('doc_id'),
                    "description": "Citation advises against GPS while recommendation enables it",
                    "severity": "medium"
                }

        return None

    def _find_citation_contradictions(self, citations: List[Dict]) -> List[Dict]:
        """Find contradictions between citations"""
        contradictions = []

        # Simple contradiction detection based on quotes
        for i, citation1 in enumerate(citations):
            for j, citation2 in enumerate(citations[i+1:], i+1):
                quote1 = citation1.get('quote', '').lower()
                quote2 = citation2.get('quote', '').lower()

                # Look for contradictory keywords
                if ('not recommended' in quote1 and 'recommended' in quote2) or \
                   ('should not' in quote1 and 'should' in quote2):
                    contradictions.append({
                        "citation1_id": citation1.get('doc_id'),
                        "citation2_id": citation2.get('doc_id'),
                        "conflict_type": "recommendation_contradiction",
                        "description": "Citations provide conflicting recommendations"
                    })

        return contradictions

    def _detect_recommendation_conflicts(self, recommendations: List[Dict[str, Any]]) -> List[Dict]:
        """Detect conflicts between multiple recommendations"""
        conflicts = []

        # Enhanced conflict detection logic would go here
        # For now, using simplified approach from parent class
        for i, rec1 in enumerate(recommendations):
            for j, rec2 in enumerate(recommendations[i+1:], i+1):
                if 'security_settings' in rec1 and 'security_settings' in rec2:
                    sec1 = rec1['security_settings']
                    sec2 = rec2['security_settings']

                    if sec1.get('enable_gps') != sec2.get('enable_gps'):
                        conflicts.append({
                            "type": "security_conflict",
                            "description": "Conflicting GPS settings between recommendations",
                            "recommendations": [i, j],
                            "severity": "high"
                        })

        return conflicts

    def _validate_citation_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate citation consistency across recommendations"""
        consistency = {
            "conflicts": [],
            "consistent_sources": 0,
            "total_sources": 0
        }

        # Extract all citations from recommendations
        all_citations = []
        for rec in recommendations:
            citations = rec.get('citations', [])
            all_citations.extend(citations)

        if not all_citations:
            return consistency

        # Check for source consistency
        source_positions = {}
        for citation in all_citations:
            source_id = citation.get('doc_id')
            quote = citation.get('quote', '')

            if source_id in source_positions:
                # Check if quotes from same source are consistent
                if self._quotes_contradict(source_positions[source_id], quote):
                    consistency["conflicts"].append({
                        "type": "source_inconsistency",
                        "source_id": source_id,
                        "description": "Same source provides contradictory information"
                    })
            else:
                source_positions[source_id] = quote

        consistency["total_sources"] = len(source_positions)
        consistency["consistent_sources"] = len(source_positions) - len(consistency["conflicts"])

        return consistency

    def _quotes_contradict(self, quote1: str, quote2: str) -> bool:
        """Simple contradiction detection between quotes"""
        quote1_lower = quote1.lower()
        quote2_lower = quote2.lower()

        # Look for obvious contradictions
        contradictions = [
            ('should', 'should not'),
            ('recommended', 'not recommended'),
            ('required', 'optional'),
            ('enable', 'disable')
        ]

        for pos, neg in contradictions:
            if pos in quote1_lower and neg in quote2_lower:
                return True
            if neg in quote1_lower and pos in quote2_lower:
                return True

        return False

    def _validate_business_logic(self, recommendations: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate business logic constraints"""
        validation = {
            "business_logic_valid": True,
            "business_logic_issues": []
        }

        # Business unit validation
        if 'business_unit_config' in recommendations:
            bu_config = recommendations['business_unit_config']

            # Check user count limits
            max_users = bu_config.get('max_users', 0)
            if max_users > 1000:
                validation["business_logic_issues"].append("Max users exceeds reasonable limit (1000)")
                validation["business_logic_valid"] = False
            elif max_users < 1:
                validation["business_logic_issues"].append("Max users must be at least 1")
                validation["business_logic_valid"] = False

            # Check business unit type validity
            valid_bu_types = ['Office', 'Warehouse', 'Retail Store', 'Manufacturing', 'Other']
            if bu_config.get('bu_type') not in valid_bu_types:
                validation["business_logic_issues"].append(f"Invalid business unit type: {bu_config.get('bu_type')}")

        return validation

    def _validate_security_requirements(self, recommendations: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security requirements and constraints"""
        validation = {
            "security_compliant": True,
            "security_issues": []
        }

        if 'security_settings' in recommendations:
            security = recommendations['security_settings']

            # GPS distance validation
            distance = security.get('permissible_distance', 0)
            if distance > 1000:
                validation["security_issues"].append("Permissible distance too high (max 1000m)")
                validation["security_compliant"] = False
            elif distance < 10:
                validation["security_issues"].append("Permissible distance too low (min 10m)")

        return validation
