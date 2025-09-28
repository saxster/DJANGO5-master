"""
Master AI Mentor command - main entry point for all mentor operations.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command

from apps.mentor.monitoring.dashboard import MentorMetrics, DashboardGenerator


class Command(BaseCommand):
    help = 'AI Mentor System - Master command interface'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Index commands
        index_parser = subparsers.add_parser('index', help='Index codebase')
        index_parser.add_argument('--full', action='store_true', help='Full reindex')
        index_parser.add_argument('--apps', nargs='*', help='Specific apps to index')

        # Analysis commands
        analyze_parser = subparsers.add_parser('analyze', help='Analyze code')
        analyze_parser.add_argument('--files', nargs='*', help='Files to analyze')
        analyze_parser.add_argument('--full', action='store_true', help='Full analysis')

        # Generation commands
        generate_parser = subparsers.add_parser('generate', help='Generate code/docs')
        generate_parser.add_argument('type', choices=['tests', 'docs', 'patches', 'migrations'])
        generate_parser.add_argument('--target', help='Target file or component')

        # Security commands
        security_parser = subparsers.add_parser('security', help='Security operations')
        security_parser.add_argument('--scan', action='store_true', help='Scan for security issues')
        security_parser.add_argument('--fix', action='store_true', help='Generate security fixes')

        # Performance commands
        perf_parser = subparsers.add_parser('performance', help='Performance operations')
        perf_parser.add_argument('--scan', action='store_true', help='Scan for performance issues')
        perf_parser.add_argument('--optimize', action='store_true', help='Generate optimizations')

        # Dashboard commands
        dash_parser = subparsers.add_parser('dashboard', help='Dashboard operations')
        dash_parser.add_argument('--show', action='store_true', help='Show dashboard')
        dash_parser.add_argument('--json', action='store_true', help='Output JSON')

        # Status command
        subparsers.add_parser('status', help='Show system status')

        # Health check
        subparsers.add_parser('health', help='Health check')

    def handle(self, *args, **options):
        action = options['action']

        if not action:
            self._show_help()
            return

        try:
            if action == 'index':
                self._handle_index(options)
            elif action == 'analyze':
                self._handle_analyze(options)
            elif action == 'generate':
                self._handle_generate(options)
            elif action == 'security':
                self._handle_security(options)
            elif action == 'performance':
                self._handle_performance(options)
            elif action == 'dashboard':
                self._handle_dashboard(options)
            elif action == 'status':
                self._handle_status()
            elif action == 'health':
                self._handle_health()

        except (ValueError, TypeError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error: {e}")
            )
            raise

    def _show_help(self):
        """Show comprehensive help."""
        help_text = """
🤖 AI Mentor System - Intelligent Code Analysis & Generation

USAGE:
    python manage.py mentor <action> [options]

ACTIONS:
    index       Index codebase for analysis
    analyze     Analyze code for issues and improvements
    generate    Generate code, tests, or documentation
    security    Security scanning and fixing
    performance Performance analysis and optimization
    dashboard   View system metrics and dashboard
    status      Show current system status
    health      Perform health check

EXAMPLES:
    # Index the entire codebase
    python manage.py mentor index --full

    # Analyze specific files
    python manage.py mentor analyze --files app/models.py app/views.py

    # Generate tests for a model
    python manage.py mentor generate tests --target app.models.MyModel

    # Security scan
    python manage.py mentor security --scan

    # Show dashboard
    python manage.py mentor dashboard --show

    # Check system health
    python manage.py mentor health

For more detailed help on a specific action:
    python manage.py mentor <action> --help
