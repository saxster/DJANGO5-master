"""
Tutorial Content Definitions

Complete interactive tutorials for all admin features.

Following .claude/rules.md:
- Rule #1: Simple, clean, maintainable code
- Rule #2: Self-documenting patterns
"""

# All available tutorials
TUTORIALS = {
    'welcome': {
        'id': 'welcome',
        'title': 'Welcome Tour',
        'description': 'A quick 2-minute introduction to your admin panel',
        'duration': '2 minutes',
        'difficulty': 'BEGINNER',
        'points': 10,
        'badge_icon': '👋',
        'steps': [
            {
                'title': 'Welcome! 👋',
                'message': "Hi! I'm your AI assistant. Let me show you the most important features in just 2 minutes.",
                'target_element': '#mentor-avatar',
                'position': 'left',
                'highlight_type': 'glow'
            },
            {
                'title': 'Your Command Center',
                'message': 'This is the Team Dashboard. It shows ALL your tickets, incidents, and alerts in ONE place. No more switching between pages!',
                'target_element': '#team-dashboard-link',
                'position': 'right',
                'action_required': 'view'
            },
            {
                'title': 'Priority Alerts',
                'message': 'These colored badges tell you what needs attention: 🔴 Urgent (handle now), 🟠 Soon (check today), 🟢 On Track (all good)',
                'target_element': '.priority-badge',
                'position': 'bottom'
            },
            {
                'title': 'Quick Actions ⚡',
                'message': 'Handle common problems 63% faster! Click this button to use pre-built automated responses.',
                'target_element': '.quick-action-btn',
                'position': 'bottom'
            },
            {
                'title': 'Get Help Anytime',
                'message': "Stuck? Click this ? button anytime. I'll show you relevant help based on what you're doing.",
                'target_element': '#help-toggle-btn',
                'position': 'left'
            },
            {
                'title': "You're All Set! 🎉",
                'message': "That's it! You now know the basics. Want to learn more advanced features?",
                'target_element': '#mentor-avatar',
                'position': 'left',
                'next_button': 'Complete Tour'
            }
        ]
    },
    
    'team_dashboard': {
        'id': 'team_dashboard',
        'title': 'Team Dashboard Deep Dive',
        'description': 'Master your command center in 5 minutes',
        'duration': '5 minutes',
        'difficulty': 'BEGINNER',
        'points': 20,
        'badge_icon': '📊',
        'steps': [
            {
                'title': 'Your Command Center',
                'message': 'The Team Dashboard is where you manage everything. Tickets, incidents, alerts, work orders - all in one place.',
                'target_element': '.team-dashboard-container',
                'position': 'center',
                'highlight_type': 'fade-in'
            },
            {
                'title': 'Filters & Search',
                'message': 'Use these filters to find exactly what you need: My Tasks, Unassigned, Priority Alerts, or search by keywords.',
                'target_element': '.dashboard-filters',
                'position': 'top'
            },
            {
                'title': 'One-Click Actions',
                'message': 'Click any item to see quick actions: Take It (assign to you), Assign (to someone else), Mark Done, Get Help.',
                'target_element': '.quick-actions-column',
                'position': 'left'
            },
            {
                'title': 'Priority Indicators',
                'message': '🔴 Red = Handle Now (SLA risk), 🟠 Orange = Check Today, 🟢 Green = On Track. Focus on red first!',
                'target_element': '.priority-indicators',
                'position': 'bottom'
            },
            {
                'title': 'Keyboard Shortcuts',
                'message': 'Work faster! Select an item and press: "a" to assign, "r" to resolve, "n" to add note. Press "?" to see all shortcuts.',
                'target_element': '.shortcut-hint',
                'position': 'bottom'
            },
            {
                'title': 'Real-Time Updates',
                'message': "The dashboard updates automatically every 30 seconds. New items appear with a highlight. You'll never miss anything!",
                'target_element': '.dashboard-content',
                'position': 'center'
            }
        ]
    },
    
    'priority_alerts': {
        'id': 'priority_alerts',
        'title': 'Priority Alert System',
        'description': 'Never miss urgent issues again',
        'duration': '3 minutes',
        'difficulty': 'BEGINNER',
        'points': 15,
        'badge_icon': '🎯',
        'steps': [
            {
                'title': 'What Are Priority Alerts?',
                'message': 'Priority Alerts are AI-calculated scores that tell you which items need attention first. No more guessing!',
                'target_element': '.priority-badge',
                'position': 'bottom'
            },
            {
                'title': 'The Color System',
                'message': '🔴 Red (90-100): Critical - Handle immediately, 🟠 Orange (70-89): Important - Address today, 🟢 Green (0-69): Normal - No rush',
                'target_element': '.priority-legend',
                'position': 'top'
            },
            {
                'title': 'What Affects Priority?',
                'message': 'The system considers: SLA deadline proximity, Customer VIP status, Issue severity, Time since creation, Past escalation history',
                'target_element': '.priority-factors',
                'position': 'right'
            },
            {
                'title': 'Filter by Priority',
                'message': 'Click here to show only high-priority items. Perfect for starting your day!',
                'target_element': '#priority-filter',
                'position': 'bottom',
                'action_required': 'click'
            },
            {
                'title': 'Desktop Notifications',
                'message': 'Enable notifications to get alerted when new high-priority items appear. Never miss critical issues!',
                'target_element': '.notification-settings',
                'position': 'left'
            }
        ]
    },
    
    'quick_actions': {
        'id': 'quick_actions',
        'title': 'Quick Actions Mastery',
        'description': 'Handle incidents 63% faster with automation',
        'duration': '8 minutes',
        'difficulty': 'INTERMEDIATE',
        'points': 30,
        'badge_icon': '⚡',
        'steps': [
            {
                'title': 'What are Quick Actions?',
                'message': 'Quick Actions are pre-built responses that automate common tasks. Example: "Camera Offline" action pings camera, assigns to tech team, and creates a checklist for you.',
                'target_element': '.quick-action-btn',
                'position': 'bottom'
            },
            {
                'title': 'Choosing an Action',
                'message': 'Click Quick Actions to see available options. Each shows: What it does, What happens automatically, What you need to do.',
                'target_element': '.quick-action-list',
                'position': 'top',
                'action_required': 'click'
            },
            {
                'title': 'Automated Steps',
                'message': 'Green items happen automatically. The computer does these for you. Example: Assign to on-call team, Send notifications, Update status.',
                'target_element': '.automated-steps',
                'position': 'right',
                'highlight_type': 'fade-in'
            },
            {
                'title': 'Your Checklist',
                'message': 'Orange items are your checklist. Complete each step: Upload photos, Add notes, Verify completion.',
                'target_element': '.manual-steps',
                'position': 'right',
                'highlight_type': 'fade-in'
            },
            {
                'title': 'Time Saved',
                'message': 'Each Quick Action shows time saved. Average: 20 minutes per incident. That adds up to hours every week!',
                'target_element': '.time-saved-badge',
                'position': 'bottom'
            },
            {
                'title': 'Custom Quick Actions',
                'message': 'Admins can create custom Quick Actions for your site-specific processes. Ask your admin!',
                'target_element': '.custom-actions-section',
                'position': 'left'
            },
            {
                'title': 'Success Tracking',
                'message': 'We track which Quick Actions work best. The system learns and improves recommendations over time.',
                'target_element': '.success-metrics',
                'position': 'top'
            }
        ]
    },
    
    'smart_assignment': {
        'id': 'smart_assignment',
        'title': 'Smart Assignment AI',
        'description': 'Let AI suggest the best person for each task',
        'duration': '4 minutes',
        'difficulty': 'INTERMEDIATE',
        'points': 25,
        'badge_icon': '🤖',
        'steps': [
            {
                'title': 'AI-Powered Suggestions',
                'message': 'The system analyzes skills, workload, location, and past performance to suggest the best person for this task.',
                'target_element': '.assignment-suggestions',
                'position': 'top'
            },
            {
                'title': 'Why This Person?',
                'message': "Each suggestion shows WHY they're recommended: Skills match, Low workload (3 tasks), Nearby location (2km), High success rate (94%)",
                'target_element': '.suggestion-card:first-child',
                'position': 'right'
            },
            {
                'title': 'Confidence Score',
                'message': 'The score (85%) shows how confident the AI is. Higher score = better match. Green = good match, Yellow = acceptable, Red = risky',
                'target_element': '.confidence-score',
                'position': 'bottom'
            },
            {
                'title': 'Assign with 1 Click',
                'message': 'Click here to assign to the suggested person. Or choose a different suggestion below.',
                'target_element': '.assign-btn',
                'position': 'left',
                'action_required': 'view'
            },
            {
                'title': 'Workload Balance',
                'message': 'The AI prevents overload. It considers: Current active tasks, Scheduled shifts, Recent assignment history, Time off requests',
                'target_element': '.workload-indicator',
                'position': 'bottom'
            },
            {
                'title': 'Learning Over Time',
                'message': 'The AI improves by tracking: Assignment outcomes, Task completion times, User feedback, Success patterns',
                'target_element': '.ai-learning-indicator',
                'position': 'top'
            }
        ]
    },
    
    'saved_views': {
        'id': 'saved_views',
        'title': 'Save Your Favorite Views',
        'description': 'Stop rebuilding filters - save them instead!',
        'duration': '3 minutes',
        'difficulty': 'BEGINNER',
        'points': 15,
        'badge_icon': '💾',
        'steps': [
            {
                'title': 'Why Save Views?',
                'message': 'Do you apply the same filters every day? Save them once, reuse forever. Example: "My urgent tasks", "Unassigned cameras", "VIP customer tickets"',
                'target_element': '.saved-views-intro',
                'position': 'top'
            },
            {
                'title': 'Start with Filters',
                'message': 'First, set up your filters exactly how you want them. Filter by status, priority, assignee, date range, etc.',
                'target_element': '.filter-sidebar',
                'position': 'right'
            },
            {
                'title': 'Save the View',
                'message': 'Once your filters are perfect, click here to save this view. Give it a memorable name like "Morning Patrol Checks".',
                'target_element': '#save-view-btn',
                'position': 'bottom',
                'action_required': 'click'
            },
            {
                'title': 'Access Saved Views',
                'message': 'Your saved views appear here. Click any one to instantly apply those filters. Lightning fast!',
                'target_element': '.saved-views-dropdown',
                'position': 'bottom'
            },
            {
                'title': 'Share with Team',
                'message': 'Make a view "Public" to share it with your team. Everyone can use your perfectly configured filters!',
                'target_element': '.share-view-toggle',
                'position': 'left'
            },
            {
                'title': 'Get Daily Email Reports',
                'message': 'Turn this on to receive a daily email with this exact view. Great for monitoring specific issues!',
                'target_element': '.email-report-toggle',
                'position': 'left'
            }
        ]
    },
    
    'approval_workflows': {
        'id': 'approval_workflows',
        'title': 'Approval Workflow System',
        'description': 'Streamline approvals with automation',
        'duration': '6 minutes',
        'difficulty': 'INTERMEDIATE',
        'points': 25,
        'badge_icon': '✅',
        'steps': [
            {
                'title': 'What Are Approval Workflows?',
                'message': 'Workflows automate approvals for expenses, time-off, purchases, etc. Set rules once, approve quickly forever.',
                'target_element': '.approval-workflow-intro',
                'position': 'center'
            },
            {
                'title': 'Your Pending Approvals',
                'message': 'All items waiting for YOUR approval appear here. Click to review details and approve/reject.',
                'target_element': '.pending-approvals-list',
                'position': 'top'
            },
            {
                'title': 'Quick Approve/Reject',
                'message': 'For simple items, use these buttons. For complex items, click "Review" to see full details.',
                'target_element': '.approval-buttons',
                'position': 'bottom'
            },
            {
                'title': 'Approval Chain',
                'message': 'Some items require multiple approvals. This shows the complete chain: Manager → Finance → Director',
                'target_element': '.approval-chain',
                'position': 'right'
            },
            {
                'title': 'Add Comments',
                'message': 'Leave notes for the next approver or the requester. Example: "Approved, but keep receipts"',
                'target_element': '.approval-comment-field',
                'position': 'bottom'
            },
            {
                'title': 'Auto-Approval Rules',
                'message': 'Admins can set rules: Auto-approve expenses under $50, Auto-approve time-off with 2 weeks notice, etc.',
                'target_element': '.auto-approval-rules',
                'position': 'left'
            },
            {
                'title': 'Notification Settings',
                'message': 'Configure how you want to be notified: Email immediately, Daily digest, SMS for urgent, Mobile push',
                'target_element': '.approval-notifications',
                'position': 'top'
            }
        ]
    },
    
    'timelines': {
        'id': 'timelines',
        'title': 'Activity Timelines',
        'description': 'See the complete history of any item',
        'duration': '4 minutes',
        'difficulty': 'BEGINNER',
        'points': 20,
        'badge_icon': '📅',
        'steps': [
            {
                'title': 'What Are Timelines?',
                'message': 'Every ticket, incident, and task has a timeline showing EVERYTHING that happened. Never wonder "what happened?" again!',
                'target_element': '.timeline-container',
                'position': 'left'
            },
            {
                'title': 'Event Types',
                'message': 'Different icons show different events: 👤 Assignment, 💬 Comment, 📎 Attachment, ✅ Status change, ⏰ SLA events',
                'target_element': '.timeline-legend',
                'position': 'top'
            },
            {
                'title': 'Automatic Logging',
                'message': 'Everything is logged automatically: Who did what, When it happened, What changed, Why (if noted)',
                'target_element': '.timeline-events',
                'position': 'right'
            },
            {
                'title': 'Filter Timeline',
                'message': 'Too many events? Filter by type: Show only comments, Show only status changes, Show only system events',
                'target_element': '.timeline-filters',
                'position': 'bottom'
            },
            {
                'title': 'Add Comments',
                'message': 'Add your own notes to the timeline. Great for documenting phone calls, site visits, or decisions.',
                'target_element': '.add-comment-btn',
                'position': 'bottom'
            },
            {
                'title': 'Export Timeline',
                'message': 'Need a report? Export the complete timeline to PDF or Excel. Perfect for audits!',
                'target_element': '.export-timeline-btn',
                'position': 'left'
            }
        ]
    },
    
    'shift_tracker': {
        'id': 'shift_tracker',
        'title': 'Shift & Attendance Tracking',
        'description': 'Master shift management and attendance',
        'duration': '7 minutes',
        'difficulty': 'INTERMEDIATE',
        'points': 30,
        'badge_icon': '📍',
        'steps': [
            {
                'title': 'Shift Tracking Overview',
                'message': 'Track who is working, where they are, and when they check in/out. GPS-verified attendance prevents buddy punching.',
                'target_element': '.shift-tracker-intro',
                'position': 'center'
            },
            {
                'title': 'Check In with GPS',
                'message': 'Guards must be at the correct location to check in. The system verifies GPS coordinates against geofences.',
                'target_element': '.checkin-btn',
                'position': 'bottom'
            },
            {
                'title': 'Geofence Boundaries',
                'message': 'Each site has a virtual boundary (geofence). Check-ins only work inside the boundary. Admins can adjust radius.',
                'target_element': '.geofence-map',
                'position': 'right'
            },
            {
                'title': 'Live Attendance View',
                'message': 'See who is currently on-site in real-time. Green = on-site, Yellow = late, Red = no-show, Gray = off-duty',
                'target_element': '.live-attendance',
                'position': 'top'
            },
            {
                'title': 'Exception Handling',
                'message': 'Handle GPS issues gracefully: Manual override (with reason), Photo verification, Supervisor approval',
                'target_element': '.exception-handling',
                'position': 'left'
            },
            {
                'title': 'Attendance Reports',
                'message': 'Generate reports: Daily attendance summary, Late arrival tracking, Hours worked calculation, Exception log',
                'target_element': '.attendance-reports',
                'position': 'bottom'
            },
            {
                'title': 'Shift Swaps',
                'message': 'Guards can request shift swaps. You approve or reject with one click. All changes are logged.',
                'target_element': '.shift-swap-requests',
                'position': 'right'
            }
        ]
    },
    
    'shortcuts': {
        'id': 'shortcuts',
        'title': 'Keyboard Shortcuts Bootcamp',
        'description': 'Power users are 30% faster with shortcuts',
        'duration': '5 minutes',
        'difficulty': 'ADVANCED',
        'points': 35,
        'badge_icon': '⌨️',
        'steps': [
            {
                'title': 'Why Keyboard Shortcuts?',
                'message': 'Research shows keyboard shortcuts make you 30% faster. Less clicking = more work done. Let\'s learn the essentials!',
                'target_element': '.shortcuts-intro',
                'position': 'center'
            },
            {
                'title': 'Navigation: J/K',
                'message': 'Press J to move down, K to move up. Just like Gmail! Try it now on the list below.',
                'target_element': '.ticket-row:first-child',
                'position': 'right',
                'action_required': 'practice'
            },
            {
                'title': 'Open Item: Enter',
                'message': 'Select an item with J/K, then press Enter to open it. No mouse needed!',
                'target_element': '.ticket-row',
                'position': 'bottom'
            },
            {
                'title': 'Assign: A',
                'message': 'Press A to open the assignment dialog. Type a name, press Enter. Lightning fast!',
                'target_element': '.assign-column',
                'position': 'bottom'
            },
            {
                'title': 'Resolve: R',
                'message': 'Press R to mark as resolved. For simple issues, this saves 5 clicks!',
                'target_element': '.status-column',
                'position': 'bottom'
            },
            {
                'title': 'Add Note: N',
                'message': 'Press N to quickly add a comment or note. Great for documenting actions.',
                'target_element': '.notes-column',
                'position': 'left'
            },
            {
                'title': 'Search: /',
                'message': 'Press / to jump to search box. Type your query, press Enter. No mouse clicking!',
                'target_element': '.search-box',
                'position': 'bottom'
            },
            {
                'title': 'Close Dialog: Esc',
                'message': 'Press Escape to close any dialog or modal. Much faster than clicking X.',
                'target_element': '.modal-dialog',
                'position': 'center'
            },
            {
                'title': 'Help: ?',
                'message': 'Forgot a shortcut? Press ? anytime to see the complete list. This help is always available!',
                'target_element': '#help-shortcut-hint',
                'position': 'top'
            },
            {
                'title': 'Practice Makes Perfect',
                'message': 'Start with J/K/Enter today. Add one new shortcut each day. In a week, you\'ll be a keyboard ninja! ⌨️',
                'target_element': '.shortcuts-practice',
                'position': 'center'
            }
        ]
    }
}

# Learning path recommendations
LEARNING_PATHS = {
    'default': [
        'welcome',
        'team_dashboard',
        'priority_alerts',
        'quick_actions',
        'smart_assignment',
        'saved_views',
        'approval_workflows',
        'timelines',
        'shift_tracker',
        'shortcuts'
    ],
    'beginner': [
        'welcome',
        'team_dashboard',
        'priority_alerts',
        'saved_views',
        'timelines'
    ],
    'intermediate': [
        'quick_actions',
        'smart_assignment',
        'approval_workflows',
        'shift_tracker'
    ],
    'advanced': [
        'shortcuts'
    ]
}
