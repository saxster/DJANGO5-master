"""
SOP Generator Service - Create multilingual Standard Operating Procedures.

This service generates compliance-aware SOPs from observations, domain expertise,
and zone/asset requirements. Supports multilingual translation and includes
comprehensive citations.

Features:
- Zone-based SOP generation
- Asset-specific procedures
- Multilingual translation
- Compliance citations (RBI/ASIS/ISO)
- Staffing requirements (no cost)
- Escalation triggers

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Asset,
    SOP
)
from apps.onboarding_api.services.translation import get_conversation_translator

logger = logging.getLogger(__name__)


class SOPGeneratorService:
    """
    Generate Standard Operating Procedures with multilingual support.

    Creates comprehensive, compliance-aware SOPs from site audit data.
    """

    def __init__(self):
        """Initialize SOP generator with translation service."""
        self.translator = get_conversation_translator()

    def generate_zone_sop(
        self,
        zone: OnboardingZone,
        observations: List[Dict[str, Any]],
        domain_expertise=None,
        target_languages: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate SOP for specific zone.

        Args:
            zone: OnboardingZone instance
            observations: Observations for this zone
            domain_expertise: Domain expertise service
            target_languages: Languages for translation (e.g., ['hi', 'mr'])

        Returns:
            {
                'sop_title': str,
                'purpose': str,
                'steps': List[Dict],
                'staffing_required': Dict,
                'compliance_references': List[str],
                'frequency': str,
                'escalation_triggers': List[str],
                'translated_texts': Dict[str, Dict]
            }
        """
        try:
            # Get SOP template from domain expertise
            if domain_expertise:
                template = domain_expertise.get_sop_template(zone.zone_type)
            else:
                template = self._get_default_template(zone.zone_type)

            # Enhance with observation insights
            enhanced_sop = self._enhance_with_observations(
                template,
                observations,
                zone
            )

            # Add compliance references
            enhanced_sop['compliance_references'] = self._gather_compliance_refs(
                zone,
                observations,
                domain_expertise
            )

            # Add escalation triggers
            enhanced_sop['escalation_triggers'] = self._define_escalation_triggers(
                zone,
                observations
            )

            # Generate translations if requested
            if target_languages:
                enhanced_sop['translated_texts'] = self._translate_sop(
                    enhanced_sop,
                    target_languages
                )
            else:
                enhanced_sop['translated_texts'] = {}

            logger.info(
                f"Generated SOP for {zone.zone_name} ({zone.zone_type}) "
                f"with {len(enhanced_sop['steps'])} steps"
            )

            return enhanced_sop

        except Exception as e:
            logger.error(f"Error generating zone SOP: {str(e)}", exc_info=True)
            return self._get_fallback_sop(zone)

    def generate_asset_sop(
        self,
        asset: Asset,
        zone: OnboardingZone,
        domain_expertise=None,
        target_languages: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate asset-specific SOP.

        Args:
            asset: Asset instance
            zone: Parent zone
            domain_expertise: Domain expertise service
            target_languages: Languages for translation

        Returns:
            SOP dictionary with asset-specific procedures
        """
        try:
            # Get asset-specific template
            if domain_expertise:
                template = domain_expertise.get_sop_template(
                    zone.zone_type,
                    asset.asset_type
                )
            else:
                template = self._get_asset_template(asset.asset_type)

            # Customize for specific asset
            customized = self._customize_for_asset(template, asset, zone)

            # Add compliance references
            customized['compliance_references'] = self._gather_asset_compliance_refs(
                asset,
                zone,
                domain_expertise
            )

            # Generate translations
            if target_languages:
                customized['translated_texts'] = self._translate_sop(
                    customized,
                    target_languages
                )
            else:
                customized['translated_texts'] = {}

            logger.info(f"Generated asset SOP for {asset.asset_name} ({asset.asset_type})")

            return customized

        except Exception as e:
            logger.error(f"Error generating asset SOP: {str(e)}", exc_info=True)
            return self._get_fallback_asset_sop(asset)

    def generate_site_sops(
        self,
        site: OnboardingSite,
        domain_expertise=None,
        target_languages: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate all SOPs for site (zones + assets).

        Args:
            site: OnboardingSite instance
            domain_expertise: Domain expertise service
            target_languages: Languages for translation

        Returns:
            List of generated SOPs
        """
        all_sops = []

        try:
            # Get zones with related data
            zones = site.zones.prefetch_related(
                'observations',
                'assets'
            ).all()

            for zone in zones:
                # Get observations for zone
                observations = [
                    {
                        'enhanced_text': obs.enhanced_observation.get('enhanced_text', ''),
                        'severity': obs.severity,
                        'entities': obs.entities
                    }
                    for obs in zone.observations.all()
                ]

                # Generate zone SOP
                zone_sop = self.generate_zone_sop(
                    zone,
                    observations,
                    domain_expertise,
                    target_languages
                )
                zone_sop['zone_id'] = str(zone.zone_id)
                zone_sop['zone_name'] = zone.zone_name
                all_sops.append(zone_sop)

                # Generate asset SOPs
                for asset in zone.assets.all():
                    asset_sop = self.generate_asset_sop(
                        asset,
                        zone,
                        domain_expertise,
                        target_languages
                    )
                    asset_sop['asset_id'] = str(asset.asset_id)
                    asset_sop['zone_id'] = str(zone.zone_id)
                    all_sops.append(asset_sop)

            logger.info(f"Generated {len(all_sops)} SOPs for site {site.business_unit.buname}")

        except Exception as e:
            logger.error(f"Error generating site SOPs: {str(e)}", exc_info=True)

        return all_sops

    def save_sop(
        self,
        sop_data: Dict[str, Any],
        site: OnboardingSite,
        zone: OnboardingZone = None,
        asset: Asset = None,
        reviewed_by=None
    ) -> SOP:
        """
        Save SOP to database.

        Args:
            sop_data: SOP dictionary
            site: OnboardingSite instance
            zone: Optional zone
            asset: Optional asset
            reviewed_by: Optional reviewer user

        Returns:
            Created SOP instance
        """
        sop = SOP.objects.create(
            site=site,
            zone=zone,
            asset=asset,
            sop_title=sop_data['sop_title'],
            purpose=sop_data['purpose'],
            steps=sop_data['steps'],
            staffing_required=sop_data['staffing_required'],
            compliance_references=sop_data.get('compliance_references', []),
            frequency=sop_data['frequency'],
            translated_texts=sop_data.get('translated_texts', {}),
            escalation_triggers=sop_data.get('escalation_triggers', []),
            llm_generated=True,
            reviewed_by=reviewed_by
        )

        logger.info(f"Saved SOP: {sop.sop_title} (ID: {sop.sop_id})")
        return sop

    def _enhance_with_observations(
        self,
        template: Dict[str, Any],
        observations: List[Dict[str, Any]],
        zone: OnboardingZone
    ) -> Dict[str, Any]:
        """Enhance SOP template with observation insights."""
        enhanced = template.copy()

        # Add observation-based steps
        additional_steps = []

        for obs in observations:
            if obs.get('severity') in ['critical', 'high']:
                # Add specific monitoring step
                step_num = len(enhanced['steps']) + len(additional_steps) + 1
                additional_steps.append({
                    'step': step_num,
                    'action': f"Monitor and address: {obs.get('enhanced_text', '')[:100]}",
                    'responsible': 'Security Officer',
                    'observation_based': True
                })

        if additional_steps:
            enhanced['steps'].extend(additional_steps)

        return enhanced

    def _gather_compliance_refs(
        self,
        zone: OnboardingZone,
        observations: List[Dict[str, Any]],
        domain_expertise=None
    ) -> List[str]:
        """Gather relevant compliance references."""
        refs = []

        # Get domain-specific standards
        if domain_expertise:
            standards = domain_expertise.get_compliance_standards()
            refs.extend(standards)

        # Add zone-specific compliance
        if zone.zone_type in ['vault', 'atm', 'cash_counter']:
            refs.append('RBI Master Direction on Security Measures in Banks (2021)')

        if zone.zone_type in ['control_room', 'server_room']:
            refs.append('ISO 27001 Information Security Management')

        # Generic physical security standard
        if 'ASIS' not in ' '.join(refs):
            refs.append('ASIS International Physical Security Standards')

        return list(set(refs))  # Remove duplicates

    def _define_escalation_triggers(
        self,
        zone: OnboardingZone,
        observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Define when to escalate from standard procedure."""
        triggers = []

        # Zone-specific triggers
        if zone.zone_type == 'vault':
            triggers.extend([
                'Unauthorized access attempt detected',
                'Vault door malfunction or alarm activation',
                'Dual custody violation observed'
            ])
        elif zone.zone_type == 'atm':
            triggers.extend([
                'ATM tampering or skimming device detected',
                'Cash dispenser malfunction',
                'Customer distress or robbery in progress'
            ])
        elif zone.zone_type == 'gate':
            triggers.extend([
                'Unauthorized entry attempt',
                'Suspicious package or vehicle',
                'Metal detector alarm activation'
            ])

        # Observation-based triggers
        for obs in observations:
            if obs.get('severity') == 'critical':
                triggers.append('Critical issue requiring immediate supervisor notification')
                break

        # Generic triggers
        triggers.extend([
            'Any security incident or breach',
            'Equipment failure affecting critical systems',
            'Emergency situation requiring external assistance'
        ])

        return list(set(triggers))  # Remove duplicates

    def _translate_sop(
        self,
        sop: Dict[str, Any],
        target_languages: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Translate SOP to target languages."""
        translated = {}

        for lang in target_languages:
            if lang == 'en':
                continue

            try:
                translated[lang] = {
                    'title': self.translator.service.translate_text(
                        sop['sop_title'],
                        lang,
                        'en'
                    ),
                    'purpose': self.translator.service.translate_text(
                        sop['purpose'],
                        lang,
                        'en'
                    ),
                    'steps': [
                        {
                            'step': step['step'],
                            'action': self.translator.service.translate_text(
                                step['action'],
                                lang,
                                'en'
                            ),
                            'responsible': step['responsible']
                        }
                        for step in sop['steps']
                    ]
                }

                logger.info(f"Translated SOP to {lang}")

            except Exception as e:
                logger.error(f"Error translating SOP to {lang}: {str(e)}")
                translated[lang] = {'error': f"Translation failed: {str(e)}"}

        return translated

    def _get_default_template(self, zone_type: str) -> Dict[str, Any]:
        """Get default SOP template for zone type."""
        return {
            'sop_title': f"{zone_type.replace('_', ' ').title()} Security Protocol",
            'purpose': f"Standard security procedures for {zone_type.replace('_', ' ')} zone",
            'steps': [
                {'step': 1, 'action': 'Conduct visual inspection of area', 'responsible': 'Security Officer'},
                {'step': 2, 'action': 'Verify all security systems operational', 'responsible': 'Security Officer'},
                {'step': 3, 'action': 'Document findings in security log', 'responsible': 'Security Officer'}
            ],
            'frequency': 'shift',
            'staffing_required': {
                'roles': ['Security Officer'],
                'count': 1,
                'schedule': 'Per shift assignment'
            }
        }

    def _get_asset_template(self, asset_type: str) -> Dict[str, Any]:
        """Get default asset SOP template."""
        templates = {
            'camera': {
                'sop_title': 'CCTV Camera Inspection and Maintenance',
                'purpose': 'Ensure continuous CCTV operation and optimal recording quality',
                'steps': [
                    {'step': 1, 'action': 'Verify camera power and connectivity', 'responsible': 'Security Officer'},
                    {'step': 2, 'action': 'Check lens clarity and positioning', 'responsible': 'Security Officer'},
                    {'step': 3, 'action': 'Verify recording to DVR/NVR', 'responsible': 'Technical Officer'},
                    {'step': 4, 'action': 'Document inspection results', 'responsible': 'Security Officer'}
                ],
                'frequency': 'daily',
                'staffing_required': {'roles': ['Security Officer', 'Technical Officer'], 'count': 2}
            },
            'alarm': {
                'sop_title': 'Alarm System Testing and Maintenance',
                'purpose': 'Ensure alarm system operational readiness and proper response',
                'steps': [
                    {'step': 1, 'action': 'Test alarm activation', 'responsible': 'Technical Officer'},
                    {'step': 2, 'action': 'Verify control room notification', 'responsible': 'Security Supervisor'},
                    {'step': 3, 'action': 'Check battery backup status', 'responsible': 'Technical Officer'},
                    {'step': 4, 'action': 'Document test results', 'responsible': 'Technical Officer'}
                ],
                'frequency': 'weekly',
                'staffing_required': {'roles': ['Technical Officer', 'Security Supervisor'], 'count': 2}
            }
        }

        return templates.get(asset_type, self._get_default_template('equipment'))

    def _customize_for_asset(
        self,
        template: Dict[str, Any],
        asset: Asset,
        zone: OnboardingZone
    ) -> Dict[str, Any]:
        """Customize template for specific asset instance."""
        customized = template.copy()

        # Customize title with asset name
        customized['sop_title'] = f"{asset.asset_name} - {template['sop_title']}"

        # Add asset specifications to purpose
        if asset.specifications:
            specs_text = ', '.join(
                f"{k}: {v}"
                for k, v in asset.specifications.items()
                if k in ['model', 'serial', 'location']
            )
            if specs_text:
                customized['purpose'] += f" ({specs_text})"

        return customized

    def _gather_asset_compliance_refs(
        self,
        asset: Asset,
        zone: OnboardingZone,
        domain_expertise=None
    ) -> List[str]:
        """Gather compliance references for asset."""
        refs = []

        if asset.asset_type in ['camera', 'dvr_nvr']:
            refs.append('ASIS GDL 2019 - Surveillance Systems')

        if asset.asset_type in ['alarm', 'sensor']:
            refs.append('ASIS PSC.1-2012 - Alarm Monitoring')

        if asset.asset_type in ['access_reader', 'biometric']:
            refs.append('ASIS GDL - Access Control Systems')

        # Generic standard
        refs.append('ASIS International Physical Security Standards')

        return list(set(refs))

    def _get_fallback_sop(self, zone: OnboardingZone) -> Dict[str, Any]:
        """Get fallback SOP in case of error."""
        return {
            'sop_title': f"{zone.zone_name} Security Protocol",
            'purpose': "Standard security procedures",
            'steps': [
                {'step': 1, 'action': 'Monitor assigned area', 'responsible': 'Security Officer'},
                {'step': 2, 'action': 'Report incidents immediately', 'responsible': 'Security Officer'}
            ],
            'frequency': 'continuous',
            'staffing_required': {'roles': ['Security Officer'], 'count': 1},
            'compliance_references': ['ASIS International Standards'],
            'escalation_triggers': ['Any security incident'],
            'translated_texts': {}
        }

    def _get_fallback_asset_sop(self, asset: Asset) -> Dict[str, Any]:
        """Get fallback asset SOP in case of error."""
        return {
            'sop_title': f"{asset.asset_name} Monitoring",
            'purpose': "Monitor asset operational status",
            'steps': [
                {'step': 1, 'action': 'Verify operational status', 'responsible': 'Security Officer'},
                {'step': 2, 'action': 'Report malfunctions', 'responsible': 'Security Officer'}
            ],
            'frequency': 'shift',
            'staffing_required': {'roles': ['Security Officer'], 'count': 1},
            'compliance_references': ['ASIS International Standards'],
            'escalation_triggers': ['Equipment malfunction'],
            'translated_texts': {}
        }


# Factory function
def get_sop_generator_service() -> SOPGeneratorService:
    """Factory function to get SOP generator service instance."""
    return SOPGeneratorService()