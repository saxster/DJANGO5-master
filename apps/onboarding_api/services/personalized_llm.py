"""
Personalized LLM service that integrates with the existing recommendation system

This service enhances the existing LLM implementations with personalization:
- Reranks recommendations based on user preferences
- Applies experiment configurations (A/B testing)
- Tracks cost and performance metrics
- Implements adaptive token budgeting
- Provides early exit and streaming capabilities
"""

import logging
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from apps.onboarding.models import (
    ConversationSession,
    LLMRecommendation,
)
from apps.peoples.models import People
from apps.onboarding_api.services.llm import (
    MakerLLM,
    CitationAwareMakerLLM,
    CitationAwareCheckerLLM,
    DummyMakerLLM,
    DummyCheckerLLM,
    LLMServiceException,
)
from apps.onboarding_api.services.personalization import (
    RecommendationContext,
    RecommendationReranker,
    get_reranker,
    get_assignment_service,
)
from apps.onboarding_api.services.learning import get_learning_service

logger = logging.getLogger(__name__)


class PersonalizedMakerLLM(MakerLLM):
    """
    Enhanced Maker LLM with personalization and experimentation
    """

    def __init__(self, base_llm: Optional[MakerLLM] = None):
        # Use provided base LLM or create default
        self.base_llm = base_llm or self._create_base_llm()

        # Personalization services
        self.reranker = get_reranker()
        self.assignment_service = get_assignment_service()
        self.learning_service = get_learning_service()

        # Configuration
        self.max_recommendations = getattr(settings, 'ONBOARDING_MAX_RECOMMENDATIONS', 5)
        self.default_budget_cents = getattr(settings, 'ONBOARDING_DEFAULT_BUDGET_CENTS', 1000)
        self.adaptive_budgeting = getattr(settings, 'ONBOARDING_ADAPTIVE_BUDGETING', True)
        self.enable_experiments = getattr(settings, 'ENABLE_ONBOARDING_EXPERIMENTS', True)

    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhanced context with experiment configuration"""
        try:
            # Get base enhanced context
            enhanced_context = self.base_llm.enhance_context(user_input, context, user)

            # Add experiment configuration
            if self.enable_experiments and user:
                experiment_config = self._get_experiment_configuration(user, context)
                enhanced_context['experiment_config'] = experiment_config

            # Add personalization context
            if user:
                personalization_context = self._get_personalization_context(user, context)
                enhanced_context['personalization'] = personalization_context

            return enhanced_context

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            logger.error(f"Error enhancing context with personalization: {str(e)}")
            return self.base_llm.enhance_context(user_input, context, user)

    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[Dict[str, Any]]:
        """Generate questions with personalization"""
        try:
            # Get base questions
            base_questions = self.base_llm.generate_questions(context, conversation_type)

            # Apply experiment configuration if available
            experiment_config = context.get('experiment_config', {})
            if experiment_config:
                base_questions = self._apply_experiment_config_to_questions(
                    base_questions, experiment_config
                )

            # Apply personalization
            personalization = context.get('personalization', {})
            if personalization:
                base_questions = self._personalize_questions(base_questions, personalization)

            return base_questions

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            logger.error(f"Error generating personalized questions: {str(e)}")
            return self.base_llm.generate_questions(context, conversation_type)

    def process_conversation_step(self, session: ConversationSession, user_input: str,
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Process conversation step with personalization and cost tracking"""
        start_time = timezone.now()

        try:
            # Create personalization context
            client = session.client
            budget = self._calculate_adaptive_budget(session.user, client, context)

            personalization_context = RecommendationContext(
                user=session.user,
                client=client,
                session=session,
                budget_cents=budget,
                max_recommendations=self._get_max_recommendations(session.user, client)
            )

            # Get base processing result
            base_result = self.base_llm.process_conversation_step(session, user_input, context)

            # Extract and create LLM recommendations
            recommendations = self._create_llm_recommendations(
                session, base_result, personalization_context
            )

            # Apply personalization reranking
            if recommendations:
                scored_recommendations = self.reranker.rerank_recommendations(
                    recommendations, personalization_context
                )

                # Update result with reranked recommendations
                base_result = self._update_result_with_reranked_recommendations(
                    base_result, scored_recommendations
                )

            # Track cost and performance
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            self._track_performance_metrics(session, base_result, processing_time, budget)

            return base_result

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            logger.error(f"Error in personalized conversation step: {str(e)}")
            # Fallback to base implementation
            return self.base_llm.process_conversation_step(session, user_input, context)

    def generate_recommendations(self, session: ConversationSession,
                               collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final recommendations with full personalization"""
        start_time = timezone.now()

        try:
            # Create personalization context
            client = session.client
            budget = self._calculate_adaptive_budget(session.user, client, collected_data)

            personalization_context = RecommendationContext(
                user=session.user,
                client=client,
                session=session,
                budget_cents=budget,
                max_recommendations=self._get_max_recommendations(session.user, client)
            )

            # Get base recommendations
            base_result = self.base_llm.generate_recommendations(session, collected_data)

            # Create LLM recommendation objects
            recommendations = self._create_llm_recommendations(
                session, base_result, personalization_context
            )

            # Apply personalization
            if recommendations:
                scored_recommendations = self.reranker.rerank_recommendations(
                    recommendations, personalization_context
                )

                # Update result with personalized recommendations
                base_result = self._update_result_with_final_recommendations(
                    base_result, scored_recommendations, personalization_context
                )

            # Track final performance
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            self._track_final_metrics(session, base_result, processing_time, budget)

            return base_result

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            logger.error(f"Error generating personalized recommendations: {str(e)}")
            # Fallback to base implementation
            return self.base_llm.generate_recommendations(session, collected_data)

    def _create_base_llm(self) -> MakerLLM:
        """Create base LLM based on configuration"""
        use_citations = getattr(settings, 'ENABLE_ONBOARDING_KB', False)

        if use_citations:
            return CitationAwareMakerLLM()
        else:
            return DummyMakerLLM()

    def _get_experiment_configuration(self, user: People, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get active experiment configuration for user"""
        try:
            if not self.enable_experiments:
                return {}

            # Get client from context
            client = context.get('client')
            if not client:
                return {}

            # Find active experiments for this user/client
            active_experiments = Experiment.objects.filter(
                status='running',
                scope__in=['global', 'tenant']
            )

            experiment_configs = {}

            for experiment in active_experiments:
                try:
                    assignment = self.assignment_service.get_assignment(experiment, user, client)
                    arm_config = assignment.get_arm_config()

                    if arm_config:
                        experiment_configs[experiment.name] = {
                            'experiment_id': str(experiment.experiment_id),
                            'arm': assignment.arm,
                            'config': arm_config.get('config', {}),
                            'primary_metric': experiment.primary_metric
                        }

                except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                    logger.warning(f"Error getting assignment for experiment {experiment.name}: {str(e)}")
                    continue

            return experiment_configs

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error getting experiment configuration: {str(e)}")
            return {}

    def _get_personalization_context(self, user: People, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get personalization context for user"""
        try:
            client = context.get('client')
            if not client:
                return {}

            # Get user learning summary
            learning_summary = self.learning_service.get_user_learning_summary(user, client, days=30)

            return {
                'learning_summary': learning_summary,
                'user_experience_level': self._infer_user_experience_level(user, learning_summary),
                'preferred_interaction_style': self._infer_interaction_style(learning_summary),
                'cost_sensitivity': self._infer_cost_sensitivity(learning_summary)
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error getting personalization context: {str(e)}")
            return {}

    def _apply_experiment_config_to_questions(self, questions: List[Dict[str, Any]],
                                            experiment_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply experiment configuration to questions"""
        modified_questions = questions.copy()

        for exp_name, exp_config in experiment_config.items():
            arm_config = exp_config.get('config', {})

            # Apply prompt style modifications
            if 'prompt_style' in arm_config:
                style = arm_config['prompt_style']
                modified_questions = self._apply_prompt_style(modified_questions, style)

            # Apply detail level modifications
            if 'detail_level' in arm_config:
                detail_level = arm_config['detail_level']
                modified_questions = self._apply_detail_level(modified_questions, detail_level)

        return modified_questions

    def _personalize_questions(self, questions: List[Dict[str, Any]],
                             personalization: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Personalize questions based on user preferences"""
        learning_summary = personalization.get('learning_summary', {})

        if learning_summary.get('status') != 'success':
            return questions

        metrics = learning_summary.get('metrics', {})

        # Adjust based on user patterns
        modified_questions = questions.copy()

        # If user typically spends little time on items, provide more concise questions
        avg_time_on_item = metrics.get('avg_time_on_item', 30)
        if avg_time_on_item < 20:  # Quick decision maker
            for question in modified_questions:
                if 'help_text' in question and len(question['help_text']) > 100:
                    question['help_text'] = question['help_text'][:100] + '...'

        # If user has high approval rate, reduce option count for efficiency
        approval_rate = metrics.get('approval_rate', 0.5)
        if approval_rate > 0.8:  # High approver
            for question in modified_questions:
                if question.get('type') == 'single_choice' and len(question.get('options', [])) > 5:
                    question['options'] = question['options'][:4] + ['Other']

        return modified_questions

    def _calculate_adaptive_budget(self, user: People, client, context: Dict[str, Any]) -> int:
        """Calculate adaptive budget based on user patterns and context"""
        if not self.adaptive_budgeting:
            return self.default_budget_cents

        try:
            # Get user learning summary for budget adaptation
            learning_summary = self.learning_service.get_user_learning_summary(user, client, days=7)

            base_budget = self.default_budget_cents

            if learning_summary.get('status') == 'success':
                metrics = learning_summary.get('metrics', {})

                # Adjust based on cost efficiency
                cost_efficiency = metrics.get('cost_efficiency_score', 0.5)
                if cost_efficiency > 0.8:
                    # User is cost-efficient, can afford higher budget
                    base_budget = int(base_budget * 1.2)
                elif cost_efficiency < 0.3:
                    # User is cost-inefficient, reduce budget
                    base_budget = int(base_budget * 0.8)

                # Adjust based on complexity preference
                if metrics.get('avg_time_on_item', 30) > 60:
                    # User prefers detailed analysis, increase budget
                    base_budget = int(base_budget * 1.1)

                # Adjust based on session urgency
                urgency = context.get('setup_urgency', 'no_deadline')
                if urgency == 'today':
                    # Urgent requests get higher budget for faster processing
                    base_budget = int(base_budget * 1.3)
                elif urgency == 'no_deadline':
                    # Non-urgent can use lower budget
                    base_budget = int(base_budget * 0.9)

            return max(100, min(5000, base_budget))  # Cap between $1 and $50

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error calculating adaptive budget: {str(e)}")
            return self.default_budget_cents

    def _get_max_recommendations(self, user: People, client) -> int:
        """Get maximum recommendations based on user preferences"""
        try:
            learning_summary = self.learning_service.get_user_learning_summary(user, client, days=30)

            if learning_summary.get('status') == 'success':
                metrics = learning_summary.get('metrics', {})

                # Users with high decision speed can handle more recommendations
                avg_decision_time = metrics.get('avg_decision_time', 300)
                if avg_decision_time < 120:  # Fast decision maker
                    return min(self.max_recommendations * 2, 10)
                elif avg_decision_time > 600:  # Slow decision maker
                    return max(self.max_recommendations // 2, 2)

            return self.max_recommendations

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error determining max recommendations: {str(e)}")
            return self.max_recommendations

    def _create_llm_recommendations(self, session: ConversationSession,
                                   base_result: Dict[str, Any],
                                   context: RecommendationContext) -> List[LLMRecommendation]:
        """Create LLMRecommendation objects from base result"""
        recommendations = []

        try:
            # Extract recommendations from base result
            base_recommendations = base_result.get('recommendations', {})

            if isinstance(base_recommendations, dict):
                # Single recommendation object
                rec = self._create_single_recommendation(
                    session, base_recommendations, base_result, context
                )
                if rec:
                    recommendations.append(rec)
            elif isinstance(base_recommendations, list):
                # Multiple recommendations
                for i, rec_data in enumerate(base_recommendations):
                    rec = self._create_single_recommendation(
                        session, rec_data, base_result, context, index=i
                    )
                    if rec:
                        recommendations.append(rec)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error creating LLM recommendations: {str(e)}")

        return recommendations

    def _create_single_recommendation(self, session: ConversationSession,
                                    rec_data: Dict[str, Any],
                                    base_result: Dict[str, Any],
                                    context: RecommendationContext,
                                    index: int = 0) -> Optional[LLMRecommendation]:
        """Create a single LLMRecommendation object"""
        try:
            # Get experiment configuration
            experiment_arm = None
            experiment_config = base_result.get('experiment_config', {})
            if experiment_config:
                # Use first experiment's arm (could be enhanced for multiple experiments)
                first_exp = list(experiment_config.values())[0]
                experiment_arm = first_exp.get('arm')

            recommendation = LLMRecommendation.objects.create(
                session=session,
                maker_output=rec_data,
                confidence_score=base_result.get('confidence_score', 0.5),
                authoritative_sources=base_result.get('citations', []),
                # Add personalization fields if they exist in the model
                # provider_used=base_result.get('provider_used'),
                # token_usage=base_result.get('token_usage'),
                # experiment_arm=experiment_arm
            )

            return recommendation

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error creating single recommendation: {str(e)}")
            return None

    def _update_result_with_reranked_recommendations(self, base_result: Dict[str, Any],
                                                   scored_recommendations) -> Dict[str, Any]:
        """Update result with reranked recommendations"""
        updated_result = base_result.copy()

        # Extract top recommendations
        top_recommendations = []
        total_estimated_cost = 0

        for scored_rec in scored_recommendations:
            rec_data = {
                'recommendation_id': str(scored_rec.recommendation.recommendation_id),
                'content': scored_rec.recommendation.maker_output,
                'confidence_score': scored_rec.confidence_adjusted,
                'personalization_score': scored_rec.personalization_score,
                'composite_score': scored_rec.composite_score,
                'estimated_cost_cents': scored_rec.estimated_cost_cents,
                'ranking_factors': scored_rec.ranking_factors
            }
            top_recommendations.append(rec_data)
            total_estimated_cost += scored_rec.estimated_cost_cents

        updated_result['recommendations'] = top_recommendations
        updated_result['personalization_applied'] = True
        updated_result['total_estimated_cost_cents'] = total_estimated_cost
        updated_result['recommendation_count'] = len(top_recommendations)

        # Update confidence with personalization boost
        if top_recommendations:
            avg_confidence = sum(r['confidence_score'] for r in top_recommendations) / len(top_recommendations)
            updated_result['confidence_score'] = min(1.0, avg_confidence * 1.1)  # 10% personalization boost

        return updated_result

    def _update_result_with_final_recommendations(self, base_result: Dict[str, Any],
                                                scored_recommendations,
                                                context: RecommendationContext) -> Dict[str, Any]:
        """Update result with final personalized recommendations"""
        updated_result = self._update_result_with_reranked_recommendations(
            base_result, scored_recommendations
        )

        # Add final personalization metadata
        updated_result['personalization_context'] = {
            'user_id': context.user.id,
            'client_id': context.client.id,
            'budget_cents': context.budget_cents,
            'max_recommendations': context.max_recommendations,
            'session_type': context.session_type,
            'language': context.language
        }

        # Add final metrics
        if context.preference_profile:
            updated_result['user_acceptance_rate'] = context.preference_profile.calculate_acceptance_rate()
            updated_result['preference_weights'] = context.preference_profile.weights

        return updated_result

    def _track_performance_metrics(self, session: ConversationSession,
                                 result: Dict[str, Any], processing_time_ms: float, budget_cents: int):
        """Track performance metrics for optimization"""
        try:
            # Prepare cost data
            cost_data = {
                'processing_time_ms': processing_time_ms,
                'budget_used_cents': result.get('total_estimated_cost_cents', 0),
                'budget_allocated_cents': budget_cents,
                'recommendation_count': result.get('recommendation_count', 0),
                'personalization_applied': result.get('personalization_applied', False)
            }

            # Track via learning service if recommendations exist
            recommendations = result.get('recommendations', [])
            for rec_data in recommendations:
                if 'recommendation_id' in rec_data:
                    self.learning_service.collect_cost_signal(
                        rec_data['recommendation_id'],
                        {
                            'latency_ms': processing_time_ms,
                            'cost_estimate': rec_data.get('estimated_cost_cents', 0) / 100.0,
                            'personalization_score': rec_data.get('personalization_score', 0.5)
                        }
                    )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error tracking performance metrics: {str(e)}")

    def _track_final_metrics(self, session: ConversationSession,
                           result: Dict[str, Any], processing_time_ms: float, budget_cents: int):
        """Track final recommendation metrics"""
        self._track_performance_metrics(session, result, processing_time_ms, budget_cents)

        # Additional final tracking
        try:
            logger.info(f"Generated personalized recommendations for session {session.session_id}: "
                       f"{result.get('recommendation_count', 0)} recommendations, "
                       f"${result.get('total_estimated_cost_cents', 0)/100:.2f} estimated cost, "
                       f"{processing_time_ms:.0f}ms processing time")
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error in final metrics logging: {str(e)}")

    def _apply_prompt_style(self, questions: List[Dict], style: str) -> List[Dict]:
        """Apply prompt style to questions"""
        if style == 'concise':
            for q in questions:
                if 'help_text' in q:
                    q['help_text'] = q['help_text'][:50] + '...' if len(q['help_text']) > 50 else q['help_text']
        elif style == 'detailed':
            for q in questions:
                if 'help_text' in q and len(q['help_text']) < 100:
                    q['help_text'] += ' Please provide detailed information for best results.'

        return questions

    def _apply_detail_level(self, questions: List[Dict], detail_level: str) -> List[Dict]:
        """Apply detail level to questions"""
        if detail_level == 'high':
            for q in questions:
                if q.get('type') == 'single_choice':
                    q['allow_other'] = True
        elif detail_level == 'low':
            for q in questions:
                if 'help_text' in q:
                    q['help_text'] = q['help_text'][:30] + '...' if len(q['help_text']) > 30 else q['help_text']

        return questions

    def _infer_user_experience_level(self, user: People, learning_summary: Dict) -> str:
        """Infer user experience level from learning data"""
        if learning_summary.get('status') != 'success':
            return 'beginner'

        metrics = learning_summary.get('metrics', {})
        total_interactions = metrics.get('total_interactions', 0)
        approval_rate = metrics.get('approval_rate', 0.5)
        avg_decision_time = metrics.get('avg_decision_time', 300)

        if total_interactions > 50 and approval_rate > 0.8 and avg_decision_time < 120:
            return 'expert'
        elif total_interactions > 20 and approval_rate > 0.6:
            return 'intermediate'
        else:
            return 'beginner'

    def _infer_interaction_style(self, learning_summary: Dict) -> str:
        """Infer preferred interaction style"""
        if learning_summary.get('status') != 'success':
            return 'standard'

        metrics = learning_summary.get('metrics', {})
        avg_time_on_item = metrics.get('avg_time_on_item', 30)
        avg_scroll_depth = metrics.get('avg_scroll_depth', 0.5)

        if avg_time_on_item > 60 and avg_scroll_depth > 0.7:
            return 'detailed'
        elif avg_time_on_item < 20 and avg_scroll_depth < 0.3:
            return 'quick'
        else:
            return 'standard'

    def _infer_cost_sensitivity(self, learning_summary: Dict) -> float:
        """Infer cost sensitivity from user behavior"""
        if learning_summary.get('status') != 'success':
            return 0.5

        metrics = learning_summary.get('metrics', {})
        cost_efficiency_score = metrics.get('cost_efficiency_score', 0.5)

        # High cost efficiency suggests high cost sensitivity
        return min(1.0, cost_efficiency_score + 0.2)


# Factory function
def get_personalized_llm_service() -> PersonalizedMakerLLM:
    """Get the personalized LLM service"""
    return PersonalizedMakerLLM()
