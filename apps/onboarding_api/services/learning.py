"""
Learning signals collection system for personalized recommendations

This module captures explicit and implicit user feedback to continuously
improve recommendation quality and personalization.

Learning Signals Captured:
- Explicit: approvals, rejections, modifications, rejection reasons
- Implicit: time to response, dwell time, back-and-forth count, escalations
- Contextual: language, industry, jurisdiction, site complexity, history
- Cost/latency: token counts, provider cost, step latencies
"""

import logging
from django.conf import settings
from django.utils import timezone
    PreferenceProfile,
    RecommendationInteraction,
    ConversationSession,
    LLMRecommendation
)
from apps.peoples.models import People
import numpy as np

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extracts features from user interactions for ML-based personalization
    """

    def __init__(self):
        self.feature_cache_timeout = getattr(settings, 'LEARNING_FEATURE_CACHE_TIMEOUT', 300)  # 5 minutes

        # Feature extraction weights and configurations
        self.config = {
            'time_decay_factor': 0.9,  # Decay factor for older interactions
            'min_interactions_for_profile': 3,
            'context_window_days': 30,
            'feature_vector_dimension': 128
        }

    def build_per_turn_features(self, interaction: RecommendationInteraction) -> Dict[str, Any]:
        """
        Build features for a single turn/interaction
        """
        features = {
            # Basic interaction features
            'event_type': interaction.event_type,
            'time_to_decision': interaction.get_time_to_decision(),
            'session_type': interaction.session.conversation_type,
            'user_is_staff': interaction.session.user.is_staff if interaction.session.user else False,
            'language': interaction.session.language,

            # Temporal features
            'hour_of_day': interaction.occurred_at.hour,
            'day_of_week': interaction.occurred_at.weekday(),
            'is_weekend': interaction.occurred_at.weekday() >= 5,

            # Recommendation features
            'confidence_score': interaction.recommendation.confidence_score,
            'has_citations': bool(interaction.recommendation.authoritative_sources),
            'citation_count': len(interaction.recommendation.authoritative_sources) if interaction.recommendation.authoritative_sources else 0,

            # Metadata features from interaction
            'time_on_item': interaction.metadata.get('time_on_item', 0),
            'scroll_depth': interaction.metadata.get('scroll_depth', 0.0),
            'token_usage': interaction.metadata.get('token_usage', 0),
            'cost_estimate': interaction.metadata.get('cost_estimate', 0.0),
            'provider_latency': interaction.metadata.get('provider_latency_ms', 0),
        }

        # Context features from session
        if interaction.session.context_data:
            features.update({
                'context_complexity': self._calculate_context_complexity(interaction.session.context_data),
                'has_prior_history': bool(interaction.session.context_data.get('prior_sessions')),
                'site_type': interaction.session.context_data.get('business_unit_type', 'unknown'),
                'expected_users': interaction.session.context_data.get('expected_users', 0),
                'security_level': interaction.session.context_data.get('security_level', 'basic'),
            })

        return features

    def build_aggregate_features(self, user: People, client, window_days: int = 30) -> Dict[str, Any]:
        """
        Build aggregate features across user's interaction history
        """
        cache_key = f"agg_features_{user.id}_{client.id}_{window_days}"
        cached_features = cache.get(cache_key)
        if cached_features:
            return cached_features

        # Query interactions in time window
        cutoff_date = timezone.now() - timedelta(days=window_days)
        interactions = RecommendationInteraction.objects.filter(
            session__user=user,
            session__client=client,
            occurred_at__gte=cutoff_date
        ).select_related('recommendation', 'session')

        if not interactions.exists():
            return self._get_default_aggregate_features()

        # Calculate aggregate metrics
        total_interactions = interactions.count()
        approval_rate = interactions.filter(event_type='approved').count() / total_interactions
        rejection_rate = interactions.filter(event_type='rejected').count() / total_interactions
        modification_rate = interactions.filter(event_type='modified').count() / total_interactions
        escalation_rate = interactions.filter(event_type='escalated').count() / total_interactions

        # Time-based metrics
        decision_times = [i.get_time_to_decision() for i in interactions if i.get_time_to_decision() > 0]
        avg_decision_time = np.mean(decision_times) if decision_times else 0
        decision_time_variance = np.var(decision_times) if decision_times else 0

        # Engagement metrics
        avg_time_on_item = interactions.aggregate(avg=Avg('metadata__time_on_item'))['avg'] or 0
        avg_scroll_depth = interactions.aggregate(avg=Avg('metadata__scroll_depth'))['avg'] or 0

        # Cost and efficiency metrics
        total_token_usage = sum(i.metadata.get('token_usage', 0) for i in interactions)
        total_cost = sum(i.metadata.get('cost_estimate', 0) for i in interactions)
        avg_cost_per_decision = total_cost / max(1, len(decision_times))

        # Session patterns
        session_types = list(interactions.values_list('session__conversation_type', flat=True))
        most_common_session_type = max(set(session_types), key=session_types.count) if session_types else 'unknown'

        # Temporal patterns
        interaction_hours = [i.occurred_at.hour for i in interactions]
        preferred_hours = self._find_preferred_time_windows(interaction_hours)

        features = {
            # Core metrics
            'total_interactions': total_interactions,
            'approval_rate': approval_rate,
            'rejection_rate': rejection_rate,
            'modification_rate': modification_rate,
            'escalation_rate': escalation_rate,

            # Timing patterns
            'avg_decision_time': avg_decision_time,
            'decision_time_variance': decision_time_variance,
            'preferred_hours': preferred_hours,

            # Engagement patterns
            'avg_time_on_item': avg_time_on_item,
            'avg_scroll_depth': avg_scroll_depth,
            'engagement_score': self._calculate_engagement_score(avg_time_on_item, avg_scroll_depth),

            # Cost efficiency
            'total_token_usage': total_token_usage,
            'total_cost': total_cost,
            'avg_cost_per_decision': avg_cost_per_decision,
            'cost_efficiency_score': approval_rate / max(0.01, avg_cost_per_decision),

            # Session patterns
            'most_common_session_type': most_common_session_type,
            'session_diversity': len(set(session_types)) / max(1, len(session_types)),

            # Recommendation patterns
            'preferred_confidence_level': self._calculate_preferred_confidence(interactions),
            'citation_preference': self._calculate_citation_preference(interactions),

            # Risk profile
            'risk_tolerance': self._calculate_risk_tolerance(interactions),
            'detail_preference': self._calculate_detail_preference(interactions),
        }

        # Cache for future use
        cache.set(cache_key, features, self.feature_cache_timeout)
        return features

    def extract_contextual_features(self, session: ConversationSession) -> Dict[str, Any]:
        """
        Extract contextual features from session environment
        """
        features = {
            # Basic context
            'language': session.language,
            'conversation_type': session.conversation_type,
            'session_state': session.current_state,

            # User context
            'user_is_staff': session.user.is_staff if session.user else False,
            'user_experience_level': self._infer_user_experience(session.user),

            # Client/tenant context
            'client_size': self._estimate_client_size(session.client),
            'client_industry': self._infer_client_industry(session.client),
            'client_complexity': self._calculate_client_complexity(session.client),

            # Geographic/jurisdictional context
            'jurisdiction': self._infer_jurisdiction(session.client),
            'timezone_offset': self._get_timezone_offset(session.client),
        }

        # Add session-specific context
        if session.context_data:
            features.update({
                'setup_urgency': session.context_data.get('setup_urgency', 'no_deadline'),
                'business_unit_type': session.context_data.get('business_unit_type', 'office'),
                'expected_users': session.context_data.get('expected_users', 10),
                'security_requirements': session.context_data.get('security_level', 'basic'),
                'compliance_requirements': bool(session.context_data.get('compliance_needed', False)),
            })

        return features

    def create_preference_vector(self, user: People, client) -> List[float]:
        """
        Create a dense preference vector for ML-based personalization
        """
        try:
            # Get aggregate features
            features = self.build_aggregate_features(user, client)

            # Convert to vector representation
            vector = self._features_to_vector(features)

            # Normalize vector
            vector = self._normalize_vector(vector)

            return vector.tolist()[:self.config['feature_vector_dimension']]

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error creating preference vector for user {user.id}: {str(e)}")
            return [0.0] * self.config['feature_vector_dimension']

    def _calculate_context_complexity(self, context_data: Dict[str, Any]) -> float:
        """Calculate complexity score for session context"""
        complexity_score = 0.0

        # More fields = higher complexity
        complexity_score += len(context_data) * 0.1

        # Specific complexity indicators
        if context_data.get('expected_users', 0) > 100:
            complexity_score += 0.3

        if context_data.get('security_level') in ['enhanced', 'high_security']:
            complexity_score += 0.2

        if context_data.get('compliance_needed'):
            complexity_score += 0.3

        return min(1.0, complexity_score)

    def _get_default_aggregate_features(self) -> Dict[str, Any]:
        """Default features for users with no interaction history"""
        return {
            'total_interactions': 0,
            'approval_rate': 0.5,  # Neutral default
            'rejection_rate': 0.0,
            'modification_rate': 0.0,
            'escalation_rate': 0.0,
            'avg_decision_time': 300.0,  # 5 minutes default
            'decision_time_variance': 0.0,
            'preferred_hours': [9, 10, 11, 14, 15],  # Business hours
            'avg_time_on_item': 30.0,
            'avg_scroll_depth': 0.5,
            'engagement_score': 0.5,
            'total_token_usage': 0,
            'total_cost': 0.0,
            'avg_cost_per_decision': 0.0,
            'cost_efficiency_score': 0.5,
            'most_common_session_type': 'initial_setup',
            'session_diversity': 0.0,
            'preferred_confidence_level': 0.7,
            'citation_preference': 0.5,
            'risk_tolerance': 0.5,
            'detail_preference': 0.5,
        }

    def _find_preferred_time_windows(self, hours: List[int]) -> List[int]:
        """Find preferred interaction time windows"""
        if not hours:
            return [9, 10, 11, 14, 15]  # Default business hours

        # Count frequency of each hour
        hour_counts = {}
        for hour in hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

        # Return top 5 hours
        return sorted(hour_counts.keys(), key=lambda x: hour_counts[x], reverse=True)[:5]

    def _calculate_engagement_score(self, time_on_item: float, scroll_depth: float) -> float:
        """Calculate engagement score from time and scroll metrics"""
        # Normalize time (assume 60 seconds is high engagement)
        time_score = min(1.0, time_on_item / 60.0)

        # Scroll depth is already normalized (0-1)
        scroll_score = scroll_depth

        # Weighted average
        return 0.6 * time_score + 0.4 * scroll_score

    def _calculate_preferred_confidence(self, interactions) -> float:
        """Calculate user's preferred confidence level"""
        approved_recs = [i.recommendation for i in interactions if i.event_type == 'approved']
        if not approved_recs:
            return 0.7  # Default

        confidence_scores = [r.confidence_score for r in approved_recs if r.confidence_score]
        return np.mean(confidence_scores) if confidence_scores else 0.7

    def _calculate_citation_preference(self, interactions) -> float:
        """Calculate user's preference for citations"""
        total = interactions.count()
        if total == 0:
            return 0.5

        # Count interactions with cited recommendations that were approved
        cited_approved = 0
        uncited_approved = 0

        for interaction in interactions:
            has_citations = bool(interaction.recommendation.authoritative_sources)
            if interaction.event_type == 'approved':
                if has_citations:
                    cited_approved += 1
                else:
                    uncited_approved += 1

        if cited_approved + uncited_approved == 0:
            return 0.5

        return cited_approved / (cited_approved + uncited_approved)

    def _calculate_risk_tolerance(self, interactions) -> float:
        """Calculate user's risk tolerance based on approval patterns"""
        high_risk_approved = 0
        total_decisions = 0

        for interaction in interactions:
            if interaction.event_type in ['approved', 'rejected']:
                total_decisions += 1

                # High risk indicators: low confidence, no citations, high complexity
                risk_score = 0
                if interaction.recommendation.confidence_score < 0.6:
                    risk_score += 1
                if not interaction.recommendation.authoritative_sources:
                    risk_score += 1
                if interaction.metadata.get('context_complexity', 0) > 0.7:
                    risk_score += 1

                if risk_score >= 2 and interaction.event_type == 'approved':
                    high_risk_approved += 1

        if total_decisions == 0:
            return 0.5  # Default moderate risk tolerance

        return high_risk_approved / total_decisions

    def _calculate_detail_preference(self, interactions) -> float:
        """Calculate user's preference for detailed information"""
        total_viewed = 0
        high_engagement = 0

        for interaction in interactions:
            if interaction.event_type in ['viewed', 'clicked_detail']:
                total_viewed += 1

                # High detail engagement: long time on item, high scroll depth
                time_on_item = interaction.metadata.get('time_on_item', 0)
                scroll_depth = interaction.metadata.get('scroll_depth', 0)

                if time_on_item > 45 or scroll_depth > 0.7:  # 45 seconds or 70% scroll
                    high_engagement += 1

        if total_viewed == 0:
            return 0.5

        return high_engagement / total_viewed

    def _infer_user_experience(self, user: People) -> str:
        """Infer user experience level"""
        if not user:
            return 'unknown'

        # Check user profile for experience indicators
        if user.is_staff or user.is_superuser:
            return 'expert'

        # Could check login frequency, tenure, etc.
        # For now, simple heuristic
        if hasattr(user, 'date_joined'):
            days_since_joined = (timezone.now() - user.date_joined).days
            if days_since_joined > 365:
                return 'experienced'
            elif days_since_joined > 30:
                return 'intermediate'

        return 'beginner'

    def _estimate_client_size(self, client) -> str:
        """Estimate client organization size"""
        # Use business unit preferences to estimate size
        prefs = client.bupreferences or {}

        max_users = prefs.get('no_of_users_allowed_both', 0) + prefs.get('no_of_users_allowed_web', 0)

        if max_users > 1000:
            return 'enterprise'
        elif max_users > 100:
            return 'medium'
        elif max_users > 10:
            return 'small'
        else:
            return 'micro'

    def _infer_client_industry(self, client) -> str:
        """Infer client industry from business unit configuration"""
        # Could use business unit names, types, etc.
        bu_name = client.buname.lower()

        if any(term in bu_name for term in ['hospital', 'clinic', 'medical', 'health']):
            return 'healthcare'
        elif any(term in bu_name for term in ['bank', 'finance', 'credit']):
            return 'finance'
        elif any(term in bu_name for term in ['school', 'university', 'education']):
            return 'education'
        elif any(term in bu_name for term in ['factory', 'manufacturing', 'production']):
            return 'manufacturing'
        elif any(term in bu_name for term in ['retail', 'store', 'shop']):
            return 'retail'
        else:
            return 'general'

    def _calculate_client_complexity(self, client) -> float:
        """Calculate client setup complexity"""
        complexity = 0.0
        prefs = client.bupreferences or {}

        # Number of features enabled
        enabled_features = sum(1 for v in prefs.values() if isinstance(v, bool) and v)
        complexity += min(0.5, enabled_features * 0.05)

        # Multi-site complexity
        if client.children.count() > 5:
            complexity += 0.3
        elif client.children.count() > 1:
            complexity += 0.1

        # Security features
        if client.gpsenable or client.enablesleepingguard:
            complexity += 0.2

        return min(1.0, complexity)

    def _infer_jurisdiction(self, client) -> str:
        """Infer legal jurisdiction from client configuration"""
        # Could use timezone, address, or other indicators
        # For now, return a default
        return 'unknown'

    def _get_timezone_offset(self, client) -> float:
        """Get timezone offset for client"""
        prefs = client.bupreferences or {}
        timezone_str = prefs.get('clienttimezone', '')

        # Parse timezone offset (simplified)
        if '+' in timezone_str or '-' in timezone_str:
            try:
                # Extract numeric offset
                offset_str = timezone_str.split('UTC')[1] if 'UTC' in timezone_str else '0'
                return float(offset_str)
            except:
                return 0.0

        return 0.0

    def _features_to_vector(self, features: Dict[str, Any]) -> np.ndarray:
        """Convert feature dictionary to dense vector"""
        # This is a simplified mapping - in production would use proper feature engineering
        vector_elements = []

        # Behavioral features (normalized 0-1)
        vector_elements.extend([
            min(1.0, features.get('approval_rate', 0.5)),
            min(1.0, features.get('rejection_rate', 0.0)),
            min(1.0, features.get('modification_rate', 0.0)),
            min(1.0, features.get('escalation_rate', 0.0)),
            min(1.0, features.get('engagement_score', 0.5)),
            min(1.0, features.get('risk_tolerance', 0.5)),
            min(1.0, features.get('detail_preference', 0.5)),
            min(1.0, features.get('citation_preference', 0.5)),
        ])

        # Timing features (log-normalized)
        vector_elements.extend([
            min(1.0, np.log(features.get('avg_decision_time', 300) + 1) / 10),
            min(1.0, features.get('cost_efficiency_score', 0.5)),
        ])

        # Categorical features (one-hot encoded subsets)
        session_type_map = {
            'initial_setup': [1, 0, 0, 0],
            'config_update': [0, 1, 0, 0],
            'troubleshooting': [0, 0, 1, 0],
            'feature_request': [0, 0, 0, 1],
        }
        vector_elements.extend(session_type_map.get(features.get('most_common_session_type'), [0, 0, 0, 0]))

        # Pad or truncate to desired dimension
        while len(vector_elements) < self.config['feature_vector_dimension']:
            vector_elements.append(0.0)

        return np.array(vector_elements[:self.config['feature_vector_dimension']])

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """L2 normalize the feature vector"""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm


