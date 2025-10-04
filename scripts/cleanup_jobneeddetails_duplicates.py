"""
Data Cleanup Script for JobneedDetails Duplicates

This script must be run BEFORE applying migration 0014_add_jobneeddetails_constraints.py
It identifies and removes duplicate (jobneed, question) and (jobneed, seqno) pairs,
keeping only the most recent record based on mdtz (modified timestamp).

Usage:
    python scripts/cleanup_jobneeddetails_duplicates.py --dry-run
    python scripts/cleanup_jobneeddetails_duplicates.py --execute

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management for data integrity
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
import django
django.setup()

from django.db import transaction
from django.db.models import Count, Max
from apps.activity.models import JobneedDetails
from apps.core.utils_new.db_utils import get_current_db_name
import logging

logger = logging.getLogger(__name__)


class JobneedDetailsCleanup:
    """Cleanup duplicate JobneedDetails records before constraint migration."""

    def __init__(self, dry_run=True):
        """
        Initialize cleanup handler.

        Args:
            dry_run: If True, only report duplicates without deleting
        """
        self.dry_run = dry_run
        self.stats = {
            'question_duplicates': 0,
            'seqno_duplicates': 0,
            'records_to_delete': 0,
            'records_kept': 0
        }

    def find_question_duplicates(self):
        """
        Find duplicate (jobneed, question) pairs.

        Returns:
            QuerySet: Duplicate jobneed/question combinations
        """
        duplicates = JobneedDetails.objects.values(
            'jobneed', 'question'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)

        self.stats['question_duplicates'] = duplicates.count()
        return duplicates

    def find_seqno_duplicates(self):
        """
        Find duplicate (jobneed, seqno) pairs.

        Returns:
            QuerySet: Duplicate jobneed/seqno combinations
        """
        duplicates = JobneedDetails.objects.values(
            'jobneed', 'seqno'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)

        self.stats['seqno_duplicates'] = duplicates.count()
        return duplicates

    def cleanup_question_duplicates(self):
        """
        Remove duplicate (jobneed, question) pairs, keeping most recent.

        Strategy:
        - Group by (jobneed_id, question_id)
        - Keep record with MAX(mdtz)
        - Delete older records
        """
        duplicates = self.find_question_duplicates()

        if not duplicates.exists():
            logger.info("No (jobneed, question) duplicates found")
            return

        logger.info(f"Found {duplicates.count()} duplicate (jobneed, question) pairs")

        for dup in duplicates:
            jobneed_id = dup['jobneed']
            question_id = dup['question']

            # Get all records for this combination
            records = JobneedDetails.objects.filter(
                jobneed_id=jobneed_id,
                question_id=question_id
            ).order_by('-mdtz')  # Most recent first

            records_list = list(records)
            keep_record = records_list[0]  # Keep most recent
            delete_records = records_list[1:]  # Delete older ones

            logger.info(
                f"  jobneed={jobneed_id}, question={question_id}: "
                f"Keeping id={keep_record.id} (mdtz={keep_record.mdtz}), "
                f"Deleting {len(delete_records)} older records"
            )

            if not self.dry_run:
                for record in delete_records:
                    record.delete()
                    self.stats['records_to_delete'] += 1
            else:
                self.stats['records_to_delete'] += len(delete_records)

            self.stats['records_kept'] += 1

    def cleanup_seqno_duplicates(self):
        """
        Remove duplicate (jobneed, seqno) pairs, keeping most recent.

        Strategy:
        - Group by (jobneed_id, seqno)
        - Keep record with MAX(mdtz)
        - Delete older records
        """
        duplicates = self.find_seqno_duplicates()

        if not duplicates.exists():
            logger.info("No (jobneed, seqno) duplicates found")
            return

        logger.info(f"Found {duplicates.count()} duplicate (jobneed, seqno) pairs")

        for dup in duplicates:
            jobneed_id = dup['jobneed']
            seqno = dup['seqno']

            # Get all records for this combination
            records = JobneedDetails.objects.filter(
                jobneed_id=jobneed_id,
                seqno=seqno
            ).order_by('-mdtz')  # Most recent first

            records_list = list(records)
            keep_record = records_list[0]  # Keep most recent
            delete_records = records_list[1:]  # Delete older ones

            logger.info(
                f"  jobneed={jobneed_id}, seqno={seqno}: "
                f"Keeping id={keep_record.id} (mdtz={keep_record.mdtz}), "
                f"Deleting {len(delete_records)} older records"
            )

            if not self.dry_run:
                for record in delete_records:
                    record.delete()
                    self.stats['records_to_delete'] += 1
            else:
                self.stats['records_to_delete'] += len(delete_records)

            self.stats['records_kept'] += 1

    def run(self):
        """Execute cleanup process with transaction protection."""
        mode = "DRY RUN" if self.dry_run else "LIVE EXECUTION"
        logger.info(f"=== JobneedDetails Cleanup - {mode} ===")
        logger.info(f"Started at: {datetime.now().isoformat()}")

        try:
            if self.dry_run:
                # Dry run - no transaction needed
                self.cleanup_question_duplicates()
                self.cleanup_seqno_duplicates()
            else:
                # Live run - use transaction for atomicity
                with transaction.atomic(using=get_current_db_name()):
                    self.cleanup_question_duplicates()
                    self.cleanup_seqno_duplicates()
                    logger.info("Transaction committed successfully")

            # Report statistics
            logger.info("\n=== Cleanup Statistics ===")
            logger.info(f"Duplicate (jobneed, question) pairs: {self.stats['question_duplicates']}")
            logger.info(f"Duplicate (jobneed, seqno) pairs: {self.stats['seqno_duplicates']}")
            logger.info(f"Records kept (most recent): {self.stats['records_kept']}")
            logger.info(f"Records deleted (older): {self.stats['records_to_delete']}")
            logger.info(f"Completed at: {datetime.now().isoformat()}")

            if self.dry_run:
                logger.warning("\n⚠️  This was a DRY RUN - no data was modified")
                logger.warning("Run with --execute to apply changes")
            else:
                logger.info("\n✅ Cleanup completed successfully")

            return True

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            if not self.dry_run:
                logger.error("Transaction rolled back")
            return False


def main():
    """Main entry point for cleanup script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Cleanup duplicate JobneedDetails records'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Report duplicates without deleting (default)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute cleanup (delete duplicates)'
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Determine mode
    dry_run = not args.execute

    if not dry_run:
        confirm = input(
            "\n⚠️  WARNING: This will DELETE duplicate records.\n"
            "Type 'DELETE' to confirm: "
        )
        if confirm != 'DELETE':
            logger.info("Cleanup cancelled")
            return

    # Run cleanup
    cleanup = JobneedDetailsCleanup(dry_run=dry_run)
    success = cleanup.run()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
