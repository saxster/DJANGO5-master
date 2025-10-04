"""
Seed Mental Health Interventions Command

Seeds the database with evidence-based mental health interventions including:
- Three Good Things (Seligman et al. - 6 month benefits)
- Gratitude interventions (workplace effectiveness validated)
- CBT behavioral activation (WHO-recommended)
- Motivational interviewing micro-interventions
- Stress management techniques

All content based on 2024 research findings and proven workplace effectiveness.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.wellness.models import (
    WellnessContent, WellnessContentCategory, WellnessDeliveryContext,
    WellnessContentLevel, EvidenceLevel, MentalHealthIntervention,
    MentalHealthInterventionType, InterventionDeliveryTiming, InterventionEvidenceBase
)
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seed database with evidence-based mental health interventions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Specific tenant to seed (default: all tenants)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing content',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧠 Seeding Mental Health Interventions...'))

        # Get target tenants
        target_tenant = options.get('tenant')
        if target_tenant:
            tenants = [Tenant.objects.get(subdomain_prefix=target_tenant)]
        else:
            tenants = list(Tenant.objects.all())

        overwrite = options.get('overwrite', False)
        total_created = 0

        for tenant in tenants:
            self.stdout.write(f'\n📋 Processing tenant: {tenant.tenantname}')

            # Get or create system user
            system_user = self._get_system_user(tenant)

            tenant_created = self._seed_interventions_for_tenant(tenant, system_user, overwrite)
            total_created += tenant_created

            self.stdout.write(f'   ✅ Created {tenant_created} interventions for {tenant.tenantname}')

        self.stdout.write(self.style.SUCCESS(f'\n🎉 Successfully created {total_created} mental health interventions!'))

    def _get_system_user(self, tenant):
        """Get or create system user for content creation"""
        system_user = User.objects.filter(
            tenant=tenant,
            isadmin=True
        ).first()

        if not system_user:
            system_user = User.objects.filter(tenant=tenant).first()

        return system_user

    def _seed_interventions_for_tenant(self, tenant, system_user, overwrite):
        """Seed all mental health interventions for a specific tenant"""
        created_count = 0

        # Positive Psychology Interventions
        created_count += self._create_three_good_things(tenant, system_user, overwrite)
        created_count += self._create_gratitude_interventions(tenant, system_user, overwrite)
        created_count += self._create_strength_spotting(tenant, system_user, overwrite)

        # CBT Behavioral Activation
        created_count += self._create_behavioral_activation(tenant, system_user, overwrite)
        created_count += self._create_thought_record(tenant, system_user, overwrite)
        created_count += self._create_activity_scheduling(tenant, system_user, overwrite)

        # Stress Management
        created_count += self._create_breathing_exercises(tenant, system_user, overwrite)
        created_count += self._create_progressive_relaxation(tenant, system_user, overwrite)

        # Motivational Interviewing
        created_count += self._create_motivational_checkin(tenant, system_user, overwrite)
        created_count += self._create_values_clarification(tenant, system_user, overwrite)

        # Crisis Support
        created_count += self._create_crisis_resources(tenant, system_user, overwrite)

        return created_count

    def _create_three_good_things(self, tenant, system_user, overwrite):
        """Create Three Good Things intervention (Seligman et al.)"""
        title = "Three Good Things Exercise"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Identify three positive things that happened today and reflect on why they occurred. Research shows 6-month lasting benefits.",
            content="""
**The Three Good Things Exercise**

*Research Foundation:* Developed by Dr. Martin Seligman, this exercise has been shown to increase happiness and reduce depression for up to 6 months.

**Instructions:**
1. At the end of your day, write down three things that went well
2. For each thing, write about why you think it happened
3. Be specific about your role in making these good things happen

**Examples:**
• "I helped a colleague solve a technical problem because I took time to listen"
• "I felt energized during my lunch break because I chose to go outside"
• "My supervisor praised my work because I double-checked my calculations"

**Why it works:**
• Shifts attention from negative to positive experiences
• Helps recognize your personal agency in positive outcomes
• Builds optimism and resilience over time