class PreferenceUpdater:
    """
    Updates user preference profiles based on learning signals
    """

    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        self.update_threshold = getattr(settings, 'LEARNING_UPDATE_THRESHOLD', 5)  # Min interactions before update

    def update_preference_profile(self, user: People, client, interaction: RecommendationInteraction,
                                safe_mode: bool = True):
        """
        Update user's preference profile based on new interaction

        Args:
            user: User who made the interaction
            client: Client/tenant context
            interaction: The interaction event
            safe_mode: If True, applies safety checks and gradual updates
        """
        try:
            # Get or create preference profile
            profile, created = PreferenceProfile.objects.get_or_create(
                user=user,
                client=client,
                defaults={
                    'weights': self._get_default_weights(),
                    'stats': {},
                    'preference_vector': None
                }
            )

            # Update learning statistics
            self._update_stats(profile, interaction)

            # Check if we have enough data for meaningful updates
            total_interactions = sum(profile.stats.get(k, 0) for k in ['approvals', 'rejections', 'modifications'])

            if total_interactions >= self.update_threshold:
                # Update preference weights
                self._update_preference_weights(profile, interaction, safe_mode)

                # Update preference vector
                self._update_preference_vector(profile, user, client)

            profile.save()

            logger.info(f"Updated preference profile for user {user.id} - {interaction.event_type}")

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error updating preference profile for user {user.id}: {str(e)}")
            if not safe_mode:
                raise

    def _update_stats(self, profile: PreferenceProfile, interaction: RecommendationInteraction):
        """Update statistical counters in preference profile"""
        if not profile.stats:
            profile.stats = {}

        # Map interaction event types to stat keys
        event_to_stat = {
            'approved': 'approvals',
            'rejected': 'rejections',
            'modified': 'modifications',
            'escalated': 'escalations'
        }

        stat_key = event_to_stat.get(interaction.event_type)
        if stat_key:
            profile.stats[stat_key] = profile.stats.get(stat_key, 0) + 1

        # Update timing statistics
        if interaction.event_type in ['approved', 'rejected', 'modified']:
            decision_time = interaction.get_time_to_decision()
            if decision_time > 0:
                times = profile.stats.get('decision_times', [])
                times.append(decision_time)
                # Keep only last 50 decision times
                profile.stats['decision_times'] = times[-50:]

        # Update metadata statistics
        if interaction.metadata:
            for key in ['time_on_item', 'scroll_depth', 'token_usage', 'cost_estimate']:
                if key in interaction.metadata:
                    stat_key = f"avg_{key}"
                    current_avg = profile.stats.get(stat_key, 0)
                    current_count = profile.stats.get(f"{stat_key}_count", 0)

                    # Rolling average
                    new_value = interaction.metadata[key]
                    new_avg = (current_avg * current_count + new_value) / (current_count + 1)

                    profile.stats[stat_key] = new_avg
                    profile.stats[f"{stat_key}_count"] = current_count + 1

    def _update_preference_weights(self, profile: PreferenceProfile, interaction: RecommendationInteraction,
                                 safe_mode: bool):
        """Update preference weights based on interaction patterns"""
        if not profile.weights:
            profile.weights = self._get_default_weights()

        # Learning rate (smaller for safety in production)
        learning_rate = 0.1 if safe_mode else 0.2

        # Update weights based on interaction type and recommendation characteristics
        rec = interaction.recommendation

        # Cost sensitivity updates
        if 'cost_estimate' in interaction.metadata:
            cost = interaction.metadata['cost_estimate']
            if interaction.event_type == 'approved' and cost > 0:
                # User approved despite cost - reduce cost sensitivity
                profile.weights['cost_sensitivity'] = max(0.1,
                    profile.weights.get('cost_sensitivity', 0.5) - learning_rate * 0.1)
            elif interaction.event_type == 'rejected' and cost > 0:
                # User rejected due to cost - increase cost sensitivity
                profile.weights['cost_sensitivity'] = min(1.0,
                    profile.weights.get('cost_sensitivity', 0.5) + learning_rate * 0.1)

        # Risk tolerance updates
        if rec.confidence_score:
            if interaction.event_type == 'approved' and rec.confidence_score < 0.6:
                # Approved low confidence - increase risk tolerance
                profile.weights['risk_tolerance'] = min(1.0,
                    profile.weights.get('risk_tolerance', 0.5) + learning_rate * 0.1)
            elif interaction.event_type == 'rejected' and rec.confidence_score < 0.6:
                # Rejected low confidence - decrease risk tolerance
                profile.weights['risk_tolerance'] = max(0.1,
                    profile.weights.get('risk_tolerance', 0.5) - learning_rate * 0.1)

        # Detail level preferences
        if interaction.metadata.get('time_on_item', 0) > 60:  # 1 minute = high detail engagement
            if interaction.event_type == 'approved':
                profile.weights['detail_level'] = min(1.0,
                    profile.weights.get('detail_level', 0.5) + learning_rate * 0.05)

        # Language preference reinforcement
        session_lang = interaction.session.language
        if session_lang and interaction.event_type == 'approved':
            profile.weights['language_pref'] = session_lang

    def _update_preference_vector(self, profile: PreferenceProfile, user: People, client):
        """Update the ML preference vector"""
        try:
            new_vector = self.feature_extractor.create_preference_vector(user, client)

            if profile.preference_vector and len(profile.preference_vector) == len(new_vector):
                # Exponential moving average with existing vector
                alpha = 0.3  # Learning rate for vector updates
                updated_vector = []
                for old_val, new_val in zip(profile.preference_vector, new_vector):
                    updated_vector.append(alpha * new_val + (1 - alpha) * old_val)
                profile.preference_vector = updated_vector
            else:
                # First time or dimension mismatch - use new vector
                profile.preference_vector = new_vector

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error updating preference vector: {str(e)}")

    def _get_default_weights(self) -> Dict[str, Any]:
        """Get default preference weights for new users"""
        return {
            'cost_sensitivity': 0.5,    # 0=cost-insensitive, 1=very cost-sensitive
            'risk_tolerance': 0.5,      # 0=risk-averse, 1=risk-accepting
            'detail_level': 0.5,        # 0=brief, 1=detailed
            'language_pref': 'en',      # Primary language preference
            'citation_importance': 0.5, # 0=citations not important, 1=citations required
            'response_speed_pref': 0.5, # 0=accuracy over speed, 1=speed over accuracy
        }


