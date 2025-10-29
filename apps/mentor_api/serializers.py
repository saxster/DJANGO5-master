"""
Serializers for Mentor API endpoints.
"""

from rest_framework import serializers


class PlanRequestSerializer(serializers.Serializer):
    """Serializer for plan generation requests."""
    request = serializers.CharField(
        help_text="Natural language description of the requested change"
    )
    scope = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Limit the scope to specific apps or directories",
    )
    complexity = serializers.ChoiceField(
        choices=['simple', 'medium', 'complex'],
        required=False,
        help_text="Override complexity estimation",
    )
    format = serializers.ChoiceField(
        choices=['json', 'markdown', 'summary'],
        default='json',
        help_text="Output format for the plan",
    )


class ChangeStepSerializer(serializers.Serializer):
    """Serializer for individual change steps."""
    step_id = serializers.CharField()
    description = serializers.CharField()
    step_type = serializers.CharField()
    target_files = serializers.ListField(child=serializers.CharField())
    dependencies = serializers.ListField(child=serializers.CharField(), default=list)
    risk_level = serializers.CharField()
    estimated_time = serializers.IntegerField()


class PlanResponseSerializer(serializers.Serializer):
    """Serializer for plan generation responses."""
    plan_id = serializers.CharField()
    request = serializers.CharField()
    steps = ChangeStepSerializer(many=True)
    impacted_files = serializers.ListField(child=serializers.CharField())
    required_tests = serializers.ListField(child=serializers.CharField())
    migration_needed = serializers.BooleanField()
    overall_risk = serializers.CharField()
    estimated_total_time = serializers.IntegerField()
    prerequisites = serializers.ListField(child=serializers.CharField())
    rollback_plan = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class PatchRequestSerializer(serializers.Serializer):
    """Serializer for patch generation requests."""
    request = serializers.CharField(
        required=False,
        help_text="Natural language description of patches to generate"
    )
    type = serializers.ChoiceField(
        choices=['security', 'performance', 'bugfix', 'improvement'],
        default='improvement',
        help_text="Type of patches to generate"
    )
    scope = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Limit patching to specific files or directories"
    )
    files = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Specific files to patch"
    )
    dry_run = serializers.BooleanField(
        default=True,
        help_text="Show what patches would be applied without applying them"
    )
    branch = serializers.CharField(
        required=False,
        help_text="Create patches on a new git branch"
    )
    auto_test = serializers.BooleanField(
        default=True,
        help_text="Run tests after applying patches"
    )


class CodePatchSerializer(serializers.Serializer):
    """Serializer for individual code patches."""
    type = serializers.CharField()
    priority = serializers.CharField()
    description = serializers.CharField()
    file_path = serializers.CharField()
    original_code = serializers.CharField()
    modified_code = serializers.CharField()
    line_start = serializers.IntegerField()
    line_end = serializers.IntegerField()
    dependencies = serializers.ListField(child=serializers.CharField())
    confidence = serializers.FloatField()


class PatchResponseSerializer(serializers.Serializer):
    """Serializer for patch generation responses."""
    applied = serializers.ListField(child=serializers.DictField(), default=list)
    failed = serializers.ListField(child=serializers.DictField(), default=list)
    rollback_id = serializers.CharField(required=False, allow_null=True)
    branch_created = serializers.CharField(required=False, allow_null=True)
    patches = CodePatchSerializer(many=True, default=list)


class TestRequestSerializer(serializers.Serializer):
    """Serializer for test execution requests."""
    targets = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Specific files or symbols to test"
    )
    changed = serializers.BooleanField(
        default=False,
        help_text="Test only files changed since last commit"
    )
    since = serializers.CharField(
        required=False,
        help_text="Test files changed since specific commit SHA"
    )
    flaky = serializers.BooleanField(
        default=False,
        help_text="Run only flaky tests (low success rate)"
    )
    slow = serializers.BooleanField(
        default=False,
        help_text="Run only slow tests"
    )
    coverage = serializers.BooleanField(
        default=False,
        help_text="Collect code coverage data"
    )
    markers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter tests by pytest markers"
    )
    parallel = serializers.BooleanField(
        default=True,
        help_text="Run tests in parallel"
    )
    timeout = serializers.IntegerField(
        default=600,
        help_text="Test execution timeout in seconds"
    )


