"""
MentorSpec schema definition and validation for structured change requests.

This module defines the schema for MentorSpec files - structured YAML/JSON
documents that capture all requirements, constraints, and acceptance criteria
for AI Mentor change requests.
"""

import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from django.conf import settings


class IntentType(Enum):
    """Types of change intents."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    MAINTENANCE = "maintenance"


class RiskTolerance(Enum):
    """Risk tolerance levels for changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PriorityLevel(Enum):
    """Priority levels for change requests."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class SecurityConstraint:
    """Security constraint specification."""
    type: str  # 'no_secrets', 'scan_patterns', 'require_review', 'compliance'
    description: str
    required: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceConstraint:
    """Performance constraint specification."""
    metric: str  # 'response_time', 'memory_usage', 'cpu_usage', 'db_queries'
    threshold: Union[int, float]
    unit: str  # 'ms', 'mb', 'percent', 'count'
    description: str


@dataclass
class ComplianceConstraint:
    """Compliance constraint specification."""
    framework: str  # 'GDPR', 'HIPAA', 'PCI-DSS', 'SOX', 'ISO27001'
    requirements: List[str]
    documentation_required: bool = True


@dataclass
class MigrationPlan:
    """Database migration plan specification."""
    required: bool
    backward_compatible: bool
    data_migration_needed: bool
    migration_window: Optional[str] = None  # e.g., "maintenance_window"
    rollback_plan: List[str] = field(default_factory=list)
    validation_queries: List[str] = field(default_factory=list)


@dataclass
class TestPlan:
    """Testing requirements specification."""
    required_coverage: float = 80.0  # minimum test coverage percentage
    test_types: List[str] = field(default_factory=lambda: ["unit", "integration"])
    regression_tests: List[str] = field(default_factory=list)
    performance_tests: List[str] = field(default_factory=list)
    security_tests: List[str] = field(default_factory=list)
    manual_tests: List[str] = field(default_factory=list)


@dataclass
class RolloutPlan:
    """Deployment and rollout plan specification."""
    strategy: str = "direct"  # 'direct', 'phased', 'canary', 'blue_green'
    feature_flags: List[str] = field(default_factory=list)
    environments: List[str] = field(default_factory=lambda: ["development", "staging", "production"])
    approval_gates: List[str] = field(default_factory=list)
    monitoring_requirements: List[str] = field(default_factory=list)


@dataclass
class MentorSpec:
    """
    Complete specification for an AI Mentor change request.

    This is the core data structure that captures all requirements,
    constraints, and expectations for a change request.
    """

    # Required fields
    id: str
    title: str
    intent: IntentType
    description: str

    # Scope and targeting
    impacted_areas: List[str] = field(default_factory=list)  # ['apps/core/', 'models', 'urls']
    target_files: List[str] = field(default_factory=list)
    excluded_files: List[str] = field(default_factory=list)

    # Acceptance criteria and testing
    acceptance_criteria: List[str] = field(default_factory=list)
    test_plan: TestPlan = field(default_factory=TestPlan)

    # Constraints
    security_constraints: List[SecurityConstraint] = field(default_factory=list)
    performance_constraints: List[PerformanceConstraint] = field(default_factory=list)
    compliance_constraints: List[ComplianceConstraint] = field(default_factory=list)

    # Migration and deployment
    migration_plan: Optional[MigrationPlan] = None
    rollout_plan: RolloutPlan = field(default_factory=RolloutPlan)

    # Metadata
    priority: PriorityLevel = PriorityLevel.MEDIUM
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    estimated_effort_hours: Optional[float] = None
    deadline: Optional[str] = None  # ISO format date

    # References and context
    references: List[str] = field(default_factory=list)  # URLs, ticket IDs, etc.
    dependencies: List[str] = field(default_factory=list)  # Other spec IDs
    related_specs: List[str] = field(default_factory=list)

    # Ownership and approval
    owner: Optional[str] = None  # User ID or email
    reviewers: List[str] = field(default_factory=list)
    approvers: List[str] = field(default_factory=list)

    # System fields
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"
    status: str = "draft"  # 'draft', 'review', 'approved', 'implemented', 'rejected'

    def __post_init__(self):
        """Post-initialization validation and normalization."""
        # Ensure ID is valid
        if not self.id or not self.id.replace('-', '').replace('_', '').isalnum():
            raise ValueError("ID must be alphanumeric with hyphens or underscores")

        # Normalize intent
        if isinstance(self.intent, str):
            self.intent = IntentType(self.intent.lower())

        # Normalize priority and risk tolerance
        if isinstance(self.priority, str):
            self.priority = PriorityLevel(self.priority.lower())
        if isinstance(self.risk_tolerance, str):
            self.risk_tolerance = RiskTolerance(self.risk_tolerance.lower())

        # Auto-create migration plan if needed
        if self.intent in [IntentType.FEATURE, IntentType.REFACTOR] and not self.migration_plan:
            has_models = any('models' in area.lower() for area in self.impacted_areas)
            if has_models:
                self.migration_plan = MigrationPlan(required=True, backward_compatible=True, data_migration_needed=False)


class MentorSpecValidator:
    """Validator for MentorSpec objects and files."""

    @staticmethod
    def validate_spec(spec: MentorSpec) -> List[str]:
        """
        Validate a MentorSpec object and return list of validation errors.

        Returns empty list if spec is valid.
        """
        errors = []

        # Required field validation
        if not spec.title or not spec.title.strip():
            errors.append("Title is required and cannot be empty")

        if not spec.description or not spec.description.strip():
            errors.append("Description is required and cannot be empty")

        if not spec.acceptance_criteria:
            errors.append("At least one acceptance criterion is required")

        # Logical validation
        if spec.risk_tolerance == RiskTolerance.LOW and spec.priority == PriorityLevel.URGENT:
            errors.append("Urgent priority conflicts with low risk tolerance")

        if spec.intent == IntentType.SECURITY and spec.risk_tolerance == RiskTolerance.LOW:
            errors.append("Security changes should have medium or higher risk tolerance")

        # Migration validation
        if spec.migration_plan and spec.migration_plan.required:
            if not spec.migration_plan.rollback_plan:
                errors.append("Migration requires a rollback plan")

        # Constraint validation
        for constraint in spec.security_constraints:
            if constraint.required and not constraint.description:
                errors.append(f"Required security constraint '{constraint.type}' needs description")

        # Test plan validation
        if spec.test_plan.required_coverage < 0 or spec.test_plan.required_coverage > 100:
            errors.append("Test coverage must be between 0 and 100")

        if spec.intent == IntentType.SECURITY and 'security' not in spec.test_plan.test_types:
            errors.append("Security changes require security tests")

        return errors

    @staticmethod
    def validate_file(file_path: Union[str, Path]) -> List[str]:
        """Validate a MentorSpec file and return validation errors."""
        errors = []
        file_path = Path(file_path)

        if not file_path.exists():
            errors.append(f"Spec file not found: {file_path}")
            return errors

        try:
            spec = MentorSpecLoader.load_from_file(file_path)
            errors.extend(MentorSpecValidator.validate_spec(spec))
        except (TypeError, ValidationError, ValueError) as e:
            errors.append(f"Failed to load spec file: {str(e)}")

        return errors


class MentorSpecLoader:
    """Loader for MentorSpec files."""

    @staticmethod
    def load_from_file(file_path: Union[str, Path]) -> MentorSpec:
        """Load a MentorSpec from a YAML or JSON file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Spec file not found: {file_path}")

        content = file_path.read_text(encoding='utf-8')

        # Parse based on file extension
        if file_path.suffix.lower() in ['.yaml', '.yml']:
            data = yaml.safe_load(content)
        elif file_path.suffix.lower() == '.json':
            data = json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"File is neither valid YAML nor JSON: {e}")

        return MentorSpecLoader._dict_to_spec(data)

    @staticmethod
    def load_from_dict(data: Dict[str, Any]) -> MentorSpec:
        """Load a MentorSpec from a dictionary."""
        return MentorSpecLoader._dict_to_spec(data)

    @staticmethod
    def _dict_to_spec(data: Dict[str, Any]) -> MentorSpec:
        """Convert dictionary to MentorSpec object."""
        # Handle nested objects
        if 'test_plan' in data and isinstance(data['test_plan'], dict):
            data['test_plan'] = TestPlan(**data['test_plan'])

        if 'migration_plan' in data and isinstance(data['migration_plan'], dict):
            data['migration_plan'] = MigrationPlan(**data['migration_plan'])

        if 'rollout_plan' in data and isinstance(data['rollout_plan'], dict):
            data['rollout_plan'] = RolloutPlan(**data['rollout_plan'])

        # Handle constraint lists
        for constraint_type in ['security_constraints', 'performance_constraints', 'compliance_constraints']:
            if constraint_type in data and isinstance(data[constraint_type], list):
                constraint_class = {
                    'security_constraints': SecurityConstraint,
                    'performance_constraints': PerformanceConstraint,
                    'compliance_constraints': ComplianceConstraint
                }[constraint_type]

                data[constraint_type] = [
                    constraint_class(**item) if isinstance(item, dict) else item
                    for item in data[constraint_type]
                ]

        return MentorSpec(**data)


