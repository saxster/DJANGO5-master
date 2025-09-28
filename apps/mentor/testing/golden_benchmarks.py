"""
Golden benchmark suite for AI Mentor system regression testing.

This module provides:
- Realistic test scenarios for common development tasks
- Expected outcomes for LLM and analyzer validation
- Regression testing to ensure system quality
- Performance benchmarking
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum



class BenchmarkType(Enum):
    """Types of benchmark scenarios."""
    FEATURE_ADDITION = "feature_addition"
    BUG_FIX = "bug_fix"
    SECURITY_FIX = "security_fix"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    REFACTORING = "refactoring"
    CODE_EXPLANATION = "code_explanation"


class DifficultyLevel(Enum):
    """Difficulty levels for benchmarks."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class ExpectedOutcome:
    """Expected outcome for a benchmark."""
    min_steps: int
    max_steps: int
    required_files: List[str]
    required_tests: List[str]
    migration_required: bool
    risk_level: str
    estimated_time_minutes: int
    key_concepts: List[str]
    success_criteria: List[str]


@dataclass
class BenchmarkScenario:
    """A benchmark test scenario."""
    id: str
    name: str
    description: str
    benchmark_type: BenchmarkType
    difficulty: DifficultyLevel
    request: str
    scope: Optional[List[str]]
    context_files: List[str]  # Files that should exist for this benchmark
    expected_outcome: ExpectedOutcome
    tags: List[str] = field(default_factory=list)
    created_by: str = "system"
    notes: str = ""


@dataclass
class BenchmarkResult:
    """Result of running a benchmark."""
    scenario_id: str
    passed: bool
    score: float  # 0.0 to 1.0
    execution_time_seconds: float
    actual_steps: int
    actual_files: List[str]
    actual_risk_level: str
    differences: List[str]
    llm_iterations: int
    confidence_score: float
    timestamp: str


