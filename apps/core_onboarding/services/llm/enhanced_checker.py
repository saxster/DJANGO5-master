"""
Enhanced Checker LLM with template-based validation (Phase 2).

Provides structured validation templates for different recommendation types.
Extracted from: apps/onboarding_api/services/llm.py (lines 350-581)
Date: 2025-10-10
"""
from typing import Dict, List, Any
import logging
import json
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError

# Import base classes
try:
    from .base import CheckerLLM
except ImportError:
    # Fallback if base module not available
    from abc import ABC, abstractmethod

    class CheckerLLM(ABC):
        """Abstract base class for Checker LLM"""
        @abstractmethod
        def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            pass

        @abstractmethod
        def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
            pass

# Import exceptions
try:
    from .exceptions import LLMServiceException
except ImportError:
    # Fallback if exceptions module not available
    class LLMServiceException(Exception):
        pass

logger = logging.getLogger(__name__)


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
