"""
Tutorial Content Library - Interactive Admin Tutorials

Comprehensive tutorial definitions for the AI mentor system.

Following .claude/rules.md:
- Rule #16: Magic numbers → constants
- Single responsibility per tutorial
- Concise, actionable content
"""

TUTORIALS = {
    'welcome': {
        'id': 'welcome',
        'title': 'Welcome to Your AI-Powered Admin Panel',
        'description': 'Quick 2-minute overview of key features',
        'duration': '2 minutes',
        'difficulty': 'BEGINNER',
        'category': 'Getting Started',
        'steps': [
            {
                'title': 'Welcome!',
                'content': 'This admin panel is supercharged with AI to help you work faster and smarter. Let me show you around.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Your Command Center',
                'content': 'The Team Dashboard shows everything: urgent items, team workload, recent activities. Check it every morning.',
                'highlight': '#team-dashboard-link',
                'action': 'Click to view dashboard'
            },
            {
                'title': 'AI Suggestions',
                'content': 'See this lightbulb icon? That\'s your AI mentor. Click it anytime for smart suggestions based on what you\'re doing.',
                'highlight': '.mentor-icon',
                'action': None
            },
            {
                'title': 'You\'re Ready!',
                'content': 'That\'s it! Explore on your own, or take detailed tutorials for specific features. Press ? anytime for keyboard shortcuts.',
                'highlight': None,
                'action': 'Start using the admin panel'
            }
        ]
    },
    
    'team_dashboard_deep_dive': {
        'id': 'team_dashboard_deep_dive',
        'title': 'Master Your Team Dashboard',
        'description': 'Learn to use your command center effectively',
        'duration': '10 minutes',
        'difficulty': 'BEGINNER',
        'category': 'Core Features',
        'steps': [
            {
                'title': 'Your Command Center',
                'content': 'The Team Dashboard is your mission control. Everything important happens here.',
                'highlight': '#team-dashboard',
                'action': None
            },
            {
                'title': 'Priority Alerts First',
                'content': 'Red items are urgent and might miss deadlines. Always check these first thing in the morning.',
                'highlight': '.priority-alerts-section',
                'action': 'Review urgent items'
            },
            {
                'title': 'Team Workload',
                'content': 'See who\'s busy and who has capacity. Use this to balance work assignments.',
                'highlight': '.team-workload-chart',
                'action': None
            },
            {
                'title': 'Activity Timeline',
                'content': 'Recent activities scroll here in real-time. Click any item for full details.',
                'highlight': '.activity-timeline',
                'action': 'Click an activity'
            },
            {
                'title': 'Quick Filters',
                'content': 'Filter by status, priority, person, or date range. Your filters are saved automatically.',
                'highlight': '.dashboard-filters',
                'action': 'Try a filter'
            },
            {
                'title': 'Export Data',
                'content': 'Need a report? Export to Excel or PDF with one click.',
                'highlight': '.export-button',
                'action': 'Click to see export options'
            }
        ]
    },
    
    'quick_actions_mastery': {
        'id': 'quick_actions_mastery',
        'title': 'Quick Actions Mastery',
        'description': 'Handle common incidents 63% faster',
        'duration': '15 minutes',
        'difficulty': 'INTERMEDIATE',
        'category': 'Productivity',
        'steps': [
            {
                'title': 'What Are Quick Actions?',
                'content': 'Quick Actions are pre-programmed responses to common issues. They save 20+ minutes per incident by automating repetitive work.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Find Quick Actions',
                'content': 'On any ticket detail page, click the lightning bolt icon to see available Quick Actions.',
                'highlight': '.quick-actions-button',
                'action': 'Click lightning bolt'
            },
            {
                'title': 'Camera Offline Example',
                'content': 'For "Camera Offline" tickets, Quick Action automatically: 1) Pings camera, 2) Creates troubleshooting checklist, 3) Assigns to tech team, 4) Sends notification.',
                'highlight': '.quick-action-camera-offline',
                'action': 'Click to preview'
            },
            {
                'title': 'Review Before Apply',
                'content': 'Always review what Quick Action will do before confirming. You can customize steps if needed.',
                'highlight': '.quick-action-preview',
                'action': None
            },
            {
                'title': 'Create Custom Quick Actions',
                'content': 'See a pattern? Create your own Quick Action for recurring issues. Admins save 10+ hours per week this way.',
                'highlight': '.create-quick-action',
                'action': 'Create custom action'
            }
        ]
    },
    
    'priority_alerts_guide': {
        'id': 'priority_alerts_guide',
        'title': 'Never Miss Another Deadline',
        'description': 'Master priority alerts and SLA predictions',
        'duration': '8 minutes',
        'difficulty': 'BEGINNER',
        'category': 'Core Features',
        'steps': [
            {
                'title': 'AI Predicts SLA Violations',
                'content': 'Our AI analyzes ticket patterns and predicts which tickets might miss their deadlines. You get warned hours in advance.',
                'highlight': '.priority-alerts',
                'action': None
            },
            {
                'title': 'Risk Levels Explained',
                'content': 'HIGH (red) = Likely to miss deadline. MEDIUM (yellow) = Watch closely. LOW (green) = On track.',
                'highlight': '.risk-level-legend',
                'action': None
            },
            {
                'title': 'Take Action Early',
                'content': 'When you see a HIGH risk alert, you have options: Reassign, Escalate, Request extension, or Add resources.',
                'highlight': '.alert-actions',
                'action': 'Click an alert to see actions'
            },
            {
                'title': 'Configure Your Alerts',
                'content': 'Set how early you want warnings (2 hours? 1 day?) and choose notification methods (email, SMS, push).',
                'highlight': '.alert-settings',
                'action': 'Configure preferences'
            }
        ]
    },
    
    'smart_assignment_tutorial': {
        'id': 'smart_assignment_tutorial',
        'title': 'AI-Powered Smart Assignment',
        'description': 'Let AI assign tickets to the right person',
        'duration': '10 minutes',
        'difficulty': 'INTERMEDIATE',
        'category': 'AI Features',
        'steps': [
            {
                'title': 'The Assignment Problem',
                'content': 'Manually assigning 50+ tickets per day? It takes 2-3 minutes each. Smart Assignment does it in seconds.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'How It Works',
                'content': 'AI considers: 1) Skills match, 2) Current workload, 3) Past performance, 4) Availability, 5) Location proximity.',
                'highlight': '.smart-assignment-algorithm',
                'action': None
            },
            {
                'title': 'Single Ticket Assignment',
                'content': 'On ticket page, click "Suggest Assignment". AI shows top 3 candidates with confidence scores and reasoning.',
                'highlight': '.suggest-assignment-button',
                'action': 'Try it'
            },
            {
                'title': 'Bulk Assignment',
                'content': 'On ticket list, select multiple tickets and choose "Smart Assign All". AI assigns all at once.',
                'highlight': '.bulk-smart-assign',
                'action': 'Select tickets and try'
            },
            {
                'title': 'Review & Override',
                'content': 'AI suggestions are just that - suggestions. You can always override and assign manually.',
                'highlight': '.assignment-override',
                'action': None
            }
        ]
    },
    
    'saved_views_workshop': {
        'id': 'saved_views_workshop',
        'title': 'Save Time with Saved Views',
        'description': 'Stop rebuilding filters every day',
        'duration': '8 minutes',
        'difficulty': 'BEGINNER',
        'category': 'Productivity',
        'steps': [
            {
                'title': 'The Daily Grind',
                'content': 'Do you filter by the same criteria every day? "High priority + Unassigned + My team"? Stop! Save it once, use forever.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Create a Saved View',
                'content': 'Apply your filters, then click "Save View". Name it something memorable like "Morning Urgent Review".',
                'highlight': '.save-view-button',
                'action': 'Save current view'
            },
            {
                'title': 'Access Saved Views',
                'content': 'Your saved views appear in the sidebar. Click once to apply all filters instantly.',
                'highlight': '.saved-views-list',
                'action': 'Click a saved view'
            },
            {
                'title': 'Share with Team',
                'content': 'Share useful views with your team. Everyone sees the same filtered data.',
                'highlight': '.share-view-button',
                'action': 'Share a view'
            },
            {
                'title': 'Scheduled Email Reports',
                'content': 'Pro tip: Get any saved view emailed to you daily at 8 AM. Perfect for morning standup.',
                'highlight': '.schedule-report-button',
                'action': 'Schedule a report'
            }
        ]
    },
    
    'keyboard_shortcuts_bootcamp': {
        'id': 'keyboard_shortcuts_bootcamp',
        'title': 'Keyboard Shortcuts Bootcamp',
        'description': 'Work 30% faster without touching your mouse',
        'duration': '12 minutes',
        'difficulty': 'ADVANCED',
        'category': 'Productivity',
        'steps': [
            {
                'title': 'Why Shortcuts Matter',
                'content': 'Power users handle 100+ tickets daily using almost no mouse. Learn just 5 shortcuts to start saving 30% time.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Essential 5 Shortcuts',
                'content': 'Start with these:\n? = Show all shortcuts\na = Assign ticket\nr = Resolve ticket\nn = Add note\n/ = Search',
                'highlight': '.shortcuts-cheatsheet',
                'action': 'Press ? to see all'
            },
            {
                'title': 'Practice: Assign Ticket',
                'content': 'Open any unassigned ticket. Press "a". Type person\'s name, press Enter. Done in 3 seconds!',
                'highlight': None,
                'action': 'Try it now'
            },
            {
                'title': 'Practice: Quick Notes',
                'content': 'Press "n" to add a note without clicking. Type, press Ctrl+Enter to save. No mouse needed!',
                'highlight': None,
                'action': 'Add a note with "n"'
            },
            {
                'title': 'Advanced: Custom Shortcuts',
                'content': 'Create your own shortcuts for actions you do 10+ times daily. Settings > Keyboard Shortcuts.',
                'highlight': '.custom-shortcuts-settings',
                'action': 'Create custom shortcut'
            }
        ]
    },
    
    'approval_workflow_guide': {
        'id': 'approval_workflow_guide',
        'title': 'Approval Workflows for Safety',
        'description': 'Prevent costly mistakes with approvals',
        'duration': '15 minutes',
        'difficulty': 'ADVANCED',
        'category': 'Enterprise Features',
        'steps': [
            {
                'title': 'High-Risk Actions Need Approval',
                'content': 'Some actions are irreversible or expensive: Deleting records, bulk updates, financial transactions. Require approval first.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Request Approval',
                'content': 'When you try a high-risk action, system asks for approval. Enter justification and submit.',
                'highlight': '.approval-request-form',
                'action': 'Submit test request'
            },
            {
                'title': 'Approve Requests',
                'content': 'If you\'re an approver, you see pending requests here. Review details carefully before approving.',
                'highlight': '.approval-inbox',
                'action': 'Review a request'
            },
            {
                'title': 'Audit Trail',
                'content': 'Every approval is logged: Who requested, who approved, when, why. Perfect for compliance.',
                'highlight': '.approval-audit-log',
                'action': 'View audit log'
            }
        ]
    },
    
    'timeline_investigation': {
        'id': 'timeline_investigation',
        'title': 'Investigate with Activity Timelines',
        'description': 'See complete history of any record',
        'duration': '10 minutes',
        'difficulty': 'INTERMEDIATE',
        'category': 'Troubleshooting',
        'steps': [
            {
                'title': 'What Happened?',
                'content': 'When investigating issues, you need to know: What changed? Who changed it? When? Why? Timeline shows everything.',
                'highlight': None,
                'action': None
            },
            {
                'title': 'Open Timeline',
                'content': 'On any detail page, click the clock icon to see full activity timeline.',
                'highlight': '.timeline-button',
                'action': 'Open timeline'
            },
            {
                'title': 'Filter Timeline',
                'content': 'Too many events? Filter by: Event type, User, Date range, Field changed.',
                'highlight': '.timeline-filters',
                'action': 'Apply filters'
            },
            {
                'title': 'Related Events',
                'content': 'Timeline shows related events from other records. See the full story.',
                'highlight': '.related-events',
                'action': 'Expand related events'
            }
        ]
    },
    
    'shift_tracker_training': {
        'id': 'shift_tracker_training',
        'title': 'Real-Time Shift Tracker',
        'description': 'Monitor who\'s working right now',
        'duration': '8 minutes',
        'difficulty': 'BEGINNER',
        'category': 'Operations',
        'steps': [
            {
                'title': 'Live Shift Status',
                'content': 'Shift Tracker shows who\'s clocked in, where they are, and what they\'re working on - in real time.',
                'highlight': '.shift-tracker',
                'action': None
            },
            {
                'title': 'Post Assignments',
                'content': 'See all posts and who\'s assigned to each. Empty posts show in red.',
                'highlight': '.post-assignments',
                'action': None
            },
            {
                'title': 'GPS Tracking',
                'content': 'Click any guard to see their location on map. Ensure they\'re at assigned post.',
                'highlight': '.guard-location',
                'action': 'View on map'
            },
            {
                'title': 'Missing Clock-Outs',
                'content': 'System alerts you if someone forgot to clock out. Fix it with one click.',
                'highlight': '.missing-clockout-alert',
                'action': 'Fix clock-out'
            }
        ]
    },
    
    'efficiency_optimization': {
        'id': 'efficiency_optimization',
        'title': 'Maximize Your Efficiency',
        'description': 'Use AI insights to work smarter',
        'duration': '12 minutes',
        'difficulty': 'ADVANCED',
        'category': 'AI Features',
        'steps': [
            {
                'title': 'Your Efficiency Score',
                'content': 'AI calculates your efficiency score (0-100) based on: Features used, Time saved, Shortcuts mastery.',
                'highlight': '.efficiency-score',
                'action': None
            },
            {
                'title': 'Time Saved Report',
                'content': 'See exactly how many hours you\'ve saved using AI features. Share this with your manager!',
                'highlight': '.time-saved-report',
                'action': 'View detailed report'
            },
            {
                'title': 'Personalized Recommendations',
                'content': 'AI suggests which features you should learn next for maximum impact.',
                'highlight': '.ai-recommendations',
                'action': 'View recommendations'
            },
            {
                'title': 'Weekly Goals',
                'content': 'Set efficiency goals: "Save 5 hours this week" or "Learn 2 new features". Track your progress.',
                'highlight': '.efficiency-goals',
                'action': 'Set a goal'
            }
        ]
    }
}


