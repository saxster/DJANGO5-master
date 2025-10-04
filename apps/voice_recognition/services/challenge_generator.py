"""
Challenge-Response Generator for Voice Biometric Authentication

Generates unpredictable challenge phrases to prevent:
- Replay attacks (pre-recorded audio)
- Deepfake/AI voice cloning attacks
- Impersonation attacks

Challenge types:
- Temporal (time-based, cannot be pre-recorded)
- Personal (user-specific information)
- Visual correlation (on-screen display)
- Behavioral liveness (specific speaking patterns)
- Multilingual (language mixing)

Following .claude/rules.md:
- Rule #7: Service methods <150 lines
- Rule #9: Specific exception handling
"""

import random
import string
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ChallengeResponseGenerator:
    """
    Generate anti-spoofing challenge phrases for voice enrollment and verification.

    Challenges are designed to be:
    - Unpredictable (cannot be guessed in advance)
    - Time-bound (must be answered immediately)
    - User-specific (only legitimate user knows the answer)
    - Linguistically diverse (for multilingual environments)
    """

    # Challenge categories with difficulty levels
    CHALLENGE_TYPES = [
        'temporal',
        'personal',
        'visual_correlation',
        'liveness',
        'multilingual',
        'mathematical',
    ]

    def __init__(self, user=None, language_code='en-US'):
        """
        Initialize challenge generator.

        Args:
            user: User object for personalized challenges
            language_code: Primary language for challenges
        """
        self.user = user
        self.language_code = language_code
        self.language_short = language_code.split('-')[0].lower()

    def generate_enrollment_challenges(self, num_challenges=5) -> List[Dict[str, Any]]:
        """
        Generate multiple challenges for voice enrollment.

        Enrollment requires more rigorous challenges than verification.

        Args:
            num_challenges: Number of challenges to generate (default: 5)

        Returns:
            List of challenge dictionaries with phrase, type, and expected response
        """
        challenges = []

        # Ensure diversity of challenge types
        challenge_types = self._select_diverse_challenge_types(num_challenges)

        for challenge_type in challenge_types:
            try:
                challenge = self._generate_challenge_by_type(
                    challenge_type,
                    enrollment_mode=True
                )
                challenges.append(challenge)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Error generating {challenge_type} challenge: {e}")
                # Fall back to temporal challenge
                challenges.append(self._generate_temporal_challenge())

        return challenges

    def generate_verification_challenge(self) -> Dict[str, Any]:
        """
        Generate a single challenge for voice verification.

        Verification challenges are simpler than enrollment but still prevent replay.

        Returns:
            Challenge dictionary with phrase and expected response
        """
        # For verification, prefer simpler challenges
        challenge_types = ['temporal', 'visual_correlation', 'mathematical']
        challenge_type = random.choice(challenge_types)

        return self._generate_challenge_by_type(challenge_type, enrollment_mode=False)

    def _select_diverse_challenge_types(self, num_challenges: int) -> List[str]:
        """Select diverse challenge types ensuring variety."""
        selected = []

        # Ensure at least one of each critical type
        critical_types = ['temporal', 'visual_correlation', 'liveness']
        selected.extend(critical_types[:min(num_challenges, len(critical_types))])

        # Fill remaining with random types
        remaining = num_challenges - len(selected)
        if remaining > 0:
            available = [t for t in self.CHALLENGE_TYPES if t not in selected]
            selected.extend(random.choices(available, k=remaining))

        random.shuffle(selected)
        return selected[:num_challenges]

    def _generate_challenge_by_type(
        self,
        challenge_type: str,
        enrollment_mode: bool = False
    ) -> Dict[str, Any]:
        """Generate challenge based on type."""
        generators = {
            'temporal': self._generate_temporal_challenge,
            'personal': self._generate_personal_challenge,
            'visual_correlation': self._generate_visual_challenge,
            'liveness': self._generate_liveness_challenge,
            'multilingual': self._generate_multilingual_challenge,
            'mathematical': self._generate_mathematical_challenge,
        }

        generator = generators.get(challenge_type, self._generate_temporal_challenge)
        return generator()

    def _generate_temporal_challenge(self) -> Dict[str, Any]:
        """
        Generate time-based challenge (cannot be pre-recorded).

        Examples:
        - "Say the current time: 14:35:42"
        - "Read today's date backwards: 2025-09-29"
        """
        now = timezone.now()

        challenges = [
            {
                'phrase': f"Say the current time: {now.strftime('%H:%M:%S')}",
                'expected_keywords': [now.strftime('%H'), now.strftime('%M')],
                'type': 'temporal',
                'difficulty': 'easy',
            },
            {
                'phrase': f"Read today's date: {now.strftime('%Y-%m-%d')}",
                'expected_keywords': [str(now.year), str(now.month), str(now.day)],
                'type': 'temporal',
                'difficulty': 'easy',
            },
            {
                'phrase': f"Say: Today is {now.strftime('%A, %B %d, %Y')}",
                'expected_keywords': [now.strftime('%A'), now.strftime('%B')],
                'type': 'temporal',
                'difficulty': 'medium',
            },
        ]

        challenge = random.choice(challenges)
        challenge['generated_at'] = timezone.now()
        challenge['valid_until'] = timezone.now() + timezone.timedelta(seconds=30)

        return challenge

    def _generate_personal_challenge(self) -> Dict[str, Any]:
        """
        Generate user-specific challenge (only real user knows).

        Requires user object with personal information.
        """
        if not self.user:
            # Fall back to generic challenge
            return self._generate_temporal_challenge()

        challenges = [
            {
                'phrase': f"State your employee ID: {self.user.peoplecode}",
                'expected_keywords': [str(self.user.peoplecode)],
                'type': 'personal',
                'difficulty': 'easy',
            },
            {
                'phrase': f"Say your full name: {self.user.peoplename}",
                'expected_keywords': self.user.peoplename.split(),
                'type': 'personal',
                'difficulty': 'easy',
            },
        ]

        # Add manager name if available
        if hasattr(self.user, 'reporting_manager') and self.user.reporting_manager:
            challenges.append({
                'phrase': f"Who is your reporting manager?",
                'expected_keywords': self.user.reporting_manager.peoplename.split(),
                'type': 'personal',
                'difficulty': 'medium',
            })

        challenge = random.choice(challenges)
        challenge['generated_at'] = timezone.now()
        challenge['valid_until'] = timezone.now() + timezone.timedelta(seconds=45)

        return challenge

    def _generate_visual_challenge(self) -> Dict[str, Any]:
        """
        Generate challenge with on-screen code (visual-audio correlation).

        User must read what they see on screen, preventing replay attacks.
        """
        # Generate random code
        code_length = random.randint(4, 6)
        code = ''.join(random.choices(string.digits, k=code_length))

        return {
            'phrase': f"Read the code displayed on screen: {code}",
            'display_code': code,
            'expected_keywords': list(code),
            'type': 'visual_correlation',
            'difficulty': 'easy',
            'generated_at': timezone.now(),
            'valid_until': timezone.now() + timezone.timedelta(seconds=30),
        }

    def _generate_liveness_challenge(self) -> Dict[str, Any]:
        """
        Generate behavioral liveness challenge.

        Requires specific speaking patterns that are hard to fake.
        """
        challenges = [
            {
                'phrase': "Say 'yes' then 'no' with a 2-second pause",
                'expected_pattern': ['yes', 'pause', 'no'],
                'type': 'liveness',
                'difficulty': 'medium',
            },
            {
                'phrase': "Count from 1 to 5, emphasizing number 3",
                'expected_pattern': ['1', '2', 'THREE', '4', '5'],
                'type': 'liveness',
                'difficulty': 'medium',
            },
            {
                'phrase': "Say your name, then spell it slowly",
                'expected_pattern': ['name', 'spelling'],
                'type': 'liveness',
                'difficulty': 'hard',
            },
        ]

        challenge = random.choice(challenges)
        challenge['generated_at'] = timezone.now()
        challenge['valid_until'] = timezone.now() + timezone.timedelta(seconds=60)

        return challenge

    def _generate_multilingual_challenge(self) -> Dict[str, Any]:
        """
        Generate multilingual challenge (for multilingual environments).

        User must mix languages, which is harder for deepfakes to fake naturally.
        """
        if self.language_short == 'hi':
            # Hindi + English
            return {
                'phrase': "Say numbers 1 to 3 in English, then 4 to 6 in Hindi",
                'expected_keywords': ['one', 'two', 'three', 'चार', 'पांच', 'छह'],
                'type': 'multilingual',
                'difficulty': 'hard',
                'generated_at': timezone.now(),
                'valid_until': timezone.now() + timezone.timedelta(seconds=45),
            }
        else:
            # Default to temporal challenge
            return self._generate_temporal_challenge()

    def _generate_mathematical_challenge(self) -> Dict[str, Any]:
        """
        Generate simple math challenge.

        User must calculate and speak answer, requiring real-time cognition.
        """
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operation = random.choice(['+', '-'])

        if operation == '+':
            answer = num1 + num2
            phrase = f"What is {num1} plus {num2}?"
        else:
            # Ensure positive result
            if num1 < num2:
                num1, num2 = num2, num1
            answer = num1 - num2
            phrase = f"What is {num1} minus {num2}?"

        return {
            'phrase': phrase,
            'expected_keywords': [str(answer)],
            'expected_answer': answer,
            'type': 'mathematical',
            'difficulty': 'medium',
            'generated_at': timezone.now(),
            'valid_until': timezone.now() + timezone.timedelta(seconds=30),
        }

    def validate_response(
        self,
        challenge: Dict[str, Any],
        spoken_text: str
    ) -> Dict[str, Any]:
        """
        Validate user's spoken response against challenge.

        Args:
            challenge: The challenge that was given
            spoken_text: Transcribed text from user's voice

        Returns:
            Validation result with match status and confidence
        """
        try:
            # Check if challenge has expired
            if 'valid_until' in challenge:
                if timezone.now() > challenge['valid_until']:
                    return {
                        'matched': False,
                        'confidence': 0.0,
                        'reason': 'Challenge expired',
                        'fraud_indicator': 'RESPONSE_TOO_SLOW'
                    }

            # Normalize spoken text
            spoken_normalized = spoken_text.lower().strip()

            # Check for expected keywords
            expected_keywords = challenge.get('expected_keywords', [])
            matched_keywords = sum(
                1 for keyword in expected_keywords
                if str(keyword).lower() in spoken_normalized
            )

            match_ratio = (
                matched_keywords / len(expected_keywords)
                if expected_keywords else 0.0
            )

            # Threshold for match
            threshold = 0.7 if challenge.get('difficulty') == 'hard' else 0.6

            return {
                'matched': match_ratio >= threshold,
                'confidence': match_ratio,
                'matched_keywords': matched_keywords,
                'total_keywords': len(expected_keywords),
                'reason': 'Match successful' if match_ratio >= threshold else 'Insufficient keyword matches'
            }

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Error validating response: {e}")
            return {
                'matched': False,
                'confidence': 0.0,
                'reason': f'Validation error: {str(e)}',
                'fraud_indicator': 'VALIDATION_ERROR'
            }