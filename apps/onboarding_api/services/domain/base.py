"""
Base Domain Expertise Service - Abstract interface for domain-specific knowledge.

This module defines the abstract interface that all domain expertise services
must implement. Domain services provide industry-specific knowledge for:
- Observation enhancement (steel-manning)
- Compliance validation
- SOP generation
- Targeted audit questions

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from decimal import Decimal


class DomainExpertise(ABC):
    """
    Abstract base class for domain-specific expertise.

    Each domain (banking, retail, industrial) implements this interface
    to provide specialized knowledge and validation.
    """

    def __init__(self, site_type: str):
        """
        Initialize domain expertise.

        Args:
            site_type: Type of site (bank_branch, atm, retail_store, etc.)
        """
        self.site_type = site_type
        self.compliance_standards = self._load_compliance_standards()
        self.sop_templates = self._load_sop_templates()

    @abstractmethod
    def enhance_observation(
        self,
        observation: Dict[str, Any],
        zone_type: str
    ) -> Dict[str, Any]:
        """
        Enhance observation with domain expertise (steel-manning).

        Transforms raw observation into professional assessment with:
        - Technical terminology
        - Risk classification
        - Compliance references
        - Recommended actions

        Args:
            observation: Raw observation data
            zone_type: Type of zone (gate, vault, etc.)

        Returns:
            {
                'enhanced_text': str,
                'risk_level': str,
                'compliance_issues': List[str],
                'recommended_actions': List[str],
                'citations': List[str]
            }
        """
        pass

    @abstractmethod
    def generate_questions(
        self,
        zone_type: str,
        current_observations: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate targeted audit questions for zone.

        Returns contextual questions based on:
        - Zone type and importance
        - Compliance requirements
        - Previous observations
        - Common gaps/issues

        Args:
            zone_type: Type of zone
            current_observations: Existing observations (optional)

        Returns:
            [
                {
                    'question': str,
                    'category': str,
                    'priority': str,
                    'expected_answer_type': str,
                    'compliance_reference': str | None
                }
            ]
        """
        pass

    @abstractmethod
    def validate_configuration(
        self,
        zone_type: str,
        configuration: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate configuration against compliance standards.

        Args:
            zone_type: Type of zone
            configuration: Proposed configuration (assets, guards, etc.)

        Returns:
            {
                'is_compliant': bool,
                'violations': List[Dict],
                'recommendations': List[str],
                'risk_score': Decimal
            }
        """
        pass

    @abstractmethod
    def get_sop_template(
        self,
        zone_type: str,
        asset_type: str = None
    ) -> Dict[str, Any]:
        """
        Get SOP template for zone/asset.

        Args:
            zone_type: Type of zone
            asset_type: Type of asset (optional)

        Returns:
            {
                'title': str,
                'purpose': str,
                'steps': List[Dict],
                'frequency': str,
                'staffing': Dict,
                'compliance_references': List[str]
            }
        """
        pass

    @abstractmethod
    def assess_risk(
        self,
        zone_type: str,
        observations: List[Dict[str, Any]],
        assets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess risk level for zone.

        Args:
            zone_type: Type of zone
            observations: All observations for zone
            assets: Assets in zone

        Returns:
            {
                'overall_risk': str,
                'risk_score': Decimal,
                'risk_factors': List[str],
                'mitigation_priority': str
            }
        """
        pass

    @abstractmethod
    def _load_compliance_standards(self) -> Dict[str, Any]:
        """
        Load compliance standards for this domain.

        Returns:
            Dictionary of standards with requirements
        """
        pass

    @abstractmethod
    def _load_sop_templates(self) -> Dict[str, Any]:
        """
        Load SOP templates for this domain.

        Returns:
            Dictionary of templates by zone/asset type
        """
        pass

    # Common utility methods (implemented in base)

    def get_compliance_standards(self) -> List[str]:
        """Get list of applicable compliance standards."""
        return list(self.compliance_standards.keys())

    def get_zone_importance_level(self, zone_type: str) -> str:
        """
        Determine importance level for zone type.

        Returns:
            'critical', 'high', 'medium', or 'low'
        """
        critical_zones = ['vault', 'atm', 'cash_counter', 'control_room', 'server_room']
        high_zones = ['gate', 'entry_exit', 'perimeter']
        medium_zones = ['reception', 'parking', 'loading_dock']

        if zone_type in critical_zones:
            return 'critical'
        elif zone_type in high_zones:
            return 'high'
        elif zone_type in medium_zones:
            return 'medium'
        else:
            return 'low'

    def get_minimum_coverage_hours(self, zone_type: str) -> int:
        """
        Get minimum required coverage hours for zone.

        Returns:
            Hours of coverage required (0-24)
        """
        coverage_map = {
            'vault': 24,  # 24/7 coverage
            'atm': 24,
            'cash_counter': 12,  # Business hours + buffer
            'control_room': 24,
            'server_room': 24,
            'gate': 24,
            'entry_exit': 12,
            'perimeter': 16,  # Extended hours
            'reception': 10,
            'parking': 12,
            'loading_dock': 10,
            'emergency_exit': 0,  # Monitored, not manned
        }

        return coverage_map.get(zone_type, 8)

    def standardize_terminology(self, text: str) -> str:
        """
        Convert casual language to professional terminology.

        Args:
            text: Raw observation text

        Returns:
            Professional terminology version
        """
        # Common replacements
        replacements = {
            'broken': 'non-functional',
            'not working': 'inoperative',
            'missing': 'absent',
            'old': 'legacy equipment',
            'bad': 'substandard',
            'good': 'operational',
            'okay': 'acceptable',
            'locked': 'secured',
            'unlocked': 'unsecured',
        }

        result = text
        for casual, professional in replacements.items():
            result = result.replace(casual, professional)

        return result


class DomainExpertiseFactory:
    """
    Factory for creating domain expertise services.
    """

    _registry = {}

    @classmethod
    def register(cls, domain_name: str, expertise_class):
        """Register a domain expertise implementation."""
        cls._registry[domain_name] = expertise_class

    @classmethod
    def create(cls, site_type: str) -> DomainExpertise:
        """
        Create appropriate domain expertise for site type.

        Args:
            site_type: Type of site (bank_branch, atm, retail_store, etc.)

        Returns:
            DomainExpertise instance
        """
        # Map site types to domains
        domain_map = {
            'bank_branch': 'banking',
            'atm': 'banking',
            'retail_store': 'retail',
            'warehouse': 'industrial',
            'office': 'generic',
            'industrial': 'industrial',
        }

        domain = domain_map.get(site_type, 'generic')

        if domain in cls._registry:
            return cls._registry[domain](site_type)

        # Fallback to generic if specific domain not available
        from .security_banking import BankingSecurityExpertise
        return BankingSecurityExpertise(site_type)

    @classmethod
    def get_available_domains(cls) -> List[str]:
        """Get list of registered domains."""
        return list(cls._registry.keys())