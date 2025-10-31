"""
Wisdom Conversation Generator

Core service that transforms fragmented mental health interventions into
continuous, chronological conversations that read like "one continuous book
that flows with no interruption".

Chain of Thought Reasoning:
1. Take intervention delivery data + user context
2. Transform clinical intervention into warm, conversational tone
3. Generate contextual bridges between conversations
4. Apply narrative flow and personalization
5. Create seamless book-like reading experience
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement
)
from ..models.mental_health_interventions import InterventionDeliveryLog

User = get_user_model()
logger = logging.getLogger(__name__)


class WisdomConversationGenerator:
    """
    Core service for generating wisdom conversations from intervention deliveries.

    Ultra-think approach: Transform clinical interventions into warm, personal
    conversations that feel like a supportive friend's ongoing dialogue.
    """

    def __init__(self):
        # Personalization logic is implemented inline in methods below
        pass

        # Conversation tone templates for different intervention types
        self.tone_templates = {
            'THREE_GOOD_THINGS': {
                'warm_supportive': self._three_good_things_warm_template,
                'gentle_encouraging': self._three_good_things_gentle_template,
                'motivational_energetic': self._three_good_things_motivational_template,
            },
            'GRATITUDE_JOURNAL': {
                'warm_supportive': self._gratitude_warm_template,
                'gentle_encouraging': self._gratitude_gentle_template,
                'motivational_energetic': self._gratitude_motivational_template,
            },
            'CBT_THOUGHT_RECORD': {
                'warm_supportive': self._cbt_warm_template,
                'professional_clinical': self._cbt_clinical_template,
                'gentle_encouraging': self._cbt_gentle_template,
            },
            'MOTIVATIONAL_INTERVIEWING': {
                'warm_supportive': self._mi_warm_template,
                'motivational_energetic': self._mi_energetic_template,
                'gentle_encouraging': self._mi_gentle_template,
            },
            'CRISIS_SUPPORT': {
                'crisis_stabilizing': self._crisis_stabilizing_template,
                'warm_supportive': self._crisis_warm_template,
                'professional_clinical': self._crisis_clinical_template,
            },
        }

        # Bridge generation patterns for narrative flow
        self.bridge_patterns = {
            'temporal': [
                "As the days unfolded, I found myself thinking about...",
                "Later that week, something shifted in my perspective...",
                "Time has a way of bringing clarity, and I realized...",
                "Reflecting on our last conversation, I noticed...",
            ],
            'emotional': [
                "Your resilience continues to inspire me, and I wanted to share...",
                "I've been thinking about your journey, and here's what came to mind...",
                "There's something beautiful happening in your growth that I want to acknowledge...",
                "Your courage in facing challenges reminds me of...",
            ],
            'thematic': [
                "Building on what we explored about gratitude...",
                "This connects beautifully to your stress management journey...",
                "Your mindfulness practice is evolving, and I see...",
                "The patterns we've been discussing are becoming clearer...",
            ],
            'milestone': [
                "What an incredible milestone you've reached! Let me share...",
                "This achievement deserves recognition - you've shown...",
                "I'm so proud of how far you've come. Looking at your journey...",
                "Celebrating this moment with you feels perfect because...",
            ]
        }

    def generate_conversation_from_delivery(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: Optional[ConversationThread] = None
    ) -> WisdomConversation:
        """
        Transform an intervention delivery into a wisdom conversation.

        Chain of Thought:
        1. Analyze delivery context and user state
        2. Select appropriate thread or create new one
        3. Generate conversational content with proper tone
        4. Create contextual bridge if needed
        5. Apply personalization based on user history
        """

        logger.info(f"Generating wisdom conversation from delivery {delivery_log.id}")

        # Step 1: Analyze context
        user = delivery_log.user
        intervention = delivery_log.intervention

        # Step 2: Get or create conversation thread
        if not thread:
            thread = self._get_or_create_thread(user, intervention)

        # Step 3: Generate conversational content
        conversation_text = self._generate_conversation_text(
            delivery_log, thread
        )

        # Step 4: Generate contextual bridge
        bridge_text = self._generate_contextual_bridge(thread, delivery_log)

        # Step 5: Create conversation
        conversation = WisdomConversation.objects.create(
            user=user,
            tenant=user.tenant if hasattr(user, 'tenant') else None,
            thread=thread,
            conversation_text=conversation_text,
            conversation_date=delivery_log.delivered_at,
            conversation_tone=self._select_conversation_tone(delivery_log, thread),
            source_type='intervention_delivery',
            source_intervention_delivery=delivery_log,
            source_journal_entry=delivery_log.trigger_journal_entry,
            contextual_bridge_text=bridge_text,
            personalization_score=self._calculate_personalization_score(delivery_log, thread),
            conversation_metadata=self._generate_conversation_metadata(delivery_log),
            is_milestone_conversation=self._is_milestone_conversation(delivery_log, thread)
        )

        logger.info(f"Created wisdom conversation {conversation.id} for thread {thread.title}")
        return conversation

    def _get_or_create_thread(self, user: User, intervention) -> ConversationThread:
        """Get existing thread or create new one based on intervention type"""

        thread_type_mapping = {
            'THREE_GOOD_THINGS': 'three_good_things',
            'GRATITUDE_JOURNAL': 'gratitude_journey',
            'CBT_THOUGHT_RECORD': 'cbt_cognitive',
            'MOTIVATIONAL_INTERVIEWING': 'motivational_growth',
            'CRISIS_SUPPORT': 'crisis_recovery',
            'STRESS_MANAGEMENT': 'stress_management',
            'WORKPLACE_WELLNESS': 'workplace_wellness',
            'PREVENTIVE_CARE': 'preventive_care',
        }

        intervention_type = intervention.intervention_type
        thread_type = thread_type_mapping.get(intervention_type, 'workplace_wellness')

        thread, created = ConversationThread.objects.get_or_create(
            user=user,
            thread_type=thread_type,
            defaults={
                'tenant': user.tenant if hasattr(user, 'tenant') else None,
                'title': self._generate_thread_title(thread_type, user),
                'description': self._generate_thread_description(thread_type),
                'priority_level': self._get_thread_priority(intervention_type),
                'narrative_style': self._select_narrative_style(user, intervention_type),
            }
        )

        if created:
            logger.info(f"Created new conversation thread: {thread.title} for user {user.peoplename}")

        return thread

    def _generate_conversation_text(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Generate the main conversational text using appropriate template"""

        intervention_type = delivery_log.intervention.intervention_type
        narrative_style = thread.narrative_style

        # Get template function
        template_func = self.tone_templates.get(intervention_type, {}).get(
            narrative_style,
            self._generic_warm_template
        )

        # Generate conversation using template
        conversation_text = template_func(delivery_log, thread)

        # Apply personalization
        conversation_text = self._apply_personalization(
            conversation_text, delivery_log, thread
        )

        return conversation_text

    def _generate_contextual_bridge(
        self,
        thread: ConversationThread,
        delivery_log: InterventionDeliveryLog
    ) -> str:
        """Generate bridging text that connects to previous conversation"""

        # Get last conversation in thread
        last_conversation = thread.wisdom_conversations.order_by('-sequence_number').first()

        if not last_conversation:
            return ""  # First conversation needs no bridge

        # Calculate time gap
        time_gap = delivery_log.delivered_at - last_conversation.conversation_date

        # Select bridge type based on context
        bridge_type = self._select_bridge_type(delivery_log, last_conversation, time_gap)

        # Generate bridge text
        bridge_text = self._generate_bridge_text(bridge_type, delivery_log, last_conversation)

        return bridge_text

    def _select_bridge_type(
        self,
        delivery_log: InterventionDeliveryLog,
        last_conversation: WisdomConversation,
        time_gap: timedelta
    ) -> str:
        """Select appropriate bridge type based on context"""

        # Crisis intervention always gets emotional bridge
        if delivery_log.intervention.intervention_type == 'CRISIS_SUPPORT':
            return 'emotional'

        # Milestone conversations get milestone bridge
        if delivery_log.effectiveness_score >= 4.5:
            return 'milestone'

        # Long time gaps get temporal bridge
        if time_gap.days > 7:
            return 'temporal'

        # Same intervention type gets thematic bridge
        if (last_conversation.source_intervention_delivery and
            last_conversation.source_intervention_delivery.intervention.intervention_type ==
            delivery_log.intervention.intervention_type):
            return 'thematic'

        # Default to emotional bridge
        return 'emotional'

    def _generate_bridge_text(
        self,
        bridge_type: str,
        delivery_log: InterventionDeliveryLog,
        last_conversation: WisdomConversation
    ) -> str:
        """Generate actual bridge text"""

        patterns = self.bridge_patterns.get(bridge_type, self.bridge_patterns['emotional'])
        base_text = patterns[hash(delivery_log.id.hex) % len(patterns)]

        # Personalize the bridge text
        user_name = delivery_log.user.peoplename or "friend"
        personalized_text = base_text.replace("your", f"{user_name}'s")

        return personalized_text

    # Template functions for different intervention types and tones

    def _three_good_things_warm_template(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Warm, supportive template for Three Good Things intervention"""

        user_name = delivery_log.user.peoplename or "friend"

        conversation_templates = [
            f"Hey {user_name}, I've been thinking about the power of gratitude in your daily life. "
            f"You know how sometimes the world feels overwhelming, especially in your work? "
            f"I want to share something beautiful with you - a simple practice that can shift everything. "
            f"Tonight, before you sleep, think of three good things that happened today. "
            f"They don't need to be big - maybe a colleague's smile, a moment of calm, "
            f"or simply getting through a challenging task. Write them down, and for each one, "
            f"ask yourself: why was this good? What made it meaningful? "
            f"This isn't just positive thinking - it's rewiring your brain to notice the light "
            f"that's always there, even on the darkest days. You deserve to see that light, {user_name}.",

            f"I keep thinking about your resilience, {user_name}, and how you navigate each day. "
            f"There's something I want to gift you - a moment of reflection that can change everything. "
            f"As you wind down tonight, I invite you to pause and identify three good things from your day. "
            f"Maybe it was finally solving that problem at work, a kind word from a friend, "
            f"or simply the taste of your morning coffee. Whatever they are, hold them gently. "
            f"For each good thing, dig a little deeper - why did it matter? How did it make you feel? "
            f"This practice isn't about ignoring difficulties; it's about training your heart "
            f"to recognize the goodness that coexists with challenge. You're building a foundation "
            f"of gratitude that will support you through anything.",
        ]

        return conversation_templates[hash(delivery_log.id.hex) % len(conversation_templates)]

    def _gratitude_warm_template(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Warm template for gratitude journal intervention"""

        user_name = delivery_log.user.peoplename or "friend"

        conversation_templates = [
            f"Dear {user_name}, there's something magical about gratitude that I want to explore with you. "
            f"In your busy world of schedules and deadlines, it's easy to rush past the moments "
            f"that actually nourish your soul. But what if we slowed down together? "
            f"I'm inviting you to start a gratitude practice - not as another task on your list, "
            f"but as a gift to yourself. Each day, notice what you're grateful for. "
            f"It might be the warmth of sunlight through your window, a supportive text from a friend, "
            f"or the satisfaction of completing something meaningful. Write these moments down. "
            f"Let them remind you that even in chaos, there's always something to treasure. "
            f"Your heart knows how to recognize goodness, {user_name}. Let's help it remember.",

            f"I've been reflecting on your journey, {user_name}, and I'm struck by your strength. "
            f"Today, I want to offer you a different kind of strength - the power of gratitude. "
            f"Research shows that people who practice gratitude regularly experience better sleep, "
            f"stronger relationships, and greater resilience. But beyond the science, there's something "
            f"deeply human about acknowledging what we're thankful for. It connects us to what matters most. "
            f"Will you try something with me? Each morning or evening, write down three things you're grateful for. "
            f"They can be profound or simple - both matter equally. Notice how this practice "
            f"shifts your perspective over time. You're not just listing good things; "
            f"you're training your heart to be a magnet for joy.",
        ]

        return conversation_templates[hash(delivery_log.id.hex) % len(conversation_templates)]

    def _cbt_warm_template(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Warm template for CBT thought record intervention"""

        user_name = delivery_log.user.peoplename or "friend"

        conversation_templates = [
            f"Hi {user_name}, I want to share something important about the thoughts that visit your mind. "
            f"You know those moments when your inner voice gets really loud, especially during stressful times at work? "
            f"Those thoughts aren't always telling you the truth. They're often old patterns, worn grooves "
            f"from past experiences that don't serve you anymore. But here's the beautiful thing - "
            f"you have more power over your thoughts than you realize. "
            f"When you notice yourself thinking 'I'm not good enough' or 'This is too hard,' "
            f"pause and ask: Is this thought helpful? Is it even true? What would I tell a good friend "
            f"in this situation? You can actually rewrite the story your mind tells you. "
            f"It takes practice, but every time you question an unhelpful thought, "
            f"you're building a healthier relationship with your own mind. You deserve that kindness, {user_name}.",

            f"I've been thinking about your thought patterns, {user_name}, and how they shape your daily experience. "
            f"Sometimes our minds become echo chambers, repeating the same worries and doubts. "
            f"But what if I told you that you could become the editor of your own thoughts? "
            f"When you catch yourself in a spiral of negative thinking, try this: "
            f"Write down the thought that's bothering you. Then ask yourself - what evidence do I have "
            f"that this is true? What evidence suggests it might not be? What would a balanced view look like? "
            f"This isn't about forcing positivity; it's about finding truth and balance. "
            f"Your thoughts influence your feelings, which influence your actions. "
            f"By changing your thoughts, you're changing your entire experience of life. "
            f"That's incredibly powerful, and you absolutely have the strength to do this.",
        ]

        return conversation_templates[hash(delivery_log.id.hex) % len(conversation_templates)]

    def _crisis_stabilizing_template(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Stabilizing template for crisis support intervention"""

        user_name = delivery_log.user.peoplename or "friend"

        conversation_templates = [
            f"Dear {user_name}, I want you to know that you are not alone right now. "
            f"What you're feeling is overwhelming, and that's completely understandable. "
            f"First, let's focus on this moment - just this moment. Take three slow, deep breaths with me. "
            f"Feel your feet on the ground. Notice five things you can see around you. "
            f"You are safe right now. These feelings, as intense as they are, will pass. "
            f"I need you to remember that reaching out was brave. Asking for help takes courage. "
            f"If you're having thoughts of hurting yourself, please contact emergency services "
            f"or a crisis helpline immediately. Your life has value, and there are people trained "
            f"to support you through this darkness. This pain is temporary, but your life is precious. "
            f"Hold on to that truth, {user_name}. Better days are coming.",

            f"{user_name}, I see you're in significant distress right now, and I want to be here with you. "
            f"Sometimes life feels unbearable, and the pain seems endless. But you've survived "
            f"difficult times before, and you have that same strength within you now. "
            f"Let's focus on getting through the next hour, then the next day. "
            f"Grounding techniques can help: name three things you can touch, two things you can smell, "
            f"one thing you can taste. This brings you back to the present moment. "
            f"Please don't make any permanent decisions based on temporary feelings. "
            f"If you're considering self-harm, call 988 (Suicide & Crisis Lifeline) or emergency services. "
            f"There are people who want to help you carry this burden. "
            f"Your story isn't over, {user_name}. This chapter is painful, but it's not the end.",
        ]

        return conversation_templates[hash(delivery_log.id.hex) % len(conversation_templates)]

    def _generic_warm_template(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Generic warm template for any intervention type"""

        user_name = delivery_log.user.peoplename or "friend"

        return (f"Hi {user_name}, I've been reflecting on your journey and wanted to share "
                f"something that might be helpful. You've shown such resilience in facing "
                f"your challenges, and I believe this next step in your growth will serve you well. "
                f"Remember that every small action you take toward better mental health "
                f"is meaningful and worthy of recognition. You're doing important work, "
                f"and I'm here to support you along the way.")

    def _select_conversation_tone(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Select appropriate conversation tone based on context"""

        intervention_type = delivery_log.intervention.intervention_type

        if intervention_type == 'CRISIS_SUPPORT':
            return 'crisis_stabilizing'
        elif delivery_log.effectiveness_score >= 4.5:
            return 'celebratory'
        elif intervention_type in ['THREE_GOOD_THINGS', 'GRATITUDE_JOURNAL']:
            return 'encouraging'
        elif intervention_type == 'CBT_THOUGHT_RECORD':
            return 'supportive'
        elif intervention_type == 'MOTIVATIONAL_INTERVIEWING':
            return 'motivational'
        else:
            return 'supportive'

    def _calculate_personalization_score(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> float:
        """Calculate how well personalized this conversation is"""

        base_score = 0.5  # Start with neutral

        # Increase for user name usage
        if delivery_log.user.peoplename:
            base_score += 0.1

        # Increase for intervention history
        user_history = InterventionDeliveryLog.objects.filter(
            user=delivery_log.user,
            intervention__intervention_type=delivery_log.intervention.intervention_type
        ).count()

        if user_history > 1:
            base_score += 0.2

        # Increase for thread personalization data
        if thread.personalization_data:
            base_score += 0.1

        # Increase for contextual relevance
        if delivery_log.trigger_journal_entry:
            base_score += 0.1

        return min(1.0, base_score)

    def _generate_conversation_metadata(self, delivery_log: InterventionDeliveryLog) -> Dict:
        """Generate metadata for the conversation"""

        return {
            'intervention_type': delivery_log.intervention.intervention_type,
            'intervention_title': delivery_log.intervention.title,
            'delivery_method': delivery_log.delivery_method,
            'effectiveness_score': delivery_log.effectiveness_score,
            'escalation_level': delivery_log.escalation_level,
            'generated_at': timezone.now().isoformat(),
            'keywords': self._extract_keywords(delivery_log),
        }

    def _extract_keywords(self, delivery_log: InterventionDeliveryLog) -> List[str]:
        """Extract relevant keywords from delivery context"""

        keywords = []

        # Add intervention type keywords
        type_keywords = {
            'THREE_GOOD_THINGS': ['gratitude', 'positivity', 'reflection'],
            'GRATITUDE_JOURNAL': ['thankfulness', 'appreciation', 'mindfulness'],
            'CBT_THOUGHT_RECORD': ['thoughts', 'cognitive', 'reframing'],
            'MOTIVATIONAL_INTERVIEWING': ['motivation', 'goals', 'change'],
            'CRISIS_SUPPORT': ['crisis', 'safety', 'stabilization'],
        }

        keywords.extend(type_keywords.get(delivery_log.intervention.intervention_type, []))

        # Add escalation level keywords
        if delivery_log.escalation_level >= 3:
            keywords.extend(['urgent', 'priority', 'intensive'])

        return keywords

    def _is_milestone_conversation(
        self,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> bool:
        """Determine if this is a milestone conversation"""

        # High effectiveness indicates milestone
        if delivery_log.effectiveness_score >= 4.5:
            return True

        # Crisis recovery is always milestone
        if delivery_log.intervention.intervention_type == 'CRISIS_SUPPORT':
            return True

        # Thread milestones (every 10th conversation)
        conversation_count = thread.conversation_count + 1
        if conversation_count % 10 == 0:
            return True

        return False

    def _generate_thread_title(self, thread_type: str, user: User) -> str:
        """Generate appropriate title for conversation thread"""

        user_name = user.peoplename or "Your"

        title_templates = {
            'gratitude_journey': f"{user_name} Gratitude Journey",
            'stress_management': f"{user_name} Stress Management Path",
            'three_good_things': f"{user_name} Three Good Things Practice",
            'cbt_cognitive': f"{user_name} Cognitive Wellness Journey",
            'crisis_recovery': f"{user_name} Recovery & Healing",
            'workplace_wellness': f"{user_name} Workplace Wellness",
            'motivational_growth': f"{user_name} Growth & Motivation",
            'preventive_care': f"{user_name} Preventive Mental Health",
            'achievement_celebration': f"{user_name} Achievements & Milestones",
            'reflection_insights': f"{user_name} Reflection & Insights",
        }

        return title_templates.get(thread_type, f"{user_name} Wisdom Conversations")

    def _generate_thread_description(self, thread_type: str) -> str:
        """Generate description for conversation thread"""

        descriptions = {
            'gratitude_journey': "A personal journey exploring gratitude and appreciation in daily life",
            'stress_management': "Conversations focused on managing stress and building resilience",
            'three_good_things': "Daily reflections on positive experiences and meaningful moments",
            'cbt_cognitive': "Cognitive behavioral insights for healthier thought patterns",
            'crisis_recovery': "Support and guidance through difficult times toward healing",
            'workplace_wellness': "Mental health support tailored for workplace challenges",
            'motivational_growth': "Motivation and encouragement for personal development",
            'preventive_care': "Proactive mental health practices for ongoing wellbeing",
            'achievement_celebration': "Celebrating milestones and personal achievements",
            'reflection_insights': "Deep reflections and insights for personal growth",
        }

        return descriptions.get(thread_type, "Supportive conversations for mental health and wellbeing")

    def _get_thread_priority(self, intervention_type: str) -> int:
        """Get priority level for thread based on intervention type"""

        priority_mapping = {
            'CRISIS_SUPPORT': 5,
            'CBT_THOUGHT_RECORD': 3,
            'MOTIVATIONAL_INTERVIEWING': 3,
            'STRESS_MANAGEMENT': 3,
            'THREE_GOOD_THINGS': 2,
            'GRATITUDE_JOURNAL': 2,
            'WORKPLACE_WELLNESS': 2,
            'PREVENTIVE_CARE': 1,
        }

        return priority_mapping.get(intervention_type, 2)

    def _select_narrative_style(self, user: User, intervention_type: str) -> str:
        """Select narrative style based on user and intervention type"""

        # Crisis situations need stabilizing style
        if intervention_type == 'CRISIS_SUPPORT':
            return 'crisis_stabilizing'

        # CBT might need more clinical approach
        if intervention_type == 'CBT_THOUGHT_RECORD':
            return 'professional_clinical'

        # Default to warm supportive for most interventions
        return 'warm_supportive'

    def _apply_personalization(
        self,
        conversation_text: str,
        delivery_log: InterventionDeliveryLog,
        thread: ConversationThread
    ) -> str:
        """Apply user-specific personalization to conversation text"""

        personalized_text = conversation_text

        # Apply workplace context if available
        if hasattr(delivery_log.user, 'designation') and delivery_log.user.designation:
            role_context = self._get_role_context(delivery_log.user.designation)
            if role_context:
                personalized_text = personalized_text.replace(
                    "in your work", f"in your role as {delivery_log.user.designation}"
                )

        # Apply effectiveness history
        personalization_data = thread.personalization_data
        if personalization_data.get('preferred_examples'):
            # Use preferred examples in future iterations
            pass

        return personalized_text

    def _get_role_context(self, designation: str) -> str:
        """Get workplace context based on user designation"""

        role_contexts = {
            'manager': 'managing your team',
            'supervisor': 'supervising your staff',
            'technician': 'your technical work',
            'engineer': 'your engineering projects',
            'administrator': 'your administrative duties',
        }

        for role, context in role_contexts.items():
            if role.lower() in designation.lower():
                return context

        return ""