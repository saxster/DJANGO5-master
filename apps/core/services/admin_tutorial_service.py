"""
Admin Tutorial Service - Interactive Walkthroughs

Creates interactive step-by-step tutorials to teach administrators
how to use powerful features effectively.

Following .claude/rules.md:
- Rule #8: View methods <30 lines (delegate to services)
- Rule #11: Specific exception handling
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from apps.core.services.base_service import BaseService


@dataclass
class TutorialStep:
    """Single step in a tutorial"""
    target_element: str
    title: str
    message: str
    action: Optional[str] = None
    position: str = 'bottom'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'target_element': self.target_element,
            'title': self.title,
            'message': self.message,
            'action': self.action,
            'position': self.position
        }


@dataclass
class Tutorial:
    """Complete tutorial definition"""
    id: str
    title: str
    description: str
    steps: List[TutorialStep]
    estimated_time: str = '2 minutes'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'estimated_time': self.estimated_time,
            'steps': [step.to_dict() for step in self.steps]
        }


class AdminTutorialService(BaseService):
    """Create and manage interactive walkthroughs"""
    
    # Define all tutorials
    TUTORIALS = {
        'welcome': Tutorial(
            id='welcome',
            title='Welcome to Your Admin Panel',
            description='A 2-minute tour of the most useful features',
            estimated_time='2 minutes',
            steps=[
                TutorialStep(
                    target_element='#team-dashboard-link',
                    title='1. Your Command Center',
                    message='This is the Team Dashboard. Click here to see all your tickets, incidents, and alerts in one place. No more switching between pages!',
                    position='right'
                ),
                TutorialStep(
                    target_element='.priority-badge',
                    title='2. Priority Alerts',
                    message='These colored badges (🔴🟠🟢) tell you which items need attention first. Red = urgent, Orange = soon, Green = on track.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.quick-action-btn',
                    title='3. Quick Actions',
                    message='Click ⚡ for one-click automated responses. The computer does most of the work for you!',
                    position='left'
                ),
                TutorialStep(
                    target_element='#help-toggle-btn',
                    title='4. Get Help Anytime',
                    message='Click this ? button anytime you need help. It knows what page you\'re on and shows relevant tips.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='#save-view-btn',
                    title='5. Save Your Favorite Views',
                    message='Save any filtered view to access it quickly tomorrow. You can even get daily email reports!',
                    position='bottom'
                )
            ]
        ),
        
        'quick_actions_deep_dive': Tutorial(
            id='quick_actions_deep_dive',
            title='Master Quick Actions',
            description='Learn to handle incidents 63% faster',
            estimated_time='3 minutes',
            steps=[
                TutorialStep(
                    target_element='.quick-action-list',
                    title='What Are Quick Actions?',
                    message='Quick Actions are pre-built automated responses for common issues. They save you time by doing repetitive tasks automatically.',
                    position='top'
                ),
                TutorialStep(
                    target_element='.quick-action-card:first-child',
                    title='Example: Camera Offline',
                    message='This Quick Action will: 1) Ping the camera, 2) Assign to tech team, 3) Create troubleshooting checklist. All in 1 click!',
                    position='right'
                ),
                TutorialStep(
                    target_element='.apply-quick-action-btn',
                    title='Apply a Quick Action',
                    message='Just click this button to apply the action. The system will handle everything automatically and notify relevant people.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.quick-action-history',
                    title='Track What Happened',
                    message='Every Quick Action is logged here. You can see exactly what was done and when.',
                    position='left'
                )
            ]
        ),
        
        'smart_assignment_tutorial': Tutorial(
            id='smart_assignment_tutorial',
            title='Smart Assignment Guide',
            description='Let AI suggest the best person for each task',
            estimated_time='2 minutes',
            steps=[
                TutorialStep(
                    target_element='.assignment-suggestions',
                    title='AI-Powered Suggestions',
                    message='The system analyzes skills, workload, location, and past performance to suggest the best person for this task.',
                    position='top'
                ),
                TutorialStep(
                    target_element='.suggestion-card:first-child',
                    title='Why This Person?',
                    message='Each suggestion shows WHY they\'re recommended. This helps you make informed decisions.',
                    position='right'
                ),
                TutorialStep(
                    target_element='.confidence-score',
                    title='Confidence Score',
                    message='The score (85%) shows how confident the AI is. Higher score = better match.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.assign-btn',
                    title='Assign with 1 Click',
                    message='Click here to assign to the suggested person. Or choose a different suggestion below.',
                    position='left'
                )
            ]
        ),
        
        'saved_views_tutorial': Tutorial(
            id='saved_views_tutorial',
            title='Save Your Favorite Views',
            description='Stop rebuilding filters - save them instead!',
            estimated_time='2 minutes',
            steps=[
                TutorialStep(
                    target_element='.filter-sidebar',
                    title='Start with Filters',
                    message='First, set up your filters exactly how you want them. Filter by status, priority, assignee, etc.',
                    position='right'
                ),
                TutorialStep(
                    target_element='#save-view-btn',
                    title='Save the View',
                    message='Once your filters are perfect, click here to save this view. Give it a memorable name.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.saved-views-dropdown',
                    title='Access Saved Views',
                    message='Your saved views appear here. Click any one to instantly apply those filters.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.email-report-toggle',
                    title='Get Daily Email Reports',
                    message='Turn this on to receive a daily email with this exact view. Great for monitoring specific issues!',
                    position='left'
                )
            ]
        ),
        
        'keyboard_shortcuts_tutorial': Tutorial(
            id='keyboard_shortcuts_tutorial',
            title='Work Faster with Keyboard Shortcuts',
            description='Power users are 30% faster with shortcuts',
            estimated_time='3 minutes',
            steps=[
                TutorialStep(
                    target_element='.ticket-row:first-child',
                    title='Navigate with J/K',
                    message='Press J to move down, K to move up. Just like Gmail!',
                    position='right'
                ),
                TutorialStep(
                    target_element='.assign-column',
                    title='Press A to Assign',
                    message='While on any ticket, press A to open the assignment dialog. No mouse needed!',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='.status-column',
                    title='Press R to Resolve',
                    message='Press R to quickly mark as resolved. Press C to close. Press N to add a note.',
                    position='bottom'
                ),
                TutorialStep(
                    target_element='#help-shortcut-hint',
                    title='Press ? for All Shortcuts',
                    message='Anytime you forget, press ? to see the complete list of shortcuts.',
                    position='top'
                )
            ]
        )
    }
    
    @staticmethod
    def get_tutorial(tutorial_id: str) -> Optional[Dict]:
        """
        Get tutorial by ID.
        
        Args:
            tutorial_id: Unique tutorial identifier
            
        Returns:
            Tutorial dictionary or None if not found
        """
        tutorial = AdminTutorialService.TUTORIALS.get(tutorial_id)
        return tutorial.to_dict() if tutorial else None
    
    @staticmethod
    def list_tutorials() -> List[Dict]:
        """
        List all available tutorials.
        
        Returns:
            List of tutorial summaries
        """
        return [
            {
                'id': tutorial.id,
                'title': tutorial.title,
                'description': tutorial.description,
                'estimated_time': tutorial.estimated_time
            }
            for tutorial in AdminTutorialService.TUTORIALS.values()
        ]
    
    @staticmethod
    def get_recommended_tutorials(user) -> List[Dict]:
        """
        Get tutorials recommended for user based on their experience.
        
        Args:
            user: Administrator user object
            
        Returns:
            List of recommended tutorials
        """
        from apps.core.models.admin_mentor import AdminMentorSession
        
        try:
            session = AdminMentorSession.objects.filter(
                admin_user=user
            ).order_by('-session_start').first()
            
            if not session:
                # New user - recommend welcome tutorial
                return [
                    AdminTutorialService.get_tutorial('welcome'),
                    AdminTutorialService.get_tutorial('keyboard_shortcuts_tutorial')
                ]
            
            # Recommend based on unused features
            recommendations = []
            
            if 'quick_actions' not in session.features_used:
                recommendations.append(
                    AdminTutorialService.get_tutorial('quick_actions_deep_dive')
                )
            
            if 'smart_assignment' not in session.features_used:
                recommendations.append(
                    AdminTutorialService.get_tutorial('smart_assignment_tutorial')
                )
            
            if 'saved_views' not in session.features_used:
                recommendations.append(
                    AdminTutorialService.get_tutorial('saved_views_tutorial')
                )
            
            if session.shortcuts_used < 5:
                recommendations.append(
                    AdminTutorialService.get_tutorial('keyboard_shortcuts_tutorial')
                )
            
            return recommendations[:3]
            
        except Exception as e:
            from apps.core.services.base_service import logger
            logger.error(f"Error getting recommended tutorials: {e}", exc_info=True)
            return [AdminTutorialService.get_tutorial('welcome')]
