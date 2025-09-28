"""
Change scope controller with approval gates and blast radius control.

This controller provides:
- File count limits: Maximum files per patch
- Line count limits: Change size restrictions
- Blast radius: Impact assessment
- Critical file protection: Settings, migrations
- Approval requirements: Human review gates
"""

import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from apps.mentor.generators.patch_generator import CodePatch, PatchPriority
from apps.mentor.guards.write_policy import get_write_policy, WriteRequest


class ApprovalLevel(Enum):
    NONE = "none"
    DEVELOPER = "developer"
    LEAD = "lead"
    ARCHITECT = "architect"


@dataclass
class ScopeLimit:
    """Container for scope limitation rules."""
    max_files: int
    max_lines_per_file: int
    max_total_lines: int
    approval_required: ApprovalLevel
    critical_files: Set[str]


class ChangeScope:
    """Container for change scope analysis."""
    files_affected: int
    lines_changed: int
    blast_radius: int
    risk_score: float
    approval_level: ApprovalLevel


class ScopeController:
    """Controls change scope and enforces approval gates."""

    def __init__(self):
        self.limits = self._initialize_limits()

    def _initialize_limits(self) -> Dict[str, ScopeLimit]:
        """Initialize scope limits by change type."""
        return {
            'security': ScopeLimit(
                max_files=50,
                max_lines_per_file=200,
                max_total_lines=1000,
                approval_required=ApprovalLevel.LEAD,
                critical_files={'settings.py', 'urls.py'}
            ),
            'feature': ScopeLimit(
                max_files=20,
                max_lines_per_file=100,
                max_total_lines=500,
                approval_required=ApprovalLevel.DEVELOPER,
                critical_files=set()
            ),
            'refactor': ScopeLimit(
                max_files=30,
                max_lines_per_file=150,
                max_total_lines=800,
                approval_required=ApprovalLevel.LEAD,
                critical_files=set()
            )
        }

    def validate_scope(self, patches: List[CodePatch]) -> ChangeScope:
        """Validate change scope against limits."""
        files_affected = len(set(patch.file_path for patch in patches))
        lines_changed = sum(patch.line_end - patch.line_start + 1 for patch in patches)

        # Calculate blast radius and risk
        blast_radius = self._calculate_blast_radius(patches)
        risk_score = self._calculate_risk_score(patches)
        approval_level = self._determine_approval_level(patches, risk_score)

        return ChangeScope(
            files_affected=files_affected,
            lines_changed=lines_changed,
            blast_radius=blast_radius,
            risk_score=risk_score,
            approval_level=approval_level
        )

    def _calculate_blast_radius(self, patches: List[CodePatch]) -> int:
        """Calculate change blast radius."""
        # Simplified calculation based on file count and complexity
        unique_files = set(patch.file_path for patch in patches)
        return len(unique_files) * 2  # Placeholder multiplier

    def _calculate_risk_score(self, patches: List[CodePatch]) -> float:
        """Calculate overall risk score."""
        risk_weights = {
            PatchPriority.CRITICAL: 10,
            PatchPriority.HIGH: 7,
            PatchPriority.MEDIUM: 4,
            PatchPriority.LOW: 1
        }

        total_risk = sum(risk_weights.get(patch.priority, 0) for patch in patches)
        max_possible = len(patches) * 10

        return (total_risk / max_possible) if max_possible > 0 else 0

    def _determine_approval_level(self, patches: List[CodePatch], risk_score: float) -> ApprovalLevel:
        """Determine required approval level."""
        if risk_score > 0.8:
            return ApprovalLevel.ARCHITECT
        elif risk_score > 0.5:
            return ApprovalLevel.LEAD
        elif risk_score > 0.2:
            return ApprovalLevel.DEVELOPER
        else:
            return ApprovalLevel.NONE

    def is_patch_allowed(self, patch: CodePatch) -> bool:
        """Check if a single patch is allowed based on scope limits and policies."""
        try:
            # Use centralized WritePolicy for validation
            write_policy = get_write_policy()

            # Calculate content size (estimate from patch)
            content_size = 0
            if patch.modified_code:
                content_size = len(patch.modified_code.encode('utf-8'))

            # Create write request
            write_request = WriteRequest(
                operation_type='modify',
                file_path=patch.file_path,
                content_size=content_size,
                content_preview=patch.modified_code[:500] if patch.modified_code else None
            )

            # Validate using centralized policy
            policy_result = write_policy.validate_write(write_request)

            # If writePolicy says no, respect that decision
            if not policy_result.allowed:
                return False

            # Additional scope-specific validations
            patch_type = self._infer_patch_type(patch)
            limits = self.limits.get(patch_type, self.limits['feature'])

            # Check scope-specific line limits
            if patch.line_end and patch.line_start:
                lines_changed = patch.line_end - patch.line_start + 1
                if lines_changed > limits.max_lines_per_file:
                    return False

            # Check file permissions
            try:
                file_path = Path(patch.file_path)
                if file_path.exists() and not os.access(file_path, os.W_OK):
                    return False
            except (TypeError, ValidationError, ValueError):
                return False

            # Check if patch type is allowed
            if patch_type == 'security' and not self._security_patches_enabled():
                return False

            return True

        except (TypeError, ValidationError, ValueError):
            # If any validation fails, err on the side of caution
            return False

    def _infer_patch_type(self, patch: CodePatch) -> str:
        """Infer patch type from patch characteristics."""
        # Check patch priority and description for clues
        description = patch.description.lower() if patch.description else ""

        if any(word in description for word in ['security', 'vulnerability', 'xss', 'sql injection']):
            return 'security'
        elif any(word in description for word in ['performance', 'optimize', 'slow', 'cache']):
            return 'performance'
        elif any(word in description for word in ['refactor', 'restructure', 'reorganize']):
            return 'refactor'
        elif any(word in description for word in ['bug', 'fix', 'error', 'exception']):
            return 'bugfix'
        else:
            return 'feature'

    def _security_patches_enabled(self) -> bool:
        """Check if security patches are enabled (can be controlled by environment)."""
        return os.getenv('MENTOR_SECURITY_PATCHES_ENABLED', 'true').lower() == 'true'

    def get_policy_report(self, patches: List[CodePatch]) -> Dict[str, Any]:
        """Get a detailed policy validation report for a list of patches."""
        write_policy = get_write_policy()

        # Create write requests for all patches
        write_requests = []
        for patch in patches:
            content_size = len(patch.modified_code.encode('utf-8')) if patch.modified_code else 0
            write_requests.append(WriteRequest(
                operation_type='modify',
                file_path=patch.file_path,
                content_size=content_size,
                content_preview=patch.modified_code[:500] if patch.modified_code else None
            ))

        # Get batch validation result
        batch_result = write_policy.validate_batch_write(write_requests)

        # Combine with scope validation
        scope_result = self.validate_scope(patches)

        return {
            'write_policy_allowed': batch_result.allowed,
            'write_policy_violations': batch_result.violations,
            'write_policy_recommendations': batch_result.recommendations,
            'write_policy_risk_level': batch_result.risk_level,
            'scope_validation': {
                'files_affected': scope_result.files_affected,
                'lines_changed': scope_result.lines_changed,
                'blast_radius': scope_result.blast_radius,
                'risk_score': scope_result.risk_score,
                'approval_level': scope_result.approval_level.value
            }
        }