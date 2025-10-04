"""
CBT Thought Record Templates with Mood Pattern Triggers

Dynamic CBT thought record templates that adapt to user's specific triggers and patterns.
Based on clinical CBT protocols and workplace-specific stressor research.

This service:
- Generates personalized CBT thought record templates
- Adapts templates based on user's historical triggers and patterns
- Provides contextual prompts for workplace-specific situations
- Implements progressive CBT skill building

Clinical foundation: Beck's Cognitive Therapy, Burns' Feeling Good methodology, workplace CBT research.
"""

import logging
from django.utils import timezone
from collections import defaultdict, Counter
from datetime import timedelta

from apps.wellness.models import (
    MentalHealthIntervention,
    InterventionDeliveryLog,
    MentalHealthInterventionType
)

logger = logging.getLogger(__name__)


class CBTThoughtRecordTemplateEngine:
    """
    Dynamic CBT thought record template generation with pattern-based customization

    Adapts CBT thought record templates based on:
    - User's historical thought patterns
    - Common workplace triggers
    - Mood pattern analysis
    - Progressive skill building
    """

    def __init__(self):
        # Common workplace cognitive distortions (Beck's categories adapted for workplace)
        self.WORKPLACE_COGNITIVE_DISTORTIONS = {
            'catastrophizing': {
                'definition': 'Expecting the worst possible outcome',
                'workplace_examples': [
                    'One mistake means I\'ll be fired',
                    'If this project fails, my career is over',
                    'This equipment breakdown will ruin everything'
                ],
                'prompts': [
                    'What\'s the worst that could realistically happen?',
                    'How likely is this worst-case scenario?',
                    'What would you tell a colleague in this situation?'
                ]
            },
            'all_or_nothing': {
                'definition': 'Seeing things as completely good or completely bad',
                'workplace_examples': [
                    'I\'m either perfect at my job or completely incompetent',
                    'This task is either done perfectly or it\'s worthless',
                    'If I can\'t fix this, I\'m a total failure'
                ],
                'prompts': [
                    'What would "good enough" look like in this situation?',
                    'Can you think of a middle ground between perfect and failure?',
                    'How would you rate your performance on a scale of 1-10?'
                ]
            },
            'personalization': {
                'definition': 'Blaming yourself for things outside your control',
                'workplace_examples': [
                    'The team meeting went badly because of something I said',
                    'If equipment breaks, it\'s because I didn\'t maintain it properly',
                    'My colleague is upset, it must be my fault'
                ],
                'prompts': [
                    'What factors outside your control contributed to this?',
                    'Would you blame a colleague for this same situation?',
                    'What percentage of this situation was actually under your control?'
                ]
            },
            'mind_reading': {
                'definition': 'Assuming you know what others are thinking',
                'workplace_examples': [
                    'My supervisor thinks I\'m incompetent',
                    'Everyone can tell I don\'t know what I\'m doing',
                    'My colleagues think I\'m lazy'
                ],
                'prompts': [
                    'What actual evidence do you have for what they\'re thinking?',
                    'What are some alternative explanations for their behavior?',
                    'How could you find out what they actually think?'
                ]
            },
            'fortune_telling': {
                'definition': 'Predicting negative outcomes without evidence',
                'workplace_examples': [
                    'This meeting is going to go terribly',
                    'I\'ll never be able to learn this new procedure',
                    'Tomorrow will be another awful day at work'
                ],
                'prompts': [
                    'What evidence do you have that this will happen?',
                    'What has happened in similar situations before?',
                    'What\'s a more realistic prediction based on facts?'
                ]
            }
        }

        # Workplace-specific triggers and corresponding templates
        self.WORKPLACE_TRIGGER_TEMPLATES = {
            'equipment_failure': {
                'situation_prompt': 'Describe what equipment failed and how it affected your work:',
                'emotion_prompts': [
                    'How frustrated are you feeling? (1-10)',
                    'Are you feeling anxious about delays? (1-10)',
                    'Any feelings of personal responsibility? (1-10)'
                ],
                'thought_prompts': [
                    'What went through your mind when the equipment failed?',
                    'What does this mean about your abilities as a worker?',
                    'What are you predicting will happen because of this?'
                ],
                'evidence_prompts': [
                    'How often does this equipment usually work properly?',
                    'Have other people had similar equipment issues?',
                    'What factors contributed to this failure that were outside your control?'
                ],
                'reframe_prompts': [
                    'What would you tell a colleague who experienced this same problem?',
                    'How might you handle this situation in a practical way?',
                    'What\'s a more balanced way to think about equipment failures?'
                ]
            },
            'deadline_pressure': {
                'situation_prompt': 'Describe the deadline and what\'s causing the time pressure:',
                'emotion_prompts': [
                    'How stressed are you feeling about the deadline? (1-10)',
                    'Are you feeling overwhelmed by the workload? (1-10)',
                    'Any anxiety about disappointing others? (1-10)'
                ],
                'thought_prompts': [
                    'What thoughts are going through your mind about this deadline?',
                    'What are you telling yourself about your ability to meet it?',
                    'What do you think will happen if you\'re late?'
                ],
                'evidence_prompts': [
                    'What factors have contributed to this time pressure?',
                    'How much of this situation was within your control?',
                    'What resources or support might be available?'
                ],
                'reframe_prompts': [
                    'What\'s the most realistic assessment of this deadline?',
                    'How can you prioritize the most important parts?',
                    'What would good enough look like in this situation?'
                ]
            },
            'interpersonal_conflict': {
                'situation_prompt': 'Describe the conflict or difficult interaction:',
                'emotion_prompts': [
                    'How upset are you feeling about this interaction? (1-10)',
                    'Are you feeling angry or frustrated? (1-10)',
                    'Any feelings of being misunderstood? (1-10)'
                ],
                'thought_prompts': [
                    'What are you thinking about the other person\'s intentions?',
                    'What does this conflict mean about your working relationships?',
                    'What are you predicting will happen going forward?'
                ],
                'evidence_prompts': [
                    'What actual evidence do you have about their intentions?',
                    'What might be their perspective on this situation?',
                    'What external factors might have influenced their behavior?'
                ],
                'reframe_prompts': [
                    'How might this look from their point of view?',
                    'What\'s the most charitable interpretation of their actions?',
                    'How can you focus on resolving the issue rather than blame?'
                ]
            },
            'performance_concerns': {
                'situation_prompt': 'Describe what happened that\'s making you question your performance:',
                'emotion_prompts': [
                    'How worried are you about your job performance? (1-10)',
                    'Are you feeling inadequate or incompetent? (1-10)',
                    'Any fear about job security? (1-10)'
                ],
                'thought_prompts': [
                    'What are you telling yourself about your capabilities?',
                    'What does this incident mean about your value as an employee?',
                    'What are you predicting about your future at work?'
                ],
                'evidence_prompts': [
                    'What feedback have you actually received about your work?',
                    'What are your actual job responsibilities and how do you measure up?',
                    'What evidence do you have of your competence and contributions?'
                ],
                'reframe_prompts': [
                    'How would you evaluate a colleague who had this same experience?',
                    'What learning opportunities does this situation provide?',
                    'What\'s a more balanced assessment of your overall performance?'
                ]
            }
        }

        # Progressive CBT skill building templates
        self.SKILL_PROGRESSION_TEMPLATES = {
            'beginner': {
                'guidance': 'This is your introduction to thought records. We\'ll go step by step.',
                'simplified_steps': ['situation', 'emotion', 'automatic_thought', 'balanced_thought'],
                'extra_support': True,
                'examples_provided': True
            },
            'intermediate': {
                'guidance': 'You\'re developing CBT skills. Let\'s add evidence examination.',
                'simplified_steps': ['situation', 'emotion', 'automatic_thought', 'evidence_for', 'evidence_against', 'balanced_thought'],
                'extra_support': False,
                'examples_provided': False
            },
            'advanced': {
                'guidance': 'You\'re skilled at thought records. Let\'s focus on cognitive distortions.',
                'simplified_steps': ['situation', 'emotion', 'automatic_thought', 'cognitive_distortion', 'evidence_analysis', 'balanced_thought', 'behavioral_experiment'],
                'extra_support': False,
                'examples_provided': False
            }
        }

    def generate_thought_record_template(self, user, journal_entry=None, mood_rating=None, stress_triggers=None):
        """
        Generate personalized CBT thought record template

        Args:
            user: User object
            journal_entry: Current journal entry that triggered this (optional)
            mood_rating: Current mood rating (1-10)
            stress_triggers: List of current stress triggers

        Returns:
            dict: Customized thought record template
        """
        logger.info(f"Generating CBT thought record template for user {user.id}")

        # Analyze user's CBT experience level
        skill_level = self._assess_user_cbt_skill_level(user)

        # Identify primary trigger/pattern
        primary_trigger = self._identify_primary_trigger(journal_entry, stress_triggers)

        # Get user's historical patterns
        user_patterns = self._analyze_user_thought_patterns(user)

        # Generate customized template
        template = self._build_template(
            skill_level=skill_level,
            primary_trigger=primary_trigger,
            user_patterns=user_patterns,
            current_mood=mood_rating
        )

        # Add personalized prompts
        template = self._add_personalized_prompts(template, user_patterns)

        # Add skill-building elements
        template = self._add_skill_building_elements(template, skill_level, user_patterns)

        return template

    def _assess_user_cbt_skill_level(self, user):
        """Assess user's CBT skill level based on previous completions"""

        # Count completed CBT thought records
        completed_records = InterventionDeliveryLog.objects.filter(
            user=user,
            intervention__intervention_type=MentalHealthInterventionType.THOUGHT_RECORD,
            was_completed=True
        ).count()

        # Assess completion quality (if user_response data available)
        quality_scores = []
        recent_completions = InterventionDeliveryLog.objects.filter(
            user=user,
            intervention__intervention_type=MentalHealthInterventionType.THOUGHT_RECORD,
            was_completed=True,
            user_response__isnull=False
        ).order_by('-delivered_at')[:5]

        for completion in recent_completions:
            if completion.user_response and isinstance(completion.user_response, dict):
                # Simple quality assessment based on response completeness
                steps_completed = len([k for k, v in completion.user_response.items() if v and str(v).strip()])
                quality_scores.append(steps_completed)

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # Determine skill level
        if completed_records >= 10 and avg_quality >= 6:
            return 'advanced'
        elif completed_records >= 5 and avg_quality >= 4:
            return 'intermediate'
        else:
            return 'beginner'

    def _identify_primary_trigger(self, journal_entry, stress_triggers):
        """Identify the primary trigger for this thought record"""

        # If stress triggers provided, analyze them
        if stress_triggers:
            for trigger in stress_triggers:
                trigger_lower = trigger.lower()

                if any(word in trigger_lower for word in ['equipment', 'machine', 'tool', 'device']):
                    return 'equipment_failure'
                elif any(word in trigger_lower for word in ['deadline', 'due', 'time', 'urgent']):
                    return 'deadline_pressure'
                elif any(word in trigger_lower for word in ['conflict', 'argument', 'difficult', 'tension']):
                    return 'interpersonal_conflict'
                elif any(word in trigger_lower for word in ['performance', 'mistake', 'error', 'feedback']):
                    return 'performance_concerns'

        # If journal entry provided, analyze content
        if journal_entry and journal_entry.content:
            content_lower = journal_entry.content.lower()

            if any(word in content_lower for word in ['equipment', 'broke', 'malfunction']):
                return 'equipment_failure'
            elif any(word in content_lower for word in ['deadline', 'behind', 'rush']):
                return 'deadline_pressure'
            elif any(word in content_lower for word in ['colleague', 'supervisor', 'conflict']):
                return 'interpersonal_conflict'
            elif any(word in content_lower for word in ['mistake', 'wrong', 'failed']):
                return 'performance_concerns'

        # Default to general workplace stress
        return 'general_workplace_stress'

    def _analyze_user_thought_patterns(self, user):
        """Analyze user's historical thought patterns from previous thought records"""

        patterns = {
            'common_distortions': [],
            'frequent_triggers': [],
            'emotional_themes': [],
            'progress_indicators': []
        }

        # Get user's previous thought record completions
        previous_records = InterventionDeliveryLog.objects.filter(
            user=user,
            intervention__intervention_type=MentalHealthInterventionType.THOUGHT_RECORD,
            was_completed=True,
            user_response__isnull=False
        ).order_by('-delivered_at')[:20]  # Last 20 completions

        if not previous_records:
            return patterns

        # Analyze patterns from user responses
        all_thoughts = []
        all_emotions = []
        all_situations = []

        for record in previous_records:
            if record.user_response and isinstance(record.user_response, dict):
                # Extract automatic thoughts
                thought = record.user_response.get('automatic_thought', '')
                if thought:
                    all_thoughts.append(thought.lower())

                # Extract emotions
                emotion = record.user_response.get('emotion', '')
                if emotion:
                    all_emotions.append(emotion.lower())

                # Extract situations
                situation = record.user_response.get('situation', '')
                if situation:
                    all_situations.append(situation.lower())

        # Identify common cognitive distortions
        patterns['common_distortions'] = self._identify_distortion_patterns(all_thoughts)

        # Identify frequent triggers
        patterns['frequent_triggers'] = self._identify_trigger_patterns(all_situations)

        # Identify emotional themes
        patterns['emotional_themes'] = self._identify_emotional_patterns(all_emotions)

        return patterns

    def _identify_distortion_patterns(self, thoughts):
        """Identify common cognitive distortion patterns in user's thoughts"""
        distortion_indicators = {
            'catastrophizing': ['disaster', 'terrible', 'awful', 'worst', 'ruined', 'everything'],
            'all_or_nothing': ['always', 'never', 'completely', 'totally', 'perfect', 'failure'],
            'personalization': ['my fault', 'because of me', 'i caused', 'i should have'],
            'mind_reading': ['they think', 'he thinks', 'she thinks', 'everyone knows'],
            'fortune_telling': ['will never', 'going to fail', 'will happen', 'going to be']
        }

        found_patterns = []
        all_thoughts_text = ' '.join(thoughts)

        for distortion, indicators in distortion_indicators.items():
            count = sum(1 for indicator in indicators if indicator in all_thoughts_text)
            if count >= 2:  # Found in at least 2 thoughts
                found_patterns.append(distortion)

        return found_patterns

    def _identify_trigger_patterns(self, situations):
        """Identify common trigger patterns"""
        trigger_keywords = {
            'equipment_failure': ['equipment', 'machine', 'broke', 'malfunction'],
            'deadline_pressure': ['deadline', 'time', 'rush', 'behind'],
            'interpersonal_conflict': ['colleague', 'supervisor', 'argument', 'conflict'],
            'performance_concerns': ['mistake', 'error', 'feedback', 'performance']
        }

        found_patterns = []
        all_situations_text = ' '.join(situations)

        for pattern, keywords in trigger_keywords.items():
            count = sum(1 for keyword in keywords if keyword in all_situations_text)
            if count >= 2:
                found_patterns.append(pattern)

        return found_patterns

    def _identify_emotional_patterns(self, emotions):
        """Identify common emotional patterns"""
        emotion_categories = {
            'anxiety': ['worried', 'anxious', 'nervous', 'scared', 'panic'],
            'anger': ['angry', 'frustrated', 'mad', 'irritated', 'furious'],
            'sadness': ['sad', 'depressed', 'down', 'hopeless', 'disappointed'],
            'stress': ['stressed', 'overwhelmed', 'pressure', 'tense']
        }

        found_patterns = []
        all_emotions_text = ' '.join(emotions)

        for category, keywords in emotion_categories.items():
            count = sum(1 for keyword in keywords if keyword in all_emotions_text)
            if count >= 2:
                found_patterns.append(category)

        return found_patterns

    def _build_template(self, skill_level, primary_trigger, user_patterns, current_mood):
        """Build the customized thought record template"""

        # Get base template for skill level
        base_template = self.SKILL_PROGRESSION_TEMPLATES[skill_level].copy()

        # Get trigger-specific template if available
        trigger_template = self.WORKPLACE_TRIGGER_TEMPLATES.get(
            primary_trigger,
            self.WORKPLACE_TRIGGER_TEMPLATES['performance_concerns']  # Default
        )

        # Build complete template
        template = {
            'template_id': f"cbt_thought_record_{skill_level}_{primary_trigger}",
            'skill_level': skill_level,
            'primary_trigger': primary_trigger,
            'guidance_text': base_template['guidance'],
            'steps': base_template['simplified_steps'],
            'prompts': {},
            'examples': {},
            'distortion_focus': [],
            'personalization': {
                'user_patterns_detected': len(user_patterns['common_distortions']) > 0,
                'frequent_triggers': user_patterns['frequent_triggers'],
                'emotional_themes': user_patterns['emotional_themes']
            }
        }

        # Add step-specific prompts
        for step in template['steps']:
            if step == 'situation':
                template['prompts'][step] = trigger_template['situation_prompt']
            elif step == 'emotion':
                template['prompts'][step] = trigger_template['emotion_prompts']
            elif step == 'automatic_thought':
                template['prompts'][step] = trigger_template['thought_prompts']
            elif step in ['evidence_for', 'evidence_against', 'evidence_analysis']:
                template['prompts'][step] = trigger_template['evidence_prompts']
            elif step == 'balanced_thought':
                template['prompts'][step] = trigger_template['reframe_prompts']
            elif step == 'cognitive_distortion':
                template['prompts'][step] = self._get_distortion_prompts(user_patterns['common_distortions'])

        # Add examples for beginners
        if base_template['examples_provided']:
            template['examples'] = self._get_examples_for_trigger(primary_trigger)

        return template

    def _add_personalized_prompts(self, template, user_patterns):
        """Add personalized prompts based on user's patterns"""

        if user_patterns['common_distortions']:
            # Add distortion-specific guidance
            template['distortion_focus'] = user_patterns['common_distortions']
            template['personalized_guidance'] = f"Based on your previous entries, you tend toward {', '.join(user_patterns['common_distortions'])} thinking patterns. Let's pay special attention to these."

        if user_patterns['emotional_themes']:
            # Add emotion-specific prompts
            dominant_emotion = user_patterns['emotional_themes'][0] if user_patterns['emotional_themes'] else None
            if dominant_emotion:
                template['emotion_focus'] = dominant_emotion
                emotion_prompts = {
                    'anxiety': "You often experience anxiety. Rate your worry level and identify what specifically you're anxious about.",
                    'anger': "You frequently feel frustrated. What triggered this anger and what thoughts are fueling it?",
                    'sadness': "You commonly feel down. What thoughts are contributing to this sadness?",
                    'stress': "You regularly feel overwhelmed. What aspects of this situation feel most stressful?"
                }
                template['emotion_guidance'] = emotion_prompts.get(dominant_emotion, "")

        return template

    def _add_skill_building_elements(self, template, skill_level, user_patterns):
        """Add skill-building elements appropriate to user's level"""

        if skill_level == 'beginner':
            template['learning_focus'] = "Today we're learning to identify the connection between thoughts and feelings."
            template['success_criteria'] = "Complete each step thoughtfully. There are no wrong answers."

        elif skill_level == 'intermediate':
            template['learning_focus'] = "We're building your skills in examining evidence for and against your thoughts."
            template['success_criteria'] = "Practice looking at situations from multiple perspectives."

        elif skill_level == 'advanced':
            template['learning_focus'] = "Advanced CBT skills: identifying specific cognitive distortions and planning behavioral experiments."
            template['success_criteria'] = "Focus on developing a specific plan to test your balanced thought."

        # Add distortion education if user shows patterns
        if user_patterns['common_distortions']:
            template['distortion_education'] = {}
            for distortion in user_patterns['common_distortions']:
                if distortion in self.WORKPLACE_COGNITIVE_DISTORTIONS:
                    template['distortion_education'][distortion] = self.WORKPLACE_COGNITIVE_DISTORTIONS[distortion]

        return template

    def _get_distortion_prompts(self, common_distortions):
        """Get prompts for identifying cognitive distortions"""
        if common_distortions:
            # Focus on user's common distortions
            prompts = []
            for distortion in common_distortions:
                if distortion in self.WORKPLACE_COGNITIVE_DISTORTIONS:
                    prompts.extend(self.WORKPLACE_COGNITIVE_DISTORTIONS[distortion]['prompts'])
            return prompts
        else:
            # General distortion identification prompts
            return [
                "Are you expecting the worst possible outcome?",
                "Are you seeing this situation as all good or all bad?",
                "Are you blaming yourself for things outside your control?",
                "Are you assuming you know what others are thinking?",
                "Are you predicting the future without evidence?"
            ]

    def _get_examples_for_trigger(self, trigger):
        """Get examples for specific triggers to help beginners"""
        examples = {
            'equipment_failure': {
                'situation': "The conveyor belt broke down during my shift",
                'emotion': "Frustrated (7/10), Worried about delays (6/10)",
                'automatic_thought': "This always happens when I'm working. I must not be maintaining equipment properly.",
                'balanced_thought': "Equipment breaks down sometimes regardless of maintenance. This isn't a reflection of my competence, and we have procedures to handle these situations."
            },
            'deadline_pressure': {
                'situation': "I have three reports due tomorrow and haven't finished any of them",
                'emotion': "Overwhelmed (8/10), Anxious (7/10)",
                'automatic_thought': "I'll never get these done. I'm going to disappoint everyone and look incompetent.",
                'balanced_thought': "I can prioritize the most important parts and communicate with my supervisor about realistic timelines. Doing my best is sufficient."
            },
            'interpersonal_conflict': {
                'situation': "My colleague snapped at me during the team meeting",
                'emotion': "Hurt (6/10), Angry (5/10)",
                'automatic_thought': "They obviously don't respect me. Everyone probably thinks I'm incompetent.",
                'balanced_thought': "They might be having a stressful day. This one interaction doesn't define our working relationship or what others think of me."
            },
            'performance_concerns': {
                'situation': "I made an error in the safety checklist that my supervisor caught",
                'emotion': "Embarrassed (7/10), Worried (8/10)",
                'automatic_thought': "I'm terrible at this job. They're going to think I'm careless and maybe fire me.",
                'balanced_thought': "Everyone makes occasional mistakes. My supervisor is helping me improve, and one error doesn't define my overall performance."
            }
        }

        return examples.get(trigger, examples['performance_concerns'])

    def get_follow_up_questions(self, user, completed_template_response):
        """Generate follow-up questions based on completed thought record"""

        if not completed_template_response:
            return []

        follow_ups = []

        # Check if balanced thought was significantly different from automatic thought
        automatic_thought = completed_template_response.get('automatic_thought', '').lower()
        balanced_thought = completed_template_response.get('balanced_thought', '').lower()

        if automatic_thought and balanced_thought:
            # Simple similarity check
            common_words = set(automatic_thought.split()) & set(balanced_thought.split())
            if len(common_words) / max(len(automatic_thought.split()), 1) > 0.7:
                follow_ups.append("Your balanced thought is quite similar to your automatic thought. Can you try to find a more different perspective?")

        # Check for action planning
        if 'behavioral_experiment' not in completed_template_response:
            follow_ups.append("What's one small action you could take to test your balanced thought?")

        # Check emotional change
        initial_emotion_intensity = self._extract_emotion_intensity(completed_template_response.get('emotion', ''))
        if initial_emotion_intensity and initial_emotion_intensity >= 7:
            follow_ups.append("Your initial emotion was quite intense. How are you feeling now after completing this thought record?")

        # Suggest skill practice
        follow_ups.append("Which step of this thought record felt most challenging? We can focus on that skill in future exercises.")

        return follow_ups

    def _extract_emotion_intensity(self, emotion_text):
        """Extract emotion intensity rating from text"""
        import re
        # Look for patterns like "(8/10)" or "8/10" or "8 out of 10"
        patterns = [r'\((\d+)/10\)', r'(\d+)/10', r'(\d+)\s*out\s*of\s*10']

        for pattern in patterns:
            match = re.search(pattern, emotion_text)
            if match:
                return int(match.group(1))

        return None

    def generate_progress_summary(self, user, days=30):
        """Generate summary of user's CBT thought record progress"""

        since_date = timezone.now() - timedelta(days=days)
        completions = InterventionDeliveryLog.objects.filter(
            user=user,
            intervention__intervention_type=MentalHealthInterventionType.THOUGHT_RECORD,
            was_completed=True,
            delivered_at__gte=since_date
        ).order_by('delivered_at')

        if not completions:
            return {
                'total_completions': 0,
                'progress_level': 'beginner',
                'message': 'Start your CBT journey with your first thought record'
            }

        # Analyze progress
        total_completions = completions.count()

        # Assess improvement in completion quality
        early_completions = completions[:total_completions//2] if total_completions >= 4 else completions[:1]
        recent_completions = completions[total_completions//2:] if total_completions >= 4 else completions[1:]

        early_quality = self._assess_completion_quality(early_completions)
        recent_quality = self._assess_completion_quality(recent_completions)

        progress_summary = {
            'total_completions': total_completions,
            'progress_level': self._assess_user_cbt_skill_level(user),
            'completion_trend': 'improving' if recent_quality > early_quality else 'stable',
            'average_quality_score': recent_quality,
            'days_analyzed': days,
            'most_recent_completion': completions.last().delivered_at if completions else None,
            'skill_strengths': [],
            'areas_for_improvement': [],
            'next_learning_goals': []
        }

        # Add specific feedback
        if total_completions >= 10:
            progress_summary['skill_strengths'].append("Consistent practice with thought records")
        if recent_quality >= 6:
            progress_summary['skill_strengths'].append("Thorough completion of CBT steps")
        if recent_quality > early_quality:
            progress_summary['skill_strengths'].append("Improving CBT skills over time")

        # Areas for improvement
        if recent_quality < 4:
            progress_summary['areas_for_improvement'].append("Focus on completing all steps thoroughly")
        if total_completions < 5:
            progress_summary['areas_for_improvement'].append("Build consistency with regular practice")

        # Next learning goals
        current_level = progress_summary['progress_level']
        if current_level == 'beginner':
            progress_summary['next_learning_goals'] = [
                "Practice identifying the connection between thoughts and feelings",
                "Learn to separate facts from interpretations"
            ]
        elif current_level == 'intermediate':
            progress_summary['next_learning_goals'] = [
                "Develop skills in examining evidence",
                "Practice identifying cognitive distortions"
            ]
        else:
            progress_summary['next_learning_goals'] = [
                "Master advanced cognitive distortion identification",
                "Develop behavioral experiments to test thoughts"
            ]

        return progress_summary

    def _assess_completion_quality(self, completions):
        """Assess quality of thought record completions"""
        if not completions:
            return 0

        quality_scores = []
        for completion in completions:
            if completion.user_response and isinstance(completion.user_response, dict):
                # Count meaningful responses (non-empty and substantial)
                meaningful_responses = 0
                for key, value in completion.user_response.items():
                    if value and isinstance(value, str) and len(value.strip()) > 10:
                        meaningful_responses += 1
                    elif value and isinstance(value, list) and len(value) > 0:
                        meaningful_responses += 1

                quality_scores.append(meaningful_responses)

        return sum(quality_scores) / len(quality_scores) if quality_scores else 0