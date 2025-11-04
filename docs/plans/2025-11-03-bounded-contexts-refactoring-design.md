# Bounded Contexts Refactoring - Design Document

**Date**: November 3, 2025
**Type**: Big Bang Architecture Refactoring
**Timeline**: 2-3 weeks
**Backward Compatibility**: None (all imports updated)
**Git Strategy**: Single feature branch

---

## Design Overview

### Problem Statement

Current `apps/onboarding/` mixes three distinct domains:
1. Client/business relationship establishment
2. Physical site surveys with multimodal capture
3. Worker intake and provisioning

This creates confusion about boundaries, makes testing difficult, and violates single responsibility principle.

### Solution

Extract three bounded contexts with shared multimodal infrastructure:

```
apps/client_onboarding/     → Business relationships
apps/site_onboarding/       → Physical location surveys
apps/people_onboarding/     → Worker intake (already exists)
apps/core_onboarding/       → Shared voice/media/AI platform
```

**Delete**: `apps/onboarding/` completely (clean slate)

---

## Architecture

### Bounded Context 1: Client Onboarding

**Purpose**: Establish and manage business relationships

**Models**:
- `BusinessUnit` (renamed from Bt for clarity)
- `Contract`
- `Subscription`
- `ClientPreferences`

**Public API**:
- `ClientService`: create_client, update_preferences, get_status

**Handlers**:
- `ClientConversationHandler`: Voice/text conversations for client setup

---

### Bounded Context 2: Site Onboarding

**Purpose**: Survey and operationalize physical locations

**Models**:
- `OnboardingSite`
- `OnboardingZone` (zone-centric backbone)
- `SitePhoto`, `SiteVideo` (context-specific media wrappers)
- `Asset`, `Checkpoint`, `MeterPoint`
- `SOP`, `CoveragePlan`

**Public API**:
- `SiteService`: create_site, create_zone, generate_sop

**Handlers**:
- `SiteConversationHandler`: Voice/text site surveys

---

### Bounded Context 3: Worker Onboarding

**Purpose**: Intake and enable human resources

**Models** (already exist in apps/people_onboarding/):
- `OnboardingRequest`
- `OnboardingTask`
- `WorkerDocument` (NEW: media wrapper)

**Public API** (NEW):
- `WorkerService`: create_request, upload_document, assign_to_site

**Handlers** (NEW):
- `WorkerConversationHandler`: Voice/text worker intake

---

### Shared Kernel: Core Onboarding Platform

**Purpose**: Multimodal conversation infrastructure used by ALL contexts

**Models**:
- `ConversationSession` (with context_type field)
- `OnboardingObservation` (universal: voice/text + 0-N media)
- `OnboardingMedia` (universal media storage)
- `LLMRecommendation` (maker-checker AI)
- `AuthoritativeKnowledge` (knowledge base)
- `AIChangeSet` (change management)
- `TypeAssist`, `GeofenceMaster` (classification)

**Services**:
- `MultimodalInputProcessor`: Voice OR text + 0-N photos/videos
- `ConversationOrchestrator`: Routes to context handlers
- LLM services: Maker, Checker, Consensus
- Knowledge services: RAG, embeddings, vector stores
- Translation services
- Vision API integration
- Speech-to-text services

**Background Tasks** (with security fixes):
- `base_task.py`: OnboardingBaseTask with DLQ
- `retry_strategies.py`: Exception-specific retry
- `dead_letter_queue.py`: Failed task recovery (with race condition fix)
- `conversation_tasks.py`: Generic conversation processing

---

## Multimodal Capabilities

### Input Flexibility

**Every observation supports**:
- Voice OR text (user choice, not both)
- 0 to N photos (unlimited)
- 0 to N videos (unlimited)
- Optional GPS location

**Examples**:
```json
// Text only, no media
{
  "text_input": "Client confirmed security needs",
  "photos": [],
  "videos": []
}

// Voice + 3 photos
{
  "audio_file": File,
  "photos": [File, File, File],
  "videos": [],
  "gps_location": {"lat": 12.34, "lng": 56.78}
}

// Voice only, no media
{
  "audio_file": File,
  "photos": [],
  "videos": []
}

// Text + video + photos
{
  "text_input": "Camera coverage test",
  "photos": [File, File],
  "videos": [File],
  "gps_location": {"lat": 12.34, "lng": 56.78}
}
```

### Media Processing Pipeline

```
Upload (0-N files)
  ↓
Security Validation (size, MIME type, malware scan)
  ↓
Storage (S3/GCS with secure URLs)
  ↓
AI Analysis
  ├─ Photos → Vision API (object detection, safety concerns)
  ├─ Videos → Video analysis (future: frame extraction + Vision API)
  └─ Audio → Speech-to-text + translation
  ↓
Link to Observation
  ↓
LLM Enhancement (combines text + media analysis)
  ↓
Generate Actions (SOPs, assets, tasks)
```

---

## Database Schema Changes

### New Tables