**For best results:** Practice this exercise weekly for at least one week. Research shows this timing is more effective than daily practice.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.PATTERN_TRIGGERED,
            content_level=WellnessContentLevel.INTERACTIVE,
            evidence_level=EvidenceLevel.PEER_REVIEWED_RESEARCH,
            tags=['positive_psychology', 'mood_enhancement', 'resilience', 'gratitude'],
            trigger_patterns={
                'mood_threshold': 6,
                'frequency': 'weekly',
                'optimal_times': ['evening', 'end_of_shift']
            },
            workplace_specific=True,
            field_worker_relevant=True,
            action_tips=[
                "Focus on things within your control",
                "Include both big and small positive moments",
                "Notice patterns in what makes you feel good",
                "Practice weekly, not daily, for best results"
            ],
            key_takeaways=[
                "You have more control over positive experiences than you think",
                "Regular reflection builds lasting happiness",
                "Small positive moments matter as much as big ones"
            ],
            source_name="University of Pennsylvania Positive Psychology Center",
            evidence_summary="Seligman et al. study showed 6-month increase in happiness and decrease in depression",
            citations=[
                "Seligman, M. E. P., Steen, T. A., Park, N., & Peterson, C. (2005). Positive psychology progress: Empirical validation of interventions."
            ],
            estimated_reading_time=5,
            complexity_score=2,
            created_by=system_user
        )

        intervention = MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.THREE_GOOD_THINGS,
            evidence_base=InterventionEvidenceBase.SELIGMAN_VALIDATED,
            expected_benefit_duration="6 months post-intervention (research validated)",
            effectiveness_percentage=85,
            optimal_frequency=InterventionDeliveryTiming.WEEKLY,
            intervention_duration_minutes=5,
            mood_trigger_threshold=6,
            crisis_escalation_level=0,
            workplace_context_tags=['end_of_shift', 'project_completion', 'team_success'],
            guided_questions=[
                "What is the first good thing that happened today?",
                "Why do you think this good thing happened?",
                "What role did you play in making this happen?",
                "What is the second good thing that happened today?",
                "Why do you think this good thing happened?",
                "What role did you play in making this happen?",
                "What is the third good thing that happened today?",
                "Why do you think this good thing happened?",
                "What role did you play in making this happen?"
            ],
            template_structure={
                'format': 'three_items',
                'fields': ['event_description', 'why_it_happened', 'my_role'],
                'reflection_prompt': 'What patterns do you notice in these positive experiences?'
            },
            follow_up_prompts=[
                "How might you create more experiences like these?",
                "What strengths did you use today that contributed to these positive moments?"
            ]
        )

        return 1

    def _create_gratitude_interventions(self, tenant, system_user, overwrite):
        """Create gratitude-based interventions"""
        created = 0

        # Daily Gratitude Practice
        title = "Daily Gratitude Practice"
        if not overwrite and self._intervention_exists(tenant, title):
            pass
        else:
            content = WellnessContent.objects.create(
                tenant=tenant,
                title=title,
                summary="A brief daily practice to cultivate appreciation and improve workplace wellbeing. Proven effective for stress reduction.",
                content="""
**Daily Gratitude Practice for Field Workers**

*Research Foundation:* Workplace gratitude interventions show significant improvements in well-being, mental health, and job performance.

**Quick Practice (2 minutes):**
1. Think of one person you're grateful for today
2. Think of one aspect of your work you appreciate
3. Think of one thing about yourself you're thankful for

**Work-Specific Gratitude:**
• Appreciation for safety equipment that protects you
• Gratitude for team members who support you
• Recognition of skills you've developed
• Thankfulness for job security and steady income

**Benefits for Workers:**
• Reduced job stress and burnout
• Improved relationships with colleagues
• Better sleep and physical health
• Increased job satisfaction

**When to Practice:**
• Start of shift (sets positive tone)
• During breaks (mental reset)
• End of difficult tasks (perspective shift)
                """,
                category=WellnessContentCategory.MENTAL_HEALTH,
                delivery_context=WellnessDeliveryContext.DAILY_TIP,
                content_level=WellnessContentLevel.QUICK_TIP,
                evidence_level=EvidenceLevel.PEER_REVIEWED_RESEARCH,
                tags=['gratitude', 'workplace_wellness', 'stress_reduction', 'job_satisfaction'],
                workplace_specific=True,
                field_worker_relevant=True,
                estimated_reading_time=2,
                created_by=system_user
            )

            MentalHealthIntervention.objects.create(
                tenant=tenant,
                wellness_content=content,
                intervention_type=MentalHealthInterventionType.GRATITUDE_JOURNAL,
                evidence_base=InterventionEvidenceBase.WORKPLACE_VALIDATED,
                expected_benefit_duration="Immediate mood improvement, cumulative long-term benefits",
                effectiveness_percentage=75,
                optimal_frequency=InterventionDeliveryTiming.WEEKLY,
                intervention_duration_minutes=2,
                stress_trigger_threshold=3,
                workplace_context_tags=['shift_start', 'break_time', 'stress_moment'],
                guided_questions=[
                    "Who is one person you're grateful for today?",
                    "What's one aspect of your work you appreciate?",
                    "What's one thing about yourself you're thankful for?"
                ]
            )
            created += 1

        return created

    def _create_strength_spotting(self, tenant, system_user, overwrite):
        """Create character strengths identification intervention"""
        title = "Character Strengths Identification"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Identify and utilize your core character strengths to improve work performance and personal satisfaction.",
            content="""
**Character Strengths for Field Workers**

*Research Foundation:* Using signature strengths leads to increased engagement, performance, and job satisfaction.

**Common Field Worker Strengths:**
• **Perseverance**: Completing difficult tasks despite obstacles
• **Teamwork**: Collaborating effectively with colleagues
• **Problem-solving**: Finding practical solutions quickly
• **Reliability**: Being dependable in challenging conditions
• **Courage**: Facing workplace hazards and challenges
• **Attention to detail**: Maintaining quality and safety standards

**Strength-Spotting Exercise:**
1. Reflect on a recent work success
2. What personal qualities helped you succeed?
3. How can you use these strengths more often?
4. How can you help colleagues recognize their strengths?

**Applying Strengths:**
• Use problem-solving skills for efficiency improvements
• Apply teamwork strength to mentor new employees
• Leverage attention to detail for safety protocols
• Channel perseverance during challenging projects
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.STREAK_MILESTONE,
            content_level=WellnessContentLevel.INTERACTIVE,
            evidence_level=EvidenceLevel.SELIGMAN_VALIDATED,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=7,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.STRENGTH_SPOTTING,
            evidence_base=InterventionEvidenceBase.SELIGMAN_VALIDATED,
            expected_benefit_duration="Long-term improvement in job satisfaction and performance",
            effectiveness_percentage=80,
            optimal_frequency=InterventionDeliveryTiming.MONTHLY,
            intervention_duration_minutes=7,
            guided_questions=[
                "What was a recent work success you're proud of?",
                "What personal qualities helped you achieve this success?",
                "How did you apply these strengths?",
                "When do you feel most energized at work?",
                "What strengths are you using in those moments?"
            ]
        )

        return 1

    def _create_behavioral_activation(self, tenant, system_user, overwrite):
        """Create CBT behavioral activation intervention"""
        title = "Behavioral Activation for Low Mood"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Evidence-based technique to improve mood through purposeful activity engagement. WHO-recommended for depression prevention.",
            content="""