class GoldenBenchmarkSuite:
    """Suite of golden benchmarks for AI Mentor testing."""

    def __init__(self):
        self.scenarios = self._load_benchmark_scenarios()
        self.results_history = []

    def _load_benchmark_scenarios(self) -> List[BenchmarkScenario]:
        """Load predefined benchmark scenarios."""
        scenarios = [
            # Feature Addition Scenarios
            BenchmarkScenario(
                id="add_user_avatar_feature",
                name="Add User Avatar Feature",
                description="Add user avatar upload and display functionality",
                benchmark_type=BenchmarkType.FEATURE_ADDITION,
                difficulty=DifficultyLevel.MEDIUM,
                request="Add user avatar functionality where users can upload profile pictures, resize them automatically, and display them in the header",
                scope=["apps/peoples/", "frontend/templates/"],
                context_files=["apps/peoples/models.py", "apps/peoples/views.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=4,
                    max_steps=8,
                    required_files=["apps/peoples/models.py", "apps/peoples/views.py", "frontend/templates/"],
                    required_tests=["test_avatar_upload", "test_avatar_display"],
                    migration_required=True,
                    risk_level="medium",
                    estimated_time_minutes=120,
                    key_concepts=["file upload", "image processing", "model changes"],
                    success_criteria=[
                        "Avatar field added to user model",
                        "Upload view implemented",
                        "Template updated to display avatar",
                        "Tests cover upload and display"
                    ]
                ),
                tags=["user_management", "file_upload", "frontend"]
            ),

            # Bug Fix Scenarios
            BenchmarkScenario(
                id="fix_n_plus_one_query",
                name="Fix N+1 Query Problem",
                description="Fix N+1 query problem in user dashboard",
                benchmark_type=BenchmarkType.BUG_FIX,
                difficulty=DifficultyLevel.MEDIUM,
                request="Fix the N+1 query problem in the user dashboard where we're loading user activities. Currently it makes one query per activity instead of using proper joins",
                scope=["apps/activity/", "apps/peoples/"],
                context_files=["apps/activity/views.py", "apps/activity/models.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=2,
                    max_steps=5,
                    required_files=["apps/activity/views.py"],
                    required_tests=["test_dashboard_query_count"],
                    migration_required=False,
                    risk_level="low",
                    estimated_time_minutes=30,
                    key_concepts=["query optimization", "select_related", "prefetch_related"],
                    success_criteria=[
                        "Query count reduced to O(1)",
                        "Dashboard performance improved",
                        "Functionality unchanged"
                    ]
                ),
                tags=["performance", "database", "optimization"]
            ),

            # Security Fix Scenarios
            BenchmarkScenario(
                id="fix_sql_injection_vulnerability",
                name="Fix SQL Injection Vulnerability",
                description="Fix SQL injection in user search functionality",
                benchmark_type=BenchmarkType.SECURITY_FIX,
                difficulty=DifficultyLevel.COMPLEX,
                request="Fix the SQL injection vulnerability in apps/peoples/views.py line 145 where user search input is concatenated directly into a raw SQL query",
                scope=["apps/peoples/"],
                context_files=["apps/peoples/views.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=3,
                    max_steps=6,
                    required_files=["apps/peoples/views.py"],
                    required_tests=["test_search_sql_injection_protection"],
                    migration_required=False,
                    risk_level="high",
                    estimated_time_minutes=45,
                    key_concepts=["SQL injection", "parameterized queries", "input validation"],
                    success_criteria=[
                        "Raw SQL replaced with parameterized query",
                        "Input validation added",
                        "Security tests pass",
                        "Search functionality preserved"
                    ]
                ),
                tags=["security", "sql_injection", "critical"]
            ),

            # Performance Optimization Scenarios
            BenchmarkScenario(
                id="optimize_dashboard_queries",
                name="Optimize Dashboard Database Queries",
                description="Optimize the main dashboard database access patterns",
                benchmark_type=BenchmarkType.PERFORMANCE_OPTIMIZATION,
                difficulty=DifficultyLevel.COMPLEX,
                request="Optimize the main dashboard page which currently loads in 3-5 seconds. The issue is N+1 queries and missing database indexes. Target is under 500ms load time",
                scope=["apps/activity/", "apps/peoples/"],
                context_files=["apps/activity/views/dashboard_views.py", "apps/activity/models.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=5,
                    max_steps=10,
                    required_files=["apps/activity/views/dashboard_views.py", "apps/activity/models.py"],
                    required_tests=["test_dashboard_performance"],
                    migration_required=True,
                    risk_level="medium",
                    estimated_time_minutes=180,
                    key_concepts=["database optimization", "indexing", "caching", "query analysis"],
                    success_criteria=[
                        "Dashboard loads under 500ms",
                        "Query count reduced to <10",
                        "Database indexes added",
                        "Caching implemented"
                    ]
                ),
                tags=["performance", "database", "dashboard"]
            ),

            # Refactoring Scenarios
            BenchmarkScenario(
                id="refactor_authentication_module",
                name="Refactor Authentication Module",
                description="Refactor authentication to use dependency injection pattern",
                benchmark_type=BenchmarkType.REFACTORING,
                difficulty=DifficultyLevel.EXPERT,
                request="Refactor the authentication module in apps/peoples/ to use dependency injection pattern, making it easier to test and extend with different authentication providers",
                scope=["apps/peoples/"],
                context_files=["apps/peoples/views.py", "apps/peoples/models.py", "apps/peoples/authentication.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=6,
                    max_steps=12,
                    required_files=["apps/peoples/authentication.py", "apps/peoples/providers/"],
                    required_tests=["test_authentication_providers", "test_dependency_injection"],
                    migration_required=False,
                    risk_level="high",
                    estimated_time_minutes=240,
                    key_concepts=["dependency injection", "design patterns", "testability"],
                    success_criteria=[
                        "Authentication abstracted into interface",
                        "Multiple providers supported",
                        "Existing functionality preserved",
                        "Test coverage maintained"
                    ]
                ),
                tags=["refactoring", "architecture", "testing"]
            ),

            # Code Explanation Scenarios
            BenchmarkScenario(
                id="explain_payment_processing",
                name="Explain Payment Processing Flow",
                description="Explain the payment processing workflow",
                benchmark_type=BenchmarkType.CODE_EXPLANATION,
                difficulty=DifficultyLevel.MEDIUM,
                request="Explain how the payment processing system works, including the models, views, and external integrations",
                scope=["apps/payments/"],
                context_files=["apps/payments/models.py", "apps/payments/views.py", "apps/payments/processors.py"],
                expected_outcome=ExpectedOutcome(
                    min_steps=1,
                    max_steps=1,
                    required_files=[],
                    required_tests=[],
                    migration_required=False,
                    risk_level="low",
                    estimated_time_minutes=5,
                    key_concepts=["payment flow", "external apis", "state management"],
                    success_criteria=[
                        "Clear explanation of payment flow",
                        "All major components covered",
                        "Integration points explained",
                        "Usage examples provided"
                    ]
                ),
                tags=["explanation", "payments", "workflow"]
            )
        ]

        return scenarios

    def run_benchmark(self, scenario_id: str) -> BenchmarkResult:
        """Run a specific benchmark scenario."""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Benchmark scenario not found: {scenario_id}")

        start_time = time.time()

        try:
            # Run the appropriate mentor operation based on benchmark type
            result = self._execute_scenario(scenario)
            execution_time = time.time() - start_time

            # Evaluate the result against expected outcomes
            benchmark_result = self._evaluate_result(scenario, result, execution_time)

            # Store result
            self.results_history.append(benchmark_result)

            return benchmark_result

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            execution_time = time.time() - start_time
            return BenchmarkResult(
                scenario_id=scenario_id,
                passed=False,
                score=0.0,
                execution_time_seconds=execution_time,
                actual_steps=0,
                actual_files=[],
                actual_risk_level="unknown",
                differences=[f"Execution failed: {str(e)}"],
                llm_iterations=0,
                confidence_score=0.0,
                timestamp=datetime.now().isoformat()
            )

    def _execute_scenario(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Execute a benchmark scenario."""
        if scenario.benchmark_type == BenchmarkType.FEATURE_ADDITION:
            return self._run_plan_generation(scenario)
        elif scenario.benchmark_type == BenchmarkType.BUG_FIX:
            return self._run_plan_generation(scenario)
        elif scenario.benchmark_type == BenchmarkType.SECURITY_FIX:
            return self._run_security_patch_generation(scenario)
        elif scenario.benchmark_type == BenchmarkType.PERFORMANCE_OPTIMIZATION:
            return self._run_performance_optimization(scenario)
        elif scenario.benchmark_type == BenchmarkType.REFACTORING:
            return self._run_refactoring_plan(scenario)
        elif scenario.benchmark_type == BenchmarkType.CODE_EXPLANATION:
            return self._run_code_explanation(scenario)
        else:
            raise ValueError(f"Unknown benchmark type: {scenario.benchmark_type}")

    def _run_plan_generation(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Run plan generation for benchmark."""
        from apps.mentor.management.commands.mentor_plan import PlanGenerator

        generator = PlanGenerator()
        plan = generator.generate_plan(scenario.request, scenario.scope)

        return {
            'type': 'plan',
            'plan_id': plan.plan_id,
            'steps': [step.to_dict() for step in plan.steps],
            'impacted_files': list(plan.impacted_files),
            'required_tests': plan.required_tests,
            'migration_needed': plan.migration_needed,
            'overall_risk': plan.overall_risk,
            'estimated_total_time': plan.estimated_total_time
        }

    def _run_security_patch_generation(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Run security patch generation for benchmark."""
        from apps.mentor.management.commands.mentor_patch import PatchOrchestrator, PatchRequest

        orchestrator = PatchOrchestrator()
        patch_request = PatchRequest(
            request=scenario.request,
            scope=scenario.scope,
            patch_type='security',
            dry_run=True
        )

        patches = orchestrator.generate_patches(patch_request)

        return {
            'type': 'security_patches',
            'patch_count': len(patches),
            'patches': [{
                'description': patch.description,
                'file_path': patch.file_path,
                'priority': patch.priority.value,
                'confidence': patch.confidence
            } for patch in patches]
        }

    def _run_performance_optimization(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Run performance optimization for benchmark."""
        # Similar to plan generation but with performance focus
        return self._run_plan_generation(scenario)

    def _run_refactoring_plan(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Run refactoring plan for benchmark."""
        return self._run_plan_generation(scenario)

    def _run_code_explanation(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Run code explanation for benchmark."""
        from apps.mentor.management.commands.mentor_explain import CodeExplainer

        explainer = CodeExplainer()
        # Extract target from request (simplified)
        target = scenario.scope[0] if scenario.scope else "general"

        explanation = explainer.explain_query(scenario.request)

        return {
            'type': 'explanation',
            'target': target,
            'explanation': explanation,
            'completeness_score': self._assess_explanation_completeness(explanation, scenario)
        }

    def _evaluate_result(self, scenario: BenchmarkScenario, result: Dict[str, Any],
                        execution_time: float) -> BenchmarkResult:
        """Evaluate actual result against expected outcome."""
        score = 0.0
        differences = []
        passed = True

        expected = scenario.expected_outcome

        if result['type'] == 'plan':
            # Evaluate plan generation results
            actual_steps = len(result['steps'])
            actual_files = result['impacted_files']
            actual_risk = result['overall_risk']

            # Score based on step count accuracy
            if expected.min_steps <= actual_steps <= expected.max_steps:
                score += 0.3
            else:
                differences.append(f"Step count {actual_steps} not in expected range {expected.min_steps}-{expected.max_steps}")
                passed = False

            # Score based on file identification
            file_overlap = len(set(actual_files) & set(expected.required_files))
            file_score = file_overlap / len(expected.required_files) if expected.required_files else 1.0
            score += 0.3 * file_score

            if file_score < 0.5:
                differences.append(f"Poor file identification: {file_overlap}/{len(expected.required_files)} expected files found")

            # Score based on risk assessment
            if actual_risk == expected.risk_level:
                score += 0.2
            else:
                differences.append(f"Risk level mismatch: expected {expected.risk_level}, got {actual_risk}")

            # Score based on migration detection
            if result['migration_needed'] == expected.migration_required:
                score += 0.2
            else:
                differences.append(f"Migration requirement mismatch: expected {expected.migration_required}, got {result['migration_needed']}")

        elif result['type'] == 'security_patches':
            # Evaluate security patch results
            patch_count = result['patch_count']

            if patch_count > 0:
                score += 0.5
            else:
                differences.append("No security patches generated for known vulnerability")
                passed = False

            # Check patch quality
            high_confidence_patches = [p for p in result['patches'] if p['confidence'] > 0.8]
            confidence_score = len(high_confidence_patches) / patch_count if patch_count > 0 else 0
            score += 0.5 * confidence_score

        elif result['type'] == 'explanation':
            # Evaluate explanation quality
            completeness_score = result.get('completeness_score', 0.0)
            score = completeness_score

        # Final scoring
        score = min(score, 1.0)
        if score < 0.6:
            passed = False

        return BenchmarkResult(
            scenario_id=scenario.id,
            passed=passed,
            score=score,
            execution_time_seconds=execution_time,
            actual_steps=result.get('steps', []) if isinstance(result.get('steps'), list) else 0,
            actual_files=result.get('impacted_files', []),
            actual_risk_level=result.get('overall_risk', 'unknown'),
            differences=differences,
            llm_iterations=result.get('llm_iterations', 1),
            confidence_score=result.get('confidence_score', 0.0),
            timestamp=datetime.now().isoformat()
        )

    def _assess_explanation_completeness(self, explanation: Dict[str, Any],
                                       scenario: BenchmarkScenario) -> float:
        """Assess completeness of code explanation."""
        completeness_score = 0.0

        # Check for required components
        required_components = ['overview', 'technical_details', 'usage_examples']
        for component in required_components:
            if component in explanation and explanation[component]:
                completeness_score += 0.33

        # Check if key concepts are covered
        key_concepts = scenario.expected_outcome.key_concepts
        explanation_text = json.dumps(explanation).lower()
        concept_coverage = sum(1 for concept in key_concepts if concept.lower() in explanation_text)
        concept_score = concept_coverage / len(key_concepts) if key_concepts else 1.0
        completeness_score = (completeness_score + concept_score) / 2

        return min(completeness_score, 1.0)

    def run_full_suite(self) -> Dict[str, Any]:
        """Run the complete benchmark suite."""
        suite_start_time = time.time()
        results = []

        for scenario in self.scenarios:
            print(f"Running benchmark: {scenario.name}")
            try:
                result = self.run_benchmark(scenario.id)
                results.append(result)
                print(f"  ✅ {scenario.name}: {'PASSED' if result.passed else 'FAILED'} (score: {result.score:.2f})")
            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
                print(f"  ❌ {scenario.name}: ERROR - {str(e)}")
                results.append(BenchmarkResult(
                    scenario_id=scenario.id,
                    passed=False,
                    score=0.0,
                    execution_time_seconds=0.0,
                    actual_steps=0,
                    actual_files=[],
                    actual_risk_level="unknown",
                    differences=[f"Execution error: {str(e)}"],
                    llm_iterations=0,
                    confidence_score=0.0,
                    timestamp=datetime.now().isoformat()
                ))

        suite_execution_time = time.time() - suite_start_time

        # Calculate suite statistics
        total_scenarios = len(results)
        passed_scenarios = len([r for r in results if r.passed])
        average_score = sum(r.score for r in results) / total_scenarios if total_scenarios > 0 else 0
        average_execution_time = sum(r.execution_time_seconds for r in results) / total_scenarios if total_scenarios > 0 else 0

        return {
            'suite_summary': {
                'total_scenarios': total_scenarios,
                'passed_scenarios': passed_scenarios,
                'failed_scenarios': total_scenarios - passed_scenarios,
                'pass_rate': passed_scenarios / total_scenarios if total_scenarios > 0 else 0,
                'average_score': round(average_score, 3),
                'average_execution_time_seconds': round(average_execution_time, 2),
                'total_suite_time_seconds': round(suite_execution_time, 2)
            },
            'individual_results': results,
            'failed_scenarios': [r for r in results if not r.passed],
            'performance_outliers': [r for r in results if r.execution_time_seconds > 30],  # Over 30 seconds
            'low_confidence_results': [r for r in results if r.confidence_score < 0.7]
        }

    def get_scenario(self, scenario_id: str) -> Optional[BenchmarkScenario]:
        """Get a specific benchmark scenario."""
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None

    def get_scenarios_by_type(self, benchmark_type: BenchmarkType) -> List[BenchmarkScenario]:
        """Get scenarios filtered by type."""
        return [s for s in self.scenarios if s.benchmark_type == benchmark_type]

    def get_scenarios_by_difficulty(self, difficulty: DifficultyLevel) -> List[BenchmarkScenario]:
        """Get scenarios filtered by difficulty."""
        return [s for s in self.scenarios if s.difficulty == difficulty]

    def add_custom_scenario(self, scenario: BenchmarkScenario):
        """Add a custom benchmark scenario."""
        # Validate scenario
        if not scenario.id or not scenario.request:
            raise ValueError("Scenario must have id and request")

        # Check for duplicate IDs
        if any(s.id == scenario.id for s in self.scenarios):
            raise ValueError(f"Scenario with ID {scenario.id} already exists")

        self.scenarios.append(scenario)

    def export_benchmark_report(self, output_path: str):
        """Export benchmark results to file."""
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'total_scenarios': len(self.scenarios),
            'scenarios': [self._scenario_to_dict(s) for s in self.scenarios],
            'latest_results': self.results_history[-10:] if self.results_history else []
        }

        Path(output_path).write_text(json.dumps(report_data, indent=2))

    def _scenario_to_dict(self, scenario: BenchmarkScenario) -> Dict[str, Any]:
        """Convert scenario to dictionary for serialization."""
        return {
            'id': scenario.id,
            'name': scenario.name,
            'description': scenario.description,
            'type': scenario.benchmark_type.value,
            'difficulty': scenario.difficulty.value,
            'request': scenario.request,
            'scope': scenario.scope,
            'expected_outcome': {
                'min_steps': scenario.expected_outcome.min_steps,
                'max_steps': scenario.expected_outcome.max_steps,
                'required_files': scenario.expected_outcome.required_files,
                'required_tests': scenario.expected_outcome.required_tests,
                'migration_required': scenario.expected_outcome.migration_required,
                'risk_level': scenario.expected_outcome.risk_level,
                'estimated_time_minutes': scenario.expected_outcome.estimated_time_minutes,
                'key_concepts': scenario.expected_outcome.key_concepts,
                'success_criteria': scenario.expected_outcome.success_criteria
            },
            'tags': scenario.tags
        }


class BenchmarkRunner:
    """Runner for executing benchmarks as part of CI/CD."""

    def __init__(self):
        self.suite = GoldenBenchmarkSuite()

    def run_regression_tests(self) -> bool:
        """Run regression benchmarks and return pass/fail."""
        # Run a subset of critical benchmarks
        critical_scenarios = [
            "fix_sql_injection_vulnerability",
            "fix_n_plus_one_query",
            "add_user_avatar_feature"
        ]

        passed_all = True

        for scenario_id in critical_scenarios:
            try:
                result = self.suite.run_benchmark(scenario_id)
                if not result.passed or result.score < 0.7:
                    passed_all = False
                    print(f"REGRESSION FAILURE: {scenario_id} - Score: {result.score}")

            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                passed_all = False
                print(f"REGRESSION ERROR: {scenario_id} - {str(e)}")

        return passed_all

    def run_performance_benchmarks(self) -> Dict[str, float]:
        """Run performance-focused benchmarks."""
        performance_scenarios = self.suite.get_scenarios_by_type(BenchmarkType.PERFORMANCE_OPTIMIZATION)
        performance_results = {}

        for scenario in performance_scenarios:
            result = self.suite.run_benchmark(scenario.id)
            performance_results[scenario.id] = result.execution_time_seconds

        return performance_results


# Global benchmark suite
_benchmark_suite = None

def get_benchmark_suite() -> GoldenBenchmarkSuite:
    """Get global benchmark suite instance."""
    global _benchmark_suite
    if _benchmark_suite is None:
        _benchmark_suite = GoldenBenchmarkSuite()
    return _benchmark_suite