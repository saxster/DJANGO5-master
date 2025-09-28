"""
mentor_plan management command for the AI Mentor system.

This command takes natural language requests and generates structured
change plans with impacted files, required tests, and risk assessments.
"""

import json
import uuid
from typing import Dict, List, Set, Any, Optional
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class ChangeStep:
    """Represents a single step in a change plan."""

    def __init__(self, step_id: str, description: str, step_type: str,
                 target_files: List[str], dependencies: List[str] = None,
                 risk_level: str = 'low', estimated_time: int = 15):
        self.step_id = step_id
        self.description = description
        self.step_type = step_type  # create, modify, delete, test, migrate
        self.target_files = target_files
        self.dependencies = dependencies or []
        self.risk_level = risk_level  # low, medium, high, critical
        self.estimated_time = estimated_time  # minutes

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'description': self.description,
            'step_type': self.step_type,
            'target_files': self.target_files,
            'dependencies': self.dependencies,
            'risk_level': self.risk_level,
            'estimated_time': self.estimated_time
        }


class ChangePlan:
    """Represents a complete change plan."""

    def __init__(self, request: str, plan_id: str = None):
        self.plan_id = plan_id or str(uuid.uuid4())
        self.request = request
        self.steps: List[ChangeStep] = []
        self.impacted_files: Set[str] = set()
        self.required_tests: List[str] = []
        self.migration_needed = False
        self.overall_risk = 'low'
        self.estimated_total_time = 0
        self.prerequisites: List[str] = []
        self.rollback_plan: List[str] = []
        self.impact_analysis: Optional[ImpactResult] = None

    def add_step(self, step: ChangeStep):
        """Add a step to the plan."""
        self.steps.append(step)
        self.impacted_files.update(step.target_files)
        self.estimated_total_time += step.estimated_time

        # Update overall risk level
        risk_levels = ['low', 'medium', 'high', 'critical']
        current_risk_index = risk_levels.index(self.overall_risk)
        step_risk_index = risk_levels.index(step.risk_level)
        if step_risk_index > current_risk_index:
            self.overall_risk = step.risk_level

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'plan_id': self.plan_id,
            'request': self.request,
            'steps': [step.to_dict() for step in self.steps],
            'impacted_files': list(self.impacted_files),
            'required_tests': self.required_tests,
            'migration_needed': self.migration_needed,
            'overall_risk': self.overall_risk,
            'estimated_total_time': self.estimated_total_time,
            'prerequisites': self.prerequisites,
            'rollback_plan': self.rollback_plan,
            'created_at': timezone.now().isoformat()
        }

        # Include impact analysis if available
        if self.impact_analysis:
            result['impact_analysis'] = {
                'affected_files': list(self.impact_analysis.affected_files),
                'affected_symbols': list(self.impact_analysis.affected_symbols),
                'affected_tests': list(self.impact_analysis.affected_tests),
                'affected_urls': list(self.impact_analysis.affected_urls),
                'breaking_changes': self.impact_analysis.breaking_changes,
                'migration_required': self.impact_analysis.migration_required,
                'migration_suggestions': self.impact_analysis.migration_suggestions,
                'test_coverage_gaps': self.impact_analysis.test_coverage_gaps,
                'severity': self.impact_analysis.severity.value,
                'confidence': self.impact_analysis.confidence
            }

        return result


