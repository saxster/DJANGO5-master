"""
Management command to generate recommendations for users
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

from apps.core.recommendation_engine import RecommendationEngine
from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, NavigationRecommendation
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate recommendations for users based on their behavior patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Generate recommendations for a specific user ID',
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Generate recommendations for all active users',
        )
        parser.add_argument(
            '--active-days',
            type=int,
            default=30,
            help='Consider users active within this many days (default: 30)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of recommendations per user (default: 10)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regenerate recommendations even if recent ones exist',
        )
        parser.add_argument(
            '--navigation-only',
            action='store_true',
            help='Generate only navigation recommendations',
        )
        parser.add_argument(
            '--content-only',
            action='store_true',
            help='Generate only content recommendations',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options.get('verbose', False)
        
        try:
            engine = RecommendationEngine()
            
            if options['navigation_only']:
                self._generate_navigation_recommendations(engine, options)
            elif options['content_only']:
                self._generate_content_recommendations(engine, options)
            else:
                # Generate both types
                self._generate_content_recommendations(engine, options)
                self._generate_navigation_recommendations(engine, options)
            
            self.stdout.write(
                self.style.SUCCESS('Successfully generated recommendations')
            )
            
        except Exception as e:
            logger.error(f"Error in generate_recommendations command: {str(e)}")
            raise CommandError(f'Error generating recommendations: {str(e)}')

    def _generate_content_recommendations(self, engine, options):
        """Generate content recommendations"""
        users = self._get_target_users(options)
        
        if not users:
            self.stdout.write(self.style.WARNING('No users found to generate recommendations for'))
            return
        
        total_users = len(users)
        generated_count = 0
        
        self.stdout.write(f'Generating content recommendations for {total_users} users...')
        
        for i, user in enumerate(users, 1):
            try:
                if self.verbose:
                    self.stdout.write(f'Processing user {i}/{total_users}: {user.username}')
                
                # Check if recent recommendations exist
                if not options['force']:
                    recent_cutoff = timezone.now() - timedelta(hours=24)
                    recent_recs = ContentRecommendation.objects.filter(
                        user=user,
                        created_at__gte=recent_cutoff
                    ).exists()
                    
                    if recent_recs:
                        if self.verbose:
                            self.stdout.write(f'  Skipping {user.username} - recent recommendations exist')
                        continue
                
                # Generate recommendations
                recommendations = engine.generate_user_recommendations(
                    user, 
                    limit=options['limit']
                )
                
                if recommendations:
                    # Save recommendations to database
                    saved_count = 0
                    for rec in recommendations:
                        try:
                            # Check if similar recommendation already exists
                            existing = ContentRecommendation.objects.filter(
                                user=user,
                                content_url=rec.content_url,
                                is_active=True
                            ).exists()
                            
                            if not existing:
                                rec.save()
                                saved_count += 1
                        except Exception as e:
                            logger.error(f"Error saving recommendation for user {user.id}: {str(e)}")
                    
                    if self.verbose:
                        self.stdout.write(f'  Generated {saved_count} recommendations for {user.username}')
                    
                    generated_count += saved_count
                else:
                    if self.verbose:
                        self.stdout.write(f'  No recommendations generated for {user.username}')
                
            except Exception as e:
                logger.error(f"Error processing user {user.id}: {str(e)}")
                if self.verbose:
                    self.stdout.write(f'  Error processing {user.username}: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Generated {generated_count} content recommendations total')
        )

    def _generate_navigation_recommendations(self, engine, options):
        """Generate navigation recommendations"""
        self.stdout.write('Generating navigation recommendations...')
        
        try:
            # Generate global navigation recommendations
            nav_recommendations = engine.generate_navigation_recommendations()
            
            saved_count = 0
            for rec in nav_recommendations:
                try:
                    # Check if similar recommendation already exists
                    existing = NavigationRecommendation.objects.filter(
                        recommendation_type=rec.recommendation_type,
                        target_page=rec.target_page,
                        status__in=['pending', 'approved']
                    ).exists()
                    
                    if not existing or options['force']:
                        if existing and options['force']:
                            # Update existing recommendation
                            NavigationRecommendation.objects.filter(
                                recommendation_type=rec.recommendation_type,
                                target_page=rec.target_page,
                                status__in=['pending', 'approved']
                            ).update(status='rejected')  # Mark old ones as rejected
                        
                        rec.save()
                        saved_count += 1
                        
                        if self.verbose:
                            self.stdout.write(f'  Generated: {rec.title}')
                
                except Exception as e:
                    logger.error(f"Error saving navigation recommendation: {str(e)}")
            
            # Generate page-specific recommendations for popular pages
            from apps.core.models.heatmap import HeatmapSession
            popular_pages = HeatmapSession.objects.values('page_url').annotate(
                visit_count=models.Count('id')
            ).filter(visit_count__gte=10).order_by('-visit_count')[:10]
            
            for page_data in popular_pages:
                page_url = page_data['page_url']
                try:
                    page_recommendations = engine.generate_navigation_recommendations(page_url)
                    
                    for rec in page_recommendations:
                        existing = NavigationRecommendation.objects.filter(
                            recommendation_type=rec.recommendation_type,
                            target_page=rec.target_page,
                            status__in=['pending', 'approved']
                        ).exists()
                        
                        if not existing or options['force']:
                            if existing and options['force']:
                                NavigationRecommendation.objects.filter(
                                    recommendation_type=rec.recommendation_type,
                                    target_page=rec.target_page,
                                    status__in=['pending', 'approved']
                                ).update(status='rejected')
                            
                            rec.save()
                            saved_count += 1
                            
                            if self.verbose:
                                self.stdout.write(f'  Generated for {page_url}: {rec.title}')
                
                except Exception as e:
                    logger.error(f"Error generating recommendations for page {page_url}: {str(e)}")
            
            self.stdout.write(
                self.style.SUCCESS(f'Generated {saved_count} navigation recommendations total')
            )
            
        except Exception as e:
            logger.error(f"Error generating navigation recommendations: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Error generating navigation recommendations: {str(e)}')
            )

    def _get_target_users(self, options):
        """Get list of users to generate recommendations for"""
        if options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
                return [user]
            except User.DoesNotExist:
                raise CommandError(f'User with ID {options["user_id"]} does not exist')
        
        elif options['all_users']:
            # Get all users with recent activity
            cutoff_date = timezone.now() - timedelta(days=options['active_days'])
            
            from apps.core.models.heatmap import HeatmapSession
            active_users = User.objects.filter(
                heatmap_sessions__start_time__gte=cutoff_date
            ).distinct()
            
            return list(active_users)
        
        else:
            raise CommandError(
                'Please specify either --user-id or --all-users'
            )

    def _build_user_profiles(self, options):
        """Build user behavior profiles for users who don't have them"""
        users = self._get_target_users(options)
        
        self.stdout.write('Building user behavior profiles...')
        
        built_count = 0
        for user in users:
            try:
                profile, created = UserBehaviorProfile.objects.get_or_create(user=user)
                if created or options['force']:
                    engine = RecommendationEngine()
                    engine.behavior_analyzer.build_user_profile(user)
                    built_count += 1
                    
                    if self.verbose:
                        self.stdout.write(f'  Built profile for {user.username}')
            
            except Exception as e:
                logger.error(f"Error building profile for user {user.id}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Built {built_count} user behavior profiles')
        )