class TestResultSerializer(serializers.Serializer):
    """Serializer for individual test results."""
    node_id = serializers.CharField()
    status = serializers.CharField()
    duration = serializers.FloatField()
    output = serializers.CharField()
    error_message = serializers.CharField(allow_null=True)


class TestResponseSerializer(serializers.Serializer):
    """Serializer for test execution responses."""
    session_id = serializers.CharField()
    total_tests = serializers.IntegerField()
    passed = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    errors = serializers.IntegerField()
    total_duration = serializers.FloatField()
    coverage_percentage = serializers.FloatField(allow_null=True)
    results = TestResultSerializer(many=True)


class GuardRequestSerializer(serializers.Serializer):
    """Serializer for guard validation requests."""
    validate = serializers.BooleanField(default=False)
    pre_commit = serializers.BooleanField(default=False)
    files = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Specific files to validate"
    )
    check = serializers.ChoiceField(
        choices=['scope', 'migration', 'secrets', 'security', 'quality', 'coverage', 'dependencies'],
        required=False,
        help_text="Run specific check type"
    )
    fix_auto = serializers.BooleanField(
        default=False,
        help_text="Automatically fix issues that can be auto-fixed"
    )
    fail_on = serializers.ChoiceField(
        choices=['critical', 'error', 'warning', 'info'],
        default='error',
        help_text="Exit with error on this severity level or higher"
    )


class GuardResultSerializer(serializers.Serializer):
    """Serializer for individual guard check results."""
    check_name = serializers.CharField()
    level = serializers.CharField()
    message = serializers.CharField()
    file_path = serializers.CharField(allow_null=True)
    line_number = serializers.IntegerField(allow_null=True)
    recommendation = serializers.CharField(allow_null=True)
    auto_fixable = serializers.BooleanField()


class GuardResponseSerializer(serializers.Serializer):
    """Serializer for guard validation responses."""
    overall_status = serializers.CharField()
    total_checks = serializers.IntegerField()
    passed_checks = serializers.IntegerField()
    failed_checks = serializers.IntegerField()
    blocking_issues = serializers.IntegerField()
    results = GuardResultSerializer(many=True)


class ExplainRequestSerializer(serializers.Serializer):
    """Serializer for code explanation requests."""
    target = serializers.CharField(
        help_text="What to explain (symbol reference, file path, URL pattern, etc.)"
    )
    type = serializers.ChoiceField(
        choices=['symbol', 'file', 'url', 'model', 'graphql', 'query'],  # graphql=legacy (removed Oct 2025)
        required=False,
        help_text="Type of target to explain (auto-detected if not specified)"
    )
    depth = serializers.IntegerField(
        default=2,
        help_text="Depth of relationship traversal"
    )
    include_usage = serializers.BooleanField(
        default=True,
        help_text="Include usage examples"
    )
    include_tests = serializers.BooleanField(
        default=True,
        help_text="Include test information"
    )
    include_docs = serializers.BooleanField(
        default=True,
        help_text="Include documentation"
    )
    format = serializers.ChoiceField(
        choices=['markdown', 'json', 'summary'],
        default='json',
        help_text="Output format"
    )


class ExplainResponseSerializer(serializers.Serializer):
    """Serializer for code explanation responses."""
    target = serializers.CharField()
    type = serializers.CharField()
    explanation = serializers.DictField()
    formatted_output = serializers.CharField(allow_null=True)


class MentorStatusSerializer(serializers.Serializer):
    """Serializer for mentor system status."""
    status = serializers.CharField()
    index_health = serializers.DictField()
    usage_statistics = serializers.DictField()
    quality_metrics = serializers.DictField()
    last_update = serializers.DateTimeField(allow_null=True)


class MentorHealthSerializer(serializers.Serializer):
    """Serializer for mentor health check."""
    overall_health = serializers.CharField()
    component_checks = serializers.ListField(child=serializers.DictField())
    issues_found = serializers.IntegerField()
    recommendations = serializers.ListField(child=serializers.CharField())
