"""
Django management command for Redis backup operations.

Usage:
    python manage.py backup_redis
    python manage.py backup_redis --type rdb
    python manage.py backup_redis --type full --compress
    python manage.py backup_redis --name custom_backup_name
    python manage.py backup_redis --list
    python manage.py backup_redis --verify
    python manage.py backup_redis --cleanup --retention-days 14
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.core.services.redis_backup_service import redis_backup_service
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS



class Command(BaseCommand):
    help = 'Manage Redis backups - create, list, verify, and cleanup'

    def add_arguments(self, parser):
        # Backup creation options
        parser.add_argument(
            '--type',
            choices=['rdb', 'aof', 'full'],
            default='full',
            help='Type of backup to create (default: full)'
        )

        parser.add_argument(
            '--compress',
            action='store_true',
            help='Enable backup compression'
        )

        parser.add_argument(
            '--no-compress',
            action='store_true',
            help='Disable backup compression'
        )

        parser.add_argument(
            '--name',
            type=str,
            help='Custom backup name (auto-generated if not specified)'
        )

        # Listing and verification options
        parser.add_argument(
            '--list',
            action='store_true',
            help='List available backups'
        )

        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify backup integrity'
        )

        parser.add_argument(
            '--backup-id',
            type=str,
            help='Specific backup ID to verify'
        )

        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Days back to list/verify backups (default: 7)'
        )

        # Cleanup options
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old backups'
        )

        parser.add_argument(
            '--retention-days',
            type=int,
            help='Retention period for cleanup (uses system default if not specified)'
        )

        # Output options
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        json_output = options.get('json', False)

        try:
            # Determine operation to perform
            if options.get('list'):
                result = self._list_backups(options)
            elif options.get('verify'):
                result = self._verify_backups(options)
            elif options.get('cleanup'):
                result = self._cleanup_backups(options)
            else:
                result = self._create_backup(options)

            # Output results
            if json_output:
                self.stdout.write(json.dumps(result, indent=2, default=str))
            else:
                self._display_formatted_result(result, verbosity)

        except DATABASE_EXCEPTIONS as e:
            if json_output:
                error_result = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                self.stdout.write(json.dumps(error_result, indent=2))
            else:
                raise CommandError(f'Redis backup operation failed: {e}')

    def _create_backup(self, options):
        """Create a new Redis backup."""
        backup_type = options['type']
        custom_name = options.get('name')

        # Determine compression setting
        if options.get('no_compress'):
            compression = False
        elif options.get('compress'):
            compression = True
        else:
            compression = None  # Use service default

        self.stdout.write(f"Creating {backup_type} backup...")

        backup_info = redis_backup_service.create_backup(
            backup_type=backup_type,
            compression=compression,
            custom_name=custom_name
        )

        return {
            'operation': 'create_backup',
            'status': 'completed',
            'backup_info': {
                'backup_id': backup_info.backup_id,
                'backup_type': backup_info.backup_type,
                'file_path': backup_info.file_path,
                'file_size_mb': backup_info.file_size / 1024 / 1024,
                'compression_ratio': backup_info.compression_ratio,
                'verification_status': backup_info.verification_status,
                'created_at': backup_info.created_at,
                'redis_version': backup_info.redis_version
            },
            'timestamp': timezone.now()
        }

    def _list_backups(self, options):
        """List available backups."""
        backup_type = options.get('type')
        days_back = options.get('days_back', 7)

        backups = redis_backup_service.list_backups(
            backup_type=backup_type,
            days_back=days_back
        )

        return {
            'operation': 'list_backups',
            'status': 'completed',
            'filters': {
                'backup_type': backup_type,
                'days_back': days_back
            },
            'backup_count': len(backups),
            'backups': [
                {
                    'backup_id': backup.backup_id,
                    'backup_type': backup.backup_type,
                    'file_size_mb': backup.file_size / 1024 / 1024,
                    'verification_status': backup.verification_status,
                    'created_at': backup.created_at,
                    'age_days': (timezone.now() - backup.created_at).days
                }
                for backup in backups
            ],
            'timestamp': timezone.now()
        }

    def _verify_backups(self, options):
        """Verify backup integrity."""
        backup_id = options.get('backup_id')
        days_back = options.get('days_back', 7)

        if backup_id:
            # Verify specific backup
            backups = redis_backup_service.list_backups()
            backup_info = None

            for backup in backups:
                if backup.backup_id == backup_id:
                    backup_info = backup
                    break

            if not backup_info:
                raise CommandError(f"Backup not found: {backup_id}")

            verification_status = redis_backup_service._verify_backup(backup_info)

            return {
                'operation': 'verify_backup',
                'status': 'completed',
                'backup_id': backup_id,
                'verification_status': verification_status,
                'verified': verification_status == 'verified',
                'timestamp': timezone.now()
            }
        else:
            # Verify recent backups
            backups = redis_backup_service.list_backups(days_back=days_back)
            verification_results = []

            for backup_info in backups:
                verification_status = redis_backup_service._verify_backup(backup_info)
                verification_results.append({
                    'backup_id': backup_info.backup_id,
                    'backup_type': backup_info.backup_type,
                    'verification_status': verification_status,
                    'verified': verification_status == 'verified',
                    'created_at': backup_info.created_at
                })

            verified_count = sum(1 for r in verification_results if r['verified'])

            return {
                'operation': 'verify_backups',
                'status': 'completed',
                'days_back': days_back,
                'total_backups': len(verification_results),
                'verified_count': verified_count,
                'failed_count': len(verification_results) - verified_count,
                'verification_results': verification_results,
                'timestamp': timezone.now()
            }

    def _cleanup_backups(self, options):
        """Clean up old backups."""
        retention_days = options.get('retention_days')

        self.stdout.write("Cleaning up old Redis backups...")

        cleanup_results = redis_backup_service.cleanup_old_backups(
            retention_days=retention_days
        )

        return {
            'operation': 'cleanup_backups',
            'status': 'completed',
            'retention_days': retention_days or redis_backup_service.retention_days,
            'deleted_count': cleanup_results['deleted_count'],
            'freed_space_mb': cleanup_results['freed_space_mb'],
            'errors': cleanup_results['errors'],
            'timestamp': timezone.now()
        }

    def _display_formatted_result(self, result, verbosity):
        """Display results in human-readable format."""
        operation = result.get('operation', 'unknown')

        # Header
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )
        self.stdout.write(
            self.style.HTTP_INFO(f'Redis Backup Operation: {operation.title().replace("_", " ")}')
        )
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )

        if operation == 'create_backup':
            self._display_backup_creation_result(result, verbosity)
        elif operation == 'list_backups':
            self._display_backup_list_result(result, verbosity)
        elif operation == 'verify_backup' or operation == 'verify_backups':
            self._display_verification_result(result, verbosity)
        elif operation == 'cleanup_backups':
            self._display_cleanup_result(result, verbosity)

        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )

    def _display_backup_creation_result(self, result, verbosity):
        """Display backup creation results."""
        backup_info = result['backup_info']

        self.stdout.write(
            self.style.SUCCESS(f"✅ Backup created successfully!")
        )
        self.stdout.write(f"Backup ID: {backup_info['backup_id']}")
        self.stdout.write(f"Type: {backup_info['backup_type']}")
        self.stdout.write(f"Size: {backup_info['file_size_mb']:.1f} MB")
        self.stdout.write(f"Compression: {backup_info['compression_ratio']:.2f}")
        self.stdout.write(f"Verification: {backup_info['verification_status']}")

        if backup_info['verification_status'] != 'verified':
            self.stdout.write(
                self.style.WARNING(f"⚠️  Backup verification: {backup_info['verification_status']}")
            )

        if verbosity >= 2:
            self.stdout.write(f"File path: {backup_info['file_path']}")
            self.stdout.write(f"Redis version: {backup_info['redis_version']}")

    def _display_backup_list_result(self, result, verbosity):
        """Display backup listing results."""
        backups = result['backups']

        if not backups:
            self.stdout.write(
                self.style.WARNING("No backups found matching the criteria.")
            )
            return

        self.stdout.write(f"Found {len(backups)} backup(s):")
        self.stdout.write("")

        for backup in backups:
            status_style = (
                self.style.SUCCESS if backup['verification_status'] == 'verified'
                else self.style.WARNING
            )

            self.stdout.write(
                status_style(f"📦 {backup['backup_id']}")
            )
            self.stdout.write(f"   Type: {backup['backup_type']}")
            self.stdout.write(f"   Size: {backup['file_size_mb']:.1f} MB")
            self.stdout.write(f"   Status: {backup['verification_status']}")
            self.stdout.write(f"   Age: {backup['age_days']} days")
            self.stdout.write("")

    def _display_verification_result(self, result, verbosity):
        """Display verification results."""
        if 'verification_results' in result:
            # Multiple backup verification
            total = result['total_backups']
            verified = result['verified_count']
            failed = result['failed_count']

            if failed == 0:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ All {total} backup(s) verified successfully!")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {verified}/{total} backups verified, {failed} failed")
                )

            if verbosity >= 2:
                self.stdout.write("\nDetailed results:")
                for result_item in result['verification_results']:
                    status_style = (
                        self.style.SUCCESS if result_item['verified']
                        else self.style.ERROR
                    )
                    self.stdout.write(
                        status_style(
                            f"  {result_item['backup_id']}: {result_item['verification_status']}"
                        )
                    )
        else:
            # Single backup verification
            backup_id = result['backup_id']
            verified = result['verified']

            if verified:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Backup {backup_id} verified successfully!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Backup {backup_id} verification failed: {result['verification_status']}")
                )

    def _display_cleanup_result(self, result, verbosity):
        """Display cleanup results."""
        deleted_count = result['deleted_count']
        freed_space = result['freed_space_mb']
        errors = result['errors']

        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Cleanup completed: {deleted_count} backup(s) deleted, "
                    f"{freed_space:.1f} MB freed"
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE("No old backups found to clean up.")
            )

        if errors:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {len(errors)} error(s) occurred during cleanup:")
            )
            for error in errors:
                self.stdout.write(f"  - {error}")

        self.stdout.write(f"Retention period: {result['retention_days']} days")