class PlanGenerator:
    """Generates structured change plans from natural language requests."""

    def __init__(self):
        self.impact_analyzer = ImpactAnalyzer()
        self.scope_controller = ScopeController()

    def generate_plan(self, request: str, scope: Optional[List[str]] = None) -> ChangePlan:
        """Generate a structured change plan from a natural language request."""
        plan = ChangePlan(request)

        # Analyze request intent and scope
        intent = self._analyze_request_intent(request)
        affected_areas = self._identify_affected_areas(request, scope)

        # Run impact analysis on likely affected files
        impact_result = self._analyze_change_impact(affected_areas, intent)

        # Generate plan steps based on intent and impact analysis
        if intent['type'] == 'feature':
            self._plan_feature_addition(plan, intent, affected_areas, impact_result)
        elif intent['type'] == 'bugfix':
            self._plan_bug_fix(plan, intent, affected_areas, impact_result)
        elif intent['type'] == 'refactor':
            self._plan_refactoring(plan, intent, affected_areas, impact_result)
        elif intent['type'] == 'security':
            self._plan_security_fix(plan, intent, affected_areas, impact_result)
        elif intent['type'] == 'performance':
            self._plan_performance_optimization(plan, intent, affected_areas, impact_result)
        else:
            self._plan_generic_change(plan, intent, affected_areas, impact_result)

        # Add impact-aware testing and safety steps
        self._add_impact_aware_testing_steps(plan, impact_result)
        self._add_safety_checks(plan)

        # Add migration steps if required
        if impact_result and impact_result.migration_required:
            self._add_migration_steps(plan, impact_result)

        # Generate rollback plan
        self._generate_rollback_plan(plan)

        # Store impact analysis in plan for UI display
        plan.impact_analysis = impact_result

        return plan

    def _analyze_request_intent(self, request: str) -> Dict[str, Any]:
        """Analyze the natural language request to determine intent."""
        request_lower = request.lower()

        # Simple keyword-based intent classification
        if any(word in request_lower for word in ['add', 'create', 'implement', 'new']):
            intent_type = 'feature'
        elif any(word in request_lower for word in ['fix', 'bug', 'error', 'issue']):
            intent_type = 'bugfix'
        elif any(word in request_lower for word in ['refactor', 'restructure', 'reorganize']):
            intent_type = 'refactor'
        elif any(word in request_lower for word in ['security', 'xss', 'sql injection', 'vulnerability']):
            intent_type = 'security'
        elif any(word in request_lower for word in ['performance', 'optimize', 'speed', 'slow']):
            intent_type = 'performance'
        else:
            intent_type = 'generic'

        # Extract entities (models, views, etc.)
        entities = self._extract_entities(request)

        return {
            'type': intent_type,
            'entities': entities,
            'complexity': self._estimate_complexity(request, entities)
        }

    def _extract_entities(self, request: str) -> List[str]:
        """Extract Django entities (models, views, etc.) mentioned in request."""
        entities = []

        # Look for common Django patterns
        words = request.split()
        for i, word in enumerate(words):
            # Check for Model references
            if word.lower() in ['model', 'models'] and i > 0:
                entities.append(f"model:{words[i-1]}")

            # Check for View references
            elif word.lower() in ['view', 'views'] and i > 0:
                entities.append(f"view:{words[i-1]}")

            # Check for API references
            elif word.lower() in ['api', 'endpoint'] and i > 0:
                entities.append(f"api:{words[i-1]}")

        return entities

    def _estimate_complexity(self, request: str, entities: List[str]) -> str:
        """Estimate the complexity of the requested change."""
        complexity_indicators = {
            'simple': ['fix', 'update', 'change'],
            'medium': ['add', 'create', 'implement'],
            'complex': ['refactor', 'restructure', 'migrate', 'integrate']
        }

        request_lower = request.lower()

        for level, indicators in complexity_indicators.items():
            if any(indicator in request_lower for indicator in indicators):
                # Adjust based on number of entities
                if len(entities) > 3:
                    return 'complex'
                elif len(entities) > 1:
                    return 'medium' if level == 'simple' else level
                return level

        return 'medium'  # default

    def _identify_affected_areas(self, request: str, scope: Optional[List[str]]) -> List[str]:
        """Identify areas of the codebase that will be affected."""
        areas = []

        if scope:
            areas.extend(scope)

        # Extract app names from request
        request_words = request.lower().split()
        apps = ['activity', 'peoples', 'schedhuler', 'y_helpdesk', 'work_order_management']

        for app in apps:
            if app in ' '.join(request_words):
                areas.append(f"apps/{app}/")

        return areas or ["apps/core/"]  # default to core

    def _analyze_change_impact(self, affected_areas: List[str], intent: Dict) -> Optional[ImpactResult]:
        """Analyze the impact of proposed changes using the ImpactAnalyzer."""
        try:
            # Convert affected areas to likely file paths
            likely_files = []
            for area in affected_areas:
                if area.endswith('/'):
                    # It's a directory - find key files that might be affected
                    likely_files.extend([
                        f"{area}models.py",
                        f"{area}views.py",
                        f"{area}urls.py",
                        f"{area}serializers.py",
                        f"{area}forms.py"
                    ])
                else:
                    # It's a specific file
                    likely_files.append(area)

            # Filter to files that actually exist
            existing_files = []
            for file_path in likely_files:
                if Path(file_path).exists():
                    existing_files.append(file_path)

            # If no existing files found, create a minimal analysis
            if not existing_files:
                return None

            # Run impact analysis
            change_type = ChangeType.MODIFIED  # Default assumption
            if intent['type'] == 'feature':
                change_type = ChangeType.ADDED

            return self.impact_analyzer.analyze_changes(existing_files, change_type)

        except (DatabaseError, IntegrityError) as e:
            print(f"Impact analysis failed: {e}")
            return None

    def _plan_feature_addition(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for feature addition."""
        # Step 1: Design and plan
        plan.add_step(ChangeStep(
            step_id="design",
            description="Design the new feature architecture and data model",
            step_type="design",
            target_files=[],
            risk_level="low",
            estimated_time=30
        ))

        # Use impact analysis to determine actual files to modify
        target_files = list(impact_result.affected_files) if impact_result else []
        if not target_files:
            # Fallback to area-based approach
            target_files = [f"{area}models.py" for area in areas if 'model' in str(intent['entities']).lower()]

        # Step 2: Model changes (based on impact analysis)
        if impact_result and impact_result.migration_required:
            plan.add_step(ChangeStep(
                step_id="model_changes",
                description="Add or modify Django models based on impact analysis",
                step_type="modify",
                target_files=[f for f in target_files if 'models.py' in f],
                dependencies=["design"],
                risk_level="high" if impact_result.severity.value in ['high', 'critical'] else "medium",
                estimated_time=45
            ))
            plan.migration_needed = True
        elif 'model' in str(intent['entities']).lower():
            for area in areas:
                models_file = f"{area}models.py"
                plan.add_step(ChangeStep(
                    step_id="model_changes",
                    description="Add or modify Django models",
                    step_type="modify",
                    target_files=[models_file],
                    dependencies=["design"],
                    risk_level="medium",
                    estimated_time=45
                ))
                plan.migration_needed = True

        # Step 3: API/View implementation (based on impact analysis)
        view_files = [f for f in target_files if any(pattern in f for pattern in ['views.py', 'serializers.py'])]
        if view_files:
            plan.add_step(ChangeStep(
                step_id="view_implementation",
                description="Implement views and API endpoints based on impact analysis",
                step_type="modify",
                target_files=view_files,
                dependencies=["model_changes"] if plan.migration_needed else ["design"],
                risk_level="high" if impact_result and impact_result.breaking_changes else "medium",
                estimated_time=60
            ))
        else:
            # Fallback to area-based approach
            for area in areas:
                views_file = f"{area}views.py"
                plan.add_step(ChangeStep(
                    step_id="view_implementation",
                    description="Implement views and API endpoints",
                    step_type="modify",
                    target_files=[views_file, f"{area}urls.py"],
                    dependencies=["model_changes"] if plan.migration_needed else ["design"],
                    risk_level="medium",
                    estimated_time=60
                ))

        # Step 4: Frontend/Templates
        plan.add_step(ChangeStep(
            step_id="frontend",
            description="Add or update templates and frontend components",
            step_type="modify",
            target_files=["frontend/templates/"],
            dependencies=["view_implementation"],
            risk_level="low",
            estimated_time=45
        ))

    def _plan_bug_fix(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for bug fixing."""
        # Step 1: Investigation
        plan.add_step(ChangeStep(
            step_id="investigate",
            description="Investigate and identify root cause of the bug",
            step_type="investigate",
            target_files=[],
            risk_level="low",
            estimated_time=30
        ))

        # Step 2: Fix implementation
        for area in areas:
            plan.add_step(ChangeStep(
                step_id="fix_implementation",
                description="Implement the bug fix",
                step_type="modify",
                target_files=[f"{area}*.py"],
                dependencies=["investigate"],
                risk_level="medium",
                estimated_time=30
            ))

        # Step 3: Regression testing
        plan.add_step(ChangeStep(
            step_id="regression_test",
            description="Add regression test to prevent future occurrences",
            step_type="create",
            target_files=[f"{area}tests/" for area in areas],
            dependencies=["fix_implementation"],
            risk_level="low",
            estimated_time=30
        ))

    def _plan_refactoring(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for refactoring."""
        plan.add_step(ChangeStep(
            step_id="refactor_analysis",
            description="Analyze current code structure and identify improvement opportunities",
            step_type="analyze",
            target_files=[],
            risk_level="low",
            estimated_time=45
        ))

        plan.add_step(ChangeStep(
            step_id="refactor_implementation",
            description="Implement refactoring changes",
            step_type="modify",
            target_files=[f"{area}*.py" for area in areas],
            dependencies=["refactor_analysis"],
            risk_level="high",  # Refactoring can be risky
            estimated_time=90
        ))

    def _plan_security_fix(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for security fixes."""
        plan.add_step(ChangeStep(
            step_id="security_audit",
            description="Conduct security audit to identify all vulnerabilities",
            step_type="audit",
            target_files=[],
            risk_level="low",
            estimated_time=45
        ))

        plan.add_step(ChangeStep(
            step_id="security_fix",
            description="Implement security fixes and hardening",
            step_type="modify",
            target_files=[f"{area}*.py" for area in areas],
            dependencies=["security_audit"],
            risk_level="critical",
            estimated_time=60
        ))

        # Security fixes require immediate testing
        plan.prerequisites.append("Security review by security team")

    def _plan_performance_optimization(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for performance optimization."""
        plan.add_step(ChangeStep(
            step_id="performance_profile",
            description="Profile application to identify performance bottlenecks",
            step_type="analyze",
            target_files=[],
            risk_level="low",
            estimated_time=60
        ))

        plan.add_step(ChangeStep(
            step_id="optimization_implementation",
            description="Implement performance optimizations",
            step_type="modify",
            target_files=[f"{area}*.py" for area in areas],
            dependencies=["performance_profile"],
            risk_level="medium",
            estimated_time=90
        ))

    def _plan_generic_change(self, plan: ChangePlan, intent: Dict, areas: List[str], impact_result: Optional[ImpactResult] = None):
        """Generate steps for generic changes."""
        plan.add_step(ChangeStep(
            step_id="analysis",
            description="Analyze requirements and current implementation",
            step_type="analyze",
            target_files=[],
            risk_level="low",
            estimated_time=30
        ))

        plan.add_step(ChangeStep(
            step_id="implementation",
            description="Implement the requested changes",
            step_type="modify",
            target_files=[f"{area}*.py" for area in areas],
            dependencies=["analysis"],
            risk_level="medium",
            estimated_time=60
        ))

    def _add_testing_steps(self, plan: ChangePlan):
        """Add comprehensive testing steps to the plan."""
        test_files = []
        for file_path in plan.impacted_files:
            if file_path.endswith('.py') and not file_path.endswith('test*.py'):
                test_path = file_path.replace('.py', '_test.py').replace('/', '/tests/')
                test_files.append(test_path)

        plan.add_step(ChangeStep(
            step_id="unit_tests",
            description="Create or update unit tests for changed components",
            step_type="test",
            target_files=test_files,
            dependencies=[step.step_id for step in plan.steps if step.step_type in ['modify', 'create']],
            risk_level="low",
            estimated_time=60
        ))

        plan.add_step(ChangeStep(
            step_id="integration_tests",
            description="Run integration tests to ensure system cohesion",
            step_type="test",
            target_files=[],
            dependencies=["unit_tests"],
            risk_level="low",
            estimated_time=30
        ))

        plan.required_tests = test_files

    def _add_impact_aware_testing_steps(self, plan: ChangePlan, impact_result: Optional[ImpactResult]):
        """Add testing steps based on impact analysis."""
        if not impact_result:
            # Fallback to original testing approach
            self._add_testing_steps(plan)
            return

        test_files = []

        # Add specific tests for affected symbols
        for symbol_key in impact_result.affected_symbols:
            file_path = symbol_key.split('::')[0]
            if file_path.endswith('.py') and not any(test_indicator in file_path.lower()
                                                    for test_indicator in ['test_', '/tests/', '_test.']):
                test_path = file_path.replace('.py', '_test.py').replace('/', '/tests/')
                test_files.append(test_path)

        # Add tests for affected URLs
        if impact_result.affected_urls:
            test_files.append("tests/test_urls_integration.py")

        # Add specific test step for affected tests
        if impact_result.affected_tests:
            plan.add_step(ChangeStep(
                step_id="affected_tests",
                description=f"Run affected tests ({len(impact_result.affected_tests)} tests)",
                step_type="test",
                target_files=list(impact_result.affected_tests),
                dependencies=[step.step_id for step in plan.steps if step.step_type in ['modify', 'create']],
                risk_level="medium" if impact_result.severity.value in ['high', 'critical'] else "low",
                estimated_time=30
            ))

        # Add comprehensive test step
        plan.add_step(ChangeStep(
            step_id="unit_tests",
            description="Create or update unit tests for changed components based on impact analysis",
            step_type="test",
            target_files=test_files,
            dependencies=[step.step_id for step in plan.steps if step.step_type in ['modify', 'create']],
            risk_level="low",
            estimated_time=60
        ))

        # Add integration tests if breaking changes detected
        if impact_result.breaking_changes:
            plan.add_step(ChangeStep(
                step_id="breaking_change_tests",
                description=f"Add tests to verify breaking change compatibility ({len(impact_result.breaking_changes)} breaking changes)",
                step_type="test",
                target_files=[],
                dependencies=["unit_tests"],
                risk_level="high",
                estimated_time=45
            ))

        # Add test coverage gap tests
        if impact_result.test_coverage_gaps:
            plan.add_step(ChangeStep(
                step_id="coverage_gap_tests",
                description=f"Fill test coverage gaps ({len(impact_result.test_coverage_gaps)} gaps identified)",
                step_type="test",
                target_files=[],
                dependencies=["unit_tests"],
                risk_level="medium",
                estimated_time=60
            ))

        plan.required_tests = test_files

    def _add_migration_steps(self, plan: ChangePlan, impact_result: ImpactResult):
        """Add migration steps based on impact analysis."""
        plan.add_step(ChangeStep(
            step_id="database_migration",
            description="Create and run database migrations based on model changes",
            step_type="migrate",
            target_files=[],
            dependencies=["model_changes"],
            risk_level="high" if impact_result.breaking_changes else "medium",
            estimated_time=30
        ))

        # Add data migration step if needed
        model_breaking_changes = [bc for bc in impact_result.breaking_changes if bc['type'] == 'model_field']
        if model_breaking_changes:
            plan.add_step(ChangeStep(
                step_id="data_migration",
                description="Create data migration to handle breaking model changes",
                step_type="migrate",
                target_files=[],
                dependencies=["database_migration"],
                risk_level="critical",
                estimated_time=60
            ))

        # Add migration suggestions to plan
        for suggestion in impact_result.migration_suggestions:
            plan.prerequisites.append(suggestion)

    def _add_safety_checks(self, plan: ChangePlan):
        """Add safety checks and validation steps."""
        plan.add_step(ChangeStep(
            step_id="safety_validation",
            description="Run safety checks and code quality validation",
            step_type="validate",
            target_files=[],
            dependencies=[step.step_id for step in plan.steps if step.step_type == 'modify'],
            risk_level="low",
            estimated_time=15
        ))

        if plan.migration_needed:
            plan.add_step(ChangeStep(
                step_id="migration_safety",
                description="Validate database migration safety",
                step_type="validate",
                target_files=[],
                dependencies=["model_changes"],
                risk_level="high",
                estimated_time=30
            ))

    def _generate_rollback_plan(self, plan: ChangePlan):
        """Generate a rollback plan for the changes."""
        rollback_steps = []

        # Reverse the order of steps for rollback
        for step in reversed(plan.steps):
            if step.step_type == 'modify':
                rollback_steps.append(f"Revert changes to {', '.join(step.target_files)}")
            elif step.step_type == 'create':
                rollback_steps.append(f"Remove created files: {', '.join(step.target_files)}")

        if plan.migration_needed:
            rollback_steps.append("Run database rollback migration")

        plan.rollback_plan = rollback_steps


class Command(BaseCommand):
    help = 'Generate structured change plans from natural language requests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--request',
            type=str,
            required=True,
            help='Natural language description of the requested change'
        )
        parser.add_argument(
            '--scope',
            type=str,
            nargs='*',
            help='Limit the scope to specific apps or directories'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'markdown', 'summary'],
            default='markdown',
            help='Output format for the plan'
        )
        parser.add_argument(
            '--save',
            type=str,
            help='Save the plan to a file'
        )
        parser.add_argument(
            '--complexity',
            type=str,
            choices=['simple', 'medium', 'complex'],
            help='Override complexity estimation'
        )

    def handle(self, *args, **options):
        request = options['request']
        scope = options.get('scope')
        output_format = options['format']
        save_path = options.get('save')

        self.stdout.write(f"🧠 Analyzing request: {request}")

        try:
            # Generate the plan
            generator = PlanGenerator()
            plan = generator.generate_plan(request, scope)

            self.stdout.write(self.style.SUCCESS(f"✅ Generated plan with {len(plan.steps)} steps"))
            self.stdout.write(f"📊 Estimated time: {plan.estimated_total_time} minutes")
            self.stdout.write(f"⚠️  Overall risk: {plan.overall_risk}")

            # Format output
            if output_format == 'json':
                output = json.dumps(plan.to_dict(), indent=2)
            elif output_format == 'summary':
                output = self._format_summary(plan)
            else:  # markdown
                output = self._format_markdown(plan)

            # Save or display
            if save_path:
                Path(save_path).write_text(output)
                self.stdout.write(f"💾 Plan saved to {save_path}")
            else:
                self.stdout.write("\n" + "="*60)
                self.stdout.write(output)
                self.stdout.write("="*60)

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Error generating plan: {e}"))
            raise CommandError(f"Plan generation failed: {e}")

    def _format_summary(self, plan: ChangePlan) -> str:
        """Format plan as a summary."""
        lines = [
            f"PLAN SUMMARY",
            f"Request: {plan.request}",
            f"Steps: {len(plan.steps)}",
            f"Impacted Files: {len(plan.impacted_files)}",
            f"Estimated Time: {plan.estimated_total_time} minutes",
            f"Risk Level: {plan.overall_risk}",
            f"Migration Needed: {'Yes' if plan.migration_needed else 'No'}",
        ]

        if plan.prerequisites:
            lines.append(f"Prerequisites: {', '.join(plan.prerequisites)}")

        return '\n'.join(lines)

    def _format_markdown(self, plan: ChangePlan) -> str:
        """Format plan as markdown."""
        lines = [
            f"# Change Plan: {plan.request}",
            f"",
            f"**Plan ID:** {plan.plan_id}",
            f"**Risk Level:** {plan.overall_risk}",
            f"**Estimated Time:** {plan.estimated_total_time} minutes",
            f"**Migration Required:** {'Yes' if plan.migration_needed else 'No'}",
            f"",
        ]

        if plan.prerequisites:
            lines.extend([
                f"## Prerequisites",
                f"",
            ])
            for prereq in plan.prerequisites:
                lines.append(f"- {prereq}")
            lines.append("")

        lines.extend([
            f"## Implementation Steps",
            f"",
        ])

        for i, step in enumerate(plan.steps, 1):
            lines.extend([
                f"### {i}. {step.description}",
                f"",
                f"- **Type:** {step.step_type}",
                f"- **Risk:** {step.risk_level}",
                f"- **Time:** {step.estimated_time} minutes",
            ])

            if step.target_files:
                lines.append(f"- **Files:** {', '.join(step.target_files)}")

            if step.dependencies:
                lines.append(f"- **Dependencies:** {', '.join(step.dependencies)}")

            lines.append("")

        if plan.rollback_plan:
            lines.extend([
                f"## Rollback Plan",
                f"",
            ])
            for i, rollback_step in enumerate(plan.rollback_plan, 1):
                lines.append(f"{i}. {rollback_step}")
            lines.append("")

        if plan.impacted_files:
            lines.extend([
                f"## Impacted Files",
                f"",
            ])
            for file_path in sorted(plan.impacted_files):
                lines.append(f"- {file_path}")

        return '\n'.join(lines)