class LearningSignalsCollector:
    """
    Main service for collecting and processing learning signals
    """

    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        self.preference_updater = PreferenceUpdater()

        # Configuration
        self.config = {
            'async_processing': getattr(settings, 'LEARNING_ASYNC_PROCESSING', True),
            'batch_size': getattr(settings, 'LEARNING_BATCH_SIZE', 100),
            'enable_implicit_signals': getattr(settings, 'LEARNING_IMPLICIT_SIGNALS', True),
            'enable_cost_tracking': getattr(settings, 'LEARNING_COST_TRACKING', True),
        }

    def collect_explicit_signal(self, session_id: str, recommendation_id: str, event_type: str,
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Collect explicit user feedback signals (approvals, rejections, modifications)

        Args:
            session_id: ConversationSession ID
            recommendation_id: LLMRecommendation ID
            event_type: Type of event ('approved', 'rejected', 'modified', 'escalated')
            metadata: Additional context (rejection_reason, modifications, etc.)

        Returns:
            bool: True if signal was successfully collected
        """
        try:
            # Validate inputs
            if not all([session_id, recommendation_id, event_type]):
                logger.error("Missing required parameters for explicit signal collection")
                return False

            # Get session and recommendation
            session = ConversationSession.objects.select_related('user', 'client').get(
                session_id=session_id
            )
            recommendation = LLMRecommendation.objects.get(
                recommendation_id=recommendation_id
            )

            # Create interaction record
            interaction = RecommendationInteraction.objects.create(
                session=session,
                recommendation=recommendation,
                event_type=event_type,
                metadata=metadata or {}
            )

            # Update preference profile
            if session.user:
                self.preference_updater.update_preference_profile(
                    session.user, session.client, interaction
                )

            # Trigger async processing if enabled
            if self.config['async_processing']:
                self._queue_async_processing(interaction)

            logger.info(f"Collected explicit signal: {event_type} for recommendation {recommendation_id}")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error collecting explicit signal: {str(e)}")
            return False

    def collect_implicit_signal(self, session_id: str, recommendation_id: str,
                              interaction_data: Dict[str, Any]) -> bool:
        """
        Collect implicit behavioral signals (time on item, scroll depth, etc.)

        Args:
            session_id: ConversationSession ID
            recommendation_id: LLMRecommendation ID (optional for session-level signals)
            interaction_data: Behavioral data (time_on_item, scroll_depth, click_patterns)

        Returns:
            bool: True if signal was successfully collected
        """
        if not self.config['enable_implicit_signals']:
            return True

        try:
            session = ConversationSession.objects.select_related('user', 'client').get(
                session_id=session_id
            )

            event_type = self._determine_implicit_event_type(interaction_data)

            # Handle recommendation-specific vs session-level signals
            if recommendation_id:
                recommendation = LLMRecommendation.objects.get(
                    recommendation_id=recommendation_id
                )

                interaction = RecommendationInteraction.objects.create(
                    session=session,
                    recommendation=recommendation,
                    event_type=event_type,
                    metadata=interaction_data
                )
            else:
                # Session-level implicit signal - create with most recent recommendation
                recent_rec = LLMRecommendation.objects.filter(session=session).order_by('-cdtz').first()
                if recent_rec:
                    interaction = RecommendationInteraction.objects.create(
                        session=session,
                        recommendation=recent_rec,
                        event_type=event_type,
                        metadata=interaction_data
                    )

            logger.debug(f"Collected implicit signal: {event_type} for session {session_id}")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error collecting implicit signal: {str(e)}")
            return False

    def collect_cost_signal(self, recommendation_id: str, cost_data: Dict[str, Any]) -> bool:
        """
        Collect cost and latency signals for optimization

        Args:
            recommendation_id: LLMRecommendation ID
            cost_data: Cost breakdown (provider_cost_cents, token_usage, latency_ms)

        Returns:
            bool: True if signal was successfully collected
        """
        if not self.config['enable_cost_tracking']:
            return True

        try:
            recommendation = LLMRecommendation.objects.get(
                recommendation_id=recommendation_id
            )

            # Update recommendation with cost data
            recommendation.provider_cost_cents = cost_data.get('provider_cost_cents')
            recommendation.latency_ms = cost_data.get('latency_ms')

            # Update token usage if provided
            if 'token_usage' in cost_data:
                recommendation.token_usage = cost_data['token_usage']

            recommendation.save()

            logger.debug(f"Collected cost signal for recommendation {recommendation_id}")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error collecting cost signal: {str(e)}")
            return False

    def get_user_learning_summary(self, user: People, client, days: int = 30) -> Dict[str, Any]:
        """
        Get learning summary for a user within a time window

        Args:
            user: User to analyze
            client: Client/tenant context
            days: Time window in days

        Returns:
            Dict with learning insights and metrics
        """
        try:
            # Get preference profile
            profile = PreferenceProfile.objects.filter(user=user, client=client).first()

            # Get recent interactions
            cutoff_date = timezone.now() - timedelta(days=days)
            interactions = RecommendationInteraction.objects.filter(
                session__user=user,
                session__client=client,
                occurred_at__gte=cutoff_date
            ).order_by('-occurred_at')

            # Calculate metrics
            total_interactions = interactions.count()
            if total_interactions == 0:
                return {'status': 'insufficient_data', 'message': 'No interactions in time window'}

            # Aggregate metrics
            metrics = {
                'total_interactions': total_interactions,
                'approval_rate': interactions.filter(event_type='approved').count() / total_interactions,
                'rejection_rate': interactions.filter(event_type='rejected').count() / total_interactions,
                'modification_rate': interactions.filter(event_type='modified').count() / total_interactions,
                'escalation_rate': interactions.filter(event_type='escalated').count() / total_interactions,
            }

            # Time-based analysis
            decision_interactions = interactions.filter(
                event_type__in=['approved', 'rejected', 'modified']
            )
            if decision_interactions.exists():
                decision_times = [i.get_time_to_decision() for i in decision_interactions]
                decision_times = [t for t in decision_times if t > 0]
                if decision_times:
                    metrics.update({
                        'avg_decision_time': np.mean(decision_times),
                        'decision_time_std': np.std(decision_times),
                        'median_decision_time': np.median(decision_times),
                    })

            # Engagement metrics
            engagement_data = []
            for interaction in interactions.filter(event_type__in=['viewed', 'clicked_detail']):
                time_on_item = interaction.metadata.get('time_on_item', 0)
                scroll_depth = interaction.metadata.get('scroll_depth', 0)
                if time_on_item > 0 or scroll_depth > 0:
                    engagement_data.append({
                        'time_on_item': time_on_item,
                        'scroll_depth': scroll_depth
                    })

            if engagement_data:
                metrics['avg_time_on_item'] = np.mean([e['time_on_item'] for e in engagement_data])
                metrics['avg_scroll_depth'] = np.mean([e['scroll_depth'] for e in engagement_data])

            # Preference analysis
            if profile:
                metrics['preference_weights'] = profile.weights
                metrics['acceptance_rate'] = profile.calculate_acceptance_rate()
                metrics['last_updated'] = profile.last_updated.isoformat()

            return {
                'status': 'success',
                'user_id': user.id,
                'client_id': client.id,
                'analysis_period_days': days,
                'metrics': metrics,
                'insights': self._generate_insights(metrics, profile)
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error generating learning summary for user {user.id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _determine_implicit_event_type(self, interaction_data: Dict[str, Any]) -> str:
        """Determine event type from implicit interaction data"""
        time_on_item = interaction_data.get('time_on_item', 0)
        scroll_depth = interaction_data.get('scroll_depth', 0)

        if time_on_item > 30 or scroll_depth > 0.5:
            return 'clicked_detail'  # High engagement
        elif time_on_item > 5:
            return 'viewed'  # Basic viewing
        else:
            return 'abandoned'  # Quick exit

    def _queue_async_processing(self, interaction: RecommendationInteraction):
        """Queue interaction for async batch processing"""
        # In production, this would use Celery or similar
        # For now, we'll process immediately
        try:
            self._process_interaction_async(interaction)
        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in async processing: {str(e)}")

    def _process_interaction_async(self, interaction: RecommendationInteraction):
        """Async processing of interaction for advanced analytics"""
        # This could include:
        # - Feature extraction and vector updates
        # - Anomaly detection
        # - A/B test analysis
        # - Cost optimization analysis
        pass

    def _generate_insights(self, metrics: Dict[str, Any], profile: Optional[PreferenceProfile]) -> List[str]:
        """Generate human-readable insights from metrics"""
        insights = []

        # Approval rate insights
        approval_rate = metrics.get('approval_rate', 0)
        if approval_rate > 0.8:
            insights.append("High approval rate indicates strong recommendation quality match")
        elif approval_rate < 0.4:
            insights.append("Low approval rate suggests need for better personalization")

        # Decision time insights
        avg_decision_time = metrics.get('avg_decision_time')
        if avg_decision_time:
            if avg_decision_time < 60:  # Less than 1 minute
                insights.append("Fast decision making indicates clear, actionable recommendations")
            elif avg_decision_time > 300:  # More than 5 minutes
                insights.append("Slow decision making suggests recommendations need more clarity")

        # Engagement insights
        avg_time_on_item = metrics.get('avg_time_on_item')
        if avg_time_on_item and avg_time_on_item > 45:
            insights.append("High engagement suggests user values detailed information")

        # Profile-specific insights
        if profile and profile.weights:
            cost_sensitivity = profile.weights.get('cost_sensitivity', 0.5)
            if cost_sensitivity > 0.7:
                insights.append("User is cost-sensitive - prioritize efficient recommendations")

            risk_tolerance = profile.weights.get('risk_tolerance', 0.5)
            if risk_tolerance < 0.3:
                insights.append("User is risk-averse - provide high-confidence recommendations with citations")

        return insights


# Factory function for getting the learning service
def get_learning_service() -> LearningSignalsCollector:
    """Get the learning signals collector service"""
    return LearningSignalsCollector()