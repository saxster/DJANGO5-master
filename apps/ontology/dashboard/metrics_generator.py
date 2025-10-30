"""
Ontology Coverage Metrics Generator

Analyzes codebase to calculate decorator coverage statistics across domains,
apps, criticality levels, and provides trend analysis.
"""
import ast
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.db import models

from apps.ontology.registry import OntologyRegistry


class CoverageMetricsGenerator:
    """Generate comprehensive coverage metrics for ontology decorators."""

    DECORATOR_NAMES = {
        'ontology_class',
        'ontology_service',
        'ontology_api',
        'ontology_middleware',
    }

    def __init__(self):
        self.registry = OntologyRegistry()
        self.apps_path = Path(settings.BASE_DIR) / 'apps'

    def generate_full_metrics(self) -> Dict:
        """Generate complete metrics dashboard data."""
        return {
            'summary': self.get_summary_metrics(),
            'by_domain': self.get_domain_metrics(),
            'by_app': self.get_app_metrics(),
            'by_criticality': self.get_criticality_metrics(),
            'top_gaps': self.get_top_gaps(),
            'trend': self.get_trend_metrics(),
            'leaderboard': self.get_developer_leaderboard(),
            'generated_at': datetime.now().isoformat(),
        }

    def get_summary_metrics(self) -> Dict:
        """Calculate overall coverage statistics."""
        total_files = 0
        decorated_files = 0
        total_classes = 0
        decorated_classes = 0

        for app_path in self.apps_path.iterdir():
            if not app_path.is_dir() or app_path.name.startswith(('_', '.')):
                continue

            for py_file in app_path.rglob('*.py'):
                if self._should_skip_file(py_file):
                    continue

                total_files += 1
                file_stats = self._analyze_file(py_file)
                total_classes += file_stats['total_classes']
                decorated_classes += file_stats['decorated_classes']

                if file_stats['decorated_classes'] > 0:
                    decorated_files += 1

        coverage_pct = (
            (decorated_files / total_files * 100) if total_files > 0 else 0
        )
        class_coverage_pct = (
            (decorated_classes / total_classes * 100)
            if total_classes > 0
            else 0
        )

        return {
            'total_files': total_files,
            'decorated_files': decorated_files,
            'undecorated_files': total_files - decorated_files,
            'coverage_percentage': round(coverage_pct, 2),
            'total_classes': total_classes,
            'decorated_classes': decorated_classes,
            'class_coverage_percentage': round(class_coverage_pct, 2),
        }

    def get_domain_metrics(self) -> List[Dict]:
        """Calculate coverage by business domain."""
        domain_map = {
            'Operations': ['activity', 'work_order_management', 'scheduler'],
            'Assets': ['inventory', 'monitoring'],
            'People': ['peoples', 'attendance'],
            'Help Desk': ['y_helpdesk'],
            'Reports': ['reports'],
            'Security': ['noc', 'face_recognition'],
            'Wellness': ['journal', 'wellness'],
            'Core': ['core', 'api'],
            'Onboarding': ['onboarding', 'onboarding_api'],
        }

        metrics = []
        for domain, apps in domain_map.items():
            total = 0
            decorated = 0

            for app_name in apps:
                app_path = self.apps_path / app_name
                if not app_path.exists():
                    continue

                for py_file in app_path.rglob('*.py'):
                    if self._should_skip_file(py_file):
                        continue

                    total += 1
                    file_stats = self._analyze_file(py_file)
                    if file_stats['decorated_classes'] > 0:
                        decorated += 1

            coverage = (decorated / total * 100) if total > 0 else 0
            metrics.append({
                'domain': domain,
                'total_files': total,
                'decorated_files': decorated,
                'coverage_percentage': round(coverage, 2),
            })

        return sorted(metrics, key=lambda x: x['coverage_percentage'], reverse=True)

    def get_app_metrics(self) -> List[Dict]:
        """Calculate coverage by Django app."""
        metrics = []

        for app_path in self.apps_path.iterdir():
            if not app_path.is_dir() or app_path.name.startswith(('_', '.')):
                continue

            total = 0
            decorated = 0

            for py_file in app_path.rglob('*.py'):
                if self._should_skip_file(py_file):
                    continue

                total += 1
                file_stats = self._analyze_file(py_file)
                if file_stats['decorated_classes'] > 0:
                    decorated += 1

            if total > 0:
                coverage = (decorated / total * 100)
                metrics.append({
                    'app': app_path.name,
                    'total_files': total,
                    'decorated_files': decorated,
                    'coverage_percentage': round(coverage, 2),
                })

        return sorted(metrics, key=lambda x: x['coverage_percentage'], reverse=True)

    def get_criticality_metrics(self) -> List[Dict]:
        """Calculate coverage by criticality level."""
        criticality_stats = defaultdict(lambda: {'total': 0, 'decorated': 0})

        for entry in self.registry.get_all():
            level = entry.get('criticality', 'MEDIUM')
            criticality_stats[level]['decorated'] += 1

        # Estimate total critical files (models, auth, security middleware)
        critical_patterns = [
            '**/models.py',
            '**/models/*.py',
            '**/middleware/security*.py',
            '**/middleware/api_authentication.py',
            '**/services/*auth*.py',
        ]

        for pattern in critical_patterns:
            for py_file in self.apps_path.rglob(pattern):
                if self._should_skip_file(py_file):
                    continue
                # Simplified: assume critical if matches pattern
                criticality_stats['CRITICAL']['total'] += 1

        # Add HIGH/MEDIUM/LOW defaults
        for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            stats = criticality_stats[level]
            if stats['total'] == 0:
                stats['total'] = stats['decorated']

        metrics = []
        for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            stats = criticality_stats[level]
            coverage = (
                (stats['decorated'] / stats['total'] * 100)
                if stats['total'] > 0
                else 0
            )
            metrics.append({
                'criticality': level,
                'total': stats['total'],
                'decorated': stats['decorated'],
                'coverage_percentage': round(coverage, 2),
            })

        return metrics

    def get_top_gaps(self, limit: int = 10) -> List[Dict]:
        """Identify critical files missing decorators."""
        gaps = []

        critical_patterns = {
            'Models': '**/models.py',
            'Auth Services': '**/services/*auth*.py',
            'Security Middleware': '**/middleware/security*.py',
            'API Views': '**/api/*views*.py',
        }

        for category, pattern in critical_patterns.items():
            for py_file in self.apps_path.rglob(pattern):
                if self._should_skip_file(py_file):
                    continue

                file_stats = self._analyze_file(py_file)
                if file_stats['total_classes'] > 0 and file_stats['decorated_classes'] == 0:
                    gaps.append({
                        'file': str(py_file.relative_to(self.apps_path.parent)),
                        'category': category,
                        'total_classes': file_stats['total_classes'],
                        'priority': 'CRITICAL',
                    })

        return sorted(gaps, key=lambda x: x['total_classes'], reverse=True)[:limit]

    def get_trend_metrics(self, days: int = 30) -> List[Dict]:
        """Calculate coverage trend over time using git history."""
        try:
            # Get commits with decorator changes
            result = subprocess.run(
                [
                    'git',
                    'log',
                    '--since',
                    f'{days}.days.ago',
                    '--all',
                    '--pretty=format:%H|%ai|%an',
                    '--',
                    '*.py',
                ],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                commit_hash, date_str, author = line.split('|', 2)

                # Check if commit touched ontology decorators
                diff_result = subprocess.run(
                    ['git', 'show', commit_hash, '--stat', '--', '*.py'],
                    cwd=settings.BASE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if '@ontology_' in diff_result.stdout:
                    commits.append({
                        'date': date_str.split()[0],
                        'author': author,
                        'commit': commit_hash[:7],
                    })

            # Group by date
            trend = defaultdict(int)
            for commit in commits:
                trend[commit['date']] += 1

            return [
                {'date': date, 'decorations_added': count}
                for date, count in sorted(trend.items())
            ]

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            return []

    def get_developer_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Generate leaderboard of developers by decoration contributions."""
        try:
            result = self._run_git_log_for_leaderboard()
            if not result:
                return []

            author_counts = self._count_author_contributions(result)
            leaderboard = self._format_leaderboard(author_counts)

            return leaderboard[:limit]

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            return []

    def _run_git_log_for_leaderboard(self) -> Optional[str]:
        """Run git log to get author contributions."""
        result = subprocess.run(
            [
                'git',
                'log',
                '--all',
                '--pretty=format:%an',
                '-S',
                '@ontology_',
            ],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None
        return result.stdout

    def _count_author_contributions(self, git_output: str) -> Dict[str, int]:
        """Count contributions per author."""
        author_counts = defaultdict(int)
        for line in git_output.strip().split('\n'):
            if line:
                author_counts[line] += 1
        return dict(author_counts)

    def _format_leaderboard(self, author_counts: Dict[str, int]) -> List[Dict]:
        """Format author counts into leaderboard structure."""
        return [
            {'developer': author, 'decorations_added': count}
            for author, count in sorted(
                author_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped from analysis."""
        skip_patterns = [
            '__init__.py',
            'test_',
            'tests/',
            'migrations/',
            '__pycache__',
            '.pyc',
            'conftest.py',
        ]
        file_str = str(file_path)
        return any(pattern in file_str for pattern in skip_patterns)

    def _analyze_file(self, file_path: Path) -> Dict:
        """Analyze a Python file for decorator usage."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())

            total_classes = 0
            decorated_classes = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    total_classes += 1

                    for decorator in node.decorator_list:
                        decorator_name = self._get_decorator_name(decorator)
                        if decorator_name in self.DECORATOR_NAMES:
                            decorated_classes += 1
                            break

            return {
                'total_classes': total_classes,
                'decorated_classes': decorated_classes,
            }

        except (OSError, UnicodeDecodeError, SyntaxError):
            return {'total_classes': 0, 'decorated_classes': 0}

    def _get_decorator_name(self, decorator) -> Optional[str]:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
        return None
