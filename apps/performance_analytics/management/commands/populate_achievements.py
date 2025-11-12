"""
Populate Achievement Definitions

Pre-populate achievement templates in database.

Usage:
    python manage.py populate_achievements
    python manage.py populate_achievements --reset

Compliance:
- Rule #11: Specific exception handling
"""

from django.core.management.base import BaseCommand
from apps.performance_analytics.models import Achievement
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


class Command(BaseCommand):
    """Populate achievement definitions."""
    
    help = 'Populate achievement templates in database'
    
    ACHIEVEMENTS = [
        {
            'code': 'on_time_week',
            'name': 'Perfect Week',
            'description': '7 consecutive days 100% on-time',
            'icon': '📅',
            'criteria': {'on_time_rate': 100, 'days': 7},
            'points': 10,
            'rarity': 'common',
            'category': 'attendance'
        },
        {
            'code': 'on_time_month',
            'name': 'Perfect Month',
            'description': '30 consecutive days 100% on-time',
            'icon': '📆',
            'criteria': {'on_time_rate': 100, 'days': 30},
            'points': 50,
            'rarity': 'rare',
            'category': 'attendance'
        },
        {
            'code': 'on_time_quarter',
            'name': 'Perfect Quarter',
            'description': '90 consecutive days 100% on-time',
            'icon': '🏆',
            'criteria': {'on_time_rate': 100, 'days': 90},
            'points': 200,
            'rarity': 'epic',
            'category': 'attendance'
        },
        {
            'code': 'zero_ncns_year',
            'name': 'Year Without NCNS',
            'description': '365 days without a single no-call-no-show',
            'icon': '👑',
            'criteria': {'ncns_count': 0, 'days': 365},
            'points': 500,
            'rarity': 'legendary',
            'category': 'attendance'
        },
        {
            'code': 'patrol_pro',
            'name': 'Patrol Pro',
            'description': '50 tours with 95%+ checkpoint coverage',
            'icon': '🎯',
            'criteria': {'checkpoint_rate': 95, 'tours': 50},
            'points': 75,
            'rarity': 'rare',
            'category': 'performance'
        },
        {
            'code': 'checkpoint_perfectionist',
            'name': 'Checkpoint Perfectionist',
            'description': '100% checkpoint coverage for 30 days',
            'icon': '✨',
            'criteria': {'checkpoint_rate': 100, 'days': 30},
            'points': 100,
            'rarity': 'epic',
            'category': 'performance'
        },
        {
            'code': 'sla_champion',
            'name': 'SLA Champion',
            'description': '95%+ SLA hit rate with 100+ tasks',
            'icon': '⚡',
            'criteria': {'sla_hit_rate': 95, 'tasks': 100},
            'points': 100,
            'rarity': 'epic',
            'category': 'performance'
        },
        {
            'code': 'quality_excellence',
            'name': 'Quality Excellence',
            'description': '90+ quality score with 20+ quality audits',
            'icon': '💎',
            'criteria': {'quality_score': 90, 'audits': 20},
            'points': 75,
            'rarity': 'rare',
            'category': 'quality'
        },
        {
            'code': 'team_player',
            'name': 'Team Player',
            'description': 'Received 10+ kudos in 30 days',
            'icon': '🤝',
            'criteria': {'kudos_received': 10, 'days': 30},
            'points': 50,
            'rarity': 'uncommon',
            'category': 'teamwork'
        },
        {
            'code': 'mentor_master',
            'name': 'Mentor Master',
            'description': 'Gave 20+ kudos and conducted 5+ coaching sessions',
            'icon': '🎓',
            'criteria': {'kudos_given': 20, 'coaching_sessions': 5},
            'points': 100,
            'rarity': 'rare',
            'category': 'leadership'
        },
        {
            'code': 'safety_champion',
            'name': 'Safety Champion',
            'description': '5+ near-miss reports in 30 days (proactive safety)',
            'icon': '🛡️',
            'criteria': {'near_miss_reports': 5, 'days': 30},
            'points': 75,
            'rarity': 'rare',
            'category': 'safety'
        },
        {
            'code': 'incident_detective',
            'name': 'Incident Detective',
            'description': 'Detected 10+ incidents during patrols',
            'icon': '🔍',
            'criteria': {'incidents_detected': 10},
            'points': 50,
            'rarity': 'uncommon',
            'category': 'performance'
        },
        {
            'code': 'documentation_master',
            'name': 'Documentation Master',
            'description': '100% evidence photo rate for 30 days',
            'icon': '📸',
            'criteria': {'evidence_photo_rate': 100, 'days': 30},
            'points': 50,
            'rarity': 'uncommon',
            'category': 'quality'
        },
        {
            'code': 'consistent_performer',
            'name': 'Consistent Performer',
            'description': 'BPI variance < 5 points for 90 days',
            'icon': '📊',
            'criteria': {'bpi_variance': 5, 'days': 90},
            'points': 100,
            'rarity': 'epic',
            'category': 'performance'
        },
        {
            'code': 'century_club',
            'name': 'Century Club',
            'description': '100+ tasks completed with 90%+ SLA',
            'icon': '💯',
            'criteria': {'tasks_completed': 100, 'sla_rate': 90},
            'points': 75,
            'rarity': 'rare',
            'category': 'performance'
        },
    ]
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing achievements and repopulate',
        )
    
    def handle(self, *args, **options):
        """Execute command."""
        try:
            if options['reset']:
                deleted_count, _ = Achievement.objects.all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Deleted {deleted_count} existing achievements"
                    )
                )
            
            created_count = 0
            updated_count = 0
            
            for achievement_data in self.ACHIEVEMENTS:
                achievement, created = Achievement.objects.update_or_create(
                    code=achievement_data['code'],
                    defaults={
                        'name': achievement_data['name'],
                        'description': achievement_data['description'],
                        'icon': achievement_data['icon'],
                        'criteria': achievement_data['criteria'],
                        'points': achievement_data['points'],
                        'rarity': achievement_data['rarity'],
                        'category': achievement_data['category'],
                    }
                )
                
                if created:
                    created_count += 1
                    if options['verbosity'] >= 2:
                        self.stdout.write(
                            f"  Created: {achievement.icon} {achievement.name}"
                        )
                else:
                    updated_count += 1
            
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("ACHIEVEMENTS POPULATED"))
            self.stdout.write("="*60)
            self.stdout.write(f"  Created: {created_count}")
            self.stdout.write(f"  Updated: {updated_count}")
            self.stdout.write(f"  Total: {Achievement.objects.count()}")
            
        except DATABASE_EXCEPTIONS as e:
            raise CommandError(f"Database error: {e}")
        except (ValueError, TypeError) as e:
            raise CommandError(f"Invalid data: {e}")