**Behavioral Activation Technique**

*Research Foundation:* WHO-recommended behavioral intervention with proven effectiveness equivalent to cognitive therapy.

**The Core Principle:**
Mood follows action. When we engage in meaningful activities, our mood naturally improves.

**For Field Workers:**

**High-Impact Activities:**
• Learning a new skill related to your work
• Helping a colleague solve a problem
• Organizing your workspace for efficiency
• Taking a proper lunch break outside
• Connecting with family after work

**The Activity-Mood Connection:**
1. Notice when your mood is low
2. Choose one meaningful activity
3. Do it even if you don't feel like it
4. Notice how your mood changes afterward

**Work-Based Activation:**
• Tackle a task you've been avoiding
• Reach out to a supportive colleague
• Take pride in completing safety checks
• Engage in problem-solving discussions

**Remember:** You don't need to feel motivated to start. Action creates motivation, not the other way around.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.MOOD_SUPPORT,
            content_level=WellnessContentLevel.SHORT_READ,
            evidence_level=EvidenceLevel.WHO_RECOMMENDED,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=4,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
            evidence_base=InterventionEvidenceBase.CBT_EVIDENCE_BASE,
            expected_benefit_duration="Immediate mood improvement, builds long-term resilience",
            effectiveness_percentage=85,
            optimal_frequency=InterventionDeliveryTiming.TRIGGERED_BY_PATTERN,
            intervention_duration_minutes=4,
            mood_trigger_threshold=4,
            guided_questions=[
                "How is your mood right now (1-10)?",
                "What meaningful activity could you do in the next hour?",
                "What's stopping you from doing this activity?",
                "How might you feel after completing this activity?"
            ]
        )

        return 1

    def _create_thought_record(self, tenant, system_user, overwrite):
        """Create CBT thought record intervention"""
        title = "CBT Thought Record for Workplace Stress"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Cognitive Behavioral Therapy technique to identify and reframe negative thinking patterns that increase workplace stress.",
            content="""
**CBT Thought Record Technique**

*Research Foundation:* Core CBT tool with extensive evidence for reducing anxiety, depression, and workplace stress.

**When to Use:**
• Feeling overwhelmed by work demands
• After a difficult interaction with colleagues
• When catastrophic thinking starts
• Before or after stressful tasks

**The 5-Step Process:**

**1. Situation:** What happened? (Just the facts)
*Example: "Equipment broke down during morning shift"*

**2. Emotion:** How did you feel? (Rate intensity 1-10)
*Example: "Frustrated (8/10), worried about delays (7/10)"*

**3. Automatic Thought:** What went through your mind?
*Example: "This always happens to me, I'm unlucky"*

**4. Evidence:** Is this thought realistic?
*For: Equipment does break sometimes*
*Against: It doesn't always happen, other people have breakdowns too*

**5. Balanced Thought:** What's a more realistic perspective?
*Example: "Equipment breakdowns are normal, I handled it well and got it fixed quickly"*

**Result:** Check your emotion intensity now. Often it reduces significantly.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.STRESS_RESPONSE,
            content_level=WellnessContentLevel.INTERACTIVE,
            evidence_level=EvidenceLevel.CBT_EVIDENCE_BASE,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=6,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.THOUGHT_RECORD,
            evidence_base=InterventionEvidenceBase.CBT_EVIDENCE_BASE,
            expected_benefit_duration="Immediate stress reduction, builds cognitive flexibility",
            effectiveness_percentage=90,
            optimal_frequency=InterventionDeliveryTiming.TRIGGERED_BY_PATTERN,
            intervention_duration_minutes=6,
            stress_trigger_threshold=4,
            workplace_context_tags=['equipment_failure', 'deadline_pressure', 'interpersonal_conflict'],
            template_structure={
                'steps': ['situation', 'emotion', 'automatic_thought', 'evidence_for', 'evidence_against', 'balanced_thought'],
                'emotion_scale': '1-10',
                'follow_up': 'rate_emotion_after'
            }
        )

        return 1

    def _create_activity_scheduling(self, tenant, system_user, overwrite):
        """Create pleasant activity scheduling intervention"""
        title = "Pleasant Activity Scheduling"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Schedule enjoyable activities to boost mood and energy levels. Essential component of behavioral activation therapy.",
            content="""
