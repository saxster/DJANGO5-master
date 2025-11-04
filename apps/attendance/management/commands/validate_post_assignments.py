"""
Management Command: Validate Post Assignment System

Comprehensive validation and health check for post assignment system.

Usage:
    python manage.py validate_post_assignments
    python manage.py validate_post_assignments --fix
    python manage.py validate_post_assignments --verbose
    python manage.py validate_post_assignments --check-coverage
    python manage.py validate_post_assignments --clean-expired

Author: Claude Code
Created: 2025-11-03
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Q
from datetime import date, timedelta

from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement, PeopleEventlog
from apps.onboarding.models import Shift, Bt, OnboardingZone
from apps.peoples.models import People


class Command(BaseCommand):
    help = 'Validate post assignment system integrity and health'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix issues found',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output',
        )
        parser.add_argument(
            '--check-coverage',
            action='store_true',
            help='Check post coverage gaps for today',
        )
        parser.add_argument(
            '--clean-expired',
            action='store_true',
            help='Clean up expired acknowledgements and old assignments',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Date to check (YYYY-MM-DD, defaults to today)',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.fix_issues = options['fix']

        self.stdout.write(self.style.SUCCESS('\n=== Post Assignment System Validation ===\n'))

        issues_found = 0

        # Run validation checks
        issues_found += self.check_posts_without_geofence()
        issues_found += self.check_posts_without_assignments()
        issues_found += self.check_duplicate_post_codes()
        issues_found += self.check_orphaned_assignments()
        issues_found += self.check_acknowledgement_integrity()

        if options['check_coverage']:
            issues_found += self.check_coverage_gaps(options.get('date'))

        if options['clean_expired']:
            self.clean_expired_data()

        # Summary
        self.stdout.write('\n' + '='*60)
        if issues_found == 0:
            self.stdout.write(self.style.SUCCESS(f'\n✓ System validation complete: NO ISSUES FOUND\n'))
        else:
            self.stdout.write(
                self.style.WARNING(f'\n⚠ System validation complete: {issues_found} ISSUES FOUND\n')
            )
            if not self.fix_issues:
                self.stdout.write(self.style.NOTICE('  Run with --fix to automatically resolve issues\n'))

    def check_posts_without_geofence(self):
        """Check for posts missing geofence configuration"""
        self.stdout.write('\n1. Checking posts without geofence...')

        posts = Post.objects.filter(
            active=True,
            coverage_required=True,
            geofence__isnull=True,
            gps_coordinates__isnull=True
        )

        count = posts.count()

        if count > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠ Found {count} posts without geofence or GPS coordinates'))

            if self.verbose:
                for post in posts[:10]:
                    self.stdout.write(f'    - {post.post_code}: {post.post_name}')

            if self.fix_issues:
                # Set default GPS from site
                fixed = 0
                for post in posts:
                    if post.site.gpslocation:
                        post.gps_coordinates = post.site.gpslocation
                        post.geofence_radius = 100  # Default 100m
                        post.save(update_fields=['gps_coordinates', 'geofence_radius'])
                        fixed += 1

                self.stdout.write(self.style.SUCCESS(f'  ✓ Fixed {fixed} posts with site GPS coordinates'))
                return 0  # Fixed

            return count

        self.stdout.write(self.style.SUCCESS('  ✓ All posts have geofence configuration'))
        return 0

    def check_posts_without_assignments(self):
        """Check for coverage-required posts without any assignments"""
        self.stdout.write('\n2. Checking posts without assignments...')

        today = date.today()

        posts = Post.objects.filter(
            active=True,
            coverage_required=True
        ).annotate(
            assignment_count=Count(
                'assignments',
                filter=Q(
                    assignments__assignment_date=today,
                    assignments__status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
                )
            )
        ).filter(assignment_count=0)

        count = posts.count()

        if count > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠ Found {count} posts without assignments for today'))

            if self.verbose:
                for post in posts[:10]:
                    self.stdout.write(
                        f'    - {post.post_code}: {post.post_name} '
                        f'(requires {post.required_guard_count} guards)'
                    )

            return count

        self.stdout.write(self.style.SUCCESS(f'  ✓ All coverage-required posts have assignments for today'))
        return 0

    def check_duplicate_post_codes(self):
        """Check for duplicate post codes within same site"""
        self.stdout.write('\n3. Checking for duplicate post codes...')

        from django.db.models import Count

        duplicates = Post.objects.values('site', 'post_code', 'tenant').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        count = duplicates.count()

        if count > 0:
            self.stdout.write(self.style.ERROR(f'  ✗ Found {count} duplicate post codes'))

            if self.verbose:
                for dup in duplicates:
                    site_name = Bt.objects.get(id=dup['site']).buname
                    self.stdout.write(
                        f'    - Site: {site_name}, Code: {dup["post_code"]}, Count: {dup["count"]}'
                    )

            if self.fix_issues:
                self.stdout.write(self.style.WARNING('  ⚠ Cannot auto-fix duplicate codes (manual intervention required)'))

            return count

        self.stdout.write(self.style.SUCCESS('  ✓ No duplicate post codes found'))
        return 0

    def check_orphaned_assignments(self):
        """Check for assignments with deleted posts or workers"""
        self.stdout.write('\n4. Checking for orphaned assignments...')

        # This should not happen due to CASCADE, but check anyway
        orphaned = PostAssignment.objects.filter(
            Q(post__isnull=True) | Q(worker__isnull=True)
        )

        count = orphaned.count()

        if count > 0:
            self.stdout.write(self.style.ERROR(f'  ✗ Found {count} orphaned assignments'))

            if self.fix_issues:
                deleted = orphaned.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted} orphaned assignments'))
                return 0

            return count

        self.stdout.write(self.style.SUCCESS('  ✓ No orphaned assignments found'))
        return 0

    def check_acknowledgement_integrity(self):
        """Check acknowledgement content hash integrity"""
        self.stdout.write('\n5. Checking acknowledgement integrity...')

        # Check recent acknowledgements (last 30 days)
        cutoff = timezone.now() - timedelta(days=30)
        recent_acks = PostOrderAcknowledgement.objects.filter(
            acknowledged_at__gte=cutoff,
            is_valid=True
        ).select_related('post')

        failed_integrity = 0

        for ack in recent_acks:
            if not ack.verify_integrity():
                failed_integrity += 1
                if self.verbose:
                    self.stdout.write(
                        f'    - ACK {ack.id}: Post {ack.post.post_code} orders changed after acknowledgement'
                    )

        if failed_integrity > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ Found {failed_integrity} acknowledgements with integrity issues '
                    f'(post orders changed after acknowledgement)'
                )
            )
            self.stdout.write('    This is normal if post orders were updated. Workers must re-acknowledge.')
            return failed_integrity

        self.stdout.write(self.style.SUCCESS('  ✓ All acknowledgements have valid integrity'))
        return 0

    def check_coverage_gaps(self, date_str=None):
        """Check for post coverage gaps"""
        self.stdout.write('\n6. Checking post coverage gaps...')

        if date_str:
            try:
                from datetime import datetime
                check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                check_date = date.today()
        else:
            check_date = date.today()

        gaps = []
        posts = Post.objects.filter(
            active=True,
            coverage_required=True
        ).prefetch_related('assignments')

        for post in posts:
            is_met, assigned, required = post.is_coverage_met(check_date)
            if not is_met:
                gaps.append({
                    'post': post,
                    'assigned': assigned,
                    'required': required,
                    'gap': required - assigned
                })

        if gaps:
            self.stdout.write(
                self.style.ERROR(f'  ✗ Found {len(gaps)} posts with coverage gaps for {check_date}')
            )

            if self.verbose:
                for gap_info in sorted(gaps, key=lambda x: x['gap'], reverse=True):
                    self.stdout.write(
                        f'    - {gap_info["post"].post_code}: {gap_info["post"].post_name} '
                        f'(Assigned: {gap_info["assigned"]}, Required: {gap_info["required"]}, Gap: {gap_info["gap"]})'
                    )

            return len(gaps)

        self.stdout.write(self.style.SUCCESS(f'  ✓ All posts have adequate coverage for {check_date}'))
        return 0

    def clean_expired_data(self):
        """Clean up expired acknowledgements and old assignments"""
        self.stdout.write('\n7. Cleaning expired data...')

        # Expire old acknowledgements (> 30 days)
        cutoff = timezone.now() - timedelta(days=30)
        expired_count = PostOrderAcknowledgement.objects.filter(
            acknowledged_at__lt=cutoff,
            is_valid=True,
            valid_until__isnull=True  # No explicit expiration set
        ).update(
            is_valid=False
        )

        if expired_count > 0:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Expired {expired_count} old acknowledgements (>30 days)'))

        # Archive old completed assignments (> 90 days)
        archive_cutoff = timezone.now().date() - timedelta(days=90)
        old_assignments = PostAssignment.objects.filter(
            assignment_date__lt=archive_cutoff,
            status='COMPLETED'
        )

        archive_count = old_assignments.count()

        if archive_count > 0:
            if self.verbose:
                self.stdout.write(f'  Found {archive_count} old completed assignments (>90 days)')

            # Add archival metadata
            for assignment in old_assignments:
                if not assignment.assignment_metadata:
                    assignment.assignment_metadata = {}
                assignment.assignment_metadata['archived'] = True
                assignment.assignment_metadata['archived_at'] = timezone.now().isoformat()
                assignment.save(update_fields=['assignment_metadata'])

            self.stdout.write(self.style.SUCCESS(f'  ✓ Marked {archive_count} old assignments as archived'))

        if expired_count == 0 and archive_count == 0:
            self.stdout.write(self.style.SUCCESS('  ✓ No expired data to clean'))
