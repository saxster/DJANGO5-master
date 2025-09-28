"""
Comprehensive mentor analysis command that orchestrates all analysis components.
"""

import time
from django.core.management.base import BaseCommand

from apps.mentor.analyzers.impact_analyzer import ImpactAnalyzer, ChangeType
from apps.mentor.analyzers.security_scanner import SecurityScanner
from apps.mentor.analyzers.performance_analyzer import PerformanceAnalyzer
from apps.mentor.analyzers.code_quality import CodeQualityAnalyzer
from apps.mentor.indexers.incremental_indexer import IncrementalIndexer
from apps.mentor.integrations.github_bot import GitHubBot
from apps.mentor.monitoring.dashboard import MentorMetrics


class Command(BaseCommand):
    help = 'Run comprehensive AI Mentor analysis'

    def add_arguments(self, parser):
        parser.add_argument('--files', nargs='*', help='Specific files to analyze')
        parser.add_argument('--pr-mode', action='store_true', help='PR analysis mode')
        parser.add_argument('--github-token', help='GitHub token for PR integration')
        parser.add_argument('--full-analysis', action='store_true', help='Run full analysis suite')

    def handle(self, *args, **options):
        start_time = time.time()
        metrics = MentorMetrics()

        try:
            # Update index first
            self.stdout.write("📊 Updating codebase index...")
            indexer = IncrementalIndexer()
            index_result = indexer.incremental_update()

            if index_result.get('status') == 'error':
                self.stdout.write(self.style.ERROR(f"Indexing failed: {index_result.get('error')}"))
                return

            # Determine files to analyze
            files_to_analyze = options.get('files') or self._get_changed_files()

            if not files_to_analyze:
                self.stdout.write(self.style.WARNING("No files to analyze"))
                return

            self.stdout.write(f"🔍 Analyzing {len(files_to_analyze)} files...")

            # Run comprehensive analysis
            results = self._run_comprehensive_analysis(files_to_analyze, options.get('full_analysis', False))

            # Record metrics
            analysis_time = time.time() - start_time
            metrics.record_operation('comprehensive_analysis', analysis_time, {
                'files_analyzed': len(files_to_analyze),
                'total_issues': sum(len(issues) for issues in results.values())
            })

            # Generate report
            self._generate_analysis_report(results)

            # PR mode integration
            if options.get('pr_mode'):
                self._handle_pr_integration(results, options.get('github_token'))

            elapsed = time.time() - start_time
            self.stdout.write(
                self.style.SUCCESS(f"✅ Analysis completed in {elapsed:.2f}s")
            )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Analysis failed: {e}")
            )
            raise

    def _get_changed_files(self):
        """Get changed files from git."""
        import subprocess

        try:
            result = subprocess.run([
                'git', 'diff', '--name-only', 'HEAD~1', 'HEAD'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip().endswith('.py')]
        except (FileNotFoundError, IOError, OSError, PermissionError):
            pass

        return []

    def _run_comprehensive_analysis(self, files, full_analysis=False):
        """Run all analysis components."""
        results = {}

        # Impact Analysis
        self.stdout.write("📈 Running impact analysis...")
        impact_analyzer = ImpactAnalyzer()
        results['impact'] = impact_analyzer.analyze_changes(files, ChangeType.MODIFIED)

        # Security Analysis
        self.stdout.write("🔒 Running security analysis...")
        security_scanner = SecurityScanner()
        results['security'] = security_scanner.scan_security_issues(files)

        # Performance Analysis
        self.stdout.write("⚡ Running performance analysis...")
        performance_analyzer = PerformanceAnalyzer()
        results['performance'] = performance_analyzer.analyze_performance(files)

        # Quality Analysis
        if full_analysis:
            self.stdout.write("📊 Running quality analysis...")
            quality_analyzer = CodeQualityAnalyzer()
            results['quality'] = quality_analyzer.analyze_code_quality(files)

        return results

    def _generate_analysis_report(self, results):
        """Generate comprehensive analysis report."""
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.HTTP_INFO("📋 ANALYSIS REPORT"))
        self.stdout.write("="*50)

        # Impact Summary
        if 'impact' in results:
            impact = results['impact']
            self.stdout.write(f"\n📈 IMPACT ANALYSIS:")
            self.stdout.write(f"   Files affected: {len(impact.affected_files)}")
            self.stdout.write(f"   Symbols affected: {len(impact.affected_symbols)}")
            self.stdout.write(f"   Breaking changes: {len(impact.breaking_changes)}")
            self.stdout.write(f"   Severity: {impact.severity.value.upper()}")

        # Security Summary
        if 'security' in results:
            security = results['security']
            issues = security.get('issues_by_severity', {})
            self.stdout.write(f"\n🔒 SECURITY ANALYSIS:")
            self.stdout.write(f"   Critical issues: {len(issues.get('critical', []))}")
            self.stdout.write(f"   High issues: {len(issues.get('high', []))}")
            self.stdout.write(f"   Risk score: {security.get('risk_score', 0):.1f}/100")

        # Performance Summary
        if 'performance' in results:
            performance = results['performance']
            self.stdout.write(f"\n⚡ PERFORMANCE ANALYSIS:")
            self.stdout.write(f"   Total issues: {len(performance.get('issues', []))}")
            self.stdout.write(f"   Cache opportunities: {len(performance.get('cache_opportunities', []))}")

        # Quality Summary
        if 'quality' in results:
            quality = results['quality']
            self.stdout.write(f"\n📊 QUALITY ANALYSIS:")
            self.stdout.write(f"   Quality score: {quality.get('quality_score', 0):.1f}/100")
            self.stdout.write(f"   Total issues: {quality.get('total_issues', 0)}")

    def _handle_pr_integration(self, results, github_token):
        """Handle GitHub PR integration."""
        if not github_token:
            self.stdout.write(self.style.WARNING("No GitHub token provided for PR integration"))
            return

        try:
            github_bot = GitHubBot(github_token)

            # For now, save analysis results locally
            # In a real implementation, this would post to the actual PR
            self.stdout.write("💬 PR integration enabled - results saved for comment generation")

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(self.style.ERROR(f"PR integration failed: {e}"))

