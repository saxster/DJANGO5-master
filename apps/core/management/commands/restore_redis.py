"""
Django management command for Redis restore operations.

CRITICAL: This command can overwrite Redis data. Use with extreme caution.

Usage:
    python manage.py restore_redis --list
    python manage.py restore_redis --backup-id <backup_id>
    python manage.py restore_redis --backup-id <backup_id> --confirm
    python manage.py restore_redis --backup-id <backup_id> --no-pre-backup
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.core.services.redis_backup_service import redis_backup_service


class Command(BaseCommand):
    help = 'CRITICAL: Restore Redis from backup - can cause data loss!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-id',
            type=str,
            help='ID of backup to restore from'
        )

        parser.add_argument(
            '--list',
            action='store_true',
            help='List available backups for restore'
        )

        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm restore operation (required for actual restore)'
        )

        parser.add_argument(
            '--no-pre-backup',
            action='store_true',
            help='Skip creating backup before restore (NOT RECOMMENDED)'
        )

        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Days back to show available backups (default: 30)'
        )

        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force restore without interactive confirmation (DANGEROUS)'
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        json_output = options.get('json', False)

        try:
            if options.get('list'):
                result = self._list_available_backups(options)
            else:
                result = self._perform_restore(options)

            # Output results
            if json_output:
                self.stdout.write(json.dumps(result, indent=2, default=str))
            else:
                self._display_formatted_result(result, verbosity)

        except Exception as e:
            if json_output:
                error_result = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                self.stdout.write(json.dumps(error_result, indent=2))
            else:
                raise CommandError(f'Redis restore operation failed: {e}')

    def _list_available_backups(self, options):
        """List available backups for restore."""
        days_back = options.get('days_back', 30)

        backups = redis_backup_service.list_backups(days_back=days_back)

        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x.created_at, reverse=True)

        return {
            'operation': 'list_backups_for_restore',
            'status': 'completed',
            'days_back': days_back,
            'backup_count': len(backups),
            'backups': [
                {
                    'backup_id': backup.backup_id,
                    'backup_type': backup.backup_type,
                    'file_size_mb': backup.file_size / 1024 / 1024,
                    'verification_status': backup.verification_status,
                    'created_at': backup.created_at,
                    'age_days': (timezone.now() - backup.created_at).days,
                    'redis_version': backup.redis_version,
                    'compression_ratio': backup.compression_ratio,
                    'checksum': backup.checksum[:16] + '...'  # Show partial checksum
                }
                for backup in backups
            ],
            'timestamp': timezone.now()
        }

    def _perform_restore(self, options):
        """Perform Redis restore operation with safety checks."""
        backup_id = options.get('backup_id')
        confirm = options.get('confirm', False)
        force = options.get('force', False)
        create_pre_backup = not options.get('no_pre_backup', False)

        if not backup_id:
            raise CommandError(
                "Backup ID is required for restore operation. "
                "Use --list to see available backups."
            )

        # Find the backup
        backups = redis_backup_service.list_backups()
        backup_info = None

        for backup in backups:
            if backup.backup_id == backup_id:
                backup_info = backup
                break

        if not backup_info:
            raise CommandError(f"Backup not found: {backup_id}")

        # Safety checks
        if backup_info.verification_status != 'verified':
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  WARNING: Backup verification status: {backup_info.verification_status}"
                )
            )
            if not force:
                raise CommandError(
                    "Backup verification failed. Use --force to override (NOT RECOMMENDED)"
                )

        # Interactive confirmation (unless forced or confirmed)
        if not confirm and not force:
            self.stdout.write(
                self.style.ERROR(
                    "\n🚨 CRITICAL WARNING: This operation will overwrite current Redis data!"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f"You are about to restore from backup: {backup_id}"
                )
            )
            self.stdout.write(f"Backup created: {backup_info.created_at}")
            self.stdout.write(f"Backup type: {backup_info.backup_type}")
            self.stdout.write(f"Backup size: {backup_info.file_size / 1024 / 1024:.1f} MB")

            if create_pre_backup:
                self.stdout.write(
                    self.style.NOTICE(
                        "\n✅ A backup of current data will be created before restore."
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "\n❌ NO PRE-RESTORE BACKUP WILL BE CREATED (--no-pre-backup)"
                    )
                )

            self.stdout.write(
                "\nTo proceed with restore, run the command again with --confirm flag:"
            )
            self.stdout.write(
                f"python manage.py restore_redis --backup-id {backup_id} --confirm"
            )

            return {
                'operation': 'restore_confirmation_required',
                'status': 'pending',
                'backup_id': backup_id,
                'message': 'Confirmation required - use --confirm flag to proceed',
                'backup_info': {
                    'backup_id': backup_info.backup_id,
                    'backup_type': backup_info.backup_type,
                    'created_at': backup_info.created_at,
                    'file_size_mb': backup_info.file_size / 1024 / 1024,
                    'verification_status': backup_info.verification_status
                },
                'timestamp': timezone.now()
            }

        # Perform the actual restore
        self.stdout.write(
            self.style.ERROR(f"🚨 STARTING REDIS RESTORE FROM: {backup_id}")
        )

        if create_pre_backup:
            self.stdout.write("Creating pre-restore backup...")

        restore_result = redis_backup_service.restore_backup(
            backup_info=backup_info,
            create_pre_restore_backup=create_pre_backup
        )

        return {
            'operation': 'restore_redis',
            'status': 'completed' if restore_result.success else 'failed',
            'backup_id': backup_id,
            'restore_success': restore_result.success,
            'message': restore_result.message,
            'restore_time_seconds': restore_result.restore_time_seconds,
            'data_restored': restore_result.data_restored,
            'pre_restore_backup_id': restore_result.pre_restore_backup_id,
            'create_pre_backup': create_pre_backup,
            'timestamp': timezone.now()
        }

    def _display_formatted_result(self, result, verbosity):
        """Display results in human-readable format."""
        operation = result.get('operation', 'unknown')

        # Header
        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )
        self.stdout.write(
            self.style.HTTP_INFO('Redis Restore Operation')
        )
        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )

        if operation == 'list_backups_for_restore':
            self._display_backup_list(result, verbosity)
        elif operation == 'restore_confirmation_required':
            self._display_confirmation_required(result, verbosity)
        elif operation == 'restore_redis':
            self._display_restore_result(result, verbosity)

        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )

    def _display_backup_list(self, result, verbosity):
        """Display available backups for restore."""
        backups = result['backups']

        if not backups:
            self.stdout.write(
                self.style.WARNING(
                    f"No backups found in the last {result['days_back']} days."
                )
            )
            return

        self.stdout.write(f"Available backups ({len(backups)} found):")
        self.stdout.write("")

        for i, backup in enumerate(backups, 1):
            # Color code by verification status
            if backup['verification_status'] == 'verified':
                status_style = self.style.SUCCESS
                status_icon = "✅"
            elif 'failed' in backup['verification_status']:
                status_style = self.style.ERROR
                status_icon = "❌"
            else:
                status_style = self.style.WARNING
                status_icon = "⚠️"

            self.stdout.write(
                status_style(f"{i:2d}. {status_icon} {backup['backup_id']}")
            )
            self.stdout.write(f"     Type: {backup['backup_type']}")
            self.stdout.write(f"     Size: {backup['file_size_mb']:.1f} MB")
            self.stdout.write(f"     Created: {backup['created_at']}")
            self.stdout.write(f"     Age: {backup['age_days']} days")
            self.stdout.write(f"     Status: {backup['verification_status']}")

            if verbosity >= 2:
                self.stdout.write(f"     Redis Version: {backup['redis_version']}")
                self.stdout.write(f"     Compression: {backup['compression_ratio']:.2f}")
                self.stdout.write(f"     Checksum: {backup['checksum']}")

            self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                "To restore from a backup, use:"
            )
        )
        self.stdout.write(
            "python manage.py restore_redis --backup-id <backup_id> --confirm"
        )

    def _display_confirmation_required(self, result, verbosity):
        """Display confirmation required message."""
        backup_info = result['backup_info']

        self.stdout.write(
            self.style.WARNING("⚠️  RESTORE CONFIRMATION REQUIRED")
        )
        self.stdout.write("")
        self.stdout.write(f"Backup ID: {backup_info['backup_id']}")
        self.stdout.write(f"Type: {backup_info['backup_type']}")
        self.stdout.write(f"Size: {backup_info['file_size_mb']:.1f} MB")
        self.stdout.write(f"Created: {backup_info['created_at']}")
        self.stdout.write(f"Status: {backup_info['verification_status']}")
        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(result['message'])
        )

    def _display_restore_result(self, result, verbosity):
        """Display restore operation results."""
        success = result['restore_success']
        backup_id = result['backup_id']

        if success:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Redis restore completed successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Redis restore failed!")
            )

        self.stdout.write(f"Backup ID: {backup_id}")
        self.stdout.write(f"Message: {result['message']}")
        self.stdout.write(f"Duration: {result['restore_time_seconds']:.2f} seconds")
        self.stdout.write(f"Data Restored: {'Yes' if result['data_restored'] else 'No'}")

        if result.get('pre_restore_backup_id'):
            self.stdout.write(
                self.style.NOTICE(
                    f"Pre-restore backup created: {result['pre_restore_backup_id']}"
                )
            )

        if not success:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR("⚠️  RESTORE FAILED - Check Redis service status")
            )
            if result.get('pre_restore_backup_id'):
                self.stdout.write(
                    self.style.NOTICE(
                        f"You can restore from pre-backup: {result['pre_restore_backup_id']}"
                    )
                )

        if verbosity >= 2:
            self.stdout.write(f"\nOperation timestamp: {result['timestamp']}")
            self.stdout.write(f"Create pre-backup: {'Yes' if result['create_pre_backup'] else 'No'}")