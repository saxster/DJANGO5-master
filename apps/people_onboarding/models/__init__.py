"""
People Onboarding Models Package

This package provides models for the people onboarding workflow.
All models comply with .claude/rules.md Rule #7 (< 150 lines per file).

Models:
- OnboardingRequest: Core onboarding request with workflow state
- CandidateProfile: Personal information and contact details
- DocumentSubmission: Document uploads (resume, ID, certificates)
- ApprovalWorkflow: Multi-stakeholder approval chain
- BackgroundCheck: Verification and compliance tracking
- AccessProvisioning: Biometric, device, and site access setup
- TrainingAssignment: Mandatory training and orientation
- OnboardingTask: Checklist items with due dates

All models extend EnhancedTenantModel for multi-tenancy support.
"""

from .onboarding_request import OnboardingRequest
from .candidate_profile import CandidateProfile
from .document_submission import DocumentSubmission, DocumentType
from .approval_workflow import ApprovalWorkflow, ApprovalDecision
from .background_check import BackgroundCheck, VerificationStatus
from .access_provisioning import AccessProvisioning, AccessType
from .training_assignment import TrainingAssignment, TrainingStatus
from .onboarding_task import OnboardingTask, TaskPriority
from .worker_document import WorkerDocument

__all__ = [
    # Core models
    'OnboardingRequest',
    'CandidateProfile',

    # Document management
    'DocumentSubmission',
    'DocumentType',
    'WorkerDocument',

    # Approval workflow
    'ApprovalWorkflow',
    'ApprovalDecision',

    # Verification
    'BackgroundCheck',
    'VerificationStatus',

    # Access provisioning
    'AccessProvisioning',
    'AccessType',

    # Training
    'TrainingAssignment',
    'TrainingStatus',

    # Tasks
    'OnboardingTask',
    'TaskPriority',
]