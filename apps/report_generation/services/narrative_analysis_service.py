"""
Narrative Analysis Service

Analyzes text quality using NLP techniques:
- Readability scoring (Flesch-Kincaid)
- Vague language detection
- Specific language suggestions
- Measurable outcome validation

SELF-IMPROVING: Learns from supervisor-approved exemplars to refine
what constitutes "good" writing in your specific context.
"""

import re
import logging
from typing import Dict, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class NarrativeAnalysisService:
    """
    Analyzes narrative quality and provides specific improvement suggestions.
    Self-improving through exemplar analysis.
    """
    
    # Vague language dictionary (updated from exemplar learning)
    VAGUE_LANGUAGE_PATTERNS = {
        'quantities': ['many', 'few', 'several', 'some', 'a lot', 'multiple'],
        'time': ['soon', 'later', 'recently', 'eventually', 'sometime'],
        'generic': ['thing', 'stuff', 'issue', 'problem', 'situation', 'matter'],
        'locations': ['somewhere', 'area', 'place', 'vicinity', 'around'],
        'assumptions': ['probably', 'maybe', 'might', 'could be', 'possibly', 'perhaps', 'likely'],
        'actions': ['fixed', 'handled', 'dealt with', 'took care of', 'addressed'],
    }
    
    # Specific language suggestions (learned from exemplars)
    SPECIFIC_LANGUAGE_MAP = {
        'many': 'exactly X (provide number)',
        'few': 'X units (be specific)',
        'soon': 'by [specific date/time]',
        'later': 'at [specific time]',
        'recently': 'on [specific date]',
        'thing': '[specific object/component name]',
        'stuff': '[specific materials/items]',
        'issue': '[specific problem/malfunction]',
        'problem': '[specific failure/defect]',
        'fixed': '[specific repair actions taken]',
        'handled': '[specific steps performed]',
        'probably': 'confirmed/verified OR needs investigation',
        'maybe': 'requires verification',
        'area': '[specific location/equipment ID]',
        'somewhere': '[exact location]',
    }
    
    @classmethod
    def calculate_readability_score(cls, text: str) -> float:
        """
        Calculate Flesch-Kincaid readability score.
        Score 0-100, higher is easier to read.
        60-70 = Standard, 70-80 = Fairly Easy, 80-90 = Easy
        """
        if not text or len(text.strip()) < 50:
            return 0.0
        
        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        if sentence_count == 0:
            return 0.0
        
        # Count words
        words = text.split()
        word_count = len(words)
        
        if word_count == 0:
            return 0.0
        
        # Count syllables (approximate)
        syllable_count = sum(cls._count_syllables(word) for word in words)
        
        # Flesch Reading Ease formula
        if sentence_count > 0 and word_count > 0:
            score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
            return max(0.0, min(100.0, score))
        
        return 0.0
    
    @classmethod
    def detect_vague_language(cls, text: str) -> List[str]:
        """
        Detect vague, non-specific language.
        
        SELF-IMPROVING: Pattern list updated from exemplar analysis.
        """
        vague_found = []
        text_lower = text.lower()
        
        for category, patterns in cls.VAGUE_LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                # Use word boundaries to avoid false positives
                if re.search(rf'\b{re.escape(pattern)}\b', text_lower):
                    vague_found.append(pattern)
        
        return list(set(vague_found))
    
    @classmethod
    def suggest_specific_language(cls, vague_phrase: str) -> str:
        """
        Suggest specific replacement for vague language.
        
        SELF-IMPROVING: Suggestions refined from exemplar patterns.
        """
        vague_lower = vague_phrase.lower().strip()
        
        # Direct mapping
        if vague_lower in cls.SPECIFIC_LANGUAGE_MAP:
            return cls.SPECIFIC_LANGUAGE_MAP[vague_lower]
        
        # Pattern-based suggestions
        if any(word in vague_lower for word in ['many', 'few', 'several', 'some']):
            return 'Provide exact number or range (e.g., "approximately 15", "between 10-20")'
        
        if any(word in vague_lower for word in ['soon', 'later', 'recently']):
            return 'Provide specific date and time (e.g., "by 2:00 PM on Nov 8, 2025")'
        
        if any(word in vague_lower for word in ['thing', 'stuff', 'issue', 'problem']):
            return 'Name the specific component, part, or system (e.g., "bearing", "pump motor")'
        
        if any(word in vague_lower for word in ['probably', 'maybe', 'might']):
            return 'State facts: "confirmed by inspection" or "requires verification"'
        
        return 'Be more specific with exact names, numbers, times, or locations'
    
    @classmethod
    def identify_missing_details(cls, narrative: str, template_schema: Dict) -> List[Dict]:
        """
        Identify critical details that should be present but are missing.
        
        Returns:
            List of missing detail suggestions
        """
        missing = []
        narrative_lower = narrative.lower()
        
        # Check for temporal details
        has_time = bool(re.search(r'\d{1,2}:\d{2}|am|pm|hour|minute', narrative_lower))
        has_date = bool(re.search(r'\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2}|january|february|march|april|may|june|july|august|september|october|november|december', narrative_lower))
        
        if not has_time and len(narrative) > 100:
            missing.append({
                'type': 'time',
                'description': 'No specific time mentioned',
                'suggestion': 'Add exact time of occurrence (e.g., "at 2:30 PM")'
            })
        
        if not has_date and len(narrative) > 100:
            missing.append({
                'type': 'date',
                'description': 'No specific date mentioned',
                'suggestion': 'Add exact date (e.g., "on November 7, 2025")'
            })
        
        # Check for location details
        has_location = bool(re.search(r'location|building|room|area|floor|section|zone|equipment id|asset', narrative_lower))
        if not has_location and len(narrative) > 100:
            missing.append({
                'type': 'location',
                'description': 'No specific location mentioned',
                'suggestion': 'Add exact location or equipment ID'
            })
        
        # Check for people/roles
        has_person = bool(re.search(r'operator|technician|supervisor|manager|worker|employee|staff|name|who', narrative_lower))
        if not has_person and len(narrative) > 100:
            missing.append({
                'type': 'person',
                'description': 'No people or roles mentioned',
                'suggestion': 'Identify who was involved or responsible'
            })
        
        # Check for measurements/quantities
        has_measurement = bool(re.search(r'\d+\s*(unit|kg|meter|litre|psi|rpm|volt|amp|degree|percent|%)', narrative_lower))
        if not has_measurement and 'measurement' in str(template_schema).lower():
            missing.append({
                'type': 'measurement',
                'description': 'No measurements or quantities provided',
                'suggestion': 'Include relevant measurements with units'
            })
        
        return missing
    
    @classmethod
    def validate_measurable_outcomes(cls, recommendations: str) -> Tuple[bool, List[str]]:
        """
        Validate that recommendations include measurable outcomes.
        
        Returns:
            Tuple of (has_measurable_outcomes: bool, suggestions: List[str])
        """
        if not recommendations or len(recommendations.strip()) < 20:
            return False, ['Provide detailed recommendations']
        
        suggestions = []
        
        # Check for numbers/metrics
        has_numbers = bool(re.search(r'\d+', recommendations))
        if not has_numbers:
            suggestions.append('Add measurable targets (numbers, percentages, counts)')
        
        # Check for deadlines
        has_deadline = bool(re.search(r'by|within|before|deadline|date|\d{1,2}/\d{1,2}', recommendations, re.IGNORECASE))
        if not has_deadline:
            suggestions.append('Add specific deadlines or timeframes')
        
        # Check for assigned responsibility
        has_responsibility = bool(re.search(r'by|assigned to|responsible|owner', recommendations, re.IGNORECASE))
        if not has_responsibility:
            suggestions.append('Assign responsibility to specific person or role')
        
        # Check for action verbs
        action_verbs = ['implement', 'create', 'install', 'update', 'train', 'inspect', 'repair', 'replace', 'test', 'verify']
        has_action = any(verb in recommendations.lower() for verb in action_verbs)
        if not has_action:
            suggestions.append('Use specific action verbs (implement, install, inspect, etc.)')
        
        # Check for verification method
        has_verification = bool(re.search(r'verify|check|confirm|test|validate|measure', recommendations, re.IGNORECASE))
        if not has_verification:
            suggestions.append('Include how success will be verified or measured')
        
        has_measurable = len(suggestions) <= 2
        return has_measurable, suggestions
    
    @classmethod
    def learn_from_exemplar(cls, exemplar_text: str, category: str) -> Dict:
        """
        SELF-IMPROVEMENT: Analyze exemplar to extract good patterns.
        
        Returns:
            Dict of learned patterns that can update service behavior
        """
        learned = {
            'category': category,
            'word_count': len(exemplar_text.split()),
            'sentence_count': len(re.split(r'[.!?]+', exemplar_text)),
            'readability_score': cls.calculate_readability_score(exemplar_text),
            'good_phrases': cls._extract_good_phrases(exemplar_text),
            'specific_language_examples': cls._extract_specific_examples(exemplar_text),
            'structure_patterns': cls._extract_structure_patterns(exemplar_text),
        }
        
        return learned
    
    @classmethod
    def _extract_good_phrases(cls, text: str) -> List[str]:
        """Extract well-written phrases from exemplar."""
        good_phrases = []
        
        # Look for specific, measurable statements
        # Pattern: number + unit/measurement
        measurements = re.findall(r'\d+\s*(?:kg|meter|m|litre|l|psi|rpm|volt|v|amp|a|degree|°|percent|%|hour|hr|minute|min|second|sec)', text, re.IGNORECASE)
        good_phrases.extend(measurements[:5])
        
        # Pattern: specific time references
        times = re.findall(r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?', text)
        good_phrases.extend(times[:3])
        
        # Pattern: specific dates
        dates = re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', text, re.IGNORECASE)
        good_phrases.extend(dates[:3])
        
        return good_phrases
    
    @classmethod
    def _extract_specific_examples(cls, text: str) -> Dict[str, List[str]]:
        """Extract examples of specific language to learn from."""
        examples = {
            'equipment_ids': [],
            'proper_nouns': [],
            'technical_terms': [],
        }
        
        # Equipment IDs (patterns like P-4021, PUMP-123, etc.)
        equipment_ids = re.findall(r'\b[A-Z]+-?\d+\b', text)
        examples['equipment_ids'] = list(set(equipment_ids))[:5]
        
        # Proper nouns (capitalized words that aren't sentence starts)
        sentences = text.split('.')
        for sentence in sentences[1:]:  # Skip first sentence
            words = sentence.strip().split()
            if len(words) > 0:
                capitalized = [w for w in words[1:] if w and w[0].isupper()]
                examples['proper_nouns'].extend(capitalized)
        examples['proper_nouns'] = list(set(examples['proper_nouns']))[:10]
        
        # Technical terms (words with specific patterns)
        technical = re.findall(r'\b(?:[A-Z][a-z]+){2,}\b', text)  # CamelCase words
        examples['technical_terms'] = list(set(technical))[:5]
        
        return examples
    
    @classmethod
    def _extract_structure_patterns(cls, text: str) -> Dict:
        """Extract structural patterns from exemplar."""
        patterns = {
            'uses_bullets': bool(re.search(r'\n\s*[-*•]', text)),
            'uses_numbering': bool(re.search(r'\n\s*\d+\.', text)),
            'has_sections': bool(re.search(r'\n\s*[A-Z][^.!?]*:\s*\n', text)),
            'average_sentence_length': 0,
            'paragraph_count': len(text.split('\n\n')),
        }
        
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if sentences:
            avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
            patterns['average_sentence_length'] = round(avg_length, 1)
        
        return patterns
    
    @classmethod
    def compare_against_exemplars(cls, narrative: str, exemplar_stats: List[Dict]) -> Dict:
        """
        SELF-IMPROVEMENT: Compare narrative against learned exemplar patterns.
        
        Returns:
            Comparison results with improvement suggestions
        """
        if not exemplar_stats:
            return {'comparison': 'No exemplars available yet'}
        
        current_stats = {
            'word_count': len(narrative.split()),
            'readability': cls.calculate_readability_score(narrative),
            'vague_count': len(cls.detect_vague_language(narrative)),
        }
        
        # Average exemplar stats
        avg_exemplar = {
            'word_count': sum(e['word_count'] for e in exemplar_stats) / len(exemplar_stats),
            'readability': sum(e['readability_score'] for e in exemplar_stats) / len(exemplar_stats),
        }
        
        comparison = {
            'word_count_vs_exemplar': current_stats['word_count'] / avg_exemplar['word_count'] if avg_exemplar['word_count'] > 0 else 0,
            'readability_vs_exemplar': current_stats['readability'] / avg_exemplar['readability'] if avg_exemplar['readability'] > 0 else 0,
            'vague_language_count': current_stats['vague_count'],
            'suggestions': [],
        }
        
        # Generate improvement suggestions
        if comparison['word_count_vs_exemplar'] < 0.7:
            comparison['suggestions'].append(
                f"Add more detail. Exemplar reports average {int(avg_exemplar['word_count'])} words, "
                f"yours has {current_stats['word_count']}"
            )
        
        if comparison['readability_vs_exemplar'] < 0.8:
            comparison['suggestions'].append(
                f"Improve clarity. Exemplar reports score {avg_exemplar['readability']:.1f} in readability, "
                f"yours scores {current_stats['readability']:.1f}"
            )
        
        if current_stats['vague_count'] > 5:
            comparison['suggestions'].append(
                f"Reduce vague language. Found {current_stats['vague_count']} vague terms. "
                "Use specific numbers, names, and times."
            )
        
        return comparison
    
    # Private helper methods
    
    @classmethod
    def _count_syllables(cls, word: str) -> int:
        """Approximate syllable count for a word."""
        word = word.lower().strip()
        if len(word) <= 3:
            return 1
        
        # Remove final 'e'
        if word.endswith('e'):
            word = word[:-1]
        
        # Count vowel groups
        vowels = 'aeiouy'
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        return max(1, syllable_count)
    
    @classmethod
    def update_vague_patterns_from_feedback(cls, feedback_data: List[Dict]) -> None:
        """
        SELF-IMPROVEMENT: Update vague language patterns based on supervisor feedback.
        
        Args:
            feedback_data: List of dicts with 'flagged_phrase' and 'category'
        """
        for feedback in feedback_data:
            phrase = feedback.get('flagged_phrase', '').lower().strip()
            category = feedback.get('category', 'generic')
            
            if phrase and category in cls.VAGUE_LANGUAGE_PATTERNS:
                if phrase not in cls.VAGUE_LANGUAGE_PATTERNS[category]:
                    cls.VAGUE_LANGUAGE_PATTERNS[category].append(phrase)
                    logger.info(f"Learned new vague pattern: '{phrase}' in category '{category}'")
    
    @classmethod
    def update_specific_suggestions_from_exemplars(cls, exemplar_analysis: Dict) -> None:
        """
        SELF-IMPROVEMENT: Update specific language suggestions from exemplars.
        
        Args:
            exemplar_analysis: Dict with good phrase examples
        """
        good_phrases = exemplar_analysis.get('good_phrases', [])
        specific_examples = exemplar_analysis.get('specific_language_examples', {})
        
        # Learn better suggestions from exemplars
        if specific_examples.get('equipment_ids'):
            cls.SPECIFIC_LANGUAGE_MAP['thing'] = f"[equipment ID like {specific_examples['equipment_ids'][0]}]"
        
        logger.info(f"Updated specific language suggestions from {len(good_phrases)} exemplar phrases")
