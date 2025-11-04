"""
Production-grade Citation-Aware Maker LLM with knowledge grounding.

Integrates with knowledge base for authoritative source grounding and citation support.
Extracted from: apps/onboarding_api/services/llm.py (lines 588-989)
Date: 2025-10-10
"""
from typing import Dict, List, Any
import logging
import json
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError

from .base import MakerLLM
from .exceptions import LLMServiceException
from .citation_schema import CITATION_SCHEMA
from .validation_helpers import extract_topics, should_ground_response

logger = logging.getLogger(__name__)


class CitationAwareMakerLLM(MakerLLM):
    """
    Production-grade Maker LLM with citation-aware grounding
    Integrates with knowledge base for authoritative source grounding
    """

    def __init__(self, knowledge_service=None):
        from apps.core_onboarding.services.knowledge import get_knowledge_service
        self.knowledge_service = knowledge_service or get_knowledge_service()

        # Citation schema template
        self.citation_schema = CITATION_SCHEMA

    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhanced context with knowledge grounding"""
        enhanced = {
            "original_context": context,
            "user_input_analysis": {
                "sentiment": "positive",
                "complexity": "medium",
                "topics": extract_topics(user_input),
                "user_experience_level": "beginner",
                "requires_grounding": should_ground_response(user_input)
            },
            "knowledge_grounding": []
        }

        # Ground with knowledge base if needed
        if enhanced["user_input_analysis"]["requires_grounding"]:
            knowledge_context = self._retrieve_knowledge_context(user_input, context)
            enhanced["knowledge_grounding"] = knowledge_context

        # Add user-specific context
        if user:
            enhanced["user_profile"] = {
                "email": user.email,
                "is_staff": user.is_staff,
                "login_id": getattr(user, 'loginid', ''),
                "has_setup_experience": False
            }

        return enhanced

    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[Dict[str, Any]]:
        """Generate questions with knowledge-based validation"""
        base_questions = [
            {
                "id": "business_unit_type",
                "question": "What type of business unit are you setting up?",
                "type": "single_choice",
                "options": ["Office", "Warehouse", "Retail Store", "Manufacturing", "Other"],
                "required": True,
                "knowledge_grounded": True,
                "citations": self._get_supporting_citations("business unit types")
            },
            {
                "id": "expected_users",
                "question": "How many users will be working at this location?",
                "type": "number",
                "min_value": 1,
                "max_value": 1000,
                "required": True,
                "knowledge_grounded": True,
                "citations": self._get_supporting_citations("user capacity limits")
            },
            {
                "id": "security_level",
                "question": "What security level do you require?",
                "type": "single_choice",
                "options": ["Basic", "Enhanced", "High Security"],
                "required": True,
                "knowledge_grounded": True,
                "citations": self._get_supporting_citations("security requirements")
            }
        ]

        return base_questions

    def process_conversation_step(self, session, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process conversation step with citation-aware grounding"""
        # Parse user input
        answers = self._parse_user_input(user_input)

        # Retrieve relevant knowledge
        knowledge_context = self._retrieve_knowledge_context(user_input, context)

        # Generate recommendations with citations
        recommendations = self._generate_grounded_recommendations(answers, session, knowledge_context)

        # Validate citations
        citation_validation = self._validate_citations(recommendations.get("citations", []))

        # Update session with knowledge grounding
        session.collected_data.update({
            "answers": answers,
            "knowledge_grounding": knowledge_context,
            "citation_validation": citation_validation,
            "processed_at": datetime.now().isoformat()
        })
        session.save()

        return {
            "recommendations": recommendations,
            "citations": recommendations.get("citations", []),
            "confidence_score": min(0.9, recommendations.get("confidence", 0.8) * citation_validation.get("coverage", 0.8)),
            "grounding_quality": citation_validation.get("quality_score", 0.5),
            "next_steps": [
                "Review the generated configuration and supporting evidence",
                "Verify citations match your requirements",
                "Approve or modify recommendations"
            ],
            "completion_percentage": 75
        }

    def generate_recommendations(self, session, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final recommendations with comprehensive citations"""
        answers = collected_data.get("answers", {})
        knowledge_grounding = collected_data.get("knowledge_grounding", [])

        # Generate recommendations
        recommendations = self._generate_final_recommendations(answers, knowledge_grounding)

        # Ensure all critical claims are cited
        citation_coverage = self._ensure_citation_coverage(recommendations)

        return {
            "recommendations": recommendations,
            "citations": recommendations.get("citations", []),
            "confidence_score": citation_coverage.get("confidence", 0.8),
            "citation_coverage": citation_coverage,
            "reasoning": "Based on authoritative sources and your requirements",
            "knowledge_sources_used": len(knowledge_grounding)
        }

    def _retrieve_knowledge_context(self, query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge context for grounding"""
        try:
            # Extract topics and search knowledge base
            topics = extract_topics(query)
            knowledge_hits = []

            for topic in topics:
                hits = self.knowledge_service.search_with_reranking(
                    query=f"{topic} {query}",
                    top_k=3,
                    authority_filter=['high', 'official']
                )
                knowledge_hits.extend(hits)

            # Deduplicate and limit results
            unique_hits = {hit['source_id']: hit for hit in knowledge_hits}.values()
            return list(unique_hits)[:5]

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to retrieve knowledge context: {str(e)}")
            return []

    def _get_supporting_citations(self, topic: str) -> List[Dict[str, Any]]:
        """Get citations for a specific topic"""
        try:
            hits = self.knowledge_service.search_with_reranking(
                query=topic,
                top_k=2,
                authority_filter=['high', 'official']
            )

            citations = []
            for hit in hits:
                citations.append({
                    "doc_id": hit['knowledge_id'],
                    "chunk_index": hit.get('chunk_position', 0),
                    "quote": hit['content'][:200] + "..." if len(hit['content']) > 200 else hit['content'],
                    "relevance": "supporting",
                    "authority_level": hit.get('authority_level', 'medium'),
                    "page_start": hit.get('metadata', {}).get('page_start'),
                    "page_end": hit.get('metadata', {}).get('page_end')
                })

            return citations

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to get supporting citations for {topic}: {str(e)}")
            return []

    def _generate_grounded_recommendations(self, answers: Dict[str, Any], session, knowledge_context: List[Dict]) -> Dict[str, Any]:
        """Generate recommendations with knowledge grounding"""
        recommendations = {
            "business_unit_config": {
                "bu_name": f"New {answers.get('business_unit_type', 'Office')}",
                "bu_type": answers.get('business_unit_type', 'Office'),
                "max_users": int(answers.get('expected_users', 10)),
                "security_level": answers.get('security_level', 'Basic')
            },
            "suggested_shifts": [{
                "shift_name": "Day Shift",
                "start_time": "09:00",
                "end_time": "17:00",
                "people_count": min(int(answers.get('expected_users', 10)), 20)
            }],
            "security_settings": {
                "enable_gps": answers.get('security_level') in ['Enhanced', 'High Security'],
                "enable_sleeping_guard": answers.get('security_level') == 'High Security',
                "permissible_distance": 100 if answers.get('security_level') == 'Basic' else 50
            }
        }

        # Add citations based on knowledge context
        citations = []
        for knowledge in knowledge_context:
            citations.append({
                "doc_id": knowledge['knowledge_id'],
                "chunk_index": knowledge.get('chunk_position', 0),
                "quote": knowledge['content'][:150] + "...",
                "relevance": "supporting",
                "authority_level": knowledge.get('authority_level', 'medium'),
                "page_start": knowledge.get('metadata', {}).get('page_start'),
                "page_end": knowledge.get('metadata', {}).get('page_end')
            })

        recommendations["citations"] = citations
        recommendations["confidence"] = 0.85 if knowledge_context else 0.65

        return recommendations

    def _generate_final_recommendations(self, answers: Dict[str, Any], knowledge_grounding: List[Dict]) -> Dict[str, Any]:
        """Generate final recommendations with comprehensive citations"""
        recommendations = self._generate_grounded_recommendations(answers, None, knowledge_grounding)

        # Enhance with additional grounding
        recommendations.update({
            "implementation_plan": {
                "phases": [
                    {
                        "phase": "Initial Setup",
                        "duration": "1-2 days",
                        "tasks": ["Create business unit", "Configure security", "Set up shifts"],
                        "citations": knowledge_grounding[:2]
                    }
                ]
            },
            "compliance_requirements": self._extract_compliance_requirements(knowledge_grounding),
            "risk_assessment": self._assess_risks(answers, knowledge_grounding)
        })

        return recommendations

    def _validate_citations(self, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate citation format and coverage"""
        validation = {
            "valid_format": True,
            "coverage": 0.0,
            "quality_score": 0.0,
            "issues": []
        }

        if not citations:
            validation["issues"].append("No citations provided")
            validation["coverage"] = 0.0
            return validation

        # Check citation format
        required_fields = ['doc_id', 'chunk_index', 'quote', 'relevance']
        valid_citations = 0

        for citation in citations:
            if all(field in citation for field in required_fields):
                valid_citations += 1
            else:
                missing = [field for field in required_fields if field not in citation]
                validation["issues"].append(f"Missing fields: {missing}")

        validation["valid_format"] = valid_citations == len(citations)
        validation["coverage"] = valid_citations / len(citations) if citations else 0.0
        validation["quality_score"] = validation["coverage"] * 0.7 + (0.3 if validation["valid_format"] else 0.0)

        return validation

    def _ensure_citation_coverage(self, recommendations: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all critical claims have citations"""
        citations = recommendations.get("citations", [])
        critical_claims = self._identify_critical_claims(recommendations)

        coverage_analysis = {
            "total_claims": len(critical_claims),
            "cited_claims": 0,
            "confidence": 0.5,
            "missing_citations": []
        }

        # Simple coverage check (would be more sophisticated in real implementation)
        if citations:
            coverage_analysis["cited_claims"] = min(len(citations), len(critical_claims))
            coverage_analysis["confidence"] = coverage_analysis["cited_claims"] / max(1, len(critical_claims))

        # Identify missing citations
        if coverage_analysis["cited_claims"] < len(critical_claims):
            uncited = critical_claims[coverage_analysis["cited_claims"]:]
            coverage_analysis["missing_citations"] = uncited

        return coverage_analysis

    def _identify_critical_claims(self, recommendations: Dict[str, Any]) -> List[str]:
        """Identify claims that require citations"""
        critical_claims = []

        # Business unit configuration claims
        if 'business_unit_config' in recommendations:
            critical_claims.append("Business unit type selection")
            critical_claims.append("User capacity limits")

        # Security claims
        if 'security_settings' in recommendations:
            critical_claims.append("Security level requirements")
            critical_claims.append("GPS monitoring settings")

        return critical_claims

    def _extract_compliance_requirements(self, knowledge_grounding: List[Dict]) -> List[Dict]:
        """Extract compliance requirements from knowledge sources"""
        requirements = []
        for knowledge in knowledge_grounding:
            if 'compliance' in knowledge.get('content', '').lower():
                requirements.append({
                    "requirement": "Data protection compliance",
                    "source": knowledge['knowledge_id'],
                    "description": knowledge['content'][:100] + "..."
                })
        return requirements

    def _assess_risks(self, answers: Dict[str, Any], knowledge_grounding: List[Dict]) -> Dict[str, Any]:
        """Assess risks based on configuration and knowledge"""
        risk_level = "low"
        risks = []

        # Check for high-risk configurations
        if answers.get('expected_users', 0) > 100:
            risk_level = "medium"
            risks.append("Large user base requires additional security measures")

        if answers.get('security_level') == 'Basic' and answers.get('expected_users', 0) > 50:
            risk_level = "high"
            risks.append("Basic security insufficient for large deployments")

        return {
            "level": risk_level,
            "identified_risks": risks,
            "mitigation_suggestions": ["Implement regular security audits", "Monitor user access patterns"]
        }

    def _parse_user_input(self, user_input: str) -> Dict[str, Any]:
        """Enhanced parsing with context awareness"""
        try:
            return json.loads(user_input)
        except json.JSONDecodeError:
            return {
                "raw_input": user_input,
                "parsed_at": datetime.now().isoformat(),
                "business_unit_type": "Office",
                "expected_users": 10,
                "security_level": "Basic"
            }
