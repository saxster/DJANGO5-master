"""
SLA Breach Predictor - XGBoost Binary Classifier.

Predicts if ticket/work order will breach SLA in next 2 hours.
Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Target: 40-60% incident prevention rate through proactive alerts.

Follows .claude/rules.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O

@ontology(
    domain="noc",
    purpose="Predict SLA breaches 2 hours in advance for proactive escalation",
    ml_model="XGBoost binary classifier",
    features=["current_age", "priority_level", "assigned_status", "site_workload",
              "historical_avg_resolution", "time_until_deadline", "assignee_workload", "business_hours"],
    target="will_breach_sla (binary 0/1)",
    prediction_window="2 hours",
    criticality="high",
    tags=["noc", "ml", "xgboost", "sla-prediction", "predictive-analytics"]
)
"""

import os
import joblib
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg

logger = logging.getLogger('noc.predictive.sla_breach')

__all__ = ['SLABreachPredictor']


class SLABreachPredictor:
    """
    Predicts SLA breaches 2 hours in advance.

    Features (8):
    1. current_age_minutes - How long ticket has been open
    2. priority_level - 1-5 priority score
    3. assigned_status - 1 if assigned, 0 if not
    4. site_current_workload - Concurrent open tickets at site
    5. historical_avg_resolution_time - Historical avg for this type
    6. time_until_sla_deadline_minutes - Time remaining until SLA breach
    7. assignee_current_workload - Tickets assigned to same person
    8. business_hours - 1 if during business hours (8am-6pm)
    """

    MODEL_PATH = Path(settings.BASE_DIR) / 'ml_models' / 'sla_breach_predictor.pkl'
    PREDICTION_WINDOW_HOURS = 2
    BREACH_PROBABILITY_THRESHOLD = 0.6  # 60% confidence to create alert

    @classmethod
    def predict_breach(cls, ticket) -> Tuple[float, Dict[str, Any]]:
        """
        Predict if ticket will breach SLA in next 2 hours.

        Args:
            ticket: Ticket or WorkOrder instance

        Returns:
            (probability, features) - Probability 0.0-1.0 and feature dict

        Raises:
            FileNotFoundError: If model file not found
            ValueError: If ticket data invalid
        """
        if not cls._has_sla_deadline(ticket):
            return 0.0, {}

        features = cls._extract_features(ticket)

        if not cls.MODEL_PATH.exists():
            logger.warning(f"SLA breach model not found at {cls.MODEL_PATH}, using heuristic")
            return cls._heuristic_prediction(features), features

        try:
            model = joblib.load(cls.MODEL_PATH)
            feature_vector = cls._features_to_vector(features)
            probability = model.predict_proba([feature_vector])[0][1]  # Probability of class 1 (breach)
            return float(probability), features
        except (OSError, ValueError) as e:
            logger.error(f"Error loading SLA breach model: {e}", exc_info=True)
            return cls._heuristic_prediction(features), features

    @classmethod
    def _extract_features(cls, ticket) -> Dict[str, Any]:
        """Extract 8 features from ticket."""
        from apps.y_helpdesk.models import Ticket

        now = timezone.now()
        ticket_age = (now - ticket.cdtz).total_seconds() / 60.0  # minutes

        # Feature 1: Current age
        current_age_minutes = ticket_age

        # Feature 2: Priority level (1-5)
        priority_map = {'LOW': 1, 'MEDIUM': 2, 'NORMAL': 3, 'HIGH': 4, 'CRITICAL': 5}
        priority_level = priority_map.get(ticket.priority, 3)

        # Feature 3: Assigned status
        assigned_status = 1 if ticket.assignee else 0

        # Feature 4: Site current workload
        site_current_workload = Ticket.objects.filter(
            bu=ticket.bu,
            status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
            tenant=ticket.tenant
        ).count()

        # Feature 5: Historical avg resolution time
        historical_avg_resolution_time = Ticket.objects.filter(
            priority=ticket.priority,
            status='CLOSED',
            tenant=ticket.tenant
        ).aggregate(
            avg_resolution=Avg('resolution_time_minutes')
        )['avg_resolution'] or 240.0  # Default 4 hours

        # Feature 6: Time until SLA deadline
        sla_deadline = cls._get_sla_deadline(ticket)
        time_until_sla_deadline_minutes = (sla_deadline - now).total_seconds() / 60.0 if sla_deadline else 999999.0

        # Feature 7: Assignee current workload
        assignee_current_workload = 0
        if ticket.assignee:
            assignee_current_workload = Ticket.objects.filter(
                assignee=ticket.assignee,
                status__in=['ASSIGNED', 'IN_PROGRESS'],
                tenant=ticket.tenant
            ).count()

        # Feature 8: Business hours (8am-6pm local time)
        business_hours = 1 if 8 <= now.hour < 18 else 0

        return {
            'current_age_minutes': current_age_minutes,
            'priority_level': priority_level,
            'assigned_status': assigned_status,
            'site_current_workload': site_current_workload,
            'historical_avg_resolution_time': historical_avg_resolution_time,
            'time_until_sla_deadline_minutes': time_until_sla_deadline_minutes,
            'assignee_current_workload': assignee_current_workload,
            'business_hours': business_hours,
        }

    @classmethod
    def _features_to_vector(cls, features: Dict[str, Any]) -> list:
        """Convert feature dict to ordered vector for model input."""
        return [
            features['current_age_minutes'],
            features['priority_level'],
            features['assigned_status'],
            features['site_current_workload'],
            features['historical_avg_resolution_time'],
            features['time_until_sla_deadline_minutes'],
            features['assignee_current_workload'],
            features['business_hours'],
        ]

    @classmethod
    def _heuristic_prediction(cls, features: Dict[str, Any]) -> float:
        """
        Heuristic prediction when ML model unavailable.

        Logic:
        - If time_until_deadline < current_age: Very likely breach (0.9)
        - If unassigned + high priority: Likely breach (0.7)
        - If assignee overloaded (>5 tickets): Medium risk (0.6)
        - Otherwise: Low risk (0.3)
        """
        time_remaining = features['time_until_sla_deadline_minutes']
        current_age = features['current_age_minutes']
        assigned = features['assigned_status']
        priority = features['priority_level']
        assignee_workload = features['assignee_current_workload']

        if time_remaining < current_age:
            return 0.9  # Already past halfway to deadline
        if not assigned and priority >= 4:
            return 0.7  # High priority but unassigned
        if assignee_workload > 5:
            return 0.6  # Assignee overloaded
        if time_remaining < 120:  # Less than 2 hours remaining
            return 0.75

        return 0.3  # Low risk

    @classmethod
    def _has_sla_deadline(cls, ticket) -> bool:
        """Check if ticket has SLA deadline configured."""
        return hasattr(ticket, 'sla_policy') and ticket.sla_policy is not None

    @classmethod
    def _get_sla_deadline(cls, ticket) -> Optional[timezone.datetime]:
        """Get SLA deadline for ticket."""
        if not cls._has_sla_deadline(ticket):
            return None

        # Try to get from ticket directly
        if hasattr(ticket, 'sla_deadline') and ticket.sla_deadline:
            return ticket.sla_deadline

        # Calculate from SLA policy
        if ticket.sla_policy and hasattr(ticket.sla_policy, 'response_time_minutes'):
            response_time = timedelta(minutes=ticket.sla_policy.response_time_minutes)
            return ticket.cdtz + response_time

        return None

    @classmethod
    def should_alert(cls, probability: float) -> bool:
        """Check if probability exceeds threshold for alerting."""
        return probability >= cls.BREACH_PROBABILITY_THRESHOLD
