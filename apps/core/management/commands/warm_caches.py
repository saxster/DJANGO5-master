"""
Django management command for cache warming

This command warms critical application caches during off-peak hours
to ensure optimal performance during peak usage.

Usage:
    python manage.py warm_caches
    python manage.py warm_caches --force  # Force warming even if recently done
    python manage.py warm_caches --dry-run  # Show what would be warmed
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import logging
from typing import Dict, Any

from apps.activity.managers.asset_manager_orm_optimized import AssetManagerORMOptimized
from apps.activity.managers.job_manager_orm_optimized import JobneedManagerORMOptimized
from apps.core.caching.utils import warm_cache_pattern, CACHE_PATTERNS
from apps.core.caching.form_mixins import warm_form_dropdown_caches

logger = logging.getLogger('cache_warming')


class Command(BaseCommand):
    help = 'Warm critical application caches for optimal performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cache warming even if recently done',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be warmed without actually warming',
        )
        parser.add_argument(
            '--categories',
            nargs='+',
            choices=['jobs', 'assets', 'users', 'reports', 'static', 'all'],
            default=['all'],
            help='Specific cache categories to warm',
        )
        parser.add_argument(
            '--max-time',
            type=int,
            default=300,  # 5 minutes
            help='Maximum time in seconds for warming process',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output',
        )
    
    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        
        if self.verbose:
            self.verbosity = 2
        
        start_time = timezone.now()
        
        # Check if recent warming was done (unless forced)
        if not options['force'] and not options['dry_run']:
            last_warming = cache.get('last_cache_warming')
            if last_warming:
                last_warming_dt = datetime.fromisoformat(last_warming)
                time_since = timezone.now() - last_warming_dt
                if time_since < timedelta(hours=2):
                    self.stdout.write(
                        self.style.WARNING(
                            f'Cache warming done {time_since} ago. Use --force to override.'
                        )
                    )
                    return
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No actual cache warming will occur')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Starting cache warming process...')
        )
        
        # Determine categories to warm
        categories = options['categories']
        if 'all' in categories:
            categories = ['jobs', 'assets', 'users', 'reports', 'static']
        
        warming_stats = {
            'total_items': 0,
            'total_time': 0,
            'errors': 0,
            'categories': {}
        }
        
        # Warm each category
        for category in categories:
            try:
                category_stats = self._warm_category(category, options)
                warming_stats['categories'][category] = category_stats
                warming_stats['total_items'] += category_stats.get('items', 0)
                warming_stats['errors'] += category_stats.get('errors', 0)
                
                # Check time limit
                elapsed = (timezone.now() - start_time).total_seconds()
                if elapsed > options['max_time']:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Time limit reached ({options["max_time"]}s). Stopping.'
                        )
                    )
                    break
                    
            except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, ValueError) as e:
                warming_stats['errors'] += 1
                logger.error(f"Error warming category {category}: {e}")
                if self.verbosity >= 1:
                    self.stderr.write(
                        self.style.ERROR(f'Error warming {category}: {str(e)}')
                    )
        
        end_time = timezone.now()
        warming_stats['total_time'] = (end_time - start_time).total_seconds()
        
        # Save warming timestamp
        if not options['dry_run']:
            cache.set('last_cache_warming', end_time.isoformat(), 86400)
        
        # Display results
        self._display_results(warming_stats, options)
    
    def _warm_category(self, category: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm a specific cache category"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if self.verbosity >= 2:
            self.stdout.write(f'Warming {category} caches...')
        
        try:
            if category == 'jobs':
                stats = self._warm_job_caches(options)
            elif category == 'assets':
                stats = self._warm_asset_caches(options)
            elif category == 'users':
                stats = self._warm_user_caches(options)
            elif category == 'reports':
                stats = self._warm_report_caches(options)
            elif category == 'static':
                stats = self._warm_static_caches(options)
            
        except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_category {category}: {e}")
        
        return stats
    
    def _warm_job_caches(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm job-related caches"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if options['dry_run']:
            stats['details'].append('Would warm job assignment caches for active users')
            stats['details'].append('Would warm job scheduling caches for active sites')
            stats['items'] = 50  # Estimated
            return stats
        
        try:
            # Warm job caches for active business units
            from apps.onboarding.models import Bt
            active_bus = Bt.objects.filter(
                enable=True,
                identifier__tacode__in=['BUSINESSUNIT', 'CLIENT']
            ).values_list('id', flat=True)[:10]
            
            for bu_id in active_bus:
                try:
                    # This would trigger cache warming for the BU
                    JobneedManagerORMOptimized.warm_job_caches(bu_id)
                    stats['items'] += 1
                    
                    if self.verbosity >= 2:
                        self.stdout.write(f'  Warmed job caches for BU {bu_id}')
                        
                except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                    stats['errors'] += 1
                    logger.warning(f"Error warming job caches for BU {bu_id}: {e}")
            
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_job_caches: {e}")
        
        return stats
    
    def _warm_asset_caches(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm asset-related caches"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if options['dry_run']:
            stats['details'].append('Would warm asset hierarchy caches')
            stats['details'].append('Would warm spatial asset caches')
            stats['details'].append('Would warm asset-questionset mappings')
            stats['items'] = 30  # Estimated
            return stats
        
        try:
            # Warm asset caches for active business units
            from apps.onboarding.models import Bt
            active_bus = Bt.objects.filter(
                enable=True,
                identifier__tacode='BUSINESSUNIT'
            ).values_list('id', flat=True)[:15]
            
            for bu_id in active_bus:
                try:
                    AssetManagerORMOptimized.warm_asset_caches(bu_id)
                    stats['items'] += 1
                    
                    if self.verbosity >= 2:
                        self.stdout.write(f'  Warmed asset caches for BU {bu_id}')
                        
                except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                    stats['errors'] += 1
                    logger.warning(f"Error warming asset caches for BU {bu_id}: {e}")
            
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_asset_caches: {e}")
        
        return stats
    
    def _warm_user_caches(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm user-related caches"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if options['dry_run']:
            stats['details'].append('Would warm user permission caches')
            stats['details'].append('Would warm user group membership caches')
            stats['items'] = 100  # Estimated
            return stats
        
        try:
            # Warm caches for recently active users
            from apps.peoples.models import People, Pgbelonging
            
            recent_threshold = timezone.now() - timedelta(days=7)
            active_users = People.objects.filter(
                last_login__gte=recent_threshold
            ).values_list('id', flat=True)[:50]  # Limit to prevent overload
            
            for user_id in active_users:
                try:
                    # Pre-warm user group cache
                    groups = list(
                        Pgbelonging.objects
                        .filter(people_id=user_id)
                        .exclude(pgroup_id=-1)
                        .values_list('pgroup_id', flat=True)
                    )
                    
                    cache_key = f"person_groups_{user_id}"
                    cache.set(cache_key, groups, 7200)  # 2 hours
                    
                    stats['items'] += 1
                    
                    if self.verbosity >= 2:
                        self.stdout.write(f'  Warmed user cache for user {user_id}')
                        
                except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
                    stats['errors'] += 1
                    logger.warning(f"Error warming user cache for {user_id}: {e}")
            
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_user_caches: {e}")
        
        return stats
    
    def _warm_report_caches(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm report-related caches"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if options['dry_run']:
            stats['details'].append('Would warm frequently accessed report caches')
            stats['details'].append('Would warm dashboard metric caches')
            stats['items'] = 20  # Estimated
            return stats
        
        try:
            # This would warm up commonly used reports
            # Implementation depends on specific reports in the system
            
            # Example: Warm dashboard metrics
            cache_key = "dashboard_metrics:all"
            if not cache.get(cache_key):
                # Mock dashboard metrics
                metrics = {
                    'total_jobs': 0,
                    'completed_jobs': 0,
                    'pending_jobs': 0,
                    'active_assets': 0
                }
                cache.set(cache_key, metrics, 1800)  # 30 minutes
                stats['items'] += 1
                
                if self.verbosity >= 2:
                    self.stdout.write('  Warmed dashboard metrics cache')
            
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_report_caches: {e}")
        
        return stats
    
    def _warm_static_caches(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Warm static/reference data caches"""
        stats = {'items': 0, 'errors': 0, 'details': []}
        
        if options['dry_run']:
            stats['details'].append('Would warm capability tree cache')
            stats['details'].append('Would warm type assist lookup cache')
            stats['details'].append('Would warm system configuration cache')
            stats['items'] = 10  # Estimated
            return stats
        
        try:
            # Warm capability tree
            from apps.peoples.models import Capability
            
            cache_key = "capability_tree:all"
            if not cache.get(cache_key):
                capabilities = list(
                    Capability.objects.all().values(
                        'id', 'capname', 'parent_id', 'enable'
                    ).order_by('capname')
                )
                cache.set(cache_key, capabilities, 7200)  # 2 hours
                stats['items'] += 1
                
                if self.verbosity >= 2:
                    self.stdout.write('  Warmed capability tree cache')
            
            # Warm type assist lookups
            from apps.onboarding.models import TypeAssist
            
            for category in ['JOBSTATUS', 'PRIORITY', 'ASSET_TYPE']:
                cache_key = f"typeassist:{category}"
                if not cache.get(cache_key):
                    types = list(
                        TypeAssist.objects.filter(tacode=category)
                        .values('id', 'taname', 'tacode')
                    )
                    cache.set(cache_key, types, 3600)  # 1 hour
                    stats['items'] += 1
                    
                    if self.verbosity >= 2:
                        self.stdout.write(f'  Warmed type assist cache for {category}')
            
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            stats['errors'] += 1
            logger.error(f"Error in _warm_static_caches: {e}")
        
        return stats
    
    def _display_results(self, stats: Dict[str, Any], options: Dict[str, Any]):
        """Display cache warming results"""
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('Cache Warming Results:')
        )
        self.stdout.write(f"  Total items warmed: {stats['total_items']}")
        self.stdout.write(f"  Total time: {stats['total_time']:.2f}s")
        self.stdout.write(f"  Errors: {stats['errors']}")
        
        if stats['errors'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  {stats['errors']} errors occurred during warming")
            )
        
        if self.verbosity >= 2:
            self.stdout.write('')
            self.stdout.write('Category breakdown:')
            
            for category, category_stats in stats['categories'].items():
                self.stdout.write(f"  {category}:")
                self.stdout.write(f"    Items: {category_stats.get('items', 0)}")
                self.stdout.write(f"    Errors: {category_stats.get('errors', 0)}")
                
                if 'details' in category_stats:
                    for detail in category_stats['details']:
                        self.stdout.write(f"    - {detail}")
        
        if options['dry_run']:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING('This was a dry run - no caches were actually warmed')
            )