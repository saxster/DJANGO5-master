# 🚀 People Onboarding Module - Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Apply Database Migration
```bash
python manage.py makemigrations people_onboarding
python manage.py migrate people_onboarding
```

### Step 2: Access Django Admin
```
http://localhost:8000/admin/people_onboarding/
```

### Step 3: Create Your First Onboarding Request
```python
from apps.people_onboarding.models import OnboardingRequest, CandidateProfile
from apps.onboarding.models import Bt
from datetime import date, timedelta

# Get client and bu
client = Bt.objects.first()

# Create onboarding request
request = OnboardingRequest.objects.create(
    person_type=OnboardingRequest.PersonType.EMPLOYEE_FULLTIME,
    current_state=OnboardingRequest.WorkflowState.DRAFT,
    start_date=date.today(),
    expected_completion_date=date.today() + timedelta(days=14),
    client=client,
    bu=client
)

# Create candidate profile
profile = CandidateProfile.objects.create(
    onboarding_request=request,
    first_name="John",
    last_name="Doe",
    primary_email="john.doe@example.com",
    primary_phone="+911234567890",
    current_address="123 Main St, City",
    preferred_language="en",
    client=client,
    bu=client
)

print(f"Created: {request.request_number}")
# Output: Created: POB-20250930-00001
```

---

## 📋 Common Tasks

### Transition Workflow State
```python
from apps.people_onboarding.services import WorkflowOrchestrator

# Submit for review
WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.SUBMITTED,
    user=request_user
)
```

### Upload Document
```python
from apps.people_onboarding.models import DocumentSubmission, DocumentType

doc = DocumentSubmission.objects.create(
    onboarding_request=request,
    document_type=DocumentType.RESUME,
    document_file=uploaded_file,
    is_mandatory=True,
    client=request.client,
    bu=request.bu
)
```

### Create Approval Workflow
```python
from apps.people_onboarding.models import ApprovalWorkflow

approval = ApprovalWorkflow.objects.create(
    onboarding_request=request,
    approval_level=ApprovalWorkflow.ApprovalLevel.HR,
    sequence_number=1,
    approver=hr_manager,
    client=request.client,
    bu=request.bu
)

# Approve
approval.approve(
    notes="All documents verified",
    ip_address="192.168.1.1"
)
```

### Initiate Background Check
```python
from apps.people_onboarding.services import VerificationService

check = VerificationService.initiate_background_check(
    request,
    verification_type='CRIMINAL'
)
```

### Provision Biometric Access
```python
from apps.people_onboarding.services import AccessProvisioningService

access_list = AccessProvisioningService.provision_biometric_access(request)
# Creates face recognition and voice biometric access provisions
```

### Create Training Assignment
```python
from apps.people_onboarding.models import TrainingAssignment, TrainingStatus

training = TrainingAssignment.objects.create(
    onboarding_request=request,
    training_type=TrainingAssignment.TrainingType.SAFETY_ORIENTATION,
    training_title="Site Safety Orientation",
    status=TrainingStatus.NOT_STARTED,
    due_date=date.today() + timedelta(days=7),
    is_mandatory=True,
    is_blocking=True,
    client=request.client,
    bu=request.bu
)
```

### Create Onboarding Tasks
```python
from apps.people_onboarding.models import OnboardingTask, TaskPriority

task1 = OnboardingTask.objects.create(
    onboarding_request=request,
    category=OnboardingTask.TaskCategory.DOCUMENTATION,
    title="Upload Aadhaar Card",
    status=OnboardingTask.TaskStatus.TODO,
    priority=TaskPriority.HIGH,
    is_mandatory=True,
    client=request.client,
    bu=request.bu
)

task2 = OnboardingTask.objects.create(
    onboarding_request=request,
    category=OnboardingTask.TaskCategory.PROVISIONING,
    title="Create System Login",
    status=OnboardingTask.TaskStatus.TODO,
    priority=TaskPriority.CRITICAL,
    is_mandatory=True,
    client=request.client,
    bu=request.bu
)

# Add dependency: task2 depends on task1
task2.depends_on.add(task1)
```

---

## 🔍 Query Examples

### Find Active Requests
```python
active_requests = OnboardingRequest.objects.active()
```

### Find Overdue Requests
```python
overdue = OnboardingRequest.objects.overdue()
```

### Find Pending Approvals for User
```python
my_approvals = ApprovalWorkflow.objects.filter(
    approver=current_user,
    decision='PENDING'
).select_related('onboarding_request')
```

### Find Employees by Person Type
```python
employees = OnboardingRequest.objects.by_person_type(
    OnboardingRequest.PersonType.EMPLOYEE_FULLTIME
)
```

### Search Candidates by Name
```python
from apps.people_onboarding.models import CandidateProfile

candidates = CandidateProfile.objects.search_by_name("John")
```

### Find Documents Pending Verification
```python
pending_docs = DocumentSubmission.objects.filter(
    verification_status='PENDING'
).select_related('onboarding_request')
```

### Find Expired Documents
```python
from django.utils import timezone

expired_docs = DocumentSubmission.objects.filter(
    expiry_date__lt=timezone.now().date()
)
```

---

## 📊 Admin URLs

Direct links to admin interfaces:

```
/admin/people_onboarding/onboardingrequest/        # All requests
/admin/people_onboarding/candidateprofile/         # Candidate profiles
/admin/people_onboarding/documentsubmission/       # Documents
/admin/people_onboarding/approvalworkflow/         # Approvals
/admin/people_onboarding/backgroundcheck/          # Background checks
/admin/people_onboarding/accessprovisioning/       # Access provisioning
/admin/people_onboarding/trainingassignment/       # Training
/admin/people_onboarding/onboardingtask/           # Tasks
```

