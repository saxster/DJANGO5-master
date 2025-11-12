"""
Consensus Engine for combining maker/checker outputs with knowledge sources (Phase 2).

Multi-source decision-making engine that combines:
- Maker LLM recommendations
- Checker LLM validation
- Knowledge base grounding
- Policy alignment scoring

Extracted from: apps/onboarding_api/services/llm.py (lines 1399-1682)
Date: 2025-10-10
"""
from typing import Dict, List, Any
import logging
import json
from datetime import datetime
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from .exceptions import LLMServiceException, LLMConsensusError
from .citation_schema import AUTHORITY_WEIGHTS

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """
    Phase 2 Consensus Engine for combining maker/checker outputs with knowledge
    """

    def __init__(self, knowledge_service=None):
        # Lazy import to prevent circular dependency
        from apps.core_onboarding.services.knowledge import get_knowledge_service
        self.knowledge_service = knowledge_service or get_knowledge_service()

        # Configurable thresholds
        self.consensus_thresholds = {
            'approve_threshold': getattr(settings, 'ONBOARDING_APPROVE_THRESHOLD', 0.7),
            'escalate_threshold': getattr(settings, 'ONBOARDING_ESCALATE_THRESHOLD', 0.4),
            'source_coverage_weight': 0.3,
            'agreement_weight': 0.4,
            'freshness_weight': 0.1,
            'policy_weight': 0.2
        }

    def create_consensus(
        self,
        maker_output: Dict[str, Any],
        checker_output: Dict[str, Any],
        knowledge_hits: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create consensus from maker, checker, and knowledge sources"""

        consensus = {
            "final_recommendation": {},
            "consensus_confidence": 0.0,
            "decision": "needs_review",  # approve, modify, escalate, needs_review
            "reasoning": [],
            "modifications": {},
            "risk_level": "medium",
            "source_coverage": 0.0,
            "agreement_score": 0.0,
            "freshness_score": 0.0,
            "policy_alignment": 0.0,
            "knowledge_grounding": [],
            "trace_metadata": {
                "maker_confidence": maker_output.get("confidence_score", 0.0),
                "checker_confidence": checker_output.get("confidence_adjustment", 0.0) if checker_output else 0.0,
                "knowledge_sources": len(knowledge_hits)
            }
        }

        try:
            # Score different aspects
            consensus["source_coverage"] = self._calculate_source_coverage(knowledge_hits)
            consensus["agreement_score"] = self._calculate_agreement(maker_output, checker_output)
            consensus["freshness_score"] = self._calculate_freshness(knowledge_hits)
            consensus["policy_alignment"] = self._calculate_policy_alignment(maker_output, checker_output, knowledge_hits)

            # Calculate overall consensus confidence
            consensus["consensus_confidence"] = self._calculate_consensus_confidence(
                consensus["source_coverage"],
                consensus["agreement_score"],
                consensus["freshness_score"],
                consensus["policy_alignment"],
                maker_output.get("confidence_score", 0.0)
            )

            # Determine decision based on confidence and validation
            consensus["decision"] = self._determine_decision(consensus, checker_output)

            # Create final recommendation (merge maker/checker with modifications)
            consensus["final_recommendation"] = self._merge_recommendations(
                maker_output, checker_output, consensus["modifications"]
            )

            # Add reasoning
            consensus["reasoning"] = self._generate_reasoning(consensus, maker_output, checker_output, knowledge_hits)

            # Ground with knowledge sources
            consensus["knowledge_grounding"] = self._create_knowledge_grounding(knowledge_hits)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error creating consensus: {str(e)}")
            consensus["decision"] = "escalate"
            consensus["reasoning"].append(f"Consensus error: {str(e)}")

        return consensus

    def _calculate_source_coverage(self, knowledge_hits: List[Dict[str, Any]]) -> float:
        """Calculate how well knowledge sources cover the topic"""
        if not knowledge_hits:
            return 0.0

        # Weight by authority level and relevance
        total_score = 0.0

        for hit in knowledge_hits:
            authority = hit.get('metadata', {}).get('authority_level', 'medium')
            relevance = hit.get('similarity', 0.0)
            weight = AUTHORITY_WEIGHTS.get(authority, 0.5)
            total_score += weight * relevance

        # Normalize by number of sources (diminishing returns)
        return min(1.0, total_score / max(1, len(knowledge_hits) * 0.8))

    def _calculate_agreement(self, maker_output: Dict[str, Any], checker_output: Dict[str, Any]) -> float:
        """Calculate agreement between maker and checker"""
        if not checker_output:
            return 0.5  # No checker means neutral agreement

        # Check validation results
        is_valid = checker_output.get("is_valid", True)
        confidence_adj = checker_output.get("confidence_adjustment", 0.0)

        if not is_valid:
            return 0.2  # Low agreement if checker says invalid

        # Agreement based on confidence adjustment
        if confidence_adj > 0:
            return 0.9  # High agreement if checker improves confidence
        elif confidence_adj > -0.1:
            return 0.7  # Good agreement if small negative adjustment
        elif confidence_adj > -0.3:
            return 0.4  # Low agreement if significant negative adjustment
        else:
            return 0.1  # Very low agreement if large negative adjustment

    def _calculate_freshness(self, knowledge_hits: List[Dict[str, Any]]) -> float:
        """Calculate freshness of knowledge sources"""
        if not knowledge_hits:
            return 0.0

        now = datetime.now()
        total_freshness = 0.0

        for hit in knowledge_hits:
            pub_date_str = hit.get('metadata', {}).get('publication_date')
            if pub_date_str:
                try:
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    age_days = (now - pub_date.replace(tzinfo=None)).days

                    # Freshness score based on age (newer is better)
                    if age_days < 30:
                        freshness = 1.0
                    elif age_days < 180:
                        freshness = 0.8
                    elif age_days < 365:
                        freshness = 0.6
                    elif age_days < 1095:  # 3 years
                        freshness = 0.4
                    else:
                        freshness = 0.2

                    total_freshness += freshness
                except (ValueError, TypeError, AttributeError) as e:
                    total_freshness += 0.5  # Default for unparseable dates

        return total_freshness / max(1, len(knowledge_hits))

    def _calculate_policy_alignment(self, maker_output: Dict[str, Any], checker_output: Dict[str, Any], knowledge_hits: List[Dict[str, Any]]) -> float:
        """Calculate policy alignment score"""
        alignment_score = 0.7  # Default neutral alignment

        if checker_output:
            # Policy compliance from checker
            if checker_output.get("compliance_check") == "passed":
                alignment_score += 0.2
            elif checker_output.get("compliance_check") == "failed":
                alignment_score -= 0.3

            if checker_output.get("policy_alignment") == "compliant":
                alignment_score += 0.1
            elif checker_output.get("policy_alignment") == "violation":
                alignment_score -= 0.4

        # Knowledge source authority indicates policy alignment
        if knowledge_hits:
            official_sources = [h for h in knowledge_hits if h.get('metadata', {}).get('authority_level') == 'official']
            if official_sources:
                alignment_score += 0.2

        return max(0.0, min(1.0, alignment_score))

    def _calculate_consensus_confidence(self, source_coverage: float, agreement: float, freshness: float, policy: float, maker_confidence: float) -> float:
        """Calculate overall consensus confidence score"""
        weights = self.consensus_thresholds

        weighted_score = (
            source_coverage * weights['source_coverage_weight'] +
            agreement * weights['agreement_weight'] +
            freshness * weights['freshness_weight'] +
            policy * weights['policy_weight']
        )

        # Blend with maker confidence
        blended_confidence = (weighted_score + maker_confidence) / 2.0

        return max(0.0, min(1.0, blended_confidence))

    def _determine_decision(self, consensus: Dict[str, Any], checker_output: Dict[str, Any]) -> str:
        """Determine final decision based on consensus scores"""
        confidence = consensus["consensus_confidence"]
        agreement = consensus["agreement_score"]

        # Check for explicit validation failures
        if checker_output and not checker_output.get("is_valid", True):
            if checker_output.get("risk_assessment") == "high":
                return "escalate"
            else:
                return "modify"

        # Decision based on confidence thresholds
        if confidence >= self.consensus_thresholds['approve_threshold'] and agreement >= 0.6:
            return "approve"
        elif confidence >= self.consensus_thresholds['escalate_threshold']:
            return "modify"
        else:
            return "escalate"

    def _merge_recommendations(self, maker_output: Dict[str, Any], checker_output: Dict[str, Any], modifications: Dict[str, Any]) -> Dict[str, Any]:
        """Merge maker and checker recommendations with modifications"""
        final_rec = maker_output.get("recommendations", {}).copy()

        # Apply checker suggestions
        if checker_output and checker_output.get("suggested_improvements"):
            modifications["checker_improvements"] = checker_output["suggested_improvements"]

        # Apply any consensus modifications
        for key, value in modifications.items():
            if key in final_rec:
                if isinstance(final_rec[key], dict) and isinstance(value, dict):
                    final_rec[key].update(value)
                else:
                    final_rec[key] = value

        return final_rec

    def _generate_reasoning(self, consensus: Dict[str, Any], maker_output: Dict[str, Any], checker_output: Dict[str, Any], knowledge_hits: List[Dict[str, Any]]) -> List[str]:
        """Generate human-readable reasoning for the consensus decision"""
        reasoning = []

        # Decision reasoning
        decision = consensus["decision"]
        confidence = consensus["consensus_confidence"]

        if decision == "approve":
            reasoning.append(f"Approved with high confidence ({confidence:.2f})")
        elif decision == "modify":
            reasoning.append(f"Modifications needed (confidence: {confidence:.2f})")
        elif decision == "escalate":
            reasoning.append(f"Human review required (confidence: {confidence:.2f})")

        # Agreement reasoning
        if consensus["agreement_score"] > 0.8:
            reasoning.append("Strong agreement between maker and checker")
        elif consensus["agreement_score"] < 0.3:
            reasoning.append("Low agreement between maker and checker")

        # Knowledge grounding
        if consensus["source_coverage"] > 0.7:
            reasoning.append(f"Well-supported by {len(knowledge_hits)} authoritative sources")
        elif consensus["source_coverage"] < 0.3:
            reasoning.append("Limited authoritative source coverage")

        # Policy alignment
        if consensus["policy_alignment"] > 0.8:
            reasoning.append("Fully aligned with organizational policies")
        elif consensus["policy_alignment"] < 0.4:
            reasoning.append("Potential policy alignment issues")

        return reasoning

    def _create_knowledge_grounding(self, knowledge_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create knowledge grounding references"""
        grounding = []

        for hit in knowledge_hits[:5]:  # Top 5 sources
            grounding.append({
                "source": hit.get('metadata', {}).get('document_title', 'Unknown'),
                "organization": hit.get('metadata', {}).get('source_organization', 'Unknown'),
                "authority_level": hit.get('metadata', {}).get('authority_level', 'unknown'),
                "similarity_score": hit.get('similarity', 0.0),
                "summary": hit.get('metadata', {}).get('content_summary', '')[:200] + '...' if hit.get('metadata', {}).get('content_summary', '') else ''
            })

        return grounding
