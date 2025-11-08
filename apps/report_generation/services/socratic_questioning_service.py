"""
Socratic Questioning Service

Implements AI-guided questioning using multiple frameworks:
- 5 Whys: Root cause analysis through iterative questioning
- SBAR: Situation-Background-Assessment-Recommendation
- 5W1H: Who/What/When/Where/Why/How
- Ishikawa/Fishbone: Causal mapping
- STAR: Situation-Task-Action-Result

The AI asks progressively deeper questions to extract complete,
clear, and actionable information from report authors.
"""

import logging
from typing import Dict, List, Optional, Tuple
from apps.report_generation.models import GeneratedReport, ReportAIInteraction

logger = logging.getLogger(__name__)


class SocraticQuestioningService:
    """
    AI service for generating context-aware questions that guide
    users to create complete, clear, and well-reasoned reports.
    """
    
    # Question frameworks
    FIVE_WHYS_FRAMEWORK = '5_whys'
    SBAR_FRAMEWORK = 'sbar'
    FIVE_W1H_FRAMEWORK = '5w1h'
    ISHIKAWA_FRAMEWORK = 'ishikawa'
    STAR_FRAMEWORK = 'star'
    
    # Ishikawa fishbone categories (6M)
    ISHIKAWA_CATEGORIES = [
        'people',
        'process',
        'equipment',
        'environment',
        'materials',
        'management'
    ]
    
    @classmethod
    def generate_next_question(
        cls,
        report: GeneratedReport,
        context: Dict,
        framework: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate the next AI question based on report state and framework.
        
        Args:
            report: GeneratedReport instance
            context: Current report data and user responses
            framework: Specific framework to use (auto-detect if None)
        
        Returns:
            Tuple of (question_text, question_type)
        """
        if framework is None:
            framework = cls._determine_framework(report)
        
        if framework == cls.FIVE_WHYS_FRAMEWORK:
            return cls._generate_five_whys_question(report, context)
        elif framework == cls.SBAR_FRAMEWORK:
            return cls._generate_sbar_question(report, context)
        elif framework == cls.FIVE_W1H_FRAMEWORK:
            return cls._generate_5w1h_question(report, context)
        elif framework == cls.ISHIKAWA_FRAMEWORK:
            return cls._generate_ishikawa_question(report, context)
        elif framework == cls.STAR_FRAMEWORK:
            return cls._generate_star_question(report, context)
        else:
            return cls._generate_clarification_question(report, context)
    
    @classmethod
    def _determine_framework(cls, report: GeneratedReport) -> str:
        """Auto-detect appropriate framework based on template category."""
        template_category = report.template.category
        strategy = report.template.questioning_strategy
        
        if strategy and 'primary_framework' in strategy:
            return strategy['primary_framework']
        
        # Default framework by category
        framework_mapping = {
            'incident': cls.FIVE_WHYS_FRAMEWORK,
            'rca': cls.FIVE_WHYS_FRAMEWORK,
            'capa': cls.ISHIKAWA_FRAMEWORK,
            'near_miss': cls.FIVE_W1H_FRAMEWORK,
            'shift_handover': cls.SBAR_FRAMEWORK,
            'safety': cls.SBAR_FRAMEWORK,
        }
        
        return framework_mapping.get(template_category, cls.FIVE_W1H_FRAMEWORK)
    
    @classmethod
    def _generate_five_whys_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """
        Generate 5 Whys questions for root cause analysis.
        Progressively asks "why" up to 5 levels deep.
        """
        previous_whys = cls._get_previous_interactions(report, cls.FIVE_WHYS_FRAMEWORK)
        depth = len(previous_whys)
        
        if depth >= 5:
            return (
                "We've identified a potential root cause. Can you suggest specific actions "
                "to prevent this from happening again?",
                'validation'
            )
        
        if depth == 0:
            problem = context.get('problem_statement', 'the incident')
            return (
                f"You mentioned {problem}. Why did this happen? "
                "What was the immediate cause?",
                cls.FIVE_WHYS_FRAMEWORK
            )
        
        last_answer = previous_whys[-1].answer if previous_whys else ""
        
        questions = [
            f"Why did {last_answer}? What caused this condition?",
            f"Why did {last_answer}? What was the underlying reason?",
            f"Why did {last_answer}? What process or system allowed this?",
            f"Why did {last_answer}? What root cause enabled this situation?",
            f"Why did {last_answer}? What fundamental issue needs addressing?"
        ]
        
        return (questions[depth], cls.FIVE_WHYS_FRAMEWORK)
    
    @classmethod
    def _generate_sbar_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """
        Generate SBAR framework questions:
        Situation, Background, Assessment, Recommendation
        """
        previous_sbar = cls._get_previous_interactions(report, cls.SBAR_FRAMEWORK)
        stage = len(previous_sbar)
        
        sbar_questions = [
            # Situation
            (
                "Describe the SITUATION: What exactly happened? "
                "Be specific about the event, time, location, and people involved.",
                cls.SBAR_FRAMEWORK
            ),
            # Background
            (
                "Provide the BACKGROUND: What were the conditions leading up to this? "
                "What was supposed to happen? What was the normal process?",
                cls.SBAR_FRAMEWORK
            ),
            # Assessment
            (
                "Give your ASSESSMENT: What do you think caused this? "
                "What are the risks if this happens again? What's the severity?",
                cls.SBAR_FRAMEWORK
            ),
            # Recommendation
            (
                "What are your RECOMMENDATIONS: What specific actions should be taken? "
                "Who should do what, and by when? How will we verify it's fixed?",
                cls.SBAR_FRAMEWORK
            ),
        ]
        
        if stage < len(sbar_questions):
            return sbar_questions[stage]
        
        return (
            "Is there anything else important to document about this incident?",
            'clarification'
        )
    
    @classmethod
    def _generate_5w1h_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """
        Generate 5W1H questions: Who, What, When, Where, Why, How
        Ensures all critical details are captured.
        """
        previous_5w1h = cls._get_previous_interactions(report, cls.FIVE_W1H_FRAMEWORK)
        stage = len(previous_5w1h)
        
        w1h_questions = [
            # What
            (
                "WHAT happened? Describe the specific event or issue in detail.",
                cls.FIVE_W1H_FRAMEWORK
            ),
            # When
            (
                "WHEN did this occur? Provide the exact date, time, and duration.",
                cls.FIVE_W1H_FRAMEWORK
            ),
            # Where
            (
                "WHERE did this happen? Be specific about location, equipment, or system.",
                cls.FIVE_W1H_FRAMEWORK
            ),
            # Who
            (
                "WHO was involved? List all people present, affected, or responsible.",
                cls.FIVE_W1H_FRAMEWORK
            ),
            # Why
            (
                "WHY did this happen? What were the contributing factors or root causes?",
                cls.FIVE_W1H_FRAMEWORK
            ),
            # How
            (
                "HOW did it happen? Describe the sequence of events step by step.",
                cls.FIVE_W1H_FRAMEWORK
            ),
        ]
        
        if stage < len(w1h_questions):
            return w1h_questions[stage]
        
        return (
            "Based on this information, what preventive measures do you recommend?",
            'validation'
        )
    
    @classmethod
    def _generate_ishikawa_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """
        Generate Ishikawa/Fishbone questions covering 6M categories:
        People, Process, Equipment, Environment, Materials, Management
        """
        previous_ishikawa = cls._get_previous_interactions(report, cls.ISHIKAWA_FRAMEWORK)
        stage = len(previous_ishikawa)
        
        if stage >= len(cls.ISHIKAWA_CATEGORIES):
            return (
                "Based on the factors identified, what is the primary root cause? "
                "What corrective action will address this root cause?",
                'validation'
            )
        
        category = cls.ISHIKAWA_CATEGORIES[stage]
        
        category_questions = {
            'people': (
                "PEOPLE factors: Were there any issues related to training, skills, "
                "staffing levels, communication, or human error?"
            ),
            'process': (
                "PROCESS factors: Were there any issues with procedures, workflows, "
                "documentation, or how the work was supposed to be done?"
            ),
            'equipment': (
                "EQUIPMENT factors: Were there any issues with tools, machinery, "
                "technology, maintenance, or equipment reliability?"
            ),
            'environment': (
                "ENVIRONMENT factors: Were there any issues with workspace conditions, "
                "weather, noise, lighting, temperature, or safety hazards?"
            ),
            'materials': (
                "MATERIALS factors: Were there any issues with supplies, parts quality, "
                "inventory, or material specifications?"
            ),
            'management': (
                "MANAGEMENT factors: Were there any issues with planning, oversight, "
                "resource allocation, policies, or management decisions?"
            ),
        }
        
        return (category_questions[category], cls.ISHIKAWA_FRAMEWORK)
    
    @classmethod
    def _generate_star_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """
        Generate STAR questions: Situation, Task, Action, Result
        Good for performance and behavioral incident reporting.
        """
        previous_star = cls._get_previous_interactions(report, cls.STAR_FRAMEWORK)
        stage = len(previous_star)
        
        star_questions = [
            # Situation
            (
                "SITUATION: Describe the context. What was happening? "
                "What circumstances led to this event?",
                cls.STAR_FRAMEWORK
            ),
            # Task
            (
                "TASK: What was supposed to be accomplished? "
                "What were the objectives or expected outcomes?",
                cls.STAR_FRAMEWORK
            ),
            # Action
            (
                "ACTION: What specific actions were taken? "
                "Describe step-by-step what happened.",
                cls.STAR_FRAMEWORK
            ),
            # Result
            (
                "RESULT: What was the outcome? What were the consequences "
                "(positive or negative)? What was learned?",
                cls.STAR_FRAMEWORK
            ),
        ]
        
        if stage < len(star_questions):
            return star_questions[stage]
        
        return (
            "What would you do differently next time to improve the outcome?",
            'validation'
        )
    
    @classmethod
    def _generate_clarification_question(
        cls,
        report: GeneratedReport,
        context: Dict
    ) -> Tuple[str, str]:
        """Generate clarification questions for incomplete or vague responses."""
        incomplete_fields = cls._identify_incomplete_fields(report)
        
        if incomplete_fields:
            field = incomplete_fields[0]
            return (
                f"Can you provide more detail about '{field}'? "
                "This information is important for a complete report.",
                'clarification'
            )
        
        vague_responses = cls._detect_vague_responses(context)
        if vague_responses:
            vague_text = vague_responses[0]
            return (
                f"You mentioned '{vague_text}'. Can you be more specific? "
                "For example, provide exact numbers, times, or names instead of general terms.",
                'clarification'
            )
        
        return (
            "Is there any additional information that would help someone "
            "understand this incident who wasn't there?",
            'clarification'
        )
    
    @classmethod
    def detect_incomplete_reasoning(cls, narrative: str) -> List[str]:
        """
        Detect gaps in logical reasoning or missing causal links.
        
        Returns:
            List of identified issues
        """
        issues = []
        
        # Check for unexplained jumps
        if 'therefore' in narrative.lower() or 'thus' in narrative.lower():
            if 'because' not in narrative.lower() and 'since' not in narrative.lower():
                issues.append("Conclusion stated without clear reasoning")
        
        # Check for vague causation
        vague_causal_words = ['issue', 'problem', 'situation', 'thing', 'stuff']
        for word in vague_causal_words:
            if word in narrative.lower():
                issues.append(f"Vague term '{word}' used - be more specific")
        
        # Check for missing who/when/where
        if len(narrative) > 100:
            has_time = any(word in narrative.lower() for word in ['at', 'on', 'during', 'time'])
            has_location = any(word in narrative.lower() for word in ['in', 'at', 'location', 'area'])
            has_person = any(word in narrative.lower() for word in ['who', 'operator', 'technician', 'worker'])
            
            if not has_time:
                issues.append("Missing time information")
            if not has_location:
                issues.append("Missing location information")
            if not has_person:
                issues.append("Missing responsible person/role")
        
        return issues
    
    @classmethod
    def suggest_clarifying_questions(cls, vague_statement: str) -> List[str]:
        """Generate questions to clarify vague or incomplete statements."""
        questions = []
        
        # Check for vague quantities
        if any(word in vague_statement.lower() for word in ['many', 'few', 'several', 'some']):
            questions.append("How many exactly? Provide a specific number or range.")
        
        # Check for vague time
        if any(word in vague_statement.lower() for word in ['soon', 'later', 'recently', 'eventually']):
            questions.append("When exactly? Provide a specific date and time.")
        
        # Check for vague locations
        if any(word in vague_statement.lower() for word in ['somewhere', 'area', 'place']):
            questions.append("Where exactly? Provide a specific location or equipment ID.")
        
        # Check for vague actions
        if any(word in vague_statement.lower() for word in ['fixed', 'handled', 'dealt with']):
            questions.append("How exactly was it fixed? Describe the specific steps taken.")
        
        # Check for assumptions
        if any(word in vague_statement.lower() for word in ['probably', 'maybe', 'might', 'could be']):
            questions.append("Do you know for certain? If not, how can we verify?")
        
        return questions
    
    @classmethod
    def _get_previous_interactions(
        cls,
        report: GeneratedReport,
        question_type: str
    ) -> List[ReportAIInteraction]:
        """Get all previous interactions of a specific type."""
        return list(report.ai_interactions_detailed.filter(
            question_type=question_type
        ).order_by('iteration'))
    
    @classmethod
    def _identify_incomplete_fields(cls, report: GeneratedReport) -> List[str]:
        """Identify required fields that are incomplete or missing."""
        template_schema = report.template.schema
        report_data = report.report_data
        incomplete = []
        
        for field_name, field_spec in template_schema.get('fields', {}).items():
            if field_spec.get('required', False):
                value = report_data.get(field_name)
                if not value or (isinstance(value, str) and len(value.strip()) < 10):
                    incomplete.append(field_name)
        
        return incomplete
    
    @classmethod
    def _detect_vague_responses(cls, context: Dict) -> List[str]:
        """Detect vague language in responses."""
        vague_indicators = [
            'thing', 'stuff', 'issue', 'problem', 'situation',
            'many', 'few', 'several', 'some',
            'soon', 'later', 'recently',
            'probably', 'maybe', 'might'
        ]
        
        vague_found = []
        for key, value in context.items():
            if isinstance(value, str):
                for indicator in vague_indicators:
                    if indicator in value.lower():
                        vague_found.append(f"{key}: '{value[:50]}'")
                        break
        
        return vague_found