---

## 🎯 Complete Onboarding Workflow Example

```python
from apps.people_onboarding.models import *
from apps.people_onboarding.services import *
from apps.onboarding.models import Bt
from datetime import date, timedelta

# Get client
client = Bt.objects.first()

# 1. Create Request (DRAFT)
request = OnboardingRequest.objects.create(
    person_type=OnboardingRequest.PersonType.CONTRACTOR,
    start_date=date.today(),
    expected_completion_date=date.today() + timedelta(days=21),
    client=client,
    bu=client
)

# 2. Create Candidate Profile
profile = CandidateProfile.objects.create(
    onboarding_request=request,
    first_name="Jane",
    last_name="Smith",
    primary_email="jane.smith@example.com",
    primary_phone="+919876543210",
    current_address="456 Oak St, City",
    client=client,
    bu=client
)

# 3. Submit Request (DRAFT → SUBMITTED)
WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.SUBMITTED
)

# 4. Upload Documents (SUBMITTED → DOCUMENT_VERIFICATION)
resume = DocumentSubmission.objects.create(
    onboarding_request=request,
    document_type=DocumentType.RESUME,
    document_file='path/to/resume.pdf',
    is_mandatory=True,
    client=client,
    bu=client
)

aadhaar = DocumentSubmission.objects.create(
    onboarding_request=request,
    document_type=DocumentType.AADHAAR,
    document_file='path/to/aadhaar.pdf',
    is_mandatory=True,
    client=client,
    bu=client
)

WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.DOCUMENT_VERIFICATION
)

# 5. Initiate Background Check (DOCUMENT_VERIFICATION → BACKGROUND_CHECK)
criminal_check = VerificationService.initiate_background_check(
    request,
    BackgroundCheck.VerificationType.CRIMINAL
)

WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.BACKGROUND_CHECK
)

# 6. Create Approval Workflow (BACKGROUND_CHECK → PENDING_APPROVAL)
hr_approval = ApprovalWorkflow.objects.create(
    onboarding_request=request,
    approval_level=ApprovalWorkflow.ApprovalLevel.HR,
    sequence_number=1,
    approver=hr_manager,
    client=client,
    bu=client
)

manager_approval = ApprovalWorkflow.objects.create(
    onboarding_request=request,
    approval_level=ApprovalWorkflow.ApprovalLevel.MANAGER,
    sequence_number=2,
    approver=department_manager,
    client=client,
    bu=client
)

WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.PENDING_APPROVAL
)

# 7. Approve (both approvals)
hr_approval.approve(notes="Documents verified, background check clear")
manager_approval.approve(notes="Approved for contractor role")

# 8. Transition to Provisioning (PENDING_APPROVAL → APPROVED → PROVISIONING)
WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.APPROVED
)

WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.PROVISIONING
)

# 9. Provision Access
biometric_access = AccessProvisioningService.provision_biometric_access(request)
login_access = AccessProvisioning.objects.create(
    onboarding_request=request,
    access_type=AccessType.LOGIN_CREDENTIALS,
    status='COMPLETED',
    access_details={'loginid': 'jane.smith', 'email': 'jane.smith@company.com'},
    client=client,
    bu=client
)

# 10. Assign Training (PROVISIONING → TRAINING)
safety_training = TrainingAssignment.objects.create(
    onboarding_request=request,
    training_type=TrainingAssignment.TrainingType.SAFETY_ORIENTATION,
    training_title="Contractor Safety Training",
    status=TrainingStatus.NOT_STARTED,
    due_date=date.today() + timedelta(days=3),
    is_mandatory=True,
    is_blocking=True,
    client=client,
    bu=client
)

WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.TRAINING
)

# 11. Complete Training
safety_training.status = TrainingStatus.COMPLETED
safety_training.completion_date = date.today()
safety_training.assessment_score = 85.0
safety_training.save()

# 12. Complete Onboarding (TRAINING → COMPLETED)
WorkflowOrchestrator.transition_to(
    request,
    OnboardingRequest.WorkflowState.COMPLETED
)

print(f"✅ Onboarding completed for {profile.full_name}")
print(f"Request: {request.request_number}")
print(f"Duration: {(request.actual_completion_date - request.start_date).days} days")
```

---

## 🔧 Troubleshooting

### Issue: Migration fails
**Solution**: Ensure all dependencies are migrated first:
```bash
python manage.py migrate onboarding
python manage.py migrate peoples
python manage.py migrate work_order_management
python manage.py makemigrations people_onboarding
python manage.py migrate people_onboarding
```

### Issue: Can't transition state
**Solution**: Check valid transitions:
```python
request.can_transition_to(new_state)  # Returns True/False
```

### Issue: Task dependency error
**Solution**: Ensure dependent tasks are completed:
```python
if task.can_start():
    # Start task
else:
    # Dependencies not met
    pending_deps = task.depends_on.exclude(status='COMPLETED')
```

---

## 📚 Next Steps

1. **Customize Workflows**: Adjust approval chains for your organization
2. **Integrate Biometrics**: Connect face/voice recognition systems
3. **Add Templates**: Create onboarding templates for common roles
4. **Build Portal**: Create self-service candidate portal
5. **Enable Notifications**: Configure email/SMS alerts
6. **Add Analytics**: Build dashboard for onboarding metrics

---

**Last Updated**: September 30, 2025
**Version**: 1.0.0