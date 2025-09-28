"""
Enhanced GitHub bot integration for AI Mentor system.

This module provides:
- Automated PR creation with AI analysis
- Code review comments with suggestions
- Status checks integration
- Issue analysis and planning
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from django.conf import settings


@dataclass
class PRAnalysis:
    """Analysis of a pull request."""
    pr_number: int
    files_changed: List[str]
    lines_added: int
    lines_deleted: int
    risk_assessment: str
    impact_analysis: Dict[str, Any]
    suggested_tests: List[str]
    security_concerns: List[str]
    performance_implications: List[str]
    breaking_changes: List[str]
    ai_confidence: float


@dataclass
class CodeReviewComment:
    """AI-generated code review comment."""
    file_path: str
    line_number: int
    comment_type: str  # 'suggestion', 'warning', 'info', 'critical'
    title: str
    message: str
    suggested_code: Optional[str] = None
    confidence: float = 0.8


class EnhancedGitHubBot:
    """Enhanced GitHub bot with AI analysis capabilities."""

    def __init__(self, repo_owner: str, repo_name: str, access_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.access_token = access_token
        self.base_url = "https://api.github.com"

    def analyze_pull_request(self, pr_number: int) -> PRAnalysis:
        """Perform comprehensive AI analysis of a pull request."""
        # Get PR details
        pr_data = self._get_pr_data(pr_number)
        files_changed = self._get_pr_files(pr_number)

        # Run impact analysis
        from apps.mentor.analyzers.impact_analyzer import ImpactAnalyzer, ChangeType
        analyzer = ImpactAnalyzer()

        file_paths = [f['filename'] for f in files_changed]
        impact_result = analyzer.analyze_changes(file_paths, ChangeType.MODIFIED)

        # Analyze security implications
        security_concerns = self._analyze_security_implications(files_changed)

        # Analyze performance implications
        performance_implications = self._analyze_performance_implications(files_changed)

        # Calculate overall risk
        risk_level = self._calculate_pr_risk(impact_result, security_concerns, performance_implications)

        # Generate test suggestions
        suggested_tests = self._suggest_tests(files_changed, impact_result)

        return PRAnalysis(
            pr_number=pr_number,
            files_changed=file_paths,
            lines_added=sum(f.get('additions', 0) for f in files_changed),
            lines_deleted=sum(f.get('deletions', 0) for f in files_changed),
            risk_assessment=risk_level,
            impact_analysis={
                'affected_files': list(impact_result.affected_files),
                'affected_symbols': list(impact_result.affected_symbols),
                'breaking_changes': impact_result.breaking_changes,
                'severity': impact_result.severity.value
            },
            suggested_tests=suggested_tests,
            security_concerns=security_concerns,
            performance_implications=performance_implications,
            breaking_changes=[bc['description'] for bc in impact_result.breaking_changes],
            ai_confidence=impact_result.confidence
        )

    def create_analysis_comment(self, analysis: PRAnalysis) -> str:
        """Create a comprehensive analysis comment for PR."""
        comment_parts = [
            "## 🤖 AI Mentor Analysis",
            "",
            f"**Overall Risk Assessment:** {analysis.risk_assessment.upper()}",
            f"**AI Confidence:** {analysis.ai_confidence:.1%}",
            "",
            "### 📊 Change Summary",
            f"- **Files Changed:** {len(analysis.files_changed)}",
            f"- **Lines Added:** +{analysis.lines_added}",
            f"- **Lines Deleted:** -{analysis.lines_deleted}",
            f"- **Affected Components:** {len(analysis.impact_analysis.get('affected_symbols', []))}",
            ""
        ]

        # Breaking Changes Section
        if analysis.breaking_changes:
            comment_parts.extend([
                "### ⚠️ Breaking Changes Detected",
                ""
            ])
            for change in analysis.breaking_changes:
                comment_parts.append(f"- {change}")
            comment_parts.append("")

        # Security Concerns Section
        if analysis.security_concerns:
            comment_parts.extend([
                "### 🔒 Security Analysis",
                ""
            ])
            for concern in analysis.security_concerns:
                comment_parts.append(f"- ⚠️ {concern}")
            comment_parts.append("")

        # Performance Implications Section
        if analysis.performance_implications:
            comment_parts.extend([
                "### ⚡ Performance Implications",
                ""
            ])
            for implication in analysis.performance_implications:
                comment_parts.append(f"- 📈 {implication}")
            comment_parts.append("")

        # Test Suggestions Section
        if analysis.suggested_tests:
            comment_parts.extend([
                "### 🧪 Suggested Tests",
                "",
                "Consider adding these tests to ensure the changes work correctly:",
                ""
            ])
            for test in analysis.suggested_tests:
                comment_parts.append(f"- [ ] {test}")
            comment_parts.append("")

        # Impact Analysis Section
        comment_parts.extend([
            "### 🎯 Impact Analysis",
            f"- **Affected Files:** {len(analysis.impact_analysis.get('affected_files', []))}",
            f"- **Affected Symbols:** {len(analysis.impact_analysis.get('affected_symbols', []))}",
            f"- **Impact Severity:** {analysis.impact_analysis.get('severity', 'unknown')}",
            ""
        ])

        # Recommendations Section
        comment_parts.extend([
            "### 💡 Recommendations",
            ""
        ])

        if analysis.risk_assessment in ['high', 'critical']:
            comment_parts.append("- 🔍 **Manual review recommended** due to high risk level")

        if analysis.breaking_changes:
            comment_parts.append("- 📋 **Update migration plan** to handle breaking changes")

        if len(analysis.files_changed) > 10:
            comment_parts.append("- 🔄 **Consider breaking into smaller PRs** for easier review")

        if analysis.ai_confidence < 0.7:
            comment_parts.append("- ⚠️ **Low AI confidence** - additional human review recommended")

        comment_parts.extend([
            "",
            "---",
            "*This analysis was generated by AI Mentor. Please review carefully and use your judgment.*"
        ])

        return "\n".join(comment_parts)

    def create_mentor_pr(self, branch_name: str, title: str, body: str,
                        mentor_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PR with AI Mentor context and analysis."""
        # Enhance PR body with mentor context
        enhanced_body = self._enhance_pr_body(body, mentor_context)

        # Create the PR
        pr_data = {
            'title': title,
            'body': enhanced_body,
            'head': branch_name,
            'base': 'main'  # or master, depending on repo
        }

        # In a real implementation, this would call GitHub API
        pr_response = self._mock_create_pr(pr_data)

        # Add AI analysis comment
        if pr_response.get('number'):
            analysis = self.analyze_pull_request(pr_response['number'])
            analysis_comment = self.create_analysis_comment(analysis)
            self._add_pr_comment(pr_response['number'], analysis_comment)

            # Set status checks
            self._set_status_checks(pr_response['number'], analysis)

        return pr_response

    def _enhance_pr_body(self, body: str, mentor_context: Dict[str, Any]) -> str:
        """Enhance PR body with mentor context information."""
        enhanced_parts = [body, ""]

        if mentor_context.get('plan_id'):
            enhanced_parts.extend([
                "## 🤖 AI Mentor Context",
                f"**Plan ID:** {mentor_context['plan_id']}",
                f"**Generated Steps:** {mentor_context.get('total_steps', 0)}",
                f"**Estimated Time:** {mentor_context.get('estimated_time', 0)} minutes",
                ""
            ])

        if mentor_context.get('impact_analysis'):
            impact = mentor_context['impact_analysis']
            enhanced_parts.extend([
                "## 📊 Impact Analysis",
                f"**Files Affected:** {len(impact.get('affected_files', []))}",
                f"**Symbols Affected:** {len(impact.get('affected_symbols', []))}",
                f"**Breaking Changes:** {len(impact.get('breaking_changes', []))}",
                f"**Severity:** {impact.get('severity', 'unknown')}",
                ""
            ])

        if mentor_context.get('patches_applied'):
            enhanced_parts.extend([
                "## 🔧 Patches Applied",
                f"**Total Patches:** {len(mentor_context['patches_applied'])}",
                ""
            ])
            for patch in mentor_context['patches_applied'][:5]:  # Show first 5
                enhanced_parts.append(f"- {patch.get('description', 'Unknown patch')}")

        enhanced_parts.extend([
            "",
            "---",
            "*This PR was created with assistance from AI Mentor*"
        ])

        return "\n".join(enhanced_parts)

    def generate_code_review_comments(self, pr_number: int) -> List[CodeReviewComment]:
        """Generate AI-powered code review comments."""
        files_changed = self._get_pr_files(pr_number)
        comments = []

        for file_data in files_changed:
            file_path = file_data['filename']
            patch_content = file_data.get('patch', '')

            # Analyze each file for potential issues
            file_comments = self._analyze_file_changes(file_path, patch_content)
            comments.extend(file_comments)

        return comments

    def _analyze_file_changes(self, file_path: str, patch_content: str) -> List[CodeReviewComment]:
        """Analyze changes in a specific file."""
        comments = []

        # Security analysis
        if self._has_security_patterns(patch_content):
            comments.append(CodeReviewComment(
                file_path=file_path,
                line_number=self._find_pattern_line(patch_content, r'eval\(|exec\('),
                comment_type='critical',
                title='Security Concern',
                message='This code uses eval() or exec() which can be dangerous. Consider safer alternatives.',
                confidence=0.9
            ))

        # Performance analysis
        if '/models.py' in file_path and 'ForeignKey' in patch_content:
            if 'select_related' not in patch_content and 'prefetch_related' not in patch_content:
                comments.append(CodeReviewComment(
                    file_path=file_path,
                    line_number=self._find_pattern_line(patch_content, r'ForeignKey'),
                    comment_type='suggestion',
                    title='Performance Optimization',
                    message='Consider using select_related() or prefetch_related() when accessing this ForeignKey to avoid N+1 queries.',
                    confidence=0.7
                ))

        # Code quality analysis
        if self._has_code_quality_issues(patch_content):
            comments.append(CodeReviewComment(
                file_path=file_path,
                line_number=self._find_pattern_line(patch_content, r'except:'),
                comment_type='warning',
                title='Code Quality',
                message='Bare except clauses can hide important errors. Consider catching specific exceptions.',
                suggested_code='except SpecificException:',
                confidence=0.8
            ))

        return comments

    def _has_security_patterns(self, content: str) -> bool:
        """Check for security-sensitive patterns."""
        patterns = [r'eval\(', r'exec\(', r'__import__', r'compile\(']
        return any(re.search(pattern, content) for pattern in patterns)

    def _has_code_quality_issues(self, content: str) -> bool:
        """Check for code quality issues."""
        patterns = [r'except:', r'print\(', r'import \*']
        return any(re.search(pattern, content) for pattern in patterns)

    def _find_pattern_line(self, content: str, pattern: str) -> int:
        """Find line number of pattern match."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                return i + 1
        return 1

    def _analyze_security_implications(self, files_changed: List[Dict[str, Any]]) -> List[str]:
        """Analyze security implications of file changes."""
        concerns = []

        for file_data in files_changed:
            file_path = file_data['filename']
            patch = file_data.get('patch', '')

            # Check for sensitive file modifications
            if any(sensitive in file_path for sensitive in ['settings.py', 'urls.py', 'middleware']):
                concerns.append(f"Sensitive file modified: {file_path}")

            # Check for security-related code patterns
            if re.search(r'(password|secret|key|token)\s*=', patch, re.IGNORECASE):
                concerns.append(f"Potential credential in {file_path}")

            # Check for authentication/authorization changes
            if re.search(r'(login|auth|permission|decorator)', patch, re.IGNORECASE):
                concerns.append(f"Authentication/authorization changes in {file_path}")

        return concerns

    def _analyze_performance_implications(self, files_changed: List[Dict[str, Any]]) -> List[str]:
        """Analyze performance implications of changes."""
        implications = []

        for file_data in files_changed:
            file_path = file_data['filename']
            patch = file_data.get('patch', '')

            # Check for database-related changes
            if '/models.py' in file_path:
                if 'Field(' in patch:
                    implications.append(f"Database schema changes in {file_path}")

            # Check for query-related changes
            if re.search(r'\.filter\(|\.get\(|\.all\(', patch):
                implications.append(f"Database query changes in {file_path}")

            # Check for view changes that might affect response time
            if '/views.py' in file_path and 'def ' in patch:
                implications.append(f"View logic changes in {file_path}")

        return implications

    def _calculate_pr_risk(self, impact_result, security_concerns: List[str],
                          performance_implications: List[str]) -> str:
        """Calculate overall PR risk level."""
        risk_score = 0

        # Risk from impact analysis
        if impact_result.severity.value == 'critical':
            risk_score += 4
        elif impact_result.severity.value == 'high':
            risk_score += 3
        elif impact_result.severity.value == 'medium':
            risk_score += 2
        else:
            risk_score += 1

        # Risk from breaking changes
        risk_score += len(impact_result.breaking_changes)

        # Risk from security concerns
        risk_score += len(security_concerns) * 2

        # Risk from performance implications
        risk_score += len(performance_implications)

        if risk_score >= 8:
            return 'critical'
        elif risk_score >= 5:
            return 'high'
        elif risk_score >= 3:
            return 'medium'
        else:
            return 'low'

    def _suggest_tests(self, files_changed: List[Dict[str, Any]], impact_result) -> List[str]:
        """Suggest tests based on file changes."""
        suggestions = []

        # Test suggestions based on file types
        for file_data in files_changed:
            file_path = file_data['filename']

            if '/models.py' in file_path:
                suggestions.append(f"Model tests for {file_path}")

            if '/views.py' in file_path:
                suggestions.append(f"View integration tests for {file_path}")

            if '/api/' in file_path:
                suggestions.append(f"API endpoint tests for {file_path}")

        # Test suggestions based on impact analysis
        if impact_result.breaking_changes:
            suggestions.append("Breaking change compatibility tests")

        if impact_result.migration_required:
            suggestions.append("Database migration tests")

        # Remove duplicates and limit
        return list(set(suggestions))[:10]

    def post_analysis_comment(self, pr_number: int, analysis: PRAnalysis):
        """Post AI analysis as a PR comment."""
        comment_body = self.create_analysis_comment(analysis)
        self._add_pr_comment(pr_number, comment_body)

    def set_status_checks(self, pr_number: int, analysis: PRAnalysis):
        """Set GitHub status checks based on analysis."""
        # Get latest commit SHA
        commit_sha = self._get_latest_commit_sha(pr_number)

        # AI Mentor Analysis Check
        self._create_status_check(
            commit_sha,
            'ai-mentor/analysis',
            'completed' if analysis.ai_confidence > 0.7 else 'failed',
            f'AI analysis complete (confidence: {analysis.ai_confidence:.1%})'
        )

        # Security Check
        security_status = 'failed' if analysis.security_concerns else 'completed'
        security_description = f"{len(analysis.security_concerns)} security concerns" if analysis.security_concerns else "No security issues detected"
        self._create_status_check(commit_sha, 'ai-mentor/security', security_status, security_description)

        # Breaking Changes Check
        breaking_status = 'failed' if analysis.breaking_changes else 'completed'
        breaking_description = f"{len(analysis.breaking_changes)} breaking changes" if analysis.breaking_changes else "No breaking changes"
        self._create_status_check(commit_sha, 'ai-mentor/breaking-changes', breaking_status, breaking_description)

        # Risk Assessment Check
        risk_status = 'failed' if analysis.risk_assessment in ['high', 'critical'] else 'completed'
        self._create_status_check(commit_sha, 'ai-mentor/risk-assessment', risk_status, f"Risk level: {analysis.risk_assessment}")

    def create_mentor_pr_from_plan(self, plan_data: Dict[str, Any], branch_name: str) -> Dict[str, Any]:
        """Create a PR from an AI Mentor plan."""
        # Generate PR title and body from plan
        title = f"AI Mentor: {plan_data.get('request', 'Code changes')}"

        body_parts = [
            "## 🤖 AI Mentor Generated Changes",
            "",
            f"**Original Request:** {plan_data.get('request', 'N/A')}",
            f"**Plan ID:** {plan_data.get('plan_id', 'N/A')}",
            "",
            "### Implementation Plan",
            ""
        ]

        # Add plan steps
        for i, step in enumerate(plan_data.get('steps', []), 1):
            body_parts.append(f"{i}. **{step.get('description', 'Unknown step')}**")
            body_parts.append(f"   - Type: {step.get('step_type', 'unknown')}")
            body_parts.append(f"   - Risk: {step.get('risk_level', 'unknown')}")
            body_parts.append(f"   - Time: {step.get('estimated_time', 0)} minutes")
            body_parts.append("")

        # Add impact analysis if available
        if plan_data.get('impact_analysis'):
            impact = plan_data['impact_analysis']
            body_parts.extend([
                "### Impact Analysis",
                f"- **Files Affected:** {len(impact.get('affected_files', []))}",
                f"- **Breaking Changes:** {len(impact.get('breaking_changes', []))}",
                f"- **Severity:** {impact.get('severity', 'unknown')}",
                f"- **Confidence:** {impact.get('confidence', 0):.1%}",
                ""
            ])

        body_parts.extend([
            "### Checklist",
            "- [ ] Code review completed",
            "- [ ] Tests added/updated",
            "- [ ] Documentation updated",
            "- [ ] Security review (if required)",
            "",
            "*Generated by AI Mentor System*"
        ])

        pr_body = "\n".join(body_parts)

        return self.create_mentor_pr(branch_name, title, pr_body, plan_data)

    # Mock GitHub API methods (replace with real API calls)
    def _get_pr_data(self, pr_number: int) -> Dict[str, Any]:
        """Mock: Get PR data from GitHub API."""
        return {
            'number': pr_number,
            'title': 'Sample PR',
            'body': 'Sample PR body',
            'head': {'sha': 'abc123'},
            'base': {'sha': 'def456'}
        }

    def _get_pr_files(self, pr_number: int) -> List[Dict[str, Any]]:
        """Mock: Get files changed in PR."""
        return [
            {
                'filename': 'apps/peoples/models.py',
                'additions': 15,
                'deletions': 3,
                'patch': '@@ -1,3 +1,3 @@\n class User(models.Model):\n+    avatar = models.ImageField()\n     name = models.CharField()'
            },
            {
                'filename': 'apps/peoples/views.py',
                'additions': 25,
                'deletions': 0,
                'patch': '@@ -1,3 +1,3 @@\n+def upload_avatar(request):\n+    # Implementation\n+    pass'
            }
        ]

    def _mock_create_pr(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock: Create PR via GitHub API."""
        return {
            'number': 123,
            'html_url': 'https://github.com/owner/repo/pull/123',
            'state': 'open'
        }

    def _add_pr_comment(self, pr_number: int, comment_body: str):
        """Mock: Add comment to PR."""
        print(f"Would add comment to PR #{pr_number}:")
        print(comment_body[:200] + "..." if len(comment_body) > 200 else comment_body)

    def _get_latest_commit_sha(self, pr_number: int) -> str:
        """Mock: Get latest commit SHA for PR."""
        return "abc123def456"

    def _create_status_check(self, commit_sha: str, context: str, status: str, description: str):
        """Mock: Create GitHub status check."""
        print(f"Status check: {context} = {status} ({description})")


