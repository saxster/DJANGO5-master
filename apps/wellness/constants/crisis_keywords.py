"""
Crisis Detection Keywords and Patterns

Centralized crisis detection keywords and stress trigger patterns
used across journal analytics and wellness services.

CONSOLIDATES FROM:
- apps/journal/services/analytics_service.py (lines 765-768)
- apps/journal/services/pattern_analyzer.py (lines 45-58)
- apps/wellness/services/wellness/urgency_analysis_service.py (lines 20)

USAGE:
- Crisis keyword detection for immediate intervention
- Stress trigger categorization for targeted content
- Urgency scoring in wellness content delivery
"""

# Crisis keywords for content analysis (most severe indicators)
CRISIS_KEYWORDS = [
    'hopeless',
    'overwhelmed',
    "can't cope",
    'breaking point',
    'giving up',
    'no point',
    'worthless',
    'suicidal',
    'end it all',
    'nobody cares',
    'failure',
    'disaster',
    'catastrophe',
    'ruined'
]

# Crisis risk factors (broader warning signs)
CRISIS_RISK_FACTORS = {
    'mood_crisis': {
        'threshold': 2,  # mood_rating <= 2
        'urgency_boost': 4,
        'intervention': 'mood_crisis_support'
    },
    'high_stress': {
        'threshold': 4,  # stress_level >= 4
        'urgency_boost': 3,
        'intervention': 'stress_management'
    },
    'low_energy': {
        'threshold': 3,  # energy_level <= 3
        'urgency_boost': 1,
        'intervention': 'energy_management'
    },
    'safety_concern': {
        'entry_type': 'SAFETY_CONCERN',
        'urgency_boost': 2,
        'intervention': 'workplace_safety_education'
    }
}

# Stress trigger patterns for categorization and targeted interventions
STRESS_TRIGGER_PATTERNS = {
    'equipment': {
        'keywords': [
            'equipment',
            'machine',
            'tool',
            'device',
            'system',
            'malfunction'
        ],
        'urgency_boost': 2,
        'category': 'equipment_stress_management',
        'action': 'equipment_failure_protocol'
    },
    'deadline': {
        'keywords': [
            'deadline',
            'due',
            'urgent',
            'rush',
            'time pressure',
            'behind schedule'
        ],
        'urgency_boost': 1,
        'category': 'time_management',
        'action': 'priority_setting_technique'
    },
    'workload': {
        'keywords': [
            'overloaded',
            'too much',
            'exhausted',
            'burnout',
            'overwhelmed'
        ],
        'urgency_boost': 1,
        'category': 'workload_management',
        'action': 'workload_balancing'
    },
    'interpersonal': {
        'keywords': [
            'conflict',
            'argument',
            'tension',
            'difficult',
            'colleague'
        ],
        'urgency_boost': 1,
        'category': 'interpersonal_skills',
        'action': 'conflict_resolution'
    },
    'safety': {
        'keywords': [
            'unsafe',
            'dangerous',
            'risk',
            'hazard',
            'accident',
            'injury'
        ],
        'urgency_boost': 2,
        'category': 'workplace_safety',
        'action': 'safety_protocols'
    }
}