def get_tutorial(tutorial_id):
    """
    Retrieve tutorial by unique identifier.

    Fetches tutorial configuration from the in-memory TUTORIALS registry.
    Used by the AI mentor system to deliver contextual learning content
    to admin users based on their current workflow context.

    Args:
        tutorial_id: Unique tutorial identifier. Valid IDs include:
            'welcome', 'team_dashboard_deep_dive', 'quick_actions_mastery',
            'priority_alerts_guide', 'smart_assignment_tutorial',
            'saved_views_workshop', 'keyboard_shortcuts_bootcamp',
            'approval_workflow_guide', 'timeline_investigation',
            'shift_tracker_training', 'efficiency_optimization'

    Returns:
        Dictionary with tutorial data containing keys:
        - id: Tutorial identifier
        - title: Display title
        - description: Brief description
        - duration: Estimated completion time (e.g., "10 minutes")
        - difficulty: Skill level (BEGINNER, INTERMEDIATE, ADVANCED)
        - category: Tutorial category grouping
        - steps: List of tutorial steps with content and UI actions

        Returns None if tutorial_id not found.

    Example:
        >>> tutorial = get_tutorial('welcome')
        >>> print(tutorial['title'])
        'Welcome to Your AI-Powered Admin Panel'
        >>> print(tutorial['duration'])
        '2 minutes'
        >>> print(len(tutorial['steps']))
        4

    Related: list_tutorials(), get_recommended_for_skill_level()
    """
    return TUTORIALS.get(tutorial_id)