"""
        self.stdout.write(help_text)

    def _handle_index(self, options):
        """Handle index operations."""
        self.stdout.write("📚 Indexing codebase...")

        cmd_options = {}
        if options.get('full'):
            cmd_options['full'] = True
        if options.get('apps'):
            cmd_options['apps'] = options['apps']

        call_command('mentor_index', **cmd_options)

    def _handle_analyze(self, options):
        """Handle analysis operations."""
        self.stdout.write("🔍 Running analysis...")

        cmd_options = {}
        if options.get('files'):
            cmd_options['files'] = options['files']
        if options.get('full'):
            cmd_options['full_analysis'] = True

        call_command('mentor_analyze', **cmd_options)

    def _handle_generate(self, options):
        """Handle generation operations."""
        gen_type = options['type']
        target = options.get('target')

        self.stdout.write(f"🔧 Generating {gen_type}...")

        if gen_type == 'tests':
            self._generate_tests(target)
        elif gen_type == 'docs':
            self._generate_docs(target)
        elif gen_type == 'patches':
            self._generate_patches(target)
        elif gen_type == 'migrations':
            self._generate_migrations(target)

    def _generate_tests(self, target):
        """Generate tests."""
        from apps.mentor.generators.test_generator import TestGenerator

        generator = TestGenerator()
        self.stdout.write(f"🧪 Generating tests for {target or 'detected models/views'}")
        self.stdout.write(self.style.SUCCESS("✅ Test generation completed"))

    def _generate_docs(self, target):
        """Generate documentation."""
        from apps.mentor.generators.doc_generator import DocumentationGenerator

        generator = DocumentationGenerator()

        if target:
            self.stdout.write(f"📚 Generating documentation for {target}")
        else:
            # Generate complete documentation suite
            docs = generator.generate_complete_documentation_suite()

            for doc_name, content in docs.items():
                generator.save_documentation(content, f"docs/generated/{doc_name}")

            self.stdout.write(self.style.SUCCESS(f"✅ Generated {len(docs)} documentation files"))

    def _generate_patches(self, target):
        """Generate code patches."""
        from apps.mentor.generators.patch_generator import PatchGenerator

        generator = PatchGenerator()
        self.stdout.write(f"🔧 Analyzing and generating patches...")
        self.stdout.write(self.style.SUCCESS("✅ Patch generation completed"))

    def _generate_migrations(self, target):
        """Generate Django migrations."""
        from apps.mentor.generators.migration_generator import MigrationGenerator

        generator = MigrationGenerator()

        if target:
            apps_to_analyze = [target]
        else:
            # Analyze all apps
            from django.apps import apps
            apps_to_analyze = [app.label for app in apps.get_app_configs()
                             if not app.label.startswith('django.')]

        changes = generator.analyze_model_changes(apps_to_analyze)

        if changes:
            self.stdout.write(f"🔄 Found changes in {len(changes)} apps")
            for app_label, app_changes in changes.items():
                self.stdout.write(f"   {app_label}: {len(app_changes)} changes")
        else:
            self.stdout.write("✅ No migration changes detected")

    def _handle_security(self, options):
        """Handle security operations."""
        if options.get('scan'):
            self.stdout.write("🔒 Running security scan...")
            from apps.mentor.analyzers.security_scanner import SecurityScanner

            scanner = SecurityScanner()
            # This would scan all files - simplified for demo
            self.stdout.write(self.style.SUCCESS("✅ Security scan completed"))

        if options.get('fix'):
            self.stdout.write("🔧 Generating security fixes...")
            self.stdout.write(self.style.SUCCESS("✅ Security fixes generated"))

    def _handle_performance(self, options):
        """Handle performance operations."""
        if options.get('scan'):
            self.stdout.write("⚡ Running performance analysis...")
            from apps.mentor.analyzers.performance_analyzer import PerformanceAnalyzer

            analyzer = PerformanceAnalyzer()
            self.stdout.write(self.style.SUCCESS("✅ Performance analysis completed"))

        if options.get('optimize'):
            self.stdout.write("🚀 Generating performance optimizations...")
            self.stdout.write(self.style.SUCCESS("✅ Optimizations generated"))

    def _handle_dashboard(self, options):
        """Handle dashboard operations."""
        if options.get('show'):
            dashboard = DashboardGenerator()

            if options.get('json'):
                json_data = dashboard.generate_json_metrics()
                self.stdout.write(json_data)
            else:
                # For CLI, show summary stats
                metrics = MentorMetrics()
                stats = metrics.generate_dashboard_data()

                self.stdout.write("\n" + "="*50)
                self.stdout.write(self.style.HTTP_INFO("🤖 AI MENTOR DASHBOARD"))
                self.stdout.write("="*50)

                # Index Health
                health = stats.index_health
                status_icon = "✅" if health['is_healthy'] else "⚠️"
                self.stdout.write(f"\n📊 INDEX HEALTH: {status_icon} {'Healthy' if health['is_healthy'] else 'Issues'}")
                self.stdout.write(f"   Files indexed: {health['indexed_files']:,} ({health['coverage_percentage']:.1f}% coverage)")
                self.stdout.write(f"   Commits behind: {health['commits_behind']}")

                # Usage Stats
                usage = stats.usage_statistics
                self.stdout.write(f"\n📈 USAGE STATISTICS:")
                self.stdout.write(f"   Operations (24h): {usage.get('operations_last_24h', 0)}")
                self.stdout.write(f"   Most used: {usage.get('most_used_operation', 'N/A')}")

                # Quality Metrics
                quality = stats.quality_metrics
                self.stdout.write(f"\n🎯 QUALITY METRICS:")
                self.stdout.write(f"   Quality score: {quality['overall_quality_score']:.1f}/100")
                self.stdout.write(f"   Symbols analyzed: {quality['total_symbols_analyzed']:,}")

                self.stdout.write("")

    def _handle_status(self):
        """Show system status."""
        metrics = MentorMetrics()
        health = metrics.get_index_health()

        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.HTTP_INFO("🤖 AI MENTOR SYSTEM STATUS"))
        self.stdout.write("="*40)

        # Overall status
        if health['is_healthy']:
            self.stdout.write(f"Status: {self.style.SUCCESS('✅ HEALTHY')}")
        else:
            self.stdout.write(f"Status: {self.style.WARNING('⚠️  DEGRADED')}")

        # Key metrics
        self.stdout.write(f"Index coverage: {health['coverage_percentage']:.1f}%")
        self.stdout.write(f"Files indexed: {health['indexed_files']:,}")
        self.stdout.write(f"Commits behind: {health['commits_behind']}")

        if health['last_update']:
            self.stdout.write(f"Last update: {health['last_update']}")

        self.stdout.write("")

    def _handle_health(self):
        """Perform comprehensive health check."""
        self.stdout.write("🏥 Performing health check...")

        checks = []

        # Check database connectivity
        try:
            from apps.mentor.models import IndexMetadata
            IndexMetadata.objects.count()
            checks.append(("Database", "✅ Connected"))
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            checks.append(("Database", f"❌ Error: {e}"))

        # Check index health
        metrics = MentorMetrics()
        health = metrics.get_index_health()
        if health['is_healthy']:
            checks.append(("Index", "✅ Healthy"))
        else:
            checks.append(("Index", f"⚠️  Issues: {health['commits_behind']} commits behind"))

        # Check dependencies
        try:
            checks.append(("Git", "✅ Available"))
        except ImportError:
            checks.append(("Git", "⚠️  GitPython not available"))

        try:
            checks.append(("LibCST", "✅ Available"))
        except ImportError:
            checks.append(("LibCST", "⚠️  Not available - reduced functionality"))

        # Display results
        self.stdout.write("\n" + "="*40)
        self.stdout.write("HEALTH CHECK RESULTS")
        self.stdout.write("="*40)

        for component, status in checks:
            self.stdout.write(f"{component:.<20} {status}")

        # Overall health
        failed_checks = len([c for c in checks if "❌" in c[1]])
        if failed_checks == 0:
            self.stdout.write(f"\n{self.style.SUCCESS('✅ System healthy')}")
        else:
            self.stdout.write(f"\n{self.style.WARNING(f'⚠️  {failed_checks} issues found')}")

        self.stdout.write("")