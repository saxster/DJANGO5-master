"""
Interactive Tutorial Engine - Complete Walkthrough System

Creates interactive step-by-step tutorials with progress tracking,
achievements, and completion certificates.

Following .claude/rules.md:
- Rule #8: Service methods <50 lines
- Rule #11: Specific exception handling
- Rule #14: All network calls include timeout
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.services.base_service import BaseService, logger


class TutorialEngine(BaseService):
    """Interactive tutorial system with step-by-step walkthroughs"""
    
    def __init__(self, tutorial_id: str, user):
        """
        Initialize tutorial engine.
        
        Args:
            tutorial_id: Unique tutorial identifier
            user: User taking the tutorial
        """
        self.tutorial_id = tutorial_id
        self.user = user
        self.current_step = 0
        self.completed = False
        self.started_at = None
        self.completed_at = None
        self.steps_completed = []
    
    def start(self) -> Dict[str, Any]:
        """
        Start the tutorial.
        
        Returns:
            First step data
        """
        from apps.core.tutorials.content import TUTORIALS
        from apps.core.models.tutorial_progress import TutorialProgress
        
        if self.tutorial_id not in TUTORIALS:
            raise ValueError(f"Tutorial not found: {self.tutorial_id}")
        
        self.started_at = timezone.now()
        
        try:
            with transaction.atomic():
                # Create or update progress record
                progress, created = TutorialProgress.objects.get_or_create(
                    user=self.user,
                    tutorial_id=self.tutorial_id,
                    defaults={
                        'status': 'STARTED',
                        'started_at': self.started_at,
                        'steps_completed': []
                    }
                )
                
                if not created:
                    # Resume tutorial
                    progress.status = 'IN_PROGRESS'
                    progress.save()
                    self.steps_completed = progress.steps_completed or []
                    self.current_step = len(self.steps_completed)
                
                logger.info(
                    f"Tutorial started: {self.tutorial_id} by user {self.user.id}"
                )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error starting tutorial: {e}", exc_info=True)
            raise
        
        return self.get_step(0)
    
    def get_step(self, step_index: int) -> Dict[str, Any]:
        """
        Get tutorial step details.
        
        Args:
            step_index: Zero-based step index
            
        Returns:
            Step data with metadata
        """
        from apps.core.tutorials.content import TUTORIALS
        
        tutorial = TUTORIALS[self.tutorial_id]
        
        if step_index >= len(tutorial['steps']):
            return self.complete()
        
        step = tutorial['steps'][step_index]
        total_steps = len(tutorial['steps'])
        
        return {
            'tutorial_id': self.tutorial_id,
            'tutorial_title': tutorial['title'],
            'step_index': step_index,
            'total_steps': total_steps,
            'progress_percent': int((step_index / total_steps) * 100),
            'step_title': step['title'],
            'step_message': step['message'],
            'target_element': step['target_element'],
            'highlight_type': step.get('highlight_type', 'pulse'),
            'position': step.get('position', 'bottom'),
            'action_required': step.get('action_required'),
            'next_button_text': step.get('next_button', 'Next →'),
            'skip_enabled': step.get('skip_enabled', True),
            'show_prev': step_index > 0,
            'estimated_time_remaining': self._estimate_time_remaining(
                step_index, total_steps
            )
        }
    
    def next_step(self, current_index: int) -> Dict[str, Any]:
        """
        Move to next step.
        
        Args:
            current_index: Current step index
            
        Returns:
            Next step data
        """
        from apps.core.models.tutorial_progress import TutorialProgress
        
        # Record completion of current step
        if current_index not in self.steps_completed:
            self.steps_completed.append(current_index)
        
        try:
            progress = TutorialProgress.objects.get(
                user=self.user,
                tutorial_id=self.tutorial_id
            )
            progress.steps_completed = self.steps_completed
            progress.status = 'IN_PROGRESS'
            progress.save()
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error updating tutorial progress: {e}", exc_info=True)
        
        return self.get_step(current_index + 1)
    
    def previous_step(self, current_index: int) -> Dict[str, Any]:
        """
        Move to previous step.
        
        Args:
            current_index: Current step index
            
        Returns:
            Previous step data
        """
        if current_index <= 0:
            return self.get_step(0)
        
        return self.get_step(current_index - 1)
    
    def complete(self) -> Dict[str, Any]:
        """
        Complete the tutorial.
        
        Returns:
            Completion data with achievement and recommendations
        """
        from apps.core.models.tutorial_progress import TutorialProgress
        from apps.core.tutorials.content import TUTORIALS
        
        self.completed = True
        self.completed_at = timezone.now()
        
        time_spent_seconds = 0
        if self.started_at:
            time_spent_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )
        
        try:
            with transaction.atomic():
                # Update progress
                progress = TutorialProgress.objects.get(
                    user=self.user,
                    tutorial_id=self.tutorial_id
                )
                progress.status = 'COMPLETED'
                progress.completed_at = self.completed_at
                progress.time_spent_seconds = time_spent_seconds
                progress.save()
                
                # Award achievement
                achievement = self._award_achievement()
                
                # Generate certificate
                certificate = self._generate_certificate()
                
                # Get next recommendation
                next_tutorial = self._get_next_tutorial()
                
                logger.info(
                    f"Tutorial completed: {self.tutorial_id} by user "
                    f"{self.user.id} in {time_spent_seconds}s"
                )
                
                return {
                    'completed': True,
                    'tutorial_id': self.tutorial_id,
                    'tutorial_title': TUTORIALS[self.tutorial_id]['title'],
                    'time_spent_seconds': time_spent_seconds,
                    'time_spent_display': self._format_duration(time_spent_seconds),
                    'achievement': achievement,
                    'certificate_url': certificate,
                    'next_recommended': next_tutorial,
                    'completion_message': self._get_completion_message()
                }
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error completing tutorial: {e}", exc_info=True)
            raise
    
    def skip(self) -> Dict[str, Any]:
        """
        Skip the tutorial.
        
        Returns:
            Skip confirmation
        """
        from apps.core.models.tutorial_progress import TutorialProgress
        
        try:
            progress = TutorialProgress.objects.get(
                user=self.user,
                tutorial_id=self.tutorial_id
            )
            progress.status = 'SKIPPED'
            progress.save()
            
            logger.info(
                f"Tutorial skipped: {self.tutorial_id} by user {self.user.id}"
            )
            
            return {
                'skipped': True,
                'tutorial_id': self.tutorial_id,
                'next_recommended': self._get_next_tutorial()
            }
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error skipping tutorial: {e}", exc_info=True)
            raise
    
    def _award_achievement(self) -> Dict[str, Any]:
        """Award achievement for completing tutorial"""
        from apps.core.models.tutorial_achievement import UserAchievement
        from apps.core.tutorials.content import TUTORIALS
        
        tutorial = TUTORIALS[self.tutorial_id]
        achievement_id = f'tutorial_{self.tutorial_id}'
        points = tutorial.get('points', 20)
        
        try:
            achievement, created = UserAchievement.objects.get_or_create(
                user=self.user,
                achievement_id=achievement_id,
                defaults={
                    'title': f'Completed: {tutorial["title"]}',
                    'description': tutorial['description'],
                    'earned_at': timezone.now(),
                    'points': points,
                    'badge_icon': tutorial.get('badge_icon', '🎓')
                }
            )
            
            if created:
                # Check for combo achievements
                self._check_combo_achievements()
            
            return {
                'id': achievement_id,
                'title': achievement.title,
                'points': points,
                'badge_icon': achievement.badge_icon,
                'newly_earned': created
            }
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error awarding achievement: {e}", exc_info=True)
            return {}
    
    def _check_combo_achievements(self):
        """Check and award combo achievements"""
        from apps.core.models.tutorial_achievement import UserAchievement
        
        completed_count = UserAchievement.objects.filter(
            user=self.user,
            achievement_id__startswith='tutorial_'
        ).count()
        
        combo_achievements = {
            3: ('quick_learner', 'Quick Learner 🚀', 50),
            5: ('dedicated_student', 'Dedicated Student 📚', 100),
            10: ('tutorial_master', 'Tutorial Master 🏆', 200)
        }
        
        for count, (aid, title, points) in combo_achievements.items():
            if completed_count >= count:
                UserAchievement.objects.get_or_create(
                    user=self.user,
                    achievement_id=aid,
                    defaults={
                        'title': title,
                        'description': f'Completed {count} tutorials',
                        'earned_at': timezone.now(),
                        'points': points,
                        'badge_icon': '🏆'
                    }
                )
    
    def _generate_certificate(self) -> str:
        """Generate completion certificate URL"""
        from apps.core.tutorials.content import TUTORIALS
        
        tutorial = TUTORIALS[self.tutorial_id]
        
        # Generate certificate ID
        cert_id = f"{self.user.id}_{self.tutorial_id}_{int(timezone.now().timestamp())}"
        
        # Cache certificate data
        cert_data = {
            'user_name': self.user.get_full_name() or self.user.username,
            'tutorial_title': tutorial['title'],
            'completed_at': self.completed_at.isoformat(),
            'certificate_id': cert_id
        }
        
        cache.set(
            f'tutorial_cert_{cert_id}',
            cert_data,
            timeout=86400 * 365  # 1 year
        )
        
        return f'/admin/tutorials/certificate/{cert_id}/'
    
    def _get_next_tutorial(self) -> Optional[Dict[str, str]]:
        """Recommend next tutorial based on learning path"""
        from apps.core.models.tutorial_progress import TutorialProgress
        from apps.core.tutorials.content import TUTORIALS, LEARNING_PATHS
        
        # Get completed tutorials
        completed = TutorialProgress.objects.filter(
            user=self.user,
            status='COMPLETED'
        ).values_list('tutorial_id', flat=True)
        
        # Find appropriate learning path
        path = LEARNING_PATHS.get('default', [])
        
        # Find next uncompleted tutorial in path
        for tutorial_id in path:
            if tutorial_id not in completed and tutorial_id in TUTORIALS:
                tutorial = TUTORIALS[tutorial_id]
                return {
                    'id': tutorial_id,
                    'title': tutorial['title'],
                    'description': tutorial['description'],
                    'duration': tutorial['duration'],
                    'difficulty': tutorial.get('difficulty', 'BEGINNER')
                }
        
        return None  # All completed!
    
    def _estimate_time_remaining(
        self, current_step: int, total_steps: int
    ) -> str:
        """Estimate time remaining in tutorial"""
        from apps.core.tutorials.content import TUTORIALS
        
        tutorial = TUTORIALS[self.tutorial_id]
        total_minutes = self._parse_duration(tutorial.get('duration', '5 minutes'))
        
        remaining_steps = total_steps - current_step
        remaining_minutes = int((remaining_steps / total_steps) * total_minutes)
        
        if remaining_minutes < 1:
            return 'Less than 1 minute'
        elif remaining_minutes == 1:
            return '1 minute'
        else:
            return f'{remaining_minutes} minutes'
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to minutes"""
        import re
        match = re.search(r'(\d+)', duration_str)
        return int(match.group(1)) if match else 5
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f'{seconds} seconds'
        
        minutes = seconds // 60
        if minutes < 60:
            return f'{minutes} minute{"s" if minutes != 1 else ""}'
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f'{hours} hour{"s" if hours != 1 else ""}'
        
        return f'{hours}h {remaining_minutes}m'
    
    def _get_completion_message(self) -> str:
        """Get personalized completion message"""
        from apps.core.tutorials.content import TUTORIALS
        
        tutorial = TUTORIALS[self.tutorial_id]
        
        messages = {
            'welcome': "Great job! You're ready to use your admin panel effectively. 🎉",
            'team_dashboard': "You've mastered the command center! Time to work faster. 🚀",
            'priority_alerts': "You'll never miss urgent issues again! 🎯",
            'quick_actions': "You can now handle incidents 63% faster! ⚡",
            'smart_assignment': "AI-powered assignment unlocked! 🤖",
            'saved_views': "You'll save hours every week! ⏱️",
            'approval_workflows': "Approval automation mastered! ✅",
            'timelines': "Visual timelines make everything clearer! 📊",
            'shift_tracker': "Shift tracking expertise achieved! 📅",
            'shortcuts': "Keyboard ninja status unlocked! ⌨️"
        }
        
        return messages.get(
            self.tutorial_id,
            f"Congratulations on completing {tutorial['title']}! 🎉"
        )
    
    @staticmethod
    def get_user_progress(user) -> Dict[str, Any]:
        """
        Get user's overall tutorial progress.
        
        Args:
            user: User object
            
        Returns:
            Progress statistics
        """
        from apps.core.models.tutorial_progress import TutorialProgress
        from apps.core.models.tutorial_achievement import UserAchievement
        from apps.core.tutorials.content import TUTORIALS
        
        total_tutorials = len(TUTORIALS)
        completed = TutorialProgress.objects.filter(
            user=user,
            status='COMPLETED'
        ).count()
        
        in_progress = TutorialProgress.objects.filter(
            user=user,
            status='IN_PROGRESS'
        ).count()
        
        total_points = UserAchievement.objects.filter(
            user=user
        ).aggregate(total=models.Sum('points'))['total'] or 0
        
        return {
            'total_tutorials': total_tutorials,
            'completed': completed,
            'in_progress': in_progress,
            'completion_percent': int((completed / total_tutorials) * 100),
            'total_points': total_points,
            'achievements_earned': UserAchievement.objects.filter(
                user=user
            ).count()
        }
