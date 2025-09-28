"""
Personalization algorithms and recommendation reranking service

This module implements the core personalization logic that uses learned user preferences
to rerank, filter, and optimize recommendations for individual users and tenants.

Key Features:
- Preference-based recommendation scoring and reranking
- Cost/quality optimization with budget constraints
- Policy-aware recommendation filtering
- Multi-armed bandit recommendation selection
- A/B test variant assignment and tracking
"""

import logging
import random
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
    Experiment,
    ExperimentAssignment,
    LLMRecommendation,
    ConversationSession
)
from apps.peoples.models import People
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RecommendationContext:
    """Context information for personalization decisions"""
    def __init__(self, user: People, client, session: ConversationSession,
                 budget_cents: Optional[int] = None, max_recommendations: int = 5):
        self.user = user
        self.client = client
        self.session = session
        self.budget_cents = budget_cents or getattr(settings, 'ONBOARDING_DEFAULT_BUDGET_CENTS', 1000)
        self.max_recommendations = max_recommendations

        # Load user preferences
        self.preference_profile = PreferenceProfile.objects.filter(
            user=user, client=client
        ).first()

        # Context metadata
        self.timestamp = timezone.now()
        self.session_type = session.conversation_type
        self.language = session.language


@dataclass
class ScoredRecommendation:
    """Scored recommendation with personalization metrics"""
    recommendation: LLMRecommendation
    personalization_score: float
    cost_score: float
    quality_score: float
    composite_score: float
    ranking_factors: Dict[str, float]
    estimated_cost_cents: int
    confidence_adjusted: float


class PolicyVersion:
    """Versioned policy configuration for prompts and parameters"""
    def __init__(self, version: str, config: Dict[str, Any]):
        self.version = version
        self.config = config

        # Extract key configurations
        self.prompt_templates = config.get('prompt_templates', {})
        self.retrieval_params = config.get('retrieval_params', {})
        self.quality_thresholds = config.get('quality_thresholds', {})
        self.cost_limits = config.get('cost_limits', {})


