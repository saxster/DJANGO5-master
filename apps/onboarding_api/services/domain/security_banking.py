"""
Banking Security Expertise - RBI/ASIS/ISO compliance.

This module provides domain-specific expertise for banking and financial
institution security, with compliance validation against:
- RBI (Reserve Bank of India) Master Directions
- ASIS International Physical Security Standards
- ISO 27001 Information Security
- Local banking regulations

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional

from .base import DomainExpertise, DomainExpertiseFactory

logger = logging.getLogger(__name__)


class BankingSecurityExpertise(DomainExpertise):
    """
    Banking and financial institution security expertise.

    Implements RBI/ASIS compliance checks and provides banking-specific
    security assessment and SOP generation.
    """

    def enhance_observation(
        self,
        observation: Dict[str, Any],
        zone_type: str
    ) -> Dict[str, Any]:
        """Steel-man observation with banking security terminology."""
        raw_text = observation.get('transcript', '')
        detected_objects = observation.get('detected_objects', [])

        # Standardize terminology
        enhanced_text = self.standardize_terminology(raw_text)

        # Add banking-specific context
        if zone_type == 'vault':
            enhanced_text = self._enhance_vault_observation(enhanced_text, detected_objects)
        elif zone_type == 'atm':
            enhanced_text = self._enhance_atm_observation(enhanced_text, detected_objects)
        elif zone_type == 'cash_counter':
            enhanced_text = self._enhance_cash_counter_observation(enhanced_text, detected_objects)

        # Assess risk
        risk_level = self._assess_observation_risk(enhanced_text, zone_type, detected_objects)

        # Identify compliance issues
        compliance_issues = self._identify_compliance_issues(
            enhanced_text,
            zone_type,
            detected_objects
        )

        # Generate recommended actions
        recommended_actions = self._generate_actions(
            risk_level,
            compliance_issues,
            zone_type
        )

        # Cite relevant standards
        citations = self._get_relevant_citations(zone_type, compliance_issues)

        return {
            'enhanced_text': enhanced_text,
            'risk_level': risk_level,
            'compliance_issues': compliance_issues,
            'recommended_actions': recommended_actions,
            'citations': citations
        }

    def generate_questions(
        self,
        zone_type: str,
        current_observations: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate targeted audit questions for banking zones."""
        questions = []

        # Zone-specific question templates
        zone_questions = {
            'vault': [
                {
                    'question': 'Is the vault door time-locked with dual-custody access?',
                    'category': 'access_control',
                    'priority': 'critical',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'RBI Master Direction on Security Measures - Vault Access'
                },
                {
                    'question': 'Are CCTV cameras positioned to cover vault entry and interior?',
                    'category': 'surveillance',
                    'priority': 'critical',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'ASIS GDL 2019 - Critical Asset Monitoring'
                },
                {
                    'question': 'What is the vault door rating and last inspection date?',
                    'category': 'physical_security',
                    'priority': 'high',
                    'expected_answer_type': 'text',
                    'compliance_reference': 'RBI - Vault Construction Standards'
                }
            ],
            'atm': [
                {
                    'question': 'Is the ATM equipped with anti-skimming devices?',
                    'category': 'fraud_prevention',
                    'priority': 'critical',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'RBI Guidelines on ATM Security'
                },
                {
                    'question': 'Are cameras covering cash replenishment and user interface?',
                    'category': 'surveillance',
                    'priority': 'high',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'ASIS - ATM Security Standard'
                },
                {
                    'question': 'Is the ATM booth lighting adequate (minimum 10 lux)?',
                    'category': 'physical_security',
                    'priority': 'medium',
                    'expected_answer_type': 'measurement',
                    'compliance_reference': 'RBI - ATM Site Requirements'
                }
            ],
            'cash_counter': [
                {
                    'question': 'Are cash drawers equipped with time-delay locks?',
                    'category': 'access_control',
                    'priority': 'high',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'RBI - Cash Handling Procedures'
                },
                {
                    'question': 'Is dual-custody maintained for high-value transactions?',
                    'category': 'operational_control',
                    'priority': 'critical',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'RBI Master Direction - Transaction Controls'
                }
            ],
            'gate': [
                {
                    'question': 'Are entry/exit logs maintained with visitor verification?',
                    'category': 'access_control',
                    'priority': 'high',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'ASIS - Access Control Standards'
                },
                {
                    'question': 'Is metal detection operational at entry points?',
                    'category': 'threat_detection',
                    'priority': 'high',
                    'expected_answer_type': 'yes_no',
                    'compliance_reference': 'RBI - Branch Security Guidelines'
                }
            ]
        }

        questions = zone_questions.get(zone_type, [])

        # Add follow-up questions based on existing observations
        if current_observations:
            questions.extend(self._generate_followup_questions(
                zone_type,
                current_observations
            ))

        return questions

    def validate_configuration(
        self,
        zone_type: str,
        configuration: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate configuration against RBI/ASIS standards."""
        violations = []
        recommendations = []

        # Get minimum requirements
        requirements = self._get_zone_requirements(zone_type)

        # Validate camera coverage
        camera_count = configuration.get('camera_count', 0)
        if camera_count < requirements.get('min_cameras', 0):
            violations.append({
                'type': 'insufficient_surveillance',
                'severity': 'high',
                'message': f"Zone requires minimum {requirements['min_cameras']} cameras, found {camera_count}",
                'standard': 'ASIS GDL 2019'
            })
            recommendations.append(
                f"Install {requirements['min_cameras'] - camera_count} additional cameras"
            )

        # Validate guard coverage
        guard_hours = configuration.get('guard_coverage_hours', 0)
        required_hours = self.get_minimum_coverage_hours(zone_type)
        if guard_hours < required_hours:
            violations.append({
                'type': 'insufficient_coverage',
                'severity': 'critical' if zone_type in ['vault', 'atm'] else 'high',
                'message': f"Zone requires {required_hours}h coverage, configured for {guard_hours}h",
                'standard': 'RBI Master Direction - Guard Requirements'
            })

        # Validate access control
        if zone_type in ['vault', 'cash_counter', 'control_room']:
            has_access_control = configuration.get('has_access_control', False)
            if not has_access_control:
                violations.append({
                    'type': 'missing_access_control',
                    'severity': 'critical',
                    'message': f"Critical zone '{zone_type}' requires electronic access control",
                    'standard': 'RBI - Access Control Mandate'
                })
                recommendations.append("Install biometric or card-based access control")

        # Calculate risk score
        risk_score = Decimal(str(len(violations) * 0.15))
        risk_score = min(risk_score, Decimal('1.0'))

        return {
            'is_compliant': len(violations) == 0,
            'violations': violations,
            'recommendations': recommendations,
            'risk_score': risk_score
        }

    def get_sop_template(
        self,
        zone_type: str,
        asset_type: str = None
    ) -> Dict[str, Any]:
        """Get banking-specific SOP template."""
        templates = self._load_sop_templates()

        template_key = f"{zone_type}_{asset_type}" if asset_type else zone_type

        return templates.get(template_key, self._get_default_template(zone_type))

    def assess_risk(
        self,
        zone_type: str,
        observations: List[Dict[str, Any]],
        assets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess risk level for banking zone."""
        risk_factors = []
        risk_score = Decimal('0.0')

        # Base risk by zone type
        zone_base_risk = {
            'vault': Decimal('0.9'),
            'atm': Decimal('0.85'),
            'cash_counter': Decimal('0.8'),
            'control_room': Decimal('0.75'),
            'gate': Decimal('0.6'),
            'reception': Decimal('0.4')
        }
        risk_score = zone_base_risk.get(zone_type, Decimal('0.5'))

        # Analyze observations for risk indicators
        for obs in observations:
            if obs.get('severity') in ['critical', 'high']:
                risk_factors.append(f"High severity issue: {obs.get('enhanced_text', '')[:50]}...")
                risk_score += Decimal('0.1')

        # Analyze asset deficiencies
        required_assets = self._get_zone_requirements(zone_type).get('required_assets', [])
        present_assets = [a.get('asset_type') for a in assets]

        for required in required_assets:
            if required not in present_assets:
                risk_factors.append(f"Missing required asset: {required}")
                risk_score += Decimal('0.15')

        # Cap at 1.0
        risk_score = min(risk_score, Decimal('1.0'))

        # Determine overall risk level
        if risk_score >= Decimal('0.8'):
            overall_risk = 'severe'
            mitigation_priority = 'immediate'
        elif risk_score >= Decimal('0.6'):
            overall_risk = 'high'
            mitigation_priority = 'urgent'
        elif risk_score >= Decimal('0.4'):
            overall_risk = 'moderate'
            mitigation_priority = 'planned'
        else:
            overall_risk = 'low'
            mitigation_priority = 'routine'

        return {
            'overall_risk': overall_risk,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'mitigation_priority': mitigation_priority
        }

    def _load_compliance_standards(self) -> Dict[str, Any]:
        """Load RBI/ASIS banking compliance standards."""
        return {
            'RBI_MASTER_DIRECTION_2021': {
                'title': 'RBI Master Direction on Security Measures in Banks',
                'requirements': {
                    'vault_access': 'Dual custody with time locks',
                    'camera_retention': '90 days minimum',
                    'guard_training': 'Annual certification required',
                    'alarm_response': 'Within 5 minutes'
                }
            },
            'ASIS_GDL_2019': {
                'title': 'ASIS General Security Risk Assessment Guideline',
                'requirements': {
                    'camera_coverage': 'No blind spots in critical zones',
                    'access_layers': 'Minimum 3 layers for critical assets',
                    'lighting_standards': 'Minimum 10 lux for ATMs'
                }
            },
            'ISO_27001': {
                'title': 'ISO 27001 Information Security Management',
                'requirements': {
                    'access_logging': 'All access events logged',
                    'incident_response': 'Documented procedures required',
                    'periodic_review': 'Annual security audits'
                }
            }
        }

    def _load_sop_templates(self) -> Dict[str, Any]:
        """Load banking SOP templates."""
        return {
            'vault': {
                'title': 'Vault Access and Security Protocol',
                'purpose': 'Ensure secure access to vault with dual custody and comprehensive audit trail',
                'steps': [
                    {'step': 1, 'action': 'Verify time lock status', 'responsible': 'Branch Manager'},
                    {'step': 2, 'action': 'Dual custody verification', 'responsible': 'Manager + Cashier'},
                    {'step': 3, 'action': 'Access logging in register', 'responsible': 'Both parties'},
                    {'step': 4, 'action': 'Camera verification active', 'responsible': 'Security Officer'},
                    {'step': 5, 'action': 'Post-access lock verification', 'responsible': 'Both parties'}
                ],
                'frequency': 'every_access',
                'staffing': {'roles': ['Branch Manager', 'Senior Cashier', 'Security Officer'], 'count': 3},
                'compliance_references': ['RBI Master Direction 2021 - Vault Access', 'ASIS GDL 2019']
            },
            'atm': {
                'title': 'ATM Site Inspection and Maintenance',
                'purpose': 'Ensure ATM security, functionality, and compliance with RBI guidelines',
                'steps': [
                    {'step': 1, 'action': 'Verify camera functionality', 'responsible': 'Security Guard'},
                    {'step': 2, 'action': 'Check lighting adequacy', 'responsible': 'Security Guard'},
                    {'step': 3, 'action': 'Inspect anti-skimming devices', 'responsible': 'Technical Officer'},
                    {'step': 4, 'action': 'Test alarm connectivity', 'responsible': 'Technical Officer'},
                    {'step': 5, 'action': 'Record inspection in log', 'responsible': 'Security Guard'}
                ],
                'frequency': 'daily',
                'staffing': {'roles': ['Security Guard', 'Technical Officer'], 'count': 2},
                'compliance_references': ['RBI Guidelines on ATM Security', 'ASIS ATM Standard']
            }
        }

    def _get_zone_requirements(self, zone_type: str) -> Dict[str, Any]:
        """Get minimum security requirements for zone."""
        requirements = {
            'vault': {
                'min_cameras': 3,
                'required_assets': ['camera', 'alarm', 'access_reader'],
                'guard_coverage': 24,
                'access_control': 'biometric'
            },
            'atm': {
                'min_cameras': 2,
                'required_assets': ['camera', 'lighting', 'alarm'],
                'guard_coverage': 24,
                'access_control': 'surveillance'
            },
            'cash_counter': {
                'min_cameras': 2,
                'required_assets': ['camera', 'alarm'],
                'guard_coverage': 12,
                'access_control': 'time_delay_lock'
            },
            'gate': {
                'min_cameras': 1,
                'required_assets': ['camera', 'metal_detector'],
                'guard_coverage': 24,
                'access_control': 'manual'
            }
        }

        return requirements.get(zone_type, {'min_cameras': 1, 'required_assets': [], 'guard_coverage': 8})

    def _enhance_vault_observation(self, text: str, objects: List[str]) -> str:
        """Enhance vault-specific observations."""
        enhanced = f"Vault Security Assessment: {text}"

        # Add technical details
        if 'door' in text.lower() or 'Door' in objects:
            enhanced += " Door configuration noted for time-lock compliance verification."

        if 'camera' in text.lower() or 'Camera' in objects:
            enhanced += " CCTV coverage evaluated for blind spot analysis."

        return enhanced

    def _enhance_atm_observation(self, text: str, objects: List[str]) -> str:
        """Enhance ATM-specific observations."""
        enhanced = f"ATM Site Security Assessment: {text}"

        if 'light' in text.lower() or 'Lighting' in objects:
            enhanced += " Illumination levels require lux meter validation (RBI minimum: 10 lux)."

        return enhanced

    def _enhance_cash_counter_observation(self, text: str, objects: List[str]) -> str:
        """Enhance cash counter observations."""
        enhanced = f"Cash Counter Security Review: {text}"

        if 'drawer' in text.lower():
            enhanced += " Time-delay lock mechanism compliance check recommended."

        return enhanced

    def _assess_observation_risk(self, text: str, zone_type: str, objects: List[str]) -> str:
        """Assess risk level from observation."""
        text_lower = text.lower()

        # Critical risk keywords
        if any(word in text_lower for word in ['unsecured', 'missing', 'broken', 'inoperative']):
            if zone_type in ['vault', 'atm', 'cash_counter']:
                return 'critical'
            return 'high'

        # High risk keywords
        if any(word in text_lower for word in ['blocked', 'obstructed', 'damaged']):
            return 'high'

        # Medium risk
        if any(word in text_lower for word in ['needs repair', 'legacy', 'outdated']):
            return 'medium'

        return 'low'

    def _identify_compliance_issues(self, text: str, zone_type: str, objects: List[str]) -> List[str]:
        """Identify RBI/ASIS compliance issues."""
        issues = []
        text_lower = text.lower()

        if zone_type == 'vault':
            if 'no camera' in text_lower or len([o for o in objects if 'camera' in o.lower()]) < 3:
                issues.append("Insufficient CCTV coverage (RBI requires minimum 3 cameras)")

        if zone_type == 'atm':
            if 'no light' in text_lower or 'dark' in text_lower:
                issues.append("Inadequate lighting (RBI mandates minimum 10 lux)")

        return issues

    def _generate_actions(self, risk_level: str, compliance_issues: List[str], zone_type: str) -> List[str]:
        """Generate recommended actions."""
        actions = []

        if risk_level in ['critical', 'high']:
            actions.append("Immediate remediation required")
            actions.append("Escalate to branch security officer")

        for issue in compliance_issues:
            if 'camera' in issue.lower():
                actions.append("Install additional CCTV cameras per RBI guidelines")
            if 'lighting' in issue.lower():
                actions.append("Upgrade lighting to meet 10 lux minimum standard")

        return actions

    def _get_relevant_citations(self, zone_type: str, issues: List[str]) -> List[str]:
        """Get relevant compliance citations."""
        citations = []

        if zone_type in ['vault', 'atm', 'cash_counter']:
            citations.append("RBI Master Direction on Security Measures in Banks (2021)")

        if any('camera' in issue.lower() for issue in issues):
            citations.append("ASIS GDL 2019 - General Security Risk Assessment")

        if not citations:
            citations.append("ASIS International Physical Security Standards")

        return citations

    def _generate_followup_questions(self, zone_type: str, observations: List[Dict]) -> List[Dict]:
        """Generate follow-up questions based on observations."""
        questions = []

        # Check for gaps in observations
        observed_topics = set()
        for obs in observations:
            text = obs.get('enhanced_text', '').lower()
            if 'camera' in text:
                observed_topics.add('surveillance')
            if 'guard' in text or 'officer' in text:
                observed_topics.add('staffing')
            if 'alarm' in text:
                observed_topics.add('alarms')

        # Add questions for missing topics
        if 'surveillance' not in observed_topics:
            questions.append({
                'question': 'What is the CCTV camera configuration and recording retention period?',
                'category': 'surveillance',
                'priority': 'high',
                'expected_answer_type': 'text',
                'compliance_reference': 'RBI - 90 day retention mandate'
            })

        return questions

    def _get_default_template(self, zone_type: str) -> Dict[str, Any]:
        """Get default SOP template."""
        return {
            'title': f"{zone_type.replace('_', ' ').title()} Security Protocol",
            'purpose': f"Standard security procedures for {zone_type} zone",
            'steps': [
                {'step': 1, 'action': 'Visual inspection of area', 'responsible': 'Security Officer'},
                {'step': 2, 'action': 'Verify all security systems operational', 'responsible': 'Security Officer'},
                {'step': 3, 'action': 'Document findings in log', 'responsible': 'Security Officer'}
            ],
            'frequency': 'shift',
            'staffing': {'roles': ['Security Officer'], 'count': 1},
            'compliance_references': ['ASIS International Standards']
        }


# Register this domain expertise
DomainExpertiseFactory.register('banking', BankingSecurityExpertise)