"""
Configuration templates service for Conversational Onboarding

Provides curated starter templates for common site types to reduce LLM dependency
and accelerate onboarding for standard configurations.
"""
import logging
from typing import Dict, List, Optional, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConfigurationTemplate:
    """Represents a configuration template for a specific site type"""

    def __init__(self, template_id: str, name: str, description: str,
                 config: Dict[str, Any], metadata: Dict[str, Any] = None):
        self.template_id = template_id
        self.name = name
        self.description = description
        self.config = config
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary representation"""
        return {
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'metadata': self.metadata
        }


class ConfigurationTemplateService:
    """Service for managing and applying configuration templates"""

    def __init__(self):
        self._templates = self._load_builtin_templates()

    def _load_builtin_templates(self) -> Dict[str, ConfigurationTemplate]:
        """Load built-in configuration templates"""
        templates = {}

        # Office/Corporate Template
        office_template = ConfigurationTemplate(
            template_id="office_corporate",
            name="Office/Corporate",
            description="Standard office environment with business hours and typical shift patterns",
            config={
                "business_units": [
                    {
                        "buname": "Main Office",
                        "bucode": "OFF001",
                        "bupreferences": {
                            "siteopentime": "08:00",
                            "siteclosetime": "18:00",
                            "guardstrenth": 2,
                            "malestrength": 1,
                            "femalestrength": 1,
                            "maxadmins": 3,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": False
                        },
                        "enable": True,
                        "gpsenable": False,
                        "enablesleepingguard": False
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Day Shift",
                        "starttime": "08:00:00",
                        "endtime": "17:00:00",
                        "peoplecount": 2,
                        "captchafreq": 30,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Night Security",
                        "starttime": "18:00:00",
                        "endtime": "06:00:00",
                        "peoplecount": 1,
                        "captchafreq": 60,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "SECURITY",
                        "taname": "Security Personnel",
                        "enable": True
                    },
                    {
                        "tacode": "ADMIN",
                        "taname": "Administrative Staff",
                        "enable": True
                    },
                    {
                        "tacode": "SUPERVISOR",
                        "taname": "Supervisor",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["office", "corporate", "headquarters", "business_center"],
                "complexity": "low",
                "setup_time_minutes": 15,
                "recommended_devices": 2,
                "typical_staff_count": "5-20"
            }
        )
        templates[office_template.template_id] = office_template

        # Warehouse/Industrial Template
        warehouse_template = ConfigurationTemplate(
            template_id="warehouse_industrial",
            name="Warehouse/Industrial",
            description="Industrial facility with 24/7 operations and multi-shift coverage",
            config={
                "business_units": [
                    {
                        "buname": "Warehouse Operations",
                        "bucode": "WH001",
                        "bupreferences": {
                            "siteopentime": "00:00",
                            "siteclosetime": "23:59",
                            "guardstrenth": 8,
                            "malestrength": 5,
                            "femalestrength": 3,
                            "maxadmins": 5,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": True,
                            "permissibledistance": 100,
                            "no_of_devices_allowed": 8,
                            "total_people_count": 25
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": True,
                        "iswarehouse": True,
                        "deviceevent": True
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Morning Shift",
                        "starttime": "06:00:00",
                        "endtime": "14:00:00",
                        "peoplecount": 8,
                        "captchafreq": 15,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Afternoon Shift",
                        "starttime": "14:00:00",
                        "endtime": "22:00:00",
                        "peoplecount": 6,
                        "captchafreq": 15,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Night Shift",
                        "starttime": "22:00:00",
                        "endtime": "06:00:00",
                        "peoplecount": 4,
                        "captchafreq": 20,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "GUARD",
                        "taname": "Security Guard",
                        "enable": True
                    },
                    {
                        "tacode": "SUPERVISOR",
                        "taname": "Shift Supervisor",
                        "enable": True
                    },
                    {
                        "tacode": "WAREHOUSE",
                        "taname": "Warehouse Worker",
                        "enable": True
                    },
                    {
                        "tacode": "DRIVER",
                        "taname": "Driver/Operator",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["warehouse", "industrial", "manufacturing", "distribution"],
                "complexity": "high",
                "setup_time_minutes": 45,
                "recommended_devices": 8,
                "typical_staff_count": "20-100"
            }
        )
        templates[warehouse_template.template_id] = warehouse_template

        # Retail/Store Template
        retail_template = ConfigurationTemplate(
            template_id="retail_store",
            name="Retail/Store",
            description="Retail store with customer-facing hours and point-of-sale security",
            config={
                "business_units": [
                    {
                        "buname": "Retail Store",
                        "bucode": "RT001",
                        "bupreferences": {
                            "siteopentime": "09:00",
                            "siteclosetime": "21:00",
                            "guardstrenth": 4,
                            "malestrength": 2,
                            "femalestrength": 2,
                            "maxadmins": 2,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": False,
                            "no_of_devices_allowed": 4,
                            "total_people_count": 12
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": False,
                        "deviceevent": True
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Opening Shift",
                        "starttime": "08:30:00",
                        "endtime": "16:30:00",
                        "peoplecount": 3,
                        "captchafreq": 20,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Closing Shift",
                        "starttime": "14:00:00",
                        "endtime": "22:00:00",
                        "peoplecount": 3,
                        "captchafreq": 20,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Security Overnight",
                        "starttime": "22:00:00",
                        "endtime": "08:00:00",
                        "peoplecount": 1,
                        "captchafreq": 45,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "CASHIER",
                        "taname": "Cashier",
                        "enable": True
                    },
                    {
                        "tacode": "SALES",
                        "taname": "Sales Associate",
                        "enable": True
                    },
                    {
                        "tacode": "MANAGER",
                        "taname": "Store Manager",
                        "enable": True
                    },
                    {
                        "tacode": "SECURITY",
                        "taname": "Security Guard",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["retail", "store", "shop", "mall", "boutique"],
                "complexity": "medium",
                "setup_time_minutes": 25,
                "recommended_devices": 4,
                "typical_staff_count": "8-25"
            }
        )
        templates[retail_template.template_id] = retail_template

        # Healthcare/Hospital Template
        healthcare_template = ConfigurationTemplate(
            template_id="healthcare_hospital",
            name="Healthcare/Hospital",
            description="Healthcare facility with 24/7 operations and strict security requirements",
            config={
                "business_units": [
                    {
                        "buname": "Medical Center",
                        "bucode": "HC001",
                        "bupreferences": {
                            "siteopentime": "00:00",
                            "siteclosetime": "23:59",
                            "guardstrenth": 12,
                            "malestrength": 6,
                            "femalestrength": 6,
                            "maxadmins": 8,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": True,
                            "permissibledistance": 50,
                            "no_of_devices_allowed": 12,
                            "total_people_count": 50
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": True,
                        "deviceevent": True,
                        "skipsiteaudit": False
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Day Shift",
                        "starttime": "07:00:00",
                        "endtime": "19:00:00",
                        "peoplecount": 12,
                        "captchafreq": 10,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Night Shift",
                        "starttime": "19:00:00",
                        "endtime": "07:00:00",
                        "peoplecount": 8,
                        "captchafreq": 15,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "NURSE",
                        "taname": "Nursing Staff",
                        "enable": True
                    },
                    {
                        "tacode": "DOCTOR",
                        "taname": "Medical Doctor",
                        "enable": True
                    },
                    {
                        "tacode": "SECURITY",
                        "taname": "Hospital Security",
                        "enable": True
                    },
                    {
                        "tacode": "ADMIN",
                        "taname": "Administrative Staff",
                        "enable": True
                    },
                    {
                        "tacode": "TECH",
                        "taname": "Medical Technician",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["hospital", "clinic", "healthcare", "medical_center"],
                "complexity": "high",
                "setup_time_minutes": 60,
                "recommended_devices": 12,
                "typical_staff_count": "30-200"
            }
        )
        templates[healthcare_template.template_id] = healthcare_template

        # Manufacturing/Factory Template
        manufacturing_template = ConfigurationTemplate(
            template_id="manufacturing_factory",
            name="Manufacturing/Factory",
            description="Manufacturing facility with multi-shift operations and safety requirements",
            config={
                "business_units": [
                    {
                        "buname": "Manufacturing Plant",
                        "bucode": "MFG001",
                        "bupreferences": {
                            "siteopentime": "00:00",
                            "siteclosetime": "23:59",
                            "guardstrenth": 15,
                            "malestrength": 10,
                            "femalestrength": 5,
                            "maxadmins": 10,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": True,
                            "permissibledistance": 200,
                            "no_of_devices_allowed": 15,
                            "total_people_count": 75
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": True,
                        "deviceevent": True,
                        "iswarehouse": False
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "First Shift",
                        "starttime": "06:00:00",
                        "endtime": "14:00:00",
                        "peoplecount": 25,
                        "captchafreq": 10,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Second Shift",
                        "starttime": "14:00:00",
                        "endtime": "22:00:00",
                        "peoplecount": 20,
                        "captchafreq": 10,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Third Shift",
                        "starttime": "22:00:00",
                        "endtime": "06:00:00",
                        "peoplecount": 15,
                        "captchafreq": 15,
                        "nightshiftappicable": True,
                        "enable": True
                    },
                    {
                        "shiftname": "Maintenance Shift",
                        "starttime": "02:00:00",
                        "endtime": "06:00:00",
                        "peoplecount": 5,
                        "captchafreq": 20,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "OPERATOR",
                        "taname": "Machine Operator",
                        "enable": True
                    },
                    {
                        "tacode": "SUPERVISOR",
                        "taname": "Production Supervisor",
                        "enable": True
                    },
                    {
                        "tacode": "MAINTENANCE",
                        "taname": "Maintenance Technician",
                        "enable": True
                    },
                    {
                        "tacode": "QC",
                        "taname": "Quality Control Inspector",
                        "enable": True
                    },
                    {
                        "tacode": "SAFETY",
                        "taname": "Safety Officer",
                        "enable": True
                    },
                    {
                        "tacode": "SECURITY",
                        "taname": "Plant Security",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["manufacturing", "factory", "plant", "production", "assembly"],
                "complexity": "high",
                "setup_time_minutes": 50,
                "recommended_devices": 15,
                "typical_staff_count": "50-200",
                "industry_specific_features": ["safety_compliance", "production_tracking", "equipment_monitoring"],
                "compliance_requirements": ["OSHA", "ISO_9001", "safety_protocols"]
            }
        )
        templates[manufacturing_template.template_id] = manufacturing_template

        # Educational Institution Template
        educational_template = ConfigurationTemplate(
            template_id="educational_institution",
            name="Educational Institution",
            description="School, college, or university with daytime operations and security needs",
            config={
                "business_units": [
                    {
                        "buname": "Educational Campus",
                        "bucode": "EDU001",
                        "bupreferences": {
                            "siteopentime": "06:00",
                            "siteclosetime": "22:00",
                            "guardstrenth": 6,
                            "malestrength": 3,
                            "femalestrength": 3,
                            "maxadmins": 5,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": False,
                            "permissibledistance": 150,
                            "no_of_devices_allowed": 8,
                            "total_people_count": 40
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": False,
                        "deviceevent": True
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Day Operations",
                        "starttime": "07:00:00",
                        "endtime": "18:00:00",
                        "peoplecount": 8,
                        "captchafreq": 25,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Evening Activities",
                        "starttime": "18:00:00",
                        "endtime": "22:00:00",
                        "peoplecount": 4,
                        "captchafreq": 30,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Night Security",
                        "starttime": "22:00:00",
                        "endtime": "07:00:00",
                        "peoplecount": 2,
                        "captchafreq": 45,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "TEACHER",
                        "taname": "Teaching Staff",
                        "enable": True
                    },
                    {
                        "tacode": "ADMIN",
                        "taname": "Administrative Staff",
                        "enable": True
                    },
                    {
                        "tacode": "SECURITY",
                        "taname": "Campus Security",
                        "enable": True
                    },
                    {
                        "tacode": "MAINTENANCE",
                        "taname": "Maintenance Staff",
                        "enable": True
                    },
                    {
                        "tacode": "STUDENT_WORKER",
                        "taname": "Student Worker",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["school", "college", "university", "educational", "campus"],
                "complexity": "medium",
                "setup_time_minutes": 30,
                "recommended_devices": 8,
                "typical_staff_count": "20-100",
                "special_considerations": ["student_privacy", "child_protection", "emergency_procedures"]
            }
        )
        templates[educational_template.template_id] = educational_template

        # Data Center Template
        datacenter_template = ConfigurationTemplate(
            template_id="datacenter_facility",
            name="Data Center",
            description="High-security data center with 24/7 operations and strict access controls",
            config={
                "business_units": [
                    {
                        "buname": "Data Center",
                        "bucode": "DC001",
                        "bupreferences": {
                            "siteopentime": "00:00",
                            "siteclosetime": "23:59",
                            "guardstrenth": 8,
                            "malestrength": 4,
                            "femalestrength": 4,
                            "maxadmins": 6,
                            "billingtype": "monthly",
                            "clienttimezone": "UTC",
                            "ispermitneeded": True,
                            "permissibledistance": 50,
                            "no_of_devices_allowed": 10,
                            "total_people_count": 20
                        },
                        "enable": True,
                        "gpsenable": True,
                        "enablesleepingguard": True,
                        "deviceevent": True,
                        "skipsiteaudit": False
                    }
                ],
                "shifts": [
                    {
                        "shiftname": "Day Operations",
                        "starttime": "08:00:00",
                        "endtime": "20:00:00",
                        "peoplecount": 6,
                        "captchafreq": 5,
                        "nightshiftappicable": False,
                        "enable": True
                    },
                    {
                        "shiftname": "Night Operations",
                        "starttime": "20:00:00",
                        "endtime": "08:00:00",
                        "peoplecount": 4,
                        "captchafreq": 5,
                        "nightshiftappicable": True,
                        "enable": True
                    }
                ],
                "type_assists": [
                    {
                        "tacode": "SYSADMIN",
                        "taname": "System Administrator",
                        "enable": True
                    },
                    {
                        "tacode": "SECURITY",
                        "taname": "Physical Security",
                        "enable": True
                    },
                    {
                        "tacode": "TECH",
                        "taname": "Data Center Technician",
                        "enable": True
                    },
                    {
                        "tacode": "MANAGER",
                        "taname": "Facility Manager",
                        "enable": True
                    },
                    {
                        "tacode": "NETWORK",
                        "taname": "Network Engineer",
                        "enable": True
                    }
                ]
            },
            metadata={
                "suitable_for": ["datacenter", "server_farm", "cloud_facility", "colocation"],
                "complexity": "high",
                "setup_time_minutes": 40,
                "recommended_devices": 10,
                "typical_staff_count": "10-30",
                "security_level": "maximum",
                "compliance_requirements": ["SOC2", "ISO_27001", "HIPAA", "physical_access_controls"]
            }
        )
        templates[datacenter_template.template_id] = datacenter_template

        return templates

    def get_all_templates(self) -> List[ConfigurationTemplate]:
        """Get all available configuration templates"""
        return list(self._templates.values())

    def get_template(self, template_id: str) -> Optional[ConfigurationTemplate]:
        """Get a specific template by ID"""
        return self._templates.get(template_id)

    def find_templates_by_keywords(self, keywords: List[str]) -> List[ConfigurationTemplate]:
        """Find templates matching given keywords"""
        matching_templates = []

        for template in self._templates.values():
            # Check if any keyword matches template metadata
            suitable_for = template.metadata.get('suitable_for', [])
            for keyword in keywords:
                if any(keyword.lower() in suitable.lower() for suitable in suitable_for):
                    matching_templates.append(template)
                    break
                elif keyword.lower() in template.name.lower():
                    matching_templates.append(template)
                    break
                elif keyword.lower() in template.description.lower():
                    matching_templates.append(template)
                    break

        return matching_templates

    def recommend_templates(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recommend templates based on context information

        Args:
            context: Dictionary containing site information like:
                - site_type: Type of facility
                - operating_hours: Operating schedule
                - staff_count: Number of staff
                - security_level: Required security level

        Returns:
            List of recommended templates with confidence scores
        """
        recommendations = []

        site_type = context.get('site_type', '').lower()
        staff_count = context.get('staff_count', 0)
        operating_hours = context.get('operating_hours', '').lower()

        for template in self._templates.values():
            confidence = 0.0
            reasons = []

            # Site type matching
            suitable_for = template.metadata.get('suitable_for', [])
            if any(site_type in suitable.lower() for suitable in suitable_for):
                confidence += 0.4
                reasons.append(f"Matches site type: {site_type}")

            # Staff count matching
            typical_staff = template.metadata.get('typical_staff_count', '')
            if typical_staff and staff_count:
                # Parse staff count ranges (e.g., "5-20", "20-100")
                if '-' in typical_staff:
                    try:
                        min_staff, max_staff = map(int, typical_staff.split('-'))
                        if min_staff <= staff_count <= max_staff:
                            confidence += 0.3
                            reasons.append(f"Staff count ({staff_count}) fits range {typical_staff}")
                    except ValueError:
                        pass

            # Operating hours matching
            if '24' in operating_hours or 'round the clock' in operating_hours:
                # Check if template supports 24/7 operations
                config = template.config
                bus_units = config.get('business_units', [])
                if bus_units:
                    bu_prefs = bus_units[0].get('bupreferences', {})
                    if (bu_prefs.get('siteopentime') == '00:00' and
                        bu_prefs.get('siteclosetime') == '23:59'):
                        confidence += 0.2
                        reasons.append("Supports 24/7 operations")

            # Add base score for all templates
            confidence += 0.1

            if confidence > 0.2:  # Only include templates with reasonable confidence
                recommendations.append({
                    'template': template.to_dict(),
                    'confidence': confidence,
                    'reasons': reasons,
                    'setup_time_minutes': template.metadata.get('setup_time_minutes', 30)
                })

        # Sort by confidence score
        recommendations.sort(key=lambda x: x['confidence'], reverse=True)

        return recommendations

    def apply_template(self, template_id: str, customizations: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Apply a configuration template with optional customizations

        Args:
            template_id: ID of the template to apply
            customizations: Dictionary of customizations to apply

        Returns:
            Applied configuration ready for system setup
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Start with base template config
        applied_config = template.config.copy()

        # Apply customizations if provided
        if customizations:
            applied_config = self._merge_customizations(applied_config, customizations)

        return {
            'template_id': template_id,
            'template_name': template.name,
            'applied_config': applied_config,
            'metadata': template.metadata,
            'customizations_applied': bool(customizations)
        }

    def _merge_customizations(self, base_config: Dict[str, Any],
                            customizations: Dict[str, Any]) -> Dict[str, Any]:
        """Merge customizations into base configuration"""
        import copy
        result = copy.deepcopy(base_config)

        # Simple merge for now - can be enhanced for complex merging logic
        for key, value in customizations.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key].update(value)
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                result[key].extend(value)
            else:
                result[key] = value

        return result

    def validate_template_compatibility(self, template_id: str,
                                      client_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if a template is compatible with client constraints

        Args:
            template_id: Template to validate
            client_constraints: Client-specific constraints and limitations

        Returns:
            Validation result with compatibility status and issues
        """
        template = self.get_template(template_id)
        if not template:
            return {'compatible': False, 'error': f'Template {template_id} not found'}

        issues = []
        warnings = []

        # Check device limits
        max_devices = client_constraints.get('max_devices', float('inf'))
        template_devices = template.metadata.get('recommended_devices', 1)
        if template_devices > max_devices:
            issues.append(f"Template requires {template_devices} devices, client limit is {max_devices}")

        # Check staff limits
        max_staff = client_constraints.get('max_staff', float('inf'))
        template_staff_range = template.metadata.get('typical_staff_count', '')
        if template_staff_range and '-' in template_staff_range:
            try:
                min_staff, template_max_staff = map(int, template_staff_range.split('-'))
                if min_staff > max_staff:
                    issues.append(f"Template requires minimum {min_staff} staff, client limit is {max_staff}")
                elif template_max_staff > max_staff:
                    warnings.append(f"Template optimized for up to {template_max_staff} staff, client limit is {max_staff}")
            except ValueError:
                pass

        # Check feature requirements
        required_features = template.metadata.get('required_features', [])
        client_features = client_constraints.get('available_features', [])
        missing_features = [f for f in required_features if f not in client_features]
        if missing_features:
            issues.append(f"Missing required features: {', '.join(missing_features)}")

        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'confidence': 1.0 - (len(issues) * 0.5) - (len(warnings) * 0.1)
        }

    def apply_template_to_tenant(self, template_id: str, client, user,
                               customizations: Dict[str, Any] = None,
                               dry_run: bool = True) -> Dict[str, Any]:
        """
        Apply template configuration directly to tenant database

        Args:
            template_id: Template to apply
            client: Client/tenant to apply to
            user: User performing the application
            customizations: Optional customizations
            dry_run: Whether to perform actual database changes

        Returns:
            Application result with created objects and metadata
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Apply customizations
        config = template.config.copy()
        if customizations:
            config = self._merge_customizations(config, customizations)

        result = {
            'template_id': template_id,
            'template_name': template.name,
            'dry_run': dry_run,
            'created_objects': {
                'business_units': [],
                'shifts': [],
                'type_assists': []
            },
            'errors': [],
            'warnings': [],
            'applied_at': timezone.now().isoformat() if not dry_run else None
        }

        try:
            from django.db import transaction
            from apps.onboarding.models import Bt, Shift, TypeAssist

            if not dry_run:
                with transaction.atomic():
                    # Create TypeAssist objects first (they're referenced by other objects)
                    type_assists_map = {}
                    for ta_config in config.get('type_assists', []):
                        try:
                            ta = TypeAssist.objects.create(
                                tacode=ta_config['tacode'],
                                taname=ta_config['taname'],
                                client=client,
                                enable=ta_config.get('enable', True)
                            )
                            type_assists_map[ta_config['tacode']] = ta
                            result['created_objects']['type_assists'].append({
                                'id': ta.id,
                                'tacode': ta.tacode,
                                'taname': ta.taname
                            })
                        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                            result['errors'].append(f"Failed to create TypeAssist {ta_config['tacode']}: {str(e)}")

                    # Create Business Units
                    business_units_map = {}
                    for bu_config in config.get('business_units', []):
                        try:
                            # Get identifier if specified
                            identifier = None
                            if 'identifier_code' in bu_config:
                                identifier = type_assists_map.get(bu_config['identifier_code'])

                            # Get butype if specified
                            butype = None
                            if 'butype_code' in bu_config:
                                butype = type_assists_map.get(bu_config['butype_code'])

                            bu = Bt.objects.create(
                                buname=bu_config['buname'],
                                bucode=bu_config['bucode'],
                                bupreferences=bu_config.get('bupreferences', {}),
                                identifier=identifier,
                                butype=butype,
                                enable=bu_config.get('enable', True),
                                gpsenable=bu_config.get('gpsenable', False),
                                enablesleepingguard=bu_config.get('enablesleepingguard', False),
                                iswarehouse=bu_config.get('iswarehouse', False),
                                deviceevent=bu_config.get('deviceevent', False),
                                skipsiteaudit=bu_config.get('skipsiteaudit', False),
                                pdist=bu_config.get('permissibledistance', 0.0)
                            )
                            business_units_map[bu_config['bucode']] = bu
                            result['created_objects']['business_units'].append({
                                'id': bu.id,
                                'bucode': bu.bucode,
                                'buname': bu.buname
                            })
                        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                            result['errors'].append(f"Failed to create Business Unit {bu_config['bucode']}: {str(e)}")

                    # Create Shifts
                    for shift_config in config.get('shifts', []):
                        try:
                            # Get designation if specified
                            designation = None
                            if 'designation_code' in shift_config:
                                designation = type_assists_map.get(shift_config['designation_code'])

                            # Get default BU (first one created)
                            bu = list(business_units_map.values())[0] if business_units_map else None

                            shift = Shift.objects.create(
                                shiftname=shift_config['shiftname'],
                                starttime=shift_config['starttime'],
                                endtime=shift_config['endtime'],
                                peoplecount=shift_config.get('peoplecount', 1),
                                captchafreq=shift_config.get('captchafreq', 30),
                                nightshiftappicable=shift_config.get('nightshiftappicable', False),
                                enable=shift_config.get('enable', True),
                                bu=bu,
                                client=client,
                                designation=designation
                            )
                            result['created_objects']['shifts'].append({
                                'id': shift.id,
                                'shiftname': shift.shiftname,
                                'starttime': str(shift.starttime),
                                'endtime': str(shift.endtime)
                            })
                        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                            result['errors'].append(f"Failed to create Shift {shift_config['shiftname']}: {str(e)}")

                logger.info(f"Applied template {template_id} to client {client.id}")

            else:
                # Dry run - just validate configuration
                result['validation'] = self.validate_template_compatibility(
                    template_id, {'max_devices': 1000, 'max_staff': 1000}
                )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            result['errors'].append(f"Template application failed: {str(e)}")
            logger.error(f"Template application error: {str(e)}")

        return result

    def get_template_analytics(self) -> Dict[str, Any]:
        """Get analytics about template usage and performance"""
        # This would integrate with actual usage data in production
        analytics = {
            'total_templates': len(self._templates),
            'templates_by_complexity': {},
            'average_setup_time': 0,
            'most_popular_templates': [],
            'industry_coverage': set()
        }

        # Calculate complexity breakdown
        for template in self._templates.values():
            complexity = template.metadata.get('complexity', 'medium')
            analytics['templates_by_complexity'][complexity] = \
                analytics['templates_by_complexity'].get(complexity, 0) + 1

            # Add to industry coverage
            suitable_for = template.metadata.get('suitable_for', [])
            analytics['industry_coverage'].update(suitable_for)

        # Calculate average setup time
        total_time = sum(
            template.metadata.get('setup_time_minutes', 30)
            for template in self._templates.values()
        )
        analytics['average_setup_time'] = total_time / len(self._templates)

        # Convert set to list for JSON serialization
        analytics['industry_coverage'] = list(analytics['industry_coverage'])

        return analytics

    def create_custom_template(self, name: str, description: str,
                             base_template_id: str, customizations: Dict[str, Any],
                             user) -> str:
        """
        Create a custom template based on an existing template

        Args:
            name: Name for the custom template
            description: Description of the custom template
            base_template_id: Base template to customize
            customizations: Customizations to apply
            user: User creating the template

        Returns:
            ID of the created custom template
        """
        base_template = self.get_template(base_template_id)
        if not base_template:
            raise ValueError(f"Base template {base_template_id} not found")

        # Generate unique ID for custom template
        import uuid
        custom_id = f"custom_{str(uuid.uuid4())[:8]}"

        # Apply customizations to base config
        custom_config = self._merge_customizations(base_template.config, customizations)

        # Create custom template
        custom_template = ConfigurationTemplate(
            template_id=custom_id,
            name=name,
            description=description,
            config=custom_config,
            metadata={
                **base_template.metadata,
                'custom': True,
                'base_template': base_template_id,
                'created_by': user.email if hasattr(user, 'email') else str(user),
                'created_at': timezone.now().isoformat(),
                'complexity': 'custom'
            }
        )

        # Store custom template (in production, this would go to database)
        self._templates[custom_id] = custom_template

        logger.info(f"Created custom template {custom_id} based on {base_template_id}")
        return custom_id

    def get_quick_start_recommendations(self, site_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get intelligent quick-start recommendations based on minimal site information

        Args:
            site_info: Basic site information (industry, size, etc.)

        Returns:
            Comprehensive recommendations for rapid onboarding
        """
        recommendations = {
            'primary_template': None,
            'alternative_templates': [],
            'customization_suggestions': [],
            'estimated_completion_time': 30,
            'confidence_score': 0.0,
            'next_steps': []
        }

        # Extract key information
        industry = site_info.get('industry', '').lower()
        size = site_info.get('size', '').lower()
        operating_hours = site_info.get('operating_hours', '').lower()
        security_level = site_info.get('security_level', 'medium').lower()

        # Find best matching template
        context = {
            'site_type': industry,
            'operating_hours': operating_hours,
            'security_level': security_level
        }

        # Add staff count estimate based on size
        size_to_staff = {
            'small': 10,
            'medium': 25,
            'large': 75,
            'enterprise': 200
        }
        context['staff_count'] = size_to_staff.get(size, 25)

        template_recommendations = self.recommend_templates(context)

        if template_recommendations:
            primary = template_recommendations[0]
            recommendations['primary_template'] = primary['template']
            recommendations['confidence_score'] = primary['confidence']
            recommendations['estimated_completion_time'] = primary['setup_time_minutes']

            # Add alternatives
            recommendations['alternative_templates'] = [
                rec['template'] for rec in template_recommendations[1:3]
            ]

            # Generate customization suggestions
            recommendations['customization_suggestions'] = self._generate_customization_suggestions(
                primary['template'], site_info
            )

            # Generate next steps
            recommendations['next_steps'] = self._generate_next_steps(
                primary['template'], site_info
            )

        return recommendations

    def _generate_customization_suggestions(self, template: Dict[str, Any],
                                          site_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate smart customization suggestions"""
        suggestions = []

        # Size-based customizations
        size = site_info.get('size', '').lower()
        if size == 'small':
            suggestions.append({
                'type': 'staff_reduction',
                'title': 'Reduce staff counts for small operation',
                'description': 'Consider reducing shift personnel by 30-50% for smaller facilities',
                'impact': 'cost_reduction'
            })
        elif size == 'large':
            suggestions.append({
                'type': 'staff_increase',
                'title': 'Increase staff counts for large operation',
                'description': 'Consider increasing shift personnel by 50-100% for larger facilities',
                'impact': 'coverage_improvement'
            })

        # Security level customizations
        security_level = site_info.get('security_level', 'medium').lower()
        if security_level == 'high':
            suggestions.append({
                'type': 'security_enhancement',
                'title': 'Enable enhanced security features',
                'description': 'Enable GPS tracking, sleeping guard detection, and frequent check-ins',
                'impact': 'security_improvement'
            })
        elif security_level == 'low':
            suggestions.append({
                'type': 'security_simplification',
                'title': 'Simplify security requirements',
                'description': 'Disable advanced security features to reduce complexity',
                'impact': 'simplification'
            })

        # Industry-specific suggestions
        industry = site_info.get('industry', '').lower()
        if 'retail' in industry:
            suggestions.append({
                'type': 'customer_facing',
                'title': 'Enable customer-facing features',
                'description': 'Configure for customer interaction and point-of-sale security',
                'impact': 'customer_experience'
            })

        return suggestions

    def _generate_next_steps(self, template: Dict[str, Any],
                           site_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate actionable next steps for template implementation"""
        steps = [
            {
                'step': 1,
                'title': 'Review Template Configuration',
                'description': 'Review the generated configuration and make any necessary adjustments',
                'estimated_time': '5 minutes'
            },
            {
                'step': 2,
                'title': 'Apply Configuration',
                'description': 'Apply the template configuration to your system',
                'estimated_time': '2 minutes'
            },
            {
                'step': 3,
                'title': 'Add Users and Devices',
                'description': 'Import your users and register devices',
                'estimated_time': '10-30 minutes'
            },
            {
                'step': 4,
                'title': 'Test System',
                'description': 'Perform end-to-end testing of your configuration',
                'estimated_time': '15 minutes'
            },
            {
                'step': 5,
                'title': 'Go Live',
                'description': 'Enable the system for production use',
                'estimated_time': '5 minutes'
            }
        ]

        # Add industry-specific steps
        industry = site_info.get('industry', '').lower()
        if 'manufacturing' in industry or 'factory' in industry:
            steps.insert(3, {
                'step': '3a',
                'title': 'Configure Safety Protocols',
                'description': 'Set up manufacturing-specific safety and compliance procedures',
                'estimated_time': '15 minutes'
            })

        return steps

    def get_template_usage_stats(self) -> Dict[str, Any]:
        """Get template usage statistics (would integrate with real data in production)"""
        # Placeholder for production implementation
        return {
            'most_used_templates': [
                {'template_id': 'office_corporate', 'usage_count': 145, 'success_rate': 0.92},
                {'template_id': 'retail_store', 'usage_count': 98, 'success_rate': 0.89},
                {'template_id': 'manufacturing_factory', 'usage_count': 67, 'success_rate': 0.85},
                {'template_id': 'healthcare_hospital', 'usage_count': 43, 'success_rate': 0.91},
                {'template_id': 'datacenter_facility', 'usage_count': 23, 'success_rate': 0.95}
            ],
            'average_setup_time_actual': {
                'office_corporate': 12.3,
                'retail_store': 18.7,
                'manufacturing_factory': 42.1,
                'healthcare_hospital': 51.2,
                'datacenter_facility': 35.8
            },
            'common_customizations': [
                {'type': 'timezone_adjustment', 'frequency': 0.78},
                {'type': 'staff_count_adjustment', 'frequency': 0.65},
                {'type': 'operating_hours_adjustment', 'frequency': 0.45},
                {'type': 'security_level_adjustment', 'frequency': 0.34}
            ],
            'success_factors': [
                'Clear industry match',
                'Appropriate staff sizing',
                'Correct security level',
                'Proper timezone configuration'
            ]
        }


# Global service instance
_template_service = None


def get_template_service() -> ConfigurationTemplateService:
    """Get the global configuration template service instance"""
    global _template_service
    if _template_service is None:
        _template_service = ConfigurationTemplateService()
    return _template_service