class RecommendationReranker:
    """
    Core reranking service that personalizes recommendations based on user preferences
    """

    def __init__(self):
        # Scoring weights (configurable)
        self.scoring_weights = {
            'personalization': getattr(settings, 'RERANK_PERSONALIZATION_WEIGHT', 0.4),
            'consensus_confidence': getattr(settings, 'RERANK_CONSENSUS_WEIGHT', 0.3),
            'citation_strength': getattr(settings, 'RERANK_CITATION_WEIGHT', 0.2),
            'cost_efficiency': getattr(settings, 'RERANK_COST_WEIGHT', 0.1)
        }

        # Caching configuration
        self.cache_timeout = getattr(settings, 'RERANK_CACHE_TIMEOUT', 300)  # 5 minutes

        # Policy registry
        self.policy_registry = self._load_policy_registry()

    def rerank_recommendations(self, recommendations: List[LLMRecommendation],
                             context: RecommendationContext) -> List[ScoredRecommendation]:
        """
        Rerank recommendations based on user preferences and context

        Args:
            recommendations: List of candidate recommendations
            context: Personalization context with user, preferences, budget

        Returns:
            List of scored and reranked recommendations
        """
        try:
            if not recommendations:
                return []

            # Score each recommendation
            scored_recommendations = []
            for rec in recommendations:
                scored_rec = self._score_recommendation(rec, context)
                if scored_rec:
                    scored_recommendations.append(scored_rec)

            # Sort by composite score (descending)
            scored_recommendations.sort(key=lambda x: x.composite_score, reverse=True)

            # Apply budget constraints
            budget_filtered = self._apply_budget_constraints(scored_recommendations, context)

            # Apply quality filters
            quality_filtered = self._apply_quality_filters(budget_filtered, context)

            # Limit to max recommendations
            final_recommendations = quality_filtered[:context.max_recommendations]

            logger.info(f"Reranked {len(recommendations)} recommendations to {len(final_recommendations)} "
                       f"for user {context.user.id}")

            return final_recommendations

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error reranking recommendations: {str(e)}")
            # Fallback: return original recommendations with basic scoring
            return self._fallback_scoring(recommendations, context)

    def _score_recommendation(self, rec: LLMRecommendation,
                            context: RecommendationContext) -> Optional[ScoredRecommendation]:
        """Score a single recommendation with personalization factors"""
        try:
            # Base scores
            personalization_score = self._calculate_personalization_score(rec, context)
            consensus_score = rec.confidence_score or 0.0
            citation_score = self._calculate_citation_score(rec, context)
            cost_score = self._calculate_cost_score(rec, context)

            # Quality adjustments
            quality_score = self._calculate_quality_score(rec, context)

            # Composite score
            composite_score = (
                self.scoring_weights['personalization'] * personalization_score +
                self.scoring_weights['consensus_confidence'] * consensus_score +
                self.scoring_weights['citation_strength'] * citation_score +
                self.scoring_weights['cost_efficiency'] * cost_score
            )

            # Apply quality multiplier
            composite_score *= quality_score

            # Ranking factors for explainability
            ranking_factors = {
                'personalization': personalization_score,
                'consensus_confidence': consensus_score,
                'citation_strength': citation_score,
                'cost_efficiency': cost_score,
                'quality_multiplier': quality_score
            }

            # Estimate cost
            estimated_cost = self._estimate_recommendation_cost(rec, context)

            # Adjust confidence based on personalization
            confidence_adjusted = min(1.0, consensus_score + personalization_score * 0.1)

            return ScoredRecommendation(
                recommendation=rec,
                personalization_score=personalization_score,
                cost_score=cost_score,
                quality_score=quality_score,
                composite_score=composite_score,
                ranking_factors=ranking_factors,
                estimated_cost_cents=estimated_cost,
                confidence_adjusted=confidence_adjusted
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error scoring recommendation {rec.recommendation_id}: {str(e)}")
            return None

    def _calculate_personalization_score(self, rec: LLMRecommendation,
                                       context: RecommendationContext) -> float:
        """Calculate how well recommendation matches user preferences"""
        if not context.preference_profile or not context.preference_profile.weights:
            return 0.5  # Neutral score for unknown preferences

        preferences = context.preference_profile.weights
        score = 0.5  # Base score

        # Cost sensitivity alignment
        cost_sensitivity = preferences.get('cost_sensitivity', 0.5)
        estimated_cost = self._estimate_recommendation_cost(rec, context)
        if estimated_cost > 0:
            # High cost sensitivity = prefer lower cost recommendations
            cost_factor = max(0.0, 1.0 - (estimated_cost / 1000.0))  # Normalize to $10 max
            score += (cost_sensitivity * cost_factor - 0.5) * 0.3

        # Risk tolerance alignment
        risk_tolerance = preferences.get('risk_tolerance', 0.5)
        confidence = rec.confidence_score or 0.5
        # High risk tolerance = accept lower confidence recommendations
        risk_factor = 1.0 - risk_tolerance  # Convert to risk aversion
        confidence_penalty = risk_factor * max(0.0, 0.7 - confidence)
        score -= confidence_penalty * 0.3

        # Citation importance alignment
        citation_importance = preferences.get('citation_importance', 0.5)
        has_citations = bool(rec.authoritative_sources)
        citation_count = len(rec.authoritative_sources) if rec.authoritative_sources else 0

        if citation_importance > 0.7:  # User values citations highly
            if has_citations:
                score += min(0.3, citation_count * 0.1)
            else:
                score -= 0.2
        elif citation_importance < 0.3:  # User doesn't care about citations
            if not has_citations:
                score += 0.1  # Prefer simpler recommendations

        # Detail level preference
        detail_level = preferences.get('detail_level', 0.5)
        rec_complexity = self._estimate_recommendation_complexity(rec)
        complexity_match = 1.0 - abs(detail_level - rec_complexity)
        score += (complexity_match - 0.5) * 0.2

        # Language preference
        language_pref = preferences.get('language_pref', 'en')
        if context.session.language == language_pref:
            score += 0.1

        # Use preference vector if available
        if (context.preference_profile.preference_vector and
            hasattr(rec, 'content_vector') and rec.content_vector):
            vector_similarity = self._calculate_vector_similarity(
                context.preference_profile.preference_vector,
                rec.content_vector
            )
            score += vector_similarity * 0.3

        return max(0.0, min(1.0, score))

    def _calculate_citation_score(self, rec: LLMRecommendation,
                                context: RecommendationContext) -> float:
        """Calculate citation quality and relevance score"""
        if not rec.authoritative_sources:
            return 0.0

        total_score = 0.0
        citation_count = len(rec.authoritative_sources)

        for source in rec.authoritative_sources:
            source_score = 0.0

            # Authority level scoring
            authority_weights = {'official': 1.0, 'high': 0.8, 'medium': 0.6, 'low': 0.3}
            authority = source.get('authority_level', 'medium')
            source_score += authority_weights.get(authority, 0.5)

            # Recency scoring (if available)
            if 'publication_date' in source:
                try:
                    pub_date = datetime.fromisoformat(source['publication_date'])
                    age_days = (datetime.now() - pub_date).days
                    recency_score = max(0.2, 1.0 - age_days / 1095)  # 3 years = 0.2 score
                    source_score *= recency_score
                except:
                    pass  # Use base score if date parsing fails

            total_score += source_score

        # Normalize by citation count and apply diminishing returns
        if citation_count > 0:
            avg_quality = total_score / citation_count
            citation_bonus = min(0.3, citation_count * 0.1)  # Up to 30% bonus
            return min(1.0, avg_quality + citation_bonus)

        return 0.0

    def _calculate_cost_score(self, rec: LLMRecommendation,
                            context: RecommendationContext) -> float:
        """Calculate cost efficiency score"""
        estimated_cost = self._estimate_recommendation_cost(rec, context)

        if estimated_cost == 0:
            return 1.0  # Perfect score for free recommendations

        # Budget efficiency - how much of budget this uses
        budget_ratio = estimated_cost / context.budget_cents

        # Quality per dollar - confidence score divided by cost
        quality_per_dollar = (rec.confidence_score or 0.5) / max(1, estimated_cost / 100)  # Per dollar

        # Combine factors
        budget_score = max(0.0, 1.0 - budget_ratio)
        efficiency_score = min(1.0, quality_per_dollar)

        return 0.6 * budget_score + 0.4 * efficiency_score

    def _calculate_quality_score(self, rec: LLMRecommendation,
                               context: RecommendationContext) -> float:
        """Calculate overall quality score as a multiplier"""
        quality_factors = []

        # Base confidence
        confidence = rec.confidence_score or 0.5
        quality_factors.append(confidence)

        # Citation quality
        if rec.authoritative_sources:
            citation_quality = len(rec.authoritative_sources) / 5.0  # Normalize to 5 citations
            quality_factors.append(min(1.0, citation_quality))
        else:
            quality_factors.append(0.3)  # Penalty for no citations

        # Consensus quality (if available from checker)
        if hasattr(rec, 'checker_output') and rec.checker_output:
            checker_score = rec.checker_output.get('confidence_adjustment', 0.0) + 0.5
            quality_factors.append(max(0.0, min(1.0, checker_score)))

        # Processing quality indicators
        if rec.latency_ms and rec.latency_ms < 5000:  # Fast processing bonus
            quality_factors.append(1.1)
        elif rec.latency_ms and rec.latency_ms > 30000:  # Slow processing penalty
            quality_factors.append(0.8)

        # Return geometric mean of quality factors
        if quality_factors:
            product = 1.0
            for factor in quality_factors:
                product *= factor
            return product ** (1.0 / len(quality_factors))

        return 0.5

    def _estimate_recommendation_cost(self, rec: LLMRecommendation,
                                    context: RecommendationContext) -> int:
        """Estimate cost in cents for this recommendation"""
        # Use actual cost if available
        if rec.provider_cost_cents:
            return rec.provider_cost_cents

        # Estimate based on token usage
        if hasattr(rec, 'token_usage') and rec.token_usage:
            # Rough estimate: $0.002 per 1K tokens for GPT-4 class models
            total_tokens = sum(rec.token_usage.values()) if isinstance(rec.token_usage, dict) else rec.token_usage
            estimated_cost = (total_tokens / 1000) * 0.2  # 20 cents per 1K tokens
            return int(estimated_cost * 100)  # Convert to cents

        # Fallback estimate based on complexity
        base_cost = 50  # 50 cents base cost
        if rec.authoritative_sources:
            base_cost += len(rec.authoritative_sources) * 10  # 10 cents per citation

        complexity = self._estimate_recommendation_complexity(rec)
        cost_multiplier = 0.5 + complexity  # 0.5x to 1.5x multiplier

        return int(base_cost * cost_multiplier)

    def _estimate_recommendation_complexity(self, rec: LLMRecommendation) -> float:
        """Estimate recommendation complexity (0.0 to 1.0)"""
        complexity = 0.5  # Base complexity

        # Citation complexity
        if rec.authoritative_sources:
            complexity += min(0.3, len(rec.authoritative_sources) * 0.1)

        # Content complexity (if available)
        if hasattr(rec, 'maker_output') and rec.maker_output:
            content = str(rec.maker_output)
            word_count = len(content.split())
            complexity += min(0.2, word_count / 1000)  # Up to 0.2 for 1000+ words

        # Structured complexity (nested objects, arrays)
        if rec.consensus and isinstance(rec.consensus, dict):
            nested_depth = self._calculate_json_depth(rec.consensus)
            complexity += min(0.2, nested_depth * 0.05)

        return min(1.0, complexity)

    def _calculate_json_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum depth of a JSON object"""
        if not isinstance(obj, (dict, list)):
            return current_depth

        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_json_depth(v, current_depth + 1) for v in obj.values())

        if isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_json_depth(item, current_depth + 1) for item in obj)

        return current_depth

    def _calculate_vector_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2[:len(vec1)])  # Truncate to match length

            # Pad shorter vector with zeros
            if len(v2) < len(v1):
                v2 = np.pad(v2, (0, len(v1) - len(v2)))

            # Calculate cosine similarity
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error calculating vector similarity: {str(e)}")
            return 0.0

    def _apply_budget_constraints(self, recommendations: List[ScoredRecommendation],
                                context: RecommendationContext) -> List[ScoredRecommendation]:
        """Apply budget constraints while maximizing value"""
        # Greedy knapsack approach - sort by value per cost ratio
        for rec in recommendations:
            if rec.estimated_cost_cents > 0:
                rec.value_per_cost = rec.composite_score / rec.estimated_cost_cents
            else:
                rec.value_per_cost = float('inf')  # Free recommendations have infinite value per cost

        # Sort by value per cost ratio
        recommendations.sort(key=lambda x: x.value_per_cost, reverse=True)

        # Select recommendations within budget
        selected = []
        remaining_budget = context.budget_cents

        for rec in recommendations:
            if rec.estimated_cost_cents <= remaining_budget:
                selected.append(rec)
                remaining_budget -= rec.estimated_cost_cents

        return selected

    def _apply_quality_filters(self, recommendations: List[ScoredRecommendation],
                             context: RecommendationContext) -> List[ScoredRecommendation]:
        """Apply quality filters based on policy and preferences"""
        filtered = []

        # Minimum confidence threshold
        min_confidence = getattr(settings, 'ONBOARDING_MIN_CONFIDENCE_THRESHOLD', 0.3)
        if context.preference_profile and context.preference_profile.weights:
            risk_tolerance = context.preference_profile.weights.get('risk_tolerance', 0.5)
            # Risk-averse users get higher threshold
            min_confidence = max(min_confidence, 0.6 - risk_tolerance * 0.3)

        for rec in recommendations:
            # Confidence filter
            if rec.confidence_adjusted < min_confidence:
                logger.debug(f"Filtered recommendation {rec.recommendation.recommendation_id} - "
                           f"low confidence {rec.confidence_adjusted}")
                continue

            # Quality score filter
            if rec.quality_score < 0.2:
                logger.debug(f"Filtered recommendation {rec.recommendation.recommendation_id} - "
                           f"low quality score {rec.quality_score}")
                continue

            # Citation requirement filter (if user requires citations)
            if (context.preference_profile and
                context.preference_profile.weights.get('citation_importance', 0.5) > 0.8 and
                not rec.recommendation.authoritative_sources):
                logger.debug(f"Filtered recommendation {rec.recommendation.recommendation_id} - "
                           f"missing required citations")
                continue

            filtered.append(rec)

        return filtered

    def _fallback_scoring(self, recommendations: List[LLMRecommendation],
                        context: RecommendationContext) -> List[ScoredRecommendation]:
        """Fallback scoring when main scoring fails"""
        scored = []
        for rec in recommendations:
            scored_rec = ScoredRecommendation(
                recommendation=rec,
                personalization_score=0.5,
                cost_score=0.5,
                quality_score=rec.confidence_score or 0.5,
                composite_score=rec.confidence_score or 0.5,
                ranking_factors={'fallback': True},
                estimated_cost_cents=100,  # Default estimate
                confidence_adjusted=rec.confidence_score or 0.5
            )
            scored.append(scored_rec)

        # Sort by confidence score
        scored.sort(key=lambda x: x.recommendation.confidence_score or 0.0, reverse=True)
        return scored[:context.max_recommendations]

    def _load_policy_registry(self) -> Dict[str, PolicyVersion]:
        """Load policy registry from configuration"""
        # This would typically load from database or configuration files
        default_policy = PolicyVersion('v1.0', {
            'prompt_templates': {
                'concise': "Provide concise, actionable recommendations.",
                'detailed': "Provide comprehensive, detailed recommendations with explanations.",
                'casual': "Provide friendly, conversational recommendations.",
                'formal': "Provide professional, formal recommendations."
            },
            'retrieval_params': {
                'k': 5,
                'hybrid_alpha': 0.7,
                'rerank_threshold': 0.6
            },
            'quality_thresholds': {
                'min_confidence': 0.3,
                'min_citation_count': 0,
                'max_cost_cents': 1000
            },
            'cost_limits': {
                'daily_budget_cents': 10000,
                'per_recommendation_limit_cents': 500
            }
        })

        return {'default': default_policy, 'v1.0': default_policy}


class BanditEngine:
    """
    Multi-armed bandit engine for experiment arm selection and optimization
    """

    def __init__(self):
        self.epsilon = getattr(settings, 'BANDIT_EPSILON', 0.1)  # Exploration rate
        self.default_prior = (1.0, 1.0)  # Beta distribution parameters
        self.min_samples_per_arm = getattr(settings, 'BANDIT_MIN_SAMPLES', 10)

    def select_arm(self, experiment: Experiment, context: RecommendationContext) -> str:
        """
        Select experiment arm using Thompson Sampling or epsilon-greedy

        Args:
            experiment: The experiment to select arm for
            context: User/session context

        Returns:
            str: Selected arm name
        """
        try:
            # Get current arm performance
            arm_performance = self._get_arm_performance(experiment, context)

            # Check safety constraints
            violations = experiment.check_safety_constraints(arm_performance)
            if violations:
                logger.warning(f"Safety violations in experiment {experiment.name}: {violations}")
                # Return control arm or best performing safe arm
                return self._get_safe_arm(experiment, arm_performance)

            # Use Thompson Sampling for arm selection
            if len(arm_performance) >= 2:  # Need at least 2 arms with data
                selected_arm = self._thompson_sampling(arm_performance, experiment)
            else:
                # Fallback to epsilon-greedy
                selected_arm = self._epsilon_greedy(arm_performance, experiment)

            logger.debug(f"Selected arm '{selected_arm}' for experiment {experiment.name}")
            return selected_arm

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error selecting arm for experiment {experiment.experiment_id}: {str(e)}")
            # Fallback to first arm
            return experiment.arms[0]['name'] if experiment.arms else 'control'

    def _get_arm_performance(self, experiment: Experiment,
                           context: RecommendationContext) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for each experiment arm"""
        cache_key = f"arm_perf_{experiment.experiment_id}_{context.client.id}"
        cached_performance = cache.get(cache_key)
        if cached_performance:
            return cached_performance

        performance = {}

        # Get assignments for this experiment
        assignments = ExperimentAssignment.objects.filter(
            experiment=experiment,
            client=context.client
        ).select_related('user')

        for assignment in assignments:
            arm_name = assignment.arm
            if arm_name not in performance:
                performance[arm_name] = {
                    'successes': 0,
                    'failures': 0,
                    'total_interactions': 0,
                    'avg_decision_time': 0.0,
                    'total_cost_cents': 0,
                    'error_rate': 0.0,
                    'complaint_rate': 0.0,
                    'daily_spend_cents': 0
                }

            # Get interactions for this assignment's user
            if assignment.user:
                user_interactions = self._get_user_interactions_for_experiment(
                    assignment.user, experiment, assignment.assigned_at
                )

                # Calculate metrics
                arm_metrics = performance[arm_name]
                for interaction in user_interactions:
                    arm_metrics['total_interactions'] += 1

                    if interaction.event_type == 'approved':
                        arm_metrics['successes'] += 1
                    elif interaction.event_type in ['rejected', 'escalated']:
                        arm_metrics['failures'] += 1

                    # Cost tracking
                    cost = interaction.metadata.get('cost_estimate', 0)
                    arm_metrics['total_cost_cents'] += cost

                    # Decision time
                    decision_time = interaction.get_time_to_decision()
                    if decision_time > 0:
                        current_avg = arm_metrics['avg_decision_time']
                        count = arm_metrics['total_interactions']
                        arm_metrics['avg_decision_time'] = (
                            (current_avg * (count - 1) + decision_time) / count
                        )

        # Calculate derived metrics
        for arm_name, metrics in performance.items():
            total = metrics['successes'] + metrics['failures']
            if total > 0:
                metrics['success_rate'] = metrics['successes'] / total
                metrics['failure_rate'] = metrics['failures'] / total
            else:
                metrics['success_rate'] = 0.5  # Prior
                metrics['failure_rate'] = 0.5

        # Cache results
        cache.set(cache_key, performance, 300)  # 5 minute cache
        return performance

    def _thompson_sampling(self, arm_performance: Dict[str, Dict],
                         experiment: Experiment) -> str:
        """Thompson Sampling arm selection"""
        arm_samples = {}

        for arm_name, perf in arm_performance.items():
            # Beta distribution parameters
            alpha = perf['successes'] + self.default_prior[0]
            beta = perf['failures'] + self.default_prior[1]

            # Sample from Beta distribution
            arm_samples[arm_name] = np.random.beta(alpha, beta)

        # Select arm with highest sample
        return max(arm_samples, key=arm_samples.get)

    def _epsilon_greedy(self, arm_performance: Dict[str, Dict],
                       experiment: Experiment) -> str:
        """Epsilon-greedy arm selection"""
        # Exploration vs exploitation
        if random.random() < self.epsilon:
            # Explore: random arm selection
            return random.choice([arm['name'] for arm in experiment.arms])
        else:
            # Exploit: select best performing arm
            best_arm = None
            best_performance = -1

            for arm_name, perf in arm_performance.items():
                success_rate = perf.get('success_rate', 0.5)
                if success_rate > best_performance:
                    best_performance = success_rate
                    best_arm = arm_name

            return best_arm or experiment.arms[0]['name']

    def _get_safe_arm(self, experiment: Experiment,
                     arm_performance: Dict[str, Dict]) -> str:
        """Get safest performing arm when constraints are violated"""
        safe_arms = []

        for arm_name, perf in arm_performance.items():
            # Check safety metrics
            error_rate = perf.get('error_rate', 0.0)
            complaint_rate = perf.get('complaint_rate', 0.0)
            daily_spend = perf.get('daily_spend_cents', 0)

            safety_constraints = experiment.safety_constraints or {}
            is_safe = (
                error_rate <= safety_constraints.get('max_error_rate', 0.1) and
                complaint_rate <= safety_constraints.get('max_complaint_rate', 0.05) and
                daily_spend <= safety_constraints.get('max_daily_spend_cents', 10000)
            )

            if is_safe:
                safe_arms.append((arm_name, perf.get('success_rate', 0.5)))

        if safe_arms:
            # Return best performing safe arm
            return max(safe_arms, key=lambda x: x[1])[0]
        else:
            # Fallback to control or first arm
            return 'control' if any(arm['name'] == 'control' for arm in experiment.arms) else experiment.arms[0]['name']

    def _get_user_interactions_for_experiment(self, user: People, experiment: Experiment,
                                            since_date: datetime):
        """Get user interactions relevant to experiment"""
        from apps.onboarding.models import RecommendationInteraction

        return RecommendationInteraction.objects.filter(
            session__user=user,
            occurred_at__gte=since_date,
            # Add experiment-specific filters if needed
        ).select_related('recommendation', 'session')

    def update_arm_performance(self, experiment: Experiment, arm_name: str,
                             outcome: str, metadata: Optional[Dict] = None):
        """Update arm performance with new outcome"""
        try:
            # This would update the performance tracking
            # In a full implementation, this might update a database table
            # or trigger a background job to recalculate performance metrics

            cache_key_pattern = f"arm_perf_{experiment.experiment_id}_*"
            # Invalidate related cache entries
            # Note: Django cache doesn't support pattern-based deletion by default
            # In production, you'd use Redis or implement a cache tagging system

            logger.info(f"Updated performance for arm {arm_name} in experiment {experiment.name}: {outcome}")

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error updating arm performance: {str(e)}")


class AssignmentService:
    """
    Manages experiment assignments for users and clients
    """

    def __init__(self):
        self.bandit_engine = BanditEngine()
        self.assignment_cache_timeout = 3600  # 1 hour

    def get_assignment(self, experiment: Experiment, user: People, client) -> ExperimentAssignment:
        """
        Get or create experiment assignment for user/client

        Args:
            experiment: The experiment
            user: User to assign (can be None for client-level assignment)
            client: Client/tenant

        Returns:
            ExperimentAssignment: Active assignment
        """
        try:
            # Check for existing assignment
            assignment_filter = {'experiment': experiment, 'client': client}
            if user:
                assignment_filter['user'] = user
            else:
                assignment_filter['user__isnull'] = True

            existing_assignment = ExperimentAssignment.objects.filter(
                **assignment_filter,
                expires_at__isnull=True  # Non-expiring assignments
            ).first()

            if existing_assignment and existing_assignment.is_active():
                return existing_assignment

            # Create new assignment
            context = RecommendationContext(user, client, None) if user else None
            selected_arm = self.bandit_engine.select_arm(experiment, context) if context else 'control'

            assignment = ExperimentAssignment.objects.create(
                experiment=experiment,
                user=user,
                client=client,
                arm=selected_arm,
                assignment_context={
                    'assignment_method': 'bandit_selection',
                    'user_id': user.id if user else None,
                    'client_id': client.id,
                    'timestamp': timezone.now().isoformat()
                }
            )

            logger.info(f"Created new assignment: {assignment}")
            return assignment

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error getting assignment for experiment {experiment.experiment_id}: {str(e)}")
            # Return default assignment
            return self._create_default_assignment(experiment, user, client)

    def _create_default_assignment(self, experiment: Experiment, user: People, client):
        """Create default assignment when normal assignment fails"""
        try:
            default_arm = experiment.arms[0]['name'] if experiment.arms else 'control'

            assignment = ExperimentAssignment.objects.create(
                experiment=experiment,
                user=user,
                client=client,
                arm=default_arm,
                assignment_context={
                    'assignment_method': 'default_fallback',
                    'error_recovery': True,
                    'timestamp': timezone.now().isoformat()
                }
            )
            return assignment
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to create default assignment: {str(e)}")
            raise


# Factory functions
def get_reranker() -> RecommendationReranker:
    """Get the recommendation reranker service"""
    return RecommendationReranker()


def get_bandit_engine() -> BanditEngine:
    """Get the multi-armed bandit engine"""
    return BanditEngine()


def get_assignment_service() -> AssignmentService:
    """Get the experiment assignment service"""
    return AssignmentService()