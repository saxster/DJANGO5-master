"""
Dummy LLM implementations for Phase 1 MVP.

Used for development, testing, and fallback when knowledge base is disabled.
Extracted from: apps/onboarding_api/services/llm.py (lines 96-343)
Date: 2025-10-10

These implementations provide structured, realistic responses without requiring
actual LLM API calls, making them ideal for:
- Local development without API costs
- Unit/integration testing
- Fallback when knowledge base is disabled
- MVP deployments before LLM integration
"""
from typing import Dict, List, Any
import json
import uuid

from .base import MakerLLM, CheckerLLM


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

    def process_conversation_step(self, session, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
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

    def generate_recommendations(self, session, collected_data: Dict[str, Any]) -> Dict[str, Any]:
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

    def _generate_step_recommendations(self, answers: Dict[str, Any], session) -> List[Dict[str, Any]]:
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