def list_tutorials(category=None, difficulty=None):
    """
    List all tutorials with optional filtering by category and difficulty.

    Returns complete tutorial registry or filtered subset. Use this to populate
    tutorial menus, browse interfaces, or generate recommended tutorial lists
    based on user preferences.

    Args:
        category: Optional category filter. Valid categories:
            'Getting Started', 'Core Features', 'Productivity',
            'AI Features', 'Enterprise Features', 'Troubleshooting',
            'Operations'
        difficulty: Optional difficulty filter. Valid levels:
            'BEGINNER', 'INTERMEDIATE', 'ADVANCED'

    Returns:
        List of tutorial dictionaries. Each tutorial contains:
        - id: Unique identifier
        - title: Display title
        - description: Brief description
        - duration: Estimated completion time
        - difficulty: Skill level required
        - category: Tutorial category
        - steps: List of tutorial steps

        Returns all 11 tutorials if no filters applied.

    Example:
        >>> # Get all beginner tutorials
        >>> beginner = list_tutorials(difficulty='BEGINNER')
        >>> print(len(beginner))
        4

        >>> # Get all productivity tutorials
        >>> productivity = list_tutorials(category='Productivity')
        >>> for t in productivity:
        ...     print(t['title'])
        'Quick Actions Mastery'
        'Save Time with Saved Views'
        'Keyboard Shortcuts Bootcamp'

        >>> # Get beginner productivity tutorials
        >>> easy_prod = list_tutorials(category='Productivity', difficulty='BEGINNER')

    Related: get_tutorial(), get_categories(), get_recommended_for_skill_level()
    """
    tutorials = list(TUTORIALS.values())

    if category:
        tutorials = [t for t in tutorials if t['category'] == category]

    if difficulty:
        tutorials = [t for t in tutorials if t['difficulty'] == difficulty]

    return tutorials


