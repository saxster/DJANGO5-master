"""
Conversation Flow Manager

Manages the threading and narrative flow logic for wisdom conversations,
ensuring they read like "one continuous book that flows with no interruption".

Chain of Thought Reasoning:
1. Monitor conversation threads for coherence
2. Manage narrative transitions between conversations
3. Handle thread merging and splitting
4. Ensure chronological ordering makes sense
5. Maintain thematic consistency within threads
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement
)
from ..models.mental_health_interventions import InterventionDeliveryLog

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationFlowManager:
    """
    Manages the narrative flow and threading logic for wisdom conversations.

    Ultra-think approach: Create seamless narrative flow that feels like
    reading a single, continuous book about the user's mental health journey.
    """

    def __init__(self):
        self.max_thread_gap_days = 30  # Auto-pause threads after 30 days of inactivity
        self.thread_merge_threshold = 0.7  # Similarity threshold for merging threads
        self.narrative_coherence_threshold = 0.8  # Minimum coherence score

    def organize_user_conversations(self, user: User) -> Dict:
        """
        Organize all user conversations into coherent narrative flow.

        Returns complete conversation organization with threading and flow analysis.
        """

        logger.info(f"Organizing conversations for user {user.peoplename}")

        # Get all user threads and conversations
        threads = ConversationThread.objects.filter(user=user).prefetch_related(
            'wisdom_conversations__engagements'
        )

        # Analyze thread health and flow
        thread_analysis = {}
        for thread in threads:
            thread_analysis[thread.id] = self._analyze_thread_flow(thread)

        # Identify threading opportunities
        threading_suggestions = self._identify_threading_opportunities(user)

        # Analyze narrative gaps
        narrative_gaps = self._identify_narrative_gaps(threads)

        # Generate flow recommendations
        flow_recommendations = self._generate_flow_recommendations(
            threads, thread_analysis, narrative_gaps
        )

        return {
            'threads': threads,
            'thread_analysis': thread_analysis,
            'threading_suggestions': threading_suggestions,
            'narrative_gaps': narrative_gaps,
            'flow_recommendations': flow_recommendations,
            'overall_narrative_health': self._calculate_overall_narrative_health(threads)
        }

    def _analyze_thread_flow(self, thread: ConversationThread) -> Dict:
        """Analyze the narrative flow within a single thread"""

        conversations = thread.wisdom_conversations.order_by('sequence_number')

        if conversations.count() < 2:
            return {
                'flow_quality': 1.0,
                'gaps': [],
                'coherence_score': 1.0,
                'engagement_trend': 'stable',
                'recommendations': []
            }

        # Analyze temporal gaps
        temporal_gaps = []
        conversations_list = list(conversations)

        for i in range(1, len(conversations_list)):
            prev_conv = conversations_list[i-1]
            curr_conv = conversations_list[i]

            gap_days = (curr_conv.conversation_date - prev_conv.conversation_date).days

            if gap_days > 14:  # Significant gap
                temporal_gaps.append({
                    'between_conversations': [prev_conv.sequence_number, curr_conv.sequence_number],
                    'gap_days': gap_days,
                    'suggested_bridge': self._suggest_gap_bridge(prev_conv, curr_conv, gap_days)
                })

        # Analyze thematic coherence
        coherence_score = self._calculate_thematic_coherence(conversations_list)

        # Analyze engagement trends
        engagement_trend = self._analyze_engagement_trend(conversations_list)

        # Calculate overall flow quality
        flow_quality = self._calculate_flow_quality(conversations_list, temporal_gaps, coherence_score)

        # Generate recommendations
        recommendations = self._generate_thread_recommendations(
            thread, temporal_gaps, coherence_score, engagement_trend
        )

        return {
            'flow_quality': flow_quality,
            'gaps': temporal_gaps,
            'coherence_score': coherence_score,
            'engagement_trend': engagement_trend,
            'recommendations': recommendations,
            'conversation_count': conversations.count(),
            'avg_reading_time': conversations.aggregate(
                avg_time=Avg('estimated_reading_time_seconds')
            )['avg_time'] or 0
        }

    def _identify_threading_opportunities(self, user: User) -> List[Dict]:
        """Identify opportunities to create new threads or merge existing ones"""

        opportunities = []

        # Check for conversations that might belong in different threads
        orphaned_conversations = self._find_orphaned_conversations(user)

        for conv in orphaned_conversations:
            opportunities.append({
                'type': 'rethreading',
                'conversation_id': conv.id,
                'current_thread': conv.thread.title,
                'suggested_thread': self._suggest_better_thread(conv),
                'confidence': self._calculate_rethreading_confidence(conv)
            })

        # Check for similar threads that could be merged
        merge_candidates = self._find_merge_candidates(user)

        for thread1, thread2, similarity in merge_candidates:
            opportunities.append({
                'type': 'thread_merge',
                'threads': [thread1.title, thread2.title],
                'similarity_score': similarity,
                'merged_title': self._suggest_merged_title(thread1, thread2),
                'confidence': similarity
            })

        # Check for threads that should be split
        split_candidates = self._find_split_candidates(user)

        for thread, split_points in split_candidates:
            opportunities.append({
                'type': 'thread_split',
                'thread': thread.title,
                'split_points': split_points,
                'suggested_threads': self._suggest_split_threads(thread, split_points),
                'confidence': self._calculate_split_confidence(thread, split_points)
            })

        return sorted(opportunities, key=lambda x: x['confidence'], reverse=True)

    def _identify_narrative_gaps(self, threads) -> List[Dict]:
        """Identify gaps in the narrative that need bridging"""

        gaps = []

        for thread in threads:
            conversations = thread.wisdom_conversations.order_by('sequence_number')

            for i, conversation in enumerate(conversations):
                # Check for missing contextual bridges
                if not conversation.contextual_bridge_text and i > 0:
                    prev_conv = conversations[i-1]
                    gap_analysis = self._analyze_conversation_gap(prev_conv, conversation)

                    if gap_analysis['needs_bridge']:
                        gaps.append({
                            'thread_title': thread.title,
                            'between_conversations': [prev_conv.sequence_number, conversation.sequence_number],
                            'gap_type': gap_analysis['gap_type'],
                            'suggested_bridge': gap_analysis['suggested_bridge'],
                            'priority': gap_analysis['priority']
                        })

        return sorted(gaps, key=lambda x: x['priority'], reverse=True)

    def _generate_flow_recommendations(
        self,
        threads,
        thread_analysis: Dict,
        narrative_gaps: List[Dict]
    ) -> List[Dict]:
        """Generate actionable recommendations for improving narrative flow"""

        recommendations = []

        # Thread-specific recommendations
        for thread in threads:
            analysis = thread_analysis.get(thread.id, {})

            if analysis.get('flow_quality', 1.0) < 0.7:
                recommendations.append({
                    'type': 'improve_thread_flow',
                    'thread': thread.title,
                    'current_quality': analysis.get('flow_quality'),
                    'specific_issues': analysis.get('recommendations', []),
                    'priority': 'high' if analysis.get('flow_quality', 1.0) < 0.5 else 'medium'
                })

        # Gap bridging recommendations
        high_priority_gaps = [g for g in narrative_gaps if g['priority'] >= 0.8]

        if high_priority_gaps:
            recommendations.append({
                'type': 'add_narrative_bridges',
                'gap_count': len(high_priority_gaps),
                'affected_threads': list(set(g['thread_title'] for g in high_priority_gaps)),
                'priority': 'high'
            })

        # Thread organization recommendations
        inactive_threads = [t for t in threads if t.status == 'active' and
                          t.last_conversation_date and
                          (timezone.now() - t.last_conversation_date).days > self.max_thread_gap_days]

        if inactive_threads:
            recommendations.append({
                'type': 'manage_inactive_threads',
                'thread_count': len(inactive_threads),
                'threads': [t.title for t in inactive_threads],
                'suggested_action': 'pause_or_archive',
                'priority': 'medium'
            })

        return sorted(recommendations, key=lambda x:
                     {'high': 3, 'medium': 2, 'low': 1}[x['priority']], reverse=True)

    def _calculate_thematic_coherence(self, conversations: List[WisdomConversation]) -> float:
        """Calculate how thematically coherent a series of conversations is"""

        if len(conversations) < 2:
            return 1.0

        # Analyze conversation metadata for thematic similarity
        coherence_scores = []

        for i in range(1, len(conversations)):
            prev_conv = conversations[i-1]
            curr_conv = conversations[i]

            # Check source intervention type similarity
            prev_type = prev_conv.conversation_metadata.get('intervention_type')
            curr_type = curr_conv.conversation_metadata.get('intervention_type')

            type_similarity = 1.0 if prev_type == curr_type else 0.5

            # Check keyword overlap
            prev_keywords = set(prev_conv.conversation_metadata.get('keywords', []))
            curr_keywords = set(curr_conv.conversation_metadata.get('keywords', []))

            if prev_keywords and curr_keywords:
                keyword_similarity = len(prev_keywords.intersection(curr_keywords)) / \
                                   len(prev_keywords.union(curr_keywords))
            else:
                keyword_similarity = 0.5

            # Check tone consistency
            tone_similarity = 1.0 if prev_conv.conversation_tone == curr_conv.conversation_tone else 0.7

            # Combined coherence score
            conversation_coherence = (type_similarity * 0.4 +
                                    keyword_similarity * 0.4 +
                                    tone_similarity * 0.2)

            coherence_scores.append(conversation_coherence)

        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 1.0

    def _analyze_engagement_trend(self, conversations: List[WisdomConversation]) -> str:
        """Analyze engagement trend across conversations"""

        if len(conversations) < 3:
            return 'stable'

        engagement_scores = []
        for conv in conversations:
            # Calculate engagement score based on various metrics
            engagement_count = conv.engagements.count()
            avg_effectiveness = conv.engagements.aggregate(
                avg_rating=Avg('effectiveness_rating')
            )['avg_rating'] or 0

            # Weight recent conversations more heavily
            days_old = (timezone.now() - conv.conversation_date).days
            recency_weight = max(0.1, 1.0 - (days_old / 365))  # Decay over a year

            engagement_score = (engagement_count * 0.3 + avg_effectiveness * 0.7) * recency_weight
            engagement_scores.append(engagement_score)

        # Analyze trend
        if len(engagement_scores) >= 3:
            recent_avg = sum(engagement_scores[-3:]) / 3
            earlier_avg = sum(engagement_scores[:-3]) / len(engagement_scores[:-3]) if len(engagement_scores) > 3 else recent_avg

            if recent_avg > earlier_avg * 1.2:
                return 'improving'
            elif recent_avg < earlier_avg * 0.8:
                return 'declining'

        return 'stable'

    def _calculate_flow_quality(
        self,
        conversations: List[WisdomConversation],
        temporal_gaps: List[Dict],
        coherence_score: float
    ) -> float:
        """Calculate overall flow quality for a thread"""

        if not conversations:
            return 1.0

        # Penalize for temporal gaps
        gap_penalty = len(temporal_gaps) * 0.1

        # Penalize for missing bridges
        missing_bridges = sum(1 for conv in conversations[1:] if not conv.contextual_bridge_text)
        bridge_penalty = (missing_bridges / max(1, len(conversations) - 1)) * 0.2

        # Reward for milestone conversations
        milestone_bonus = sum(1 for conv in conversations if conv.is_milestone_conversation) * 0.05

        # Base quality from coherence
        base_quality = coherence_score

        # Calculate final quality
        quality = base_quality - gap_penalty - bridge_penalty + milestone_bonus

        return max(0.0, min(1.0, quality))

    def _suggest_gap_bridge(
        self,
        prev_conv: WisdomConversation,
        curr_conv: WisdomConversation,
        gap_days: int
    ) -> str:
        """Suggest bridge text for a gap between conversations"""

        if gap_days > 30:
            return f"After some time away from our conversations, I wanted to reconnect with you..."
        elif gap_days > 14:
            return f"It's been a couple of weeks since we last talked, and I've been thinking about..."
        elif gap_days > 7:
            return f"As I reflect on our last conversation, something important came to mind..."
        else:
            return f"Building on what we discussed, I wanted to share..."

    def _find_orphaned_conversations(self, user: User) -> List[WisdomConversation]:
        """Find conversations that might be better placed in different threads"""

        orphaned = []

        conversations = WisdomConversation.objects.filter(user=user).select_related(
            'thread', 'source_intervention_delivery__intervention'
        )

        for conv in conversations:
            # Check if conversation intervention type matches thread type
            intervention_type = conv.conversation_metadata.get('intervention_type')
            thread_type = conv.thread.thread_type

            expected_thread_type = self._map_intervention_to_thread_type(intervention_type)

            if expected_thread_type != thread_type:
                orphaned.append(conv)

        return orphaned

    def _map_intervention_to_thread_type(self, intervention_type: str) -> str:
        """Map intervention type to expected thread type"""

        mapping = {
            'THREE_GOOD_THINGS': 'three_good_things',
            'GRATITUDE_JOURNAL': 'gratitude_journey',
            'CBT_THOUGHT_RECORD': 'cbt_cognitive',
            'MOTIVATIONAL_INTERVIEWING': 'motivational_growth',
            'CRISIS_SUPPORT': 'crisis_recovery',
            'STRESS_MANAGEMENT': 'stress_management',
            'WORKPLACE_WELLNESS': 'workplace_wellness',
            'PREVENTIVE_CARE': 'preventive_care',
        }

        return mapping.get(intervention_type, 'workplace_wellness')

    def _find_merge_candidates(self, user: User) -> List[Tuple]:
        """Find threads that could potentially be merged"""

        threads = ConversationThread.objects.filter(user=user)
        merge_candidates = []

        for i, thread1 in enumerate(threads):
            for thread2 in threads[i+1:]:
                similarity = self._calculate_thread_similarity(thread1, thread2)

                if similarity >= self.thread_merge_threshold:
                    merge_candidates.append((thread1, thread2, similarity))

        return merge_candidates

    def _calculate_thread_similarity(self, thread1: ConversationThread, thread2: ConversationThread) -> float:
        """Calculate similarity between two threads"""

        # Type similarity
        type_similarity = 1.0 if thread1.thread_type == thread2.thread_type else 0.0

        # Temporal overlap
        if (thread1.first_conversation_date and thread2.first_conversation_date and
            thread1.last_conversation_date and thread2.last_conversation_date):

            overlap = self._calculate_temporal_overlap(
                thread1.first_conversation_date, thread1.last_conversation_date,
                thread2.first_conversation_date, thread2.last_conversation_date
            )
        else:
            overlap = 0.0

        # Style similarity
        style_similarity = 1.0 if thread1.narrative_style == thread2.narrative_style else 0.5

        # Combined similarity
        return (type_similarity * 0.5 + overlap * 0.3 + style_similarity * 0.2)

    def _calculate_temporal_overlap(self, start1, end1, start2, end2) -> float:
        """Calculate temporal overlap between two date ranges"""

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)

        if overlap_start <= overlap_end:
            overlap_duration = (overlap_end - overlap_start).days
            total_duration = max((end1 - start1).days, (end2 - start2).days)

            return overlap_duration / max(1, total_duration)

        return 0.0

    def _find_split_candidates(self, user: User) -> List[Tuple]:
        """Find threads that should potentially be split"""

        split_candidates = []
        threads = ConversationThread.objects.filter(user=user)

        for thread in threads:
            conversations = list(thread.wisdom_conversations.order_by('sequence_number'))

            if len(conversations) < 6:  # Too short to split
                continue

            # Look for thematic shifts that might indicate split points
            split_points = self._identify_split_points(conversations)

            if split_points:
                split_candidates.append((thread, split_points))

        return split_candidates

    def _identify_split_points(self, conversations: List[WisdomConversation]) -> List[int]:
        """Identify potential points where a thread should be split"""

        split_points = []

        for i in range(2, len(conversations) - 2):  # Leave room on both sides
            conv = conversations[i]
            prev_conv = conversations[i-1]

            # Check for significant thematic shift
            thematic_shift = self._detect_thematic_shift(prev_conv, conv)

            # Check for significant temporal gap
            temporal_gap = (conv.conversation_date - prev_conv.conversation_date).days

            # Check for intervention type change
            prev_type = prev_conv.conversation_metadata.get('intervention_type')
            curr_type = conv.conversation_metadata.get('intervention_type')
            type_change = prev_type != curr_type

            # Combine factors to determine split worthiness
            split_score = (thematic_shift * 0.4 +
                          min(1.0, temporal_gap / 30) * 0.3 +
                          (1.0 if type_change else 0.0) * 0.3)

            if split_score >= 0.7:
                split_points.append(i)

        return split_points

    def _detect_thematic_shift(self, conv1: WisdomConversation, conv2: WisdomConversation) -> float:
        """Detect thematic shift between two conversations"""

        keywords1 = set(conv1.conversation_metadata.get('keywords', []))
        keywords2 = set(conv2.conversation_metadata.get('keywords', []))

        if not keywords1 or not keywords2:
            return 0.5

        # High shift if low keyword overlap
        overlap = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))

        similarity = overlap / union if union > 0 else 0
        shift = 1.0 - similarity

        return shift

    def _calculate_overall_narrative_health(self, threads) -> Dict:
        """Calculate overall narrative health metrics for user"""

        total_conversations = sum(thread.conversation_count for thread in threads)
        active_threads = threads.filter(status='active').count()

        # Calculate average engagement
        all_engagements = ConversationEngagement.objects.filter(
            conversation__thread__in=threads
        )

        avg_engagement = all_engagements.aggregate(
            avg_rating=Avg('effectiveness_rating')
        )['avg_rating'] or 0

        # Calculate narrative continuity
        threads_with_gaps = 0
        for thread in threads:
            conversations = thread.wisdom_conversations.order_by('sequence_number')
            has_gaps = any(
                not conv.contextual_bridge_text for conv in conversations[1:]
            )
            if has_gaps:
                threads_with_gaps += 1

        continuity_score = 1.0 - (threads_with_gaps / max(1, len(threads)))

        return {
            'total_conversations': total_conversations,
            'active_threads': active_threads,
            'avg_engagement_rating': avg_engagement,
            'narrative_continuity_score': continuity_score,
            'overall_health_score': (avg_engagement / 5.0 * 0.6 + continuity_score * 0.4)
        }