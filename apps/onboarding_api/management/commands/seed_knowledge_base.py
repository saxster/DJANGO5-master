"""
Management command to seed the knowledge base with facility management best practices
"""

from django.db import transaction
from apps.core_onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk


class Command(BaseCommand):
    help = 'Seed the knowledge base with facility management best practices and SOPs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing knowledge base entries before seeding'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes'
        )

    def handle(self, *args, **options):
        if options['clear_existing'] and not options['dry_run']:
            self.stdout.write("Clearing existing knowledge base entries...")
            AuthoritativeKnowledge.objects.all().delete()

        knowledge_entries = self.get_knowledge_base_data()

        with transaction.atomic():
            created_count = 0

            for entry in knowledge_entries:
                if options['dry_run']:
                    self.stdout.write(f"DRY RUN: Would create knowledge entry '{entry['title']}'")
                    continue

                # Create or update knowledge entry
                knowledge, created = AuthoritativeKnowledge.objects.get_or_create(
                    title=entry['title'],
                    defaults={
                        'knowledge_type': entry['type'],
                        'content': entry['content'],
                        'summary': entry['summary'],
                        'source_reference': entry['source'],
                        'confidence_level': entry['confidence'],
                        'tags': entry['tags'],
                        'is_active': True
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created knowledge entry: {entry['title']}")
                    )

                    # Create chunks for better retrieval
                    self.create_knowledge_chunks(knowledge, entry.get('chunks', []))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Knowledge entry already exists: {entry['title']}")
                    )

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would have created {len(knowledge_entries)} knowledge entries")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} new knowledge entries")
            )

    def create_knowledge_chunks(self, knowledge, chunks):
        """Create knowledge chunks for better retrieval"""
        for i, chunk_content in enumerate(chunks):
            AuthoritativeKnowledgeChunk.objects.create(
                knowledge=knowledge,
                sequence_number=i + 1,
                chunk_type='paragraph',
                content=chunk_content
            )

    def get_knowledge_base_data(self):
        """Return facility management knowledge base data"""
        return [
            {
                'title': 'Facility Security Best Practices',
                'type': 'security_policy',
                'content': '''Comprehensive security protocols for facility management:

1. ACCESS CONTROL
- All personnel must use assigned access cards
- Visitor registration required at main reception
- Escort policy mandatory for non-employees in restricted areas
- Access logs reviewed daily by security team

2. SHIFT HANDOVER PROCEDURES
- Minimum 15-minute overlap between shifts
- Written handover log must include all incidents
- Security walkthrough required at shift change
- Emergency contact verification

3. INCIDENT RESPONSE
- Immediate supervisor notification for all incidents
- Security incident log within 30 minutes
- Photo documentation when safe to do so
- Police contact for criminal activities

4. SURVEILLANCE SYSTEMS
- CCTV monitoring during all operational hours
- Recording retention minimum 30 days
- Regular equipment maintenance checks
- Privacy compliance in common areas''',
                'summary': 'Essential security protocols including access control, shift procedures, incident response, and surveillance management for facility operations.',
                'source': 'Facility Management Security Standards v2.1',
                'confidence': 'high',
                'tags': ['security', 'access_control', 'incident_response', 'surveillance'],
                'chunks': [
                    'All personnel must use assigned access cards. Visitor registration required at main reception.',
                    'Minimum 15-minute overlap between shifts required with written handover logs.',
                    'Immediate supervisor notification required for all incidents with security log within 30 minutes.',
                    'CCTV monitoring required during operational hours with 30-day retention minimum.'
                ]
            },
            {
                'title': 'Shift Scheduling and People Management',
                'type': 'operational_procedure',
                'content': '''Standard Operating Procedures for shift management:

1. SHIFT PLANNING
- Minimum staffing levels based on facility size and risk assessment
- 24/7 coverage for high-security facilities
- Holiday and weekend coverage planning 30 days in advance
- Cross-training requirements for critical positions

2. PEOPLE COUNTING AND CAPACITY
- Maximum occupancy limits per area enforced
- Real-time headcount monitoring systems
- Emergency evacuation capacity planning
- Peak hours staffing adjustments

3. STAFF SCHEDULING
- 8-hour standard shifts with optional 12-hour for coverage
- Mandatory rest periods between shifts (minimum 8 hours)
- Overtime authorization procedures
- Sick leave and emergency replacement protocols

4. PERFORMANCE MONITORING
- Regular safety compliance checks
- Customer service quality assessments
- Equipment operation competency verification
- Continuous improvement feedback loops''',
                'summary': 'Comprehensive shift scheduling guidelines covering staffing levels, capacity management, staff scheduling, and performance monitoring.',
                'source': 'Operations Management Handbook v3.0',
                'confidence': 'high',
                'tags': ['shift_scheduling', 'staffing', 'capacity_management', 'performance'],
                'chunks': [
                    'Minimum staffing levels based on facility size and risk assessment with 24/7 coverage for high-security facilities.',
                    'Maximum occupancy limits per area enforced with real-time headcount monitoring systems.',
                    '8-hour standard shifts with mandatory 8-hour rest periods between shifts.',
                    'Regular safety compliance checks and performance monitoring required.'
                ]
            },
            {
                'title': 'Business Unit Configuration Standards',
                'type': 'configuration_guideline',
                'content': '''Standards for setting up new business units within facility management systems:

1. ORGANIZATIONAL STRUCTURE
- Clear hierarchy with defined reporting relationships
- Business unit codes following standard naming conventions
- Geographic and functional grouping principles
- Budget center assignments and cost allocation

2. OPERATIONAL PARAMETERS
- Service level agreements definition
- Quality standards and KPI targets
- Resource allocation and capacity limits
- Technology infrastructure requirements

3. COMPLIANCE REQUIREMENTS
- Industry-specific regulatory compliance
- Safety and environmental standards
- Data protection and privacy requirements
- Audit and reporting obligations

4. INTEGRATION STANDARDS
- System integration points and data flows
- Communication protocols and escalation paths
- Vendor management and contract requirements
- Change management procedures''',
                'summary': 'Business unit setup standards covering organizational structure, operational parameters, compliance, and system integration.',
                'source': 'Business Configuration Standards v1.5',
                'confidence': 'high',
                'tags': ['business_unit', 'configuration', 'compliance', 'integration'],
                'chunks': [
                    'Clear hierarchy with defined reporting relationships and standard naming conventions required.',
                    'Service level agreements and quality standards must be defined for each business unit.',
                    'Industry-specific regulatory compliance and safety standards must be met.',
                    'System integration points and communication protocols must be established.'
                ]
            },
            {
                'title': 'Emergency Response Procedures',
                'type': 'emergency_procedure',
                'content': '''Emergency response protocols for facility management:

1. FIRE EMERGENCY
- Activate fire alarm immediately
- Evacuate via nearest safe exit route
- Assemble at designated muster points
- Account for all personnel using roll call
- Coordinate with fire department response

2. MEDICAL EMERGENCY
- Call emergency medical services (911/999)
- Provide first aid if qualified
- Clear access routes for emergency responders
- Document incident details for reports
- Follow up with incident investigation

3. SECURITY THREATS
- Assess threat level and respond appropriately
- Lockdown procedures for active threats
- Communication with law enforcement
- Staff and visitor safety prioritization
- Post-incident counseling resources

4. NATURAL DISASTERS
- Monitor weather alerts and warnings
- Implement business continuity plans
- Secure facility and equipment
- Coordinate with local emergency services
- Recovery and restoration procedures''',
                'summary': 'Emergency response procedures covering fire, medical, security, and natural disaster scenarios.',
                'source': 'Emergency Response Manual v2.2',
                'confidence': 'high',
                'tags': ['emergency', 'fire_safety', 'medical', 'security_threats', 'natural_disasters'],
                'chunks': [
                    'Fire emergencies require immediate alarm activation and evacuation via nearest safe exit.',
                    'Medical emergencies require immediate emergency services contact and first aid provision.',
                    'Security threats require threat assessment and appropriate lockdown procedures.',
                    'Natural disasters require monitoring alerts and implementing business continuity plans.'
                ]
            },
            {
                'title': 'Quality Assurance and Maintenance Standards',
                'type': 'maintenance_procedure',
                'content': '''Quality assurance and preventive maintenance standards:

1. PREVENTIVE MAINTENANCE
- Regular equipment inspection schedules
- Predictive maintenance using condition monitoring
- Spare parts inventory management
- Maintenance record keeping and analysis
- Vendor service contract management

2. QUALITY CONTROL
- Regular facility condition assessments
- Customer satisfaction monitoring
- Service delivery performance metrics
- Continuous improvement initiatives
- Root cause analysis for quality issues

3. SAFETY INSPECTIONS
- Daily safety walks and hazard identification
- Monthly comprehensive safety audits
- Equipment safety certification maintenance
- Personal protective equipment compliance
- Incident investigation and corrective actions

4. ENVIRONMENTAL COMPLIANCE
- Waste management and recycling programs
- Energy efficiency monitoring and optimization
- Environmental impact assessments
- Regulatory compliance tracking
- Sustainability reporting requirements''',
                'summary': 'Quality assurance standards covering preventive maintenance, quality control, safety inspections, and environmental compliance.',
                'source': 'Quality Management System v4.0',
                'confidence': 'high',
                'tags': ['quality_assurance', 'maintenance', 'safety', 'environmental', 'compliance'],
                'chunks': [
                    'Regular equipment inspection and predictive maintenance required with comprehensive record keeping.',
                    'Customer satisfaction monitoring and performance metrics tracking required.',
                    'Daily safety walks and monthly comprehensive safety audits mandatory.',
                    'Environmental compliance tracking and sustainability reporting required.'
                ]
            },
            {
                'title': 'Communication and Reporting Protocols',
                'type': 'communication_protocol',
                'content': '''Communication and reporting standards for facility operations:

1. DAILY REPORTING
- Shift handover reports with all significant events
- Incident logs with detailed descriptions
- Equipment status and maintenance needs
- Visitor and contractor activity summaries
- Weather and environmental conditions

2. ESCALATION PROCEDURES
- Clear escalation matrix for different incident types
- Response time requirements by severity level
- Authority levels for decision making
- Communication channels and backup methods
- Documentation requirements for all escalations

3. STAKEHOLDER COMMUNICATION
- Regular status updates to management
- Client communication protocols and schedules
- Vendor coordination and performance reporting
- Emergency communication procedures
- Public relations and media handling guidelines

4. PERFORMANCE REPORTING
- Key performance indicators (KPI) tracking
- Monthly operational performance summaries
- Budget variance reporting and analysis
- Compliance status reports
- Continuous improvement recommendations''',
                'summary': 'Communication protocols covering daily reporting, escalation procedures, stakeholder communication, and performance reporting.',
                'source': 'Communication Standards Guide v2.0',
                'confidence': 'high',
                'tags': ['communication', 'reporting', 'escalation', 'stakeholders', 'performance'],
                'chunks': [
                    'Daily shift handover reports required with all significant events documented.',
                    'Clear escalation matrix required for different incident types with defined response times.',
                    'Regular stakeholder communication including management updates and client protocols.',
                    'Monthly KPI tracking and performance summaries required for all operations.'
                ]
            }
        ]