"""
Django models for the AI Mentor system using PostgreSQL.

These models store code indexing data, relationships, and metadata
for the mentor's analysis and generation capabilities.
"""

from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class IndexedFile(models.Model):
    """Represents a file that has been indexed by the mentor system."""

    path = models.CharField(max_length=1000, unique=True, help_text="Relative path from project root")
    sha = models.CharField(max_length=64, help_text="SHA hash of file content")
    mtime = models.BigIntegerField(help_text="File modification time (timestamp)")
    size = models.IntegerField(help_text="File size in bytes")
    language = models.CharField(max_length=50, blank=True, help_text="Programming language")
    is_test = models.BooleanField(default=False, help_text="Whether this is a test file")
    content_preview = models.TextField(blank=True, help_text="First 1000 chars for search")

    # Full-text search support
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mentor_files'
        indexes = [
            models.Index(fields=['path']),
            models.Index(fields=['sha']),
            models.Index(fields=['mtime']),
            models.Index(fields=['language']),
            models.Index(fields=['is_test']),
            GinIndex(fields=['search_vector']),  # PostgreSQL GIN index for full-text search
        ]
        ordering = ['path']

    def __str__(self):
        return self.path

    @property
    def is_fresh(self):
        """Check if the indexed version matches the current file."""
        from pathlib import Path
        from django.conf import settings

        file_path = Path(settings.BASE_DIR) / self.path
        if not file_path.exists():
            return False

        current_mtime = int(file_path.stat().st_mtime)
        return current_mtime == self.mtime


class CodeSymbol(models.Model):
    """Represents a code symbol (class, function, variable, etc.)."""

    SYMBOL_KINDS = [
        ('class', 'Class'),
        ('function', 'Function'),
        ('method', 'Method'),
        ('variable', 'Variable'),
        ('property', 'Property'),
        ('constant', 'Constant'),
        ('module', 'Module'),
        ('import', 'Import'),
    ]

    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='symbols')
    name = models.CharField(max_length=200, help_text="Symbol name")
    kind = models.CharField(max_length=20, choices=SYMBOL_KINDS, help_text="Type of symbol")
    span_start = models.IntegerField(help_text="Starting line number")
    span_end = models.IntegerField(help_text="Ending line number")

    # Symbol details
    parents = models.JSONField(default=list, help_text="Parent symbols (for nested definitions)")
    decorators = models.JSONField(default=list, help_text="Applied decorators")
    docstring = models.TextField(blank=True, help_text="Symbol documentation")
    signature = models.TextField(blank=True, help_text="Function/method signature")
    complexity = models.IntegerField(default=0, help_text="Cyclomatic complexity")

    # Full-text search support
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_symbols'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['kind']),
            models.Index(fields=['file', 'span_start']),
            GinIndex(fields=['search_vector']),
            models.Index(fields=['complexity']),
        ]
        ordering = ['file', 'span_start']

    def __str__(self):
        return f"{self.file.path}:{self.name} ({self.kind})"

    @property
    def full_name(self):
        """Get the fully qualified symbol name."""
        if self.parents:
            return '.'.join(self.parents + [self.name])
        return self.name


class SymbolRelation(models.Model):
    """Represents relationships between code symbols."""

    RELATION_KINDS = [
        ('import', 'Import'),
        ('call', 'Function Call'),
        ('inherit', 'Inheritance'),
        ('serialize', 'Serializer Relation'),
        ('reference', 'Reference'),
        ('dependency', 'Dependency'),
    ]

    source = models.ForeignKey(CodeSymbol, on_delete=models.CASCADE, related_name='outgoing_relations')
    target = models.ForeignKey(CodeSymbol, on_delete=models.CASCADE, related_name='incoming_relations')
    kind = models.CharField(max_length=20, choices=RELATION_KINDS)
    line_number = models.IntegerField(null=True, blank=True, help_text="Line where relation occurs")
    confidence = models.FloatField(default=1.0, help_text="Confidence in this relation (0.0-1.0)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_relations'
        unique_together = ['source', 'target', 'kind']
        indexes = [
            models.Index(fields=['source', 'kind']),
            models.Index(fields=['target', 'kind']),
            models.Index(fields=['kind']),
        ]

    def __str__(self):
        return f"{self.source.name} --{self.kind}--> {self.target.name}"


class DjangoURL(models.Model):
    """Represents Django URL patterns."""

    route = models.CharField(max_length=500, help_text="URL pattern")
    name = models.CharField(max_length=200, blank=True, help_text="URL name")
    view_name = models.CharField(max_length=200, help_text="View function/class name")
    methods = models.JSONField(default=list, help_text="Allowed HTTP methods")
    permissions = models.JSONField(default=list, help_text="Required permissions")
    app_label = models.CharField(max_length=100, blank=True, help_text="Django app")

    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='urls')
    line_number = models.IntegerField(help_text="Line number in URL file")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_urls'
        indexes = [
            models.Index(fields=['route']),
            models.Index(fields=['name']),
            models.Index(fields=['view_name']),
            models.Index(fields=['app_label']),
        ]

    def __str__(self):
        return f"{self.route} -> {self.view_name}"