def get_categories():
    """
    Get all unique tutorial categories from the tutorial registry.

    Extracts distinct category values to populate category filters,
    navigation menus, and tutorial organization interfaces.

    Returns:
        List of unique category strings:
        - 'Getting Started'
        - 'Core Features'
        - 'Productivity'
        - 'AI Features'
        - 'Enterprise Features'
        - 'Troubleshooting'
        - 'Operations'

        Categories are unordered (set-derived).

    Example:
        >>> categories = get_categories()
        >>> print(len(categories))
        7
        >>> 'Productivity' in categories
        True
        >>> # Use for dropdown menu
        >>> for cat in sorted(categories):
        ...     print(f"<option>{cat}</option>")

    Related: list_tutorials(), get_tutorial()
    """
    return list(set(t['category'] for t in TUTORIALS.values()))


def get_recommended_for_skill_level(skill_level):
    """
    Get recommended tutorials matching user's skill level.

    Maps user skill levels to appropriate tutorial difficulty and returns
    matching tutorials. Used for personalized onboarding and skill development
    paths in the AI mentor system.

    Args:
        skill_level: User's self-reported or assessed skill level:
            - 'NOVICE': Complete beginners (maps to BEGINNER tutorials)
            - 'INTERMEDIATE': Some experience (maps to INTERMEDIATE tutorials)
            - 'ADVANCED': Experienced users (maps to ADVANCED tutorials)
            - 'EXPERT': Power users (maps to ADVANCED tutorials)

            Defaults to 'BEGINNER' if skill_level not recognized.

    Returns:
        List of tutorial dictionaries matching the skill level.
        Each tutorial contains standard keys (id, title, description,
        duration, difficulty, category, steps).

        Returns 4 BEGINNER, 3 INTERMEDIATE, or 3 ADVANCED tutorials
        depending on skill_level.

    Example:
        >>> # New user onboarding
        >>> novice_tutorials = get_recommended_for_skill_level('NOVICE')
        >>> print([t['title'] for t in novice_tutorials])
        ['Welcome to Your AI-Powered Admin Panel',
         'Master Your Team Dashboard',
         'Never Miss Another Deadline',
         'Real-Time Shift Tracker']

        >>> # Advanced user recommendations
        >>> advanced = get_recommended_for_skill_level('EXPERT')
        >>> print(len(advanced))
        3

    Related: list_tutorials(), get_tutorial()
    """
    difficulty_map = {
        'NOVICE': 'BEGINNER',
        'INTERMEDIATE': 'INTERMEDIATE',
        'ADVANCED': 'ADVANCED',
        'EXPERT': 'ADVANCED'
    }

    target_difficulty = difficulty_map.get(skill_level, 'BEGINNER')

    return [
        t for t in TUTORIALS.values()
        if t['difficulty'] == target_difficulty
    ]
