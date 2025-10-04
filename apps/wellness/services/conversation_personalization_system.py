"""
Conversation Tone and Personalization System

Advanced personalization engine that adapts conversation tone, style, and content
based on user preferences, engagement patterns, and effectiveness history to create
truly personalized "conversations with wisdom" that feel natural and supportive.

Chain of Thought Reasoning:
1. Analyze user engagement patterns and preferences
2. Track conversation effectiveness by tone and style
3. Adapt future conversations based on what works best
4. Consider user's emotional state and context
5. Maintain consistent but evolving personality
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg, F
import json

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement
)
from ..models.mental_health_interventions import InterventionDeliveryLog
from ..models.user_progress import WellnessUserProgress

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationPersonalizationSystem:
    """
    Advanced personalization system that creates unique conversation experiences
    tailored to each user's preferences, personality, and response patterns.

    Ultra-think approach: Create AI companion that learns and adapts like a real
    supportive friend who knows exactly how to communicate with each individual.
    """

    def __init__(self):
        # Personality trait mappings
        self.personality_traits = {
            'analytical': {
                'preferred_tones': ['professional_clinical', 'supportive'],
                'evidence_focus': True,
                'detail_level': 'high',
                'explanation_style': 'structured'
            },
            'emotional': {
                'preferred_tones': ['warm_supportive', 'gentle_encouraging'],
                'evidence_focus': False,
                'detail_level': 'medium',
                'explanation_style': 'empathetic'
            },
            'practical': {
                'preferred_tones': ['motivational_energetic', 'supportive'],
                'evidence_focus': True,
                'detail_level': 'low',
                'explanation_style': 'action_oriented'
            },
            'introspective': {
                'preferred_tones': ['reflective', 'gentle_encouraging'],
                'evidence_focus': False,
                'detail_level': 'high',
                'explanation_style': 'philosophical'
            },
            'crisis_prone': {
                'preferred_tones': ['crisis_stabilizing', 'warm_supportive'],
                'evidence_focus': False,
                'detail_level': 'low',
                'explanation_style': 'calming'
            }
        }

        # Tone adaptation rules
        self.tone_rules = {
            'warm_supportive': {
                'effectiveness_threshold': 4.0,
                'best_for_interventions': ['THREE_GOOD_THINGS', 'GRATITUDE_JOURNAL'],
                'emotional_states': ['neutral', 'positive', 'mild_stress'],
                'personality_fit': ['emotional', 'introspective']
            },
            'professional_clinical': {
                'effectiveness_threshold': 3.5,
                'best_for_interventions': ['CBT_THOUGHT_RECORD', 'CRISIS_SUPPORT'],
                'emotional_states': ['crisis', 'severe_stress'],
                'personality_fit': ['analytical', 'practical']
            },
            'gentle_encouraging': {
                'effectiveness_threshold': 4.2,
                'best_for_interventions': ['MOTIVATIONAL_INTERVIEWING'],
                'emotional_states': ['low_mood', 'mild_stress'],
                'personality_fit': ['emotional', 'introspective', 'crisis_prone']
            },
            'motivational_energetic': {
                'effectiveness_threshold': 3.8,
                'best_for_interventions': ['MOTIVATIONAL_INTERVIEWING'],
                'emotional_states': ['neutral', 'positive'],
                'personality_fit': ['practical']
            },
            'crisis_stabilizing': {
                'effectiveness_threshold': 4.5,
                'best_for_interventions': ['CRISIS_SUPPORT'],
                'emotional_states': ['crisis', 'severe_stress'],
                'personality_fit': ['crisis_prone', 'emotional']
            }
        }

        # Communication style patterns
        self.communication_styles = {
            'concise': {
                'sentence_length': 'short',
                'paragraph_length': 'brief',
                'example_usage': 'minimal',
                'repetition': 'low'
            },
            'detailed': {
                'sentence_length': 'long',
                'paragraph_length': 'extended',
                'example_usage': 'extensive',
                'repetition': 'moderate'
            },
            'balanced': {
                'sentence_length': 'medium',
                'paragraph_length': 'moderate',
                'example_usage': 'appropriate',
                'repetition': 'low'
            },
            'storytelling': {
                'sentence_length': 'varied',
                'paragraph_length': 'narrative',
                'example_usage': 'story_based',
                'repetition': 'thematic'
            }
        }

    def analyze_user_personality(self, user: User) -> Dict:
        """
        Analyze user's communication personality based on engagement patterns
        and conversation history to create personalized interaction style.
        """

        logger.info(f"Analyzing personality profile for user {user.peoplename}")

        # Get user's conversation history
        conversations = WisdomConversation.objects.filter(user=user).prefetch_related(
            'engagements'
        ).order_by('-conversation_date')[:50]  # Last 50 conversations

        if conversations.count() < 5:
            # Not enough data, use default personality with basic preferences
            return self._create_default_personality_profile(user)

        # Analyze engagement patterns by tone
        tone_effectiveness = self._analyze_tone_effectiveness(conversations)

        # Analyze preferred communication style
        communication_preferences = self._analyze_communication_preferences(conversations)

        # Analyze response patterns
        response_patterns = self._analyze_response_patterns(conversations)

        # Detect personality traits
        personality_traits = self._detect_personality_traits(
            tone_effectiveness, communication_preferences, response_patterns
        )

        # Create personalization profile
        profile = {
            'user_id': user.id,
            'personality_type': personality_traits['primary_type'],
            'secondary_traits': personality_traits['secondary_traits'],
            'preferred_tones': personality_traits['preferred_tones'],
            'communication_style': communication_preferences['preferred_style'],
            'effectiveness_by_tone': tone_effectiveness,
            'response_patterns': response_patterns,
            'last_updated': timezone.now().isoformat(),
            'confidence_score': personality_traits['confidence']
        }

        # Store in user's thread personalization data
        self._update_user_personalization_data(user, profile)

        logger.info(f"Personality analysis complete: {profile['personality_type']} type with {profile['confidence_score']:.2f} confidence")

        return profile

    def select_optimal_tone(
        self,
        user: User,
        intervention_type: str,
        emotional_context: Optional[Dict] = None,
        thread: Optional[ConversationThread] = None
    ) -> str:
        """
        Select the optimal conversation tone for this specific user and context.

        Chain of Thought:
        1. Get user's personality profile
        2. Consider intervention type requirements
        3. Factor in emotional context
        4. Check recent effectiveness patterns
        5. Select best-fit tone with fallback options
        """

        # Get user's personality profile
        personality = self._get_user_personality_profile(user)

        # Get current emotional state
        emotional_state = emotional_context or self._infer_emotional_state(user)

        # Get recent tone effectiveness
        recent_effectiveness = self._get_recent_tone_effectiveness(user)

        # Score each possible tone
        tone_scores = {}
        for tone, rules in self.tone_rules.items():
            score = self._calculate_tone_score(
                tone, rules, personality, intervention_type,
                emotional_state, recent_effectiveness
            )
            tone_scores[tone] = score

        # Select highest scoring tone
        optimal_tone = max(tone_scores.items(), key=lambda x: x[1])[0]

        logger.info(f"Selected tone '{optimal_tone}' for user {user.peoplename} with intervention {intervention_type}")

        return optimal_tone

    def personalize_conversation_content(
        self,
        base_content: str,
        user: User,
        conversation_context: Dict,
        thread: ConversationThread
    ) -> str:
        """
        Personalize conversation content based on user's profile and preferences.

        Applies user-specific modifications to make conversation feel naturally tailored.
        """

        personality = self._get_user_personality_profile(user)
        personalized_content = base_content

        # Apply name personalization
        personalized_content = self._apply_name_personalization(
            personalized_content, user, personality
        )

        # Apply communication style adaptations
        personalized_content = self._apply_communication_style(
            personalized_content, personality['communication_style']
        )

        # Apply contextual personalization
        personalized_content = self._apply_contextual_personalization(
            personalized_content, user, conversation_context
        )

        # Apply tone-specific modifications
        personalized_content = self._apply_tone_personalization(
            personalized_content, conversation_context.get('tone'), personality
        )

        # Apply learning-based optimizations
        personalized_content = self._apply_learned_preferences(
            personalized_content, user, thread
        )

        return personalized_content

    def _analyze_tone_effectiveness(self, conversations) -> Dict:
        """Analyze effectiveness of different tones for this user"""

        tone_stats = {}

        for conversation in conversations:
            tone = conversation.conversation_tone
            engagements = conversation.engagements.all()

            if engagements:
                avg_rating = engagements.aggregate(
                    avg_rating=Avg('effectiveness_rating')
                )['avg_rating'] or 0

                if tone not in tone_stats:
                    tone_stats[tone] = {
                        'total_conversations': 0,
                        'total_rating': 0,
                        'engagement_count': 0
                    }

                tone_stats[tone]['total_conversations'] += 1
                tone_stats[tone]['total_rating'] += avg_rating
                tone_stats[tone]['engagement_count'] += engagements.count()

        # Calculate average effectiveness for each tone
        effectiveness = {}
        for tone, stats in tone_stats.items():
            if stats['total_conversations'] > 0:
                effectiveness[tone] = {
                    'avg_rating': stats['total_rating'] / stats['total_conversations'],
                    'conversation_count': stats['total_conversations'],
                    'engagement_rate': stats['engagement_count'] / stats['total_conversations']
                }

        return effectiveness

    def _analyze_communication_preferences(self, conversations) -> Dict:
        """Analyze user's preferred communication style based on engagement"""

        style_effectiveness = {}

        for conversation in conversations:
            # Analyze conversation characteristics
            word_count = conversation.word_count
            reading_time = conversation.estimated_reading_time_seconds

            # Categorize style based on length and complexity
            if word_count < 100:
                style = 'concise'
            elif word_count > 300:
                style = 'detailed'
            elif reading_time > 120:  # More than 2 minutes
                style = 'storytelling'
            else:
                style = 'balanced'

            # Get effectiveness metrics
            engagements = conversation.engagements.all()
            if engagements:
                avg_rating = engagements.aggregate(
                    avg_rating=Avg('effectiveness_rating')
                )['avg_rating'] or 0

                if style not in style_effectiveness:
                    style_effectiveness[style] = []

                style_effectiveness[style].append(avg_rating)

        # Calculate average effectiveness for each style
        style_averages = {}
        for style, ratings in style_effectiveness.items():
            if ratings:
                style_averages[style] = sum(ratings) / len(ratings)

        # Select preferred style
        preferred_style = 'balanced'  # Default
        if style_averages:
            preferred_style = max(style_averages.items(), key=lambda x: x[1])[0]

        return {
            'preferred_style': preferred_style,
            'style_effectiveness': style_averages
        }

    def _analyze_response_patterns(self, conversations) -> Dict:
        """Analyze user's response patterns to conversations"""

        patterns = {
            'response_frequency': 0,
            'engagement_types': {},
            'time_to_engage': [],
            'feedback_patterns': {}
        }

        total_conversations = conversations.count()
        responded_conversations = 0

        for conversation in conversations:
            engagements = conversation.engagements.all()

            if engagements:
                responded_conversations += 1

                for engagement in engagements:
                    # Track engagement types
                    eng_type = engagement.engagement_type
                    patterns['engagement_types'][eng_type] = patterns['engagement_types'].get(eng_type, 0) + 1

                    # Track time to engagement
                    time_diff = (engagement.engagement_date - conversation.conversation_date).total_seconds() / 3600  # hours
                    patterns['time_to_engage'].append(time_diff)

                    # Track feedback patterns
                    if engagement.effectiveness_rating:
                        rating = engagement.effectiveness_rating
                        patterns['feedback_patterns'][rating] = patterns['feedback_patterns'].get(rating, 0) + 1

        # Calculate response frequency
        patterns['response_frequency'] = responded_conversations / max(1, total_conversations)

        # Calculate average time to engage
        if patterns['time_to_engage']:
            patterns['avg_time_to_engage'] = sum(patterns['time_to_engage']) / len(patterns['time_to_engage'])
        else:
            patterns['avg_time_to_engage'] = 24  # Default 24 hours

        return patterns

    def _detect_personality_traits(
        self,
        tone_effectiveness: Dict,
        communication_preferences: Dict,
        response_patterns: Dict
    ) -> Dict:
        """Detect user's personality traits based on analysis"""

        trait_scores = {}

        # Analyze tone preferences for personality indicators
        for personality_type, traits in self.personality_traits.items():
            score = 0

            # Check tone alignment
            for preferred_tone in traits['preferred_tones']:
                if preferred_tone in tone_effectiveness:
                    effectiveness = tone_effectiveness[preferred_tone]['avg_rating']
                    score += effectiveness * 0.3

            # Check communication style alignment
            if communication_preferences['preferred_style'] == traits.get('detail_level', 'medium'):
                score += 1.0

            # Check response patterns
            if response_patterns['response_frequency'] > 0.7 and personality_type == 'analytical':
                score += 0.5
            elif response_patterns['response_frequency'] < 0.3 and personality_type == 'introspective':
                score += 0.5

            trait_scores[personality_type] = score

        # Select primary and secondary traits
        sorted_traits = sorted(trait_scores.items(), key=lambda x: x[1], reverse=True)

        primary_type = sorted_traits[0][0] if sorted_traits else 'emotional'
        secondary_traits = [trait[0] for trait in sorted_traits[1:3]]

        # Get preferred tones from personality
        preferred_tones = self.personality_traits[primary_type]['preferred_tones'].copy()

        # Add tones with high effectiveness
        for tone, data in tone_effectiveness.items():
            if data['avg_rating'] >= 4.0 and tone not in preferred_tones:
                preferred_tones.append(tone)

        # Calculate confidence based on data quality
        total_conversations = sum(data.get('conversation_count', 0) for data in tone_effectiveness.values())
        confidence = min(1.0, total_conversations / 10)  # Full confidence after 10+ conversations

        return {
            'primary_type': primary_type,
            'secondary_traits': secondary_traits,
            'preferred_tones': preferred_tones[:3],  # Top 3 tones
            'confidence': confidence
        }

    def _create_default_personality_profile(self, user: User) -> Dict:
        """Create default personality profile for new users"""

        # Try to infer from user data
        default_type = 'emotional'  # Safe default

        # Check if user has wellness preferences
        try:
            wellness_progress = WellnessUserProgress.objects.get(user=user)
            if wellness_progress.preferred_content_level == 'short_read':
                default_type = 'practical'
            elif wellness_progress.preferred_content_level == 'detailed_guide':
                default_type = 'analytical'
        except WellnessUserProgress.DoesNotExist:
            pass

        return {
            'user_id': user.id,
            'personality_type': default_type,
            'secondary_traits': [],
            'preferred_tones': self.personality_traits[default_type]['preferred_tones'],
            'communication_style': 'balanced',
            'effectiveness_by_tone': {},
            'response_patterns': {},
            'last_updated': timezone.now().isoformat(),
            'confidence_score': 0.3  # Low confidence for new users
        }

    def _get_user_personality_profile(self, user: User) -> Dict:
        """Get user's personality profile from stored data or analyze if needed"""

        # Check for stored profile in threads
        recent_thread = ConversationThread.objects.filter(user=user).first()

        if recent_thread and recent_thread.personalization_data.get('personality_profile'):
            profile = recent_thread.personalization_data['personality_profile']

            # Check if profile is recent (within 30 days)
            last_updated = datetime.fromisoformat(profile['last_updated'].replace('Z', '+00:00'))
            if (timezone.now() - last_updated).days < 30:
                return profile

        # Profile is old or doesn't exist, analyze new one
        return self.analyze_user_personality(user)

    def _infer_emotional_state(self, user: User) -> Dict:
        """Infer user's current emotional state from recent activity"""

        # Get recent journal entries if available
        try:
            from apps.journal.models import JournalEntry
            recent_entries = JournalEntry.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).order_by('-created_at')[:3]

            if recent_entries:
                # Analyze mood patterns
                mood_ratings = []
                stress_levels = []

                for entry in recent_entries:
                    if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                        metrics = entry.wellbeing_metrics
                        if hasattr(metrics, 'mood_rating') and metrics.mood_rating:
                            mood_ratings.append(metrics.mood_rating)
                        if hasattr(metrics, 'stress_level') and metrics.stress_level:
                            stress_levels.append(metrics.stress_level)

                # Calculate current state
                if mood_ratings:
                    avg_mood = sum(mood_ratings) / len(mood_ratings)
                    if avg_mood <= 3:
                        return {'state': 'low_mood', 'intensity': 'moderate'}
                    elif avg_mood >= 7:
                        return {'state': 'positive', 'intensity': 'high'}

                if stress_levels:
                    avg_stress = sum(stress_levels) / len(stress_levels)
                    if avg_stress >= 4:
                        return {'state': 'severe_stress', 'intensity': 'high'}
                    elif avg_stress >= 3:
                        return {'state': 'mild_stress', 'intensity': 'moderate'}

        except ImportError:
            pass

        # Default neutral state
        return {'state': 'neutral', 'intensity': 'low'}

    def _get_recent_tone_effectiveness(self, user: User) -> Dict:
        """Get effectiveness of recent conversations by tone"""

        recent_conversations = WisdomConversation.objects.filter(
            user=user,
            conversation_date__gte=timezone.now() - timedelta(days=30)
        ).prefetch_related('engagements')

        return self._analyze_tone_effectiveness(recent_conversations)

    def _calculate_tone_score(
        self,
        tone: str,
        rules: Dict,
        personality: Dict,
        intervention_type: str,
        emotional_state: Dict,
        recent_effectiveness: Dict
    ) -> float:
        """Calculate score for a specific tone based on multiple factors"""

        score = 0.0

        # Base score from personality fit
        if tone in personality.get('preferred_tones', []):
            score += 2.0

        # Score from intervention type compatibility
        if intervention_type in rules.get('best_for_interventions', []):
            score += 1.5

        # Score from emotional state compatibility
        if emotional_state['state'] in rules.get('emotional_states', []):
            score += 1.0

        # Score from recent effectiveness
        if tone in recent_effectiveness:
            effectiveness = recent_effectiveness[tone]['avg_rating']
            score += (effectiveness / 5.0) * 2.0  # Scale to 0-2

        # Personality type bonus
        user_personality = personality.get('personality_type')
        if user_personality in rules.get('personality_fit', []):
            score += 1.0

        # Threshold bonus
        threshold = rules.get('effectiveness_threshold', 3.0)
        if tone in recent_effectiveness:
            if recent_effectiveness[tone]['avg_rating'] >= threshold:
                score += 0.5

        return score

    def _apply_name_personalization(self, content: str, user: User, personality: Dict) -> str:
        """Apply name-based personalization to content"""

        user_name = user.peoplename or "friend"

        # Determine frequency of name usage based on personality
        personality_type = personality.get('personality_type', 'emotional')

        if personality_type in ['emotional', 'crisis_prone']:
            # Use name more frequently for emotional connection
            name_frequency = 'high'
        elif personality_type == 'analytical':
            # Use name less frequently, more professional
            name_frequency = 'low'
        else:
            name_frequency = 'medium'

        # Apply name personalization
        if name_frequency == 'high' and not user_name.lower() in content.lower():
            # Add name at the beginning if not present
            content = f"{user_name}, " + content
        elif name_frequency == 'low':
            # Remove excessive name usage
            content = content.replace(f"{user_name}, ", "", 1)

        return content

    def _apply_communication_style(self, content: str, style: str) -> str:
        """Apply communication style modifications to content"""

        style_rules = self.communication_styles.get(style, self.communication_styles['balanced'])

        # Apply sentence length modifications
        if style_rules['sentence_length'] == 'short':
            # Break long sentences
            content = self._shorten_sentences(content)
        elif style_rules['sentence_length'] == 'long':
            # Combine short sentences where appropriate
            content = self._lengthen_sentences(content)

        # Apply paragraph modifications
        if style_rules['paragraph_length'] == 'brief':
            content = self._create_brief_paragraphs(content)

        return content

    def _shorten_sentences(self, content: str) -> str:
        """Break long sentences into shorter ones"""

        sentences = content.split('. ')
        shortened = []

        for sentence in sentences:
            if len(sentence.split()) > 20:  # Long sentence
                # Look for natural break points
                break_words = [', and ', ', but ', ', which ', ', that ']
                for break_word in break_words:
                    if break_word in sentence:
                        parts = sentence.split(break_word, 1)
                        shortened.append(parts[0] + '.')
                        shortened.append(parts[1].capitalize())
                        break
                else:
                    shortened.append(sentence)
            else:
                shortened.append(sentence)

        return '. '.join(shortened)

    def _update_user_personalization_data(self, user: User, profile: Dict):
        """Store personalization profile in user's thread data"""

        threads = ConversationThread.objects.filter(user=user)

        for thread in threads:
            personalization_data = thread.personalization_data.copy()
            personalization_data['personality_profile'] = profile
            thread.personalization_data = personalization_data
            thread.save(update_fields=['personalization_data'])

    def get_personalization_insights(self, user: User) -> Dict:
        """Get comprehensive personalization insights for user"""

        personality = self._get_user_personality_profile(user)
        recent_effectiveness = self._get_recent_tone_effectiveness(user)

        return {
            'personality_summary': {
                'type': personality['personality_type'],
                'confidence': personality['confidence_score'],
                'preferred_tones': personality['preferred_tones'],
                'communication_style': personality['communication_style']
            },
            'effectiveness_insights': recent_effectiveness,
            'recommendations': self._generate_personalization_recommendations(personality, recent_effectiveness),
            'adaptation_opportunities': self._identify_adaptation_opportunities(user, personality)
        }

    def _generate_personalization_recommendations(self, personality: Dict, effectiveness: Dict) -> List[str]:
        """Generate recommendations for improving personalization"""

        recommendations = []

        # Low confidence warning
        if personality['confidence_score'] < 0.5:
            recommendations.append("More conversation data needed for better personalization")

        # Effectiveness insights
        if effectiveness:
            best_tone = max(effectiveness.items(), key=lambda x: x[1]['avg_rating'])[0]
            recommendations.append(f"'{best_tone}' tone shows highest effectiveness")

            # Find underperforming tones
            poor_tones = [tone for tone, data in effectiveness.items() if data['avg_rating'] < 3.0]
            if poor_tones:
                recommendations.append(f"Consider avoiding: {', '.join(poor_tones)}")

        return recommendations