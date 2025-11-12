"""
HelpBot Management Command

Main command for managing HelpBot knowledge base, analytics, and maintenance tasks.
Integrates with existing codebase patterns and provides comprehensive management capabilities.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import logging

from apps.helpbot.services import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

    HelpBotKnowledgeService,
    HelpBotAnalyticsService,
    HelpBotContextService
)
from apps.helpbot.models import (
    HelpBotKnowledge, HelpBotSession, HelpBotMessage,
    HelpBotFeedback, HelpBotContext, HelpBotAnalytics
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    HelpBot management command - main entry point for all HelpBot operations.
    """

    help = 'Manage HelpBot knowledge base, analytics, and maintenance tasks'

    def add_arguments(self, parser):
        """Add command arguments."""
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Knowledge management
        knowledge_parser = subparsers.add_parser('knowledge', help='Knowledge base operations')
        knowledge_subparsers = knowledge_parser.add_subparsers(dest='knowledge_action')

        # Initialize knowledge base
        init_parser = knowledge_subparsers.add_parser('init', help='Initialize knowledge base')
        init_parser.add_argument('--force', action='store_true',
                               help='Force re-initialization even if data exists')

        # Update knowledge base
        update_parser = knowledge_subparsers.add_parser('update', help='Update knowledge base')
        update_parser.add_argument('--source', choices=['docs', 'models', 'api', 'all'],
                                 default='all', help='Source to update from')

        # Search knowledge
        search_parser = knowledge_subparsers.add_parser('search', help='Search knowledge base')
        search_parser.add_argument('query', help='Search query')
        search_parser.add_argument('--limit', type=int, default=10, help='Number of results')

        # Analytics operations
        analytics_parser = subparsers.add_parser('analytics', help='Analytics operations')
        analytics_subparsers = analytics_parser.add_subparsers(dest='analytics_action')

        # Generate report
        report_parser = analytics_subparsers.add_parser('report', help='Generate analytics report')
        report_parser.add_argument('--days', type=int, default=30, help='Days to include in report')
        report_parser.add_argument('--format', choices=['text', 'json'], default='text',
                                 help='Report format')

        # Generate insights
        insights_parser = analytics_subparsers.add_parser('insights', help='Generate insights')
        insights_parser.add_argument('--days', type=int, default=30, help='Days to analyze')

        # Maintenance operations
        maintenance_parser = subparsers.add_parser('maintenance', help='Maintenance operations')
        maintenance_subparsers = maintenance_parser.add_subparsers(dest='maintenance_action')

        # Cleanup old data
        cleanup_parser = maintenance_subparsers.add_parser('cleanup', help='Cleanup old data')
        cleanup_parser.add_argument('--days', type=int, default=90, help='Keep data newer than X days')
        cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')

        # Health check
        maintenance_subparsers.add_parser('health', help='System health check')

        # Status
        subparsers.add_parser('status', help='Show system status')

    def handle(self, *args, **options):
        """Handle the command."""
        action = options['action']

        if not action:
            self.print_help()
            return

        try:
            if action == 'knowledge':
                self._handle_knowledge(options)
            elif action == 'analytics':
                self._handle_analytics(options)
            elif action == 'maintenance':
                self._handle_maintenance(options)
            elif action == 'status':
                self._handle_status(options)
            else:
                raise CommandError(f"Unknown action: {action}")

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Command failed: {e}")
            raise CommandError(f"Command failed: {e}")

    def _handle_knowledge(self, options):
        """Handle knowledge base operations."""
        knowledge_action = options.get('knowledge_action')
        knowledge_service = HelpBotKnowledgeService()

        if knowledge_action == 'init':
            self.stdout.write("🚀 Initializing HelpBot knowledge base...")

            if not options.get('force'):
                # Check if knowledge already exists
                existing_count = HelpBotKnowledge.objects.count()
                if existing_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f"Knowledge base already contains {existing_count} entries.")
                    )
                    self.stdout.write("Use --force to re-initialize.")
                    return

            success = knowledge_service.initialize_index()
            if success:
                total_count = HelpBotKnowledge.objects.filter(is_active=True).count()
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Knowledge base initialized with {total_count} entries")
                )
            else:
                raise CommandError("Failed to initialize knowledge base")

        elif knowledge_action == 'update':
            source = options.get('source', 'all')
            self.stdout.write(f"📚 Updating knowledge base from {source}...")

            if source in ['docs', 'all']:
                doc_count = knowledge_service._process_documentation_files()
                self.stdout.write(f"  📄 Processed {doc_count} documentation files")

            if source in ['models', 'all']:
                model_count = knowledge_service._process_model_documentation()
                self.stdout.write(f"  🏗️ Processed {model_count} model definitions")

            if source in ['api', 'all']:
                api_count = knowledge_service._process_api_documentation()
                self.stdout.write(f"  🔗 Processed {api_count} API definitions")

            self.stdout.write(self.style.SUCCESS("✅ Knowledge base updated"))

        elif knowledge_action == 'search':
            query = options['query']
            limit = options.get('limit', 10)

            self.stdout.write(f"🔍 Searching for: '{query}'")
            results = knowledge_service.search_knowledge(query, limit=limit)

            if results:
                self.stdout.write(f"\n📋 Found {len(results)} results:")
                for i, result in enumerate(results, 1):
                    self.stdout.write(f"\n{i}. {result['title']}")
                    self.stdout.write(f"   Category: {result['category']}")
                    self.stdout.write(f"   Type: {result['knowledge_type']}")
                    self.stdout.write(f"   Effectiveness: {result['effectiveness_score']:.2f}")
                    if len(result['content']) > 150:
                        self.stdout.write(f"   Preview: {result['content'][:150]}...")
                    else:
                        self.stdout.write(f"   Content: {result['content']}")
            else:
                self.stdout.write(self.style.WARNING("No results found"))

        else:
            raise CommandError(f"Unknown knowledge action: {knowledge_action}")

    def _handle_analytics(self, options):
        """Handle analytics operations."""
        analytics_action = options.get('analytics_action')
        analytics_service = HelpBotAnalyticsService()

        if analytics_action == 'report':
            days = options.get('days', 30)
            report_format = options.get('format', 'text')

            self.stdout.write(f"📊 Generating {days}-day analytics report...")

            dashboard_data = analytics_service.get_dashboard_data(days)

            if report_format == 'json':
                import json
                self.stdout.write(json.dumps(dashboard_data, indent=2, default=str))
            else:
                self._print_analytics_report(dashboard_data, days)

        elif analytics_action == 'insights':
            days = options.get('days', 30)

            self.stdout.write(f"💡 Generating insights for the last {days} days...")

            insights = analytics_service.generate_insights(days)

            if insights:
                self.stdout.write(f"\n🎯 Found {len(insights)} insights:")
                for insight in insights:
                    severity_icon = {
                        'error': '🔴',
                        'warning': '🟡',
                        'info': '🔵'
                    }.get(insight['severity'], '⚪')

                    self.stdout.write(f"\n{severity_icon} {insight['title']}")
                    self.stdout.write(f"   {insight['description']}")
                    self.stdout.write(f"   💡 Recommendation: {insight['recommendation']}")
            else:
                self.stdout.write(self.style.SUCCESS("✅ No issues found - system performing well!"))

        else:
            raise CommandError(f"Unknown analytics action: {analytics_action}")

    def _handle_maintenance(self, options):
        """Handle maintenance operations."""
        maintenance_action = options.get('maintenance_action')

        if maintenance_action == 'cleanup':
            days = options.get('days', 90)
            dry_run = options.get('dry_run', False)

            self.stdout.write(f"🧹 {'[DRY RUN] ' if dry_run else ''}Cleaning up data older than {days} days...")

            cutoff_date = timezone.now() - timedelta(days=days)

            # Count what would be deleted
            old_contexts = HelpBotContext.objects.filter(timestamp__lt=cutoff_date).count()
            old_analytics = HelpBotAnalytics.objects.filter(date__lt=cutoff_date.date()).count()
            old_sessions = HelpBotSession.objects.filter(cdtz__lt=cutoff_date).count()

            if dry_run:
                self.stdout.write(f"Would delete:")
                self.stdout.write(f"  📍 {old_contexts} context records")
                self.stdout.write(f"  📊 {old_analytics} analytics records")
                self.stdout.write(f"  💬 {old_sessions} completed sessions (and their messages/feedback)")
            else:
                # Perform actual cleanup
                with transaction.atomic():
                    # Clean contexts
                    context_service = HelpBotContextService()
                    cleaned_contexts = context_service.cleanup_old_contexts(days)

                    # Clean analytics
                    analytics_service = HelpBotAnalyticsService()
                    cleaned_analytics = analytics_service.cleanup_old_analytics(days)

                    # Clean completed sessions older than cutoff
                    deleted_sessions = HelpBotSession.objects.filter(
                        cdtz__lt=cutoff_date,
                        current_state=HelpBotSession.StateChoices.COMPLETED
                    ).delete()[0]

                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Cleaned up {cleaned_contexts} contexts, "
                        f"{cleaned_analytics} analytics, {deleted_sessions} sessions"
                    ))

        elif maintenance_action == 'health':
            self._perform_health_check()

        else:
            raise CommandError(f"Unknown maintenance action: {maintenance_action}")

    def _handle_status(self, options):
        """Handle status display."""
        self.stdout.write("📈 HelpBot System Status")
        self.stdout.write("=" * 50)

        # Knowledge base status
        total_knowledge = HelpBotKnowledge.objects.count()
        active_knowledge = HelpBotKnowledge.objects.filter(is_active=True).count()
        avg_effectiveness = HelpBotKnowledge.objects.filter(is_active=True).aggregate(
            avg=models.Avg('effectiveness_score')
        )['avg']

        self.stdout.write(f"\n📚 Knowledge Base:")
        self.stdout.write(f"  Total articles: {total_knowledge}")
        self.stdout.write(f"  Active articles: {active_knowledge}")
        self.stdout.write(f"  Average effectiveness: {avg_effectiveness:.3f}" if avg_effectiveness else "  Average effectiveness: N/A")

        # Session statistics
        today = timezone.now().date()
        sessions_today = HelpBotSession.objects.filter(cdtz__date=today).count()
        sessions_this_week = HelpBotSession.objects.filter(
            cdtz__gte=today - timedelta(days=7)
        ).count()

        self.stdout.write(f"\n💬 Sessions:")
        self.stdout.write(f"  Today: {sessions_today}")
        self.stdout.write(f"  This week: {sessions_this_week}")

        # Message statistics
        messages_today = HelpBotMessage.objects.filter(cdtz__date=today).count()
        avg_response_time = HelpBotMessage.objects.filter(
            cdtz__date__gte=today - timedelta(days=7),
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            processing_time_ms__isnull=False
        ).aggregate(avg=models.Avg('processing_time_ms'))['avg']

        self.stdout.write(f"\n📨 Messages:")
        self.stdout.write(f"  Today: {messages_today}")
        self.stdout.write(f"  Avg response time: {avg_response_time:.0f}ms" if avg_response_time else "  Avg response time: N/A")

        # Feedback statistics
        feedback_this_week = HelpBotFeedback.objects.filter(
            cdtz__gte=timezone.now() - timedelta(days=7)
        ).count()
        avg_satisfaction = HelpBotSession.objects.filter(
            satisfaction_rating__isnull=False,
            cdtz__gte=timezone.now() - timedelta(days=7)
        ).aggregate(avg=models.Avg('satisfaction_rating'))['avg']

        self.stdout.write(f"\n⭐ Feedback:")
        self.stdout.write(f"  This week: {feedback_this_week}")
        self.stdout.write(f"  Avg satisfaction: {avg_satisfaction:.1f}/5" if avg_satisfaction else "  Avg satisfaction: N/A")

    def _perform_health_check(self):
        """Perform comprehensive health check."""
        self.stdout.write("🏥 HelpBot Health Check")
        self.stdout.write("=" * 50)

        checks = []

        # Database connectivity
        try:
            HelpBotKnowledge.objects.count()
            checks.append(("Database", "✅ Connected"))
        except DATABASE_EXCEPTIONS as e:
            checks.append(("Database", f"❌ Error: {e}"))

        # Knowledge base health
        try:
            active_count = HelpBotKnowledge.objects.filter(is_active=True).count()
            if active_count > 0:
                checks.append(("Knowledge Base", f"✅ {active_count} active articles"))
            else:
                checks.append(("Knowledge Base", "⚠️ No active articles"))
        except DATABASE_EXCEPTIONS as e:
            checks.append(("Knowledge Base", f"❌ Error: {e}"))

        # Recent activity
        try:
            recent_sessions = HelpBotSession.objects.filter(
                cdtz__gte=timezone.now() - timedelta(hours=24)
            ).count()
            if recent_sessions > 0:
                checks.append(("Recent Activity", f"✅ {recent_sessions} sessions in 24h"))
            else:
                checks.append(("Recent Activity", "ℹ️ No recent activity"))
        except DATABASE_EXCEPTIONS as e:
            checks.append(("Recent Activity", f"❌ Error: {e}"))

        # Performance check
        try:
            recent_avg_response = HelpBotMessage.objects.filter(
                cdtz__gte=timezone.now() - timedelta(days=7),
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                processing_time_ms__isnull=False
            ).aggregate(avg=models.Avg('processing_time_ms'))['avg']

            if recent_avg_response:
                if recent_avg_response < 2000:  # < 2 seconds
                    checks.append(("Performance", f"✅ Avg response: {recent_avg_response:.0f}ms"))
                elif recent_avg_response < 5000:  # < 5 seconds
                    checks.append(("Performance", f"⚠️ Avg response: {recent_avg_response:.0f}ms"))
                else:
                    checks.append(("Performance", f"❌ Slow response: {recent_avg_response:.0f}ms"))
            else:
                checks.append(("Performance", "ℹ️ No recent response data"))
        except DATABASE_EXCEPTIONS as e:
            checks.append(("Performance", f"❌ Error: {e}"))

        # Settings check
        try:
            helpbot_enabled = getattr(settings, 'HELPBOT_ENABLED', True)
            if helpbot_enabled:
                checks.append(("Configuration", "✅ HelpBot enabled"))
            else:
                checks.append(("Configuration", "⚠️ HelpBot disabled"))
        except (ValueError, TypeError, AttributeError) as e:
            checks.append(("Configuration", f"❌ Error: {e}"))

        # Display results
        self.stdout.write("\n🔍 Health Check Results:")
        for component, status in checks:
            self.stdout.write(f"  {component:<20} {status}")

        # Overall health
        failed_checks = len([c for c in checks if "❌" in c[1]])
        warning_checks = len([c for c in checks if "⚠️" in c[1]])

        self.stdout.write("\n📊 Overall Health:")
        if failed_checks == 0 and warning_checks == 0:
            self.stdout.write("  " + self.style.SUCCESS("✅ System healthy"))
        elif failed_checks == 0:
            self.stdout.write("  " + self.style.WARNING(f"⚠️ {warning_checks} warnings"))
        else:
            self.stdout.write("  " + self.style.ERROR(f"❌ {failed_checks} errors, {warning_checks} warnings"))

    def _print_analytics_report(self, data, days):
        """Print formatted analytics report."""
        self.stdout.write(f"\n📊 HelpBot Analytics Report ({days} days)")
        self.stdout.write("=" * 60)

        # Overview
        overview = data.get('overview', {})
        self.stdout.write(f"\n📈 Overview:")
        self.stdout.write(f"  Total Sessions: {overview.get('total_sessions', 0)}")
        self.stdout.write(f"  Total Messages: {overview.get('total_messages', 0)}")
        self.stdout.write(f"  Unique Users: {overview.get('unique_users', 0)}")
        self.stdout.write(f"  Avg Session Length: {overview.get('avg_session_length', 0):.1f} messages")
        self.stdout.write(f"  Completion Rate: {overview.get('completion_rate', 0):.1f}%")

        # Performance
        performance = data.get('performance_metrics', {})
        self.stdout.write(f"\n⚡ Performance:")
        self.stdout.write(f"  Avg Response Time: {performance.get('avg_response_time_ms', 0):.0f}ms")
        self.stdout.write(f"  High Confidence Rate: {performance.get('high_confidence_rate', 0):.1f}%")

        # Satisfaction
        satisfaction = data.get('user_satisfaction', {})
        self.stdout.write(f"\n⭐ User Satisfaction:")
        self.stdout.write(f"  Avg Session Rating: {satisfaction.get('avg_session_rating', 0):.1f}/5")
        self.stdout.write(f"  Total Ratings: {satisfaction.get('total_session_ratings', 0)}")
        self.stdout.write(f"  Satisfaction Rate: {satisfaction.get('satisfaction_rate', 0):.1f}%")

        # Knowledge
        knowledge = data.get('knowledge_analytics', {})
        self.stdout.write(f"\n📚 Knowledge Base:")
        self.stdout.write(f"  Active Articles: {knowledge.get('total_active_articles', 0)}")
        self.stdout.write(f"  Avg Effectiveness: {knowledge.get('avg_effectiveness_score', 0):.3f}")
        self.stdout.write(f"  Total References: {knowledge.get('total_knowledge_references', 0)}")

        # Top articles
        top_articles = knowledge.get('top_knowledge_articles', [])
        if top_articles:
            self.stdout.write(f"\n🔝 Top Knowledge Articles:")
            for i, article in enumerate(top_articles[:5], 1):
                self.stdout.write(f"  {i}. {article['title']} (used {article['usage_count']} times)")

        self.stdout.write("")

    def print_help(self):
        """Print comprehensive help information."""
        help_text = """
🤖 HelpBot Management Tool

USAGE:
    python manage.py helpbot_manage <action> [options]

ACTIONS:
    knowledge    Manage knowledge base
    analytics    Generate analytics and reports
    maintenance  System maintenance operations
    status       Show system status

KNOWLEDGE OPERATIONS:
    knowledge init [--force]           Initialize knowledge base
    knowledge update [--source]       Update knowledge from sources
    knowledge search <query>          Search knowledge base

ANALYTICS OPERATIONS:
    analytics report [--days] [--format]   Generate analytics report
    analytics insights [--days]            Generate actionable insights

MAINTENANCE OPERATIONS:
    maintenance cleanup [--days] [--dry-run]   Clean up old data
    maintenance health                          System health check

EXAMPLES:
    # Initialize knowledge base
    python manage.py helpbot_manage knowledge init

    # Update from documentation
    python manage.py helpbot_manage knowledge update --source docs

    # Search for help content
    python manage.py helpbot_manage knowledge search "how to create task"

    # Generate 7-day report
    python manage.py helpbot_manage analytics report --days 7

    # Get system insights
    python manage.py helpbot_manage analytics insights

    # Cleanup data older than 60 days (dry run first)
    python manage.py helpbot_manage maintenance cleanup --days 60 --dry-run

    # Check system health
    python manage.py helpbot_manage maintenance health

    # Show current status
    python manage.py helpbot_manage status

For more help on specific actions:
    python manage.py helpbot_manage <action> --help
"""
        self.stdout.write(help_text)