**Pleasant Activity Scheduling**

*Research Foundation:* Key component of behavioral activation with proven mood-boosting effects.

**The Concept:**
Depression and low mood often reduce our engagement in enjoyable activities. Purposefully scheduling pleasant activities helps break this cycle.

**Work-Appropriate Pleasant Activities:**

**During Breaks:**
• Listen to favorite music or podcasts
• Call a friend or family member
• Take a walk outside the facility
• Practice deep breathing in fresh air
• Enjoy a favorite snack mindfully

**After Work:**
• Engage in a hobby you enjoy
• Spend quality time with pets or family
• Watch a comedy show or funny videos
• Take a relaxing bath or shower
• Read something interesting (not work-related)

**Weekend Activities:**
• Visit a place you enjoy in nature
• Try a new restaurant or recipe
• Engage in physical activity you like
• Connect with friends or family
• Pursue learning something new

**Scheduling Tips:**
• Plan activities in advance
• Start small - even 10 minutes counts
• Choose activities that energize you
• Don't wait until you "feel like it"
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.ENERGY_BOOST,
            content_level=WellnessContentLevel.SHORT_READ,
            evidence_level=EvidenceLevel.CBT_EVIDENCE_BASE,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=4,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.ACTIVITY_SCHEDULING,
            evidence_base=InterventionEvidenceBase.CBT_EVIDENCE_BASE,
            expected_benefit_duration="Immediate mood boost, builds healthy routine patterns",
            effectiveness_percentage=75,
            optimal_frequency=InterventionDeliveryTiming.WEEKLY,
            intervention_duration_minutes=4,
            energy_trigger_threshold=4,
            mood_trigger_threshold=5
        )

        return 1

    def _create_breathing_exercises(self, tenant, system_user, overwrite):
        """Create breathing exercise interventions"""
        title = "Box Breathing for Workplace Stress"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Simple 4-4-4-4 breathing technique used by emergency responders to quickly reduce stress and improve focus.",
            content="""
**Box Breathing Technique**

*Research Foundation:* Used by Navy SEALs and emergency responders. Scientifically proven to activate parasympathetic nervous system and reduce stress hormones.

**Perfect for Field Workers:**
• Can be done anywhere, even wearing safety equipment
• Takes only 2-3 minutes
• No special training required
• Immediate stress relief

**The Technique:**
1. **Breathe IN** for 4 counts
2. **HOLD** for 4 counts
3. **Breathe OUT** for 4 counts
4. **HOLD** (empty lungs) for 4 counts
5. Repeat 4-6 cycles

**When to Use:**
• Before starting a challenging task
• After a stressful incident
• During breaks to reset your nervous system
• When you notice tension building up
• Before important conversations

**Pro Tips for Workers:**
• Use your watch or count seconds: "1-one-thousand, 2-one-thousand..."
• If 4 counts feels too long, start with 3
• Can be done standing, sitting, or even walking slowly
• Focus only on the counting - let other thoughts pass by

**Why It Works:**
Controlled breathing sends a signal to your brain that you're safe, which reduces stress hormones and improves clear thinking.
            """,
            category=WellnessContentCategory.STRESS_MANAGEMENT,
            delivery_context=WellnessDeliveryContext.STRESS_RESPONSE,
            content_level=WellnessContentLevel.QUICK_TIP,
            evidence_level=EvidenceLevel.PEER_REVIEWED_RESEARCH,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=3,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.BREATHING_EXERCISE,
            evidence_base=InterventionEvidenceBase.META_ANALYSIS,
            expected_benefit_duration="Immediate stress relief (2-5 minutes), builds stress resilience",
            effectiveness_percentage=95,
            optimal_frequency=InterventionDeliveryTiming.IMMEDIATE,
            intervention_duration_minutes=3,
            stress_trigger_threshold=3,
            crisis_escalation_level=2,
            workplace_context_tags=['equipment_failure', 'safety_concern', 'deadline_pressure', 'before_difficult_task']
        )

        return 1

    def _create_progressive_relaxation(self, tenant, system_user, overwrite):
        """Create progressive muscle relaxation intervention"""
        title = "Quick Progressive Muscle Relaxation"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Evidence-based muscle relaxation technique for releasing physical tension and mental stress. Adapted for workplace use.",
            content="""
**Progressive Muscle Relaxation (PMR)**

*Research Foundation:* Developed by Dr. Edmund Jacobson, PMR has 80+ years of research showing effectiveness for stress, anxiety, and physical tension.

**Quick 5-Minute Version for Workers:**

**Setup:**
• Find a quiet space (break room, vehicle, outdoor area)
• Sit or stand comfortably
• Remove or loosen tight equipment if possible

**The Process:**
1. **Shoulders & Neck** (30 seconds)
   - Tense: Lift shoulders toward ears, hold tight
   - Release: Drop shoulders, notice the relaxation

2. **Arms & Hands** (30 seconds)
   - Tense: Make fists, tighten arms
   - Release: Open hands, let arms hang loose

3. **Face & Jaw** (30 seconds)
   - Tense: Scrunch face, clench jaw
   - Release: Let face relax completely

4. **Back & Core** (30 seconds)
   - Tense: Arch back slightly, tighten core
   - Release: Settle into relaxed posture

5. **Legs & Feet** (30 seconds)
   - Tense: Tighten leg muscles, point toes
   - Release: Let legs feel heavy and relaxed

**Final Step:** Take 3 deep breaths and notice how your body feels now versus when you started.

**When to Use:**
• End of physically demanding shifts
• Before sleep after stressful days
• During long breaks
• When you notice muscle tension
            """,
            category=WellnessContentCategory.STRESS_MANAGEMENT,
            delivery_context=WellnessDeliveryContext.SHIFT_TRANSITION,
            content_level=WellnessContentLevel.INTERACTIVE,
            evidence_level=EvidenceLevel.PEER_REVIEWED_RESEARCH,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=5,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.PROGRESSIVE_RELAXATION,
            evidence_base=InterventionEvidenceBase.RCT_VALIDATED,
            expected_benefit_duration="Immediate relaxation, improved sleep quality",
            effectiveness_percentage=85,
            optimal_frequency=InterventionDeliveryTiming.SAME_DAY,
            intervention_duration_minutes=5,
            stress_trigger_threshold=4,
            energy_trigger_threshold=3,
            workplace_context_tags=['end_of_shift', 'physical_demanding_work', 'high_stress_day']
        )

        return 1

    def _create_motivational_checkin(self, tenant, system_user, overwrite):
        """Create motivational interviewing check-in"""
        title = "Motivational Check-In: Your Why"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Brief motivational interviewing technique to reconnect with your personal values and motivation for work.",
            content="""
**Motivational Check-In: Connecting with Your Why**

*Research Foundation:* Motivational interviewing techniques increase intrinsic motivation and job satisfaction.

**The Power of 'Why':**
When work feels routine or stressful, reconnecting with your deeper motivations can restore energy and purpose.

**Quick Reflection Questions:**

**Personal Motivation:**
• Why did you choose this type of work originally?
• What aspects of your job align with your personal values?
• How does your work contribute to something bigger than yourself?

**Daily Impact:**
• Who benefits from the work you do?
• What would be missing if you didn't do your job well?
• When do you feel most proud of your work?

**Values Connection:**
• What values are you expressing through your work? (e.g., service, craftsmanship, teamwork, security)
• How does your paycheck support what matters most to you?
• What skills are you developing that serve your long-term goals?

**For Difficult Days:**
• Even when work is challenging, what keeps you going?
• What would you tell someone else about why this work matters?
• How has this job helped you grow as a person?

**Action Step:**
Choose one insight from this reflection and carry it with you today. Let it influence how you approach your work tasks.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.DAILY_TIP,
            content_level=WellnessContentLevel.SHORT_READ,
            evidence_level=EvidenceLevel.PROFESSIONAL_CONSENSUS,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=4,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.MOTIVATIONAL_CHECK_IN,
            evidence_base=InterventionEvidenceBase.WORKPLACE_VALIDATED,
            expected_benefit_duration="Immediate motivation boost, builds long-term job satisfaction",
            effectiveness_percentage=70,
            optimal_frequency=InterventionDeliveryTiming.WEEKLY,
            intervention_duration_minutes=4,
            energy_trigger_threshold=5,
            mood_trigger_threshold=5
        )

        return 1

    def _create_values_clarification(self, tenant, system_user, overwrite):
        """Create values clarification intervention"""
        title = "Personal Values Clarification"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Identify your core personal values and explore how they connect to your work life for increased meaning and motivation.",
            content="""
