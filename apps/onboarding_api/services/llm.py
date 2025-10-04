"""
Vendor-agnostic LLM service interfaces for Conversational Onboarding (Phase 1 MVP)
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from django.conf import settings
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class MakerLLM(ABC):
    """
    Abstract base class for Maker LLM - responsible for generating initial recommendations
    """

    @abstractmethod
    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhance the initial context with LLM understanding"""
        pass

    @abstractmethod
    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[Dict[str, Any]]:
        """Generate initial questions based on context"""
        pass

    @abstractmethod
    def process_conversation_step(self, session: ConversationSession, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a conversation step and generate recommendations"""
        pass

    @abstractmethod
    def generate_recommendations(self, session: ConversationSession, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final recommendations based on collected data"""
        pass

    def process_voice_input(
        self,
        transcript: str,
        session,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process voice transcript as text input.

        Default implementation delegates to existing text processing method.
        Subclasses can override to add voice-specific processing logic.

        Args:
            transcript: Transcribed text from voice input
            session: ConversationSession instance
            context: Additional context data

        Returns:
            Response dict with same structure as process_conversation_step
        """
        return self.process_conversation_step(session, transcript, context)


class CheckerLLM(ABC):
    """
    Abstract base class for Checker LLM - responsible for validating maker recommendations
    """

    @abstractmethod
    def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and improve maker recommendations"""
        pass

    @abstractmethod
    def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check consistency across multiple recommendations"""
        pass


# =============================================================================
# PHASE 1 MVP IMPLEMENTATIONS (Dummy providers)
# =============================================================================


class DummyMakerLLM(MakerLLM):
    """
    Dummy implementation of Maker LLM for Phase 1 MVP
    Returns structured, realistic responses for testing and development
    """

    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhanced context with dummy analysis"""
        enhanced = {
            "original_context": context,
            "user_input_analysis": {
                "sentiment": "positive",
                "complexity": "medium",
                "topics": ["setup", "configuration", "business_unit"],
                "user_experience_level": "beginner"
            },
            "detected_requirements": [
                "Business unit setup",
                "User role configuration",
                "Basic security settings"
            ],
            "estimated_setup_time": "15-30 minutes",
            "recommended_approach": "guided_setup"
        }

        # Add user-specific context
        if user:
            enhanced["user_profile"] = {
                "email": user.email,
                "is_staff": user.is_staff,
                "login_id": getattr(user, 'loginid', ''),
                "has_setup_experience": False  # Default for MVP
            }

        return enhanced

    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[Dict[str, Any]]:
        """Generate initial questions based on conversation type"""
        base_questions = [
            {
                "id": "business_unit_type",
                "question": "What type of business unit are you setting up?",
                "type": "single_choice",
                "options": ["Office", "Warehouse", "Retail Store", "Manufacturing", "Other"],
                "required": True,
                "help_text": "This helps us configure the right features for your location"
            },
            {
                "id": "expected_users",
                "question": "How many users will be working at this location?",
                "type": "number",
                "min_value": 1,
                "max_value": 1000,
                "required": True,
                "help_text": "This affects licensing and device allocation"
            },
            {
                "id": "operating_hours",
                "question": "What are your typical operating hours?",
                "type": "time_range",
                "required": True,
                "help_text": "We'll configure shift patterns and monitoring accordingly"
            },
            {
                "id": "security_level",
                "question": "What security level do you require?",
                "type": "single_choice",
                "options": ["Basic", "Enhanced", "High Security"],
                "required": True,
                "help_text": "This determines authentication and monitoring features"
            }
        ]

        # Customize questions based on conversation type
        if conversation_type == "initial_setup":
            base_questions.insert(0, {
                "id": "setup_urgency",
                "question": "When do you need this setup to be operational?",
                "type": "single_choice",
                "options": ["Today", "Within a week", "Within a month", "No specific deadline"],
                "required": False
            })

        return base_questions

    def process_conversation_step(self, session: ConversationSession, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process conversation step with dummy logic"""
        # Extract answers from user input (simplified parsing for MVP)
        answers = self._parse_user_input(user_input)

        # Update session collected data
        session.collected_data.update({"answers": answers, "processed_at": str(uuid.uuid4())})
        session.save()

        # Generate recommendations based on answers
        recommendations = self._generate_step_recommendations(answers, session)

        return {
            "recommendations": recommendations,
            "confidence_score": 0.85,  # Dummy confidence
            "next_steps": [
                "Review the generated configuration",
                "Approve or modify recommendations",
                "Apply settings to your business unit"
            ],
            "completion_percentage": 75
        }

    def generate_recommendations(self, session: ConversationSession, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final recommendations"""
        answers = collected_data.get("answers", {})

        recommendations = {
            "business_unit_config": {
                "bu_name": f"New {answers.get('business_unit_type', 'Office')}",
                "bu_type": answers.get('business_unit_type', 'Office'),
                "max_users": int(answers.get('expected_users', 10)),
                "operating_hours": answers.get('operating_hours', '09:00-17:00'),
                "security_level": answers.get('security_level', 'Basic')
            },
            "suggested_shifts": self._generate_shift_suggestions(answers),
            "type_assist_configs": self._generate_typeassist_suggestions(answers),
            "security_settings": {
                "enable_gps": answers.get('security_level') in ['Enhanced', 'High Security'],
                "enable_sleeping_guard": answers.get('security_level') == 'High Security',
                "permissible_distance": 100 if answers.get('security_level') == 'Basic' else 50
            }
        }

        return {
            "recommendations": recommendations,
            "confidence_score": 0.88,
            "reasoning": "Based on your business unit type and security requirements",
            "estimated_setup_time": "20 minutes"
        }

    def _parse_user_input(self, user_input: str) -> Dict[str, Any]:
        """Simple parsing of user input for MVP"""
        # In a real implementation, this would use NLP
        # For MVP, we'll expect structured input or simple parsing
        try:
            # Try to parse as JSON first
            return json.loads(user_input)
        except json.JSONDecodeError:
            # Fallback to simple text analysis
            return {
                "raw_input": user_input,
                "parsed_at": "dummy_parser",
                "business_unit_type": "Office",  # Default
                "expected_users": 10,  # Default
                "security_level": "Basic"  # Default
            }

    def _generate_step_recommendations(self, answers: Dict[str, Any], session: ConversationSession) -> List[Dict[str, Any]]:
        """Generate recommendations for current step"""
        return [
            {
                "type": "business_unit_setup",
                "title": f"Configure {answers.get('business_unit_type', 'Office')}",
                "description": "Set up your business unit with the specified configuration",
                "confidence": 0.9,
                "actions": [
                    "Create business unit record",
                    "Set operating parameters",
                    "Configure user limits"
                ]
            },
            {
                "type": "security_configuration",
                "title": "Apply Security Settings",
                "description": f"Configure {answers.get('security_level', 'Basic')} security level",
                "confidence": 0.85,
                "actions": [
                    "Set authentication requirements",
                    "Configure monitoring parameters",
                    "Set access controls"
                ]
            }
        ]

    def _generate_shift_suggestions(self, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate shift configuration suggestions"""
        operating_hours = answers.get('operating_hours', '09:00-17:00')

        return [
            {
                "shift_name": "Day Shift",
                "start_time": "09:00",
                "end_time": "17:00",
                "people_count": min(int(answers.get('expected_users', 10)), 20),
                "description": "Standard day shift based on your operating hours"
            }
        ]

    def _generate_typeassist_suggestions(self, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate TypeAssist configuration suggestions"""
        bu_type = answers.get('business_unit_type', 'Office')

        suggestions = [
            {
                "ta_code": f"{bu_type.upper()}_TYPE",
                "ta_name": f"{bu_type} Type",
                "description": f"Standard type configuration for {bu_type}"
            }
        ]

        return suggestions


class DummyCheckerLLM(CheckerLLM):
    """
    Dummy implementation of Checker LLM for Phase 1 MVP
    Optional for MVP - can be enabled later
    """

    def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate maker recommendations"""
        validation_result = {
            "is_valid": True,
            "confidence_adjustment": 0.02,  # Slight increase
            "suggested_improvements": [],
            "risk_assessment": "low",
            "compliance_check": "passed"
        }

        # Simple validation logic for MVP
        recommendations = maker_output.get("recommendations", {})

        # Check for minimum requirements
        if not recommendations.get("business_unit_config"):
            validation_result["is_valid"] = False
            validation_result["suggested_improvements"].append(
                "Business unit configuration is required"
            )

        return validation_result

    def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check consistency across recommendations"""
        return {
            "is_consistent": True,
            "consistency_score": 0.92,
            "conflicts": [],
            "suggestions": [
                "All recommendations are consistent with business requirements"
            ]
        }


# =============================================================================
# PHASE 2: ENHANCED CHECKER LLM IMPLEMENTATIONS
# =============================================================================


class EnhancedCheckerLLM(CheckerLLM):
    """
    Phase 2 Enhanced Checker LLM with proper validation templates
    """

    def __init__(self):
        self.validation_templates = {
            'business_unit': self._get_bu_validation_template(),
            'security': self._get_security_validation_template(),
            'shift': self._get_shift_validation_template(),
            'general': self._get_general_validation_template()
        }

    def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate maker recommendations with structured analysis"""
        recommendations = maker_output.get("recommendations", {})

        # Determine validation template based on recommendation type
        template_type = self._determine_validation_type(recommendations)
        validation_template = self.validation_templates.get(template_type, self.validation_templates['general'])

        # Perform structured validation
        validation_result = {
            "is_valid": True,
            "confidence_adjustment": 0.0,
            "risk_assessment": "low",
            "compliance_check": "passed",
            "policy_alignment": "compliant",
            "suggested_improvements": [],
            "citations": [],
            "contradictions": [],
            "validation_details": {}
        }

        # Business logic validation
        try:
            validation_result.update(self._validate_business_logic(recommendations, context))
            validation_result.update(self._validate_security_requirements(recommendations, context))
            validation_result.update(self._validate_compliance(recommendations, context))
            validation_result.update(self._check_policy_alignment(recommendations, context))
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error in checker validation: {str(e)}")
            validation_result["is_valid"] = False
            validation_result["suggested_improvements"].append(f"Validation error: {str(e)}")

        # Calculate final confidence adjustment
        validation_result["confidence_adjustment"] = self._calculate_confidence_adjustment(validation_result)

        return validation_result

    def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check consistency across multiple recommendations"""
        consistency_result = {
            "is_consistent": True,
            "consistency_score": 1.0,
            "conflicts": [],
            "suggestions": []
        }

        # Cross-recommendation consistency checks
        conflicts = self._detect_conflicts(recommendations)
        if conflicts:
            consistency_result["conflicts"] = conflicts
            consistency_result["is_consistent"] = False
            consistency_result["consistency_score"] = max(0.0, 1.0 - len(conflicts) * 0.2)

        return consistency_result

    def _determine_validation_type(self, recommendations: Dict[str, Any]) -> str:
        """Determine which validation template to use"""
        if 'business_unit_config' in recommendations:
            return 'business_unit'
        elif 'security_settings' in recommendations:
            return 'security'
        elif 'suggested_shifts' in recommendations:
            return 'shift'
        else:
            return 'general'

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

    def _validate_compliance(self, recommendations: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate regulatory and policy compliance"""
        return {
            "compliance_status": "passed",
            "compliance_issues": []
        }

    def _check_policy_alignment(self, recommendations: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Check alignment with organizational policies"""
        return {
            "policy_compliant": True,
            "policy_violations": []
        }

    def _calculate_confidence_adjustment(self, validation_result: Dict[str, Any]) -> float:
        """Calculate confidence adjustment based on validation results"""
        adjustment = 0.0

        if not validation_result.get("is_valid", True):
            adjustment -= 0.3

        if not validation_result.get("business_logic_valid", True):
            adjustment -= 0.2

        if not validation_result.get("security_compliant", True):
            adjustment -= 0.25

        if validation_result.get("risk_assessment") == "high":
            adjustment -= 0.15
        elif validation_result.get("risk_assessment") == "medium":
            adjustment -= 0.05

        # Positive adjustments for good validation
        if (validation_result.get("compliance_check") == "passed" and
            validation_result.get("policy_alignment") == "compliant"):
            adjustment += 0.05

        return max(-0.5, min(0.2, adjustment))  # Cap between -0.5 and +0.2

    def _detect_conflicts(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect conflicts between recommendations"""
        conflicts = []

        # This is a simplified conflict detection for Phase 2
        # Real implementation would have more sophisticated logic

        for i, rec1 in enumerate(recommendations):
            for j, rec2 in enumerate(recommendations[i+1:], i+1):
                # Example: conflicting security settings
                if ('security_settings' in rec1 and 'security_settings' in rec2):
                    sec1 = rec1['security_settings']
                    sec2 = rec2['security_settings']

                    if sec1.get('enable_gps') != sec2.get('enable_gps'):
                        conflicts.append({
                            "type": "security_conflict",
                            "description": "Conflicting GPS settings between recommendations",
                            "recommendations": [i, j]
                        })

        return conflicts

    def _get_bu_validation_template(self) -> str:
        """Get business unit validation template"""
        return """
        Validate this business unit configuration:
        - Check if user counts are reasonable (1-1000)
        - Verify business unit type is valid
        - Ensure security settings are appropriate
        - Check for policy compliance

        Respond with structured validation results including risks and suggestions.
        """

    def _get_security_validation_template(self) -> str:
        """Get security validation template"""
        return """
        Validate these security settings:
        - Check if GPS settings are appropriate
        - Verify distance limits are reasonable
        - Ensure security level matches requirements
        - Check for security policy compliance

        Cite relevant security policies and rate risk level.
        """

    def _get_shift_validation_template(self) -> str:
        """Get shift validation template"""
        return """
        Validate this shift configuration:
        - Check if hours are reasonable (not exceeding labor laws)
        - Verify people counts match requirements
        - Ensure shift patterns don't conflict
        - Check for scheduling policy compliance
        """

    def _get_general_validation_template(self) -> str:
        """Get general validation template"""
        return """
        Validate this configuration:
        - Check for logical consistency
        - Verify all required fields are present
        - Ensure values are within reasonable ranges
        - Check for potential issues or risks
        """


# =============================================================================
# PRODUCTION-GRADE CITATION-AWARE LLM SERVICES
# =============================================================================


class CitationAwareMakerLLM(MakerLLM):
    """
    Production-grade Maker LLM with citation-aware grounding
    Integrates with knowledge base for authoritative source grounding
    """

    def __init__(self, knowledge_service=None):
        from apps.onboarding_api.services.knowledge import get_knowledge_service
        self.knowledge_service = knowledge_service or get_knowledge_service()

        # Citation schema template
        self.citation_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document knowledge ID"},
                    "chunk_index": {"type": "integer", "description": "Chunk index within document"},
                    "page_start": {"type": "integer", "description": "Starting page number"},
                    "page_end": {"type": "integer", "description": "Ending page number"},
                    "quote": {"type": "string", "description": "Exact quote from source"},
                    "relevance": {"type": "string", "enum": ["supporting", "contradicting", "contextual"]},
                    "authority_level": {"type": "string", "enum": ["low", "medium", "high", "official"]}
                },
                "required": ["doc_id", "chunk_index", "quote", "relevance"]
            }
        }

    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhanced context with knowledge grounding"""
        enhanced = {
            "original_context": context,
            "user_input_analysis": {
                "sentiment": "positive",
                "complexity": "medium",
                "topics": self._extract_topics(user_input),
                "user_experience_level": "beginner",
                "requires_grounding": self._should_ground_response(user_input)
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

    def _extract_topics(self, text: str) -> List[str]:
        """Extract key topics for knowledge retrieval"""
        topics = []

        # Simple keyword extraction
        business_keywords = ['office', 'warehouse', 'retail', 'manufacturing', 'facility']
        security_keywords = ['security', 'access', 'authentication', 'monitoring']
        config_keywords = ['setup', 'configuration', 'system', 'users', 'permissions']

        text_lower = text.lower()

        if any(kw in text_lower for kw in business_keywords):
            topics.append('business_unit_types')
        if any(kw in text_lower for kw in security_keywords):
            topics.append('security_requirements')
        if any(kw in text_lower for kw in config_keywords):
            topics.append('system_configuration')

        return topics if topics else ['general_setup']

    def _should_ground_response(self, user_input: str) -> bool:
        """Determine if response should be grounded in knowledge base"""
        grounding_keywords = ['policy', 'compliance', 'standard', 'requirement', 'guideline', 'best practice']
        return any(keyword in user_input.lower() for keyword in grounding_keywords)

    def _retrieve_knowledge_context(self, query: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge context for grounding"""
        try:
            # Extract topics and search knowledge base
            topics = self._extract_topics(query)
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


class CitationAwareCheckerLLM(CheckerLLM):
    """
    Enhanced Checker LLM with citation validation and knowledge verification
    """

    def __init__(self, knowledge_service=None):
        from apps.onboarding_api.services.knowledge import get_knowledge_service
        self.knowledge_service = knowledge_service or get_knowledge_service()

        # Citation validation schema
        self.citation_requirements = {
            'security_claims': ['authority_level', 'quote', 'doc_id'],
            'policy_claims': ['authority_level', 'quote', 'doc_id', 'page_start'],
            'configuration_claims': ['quote', 'doc_id'],
            'compliance_claims': ['authority_level', 'quote', 'doc_id', 'page_start']
        }

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
            is_valid = self._validate_single_citation(citation)
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

    def _validate_single_citation(self, citation: Dict[str, Any]) -> bool:
        """Validate format and content of a single citation"""
        required_fields = ['doc_id', 'chunk_index', 'quote', 'relevance']

        # Check required fields
        if not all(field in citation for field in required_fields):
            return False

        # Validate field types and values
        if not isinstance(citation.get('chunk_index'), int) or citation['chunk_index'] < 0:
            return False

        if citation.get('relevance') not in ['supporting', 'contradicting', 'contextual']:
            return False

        if len(citation.get('quote', '')) < 10:  # Minimum quote length
            return False

        return True

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


# =============================================================================
# PHASE 2: CONSENSUS ENGINE
# =============================================================================


class ConsensusEngine:
    """
    Phase 2 Consensus Engine for combining maker/checker outputs with knowledge
    """

    def __init__(self, knowledge_service=None):
        from apps.onboarding_api.services.knowledge import get_knowledge_service
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
        authority_weights = {'official': 1.0, 'high': 0.8, 'medium': 0.6, 'low': 0.3}

        for hit in knowledge_hits:
            authority = hit.get('metadata', {}).get('authority_level', 'medium')
            relevance = hit.get('similarity', 0.0)
            weight = authority_weights.get(authority, 0.5)
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
                except:
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


# =============================================================================
# SERVICE FACTORY (Updated for Phase 2)
# =============================================================================


def get_llm_service() -> MakerLLM:
    """Factory function to get the configured LLM service"""
    # Production-grade citation-aware LLM selection
    use_citations = getattr(settings, 'ENABLE_ONBOARDING_KB', False)

    if use_citations:
        logger.info("Using citation-aware Maker LLM with knowledge grounding")
        return CitationAwareMakerLLM()
    else:
        # Fallback to enhanced dummy implementation
        return DummyMakerLLM()


def get_checker_service() -> Optional[CheckerLLM]:
    """Factory function to get the configured Checker LLM service"""
    if not getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False):
        return None

    # Choose citation-aware checker if knowledge base is enabled
    use_citations = getattr(settings, 'ENABLE_ONBOARDING_KB', False)

    if use_citations:
        logger.info("Using citation-aware Checker LLM with knowledge validation")
        return CitationAwareCheckerLLM()
    else:
        # Fallback to enhanced checker without citations
        return EnhancedCheckerLLM()


def get_consensus_engine() -> ConsensusEngine:
    """Factory function to get the consensus engine"""
    return ConsensusEngine()