class GitHubWebhookHandler:
    """Handler for GitHub webhooks."""

    def __init__(self, bot: EnhancedGitHubBot):
        self.bot = bot

    def handle_pull_request_opened(self, payload: Dict[str, Any]):
        """Handle PR opened webhook."""
        pr_number = payload['pull_request']['number']

        # Run analysis
        analysis = self.bot.analyze_pull_request(pr_number)

        # Post analysis comment
        self.bot.post_analysis_comment(pr_number, analysis)

        # Set status checks
        self.bot.set_status_checks(pr_number, analysis)

    def handle_push(self, payload: Dict[str, Any]):
        """Handle push webhook (could trigger reanalysis)."""
        # Get affected files from push
        commits = payload.get('commits', [])
        affected_files = set()

        for commit in commits:
            affected_files.update(commit.get('added', []))
            affected_files.update(commit.get('modified', []))

        # Could trigger incremental reindexing
        print(f"Push detected affecting {len(affected_files)} files")

    def handle_issue_opened(self, payload: Dict[str, Any]):
        """Handle new issue webhook (could suggest mentor plans)."""
        issue_title = payload['issue']['title']
        issue_body = payload['issue']['body']

        # Could analyze issue and suggest mentor plan
        if any(keyword in issue_title.lower() for keyword in ['bug', 'fix', 'error']):
            print(f"Bug report detected: {issue_title}")
            # Could automatically generate a mentor plan for the bug fix


# Global bot instance (configured from settings)
_github_bot = None

def get_github_bot() -> Optional[EnhancedGitHubBot]:
    """Get configured GitHub bot instance."""
    global _github_bot
    if _github_bot is None and hasattr(settings, 'GITHUB_BOT_CONFIG'):
        config = settings.GITHUB_BOT_CONFIG
        _github_bot = EnhancedGitHubBot(
            repo_owner=config['repo_owner'],
            repo_name=config['repo_name'],
            access_token=config['access_token']
        )
    return _github_bot