**Personal Values Clarification Exercise**

*Research Foundation:* Values-based interventions increase psychological well-being, job satisfaction, and resilience to stress.

**Common Core Values:**
Choose 3-5 that resonate most strongly with you:

**Security & Stability:** Financial security, job stability, predictable income
**Service & Contribution:** Helping others, making a difference, serving community
**Mastery & Growth:** Learning new skills, becoming expert, personal development
**Family & Relationships:** Providing for family, time with loved ones, being present
**Independence:** Self-reliance, autonomy, making own decisions
**Teamwork & Belonging:** Being part of a team, workplace friendships, collaboration
**Recognition & Achievement:** Being valued, accomplishing goals, professional respect
**Adventure & Variety:** New challenges, changing environments, avoiding routine

**Reflection Questions:**
1. Which values feel most important to you right now?
2. How does your current work support these values?
3. When do you feel most aligned with your values at work?
4. What would need to change for your work to better reflect your values?

**Values in Action:**
• If you value family: Remember that your work provides for them
• If you value service: Focus on how your work helps customers or colleagues
• If you value mastery: Look for opportunities to develop skills
• If you value security: Appreciate the stability your job provides

**Integration:**
Make one small change this week to better align your work with your top value.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.STREAK_MILESTONE,
            content_level=WellnessContentLevel.DEEP_DIVE,
            evidence_level=EvidenceLevel.PROFESSIONAL_CONSENSUS,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=7,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.VALUES_CLARIFICATION,
            evidence_base=InterventionEvidenceBase.WORKPLACE_VALIDATED,
            expected_benefit_duration="Builds long-term meaning and job satisfaction",
            effectiveness_percentage=75,
            optimal_frequency=InterventionDeliveryTiming.MONTHLY,
            intervention_duration_minutes=7
        )

        return 1

    def _create_crisis_resources(self, tenant, system_user, overwrite):
        """Create crisis support resources"""
        title = "Crisis Support Resources"

        if not overwrite and self._intervention_exists(tenant, title):
            return 0

        content = WellnessContent.objects.create(
            tenant=tenant,
            title=title,
            summary="Professional mental health resources and crisis support information for immediate assistance when needed.",
            content="""
**Crisis Support Resources**

**If you're experiencing thoughts of self-harm or suicide, please reach out immediately:**

**24/7 Crisis Lines:**
• **988 Suicide & Crisis Lifeline**: Call or text 988
• **Crisis Text Line**: Text HOME to 741741
• **National Suicide Prevention Lifeline**: 1-800-273-8255

**When to Seek Professional Help:**
• Persistent feelings of hopelessness lasting more than two weeks
• Thoughts of self-harm or suicide
• Inability to function at work or home
• Substance use to cope with stress
• Significant changes in sleep, appetite, or energy lasting weeks
• Feelings of being overwhelmed that don't improve with rest

**Employee Assistance Programs (EAP):**
Many employers offer free, confidential counseling services. Check with HR about:
• Free counseling sessions (often 3-8 sessions per year)
• 24/7 phone support
• Financial and legal consultation
• Work-life balance resources

**Finding Professional Help:**
• Psychology Today therapist finder: psychologytoday.com
• Your primary care doctor can provide referrals
• Community mental health centers offer sliding-scale fees
• Many therapists now offer telehealth options

**What to Expect:**
• Initial sessions focus on understanding your concerns
• Therapy is confidential (except in cases of imminent danger)
• Many people see improvement within 6-12 sessions
• Medication evaluation may be recommended for some conditions

**Remember:** Seeking help is a sign of strength, not weakness.
            """,
            category=WellnessContentCategory.MENTAL_HEALTH,
            delivery_context=WellnessDeliveryContext.PATTERN_TRIGGERED,
            content_level=WellnessContentLevel.SHORT_READ,
            evidence_level=EvidenceLevel.WHO_RECOMMENDED,
            workplace_specific=True,
            field_worker_relevant=True,
            estimated_reading_time=4,
            created_by=system_user
        )

        MentalHealthIntervention.objects.create(
            tenant=tenant,
            wellness_content=content,
            intervention_type=MentalHealthInterventionType.CRISIS_RESOURCE,
            evidence_base=InterventionEvidenceBase.WHO_RECOMMENDED,
            expected_benefit_duration="Immediate access to professional support",
            effectiveness_percentage=100,
            optimal_frequency=InterventionDeliveryTiming.IMMEDIATE,
            intervention_duration_minutes=4,
            mood_trigger_threshold=3,
            crisis_escalation_level=8,
            workplace_context_tags=['crisis_detected', 'severe_mood_decline', 'safety_concern']
        )

        return 1

    def _intervention_exists(self, tenant, title):
        """Check if intervention with this title already exists for tenant"""
        return WellnessContent.objects.filter(
            tenant=tenant,
            title=title
        ).exists()