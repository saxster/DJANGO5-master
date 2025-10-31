"""
Experiment framework with A/B testing and multi-armed bandits

This module provides comprehensive experiment management including:
- A/B test creation, management, and analysis
- Statistical significance testing with proper corrections
- Multi-armed bandit optimization
- Policy promotion workflows
- Safety constraint monitoring and automatic pausing
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from apps.onboarding.models import (
    # Experiment,  # TBD - Model not yet implemented
    # ExperimentAssignment,  # TBD - Model not yet implemented
    # RecommendationInteraction,  # TBD - Model not yet implemented
    ConversationSession,
    LLMRecommendation
)
from apps.peoples.models import People
from apps.core.exceptions import LLMServiceException
import numpy as np
import scipy.stats as stats
from dataclasses import dataclass, asdict

# Temporary stubs for unimplemented models (TBD)
class Experiment:
    """Stub for Experiment model (TBD)"""
    objects = None
    class StatusChoices:
        DRAFT = 'draft'
        RUNNING = 'running'
        PAUSED = 'paused'
        COMPLETED = 'completed'
    class DoesNotExist(Exception):
        pass
    def get_arm_count(self):
        return 0
    def is_active(self):
        return False
    def update_results(self, results):
        pass

class ExperimentAssignment:
    """Stub for ExperimentAssignment model (TBD)"""
    objects = None

class RecommendationInteraction:
    """Stub for RecommendationInteraction model (TBD)"""
    objects = None
    def get_time_to_decision(self):
        return 0

class ExperimentError(Exception):
    """Exception for experiment-related errors"""
    pass

logger = logging.getLogger(__name__)


class ExperimentError(Exception):
    """Custom exception for experiment-related errors"""
    pass


class StatisticalTestResult:
    """Results of statistical significance testing"""
    def __init__(self, test_name: str, statistic: float, p_value: float,
                 significant: bool, effect_size: float = None, confidence_interval: Tuple[float, float] = None):
        self.test_name = test_name
        self.statistic = statistic
        self.p_value = p_value
        self.significant = significant
        self.effect_size = effect_size
        self.confidence_interval = confidence_interval
        self.alpha = getattr(settings, 'EXPERIMENT_ALPHA', 0.05)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'statistic': self.statistic,
            'p_value': self.p_value,
            'significant': self.significant,
            'effect_size': self.effect_size,
            'confidence_interval': self.confidence_interval,
            'alpha': self.alpha
        }


@dataclass
class ArmPerformance:
    """Performance metrics for an experiment arm"""
    arm_name: str
    total_users: int
    total_interactions: int
    approvals: int
    rejections: int
    modifications: int
    escalations: int
    avg_decision_time: float
    total_cost_cents: int
    conversion_rate: float
    confidence_interval: Tuple[float, float]
    sample_size: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentAnalyzer:
    """
    Statistical analysis engine for A/B tests and multi-armed bandit experiments
    """

    def __init__(self):
        self.alpha = getattr(settings, 'EXPERIMENT_ALPHA', 0.05)  # Significance level
        self.min_sample_size = getattr(settings, 'EXPERIMENT_MIN_SAMPLE_SIZE', 30)
        self.min_effect_size = getattr(settings, 'EXPERIMENT_MIN_EFFECT_SIZE', 0.02)  # 2% minimum effect
        self.bonferroni_correction = getattr(settings, 'EXPERIMENT_BONFERRONI_CORRECTION', True)

    def analyze_experiment(self, experiment: Experiment) -> Dict[str, Any]:
        """
        Comprehensive analysis of an experiment

        Args:
            experiment: The experiment to analyze

        Returns:
            Dict containing statistical analysis results
        """
        try:
            # Get arm performance data
            arm_performances = self._get_arm_performances(experiment)

            if len(arm_performances) < 2:
                return {
                    'status': 'insufficient_arms',
                    'message': 'Need at least 2 arms for comparison',
                    'arms': len(arm_performances)
                }

            # Check minimum sample sizes
            insufficient_samples = [arm for arm in arm_performances
                                  if arm.sample_size < self.min_sample_size]

            if insufficient_samples:
                return {
                    'status': 'insufficient_samples',
                    'message': f'Arms need at least {self.min_sample_size} samples',
                    'insufficient_arms': [arm.arm_name for arm in insufficient_samples],
                    'arm_performances': [arm.to_dict() for arm in arm_performances]
                }

            # Perform statistical tests
            statistical_results = self._perform_statistical_tests(arm_performances, experiment)

            # Calculate effect sizes and practical significance
            effect_analysis = self._analyze_effect_sizes(arm_performances)

            # Power analysis
            power_analysis = self._perform_power_analysis(arm_performances)

            # Generate recommendations
            recommendations = self._generate_experiment_recommendations(
                arm_performances, statistical_results, effect_analysis, power_analysis
            )

            analysis_result = {
                'status': 'complete',
                'experiment_id': str(experiment.experiment_id),
                'analysis_timestamp': timezone.now().isoformat(),
                'arm_performances': [arm.to_dict() for arm in arm_performances],
                'statistical_tests': [test.to_dict() for test in statistical_results],
                'effect_analysis': effect_analysis,
                'power_analysis': power_analysis,
                'recommendations': recommendations,
                'summary': self._generate_summary(arm_performances, statistical_results)
            }

            # Update experiment with results
            experiment.update_results(analysis_result)

            return analysis_result

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error analyzing experiment {experiment.experiment_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'experiment_id': str(experiment.experiment_id)
            }

    def _get_arm_performances(self, experiment: Experiment) -> List[ArmPerformance]:
        """Get performance metrics for each experiment arm"""
        arm_performances = []

        # Get all assignments for this experiment
        assignments = ExperimentAssignment.objects.filter(experiment=experiment).select_related('user')

        # Group by arm
        arms_data = {}
        for assignment in assignments:
            arm_name = assignment.arm
            if arm_name not in arms_data:
                arms_data[arm_name] = {
                    'users': set(),
                    'assignments': []
                }

            if assignment.user:
                arms_data[arm_name]['users'].add(assignment.user.id)
            arms_data[arm_name]['assignments'].append(assignment)

        # Calculate metrics for each arm
        for arm_name, data in arms_data.items():
            arm_perf = self._calculate_arm_metrics(arm_name, data['assignments'], experiment)
            if arm_perf:
                arm_performances.append(arm_perf)

        return arm_performances

    def _calculate_arm_metrics(self, arm_name: str, assignments: List[ExperimentAssignment],
                              experiment: Experiment) -> Optional[ArmPerformance]:
        """Calculate detailed metrics for a single arm"""
        try:
            # Get all interactions for users in this arm
            user_ids = [a.user.id for a in assignments if a.user]
            if not user_ids:
                return None

            # Get interactions since experiment started
            start_date = experiment.started_at or experiment.cdtz
            interactions = RecommendationInteraction.objects.filter(
                session__user_id__in=user_ids,
                occurred_at__gte=start_date
            ).select_related('recommendation', 'session')

            # Count outcomes
            total_interactions = interactions.count()
            approvals = interactions.filter(event_type='approved').count()
            rejections = interactions.filter(event_type='rejected').count()
            modifications = interactions.filter(event_type='modified').count()
            escalations = interactions.filter(event_type='escalated').count()

            # Calculate conversion rate (approvals / total decisions)
            total_decisions = approvals + rejections + modifications
            conversion_rate = approvals / total_decisions if total_decisions > 0 else 0.0

            # Calculate confidence interval for conversion rate
            ci = self._calculate_confidence_interval(approvals, total_decisions)

            # Calculate average decision time
            decision_interactions = interactions.filter(
                event_type__in=['approved', 'rejected', 'modified']
            )
            decision_times = [i.get_time_to_decision() for i in decision_interactions]
            decision_times = [t for t in decision_times if t > 0]
            avg_decision_time = np.mean(decision_times) if decision_times else 0.0

            # Calculate total cost
            total_cost = sum(
                i.metadata.get('cost_estimate', 0) for i in interactions
            )

            return ArmPerformance(
                arm_name=arm_name,
                total_users=len(set(user_ids)),
                total_interactions=total_interactions,
                approvals=approvals,
                rejections=rejections,
                modifications=modifications,
                escalations=escalations,
                avg_decision_time=avg_decision_time,
                total_cost_cents=int(total_cost * 100),  # Convert to cents
                conversion_rate=conversion_rate,
                confidence_interval=ci,
                sample_size=total_decisions
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating metrics for arm {arm_name}: {str(e)}")
            return None

    def _calculate_confidence_interval(self, successes: int, total: int,
                                     confidence_level: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for proportion using Wilson score interval"""
        if total == 0:
            return (0.0, 0.0)

        p = successes / total
        z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

        # Wilson score interval
        denominator = 1 + z**2 / total
        centre_adjusted_probability = p + z**2 / (2 * total)
        adjusted_standard_deviation = math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total)

        lower_bound = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
        upper_bound = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator

        return (max(0.0, lower_bound), min(1.0, upper_bound))

    def _perform_statistical_tests(self, arm_performances: List[ArmPerformance],
                                 experiment: Experiment) -> List[StatisticalTestResult]:
        """Perform statistical significance tests between arms"""
        results = []

        # Adjust alpha for multiple comparisons if using Bonferroni correction
        num_comparisons = len(arm_performances) * (len(arm_performances) - 1) // 2
        adjusted_alpha = self.alpha / num_comparisons if self.bonferroni_correction and num_comparisons > 1 else self.alpha

        # Pairwise comparisons
        for i in range(len(arm_performances)):
            for j in range(i + 1, len(arm_performances)):
                arm_a = arm_performances[i]
                arm_b = arm_performances[j]

                # Two-proportion z-test
                result = self._two_proportion_test(arm_a, arm_b, adjusted_alpha)
                result.test_name = f"{arm_a.arm_name} vs {arm_b.arm_name}"
                results.append(result)

        # Overall test (Chi-square test of independence)
        if len(arm_performances) > 2:
            chi_square_result = self._chi_square_test(arm_performances, adjusted_alpha)
            results.append(chi_square_result)

        return results

    def _two_proportion_test(self, arm_a: ArmPerformance, arm_b: ArmPerformance,
                           alpha: float) -> StatisticalTestResult:
        """Two-proportion z-test between two arms"""
        try:
            # Extract data
            x1, n1 = arm_a.approvals, arm_a.sample_size
            x2, n2 = arm_b.approvals, arm_b.sample_size

            if n1 == 0 or n2 == 0:
                return StatisticalTestResult("Two-proportion z-test", 0.0, 1.0, False)

            p1 = x1 / n1
            p2 = x2 / n2

            # Pooled proportion
            p_pool = (x1 + x2) / (n1 + n2)

            # Standard error
            se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))

            if se == 0:
                return StatisticalTestResult("Two-proportion z-test", 0.0, 1.0, False)

            # Z-statistic
            z = (p1 - p2) / se

            # P-value (two-tailed)
            p_value = 2 * (1 - stats.norm.cdf(abs(z)))

            # Effect size (Cohen's h)
            h = 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))

            return StatisticalTestResult(
                "Two-proportion z-test",
                z,
                p_value,
                p_value < alpha,
                h,
                self._difference_confidence_interval(p1, p2, n1, n2)
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error in two-proportion test: {str(e)}")
            return StatisticalTestResult("Two-proportion z-test", 0.0, 1.0, False)

    def _chi_square_test(self, arm_performances: List[ArmPerformance],
                        alpha: float) -> StatisticalTestResult:
        """Chi-square test of independence for multiple arms"""
        try:
            # Create contingency table
            approvals = [arm.approvals for arm in arm_performances]
            failures = [arm.sample_size - arm.approvals for arm in arm_performances]

            contingency_table = [approvals, failures]

            # Perform chi-square test
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)

            # Effect size (Cramér's V)
            n = sum(sum(row) for row in contingency_table)
            cramers_v = math.sqrt(chi2 / (n * (min(len(approvals), 2) - 1)))

            return StatisticalTestResult(
                "Chi-square test",
                chi2,
                p_value,
                p_value < alpha,
                cramers_v
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error in chi-square test: {str(e)}")
            return StatisticalTestResult("Chi-square test", 0.0, 1.0, False)

    def _difference_confidence_interval(self, p1: float, p2: float, n1: int, n2: int,
                                      confidence_level: float = 0.95) -> Tuple[float, float]:
        """Confidence interval for difference in proportions"""
        try:
            diff = p1 - p2
            z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

            se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)

            lower = diff - z * se
            upper = diff + z * se

            return (lower, upper)
        except (ValueError, TypeError, AttributeError) as e:
            return (-1.0, 1.0)

    def _analyze_effect_sizes(self, arm_performances: List[ArmPerformance]) -> Dict[str, Any]:
        """Analyze practical significance through effect sizes"""
        if len(arm_performances) < 2:
            return {'status': 'insufficient_arms'}

        # Find control arm (if exists) or use first arm as baseline
        control_arm = None
        for arm in arm_performances:
            if 'control' in arm.arm_name.lower():
                control_arm = arm
                break

        if not control_arm:
            control_arm = arm_performances[0]

        effect_analysis = {
            'baseline_arm': control_arm.arm_name,
            'baseline_conversion_rate': control_arm.conversion_rate,
            'comparisons': []
        }

        for arm in arm_performances:
            if arm.arm_name == control_arm.arm_name:
                continue

            # Absolute difference
            abs_diff = arm.conversion_rate - control_arm.conversion_rate

            # Relative lift
            rel_lift = (abs_diff / control_arm.conversion_rate * 100) if control_arm.conversion_rate > 0 else 0

            # Statistical power for this comparison
            power = self._calculate_statistical_power(control_arm, arm)

            # Practical significance
            practically_significant = abs(abs_diff) >= self.min_effect_size

            comparison = {
                'arm_name': arm.arm_name,
                'conversion_rate': arm.conversion_rate,
                'absolute_difference': abs_diff,
                'relative_lift_percent': rel_lift,
                'statistical_power': power,
                'practically_significant': practically_significant,
                'confidence_interval': arm.confidence_interval
            }

            effect_analysis['comparisons'].append(comparison)

        return effect_analysis

    def _calculate_statistical_power(self, arm_a: ArmPerformance, arm_b: ArmPerformance) -> float:
        """Calculate statistical power for comparison between two arms"""
        try:
            p1 = arm_a.conversion_rate
            p2 = arm_b.conversion_rate
            n1 = arm_a.sample_size
            n2 = arm_b.sample_size

            if n1 == 0 or n2 == 0 or p1 == 0:
                return 0.0

            # Effect size (Cohen's h)
            h = 2 * abs(math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))

            # Pooled sample size (harmonic mean)
            n_pooled = 2 * n1 * n2 / (n1 + n2)

            # Critical value
            z_alpha = stats.norm.ppf(1 - self.alpha / 2)

            # Power calculation
            z_beta = h * math.sqrt(n_pooled / 4) - z_alpha
            power = stats.norm.cdf(z_beta)

            return max(0.0, min(1.0, power))

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating statistical power: {str(e)}")
            return 0.0

    def _perform_power_analysis(self, arm_performances: List[ArmPerformance]) -> Dict[str, Any]:
        """Perform power analysis to determine if experiment is adequately powered"""
        min_power = getattr(settings, 'EXPERIMENT_MIN_POWER', 0.8)

        power_analysis = {
            'minimum_required_power': min_power,
            'arms_analysis': [],
            'overall_adequately_powered': True
        }

        # Use first arm as baseline for power calculations
        baseline_arm = arm_performances[0]

        for arm in arm_performances[1:]:
            power = self._calculate_statistical_power(baseline_arm, arm)

            # Calculate required sample size for desired power
            required_n = self._calculate_required_sample_size(
                baseline_arm.conversion_rate,
                arm.conversion_rate,
                min_power
            )

            arm_analysis = {
                'arm_name': arm.arm_name,
                'current_power': power,
                'adequately_powered': power >= min_power,
                'current_sample_size': arm.sample_size,
                'required_sample_size': required_n,
                'additional_samples_needed': max(0, required_n - arm.sample_size)
            }

            if power < min_power:
                power_analysis['overall_adequately_powered'] = False

            power_analysis['arms_analysis'].append(arm_analysis)

        return power_analysis

    def _calculate_required_sample_size(self, p1: float, p2: float, power: float) -> int:
        """Calculate required sample size per group for desired power"""
        try:
            if p1 == p2 or p1 == 0 or p2 == 0:
                return 1000  # Default for edge cases

            # Effect size (Cohen's h)
            h = 2 * abs(math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))

            if h == 0:
                return 1000

            # Critical values
            z_alpha = stats.norm.ppf(1 - self.alpha / 2)
            z_beta = stats.norm.ppf(power)

            # Required sample size per group
            n = 4 * ((z_alpha + z_beta) / h) ** 2

            return max(self.min_sample_size, int(math.ceil(n)))

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating required sample size: {str(e)}")
            return 1000

    def _generate_experiment_recommendations(self, arm_performances: List[ArmPerformance],
                                           statistical_results: List[StatisticalTestResult],
                                           effect_analysis: Dict[str, Any],
                                           power_analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        # Check for winners
        significant_tests = [test for test in statistical_results if test.significant]
        if significant_tests:
            # Find best performing arm
            best_arm = max(arm_performances, key=lambda x: x.conversion_rate)
            recommendations.append(
                f"Statistically significant winner found: {best_arm.arm_name} "
                f"with {best_arm.conversion_rate:.2%} conversion rate"
            )

            # Check practical significance
            if effect_analysis['comparisons']:
                max_lift = max(comp['relative_lift_percent'] for comp in effect_analysis['comparisons'])
                if max_lift >= self.min_effect_size * 100:
                    recommendations.append(
                        f"Practically significant lift of {max_lift:.1f}% detected - "
                        "consider promoting winning variant"
                    )
        else:
            recommendations.append("No statistically significant differences detected")

        # Power recommendations
        if not power_analysis['overall_adequately_powered']:
            under_powered_arms = [
                arm for arm in power_analysis['arms_analysis']
                if not arm['adequately_powered']
            ]
            if under_powered_arms:
                min_additional = min(arm['additional_samples_needed'] for arm in under_powered_arms)
                recommendations.append(
                    f"Experiment is under-powered. Need at least {min_additional} "
                    "additional samples per arm to reach 80% power"
                )

        # Safety recommendations
        escalation_rates = [arm.escalations / max(1, arm.total_interactions) for arm in arm_performances]
        max_escalation_rate = max(escalation_rates) if escalation_rates else 0
        if max_escalation_rate > 0.1:  # 10% escalation rate threshold
            worst_arm = arm_performances[escalation_rates.index(max_escalation_rate)]
            recommendations.append(
                f"High escalation rate ({max_escalation_rate:.1%}) in arm {worst_arm.arm_name} - "
                "consider safety review"
            )

        # Cost recommendations
        cost_per_approval = []
        for arm in arm_performances:
            if arm.approvals > 0:
                cost_per_approval.append((arm.arm_name, arm.total_cost_cents / arm.approvals))

        if cost_per_approval:
            cost_per_approval.sort(key=lambda x: x[1])
            most_efficient = cost_per_approval[0]
            least_efficient = cost_per_approval[-1]

            if len(cost_per_approval) > 1 and least_efficient[1] > most_efficient[1] * 2:
                recommendations.append(
                    f"Significant cost efficiency difference: {most_efficient[0]} "
                    f"is 2x more cost-effective than {least_efficient[0]}"
                )

        if not recommendations:
            recommendations.append("Continue experiment - insufficient evidence for conclusion")

        return recommendations

    def _generate_summary(self, arm_performances: List[ArmPerformance],
                         statistical_results: List[StatisticalTestResult]) -> Dict[str, Any]:
        """Generate executive summary of experiment results"""
        # Best performing arm
        best_arm = max(arm_performances, key=lambda x: x.conversion_rate)

        # Statistical significance
        significant_results = sum(1 for test in statistical_results if test.significant)

        # Sample sizes
        total_samples = sum(arm.sample_size for arm in arm_performances)

        summary = {
            'total_arms': len(arm_performances),
            'best_performing_arm': {
                'name': best_arm.arm_name,
                'conversion_rate': best_arm.conversion_rate,
                'confidence_interval': best_arm.confidence_interval
            },
            'statistical_significance': {
                'significant_comparisons': significant_results,
                'total_comparisons': len(statistical_results),
                'any_significant': significant_results > 0
            },
            'sample_size': {
                'total_samples': total_samples,
                'average_per_arm': total_samples / len(arm_performances)
            },
            'recommendation': self._get_primary_recommendation(arm_performances, statistical_results)
        }

        return summary

    def _get_primary_recommendation(self, arm_performances: List[ArmPerformance],
                                   statistical_results: List[StatisticalTestResult]) -> str:
        """Get primary recommendation for experiment"""
        significant_tests = [test for test in statistical_results if test.significant]

        if significant_tests:
            best_arm = max(arm_performances, key=lambda x: x.conversion_rate)
            return f"Promote {best_arm.arm_name} - statistically significant winner"

        # Check if we have enough samples
        min_samples_met = all(arm.sample_size >= self.min_sample_size for arm in arm_performances)
        if not min_samples_met:
            return "Continue collecting data - insufficient sample size"

        # Check for practical significance
        conversion_rates = [arm.conversion_rate for arm in arm_performances]
        if max(conversion_rates) - min(conversion_rates) >= self.min_effect_size:
            return "Consider practical significance - large effect size without statistical significance"

        return "No clear winner - consider ending experiment"


class ExperimentManager:
    """
    High-level experiment management service
    """

    def __init__(self):
        self.analyzer = ExperimentAnalyzer()
        self.safety_check_interval = timedelta(hours=6)  # Check every 6 hours

    def create_experiment(self, name: str, description: str, arms: List[Dict[str, Any]],
                         owner: People, **kwargs) -> Experiment:
        """
        Create a new experiment with validation

        Args:
            name: Experiment name
            description: Experiment description
            arms: List of arm configurations
            owner: Experiment owner
            **kwargs: Additional experiment parameters

        Returns:
            Experiment: Created experiment instance
        """
        try:
            # Validate arms configuration
            self._validate_arms_config(arms)

            # Create experiment
            experiment = Experiment.objects.create(
                name=name,
                description=description,
                arms=arms,
                owner=owner,
                scope=kwargs.get('scope', 'tenant'),
                primary_metric=kwargs.get('primary_metric', 'acceptance_rate'),
                secondary_metrics=kwargs.get('secondary_metrics', []),
                holdback_pct=kwargs.get('holdback_pct', 10.0),
                safety_constraints=kwargs.get('safety_constraints', self._get_default_safety_constraints())
            )

            logger.info(f"Created experiment {experiment.name} with {len(arms)} arms")
            return experiment

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error creating experiment: {str(e)}")
            raise ExperimentError(f"Failed to create experiment: {str(e)}")

    def start_experiment(self, experiment: Experiment) -> bool:
        """Start an experiment with safety checks"""
        try:
            with transaction.atomic():
                # Validate experiment is ready to start
                if experiment.status != Experiment.StatusChoices.DRAFT:
                    raise ExperimentError(f"Cannot start experiment in {experiment.status} status")

                if not experiment.arms:
                    raise ExperimentError("Cannot start experiment without arms")

                # Update status
                experiment.status = Experiment.StatusChoices.RUNNING
                experiment.started_at = timezone.now()
                experiment.save()

                logger.info(f"Started experiment {experiment.name}")
                return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error starting experiment {experiment.experiment_id}: {str(e)}")
            raise ExperimentError(f"Failed to start experiment: {str(e)}")

    def pause_experiment(self, experiment: Experiment, reason: str = None) -> bool:
        """Pause a running experiment"""
        try:
            if experiment.status != Experiment.StatusChoices.RUNNING:
                raise ExperimentError(f"Cannot pause experiment in {experiment.status} status")

            experiment.status = Experiment.StatusChoices.PAUSED

            # Log reason
            if not experiment.results:
                experiment.results = {}
            experiment.results['pause_reason'] = reason
            experiment.results['paused_at'] = timezone.now().isoformat()

            experiment.save()

            logger.info(f"Paused experiment {experiment.name}: {reason}")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error pausing experiment: {str(e)}")
            return False

    def complete_experiment(self, experiment: Experiment, final_analysis: bool = True) -> Dict[str, Any]:
        """Complete an experiment with final analysis"""
        try:
            with transaction.atomic():
                # Perform final analysis
                if final_analysis:
                    analysis_result = self.analyzer.analyze_experiment(experiment)
                else:
                    analysis_result = {'status': 'completed_without_analysis'}

                # Update experiment
                experiment.status = Experiment.StatusChoices.COMPLETED
                experiment.ended_at = timezone.now()
                experiment.save()

                logger.info(f"Completed experiment {experiment.name}")
                return analysis_result

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error completing experiment: {str(e)}")
            raise ExperimentError(f"Failed to complete experiment: {str(e)}")

    def check_safety_constraints(self, experiment: Experiment) -> List[str]:
        """Check safety constraints and return violations"""
        try:
            if not experiment.is_active():
                return []

            # Get current arm performance
            arm_performances = self.analyzer._get_arm_performances(experiment)

            violations = []
            safety_constraints = experiment.safety_constraints or {}

            for arm_perf in arm_performances:
                # Error rate check
                total_interactions = arm_perf.total_interactions
                errors = arm_perf.escalations  # Use escalations as proxy for errors
                error_rate = errors / total_interactions if total_interactions > 0 else 0

                max_error_rate = safety_constraints.get('max_error_rate', 0.1)
                if error_rate > max_error_rate:
                    violations.append(
                        f"Arm {arm_perf.arm_name} error rate {error_rate:.2%} "
                        f"exceeds limit {max_error_rate:.2%}"
                    )

                # Cost check
                max_daily_spend = safety_constraints.get('max_daily_spend_cents', 10000)
                if arm_perf.total_cost_cents > max_daily_spend:
                    violations.append(
                        f"Arm {arm_perf.arm_name} daily spend ${arm_perf.total_cost_cents/100:.2f} "
                        f"exceeds limit ${max_daily_spend/100:.2f}"
                    )

            # Auto-pause if violations detected
            if violations and safety_constraints.get('auto_pause_on_violation', True):
                self.pause_experiment(experiment, f"Safety violations: {'; '.join(violations)}")

            return violations

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error checking safety constraints: {str(e)}")
            return [f"Safety check failed: {str(e)}"]

    def promote_winning_arm(self, experiment: Experiment, arm_name: str) -> Dict[str, Any]:
        """Promote winning experiment arm to production policy"""
        try:
            # Validate experiment is completed
            if experiment.status != Experiment.StatusChoices.COMPLETED:
                raise ExperimentError("Can only promote arms from completed experiments")

            # Find the arm configuration
            arm_config = None
            for arm in experiment.arms:
                if arm.get('name') == arm_name:
                    arm_config = arm
                    break

            if not arm_config:
                raise ExperimentError(f"Arm {arm_name} not found in experiment")

            # Create policy version from arm config
            policy_version = self._create_policy_from_arm(arm_config, experiment)

            # Log promotion
            promotion_record = {
                'promoted_at': timezone.now().isoformat(),
                'promoted_arm': arm_name,
                'experiment_id': str(experiment.experiment_id),
                'policy_version': policy_version
            }

            # Update experiment results
            if not experiment.results:
                experiment.results = {}
            experiment.results['promotion'] = promotion_record
            experiment.save()

            logger.info(f"Promoted arm {arm_name} from experiment {experiment.name} to policy {policy_version}")

            return {
                'status': 'success',
                'promoted_arm': arm_name,
                'policy_version': policy_version,
                'promotion_record': promotion_record
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error promoting experiment arm: {str(e)}")
            raise ExperimentError(f"Failed to promote arm: {str(e)}")

    def _validate_arms_config(self, arms: List[Dict[str, Any]]):
        """Validate experiment arms configuration"""
        if not arms or len(arms) < 2:
            raise ExperimentError("Experiment must have at least 2 arms")

        required_fields = ['name']
        arm_names = set()

        for i, arm in enumerate(arms):
            # Check required fields
            for field in required_fields:
                if field not in arm:
                    raise ExperimentError(f"Arm {i} missing required field: {field}")

            # Check for duplicate names
            name = arm['name']
            if name in arm_names:
                raise ExperimentError(f"Duplicate arm name: {name}")
            arm_names.add(name)

            # Validate arm configuration structure
            if 'config' in arm and not isinstance(arm['config'], dict):
                raise ExperimentError(f"Arm {name} config must be a dictionary")

    def _get_default_safety_constraints(self) -> Dict[str, Any]:
        """Get default safety constraints for experiments"""
        return {
            'max_error_rate': 0.1,  # 10% maximum error rate
            'max_complaint_rate': 0.05,  # 5% maximum complaint rate
            'max_daily_spend_cents': 10000,  # $100 maximum daily spend
            'auto_pause_on_violation': True,
            'min_sample_size_per_arm': 30
        }

    def _create_policy_from_arm(self, arm_config: Dict[str, Any], experiment: Experiment) -> str:
        """Create a new policy version from winning arm configuration"""
        # Generate policy version identifier
        policy_version = f"exp_{experiment.experiment_id}_{arm_config['name']}_{timezone.now().strftime('%Y%m%d_%H%M')}"

        # This would typically create a new PolicyVersion record in the database
        # For now, we'll just return the version identifier

        # In a full implementation, this would:
        # 1. Create PolicyVersion record
        # 2. Update prompt templates with arm's configuration
        # 3. Set retrieval parameters from arm config
        # 4. Update quality thresholds
        # 5. Deploy to production systems

        return policy_version


# Factory function
def get_experiment_manager() -> ExperimentManager:
    """Get the experiment manager service"""
    return ExperimentManager()