class MentorSpecRepository:
    """Repository for managing MentorSpec files."""

    def __init__(self, base_path: Optional[Union[str, Path]] = None):
        """Initialize repository with base path for spec files."""
        if base_path is None:
            base_path = Path(settings.BASE_DIR) / '.mentor' / 'specs'

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_spec(self, spec: MentorSpec, format: str = 'yaml') -> Path:
        """Save a MentorSpec to file."""
        # Update timestamp
        spec.updated_at = datetime.now().isoformat()

        # Generate filename
        safe_id = spec.id.replace(' ', '_').lower()
        extension = '.yaml' if format == 'yaml' else '.json'
        file_path = self.base_path / f"{safe_id}{extension}"

        # Convert to dictionary
        spec_dict = asdict(spec)

        # Save to file
        if format == 'yaml':
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(spec_dict, f, default_flow_style=False, sort_keys=False, indent=2)
        else:  # JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(spec_dict, f, indent=2, ensure_ascii=False)

        return file_path

    def load_spec(self, spec_id: str) -> Optional[MentorSpec]:
        """Load a MentorSpec by ID."""
        safe_id = spec_id.replace(' ', '_').lower()

        # Try different extensions
        for ext in ['.yaml', '.yml', '.json']:
            file_path = self.base_path / f"{safe_id}{ext}"
            if file_path.exists():
                return MentorSpecLoader.load_from_file(file_path)

        return None

    def list_specs(self) -> List[str]:
        """List all available spec IDs."""
        specs = []
        for file_path in self.base_path.glob('*'):
            if file_path.suffix.lower() in ['.yaml', '.yml', '.json']:
                spec_id = file_path.stem
                specs.append(spec_id)

        return sorted(specs)

    def delete_spec(self, spec_id: str) -> bool:
        """Delete a spec file."""
        safe_id = spec_id.replace(' ', '_').lower()

        for ext in ['.yaml', '.yml', '.json']:
            file_path = self.base_path / f"{safe_id}{ext}"
            if file_path.exists():
                file_path.unlink()
                return True

        return False

    def validate_all_specs(self) -> Dict[str, List[str]]:
        """Validate all specs in the repository."""
        results = {}

        for spec_id in self.list_specs():
            spec = self.load_spec(spec_id)
            if spec:
                results[spec_id] = MentorSpecValidator.validate_spec(spec)
            else:
                results[spec_id] = ["Failed to load spec"]

        return results


