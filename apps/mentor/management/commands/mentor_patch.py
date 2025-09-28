"""
mentor_patch management command for the AI Mentor system.

This command generates and applies code patches based on analysis
results or natural language requests with safety validation.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from apps.mentor.analyzers.performance_analyzer import PerformanceAnalyzer
from apps.mentor.analyzers.impact_analyzer import ImpactAnalyzer, ChangeType
from apps.mentor.guards.scope_controller import ScopeController
from apps.mentor.guards.migration_safety import MigrationSafetyChecker
from apps.mentor.guards.rollback_manager import RollbackManager
from apps.mentor.guards.write_policy import get_write_policy, WriteRequest


@dataclass
class PatchRequest:
    """Represents a patch generation request."""
    request: str
    scope: Optional[List[str]] = None
    patch_type: str = 'improvement'  # improvement, security, performance, bugfix
    target_files: Optional[List[str]] = None
    dry_run: bool = True
    create_branch: bool = True
    auto_test: bool = True


class PatchOrchestrator:
    """Orchestrates the patch generation and application process."""

    def __init__(self):
        self.patch_generator = PatchGenerator()
        self.security_scanner = SecurityScanner()
        self.performance_analyzer = PerformanceAnalyzer()
        self.impact_analyzer = ImpactAnalyzer()
        self.scope_controller = ScopeController()
        self.migration_checker = MigrationSafetyChecker()
        self.rollback_manager = RollbackManager()

    def generate_patches(self, request: PatchRequest) -> List[CodePatch]:
        """Generate patches based on the request."""
        patches = []

        if request.patch_type == 'security':
            patches.extend(self._generate_security_patches(request))
        elif request.patch_type == 'performance':
            patches.extend(self._generate_performance_patches(request))
        elif request.patch_type == 'bugfix':
            patches.extend(self._generate_bugfix_patches(request))
        else:
            patches.extend(self._generate_improvement_patches(request))

        return patches

    def apply_patches(self, patches: List[CodePatch], dry_run: bool = True,
                     create_branch: bool = True) -> Dict[str, Any]:
        """Apply patches with safety checks and rollback capability."""
        results = {
            'applied': [],
            'failed': [],
            'rollback_id': None,
            'branch_created': None,
            'impact_analysis': None
        }

        if not patches:
            return results

        try:
            # Run impact analysis on all patches before applying
            file_paths = list(set(patch.file_path for patch in patches))
            impact_result = self.impact_analyzer.analyze_changes(file_paths, ChangeType.MODIFIED)
            results['impact_analysis'] = {
                'affected_files': list(impact_result.affected_files),
                'affected_symbols': list(impact_result.affected_symbols),
                'breaking_changes': impact_result.breaking_changes,
                'severity': impact_result.severity.value,
                'confidence': impact_result.confidence,
                'test_coverage_gaps': impact_result.test_coverage_gaps
            }

            # Check if impact analysis reveals critical risks
            if impact_result.severity.value == 'critical' and not dry_run:
                results['failed'].append({
                    'file': 'batch_validation',
                    'reason': 'Critical impact detected - manual review required',
                    'patch': 'Impact analysis shows critical severity'
                })
                return results

            # Create rollback point
            if not dry_run:
                rollback_id = self.rollback_manager.create_rollback_point(
                    reason=f"Patches application - {len(patches)} patches - Impact: {impact_result.severity.value}"
                )
                results['rollback_id'] = rollback_id

            # Create branch if requested
            branch_name = None
            if create_branch and not dry_run:
                branch_name = f"mentor/patches-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
                self._create_git_branch(branch_name)
                results['branch_created'] = branch_name

            # Apply patches one by one with enhanced validation
            for patch in patches:
                try:
                    # Enhanced safety validation including impact analysis
                    safety_result = self._validate_patch_safety_with_impact(patch, impact_result)
                    if safety_result['allowed']:
                        if not dry_run:
                            self._apply_single_patch(patch)
                        results['applied'].append({
                            'file': patch.file_path,
                            'type': patch.type.value,
                            'priority': patch.priority.value,
                            'description': patch.description,
                            'risk_assessment': safety_result.get('risk_assessment')
                        })
                    else:
                        results['failed'].append({
                            'file': patch.file_path,
                            'reason': safety_result.get('reason', 'Safety validation failed'),
                            'patch': patch.description,
                            'violations': safety_result.get('violations', [])
                        })
                except (TypeError, ValidationError, ValueError) as e:
                    results['failed'].append({
                        'file': patch.file_path,
                        'reason': str(e),
                        'patch': patch.description
                    })

        except (TypeError, ValidationError, ValueError) as e:
            # If something goes wrong, rollback if we created a rollback point
            if results.get('rollback_id') and not dry_run:
                self.rollback_manager.rollback(results['rollback_id'])
            raise

        return results

    def _generate_security_patches(self, request: PatchRequest) -> List[CodePatch]:
        """Generate security-focused patches."""
        patches = []

        # Get security issues from scanner
        files_to_scan = request.target_files or self._get_files_in_scope(request.scope)

        for file_path in files_to_scan:
            if not Path(file_path).exists():
                continue

            try:
                file_content = Path(file_path).read_text()
                security_issues = self.security_scanner.scan_file(file_path, file_content)

                for issue in security_issues:
                    patch = self.patch_generator.generate_security_fix(
                        file_path=file_path,
                        vulnerability=issue,
                        line_number=issue.get('line_number', 1)
                    )
                    if patch:
                        patches.append(patch)

            except (TypeError, ValidationError, ValueError) as e:
                print(f"Warning: Could not scan {file_path}: {e}")

        return patches

    def _generate_performance_patches(self, request: PatchRequest) -> List[CodePatch]:
        """Generate performance optimization patches."""
        patches = []

        files_to_analyze = request.target_files or self._get_files_in_scope(request.scope)

        for file_path in files_to_analyze:
            if not Path(file_path).exists():
                continue

            try:
                file_content = Path(file_path).read_text()
                performance_issues = self.performance_analyzer.analyze_file(file_path, file_content)

                for issue in performance_issues:
                    patch = self.patch_generator.generate_performance_optimization(
                        file_path=file_path,
                        issue=issue,
                        line_number=issue.get('line_number', 1)
                    )
                    if patch:
                        patches.append(patch)

            except (TypeError, ValidationError, ValueError) as e:
                print(f"Warning: Could not analyze {file_path}: {e}")

        return patches

    def _generate_bugfix_patches(self, request: PatchRequest) -> List[CodePatch]:
        """Generate patches for known bug patterns."""
        patches = []

        # Common Django bug patterns
        bug_patterns = [
            {
                'pattern': r'\.objects\.get\(',
                'description': 'Potential DoesNotExist exception',
                'fix': 'get_or_404 or try/except'
            },
            {
                'pattern': r'request\.GET\[',
                'description': 'Unhandled KeyError on missing parameter',
                'fix': 'request.GET.get() with default'
            },
            {
                'pattern': r'\.save\(\)$',
                'description': 'Missing transaction handling',
                'fix': 'Wrap in transaction.atomic()'
            }
        ]

        files_to_check = request.target_files or self._get_files_in_scope(request.scope)

        for file_path in files_to_check:
            if not Path(file_path).exists() or not file_path.endswith('.py'):
                continue

            try:
                file_content = Path(file_path).read_text()

                for pattern_info in bug_patterns:
                    import re
                    matches = list(re.finditer(pattern_info['pattern'], file_content, re.MULTILINE))

                    for match in matches:
                        line_number = file_content[:match.start()].count('\n') + 1
                        patch = self.patch_generator.generate_pattern_fix(
                            file_path=file_path,
                            pattern=pattern_info['pattern'],
                            fix_description=pattern_info['description'],
                            line_number=line_number
                        )
                        if patch:
                            patches.append(patch)

            except (TypeError, ValidationError, ValueError) as e:
                print(f"Warning: Could not check {file_path}: {e}")

        return patches

    def _generate_improvement_patches(self, request: PatchRequest) -> List[CodePatch]:
        """Generate general code improvement patches."""
        patches = []

        # Code quality improvements
        improvements = [
            {
                'pattern': r'except:',
                'description': 'Bare except clause',
                'fix': 'Specify exception type'
            },
            {
                'pattern': r'print\(',
                'description': 'Print statement in production code',
                'fix': 'Use logging instead'
            },
            {
                'pattern': r'import \*',
                'description': 'Wildcard import',
                'fix': 'Import specific modules'
            }
        ]

        files_to_improve = request.target_files or self._get_files_in_scope(request.scope)

        for file_path in files_to_improve:
            if not Path(file_path).exists() or not file_path.endswith('.py'):
                continue

            try:
                file_content = Path(file_path).read_text()

                for improvement in improvements:
                    import re
                    matches = list(re.finditer(improvement['pattern'], file_content, re.MULTILINE))

                    for match in matches:
                        line_number = file_content[:match.start()].count('\n') + 1
                        patch = self.patch_generator.generate_code_improvement(
                            file_path=file_path,
                            issue_description=improvement['description'],
                            line_number=line_number
                        )
                        if patch:
                            patches.append(patch)

            except (TypeError, ValidationError, ValueError) as e:
                print(f"Warning: Could not improve {file_path}: {e}")

        return patches

    def _get_files_in_scope(self, scope: Optional[List[str]]) -> List[str]:
        """Get all Python files in the specified scope."""
        if not scope:
            scope = ['apps/']

        files = []
        for scope_path in scope:
            if os.path.isfile(scope_path):
                files.append(scope_path)
            else:
                # Directory - find all Python files
                for root, dirs, file_list in os.walk(scope_path):
                    for file_name in file_list:
                        if file_name.endswith('.py'):
                            files.append(os.path.join(root, file_name))

        return files

    def _validate_patch_safety(self, patch: CodePatch) -> bool:
        """Validate that a patch is safe to apply."""
        try:
            # First check with centralized write policy
            write_policy = get_write_policy()
            content_size = len(patch.modified_code.encode('utf-8')) if patch.modified_code else 0

            write_request = WriteRequest(
                operation_type='modify',
                file_path=patch.file_path,
                content_size=content_size,
                content_preview=patch.modified_code[:500] if patch.modified_code else None
            )

            policy_result = write_policy.validate_write(write_request)
            if not policy_result.allowed:
                # Log the specific violations for debugging
                for violation in policy_result.violations:
                    print(f"Write policy violation: {violation['message']}")
                return False

            # Check scope constraints (this now also uses WritePolicy internally)
            if not self.scope_controller.is_patch_allowed(patch):
                return False

            # Check file exists (or is being created in allowed area)
            file_path = Path(patch.file_path)
            if file_path.exists():
                # Existing file - check if writable
                if not os.access(file_path, os.W_OK):
                    return False
            else:
                # New file - WritePolicy already validated the path is allowed
                pass

            # For migrations, check safety
            if 'migration' in patch.file_path.lower():
                safety_checks = self.migration_checker.validate_migration_safety(
                    patch.file_path, {'operations': []}
                )
                dangerous_checks = [c for c in safety_checks if c.level.value == 'DANGEROUS']
                if dangerous_checks:
                    return False

            return True

        except (TypeError, ValidationError, ValueError) as e:
            print(f"Patch safety validation failed: {e}")
            return False

    def _validate_patch_safety_with_impact(self, patch: CodePatch, impact_result) -> Dict[str, Any]:
        """Enhanced patch safety validation that includes impact analysis."""
        result = {
            'allowed': True,
            'reason': None,
            'violations': [],
            'risk_assessment': {}
        }

        try:
            # First run standard safety validation
            if not self._validate_patch_safety(patch):
                result['allowed'] = False
                result['reason'] = 'Standard safety validation failed'
                return result

            # Check if this patch affects files with breaking changes
            if impact_result and impact_result.breaking_changes:
                for breaking_change in impact_result.breaking_changes:
                    if breaking_change.get('file_path') == patch.file_path:
                        result['risk_assessment']['has_breaking_changes'] = True
                        result['risk_assessment']['breaking_change_type'] = breaking_change.get('type')

                        # For critical breaking changes, require manual approval
                        if breaking_change.get('severity') == 'critical':
                            result['allowed'] = False
                            result['reason'] = f"Critical breaking change detected: {breaking_change.get('description')}"
                            result['violations'].append({
                                'type': 'critical_breaking_change',
                                'message': breaking_change.get('description'),
                                'requires_manual_review': True
                            })
                            return result

            # Check if patch is in high-impact file
            if impact_result and patch.file_path in impact_result.affected_files:
                downstream_effects = len([f for f in impact_result.affected_files
                                        if f != patch.file_path])
                result['risk_assessment']['downstream_files_affected'] = downstream_effects

                # If many files affected, increase caution
                if downstream_effects > 10:
                    result['risk_assessment']['high_blast_radius'] = True
                    if impact_result.confidence < 0.7:
                        result['allowed'] = False
                        result['reason'] = 'High blast radius with low confidence - manual review required'
                        return result

            # Check test coverage for affected areas
            if impact_result and impact_result.test_coverage_gaps:
                relevant_gaps = [gap for gap in impact_result.test_coverage_gaps
                               if patch.file_path in gap]
                if relevant_gaps:
                    result['risk_assessment']['test_coverage_gaps'] = len(relevant_gaps)
                    result['violations'].append({
                        'type': 'test_coverage_gap',
                        'message': f"Limited test coverage for {patch.file_path}",
                        'recommendation': 'Add tests before applying patch'
                    })

            # Assess overall patch risk level based on impact
            risk_score = self._calculate_patch_risk_score(patch, impact_result)
            result['risk_assessment']['risk_score'] = risk_score
            result['risk_assessment']['risk_level'] = self._get_risk_level(risk_score)

            # Block extremely high-risk patches unless explicitly allowed
            if risk_score > 8.0 and not os.getenv('MENTOR_ALLOW_HIGH_RISK_PATCHES', 'false').lower() == 'true':
                result['allowed'] = False
                result['reason'] = f'Extremely high risk score ({risk_score:.1f}) - manual approval required'

            return result

        except (TypeError, ValidationError, ValueError) as e:
            print(f"Enhanced patch validation failed: {e}")
            result['allowed'] = False
            result['reason'] = f'Validation error: {str(e)}'
            return result

    def _calculate_patch_risk_score(self, patch: CodePatch, impact_result) -> float:
        """Calculate a numerical risk score for a patch based on multiple factors."""
        risk_score = 0.0

        # Base risk from patch priority
        priority_scores = {
            'LOW': 1.0,
            'MEDIUM': 3.0,
            'HIGH': 6.0,
            'CRITICAL': 9.0
        }
        risk_score += priority_scores.get(patch.priority.value, 3.0)

        # Risk from confidence level (inverse relationship)
        confidence_penalty = (1.0 - patch.confidence) * 3.0
        risk_score += confidence_penalty

        # Risk from impact analysis
        if impact_result:
            # Breaking changes add significant risk
            breaking_changes_in_file = [bc for bc in impact_result.breaking_changes
                                      if bc.get('file_path') == patch.file_path]
            risk_score += len(breaking_changes_in_file) * 2.0

            # High downstream impact adds risk
            if patch.file_path in impact_result.affected_files:
                downstream_count = len(impact_result.affected_files) - 1
                risk_score += min(downstream_count * 0.2, 2.0)  # Cap at 2.0

            # Test coverage gaps add risk
            coverage_gaps = len([gap for gap in impact_result.test_coverage_gaps
                               if patch.file_path in gap])
            risk_score += coverage_gaps * 0.5

        # Risk from file type
        if 'models.py' in patch.file_path:
            risk_score += 1.5  # Model changes are riskier
        elif 'settings' in patch.file_path:
            risk_score += 3.0  # Settings changes are very risky
        elif '/migrations/' in patch.file_path:
            risk_score += 2.0  # Migration changes are risky

        return min(risk_score, 10.0)  # Cap at 10.0

    def _get_risk_level(self, risk_score: float) -> str:
        """Convert numerical risk score to categorical risk level."""
        if risk_score >= 8.0:
            return 'critical'
        elif risk_score >= 6.0:
            return 'high'
        elif risk_score >= 3.0:
            return 'medium'
        else:
            return 'low'

    def _apply_single_patch(self, patch: CodePatch):
        """Apply a single patch to the file."""
        file_path = Path(patch.file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {patch.file_path}")

        # Read current content
        current_content = file_path.read_text()

        # Apply the patch
        if patch.original_code and patch.modified_code:
            # Replace specific code block
            if patch.original_code in current_content:
                modified_content = current_content.replace(
                    patch.original_code,
                    patch.modified_code,
                    1  # Replace only first occurrence
                )
            else:
                raise ValueError(f"Original code not found in {patch.file_path}")
        else:
            # Line-based insertion
            lines = current_content.split('\n')
            if patch.line_start <= len(lines):
                lines.insert(patch.line_start - 1, patch.modified_code)
                modified_content = '\n'.join(lines)
            else:
                raise ValueError(f"Invalid line number {patch.line_start} in {patch.file_path}")

        # Write modified content
        file_path.write_text(modified_content)

    def _create_git_branch(self, branch_name: str):
        """Create a new git branch for the patches."""
        try:
            subprocess.run(['git', 'checkout', '-b', branch_name],
                         check=True, capture_output=True, cwd=settings.BASE_DIR)
        except subprocess.CalledProcessError as e:
            raise CommandError(f"Failed to create branch {branch_name}: {e}")


class Command(BaseCommand):
    help = 'Generate and apply code patches based on analysis or requests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--request',
            type=str,
            help='Natural language description of patches to generate'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['security', 'performance', 'bugfix', 'improvement'],
            default='improvement',
            help='Type of patches to generate'
        )
        parser.add_argument(
            '--scope',
            type=str,
            nargs='*',
            help='Limit patching to specific files or directories'
        )
        parser.add_argument(
            '--files',
            type=str,
            nargs='*',
            help='Specific files to patch'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=True,
            help='Show what patches would be applied without applying them'
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply the patches (overrides --dry-run)'
        )
        parser.add_argument(
            '--branch',
            type=str,
            help='Create patches on a new git branch'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['summary', 'detailed', 'diff'],
            default='summary',
            help='Output format'
        )
        parser.add_argument(
            '--auto-test',
            action='store_true',
            default=True,
            help='Run tests after applying patches'
        )

    def handle(self, *args, **options):
        request_text = options.get('request', 'General code improvements')
        patch_type = options['type']
        scope = options.get('scope')
        target_files = options.get('files')
        dry_run = not options.get('apply', False)  # Default to dry-run unless --apply
        branch_name = options.get('branch')
        output_format = options['format']
        auto_test = options.get('auto_test', True)

        self.stdout.write(f"🔧 Generating {patch_type} patches...")
        if request_text:
            self.stdout.write(f"Request: {request_text}")

        try:
            # Create patch request
            patch_request = PatchRequest(
                request=request_text,
                scope=scope,
                patch_type=patch_type,
                target_files=target_files,
                dry_run=dry_run,
                create_branch=bool(branch_name),
                auto_test=auto_test
            )

            # Generate patches
            orchestrator = PatchOrchestrator()
            patches = orchestrator.generate_patches(patch_request)

            if not patches:
                self.stdout.write(self.style.WARNING("⚠️  No patches generated"))
                return

            self.stdout.write(f"📝 Generated {len(patches)} patches")

            # Display patches
            self._display_patches(patches, output_format)

            # Apply patches if not dry run
            if not dry_run:
                self.stdout.write("🚀 Applying patches...")
                results = orchestrator.apply_patches(
                    patches,
                    dry_run=False,
                    create_branch=bool(branch_name)
                )

                self.stdout.write(f"✅ Applied {len(results['applied'])} patches")
                if results['failed']:
                    self.stdout.write(f"❌ Failed to apply {len(results['failed'])} patches")

                if results['branch_created']:
                    self.stdout.write(f"🌿 Created branch: {results['branch_created']}")

                if results['rollback_id']:
                    self.stdout.write(f"🔄 Rollback ID: {results['rollback_id']}")

                # Run tests if requested
                if auto_test and results['applied']:
                    self.stdout.write("🧪 Running tests...")
                    self._run_tests()

            else:
                self.stdout.write(self.style.WARNING("🔍 DRY RUN - No changes applied"))
                self.stdout.write("Use --apply to actually apply these patches")

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            raise CommandError(f"Patch generation failed: {e}")

    def _display_patches(self, patches: List[CodePatch], format_type: str):
        """Display the generated patches."""
        if format_type == 'summary':
            self._display_summary(patches)
        elif format_type == 'detailed':
            self._display_detailed(patches)
        elif format_type == 'diff':
            self._display_diff(patches)

    def _display_summary(self, patches: List[CodePatch]):
        """Display patch summary."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("PATCH SUMMARY")
        self.stdout.write("="*60)

        for i, patch in enumerate(patches, 1):
            self.stdout.write(f"{i:2d}. {patch.description}")
            self.stdout.write(f"    File: {patch.file_path}")
            self.stdout.write(f"    Type: {patch.type.value} | Priority: {patch.priority.value}")
            if patch.line_start:
                self.stdout.write(f"    Line: {patch.line_start}")
            self.stdout.write("")

    def _display_detailed(self, patches: List[CodePatch]):
        """Display detailed patch information."""
        for i, patch in enumerate(patches, 1):
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"PATCH {i}: {patch.description}")
            self.stdout.write(f"{'='*60}")
            self.stdout.write(f"File: {patch.file_path}")
            self.stdout.write(f"Type: {patch.type.value}")
            self.stdout.write(f"Priority: {patch.priority.value}")

            if patch.line_start:
                self.stdout.write(f"Line: {patch.line_start}-{patch.line_end}")

            if patch.original_code:
                self.stdout.write("\nORIGINAL:")
                self.stdout.write("-" * 40)
                self.stdout.write(patch.original_code)

            if patch.modified_code:
                self.stdout.write("\nMODIFIED:")
                self.stdout.write("-" * 40)
                self.stdout.write(patch.modified_code)

            if patch.dependencies:
                self.stdout.write(f"\nDependencies: {', '.join(patch.dependencies)}")

    def _display_diff(self, patches: List[CodePatch]):
        """Display patches in diff format."""
        for patch in patches:
            if patch.original_code and patch.modified_code:
                self.stdout.write(f"\n--- {patch.file_path}")
                self.stdout.write(f"+++ {patch.file_path}")
                self.stdout.write("@@ -1,1 +1,1 @@")
                self.stdout.write(f"-{patch.original_code}")
                self.stdout.write(f"+{patch.modified_code}")

    def _run_tests(self):
        """Run tests after applying patches."""
        try:
            # Run a focused test suite
            result = subprocess.run(
                ['python', 'manage.py', 'test', '--keepdb', '--parallel'],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("✅ All tests passed"))
            else:
                self.stdout.write(self.style.ERROR("❌ Some tests failed"))
                self.stdout.write("Test output:")
                self.stdout.write(result.stdout)
                if result.stderr:
                    self.stdout.write("Errors:")
                    self.stdout.write(result.stderr)

        except subprocess.TimeoutExpired:
            self.stdout.write(self.style.WARNING("⏱️  Tests timed out"))
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Test execution failed: {e}"))