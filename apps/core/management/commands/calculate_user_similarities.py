"""
Management command to calculate user similarities for collaborative filtering
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import logging

from apps.core.recommendation_engine import CollaborativeFilteringEngine
from apps.core.models.recommendation import UserBehaviorProfile, UserSimilarity

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate user similarities for collaborative filtering recommendations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Calculate similarities for a specific user ID',
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Calculate similarities for all users with behavior profiles',
        )
        parser.add_argument(
            '--min-sessions',
            type=int,
            default=5,
            help='Minimum sessions required for similarity calculation (default: 5)',
        )
        parser.add_argument(
            '--force-rebuild',
            action='store_true',
            help='Force rebuild all similarity calculations',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing users (default: 100)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
        parser.add_argument(
            '--cleanup-old',
            action='store_true',
            help='Clean up old similarity calculations (older than 30 days)',
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options.get('verbose', False)
        
        try:
            if options['cleanup_old']:
                self._cleanup_old_similarities()
            
            engine = CollaborativeFilteringEngine()
            
            if options['user_id']:
                self._calculate_user_similarity(engine, options['user_id'], options)
            elif options['all_users']:
                self._calculate_all_similarities(engine, options)
            else:
                raise CommandError(
                    'Please specify either --user-id or --all-users'
                )
            
            self.stdout.write(
                self.style.SUCCESS('Successfully calculated user similarities')
            )
            
        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            logger.error(f"Error in calculate_user_similarities command: {str(e)}")
            raise CommandError(f'Error calculating similarities: {str(e)}')

    def _calculate_user_similarity(self, engine, user_id, options):
        """Calculate similarities for a specific user"""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'User with ID {user_id} does not exist')
        
        # Check if user has behavior profile
        profile = UserBehaviorProfile.objects.filter(user=user).first()
        if not profile:
            self.stdout.write(
                self.style.WARNING(f'User {user.username} has no behavior profile. Building one...')
            )
            from apps.core.recommendation_engine import BehaviorAnalyzer
            analyzer = BehaviorAnalyzer()
            analyzer.build_user_profile(user)
            profile = UserBehaviorProfile.objects.get(user=user)
        
        # Check session count
        from apps.core.models.heatmap import HeatmapSession
        session_count = HeatmapSession.objects.filter(user=user).count()
        
        if session_count < options['min_sessions']:
            self.stdout.write(
                self.style.WARNING(
                    f'User {user.username} has only {session_count} sessions. '
                    f'Minimum required: {options["min_sessions"]}'
                )
            )
            return
        
        self.stdout.write(f'Calculating similarities for user: {user.username}')
        
        # Calculate similarities
        engine.calculate_user_similarities(user)
        
        # Get similarity count
        similarity_count = UserSimilarity.objects.filter(
            models.Q(user1=user) | models.Q(user2=user)
        ).count()
        
        self.stdout.write(
            self.style.SUCCESS(f'Calculated {similarity_count} similarities for {user.username}')
        )
        
        if self.verbose:
            # Show top similarities
            top_similarities = UserSimilarity.objects.filter(
                models.Q(user1=user) | models.Q(user2=user)
            ).order_by('-similarity_score')[:5]
            
            self.stdout.write('Top similarities:')
            for sim in top_similarities:
                other_user = sim.user2 if sim.user1 == user else sim.user1
                self.stdout.write(f'  {other_user.username}: {sim.similarity_score:.3f}')

    def _calculate_all_similarities(self, engine, options):
        """Calculate similarities for all eligible users"""
        # Get users with sufficient activity
        from apps.core.models.heatmap import HeatmapSession
        
        eligible_users = User.objects.annotate(
            session_count=Count('heatmap_sessions')
        ).filter(
            session_count__gte=options['min_sessions']
        ).order_by('id')
        
        total_users = eligible_users.count()
        
        if total_users == 0:
            self.stdout.write(
                self.style.WARNING(
                    f'No users found with at least {options["min_sessions"]} sessions'
                )
            )
            return
        
        self.stdout.write(f'Calculating similarities for {total_users} users...')
        
        # Process users in batches
        batch_size = options['batch_size']
        processed_count = 0
        
        for i in range(0, total_users, batch_size):
            batch_users = eligible_users[i:i + batch_size]
            
            self.stdout.write(f'Processing batch {i//batch_size + 1}...')
            
            for user in batch_users:
                try:
                    # Check if user needs profile building
                    profile, created = UserBehaviorProfile.objects.get_or_create(user=user)
                    if created:
                        if self.verbose:
                            self.stdout.write(f'  Building profile for {user.username}')
                        
                        from apps.core.recommendation_engine import BehaviorAnalyzer
                        analyzer = BehaviorAnalyzer()
                        analyzer.build_user_profile(user)
                    
                    # Check if similarities need updating
                    needs_update = options['force_rebuild']
                    
                    if not needs_update:
                        # Check if user has recent similarity calculations
                        recent_cutoff = timezone.now() - timedelta(days=7)
                        recent_similarities = UserSimilarity.objects.filter(
                            models.Q(user1=user) | models.Q(user2=user),
                            calculated_at__gte=recent_cutoff
                        ).exists()
                        
                        needs_update = not recent_similarities
                    
                    if needs_update:
                        if self.verbose:
                            self.stdout.write(f'  Calculating similarities for {user.username}')
                        
                        engine.calculate_user_similarities(user)
                        processed_count += 1
                    else:
                        if self.verbose:
                            self.stdout.write(f'  Skipping {user.username} - recent calculations exist')
                
                except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError) as e:
                    logger.error(f"Error processing user {user.id}: {str(e)}")
                    if self.verbose:
                        self.stdout.write(f'  Error processing {user.username}: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {processed_count} users for similarity calculations')
        )
        
        # Show summary statistics
        total_similarities = UserSimilarity.objects.count()
        avg_similarity = UserSimilarity.objects.aggregate(
            avg=models.Avg('similarity_score')
        )['avg'] or 0
        
        self.stdout.write(f'Total similarities in database: {total_similarities}')
        self.stdout.write(f'Average similarity score: {avg_similarity:.3f}')

    def _cleanup_old_similarities(self):
        """Clean up old similarity calculations"""
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_similarities = UserSimilarity.objects.filter(
            calculated_at__lt=cutoff_date
        )
        
        count = old_similarities.count()
        
        if count > 0:
            self.stdout.write(f'Cleaning up {count} old similarity calculations...')
            old_similarities.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Cleaned up {count} old similarity calculations')
            )
        else:
            self.stdout.write('No old similarity calculations to clean up')

    def _show_similarity_statistics(self):
        """Show similarity statistics"""
        total_similarities = UserSimilarity.objects.count()
        
        if total_similarities == 0:
            self.stdout.write('No similarity data available')
            return
        
        stats = UserSimilarity.objects.aggregate(
            avg_score=models.Avg('similarity_score'),
            max_score=models.Max('similarity_score'),
            min_score=models.Min('similarity_score')
        )
        
        # Get distribution
        high_similarity = UserSimilarity.objects.filter(similarity_score__gte=0.7).count()
        medium_similarity = UserSimilarity.objects.filter(
            similarity_score__gte=0.3, 
            similarity_score__lt=0.7
        ).count()
        low_similarity = UserSimilarity.objects.filter(similarity_score__lt=0.3).count()
        
        self.stdout.write('\nSimilarity Statistics:')
        self.stdout.write(f'Total similarities: {total_similarities}')
        self.stdout.write(f'Average score: {stats["avg_score"]:.3f}')
        self.stdout.write(f'Max score: {stats["max_score"]:.3f}')
        self.stdout.write(f'Min score: {stats["min_score"]:.3f}')
        self.stdout.write('\nDistribution:')
        self.stdout.write(f'High similarity (≥0.7): {high_similarity} ({high_similarity/total_similarities*100:.1f}%)')
        self.stdout.write(f'Medium similarity (0.3-0.7): {medium_similarity} ({medium_similarity/total_similarities*100:.1f}%)')
        self.stdout.write(f'Low similarity (<0.3): {low_similarity} ({low_similarity/total_similarities*100:.1f}%)')

    def _find_similar_user_groups(self, threshold=0.8):
        """Find groups of highly similar users"""
        high_similarities = UserSimilarity.objects.filter(
            similarity_score__gte=threshold
        ).order_by('-similarity_score')
        
        if not high_similarities.exists():
            self.stdout.write(f'No user pairs found with similarity ≥ {threshold}')
            return
        
        self.stdout.write(f'\nHighly similar user pairs (≥ {threshold}):')
        for sim in high_similarities[:10]:  # Top 10
            self.stdout.write(f'  {sim.user1.username} ↔ {sim.user2.username}: {sim.similarity_score:.3f}')

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='Show similarity statistics after calculation',
        )
        parser.add_argument(
            '--find-groups',
            action='store_true',
            help='Find groups of highly similar users',
        )

    def handle(self, *args, **options):
        # Call parent handle method
        super().handle(*args, **options)
        
        # Show additional information if requested
        if options.get('show_stats'):
            self._show_similarity_statistics()
        
        if options.get('find_groups'):
            self._find_similar_user_groups()