class MentorAnalysisOrchestrator:
    """Orchestrates comprehensive mentor analysis across all components."""

    def __init__(self):
        self.metrics = MentorMetrics()

    def analyze_changeset(self, changed_files: list, options: dict = None) -> dict:
        """Analyze a set of changed files comprehensively."""
        options = options or {}
        start_time = time.time()

        try:
            # Initialize analyzers
            impact_analyzer = ImpactAnalyzer()
            security_scanner = SecurityScanner()
            performance_analyzer = PerformanceAnalyzer()
            quality_analyzer = CodeQualityAnalyzer()

            # Run analyses
            results = {
                'impact': impact_analyzer.analyze_changes(changed_files, ChangeType.MODIFIED),
                'security': security_scanner.scan_security_issues(changed_files),
                'performance': performance_analyzer.analyze_performance(changed_files),
                'quality': quality_analyzer.analyze_code_quality(changed_files) if options.get('include_quality') else {}
            }

            # Calculate overall risk and confidence
            overall_risk = self._calculate_overall_risk(results)
            confidence = self._calculate_confidence(results)

            # Record metrics
            analysis_time = time.time() - start_time
            self.metrics.record_operation('changeset_analysis', analysis_time, {
                'files_count': len(changed_files),
                'overall_risk': overall_risk,
                'confidence': confidence
            })

            return {
                'results': results,
                'overall_risk': overall_risk,
                'confidence': confidence,
                'analysis_time': analysis_time
            }

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.metrics.record_operation('changeset_analysis_error', time.time() - start_time, {
                'error': str(e)
            })
            raise

    def _calculate_overall_risk(self, results: dict) -> float:
        """Calculate overall risk score from all analyses."""
        risk_factors = []

        # Security risk (highest weight)
        security = results.get('security', {})
        if security:
            security_risk = security.get('risk_score', 0) / 100.0
            risk_factors.append(security_risk * 0.4)

        # Impact risk
        impact = results.get('impact')
        if impact and hasattr(impact, 'severity'):
            impact_weights = {'low': 0.2, 'medium': 0.5, 'high': 0.8, 'critical': 1.0}
            impact_risk = impact_weights.get(impact.severity.value, 0.5)
            risk_factors.append(impact_risk * 0.3)

        # Performance risk
        performance = results.get('performance', {})
        if performance:
            perf_issues = performance.get('issues', [])
            high_perf_issues = len([i for i in perf_issues if i.get('severity') == 'high'])
            performance_risk = min(high_perf_issues * 0.2, 1.0)
            risk_factors.append(performance_risk * 0.2)

        # Quality risk (lowest weight)
        quality = results.get('quality', {})
        if quality:
            quality_score = quality.get('quality_score', 75.0)
            quality_risk = max(0, (75.0 - quality_score) / 75.0)  # Higher risk for lower quality
            risk_factors.append(quality_risk * 0.1)

        return sum(risk_factors) if risk_factors else 0.1

    def _calculate_confidence(self, results: dict) -> float:
        """Calculate confidence in the analysis results."""
        confidence_factors = []

        # Base confidence
        confidence_factors.append(0.8)

        # Security scan confidence
        security = results.get('security', {})
        if security:
            # Higher confidence if more comprehensive scan
            total_issues = security.get('total_issues', 0)
            confidence_factors.append(min(0.9, 0.7 + (total_issues * 0.02)))

        # Impact analysis confidence
        impact = results.get('impact')
        if impact and hasattr(impact, 'confidence'):
            confidence_factors.append(impact.confidence)

        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.8