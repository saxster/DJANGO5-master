"""
Data import on-ramps integration for Conversational Onboarding.

Integrates existing CSV/Excel import flows into conversational recommendations
to shorten decision loops and accelerate onboarding completion.
"""
import logging

from django.urls import reverse

logger = logging.getLogger(__name__)


class ImportRecommendationEngine:
    """
    Engine for generating import recommendations during conversations
    """

    def __init__(self):
        self.import_templates = self._load_import_templates()
        self.context_triggers = self._define_context_triggers()

    def _load_import_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load available import templates and their metadata"""
        return {
            'users': {
                'name': 'User Import',
                'description': 'Import users, roles, and assignments from CSV/Excel',
                'url_name': 'onboarding:import',
                'template_file': 'users_import_template.xlsx',
                'required_columns': ['email', 'name', 'role'],
                'optional_columns': ['phone', 'department', 'shift', 'permissions'],
                'benefits': [
                    'Bulk user creation (faster than manual entry)',
                    'Consistent role assignments',
                    'Reduced setup time by 70%'
                ],
                'estimated_time_savings': '15-30 minutes for 20+ users'
            },
            'locations': {
                'name': 'Location Import',
                'description': 'Import business units, sites, and locations from CSV/Excel',
                'url_name': 'onboarding:import',
                'template_file': 'locations_import_template.xlsx',
                'required_columns': ['location_code', 'location_name', 'address'],
                'optional_columns': ['gps_coordinates', 'timezone', 'operating_hours'],
                'benefits': [
                    'Bulk location setup',
                    'GPS coordinates integration',
                    'Hierarchical location structures'
                ],
                'estimated_time_savings': '10-20 minutes for 10+ locations'
            },
            'shifts': {
                'name': 'Shift Schedule Import',
                'description': 'Import shift schedules and patterns from CSV/Excel',
                'url_name': 'onboarding:import',
                'template_file': 'shifts_import_template.xlsx',
                'required_columns': ['shift_name', 'start_time', 'end_time'],
                'optional_columns': ['people_count', 'designation', 'captcha_frequency'],
                'benefits': [
                    'Complex shift pattern setup',
                    'Multi-location shift coordination',
                    'Staff allocation planning'
                ],
                'estimated_time_savings': '5-15 minutes for complex schedules'
            },
            'devices': {
                'name': 'Device Import',
                'description': 'Import devices, handsets, and equipment from CSV/Excel',
                'url_name': 'onboarding:import',
                'template_file': 'devices_import_template.xlsx',
                'required_columns': ['device_name', 'model', 'imei'],
                'optional_columns': ['phone_number', 'assigned_user', 'location'],
                'benefits': [
                    'Bulk device registration',
                    'IMEI validation and tracking',
                    'User assignment automation'
                ],
                'estimated_time_savings': '10-25 minutes for 10+ devices'
            }
        }

    def _define_context_triggers(self) -> Dict[str, List[str]]:
        """Define conversation contexts that should trigger import suggestions"""
        return {
            'users': [
                'multiple users',
                'staff list',
                'employee roster',
                'team members',
                'user accounts',
                'many people',
                'bulk users',
                'existing staff'
            ],
            'locations': [
                'multiple sites',
                'various locations',
                'branch offices',
                'different buildings',
                'site list',
                'location data',
                'multiple facilities'
            ],
            'shifts': [
                'complex schedules',
                'multiple shifts',
                'shift patterns',
                'rotating schedules',
                'different timings',
                'shift management',
                'schedule import'
            ],
            'devices': [
                'many devices',
                'device list',
                'handset inventory',
                'equipment setup',
                'device registration',
                'bulk devices',
                'existing devices'
            ]
        }

    def analyze_conversation_for_import_opportunities(
        self,
        user_input: str,
        context: Dict[str, Any],
        session_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze conversation context to identify import opportunities

        Args:
            user_input: Latest user input
            context: Conversation context
            session_data: Session data collected so far

        Returns:
            List of import recommendations
        """
        recommendations = []

        # Combine all text for analysis
        analysis_text = ' '.join([
            user_input.lower(),
            str(context).lower(),
            str(session_data).lower()
        ])

        # Check for import triggers
        for import_type, triggers in self.context_triggers.items():
            trigger_matches = sum(1 for trigger in triggers if trigger in analysis_text)

            if trigger_matches >= 2:  # Multiple trigger words found
                template = self.import_templates[import_type]

                recommendation = {
                    'type': 'import_suggestion',
                    'import_type': import_type,
                    'confidence': min(0.9, trigger_matches * 0.3),
                    'title': f"Import {template['name']}",
                    'description': template['description'],
                    'benefits': template['benefits'],
                    'estimated_time_savings': template['estimated_time_savings'],
                    'import_url': reverse('onboarding:import'),  # Existing import URL
                    'template_download_url': f'/static/templates/{template["template_file"]}',
                    'required_columns': template['required_columns'],
                    'optional_columns': template['optional_columns'],
                    'trigger_reasons': [trigger for trigger in triggers if trigger in analysis_text]
                }

                recommendations.append(recommendation)

        # Sort by confidence and return top 3
        recommendations.sort(key=lambda x: x['confidence'], reverse=True)
        return recommendations[:3]

    def generate_import_template_content(self, import_type: str) -> Dict[str, Any]:
        """Generate content for import templates"""
        if import_type not in self.import_templates:
            raise ValueError(f"Unknown import type: {import_type}")

        template = self.import_templates[import_type]

        # Generate sample data based on import type
        sample_data = self._generate_sample_data(import_type)

        return {
            'import_type': import_type,
            'template_name': template['name'],
            'description': template['description'],
            'headers': template['required_columns'] + template['optional_columns'],
            'sample_data': sample_data,
            'instructions': self._generate_import_instructions(import_type),
            'validation_rules': self._get_validation_rules(import_type)
        }

    def _generate_sample_data(self, import_type: str) -> List[List[str]]:
        """Generate sample data for import templates"""
        samples = {
            'users': [
                ['john.doe@company.com', 'John Doe', 'Security Guard', '+1234567890', 'Security', 'Day Shift', 'standard'],
                ['jane.smith@company.com', 'Jane Smith', 'Supervisor', '+1234567891', 'Operations', 'Day Shift', 'supervisor'],
                ['bob.wilson@company.com', 'Bob Wilson', 'Night Guard', '+1234567892', 'Security', 'Night Shift', 'standard']
            ],
            'locations': [
                ['MAIN001', 'Main Entrance', '123 Business Ave, City, State 12345', '40.7128,-74.0060', 'EST', '24/7'],
                ['PARK001', 'Parking Lot A', '123 Business Ave - Parking, City, State 12345', '40.7129,-74.0061', 'EST', '24/7'],
                ['OFF001', 'Office Building', '123 Business Ave - Office, City, State 12345', '40.7130,-74.0062', 'EST', '8AM-6PM']
            ],
            'shifts': [
                ['Day Shift', '08:00:00', '16:00:00', '8', 'Security Guard', '30'],
                ['Evening Shift', '16:00:00', '00:00:00', '6', 'Security Guard', '20'],
                ['Night Shift', '00:00:00', '08:00:00', '4', 'Night Guard', '15']
            ],
            'devices': [
                ['Guard Device 1', 'Samsung Galaxy', '123456789012345', '+1234567800', 'john.doe@company.com', 'MAIN001'],
                ['Guard Device 2', 'Samsung Galaxy', '123456789012346', '+1234567801', 'jane.smith@company.com', 'PARK001'],
                ['Supervisor Device', 'iPhone 13', '123456789012347', '+1234567802', 'bob.wilson@company.com', 'OFF001']
            ]
        }

        return samples.get(import_type, [])

    def _generate_import_instructions(self, import_type: str) -> List[str]:
        """Generate step-by-step import instructions"""
        instructions = {
            'users': [
                "1. Download the users import template",
                "2. Fill in user details (email is required and must be unique)",
                "3. Assign roles and permissions based on your security requirements",
                "4. Upload the completed file using the import wizard",
                "5. Review the preview and confirm the import",
                "6. Users will receive email invitations automatically"
            ],
            'locations': [
                "1. Download the locations import template",
                "2. List all your sites and business units",
                "3. Include GPS coordinates for mobile app integration",
                "4. Specify operating hours for each location",
                "5. Upload and preview your location structure",
                "6. Locations will be available immediately after import"
            ],
            'shifts': [
                "1. Download the shift schedules template",
                "2. Define your shift patterns and timing",
                "3. Specify staff counts and roles for each shift",
                "4. Set captcha/check-in frequencies",
                "5. Upload and validate shift configurations",
                "6. Shifts will be ready for staff assignment"
            ],
            'devices': [
                "1. Download the devices import template",
                "2. List all devices with IMEI numbers",
                "3. Assign devices to users and locations",
                "4. Include phone numbers for SMS capabilities",
                "5. Upload and validate device registrations",
                "6. Devices will be ready for app installation"
            ]
        }

        return instructions.get(import_type, [])

    def _get_validation_rules(self, import_type: str) -> Dict[str, Any]:
        """Get validation rules for import types"""
        rules = {
            'users': {
                'email': 'Valid email format, must be unique',
                'name': 'Required, 2-100 characters',
                'role': 'Must match existing role definitions',
                'phone': 'Optional, valid phone format',
                'department': 'Optional, alphanumeric',
                'shift': 'Optional, must match existing shifts',
                'permissions': 'Optional, comma-separated permission codes'
            },
            'locations': {
                'location_code': 'Required, alphanumeric, 3-20 characters, unique',
                'location_name': 'Required, 2-200 characters',
                'address': 'Required, valid address format',
                'gps_coordinates': 'Optional, "latitude,longitude" format',
                'timezone': 'Optional, valid timezone identifier',
                'operating_hours': 'Optional, "HH:MM-HH:MM" or "24/7"'
            },
            'shifts': {
                'shift_name': 'Required, 2-50 characters, unique per location',
                'start_time': 'Required, HH:MM:SS format',
                'end_time': 'Required, HH:MM:SS format',
                'people_count': 'Optional, positive integer',
                'designation': 'Optional, must match existing roles',
                'captcha_frequency': 'Optional, minutes between check-ins'
            },
            'devices': {
                'device_name': 'Required, 2-100 characters',
                'model': 'Required, device model name',
                'imei': 'Required, valid 15-digit IMEI, unique',
                'phone_number': 'Optional, valid phone format',
                'assigned_user': 'Optional, must match existing user email',
                'location': 'Optional, must match existing location code'
            }
        }

        return rules.get(import_type, {})

    def get_import_readiness_assessment(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess readiness for different types of imports based on conversation data

        Args:
            session_data: Current session data and context

        Returns:
            Readiness assessment for each import type
        """
        assessment = {}

        for import_type, template in self.import_templates.items():
            readiness_score = 0.0
            readiness_reasons = []
            blockers = []

            # Analyze session data for readiness indicators
            if import_type == 'users':
                if session_data.get('user_count_mentioned'):
                    count = session_data.get('estimated_user_count', 0)
                    if count > 5:
                        readiness_score += 0.6
                        readiness_reasons.append(f'Large user base mentioned ({count} users)')

                if session_data.get('roles_discussed'):
                    readiness_score += 0.3
                    readiness_reasons.append('Role structure already defined')

                if not session_data.get('basic_config_complete'):
                    blockers.append('Complete basic configuration first')

            elif import_type == 'locations':
                if session_data.get('multiple_sites_mentioned'):
                    readiness_score += 0.7
                    readiness_reasons.append('Multiple sites/locations mentioned')

                if session_data.get('gps_requirements_discussed'):
                    readiness_score += 0.2
                    readiness_reasons.append('GPS requirements clarified')

            elif import_type == 'shifts':
                if session_data.get('complex_scheduling_mentioned'):
                    readiness_score += 0.6
                    readiness_reasons.append('Complex scheduling needs identified')

                if session_data.get('shift_patterns_discussed'):
                    readiness_score += 0.3
                    readiness_reasons.append('Shift patterns already discussed')

            elif import_type == 'devices':
                if session_data.get('device_count_mentioned'):
                    count = session_data.get('estimated_device_count', 0)
                    if count > 3:
                        readiness_score += 0.5
                        readiness_reasons.append(f'Multiple devices mentioned ({count} devices)')

                if session_data.get('mobile_requirements_discussed'):
                    readiness_score += 0.4
                    readiness_reasons.append('Mobile requirements clarified')

            # Determine readiness level
            if readiness_score >= 0.7:
                readiness_level = 'high'
            elif readiness_score >= 0.4:
                readiness_level = 'medium'
            elif readiness_score >= 0.2:
                readiness_level = 'low'
            else:
                readiness_level = 'not_ready'

            assessment[import_type] = {
                'readiness_level': readiness_level,
                'readiness_score': readiness_score,
                'reasons': readiness_reasons,
                'blockers': blockers,
                'template': template
            }

        return assessment

    def generate_contextual_import_suggestion(
        self,
        user_input: str,
        session_data: Dict[str, Any],
        conversation_stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate contextual import suggestion based on conversation flow

        Args:
            user_input: Latest user input
            session_data: Session data so far
            conversation_stage: Current conversation stage

        Returns:
            Import suggestion or None if no good match
        """
        # Get import opportunities
        opportunities = self.analyze_conversation_for_import_opportunities(
            user_input, {}, session_data
        )

        if not opportunities:
            return None

        # Get readiness assessment
        readiness = self.get_import_readiness_assessment(session_data)

        # Find best opportunity
        best_opportunity = None
        best_score = 0.0

        for opportunity in opportunities:
            import_type = opportunity['import_type']
            opp_readiness = readiness.get(import_type, {})

            # Calculate combined score
            combined_score = (
                opportunity['confidence'] * 0.7 +
                opp_readiness.get('readiness_score', 0.0) * 0.3
            )

            if combined_score > best_score and opp_readiness.get('readiness_level') != 'not_ready':
                best_opportunity = opportunity
                best_score = combined_score

        if best_opportunity and best_score > 0.5:
            # Enhance with readiness info
            import_type = best_opportunity['import_type']
            readiness_info = readiness[import_type]

            return {
                **best_opportunity,
                'readiness_assessment': readiness_info,
                'contextual_message': self._generate_contextual_message(
                    import_type, user_input, session_data
                ),
                'quick_start_available': readiness_info['readiness_level'] in ['high', 'medium']
            }

        return None

    def _generate_contextual_message(
        self,
        import_type: str,
        user_input: str,
        session_data: Dict[str, Any]
    ) -> str:
        """Generate contextual message for import suggestion"""
        messages = {
            'users': "Since you mentioned having multiple users, would you like to import your user list from a spreadsheet? This can save 15-30 minutes compared to manual entry.",
            'locations': "I notice you have multiple locations. Would you like to import your site information from a CSV file? This includes GPS coordinates and operating hours.",
            'shifts': "Your scheduling sounds complex. Would you like to import your shift patterns from a spreadsheet? This can handle rotating schedules and multiple time zones.",
            'devices': "With multiple devices to set up, would you like to import your device inventory? This includes IMEI registration and user assignments."
        }

        return messages.get(import_type, f"Would you like to import your {import_type} data to speed up setup?")


class ImportFlowIntegrator:
    """
    Integrates import recommendations into conversation flow
    """

    def __init__(self):
        self.recommendation_engine = ImportRecommendationEngine()

    def enhance_llm_response_with_imports(
        self,
        base_response: Dict[str, Any],
        user_input: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance LLM response with relevant import suggestions

        Args:
            base_response: Base LLM response
            user_input: User input that triggered response
            session_data: Current session data

        Returns:
            Enhanced response with import suggestions
        """
        enhanced_response = base_response.copy()

        # Get import suggestion
        import_suggestion = self.recommendation_engine.generate_contextual_import_suggestion(
            user_input, session_data, session_data.get('current_stage', 'initial')
        )

        if import_suggestion:
            # Add import suggestion to recommendations
            if 'recommendations' not in enhanced_response:
                enhanced_response['recommendations'] = []

            # Insert import suggestion at appropriate position
            enhanced_response['recommendations'].insert(0, {
                'type': 'import_suggestion',
                'priority': 'high',
                'suggestion': import_suggestion,
                'action_required': True,
                'estimated_impact': 'Significant time savings for bulk data entry'
            })

            # Add to next steps
            if 'next_steps' not in enhanced_response:
                enhanced_response['next_steps'] = []

            enhanced_response['next_steps'].insert(0,
                f"Consider importing {import_suggestion['import_type']} data to accelerate setup"
            )

            # Add import readiness to metadata
            enhanced_response['import_readiness'] = import_suggestion['readiness_assessment']

        return enhanced_response

    def get_import_progress_tracking(self, user, client) -> Dict[str, Any]:
        """
        Track import progress for analytics and recommendations

        Args:
            user: User performing imports
            client: Client/tenant context

        Returns:
            Import progress and analytics data
        """
        # This would integrate with actual import tracking in production
        # For now, return structure for future implementation

        return {
            'completed_imports': {
                'users': {'completed': False, 'count': 0, 'last_import': None},
                'locations': {'completed': False, 'count': 0, 'last_import': None},
                'shifts': {'completed': False, 'count': 0, 'last_import': None},
                'devices': {'completed': False, 'count': 0, 'last_import': None}
            },
            'suggested_next_imports': [],
            'overall_completion_percentage': 0.0,
            'estimated_time_saved': 0,
            'import_success_rate': 1.0
        }


class ConversationalImportRecommender:
    """
    Main service for providing import recommendations during conversations
    """

    def __init__(self):
        self.engine = ImportRecommendationEngine()
        self.integrator = ImportFlowIntegrator()

    def analyze_and_recommend(
        self,
        user_input: str,
        context: Dict[str, Any],
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main entry point for import analysis and recommendations

        Args:
            user_input: Latest user input
            context: Conversation context
            session_data: Session data collected so far

        Returns:
            Import recommendations and analysis
        """
        # Get import opportunities
        opportunities = self.engine.analyze_conversation_for_import_opportunities(
            user_input, context, session_data
        )

        # Get readiness assessment
        readiness = self.engine.get_import_readiness_assessment(session_data)

        # Generate contextual suggestion
        contextual_suggestion = self.engine.generate_contextual_import_suggestion(
            user_input, session_data, session_data.get('current_stage', 'initial')
        )

        return {
            'import_opportunities': opportunities,
            'readiness_assessment': readiness,
            'contextual_suggestion': contextual_suggestion,
            'has_import_ready': any(
                r['readiness_level'] in ['high', 'medium']
                for r in readiness.values()
            ),
            'recommended_import_order': self._get_recommended_import_order(readiness)
        }

    def _get_recommended_import_order(self, readiness: Dict[str, Any]) -> List[str]:
        """Get recommended order for imports based on readiness and dependencies"""
        # Define dependency order (some imports depend on others)
        dependency_order = ['locations', 'users', 'shifts', 'devices']

        # Filter by readiness and maintain dependency order
        ready_imports = [
            import_type for import_type in dependency_order
            if readiness.get(import_type, {}).get('readiness_level') in ['high', 'medium']
        ]

        return ready_imports


# Service factory functions
def get_import_recommendation_engine() -> ImportRecommendationEngine:
    """Get import recommendation engine instance"""
    return ImportRecommendationEngine()


def get_import_flow_integrator() -> ImportFlowIntegrator:
    """Get import flow integrator instance"""
    return ImportFlowIntegrator()


def get_conversational_import_recommender() -> ConversationalImportRecommender:
    """Get main conversational import recommender service"""
    return ConversationalImportRecommender()


# Utility functions for LLM integration
def enhance_conversation_with_import_suggestions(
    llm_response: Dict[str, Any],
    user_input: str,
    session_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Utility function to enhance any LLM response with import suggestions

    Args:
        llm_response: Base LLM response
        user_input: User input
        session_data: Session data

    Returns:
        Enhanced response with import recommendations
    """
    integrator = get_import_flow_integrator()
    return integrator.enhance_llm_response_with_imports(
        llm_response, user_input, session_data
    )


def get_import_suggestions_for_context(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get import suggestions based on conversation context

    Args:
        context: Conversation context and collected data

    Returns:
        List of relevant import suggestions
    """
    recommender = get_conversational_import_recommender()
    result = recommender.analyze_and_recommend(
        user_input=context.get('last_user_input', ''),
        context=context,
        session_data=context.get('session_data', {})
    )

    return result.get('import_opportunities', [])