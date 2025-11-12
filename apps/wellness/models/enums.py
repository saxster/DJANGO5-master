"""
Wellness Content Enums

Classification enums for wellness content categorization and delivery.
Refactored from monolithic models.py (697 lines → focused modules).

Related: Ultrathink Code Review Phase 3 - ARCH-001
"""

from django.db import models


class WellnessContentCategory(models.TextChoices):
    """Wellness content categories for comprehensive health education"""
    MENTAL_HEALTH = 'mental_health', 'Mental Health'
    PHYSICAL_WELLNESS = 'physical_wellness', 'Physical Wellness'
    WORKPLACE_HEALTH = 'workplace_health', 'Workplace Health'
    SUBSTANCE_AWARENESS = 'substance_awareness', 'Substance Awareness'
    PREVENTIVE_CARE = 'preventive_care', 'Preventive Care'
    SLEEP_HYGIENE = 'sleep_hygiene', 'Sleep Hygiene'
    NUTRITION_BASICS = 'nutrition_basics', 'Nutrition Basics'
    STRESS_MANAGEMENT = 'stress_management', 'Stress Management'
    PHYSICAL_ACTIVITY = 'physical_activity', 'Physical Activity'
    MINDFULNESS = 'mindfulness', 'Mindfulness'


class WellnessDeliveryContext(models.TextChoices):
    """Context-based delivery triggers for intelligent content serving"""
    DAILY_TIP = 'daily_tip', 'Daily Wellness Tip'
    PATTERN_TRIGGERED = 'pattern_triggered', 'Pattern-Based Delivery'
    STRESS_RESPONSE = 'stress_response', 'High Stress Response'
    MOOD_SUPPORT = 'mood_support', 'Low Mood Support'
    ENERGY_BOOST = 'energy_boost', 'Low Energy Response'
    SHIFT_TRANSITION = 'shift_transition', 'Shift Start/End'
    STREAK_MILESTONE = 'streak_milestone', 'Milestone Reward'
    SEASONAL = 'seasonal', 'Seasonal Health'
    WORKPLACE_SPECIFIC = 'workplace_specific', 'Workplace Guidance'
    GRATITUDE_ENHANCEMENT = 'gratitude_enhancement', 'Positive Psychology Reinforcement'


class WellnessContentLevel(models.TextChoices):
    """Content complexity and time investment levels"""
    QUICK_TIP = 'quick_tip', 'Quick Tip (1 min)'
    SHORT_READ = 'short_read', 'Short Read (3 min)'
    DEEP_DIVE = 'deep_dive', 'Deep Dive (7 min)'
    INTERACTIVE = 'interactive', 'Interactive (5 min)'
    VIDEO_CONTENT = 'video_content', 'Video Content (4 min)'


class EvidenceLevel(models.TextChoices):
    """Evidence quality levels for medical/health compliance"""
    WHO_CDC_GUIDELINE = 'who_cdc', 'WHO/CDC Guideline'
    PEER_REVIEWED_RESEARCH = 'peer_reviewed', 'Peer-Reviewed Research'
    PROFESSIONAL_CONSENSUS = 'professional', 'Professional Consensus'
    ESTABLISHED_PRACTICE = 'established', 'Established Practice'
    EDUCATIONAL_CONTENT = 'educational', 'General Education'


__all__ = [
    'WellnessContentCategory',
    'WellnessDeliveryContext',
    'WellnessContentLevel',
    'EvidenceLevel',
]
