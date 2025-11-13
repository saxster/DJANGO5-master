"""
Crisis Prevention System - Facade Pattern for Backward Compatibility

This module provides a backward-compatible facade for the refactored crisis prevention system.
The original monolithic CrisisPreventionSystem has been split into 5 focused services:

1. CrisisAssessmentService - Risk assessment and scoring
2. ProfessionalEscalationService - HR/EAP escalation workflows
3. SafetyMonitoringService - Ongoing monitoring for at-risk users
4. SafetyPlanService - Personalized safety plan creation
5. CrisisNotificationService - Notification workflows with privacy compliance

The CrisisPreventionSystem class now delegates to these specialized services,
maintaining 100% backward compatibility with existing code.
"""

import logging
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine

from .crisis_assessment_service import CrisisAssessmentService
from .professional_escalation_service import ProfessionalEscalationService
from .safety_monitoring_service import SafetyMonitoringService
from .safety_plan_service import SafetyPlanService
from .crisis_notification_service import CrisisNotificationService

logger = logging.getLogger('crisis_prevention')


class CrisisPreventionSystem:
    """
    Backward compatibility facade for crisis prevention system

    Delegates to specialized services while maintaining original API
    """

    def __init__(self):
        # Initialize original dependencies
        self.pattern_analyzer = JournalPatternAnalyzer()
        self.escalation_engine = ProgressiveEscalationEngine()

        # Initialize specialized services
        self.assessment_service = CrisisAssessmentService()
        self.escalation_service = ProfessionalEscalationService()
        self.monitoring_service = SafetyMonitoringService()
        self.safety_plan_service = SafetyPlanService()
        self.notification_service = CrisisNotificationService()

        # Expose CRISIS_RISK_FACTORS for backward compatibility
        self.CRISIS_RISK_FACTORS = self.assessment_service.CRISIS_RISK_FACTORS

        # Expose ESCALATION_PROTOCOLS for backward compatibility
        self.ESCALATION_PROTOCOLS = self.escalation_service.ESCALATION_PROTOCOLS

    # ============================================================================
    # PUBLIC API METHODS - Delegate to specialized services
    # ============================================================================

    def assess_crisis_risk(self, user, journal_entry=None, analysis_period_days=14):
        """
        Comprehensive crisis risk assessment for user

        Delegates to: CrisisAssessmentService

        Args:
            user: User object
            journal_entry: Current journal entry (optional)
            analysis_period_days: Period to analyze for risk assessment

        Returns:
            dict: Complete crisis risk assessment with action recommendations
        """
        return self.assessment_service.assess_crisis_risk(user, journal_entry, analysis_period_days)

    def initiate_professional_escalation(self, user, risk_assessment, escalation_level='elevated_risk'):
        """
        Initiate professional escalation based on risk assessment

        Delegates to: ProfessionalEscalationService

        Args:
            user: User object
            risk_assessment: Crisis risk assessment results
            escalation_level: Level of escalation required

        Returns:
            dict: Professional escalation results
        """
        return self.escalation_service.initiate_professional_escalation(user, risk_assessment, escalation_level)

    def monitor_high_risk_users(self, risk_level_threshold='moderate_risk'):
        """
        Monitor all users at or above specified risk level

        Delegates to: SafetyMonitoringService

        Args:
            risk_level_threshold: Minimum risk level to monitor

        Returns:
            dict: Monitoring results and actions taken
        """
        return self.monitoring_service.monitor_high_risk_users(risk_level_threshold)

    def create_safety_plan(self, user, risk_assessment):
        """
        Create personalized safety plan for user at elevated risk

        Delegates to: SafetyPlanService

        Based on Stanley & Brown Safety Planning Intervention (WHO-recommended)

        Args:
            user: User object
            risk_assessment: Crisis risk assessment results

        Returns:
            dict: Safety plan details
        """
        return self.safety_plan_service.create_safety_plan(user, risk_assessment)

    # ============================================================================
    # PRIVATE HELPER METHODS - Delegate to appropriate services
    # ============================================================================

    def _sanitize_risk_factors_for_logging(self, risk_factors: list) -> dict:
        """
        Sanitize risk factors for safe logging

        Delegates to: CrisisNotificationService
        """
        return self.notification_service.sanitize_risk_factors_for_logging(risk_factors)

    def _notify_crisis_team(self, user, risk_assessment):
        """Notify crisis response team - delegates to CrisisNotificationService"""
        return self.notification_service.notify_crisis_team(user, risk_assessment)

    def _notify_hr_wellness_team(self, user, risk_assessment):
        """Notify HR wellness team - delegates to CrisisNotificationService"""
        return self.notification_service.notify_hr_wellness_team(user, risk_assessment)

    def _notify_employee_assistance_program(self, user, risk_assessment):
        """Notify Employee Assistance Program - delegates to CrisisNotificationService"""
        return self.notification_service.notify_employee_assistance_program(user, risk_assessment)

    # ============================================================================
    # ADDITIONAL HELPER METHODS - For tests and backward compatibility
    # ============================================================================

    def _collect_crisis_risk_data(self, user, journal_entry, analysis_period_days):
        """Collect crisis risk data - delegates to CrisisAssessmentService"""
        return self.assessment_service._collect_crisis_risk_data(user, journal_entry, analysis_period_days)

    def _calculate_crisis_risk_score(self, risk_data):
        """Calculate crisis risk score - delegates to CrisisAssessmentService"""
        return self.assessment_service._calculate_crisis_risk_score(risk_data)

    def _identify_active_risk_factors(self, risk_data):
        """Identify active risk factors - delegates to CrisisAssessmentService"""
        return self.assessment_service._identify_active_risk_factors(risk_data)

    def _assess_protective_factors(self, risk_data):
        """Assess protective factors - delegates to CrisisAssessmentService"""
        return self.assessment_service._assess_protective_factors(risk_data)

    def _determine_risk_level(self, crisis_risk_score, active_risk_factors):
        """Determine risk level - delegates to CrisisAssessmentService"""
        return self.assessment_service._determine_risk_level(crisis_risk_score, active_risk_factors)

    def _generate_crisis_action_plan(self, risk_level, active_risk_factors, protective_factors):
        """Generate action plan - delegates to CrisisAssessmentService"""
        return self.assessment_service._generate_crisis_action_plan(risk_level, active_risk_factors, protective_factors)

    def _check_escalation_requirements(self, risk_level, crisis_risk_score):
        """Check escalation requirements - delegates to CrisisAssessmentService"""
        return self.assessment_service._check_escalation_requirements(risk_level, crisis_risk_score)

    def _execute_immediate_actions(self, user, protocol, risk_assessment):
        """Execute immediate actions - delegates to ProfessionalEscalationService"""
        return self.escalation_service._execute_immediate_actions(user, protocol, risk_assessment)

    def _notify_escalation_recipients(self, user, protocol, risk_assessment):
        """Notify escalation recipients - delegates to ProfessionalEscalationService"""
        return self.escalation_service._notify_escalation_recipients(user, protocol, risk_assessment)

    def _initiate_safety_monitoring(self, user, risk_assessment, escalation_level):
        """Initiate safety monitoring - delegates to ProfessionalEscalationService"""
        return self.escalation_service._initiate_safety_monitoring(user, risk_assessment, escalation_level)

    def _create_escalation_record(self, user, risk_assessment, escalation_level, protocol):
        """Create escalation record - delegates to ProfessionalEscalationService"""
        return self.escalation_service._create_escalation_record(user, risk_assessment, escalation_level, protocol)

    def _analyze_content_for_risk_factors(self, recent_entries, current_entry):
        """Analyze content for risk factors - delegates to CrisisAssessmentService"""
        return self.assessment_service._analyze_content_for_risk_factors(recent_entries, current_entry)

    def _extract_mood_trends(self, recent_entries):
        """Extract mood trends - delegates to CrisisAssessmentService"""
        return self.assessment_service._extract_mood_trends(recent_entries)

    def _extract_stress_patterns(self, recent_entries):
        """Extract stress patterns - delegates to CrisisAssessmentService"""
        return self.assessment_service._extract_stress_patterns(recent_entries)

    def _analyze_behavioral_risk_changes(self, user, since_date):
        """Analyze behavioral changes - delegates to CrisisAssessmentService"""
        return self.assessment_service._analyze_behavioral_risk_changes(user, since_date)

    def _analyze_intervention_response_for_risk(self, intervention_history):
        """Analyze intervention response - delegates to CrisisAssessmentService"""
        return self.assessment_service._analyze_intervention_response_for_risk(intervention_history)

    def _deliver_crisis_resources(self, user, risk_assessment):
        """Deliver crisis resources - delegates to ProfessionalEscalationService"""
        return self.escalation_service._deliver_crisis_resources(user, risk_assessment)

    def _trigger_professional_consultation(self, user, risk_assessment):
        """Trigger professional consultation - delegates to ProfessionalEscalationService"""
        return self.escalation_service._trigger_professional_consultation(user, risk_assessment)

    def _initiate_intensive_safety_monitoring(self, user, risk_assessment):
        """Initiate intensive monitoring - delegates to ProfessionalEscalationService"""
        return self.escalation_service._initiate_intensive_safety_monitoring(user, risk_assessment)

    def _intensify_interventions(self, user, risk_assessment):
        """Intensify interventions - delegates to ProfessionalEscalationService"""
        return self.escalation_service._intensify_interventions(user, risk_assessment)

    def _identify_high_risk_users(self, risk_level_threshold):
        """Identify high-risk users - delegates to SafetyMonitoringService"""
        return self.monitoring_service._identify_high_risk_users(risk_level_threshold)

    def _deliver_risk_appropriate_interventions(self, user, risk_assessment):
        """Deliver risk-appropriate interventions - delegates to SafetyMonitoringService"""
        return self.monitoring_service._deliver_risk_appropriate_interventions(user, risk_assessment)

    def _summarize_actions_taken(self, escalation_result, intervention_result):
        """Summarize actions taken - delegates to SafetyMonitoringService"""
        return self.monitoring_service._summarize_actions_taken(escalation_result, intervention_result)

    def _calculate_standard_deviation(self, values):
        """Calculate standard deviation - delegates to CrisisAssessmentService"""
        return self.assessment_service._calculate_standard_deviation(values)

    def _check_escalation_privacy_requirements(self, user, escalation_level):
        """Check privacy requirements - delegates to ProfessionalEscalationService"""
        return self.escalation_service._check_escalation_privacy_requirements(user, escalation_level)

    def _determine_monitoring_requirements(self, risk_level):
        """Determine monitoring requirements - delegates to CrisisAssessmentService"""
        return self.assessment_service._determine_monitoring_requirements(risk_level)

    def _calculate_next_assessment_date(self, risk_level):
        """Calculate next assessment date - delegates to CrisisAssessmentService"""
        return self.assessment_service._calculate_next_assessment_date(risk_level)

    def _check_privacy_compliance(self, user, risk_level):
        """Check privacy compliance - delegates to CrisisAssessmentService"""
        return self.assessment_service._check_privacy_compliance(user, risk_level)

    def _generate_risk_mitigation_strategies(self, active_risk_factors):
        """Generate risk mitigation strategies - delegates to CrisisAssessmentService"""
        return self.assessment_service._generate_risk_mitigation_strategies(active_risk_factors)

    def _generate_protective_factor_strategies(self, protective_factors):
        """Generate protective factor strategies - delegates to CrisisAssessmentService"""
        return self.assessment_service._generate_protective_factor_strategies(protective_factors)

    def _compile_appropriate_professional_resources(self, risk_level):
        """Compile professional resources - delegates to CrisisAssessmentService"""
        return self.assessment_service._compile_appropriate_professional_resources(risk_level)

    def _create_monitoring_plan(self, risk_level, active_risk_factors):
        """Create monitoring plan - delegates to CrisisAssessmentService"""
        return self.assessment_service._create_monitoring_plan(risk_level, active_risk_factors)


# Export main class for backward compatibility
__all__ = ['CrisisPreventionSystem']