```sql
-- Core onboarding
core_onboarding_conversationsession
core_onboarding_onboardingobservation
core_onboarding_onboardingmedia
core_onboarding_llmrecommendation
core_onboarding_authoritativeknowledge
core_onboarding_aichangeset
core_onboarding_typeassist
core_onboarding_geofencemaster

-- Client context
client_onboarding_businessunit
client_onboarding_contract
client_onboarding_subscription

-- Site context
site_onboarding_onboardingsite
site_onboarding_onboardingzone
site_onboarding_sitephoto
site_onboarding_sitevideo
site_onboarding_asset
site_onboarding_checkpoint
site_onboarding_meterpoint
site_onboarding_sop
site_onboarding_coverageplan

-- Worker context (already exist)
people_onboarding_onboardingrequest
people_onboarding_onboardingtask
people_onboarding_workerdocument (NEW)
```

### Deleted Tables

```sql
-- All onboarding_* tables deleted
DROP TABLE onboarding_bt;
DROP TABLE onboarding_shift;
DROP TABLE onboarding_conversationsession;
DROP TABLE onboarding_onboardingsite;
-- etc. (all tables from apps/onboarding/)
```

**Migration Strategy**: Create new apps, migrate data, drop old tables

---

## Import Updates Required

### Search & Replace Patterns

```python
# Pattern 1: Model imports
OLD: from apps.onboarding.models import Bt
NEW: from apps.client_onboarding.models import BusinessUnit

OLD: from apps.onboarding.models import OnboardingSite
NEW: from apps.site_onboarding.models import OnboardingSite

OLD: from apps.onboarding.models import ConversationSession
NEW: from apps.core_onboarding.models import ConversationSession

# Pattern 2: Service imports
OLD: from apps.onboarding_api.services.llm import get_llm_service
NEW: from apps.core_onboarding.services.llm import get_llm_service

# Pattern 3: Background tasks
OLD: from background_tasks.onboarding_tasks import process_conversation_step
NEW: from apps.core_onboarding.background_tasks.conversation_tasks import process_conversation_step
```

**Estimated**: 500+ import statements to update across 100+ files

---

## Testing Strategy

### Test Organization

```python
# apps/client_onboarding/tests/
test_business_unit_model.py
test_client_service.py
test_client_conversation_handler.py
test_client_api.py

# apps/site_onboarding/tests/
test_site_model.py
test_zone_model.py
test_site_service.py
test_multimodal_site_survey.py  # Tests voice + photos
test_site_api.py

# apps/people_onboarding/tests/
test_worker_service.py
test_worker_conversation_handler.py
test_document_upload.py  # Tests 0-N media upload

# apps/core_onboarding/tests/
test_multimodal_processor.py  # Tests voice OR text + 0-N media
test_conversation_orchestrator.py
test_media_security.py  # Tests file validation
test_conversation_tasks.py  # Tests background tasks with security fixes
```

---

Design complete! Moving to implementation planning.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Complete design presentation (remaining sections)", "status": "completed", "activeForm": "Completing design presentation"}, {"content": "Write formal design document to docs/plans/", "status": "completed", "activeForm": "Writing formal design document"}, {"content": "Set up git worktree for refactoring", "status": "in_progress", "activeForm": "Setting up git worktree"}, {"content": "Create comprehensive implementation plan", "status": "pending", "activeForm": "Creating comprehensive implementation plan"}, {"content": "Create new app directory structures", "status": "pending", "activeForm": "Creating new app directory structures"}, {"content": "Extract and migrate models to new contexts", "status": "pending", "activeForm": "Extracting and migrating models"}, {"content": "Create service layer for each context", "status": "pending", "activeForm": "Creating service layer"}, {"content": "Create multimodal infrastructure in core_onboarding", "status": "pending", "activeForm": "Creating multimodal infrastructure"}, {"content": "Migrate background tasks with security fixes", "status": "pending", "activeForm": "Migrating background tasks"}, {"content": "Update all import statements across codebase", "status": "pending", "activeForm": "Updating import statements"}, {"content": "Create API endpoints for each context", "status": "pending", "activeForm": "Creating API endpoints"}, {"content": "Update URL routing", "status": "pending", "activeForm": "Updating URL routing"}, {"content": "Update INSTALLED_APPS in settings", "status": "pending", "activeForm": "Updating INSTALLED_APPS"}, {"content": "Create database migrations", "status": "pending", "activeForm": "Creating database migrations"}, {"content": "Create admin interfaces for each context", "status": "pending", "activeForm": "Creating admin interfaces"}, {"content": "Create comprehensive test suite", "status": "pending", "activeForm": "Creating comprehensive test suite"}, {"content": "Run all tests and fix issues", "status": "pending", "activeForm": "Running tests and fixing issues"}, {"content": "Delete apps/onboarding/ completely", "status": "pending", "activeForm": "Deleting apps/onboarding/"}, {"content": "Final validation and verification", "status": "pending", "activeForm": "Final validation and verification"}]