# Template for creating new specs
DEFAULT_SPEC_TEMPLATE = """
id: "change-request-{timestamp}"
title: "Brief description of the change"
intent: "feature"  # feature, bugfix, refactor, security, performance, documentation, testing, maintenance
description: |
  Detailed description of what needs to be changed and why.

  Include background context, current problems, and desired outcomes.

impacted_areas:
  - "apps/core/"
  - "frontend/templates/"

acceptance_criteria:
  - "Criterion 1: System should..."
  - "Criterion 2: Users should be able to..."

test_plan:
  required_coverage: 80.0
  test_types:
    - "unit"
    - "integration"

security_constraints:
  - type: "no_secrets"
    description: "Ensure no hardcoded secrets in code"
    required: true

priority: "medium"  # low, medium, high, urgent
risk_tolerance: "medium"  # low, medium, high, critical

references:
  - "https://github.com/org/repo/issues/123"
  - "Ticket #456"

owner: "developer@example.com"
""".strip()


def create_spec_template(spec_id: str) -> str:
    """Create a spec template with the given ID."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_SPEC_TEMPLATE.replace("{timestamp}", timestamp).replace("change-request-{timestamp}", spec_id)


def get_spec_repository() -> MentorSpecRepository:
    """Get the default spec repository."""
    return MentorSpecRepository()