class DjangoModel(models.Model):
    """Represents Django model definitions."""

    app_label = models.CharField(max_length=100, help_text="Django app name")
    model_name = models.CharField(max_length=100, help_text="Model class name")
    fields = models.JSONField(default=dict, help_text="Field definitions")
    db_table = models.CharField(max_length=200, blank=True, help_text="Database table name")
    meta_options = models.JSONField(default=dict, help_text="Model Meta options")

    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='models')
    line_number = models.IntegerField(help_text="Line number where model is defined")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_models'
        unique_together = ['app_label', 'model_name']
        indexes = [
            models.Index(fields=['app_label', 'model_name']),
            models.Index(fields=['db_table']),
        ]

    def __str__(self):
        return f"{self.app_label}.{self.model_name}"

    @property
    def field_names(self):
        """Get list of field names."""
        return list(self.fields.keys()) if self.fields else []


class GraphQLDefinition(models.Model):
    """Represents GraphQL types, queries, mutations, and resolvers."""

    GRAPHQL_KINDS = [
        ('type', 'Type'),
        ('query', 'Query'),
        ('mutation', 'Mutation'),
        ('resolver', 'Resolver'),
        ('subscription', 'Subscription'),
    ]

    name = models.CharField(max_length=200, help_text="GraphQL definition name")
    kind = models.CharField(max_length=20, choices=GRAPHQL_KINDS)
    type_definition = models.JSONField(default=dict, help_text="GraphQL type information")

    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='graphql_definitions')
    line_number = models.IntegerField(help_text="Line number where defined")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_graphql'
        indexes = [
            models.Index(fields=['name', 'kind']),
            models.Index(fields=['kind']),
        ]

    def __str__(self):
        return f"{self.name} ({self.kind})"


class TestCase(models.Model):
    """Represents discovered test cases."""

    node_id = models.CharField(max_length=500, unique=True, help_text="Pytest node ID")
    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='tests')
    class_name = models.CharField(max_length=200, blank=True, help_text="Test class name")
    method_name = models.CharField(max_length=200, help_text="Test method name")

    markers = models.JSONField(default=list, help_text="Pytest markers")
    covered_modules = models.JSONField(default=list, help_text="Modules this test covers")

    # Performance and reliability tracking
    avg_execution_time = models.FloatField(default=0.0, help_text="Average execution time in seconds")
    success_rate = models.FloatField(default=1.0, help_text="Success rate (0.0-1.0) for flakiness tracking")
    last_run = models.DateTimeField(null=True, blank=True, help_text="Last execution time")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mentor_tests'
        indexes = [
            models.Index(fields=['file']),
            models.Index(fields=['class_name', 'method_name']),
            models.Index(fields=['success_rate']),  # For finding flaky tests
            models.Index(fields=['avg_execution_time']),  # For finding slow tests
        ]

    def __str__(self):
        return self.node_id

    @property
    def is_flaky(self):
        """Check if this test is considered flaky."""
        return self.success_rate < 0.95

    @property
    def is_slow(self):
        """Check if this test is considered slow."""
        return self.avg_execution_time > 5.0


class TestCoverage(models.Model):
    """Represents test coverage data."""

    test = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='coverage')
    file = models.ForeignKey(IndexedFile, on_delete=models.CASCADE, related_name='coverage')
    covered_lines = models.JSONField(default=list, help_text="List of covered line numbers")
    coverage_percentage = models.FloatField(help_text="Percentage of file covered by this test")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mentor_coverage'
        unique_together = ['test', 'file']
        indexes = [
            models.Index(fields=['test']),
            models.Index(fields=['file']),
            models.Index(fields=['coverage_percentage']),
        ]

    def __str__(self):
        return f"{self.test.node_id} -> {self.file.path} ({self.coverage_percentage:.1f}%)"


class IndexMetadata(models.Model):
    """Stores metadata about the indexing process."""

    key = models.CharField(max_length=200, unique=True)
    value = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mentor_metadata'

    def __str__(self):
        return f"{self.key}: {self.value[:50]}..."

    @classmethod
    def get_value(cls, key: str, default=None):
        """Get metadata value by key."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, key: str, value: str):
        """Set metadata value."""
        obj, created = cls.objects.get_or_create(key=key, defaults={'value': value})
        if not created:
            obj.value = value
            obj.save()

    @classmethod
    def get_indexed_commit(cls):
        """Get the last indexed commit SHA."""
        return cls.get_value('indexed_commit_sha')

    @classmethod
    def set_indexed_commit(cls, commit_sha: str):
        """Set the indexed commit SHA."""
        cls.set_value('indexed_commit_sha', commit_sha)
        cls.set_value('index_updated_at', timezone.now().isoformat())

    @classmethod
    def get_index_stats(cls):
        """Get indexing statistics."""
        return {
            'files': IndexedFile.objects.count(),
            'symbols': CodeSymbol.objects.count(),
            'relations': SymbolRelation.objects.count(),
            'urls': DjangoURL.objects.count(),
            'models': DjangoModel.objects.count(),
            'graphql': GraphQLDefinition.objects.count(),
            'tests': TestCase.objects.count(),
            'coverage_records': TestCoverage.objects.count(),
            'indexed_commit': cls.get_indexed_commit(),
            'index_updated_at': cls.get_value('index_updated_at'),
        }