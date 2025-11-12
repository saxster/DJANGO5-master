#!/usr/bin/env python
"""
Help Center Deployment Verification Script

Verifies that all components are properly configured and working.

Usage:
    python apps/help_center/verify_deployment.py

Checks:
- Database tables exist
- Models can be imported
- Services work
- APIs are registered
- Templates exist
- Static files exist
- Tests can run
"""

import sys
import os
import django
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

import logging
logger = logging.getLogger(__name__)



# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection
from django.apps import apps


class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_check(message, passed):
    """Print check result with color."""
    status = f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"
    logger.debug(f"{status} {message}")


def check_database_tables():
    """Check if all help_center tables exist."""
    logger.debug(f"\n{Colors.BLUE}Checking Database Tables...{Colors.END}")

    expected_tables = [
        'help_center_tag',
        'help_center_category',
        'help_center_article',
        'help_center_search_history',
        'help_center_interaction',
        'help_center_ticket_correlation',
        'help_center_badge',
        'help_center_user_badge',
        'help_center_user_points',
        'help_center_conversation_memory',
    ]

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'help_center%'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]

    all_exist = True
    for table in expected_tables:
        exists = table in existing_tables
        print_check(f"Table {table}", exists)
        if not exists:
            all_exist = False

    return all_exist


def check_models():
    """Check if models can be imported."""
    logger.debug(f"\n{Colors.BLUE}Checking Models...{Colors.END}")

    try:
        from apps.help_center.models import (
            HelpTag, HelpCategory, HelpArticle,
            HelpSearchHistory, HelpArticleInteraction, HelpTicketCorrelation
        )
        from apps.help_center.gamification_models import (
            HelpBadge, HelpUserBadge, HelpUserPoints
        )
        from apps.help_center.memory_models import HelpConversationMemory

        print_check("All models importable", True)
        return True

    except ImportError as e:
        print_check(f"Model import failed: {e}", False)
        return False


def check_services():
    """Check if services can be imported."""
    logger.debug(f"\n{Colors.BLUE}Checking Services...{Colors.END}")

    try:
        from apps.help_center.services import (
            KnowledgeService, SearchService, AIAssistantService,
            AnalyticsService, TicketIntegrationService
        )
        from apps.help_center.gamification_service import GamificationService

        print_check("All services importable", True)
        return True

    except ImportError as e:
        print_check(f"Service import failed: {e}", False)
        return False


def check_api_views():
    """Check if API views are registered."""
    logger.debug(f"\n{Colors.BLUE}Checking API Views...{Colors.END}")

    try:
        from apps.help_center.views import (
            HelpArticleViewSet, HelpCategoryViewSet, HelpAnalyticsViewSet
        )
        print_check("API ViewSets importable", True)

        from apps.help_center.serializers import (
            HelpArticleDetailSerializer, HelpSearchRequestSerializer
        )
        print_check("API Serializers importable", True)

        return True

    except ImportError as e:
        print_check(f"API import failed: {e}", False)
        return False


def check_websocket():
    """Check WebSocket consumer."""
    logger.debug(f"\n{Colors.BLUE}Checking WebSocket Consumer...{Colors.END}")

    try:
        from apps.help_center.consumers import HelpChatConsumer
        print_check("WebSocket consumer importable", True)
        return True

    except ImportError as e:
        print_check(f"WebSocket import failed: {e}", False)
        return False


def check_static_files():
    """Check if static files exist."""
    logger.debug(f"\n{Colors.BLUE}Checking Static Files...{Colors.END}")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    static_dir = os.path.join(base_dir, 'apps', 'help_center', 'static', 'help_center')

    files_to_check = [
        'js/help-button.js',
        'js/tooltips.js',
        'js/guided-tours.js',
        'js/inline-cards.js',
        'css/help-styles.css',
    ]

    all_exist = True
    for file_path in files_to_check:
        full_path = os.path.join(static_dir, file_path)
        exists = os.path.exists(full_path)
        print_check(f"Static file {file_path}", exists)
        if not exists:
            all_exist = False

    return all_exist


def check_tests():
    """Check if test files exist."""
    logger.debug(f"\n{Colors.BLUE}Checking Test Files...{Colors.END}")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    test_dir = os.path.join(base_dir, 'apps', 'help_center', 'tests')

    test_files = [
        'test_models.py',
        'test_services.py',
        'test_api.py',
        'test_security.py',
        'test_tasks.py',
    ]

    all_exist = True
    for test_file in test_files:
        full_path = os.path.join(test_dir, test_file)
        exists = os.path.exists(full_path)
        print_check(f"Test file {test_file}", exists)
        if not exists:
            all_exist = False

    return all_exist


def check_pgvector():
    """Check if pgvector extension is enabled."""
    logger.debug(f"\n{Colors.BLUE}Checking pgvector Extension...{Colors.END}")

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            result = cursor.fetchone()

        exists = result is not None
        print_check("pgvector extension enabled", exists)

        if not exists:
            logger.debug(f"{Colors.YELLOW}  Run: psql -U postgres -d YOUR_DB -c 'CREATE EXTENSION vector;'{Colors.END}")

        return exists

    except NETWORK_EXCEPTIONS as e:
        print_check(f"pgvector check failed: {e}", False)
        return False


def main():
    """Run all verification checks."""
    logger.debug(f"{Colors.BLUE}{'='*60}{Colors.END}")
    logger.debug(f"{Colors.BLUE}Help Center Deployment Verification{Colors.END}")
    logger.debug(f"{Colors.BLUE}{'='*60}{Colors.END}")

    checks = [
        ("Database Tables", check_database_tables),
        ("Models", check_models),
        ("Services", check_services),
        ("API Views", check_api_views),
        ("WebSocket", check_websocket),
        ("Static Files", check_static_files),
        ("Test Files", check_tests),
        ("pgvector Extension", check_pgvector),
    ]

    results = []
    for name, check_func in checks:
        try:
            passed = check_func()
            results.append((name, passed))
        except (ValueError, TypeError, AttributeError) as e:
            print_check(f"{name} check error: {e}", False)
            results.append((name, False))

    # Summary
    logger.debug(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    logger.debug(f"{Colors.BLUE}Summary{Colors.END}")
    logger.debug(f"{Colors.BLUE}{'='*60}{Colors.END}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    percentage = (passed_count / total_count * 100) if total_count > 0 else 0

    logger.debug(f"Passed: {passed_count}/{total_count} ({percentage:.1f}%)")

    if passed_count == total_count:
        logger.debug(f"\n{Colors.GREEN}✓ All checks passed! System is ready.{Colors.END}")
        return 0
    else:
        logger.error(f"\n{Colors.YELLOW}⚠ Some checks failed. Review output above.{Colors.END}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
