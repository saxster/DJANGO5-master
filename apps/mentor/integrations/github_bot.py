"""
GitHub PR comment bot with comprehensive impact analysis and recommendations.

This bot provides:
- Impact summary: Affected modules, URLs, models
- Risk assessment: Security, performance, breaking changes
- Test recommendations: Which tests to run
- Migration notes: Database changes required
- Review checklist: Custom requirements
"""

import os
from datetime import datetime

import requests

from apps.mentor.analyzers.impact_analyzer import ImpactAnalyzer
from apps.mentor.analyzers.security_scanner import SecurityScanner
from apps.mentor.analyzers.performance_analyzer import PerformanceAnalyzer
from apps.mentor.analyzers.code_quality import CodeQualityAnalyzer


@dataclass
class PRAnalysis:
    """Container for PR analysis results."""
    impact_summary: Dict[str, Any]
    security_issues: List[Dict[str, Any]]
    performance_issues: List[Dict[str, Any]]
    quality_issues: List[Dict[str, Any]]
    risk_score: float
    recommendations: List[str]


class GitHubBot:
    """GitHub PR comment bot for AI Mentor analysis."""

    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"

    def analyze_pr(self, pr_number: int, repo_owner: str, repo_name: str) -> PRAnalysis:
        """Analyze a GitHub PR and generate comprehensive analysis."""
        # Get PR file changes
        changed_files = self._get_pr_files(pr_number, repo_owner, repo_name)

        # Run comprehensive analysis
        impact_analyzer = ImpactAnalyzer()
        security_scanner = SecurityScanner()
        performance_analyzer = PerformanceAnalyzer()
        quality_analyzer = CodeQualityAnalyzer()

        # Analyze impact
        impact_result = impact_analyzer.analyze_changes(changed_files)

        # Analyze security
        security_result = security_scanner.scan_security_issues(changed_files)

        # Analyze performance
        performance_result = performance_analyzer.analyze_performance(changed_files)

        # Analyze quality
        quality_result = quality_analyzer.analyze_code_quality(changed_files)

        # Calculate overall risk score
        risk_score = self._calculate_overall_risk(
            impact_result, security_result, performance_result, quality_result
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            impact_result, security_result, performance_result, quality_result
        )

        return PRAnalysis(
            impact_summary=impact_result.__dict__ if hasattr(impact_result, '__dict__') else {},
            security_issues=security_result.get('issues', []),
            performance_issues=performance_result.get('issues', []),
            quality_issues=quality_result.get('issues', []),
            risk_score=risk_score,
            recommendations=recommendations
        )

    def generate_pr_comment(self, analysis: PRAnalysis, pr_number: int) -> str:
        """Generate comprehensive PR comment."""
        comment_lines = [
            "# 🤖 AI Mentor Analysis",
            "",
            f"**Analysis completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Risk Score:** {'🔴' if analysis.risk_score > 0.7 else '🟡' if analysis.risk_score > 0.3 else '🟢'} {analysis.risk_score:.2f}/1.0",
            "",
            "## 📊 Impact Summary",
            ""
        ]

        # Impact summary
        impact = analysis.impact_summary
        if impact:
            comment_lines.extend([
                f"- **Files affected:** {len(impact.get('affected_files', []))}",
                f"- **Symbols affected:** {len(impact.get('affected_symbols', []))}",
                f"- **Tests affected:** {len(impact.get('affected_tests', []))}",
                f"- **URLs affected:** {len(impact.get('affected_urls', []))}",
                ""
            ])

        # Security Issues
        if analysis.security_issues:
            comment_lines.extend([
                "## 🔒 Security Issues",
                ""
            ])

            critical_security = [i for i in analysis.security_issues if i.get('severity') == 'critical']
            high_security = [i for i in analysis.security_issues if i.get('severity') == 'high']

            if critical_security:
                comment_lines.extend([
                    "### ⚠️ Critical Issues",
                    ""
                ])
                for issue in critical_security[:3]:  # Limit to top 3
                    comment_lines.append(f"- **{issue.get('type', 'Unknown')}**: {issue.get('description', 'No description')}")

            if high_security:
                comment_lines.extend([
                    "",
                    "### 🔴 High Priority Issues",
                    ""
                ])
                for issue in high_security[:3]:  # Limit to top 3
                    comment_lines.append(f"- **{issue.get('type', 'Unknown')}**: {issue.get('description', 'No description')}")

            comment_lines.append("")

        # Performance Issues
        if analysis.performance_issues:
            comment_lines.extend([
                "## ⚡ Performance Issues",
                ""
            ])

            for issue in analysis.performance_issues[:5]:  # Limit to top 5
                severity_emoji = "🔴" if issue.get('severity') == 'high' else "🟡" if issue.get('severity') == 'medium' else "🔵"
                comment_lines.append(f"- {severity_emoji} **{issue.get('type', 'Unknown')}**: {issue.get('description', 'No description')}")

            comment_lines.append("")

        # Quality Issues
        if analysis.quality_issues:
            comment_lines.extend([
                "## 📈 Code Quality",
                ""
            ])

            major_quality = [i for i in analysis.quality_issues if i.get('severity') == 'major']
            if major_quality:
                comment_lines.extend([
                    "### Major Issues",
                    ""
                ])
                for issue in major_quality[:3]:  # Limit to top 3
                    comment_lines.append(f"- **{issue.get('type', 'Unknown')}**: {issue.get('description', 'No description')}")

            comment_lines.append("")

        # Breaking Changes
        breaking_changes = impact.get('breaking_changes', [])
        if breaking_changes:
            comment_lines.extend([
                "## 💥 Breaking Changes",
                ""
            ])

            for change in breaking_changes[:3]:  # Limit to top 3
                comment_lines.append(f"- **{change.get('type', 'Unknown')}**: {change.get('description', 'No description')}")

            comment_lines.append("")

        # Migration Requirements
        if impact.get('migration_required'):
            comment_lines.extend([
                "## 🔄 Database Migrations Required",
                "",
                "This PR requires database migrations. Please ensure:",
                ""
            ])

            for suggestion in impact.get('migration_suggestions', [])[:3]:
                comment_lines.append(f"- {suggestion}")

            comment_lines.append("")

        # Recommendations
        if analysis.recommendations:
            comment_lines.extend([
                "## 🎯 Recommendations",
                ""
            ])

            for rec in analysis.recommendations[:5]:  # Limit to top 5
                comment_lines.append(f"- {rec}")

            comment_lines.append("")

        # Test Coverage
        test_gaps = impact.get('test_coverage_gaps', [])
        if test_gaps:
            comment_lines.extend([
                "## 🧪 Test Coverage Gaps",
                ""
            ])

            for gap in test_gaps[:3]:  # Limit to top 3
                comment_lines.append(f"- {gap}")

            comment_lines.append("")

        # Review Checklist
        comment_lines.extend([
            "## ✅ Review Checklist",
            "",
            "- [ ] Security implications reviewed",
            "- [ ] Performance impact assessed",
            "- [ ] Breaking changes documented",
            "- [ ] Tests updated/added",
            "- [ ] Documentation updated",
            ""
        ])

        if analysis.risk_score > 0.7:
            comment_lines.extend([
                "- [ ] **HIGH RISK**: Architect review required",
                "- [ ] **HIGH RISK**: Staging deployment test completed",
                ""
            ])
        elif analysis.risk_score > 0.3:
            comment_lines.extend([
                "- [ ] Lead developer review completed",
                ""
            ])

        comment_lines.extend([
            "---",
            f"*Generated by AI Mentor System v1.0 | [View Analysis Details](#{pr_number})*"
        ])

        return "\n".join(comment_lines)

    def post_pr_comment(self, comment: str, pr_number: int, repo_owner: str, repo_name: str) -> bool:
        """Post comment to GitHub PR."""
        if not self.github_token:
            print("No GitHub token provided, saving comment locally")
            self._save_comment_locally(comment)
            return True

        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"

        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }

        data = {
            'body': comment
        }

        try:
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 201:
                print(f"Successfully posted comment to PR #{pr_number}")
                return True
            else:
                print(f"Failed to post comment: {response.status_code} - {response.text}")
                self._save_comment_locally(comment)
                return False

        except (requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            print(f"Error posting comment: {e}")
            self._save_comment_locally(comment)
            return False

    def _get_pr_files(self, pr_number: int, repo_owner: str, repo_name: str) -> List[str]:
        """Get list of files changed in PR."""
        if not self.github_token:
            # Fallback to git diff for local testing
            return self._get_files_from_git_diff()

        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files"

        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                files_data = response.json()
                return [file_info['filename'] for file_info in files_data]
            else:
                print(f"Failed to get PR files: {response.status_code}")
                return []

        except (requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            print(f"Error getting PR files: {e}")
            return []

    def _get_files_from_git_diff(self) -> List[str]:
        """Get changed files from git diff as fallback."""
        import subprocess

        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]

        except (requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            print(f"Error getting git diff: {e}")

        return []

    def _calculate_overall_risk(self, impact_result, security_result, performance_result, quality_result) -> float:
        """Calculate overall risk score."""
        risk_factors = []

        # Impact risk
        if hasattr(impact_result, 'severity'):
            severity_map = {'low': 0.2, 'medium': 0.5, 'high': 0.8, 'critical': 1.0}
            risk_factors.append(severity_map.get(impact_result.severity.value, 0.5))

        # Security risk
        security_issues = security_result.get('issues', [])
        if security_issues:
            critical_security = len([i for i in security_issues if i.get('severity') == 'critical'])
            high_security = len([i for i in security_issues if i.get('severity') == 'high'])
            security_risk = min((critical_security * 0.4 + high_security * 0.2), 1.0)
            risk_factors.append(security_risk)

        # Performance risk
        performance_issues = performance_result.get('issues', [])
        if performance_issues:
            high_perf = len([i for i in performance_issues if i.get('severity') == 'high'])
            performance_risk = min(high_perf * 0.3, 0.8)
            risk_factors.append(performance_risk)

        # Quality risk (lower weight)
        quality_issues = quality_result.get('issues', [])
        if quality_issues:
            critical_quality = len([i for i in quality_issues if i.get('severity') == 'critical'])
            quality_risk = min(critical_quality * 0.2, 0.6)
            risk_factors.append(quality_risk)

        # Return average risk if factors exist, otherwise low risk
        return sum(risk_factors) / len(risk_factors) if risk_factors else 0.1

    def _generate_recommendations(self, impact_result, security_result, performance_result, quality_result) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Security recommendations
        security_issues = security_result.get('issues', [])
        critical_security = [i for i in security_issues if i.get('severity') == 'critical']
        if critical_security:
            recommendations.append("🔴 **CRITICAL**: Address security vulnerabilities before merging")

        # Performance recommendations
        performance_issues = performance_result.get('issues', [])
        n_plus_one = [i for i in performance_issues if 'n_plus_one' in i.get('type', '').lower()]
        if n_plus_one:
            recommendations.append("⚡ Add select_related/prefetch_related to prevent N+1 queries")

        # Breaking changes
        if hasattr(impact_result, 'breaking_changes') and impact_result.breaking_changes:
            recommendations.append("💥 Document breaking changes and update version appropriately")

        # Migration recommendations
        if hasattr(impact_result, 'migration_required') and impact_result.migration_required:
            recommendations.append("🔄 Test migrations on staging environment before production")

        # Quality recommendations
        quality_issues = quality_result.get('issues', [])
        if quality_issues:
            recommendations.append("📈 Address code quality issues to improve maintainability")

        # Default recommendations if none specific
        if not recommendations:
            recommendations.extend([
                "✅ Code looks good! Consider adding tests if coverage is low",
                "📚 Update documentation if public APIs changed"
            ])

        return recommendations

    def _save_comment_locally(self, comment: str):
        """Save comment locally as fallback."""
        import os
        from pathlib import Path

        mentor_dir = Path('.mentor')
        mentor_dir.mkdir(exist_ok=True)

        comment_file = mentor_dir / 'pr_comment.md'
        with open(comment_file, 'w', encoding='utf-8') as f:
            f.write(comment)

        print(f"Comment saved to: {comment_file}")

    def update_pr_status(self, pr_number: int, repo_owner: str, repo_name: str,
                        state: str, description: str, context: str = "mentor/analysis") -> bool:
        """Update PR status check."""
        if not self.github_token:
            return False

        # Get the latest commit SHA
        pr_url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        try:
            pr_response = requests.get(pr_url, headers=headers)
            if pr_response.status_code != 200:
                return False

            pr_data = pr_response.json()
            commit_sha = pr_data['head']['sha']

            # Update status
            status_url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/statuses/{commit_sha}"

            status_data = {
                'state': state,  # 'pending', 'success', 'error', 'failure'
                'description': description,
                'context': context
            }

            status_response = requests.post(status_url, headers=headers, json=status_data)
            return status_response.status_code == 201

        except (FileNotFoundError, IOError, OSError, PermissionError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            print(f"Error updating PR status: {e}")
            return False