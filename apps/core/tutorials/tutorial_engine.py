"""
Interactive Tutorial Engine
===========================

Provides step-by-step interactive walkthroughs for all admin features.

Features:
- 10+ interactive tutorials
- Progress tracking
- Achievement awards
- Personalized recommendations

Created: November 7, 2025
"""

from django.utils import timezone
from datetime import timedelta
from apps.core.models import TutorialProgress, UserAchievement
from .tutorial_content import TUTORIALS


class TutorialEngine:
    """Interactive tutorial system with step-by-step walkthroughs"""
    
    def __init__(self, tutorial_id, user):
        self.tutorial_id = tutorial_id
        self.user = user
        self.current_step = 0
        self.completed = False
        self.started_at = None
        self.completed_at = None
        self.tutorial = TUTORIALS.get(tutorial_id)
        
        if not self.tutorial:
            raise ValueError(f"Tutorial '{tutorial_id}' not found")
    
    def start(self):
        """Start the tutorial"""
        self.started_at = timezone.now()
        
        # Track in database
        progress, created = TutorialProgress.objects.get_or_create(
            user=self.user,
            tutorial_id=self.tutorial_id,
            defaults={
                'status': 'STARTED',
                'started_at': self.started_at
            }
        )
        
        if not created:
            # Resume existing tutorial
            progress.status = 'IN_PROGRESS'
            progress.save()
        
        return self.get_step(0)
    
    def get_step(self, step_index):
        """Get tutorial step details"""
        if step_index >= len(self.tutorial['steps']):
            return self.complete()
        
        step = self.tutorial['steps'][step_index]
        
        return {
            'tutorial_id': self.tutorial_id,
            'tutorial_title': self.tutorial['title'],
            'step_index': step_index,
            'total_steps': len(self.tutorial['steps']),
            'progress_pct': int((step_index / len(self.tutorial['steps'])) * 100),
            'step_title': step['title'],
            'step_message': step['message'],
            'target_element': step.get('target_element'),
            'highlight_type': step.get('highlight_type', 'pulse'),
            'position': step.get('position', 'bottom'),
            'action_required': step.get('action_required'),
            'next_button_text': step.get('next_button', 'Next →'),
            'skip_enabled': step.get('skip_enabled', True),
            'show_prev': step_index > 0
        }
    
    def next_step(self):
        """Move to next step"""
        self.current_step += 1
        
        # Update progress in database
        progress = TutorialProgress.objects.get(
            user=self.user,
            tutorial_id=self.tutorial_id
        )
        
        if self.current_step not in progress.steps_completed:
            progress.steps_completed.append(self.current_step - 1)
            progress.save()
        
        return self.get_step(self.current_step)
    
    def previous_step(self):
        """Move to previous step"""
        if self.current_step > 0:
            self.current_step -= 1
        
        return self.get_step(self.current_step)
    
    def skip(self):
        """Skip the tutorial"""
        progress = TutorialProgress.objects.get(
            user=self.user,
            tutorial_id=self.tutorial_id
        )
        progress.status = 'SKIPPED'
        progress.save()
        
        return {
            'skipped': True,
            'tutorial_id': self.tutorial_id
        }
    
    def complete(self):
        """Complete the tutorial"""
        self.completed = True
        self.completed_at = timezone.now()
        
        # Update database
        progress = TutorialProgress.objects.get(
            user=self.user,
            tutorial_id=self.tutorial_id
        )
        progress.status = 'COMPLETED'
        progress.completed_at = self.completed_at
        progress.time_spent_seconds = int((self.completed_at - progress.started_at).total_seconds())
        progress.save()
        
        # Award achievement
        achievement_data = self.award_achievement()
        
        # Get next recommended tutorial
        next_tutorial = self.get_next_tutorial()
        
        return {
            'completed': True,
            'tutorial_id': self.tutorial_id,
            'tutorial_title': self.tutorial['title'],
            'time_spent': progress.time_spent_seconds,
            'achievement': achievement_data,
            'next_recommended': next_tutorial,
            'congratulations_message': f"🎉 Congratulations! You completed '{self.tutorial['title']}' in {progress.time_spent_seconds // 60} minutes!"
        }
    
    def award_achievement(self):
        """Award achievement for completing tutorial"""
        achievement_id = f'tutorial_{self.tutorial_id}'
        
        achievement, created = UserAchievement.objects.get_or_create(
            user=self.user,
            achievement_id=achievement_id,
            defaults={
                'achievement_type': 'TUTORIAL_COMPLETION',
                'title': f"Completed: {self.tutorial['title']}",
                'description': f"Mastered {self.tutorial['title']}",
                'icon': '🎓',
                'points': 20,
                'earned_at': timezone.now()
            }
        )
        
        if created:
            return {
                'unlocked': True,
                'title': achievement.title,
                'icon': achievement.icon,
                'points': achievement.points
            }
        
        return {'unlocked': False}
    
    def get_next_tutorial(self):
        """Recommend next tutorial based on learning path"""
        completed_tutorials = TutorialProgress.objects.filter(
            user=self.user,
            status='COMPLETED'
        ).values_list('tutorial_id', flat=True)
        
        # Learning path order (beginner to advanced)
        learning_path = [
            'welcome',
            'team_dashboard',
            'priority_alerts',
            'quick_actions',
            'smart_assignment',
            'saved_views',
            'timelines',
            'approval_workflows',
            'shift_tracker',
            'shortcuts_bootcamp'
        ]
        
        for tutorial_id in learning_path:
            if tutorial_id not in completed_tutorials and tutorial_id in TUTORIALS:
                tutorial = TUTORIALS[tutorial_id]
                return {
                    'id': tutorial_id,
                    'title': tutorial['title'],
                    'description': tutorial['description'],
                    'duration': tutorial['duration'],
                    'difficulty': tutorial['difficulty']
                }
        
        return None  # All tutorials completed!
    
    @staticmethod
    def get_user_progress(user):
        """Get user's overall tutorial progress"""
        total_tutorials = len(TUTORIALS)
        completed = TutorialProgress.objects.filter(
            user=user,
            status='COMPLETED'
        ).count()
        
        in_progress = TutorialProgress.objects.filter(
            user=user,
            status='IN_PROGRESS'
        ).count()
        
        return {
            'total_tutorials': total_tutorials,
            'completed': completed,
            'in_progress': in_progress,
            'not_started': total_tutorials - completed - in_progress,
            'completion_pct': int((completed / total_tutorials) * 100) if total_tutorials > 0 else 0
        }
    
    @staticmethod
    def get_recommended_tutorial(user):
        """Get the single best next tutorial for this user"""
        completed = TutorialProgress.objects.filter(
            user=user,
            status='COMPLETED'
        ).values_list('tutorial_id', flat=True)
        
        # Beginner path
        if 'welcome' not in completed:
            return 'welcome'
        
        if 'team_dashboard' not in completed:
            return 'team_dashboard'
        
        if 'priority_alerts' not in completed:
            return 'priority_alerts'
        
        # Intermediate path
        if 'quick_actions' not in completed:
            return 'quick_actions'
        
        if 'smart_assignment' not in completed:
            return 'smart_assignment'
        
        # Advanced path
        if 'saved_views' not in completed:
            return 'saved_views'
        
        if 'timelines' not in completed:
            return 'timelines'
        
        # Power user
        if 'shortcuts_bootcamp' not in completed:
            return 'shortcuts_bootcamp'
        
        return None  # All done!
