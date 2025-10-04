"""
Domain Expertise Services for Site Onboarding.

This package provides industry-specific domain expertise for security auditing,
compliance validation, and SOP generation.

Available domains:
- Banking/Financial (RBI, ASIS compliance)
- Retail (loss prevention, customer safety)
- Industrial (workplace safety, OSHA)
- Healthcare (HIPAA, patient safety)
- Government (physical security standards)

Each domain provides:
- Compliance vocabulary and standards
- Risk assessment frameworks
- SOP templates
- Targeted audit questions
- Configuration validation
"""

from .base import DomainExpertise

__all__ = ['DomainExpertise']