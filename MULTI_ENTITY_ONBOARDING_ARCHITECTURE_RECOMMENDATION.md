# Multi-Entity Onboarding Architecture - Comprehensive Analysis & Recommendation

**Date**: November 3, 2025
**Analysis Type**: Domain-Driven Design + Industry Best Practices
**Research Depth**: Ultra-comprehensive (web research + codebase exploration + DDD principles)

---

## Executive Summary

**RECOMMENDATION: 3 Bounded Contexts in Shared Django Monolith** ✅

**NOT microservices** - you gain domain clarity WITHOUT distributed system complexity.

### Current State
- ✅ You've ALREADY started separating (`apps/people_onboarding/` exists)
- ⚠️ Partially mixed (site onboarding still in main `apps/onboarding/`)
- ✅ Good foundation (clean models, < 150 lines each)

### Target State
```
├── apps/client_onboarding/     (Bounded Context 1: Business relationships)
├── apps/site_onboarding/       (Bounded Context 2: Physical locations)
├── apps/people_onboarding/     (Bounded Context 3: Human resources) ✅ EXISTS
└── apps/core_onboarding/       (Shared Kernel: ConversationSession, Knowledge, AI)
```

---

## Table of Contents

1. [Research Findings](#research-findings)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Bounded Context Definition](#bounded-context-definition)
4. [Architecture Decision Rationale](#architecture-decision-rationale)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Migration Strategy](#migration-strategy)
7. [Success Criteria](#success-criteria)

---

## Research Findings

### Industry Best Practices (2025)

#### 1. Domain-Driven Design Principles

**Key Insight**: "Bounded contexts are NOT microservices"
- Source: Vladikk.com, Microsoft Azure Architecture Center
- **Bounded Context** = Largest possible cohesive service WITHOUT conflicting models
- **Microservice** = Smallest possible deployable unit (a subset of bounded context)

**Critical Quote**:
> "A bounded context is actually the exact opposite of a microservice. It defines the boundaries of the biggest services possible: services that won't have any conflicting models inside of them."

**Implication**: If you follow DDD strictly, you get "good monoliths" first, THEN extract microservices if needed.

#### 2. Multi-Tenant SaaS Architecture Patterns

**Research Sources**:
- Relevant Software, Brocoders, AWS SaaS Lens
- Key finding: Even multi-tenant systems benefit from:
  - Shared compute infrastructure
  - Logical data isolation (schema prefixes, row-level security)
  - Unified operational experience

**Tenant Onboarding Best Practices**:
- Automated provisioning (infrastructure-as-code)
- Configuration-driven setup (avoid hardcoding)
- Guided tours with context-specific features
- Streamlined authentication (SSO, SAML)

#### 3. Facility Management Domain Specifics

**Research Sources**:
- Trackforce, TrackTik, Belfry Software
- Security workforce management platforms

**Key Findings**:
- **Tight coupling required**: Guards → Sites → Clients form operational triad
- **Real-time dependencies**: Post orders, incident reporting, checkpoint verification
- **Regulatory compliance**: Background checks, certifications, training mandated
- **Integration critical**: HRIS, access control, video management, billing systems

**Architecture Characteristics**:
- Multi-region deployment with 99.9% uptime SLA
- Modular design for rapid development
- Robust APIs for system integration
- Mobile-first for field operations

#### 4. Microservices vs Monolith Decision Framework

**Research Consensus** (Sam Newman, Martin Fowler):
- **Start with monolith** - you don't know boundaries yet
- **Extract microservices** when:
  - Team size > 10 developers per service
  - Independent scaling needs proven
  - Deployment independence critical
  - Organizational boundaries exist

**Cost of Wrong Boundaries**:
- Chatty services (performance degradation)
- Distributed transaction complexity
- Data consistency challenges
- Operational overhead (3x monitoring, logging, deployment)

---

## Current Architecture Analysis

### Discovered Structure

#### Apps/Modules Inventory:

1. **`apps/onboarding/`** (PRIMARY ONBOARDING APP)
   - **Models**:
     - `business_unit.py`: Bt (client/site hierarchy) - 140 lines
     - `site_onboarding.py`: OnboardingSite, OnboardingZone, Observation, SOP, Asset, Checkpoint, MeterPoint, SitePhoto, CoveragePlan - 848 lines total
     - `conversational_ai.py`: ConversationSession, LLMRecommendation, AuthoritativeKnowledge - 145 lines
     - `ai_changeset.py`: AIChangeSet, AIChangeRecord, ChangeSetApproval
     - `knowledge_source.py`, `knowledge_ingestion_job.py`, `knowledge_review.py`
     - `scheduling.py`: Shift - 80 lines
     - `classification.py`: TypeAssist, GeofenceMaster - 120 lines
     - `infrastructure.py`: Device, Subscription, DownTimeHistory - 140 lines
   - **Views**: `/views.py`, `/api/viewsets/` (REST endpoints)
   - **Admin**: Modular admin classes
   - **Management Commands**: `init_intelliwiz.py` (system initialization)

2. **`apps/people_onboarding/`** ✅ ALREADY SEPARATED
   - **Models**:
     - `OnboardingRequest`: Tracks worker onboarding lifecycle
       - PersonType: Employee, Contractor, Consultant, Vendor, Temporary
       - WorkflowState: 11 states (Draft → Completed)
       - Relationship to ConversationSession
     - `OnboardingTask`: Granular checklist tracking
       - TaskCategory: Documentation, Verification, Approval, Provisioning, Training, Equipment
       - TaskStatus: ToDo → In Progress → Completed
   - **Templates**: Dashboard, wizard, workflow timeline
   - **Purpose**: Human resource onboarding (separate from site operations)

3. **`apps/onboarding_api/`** (CONVERSATIONAL AI ORCHESTRATION)
   - **70+ service files**:
     - LLM services (Maker, Checker, Consensus)
     - Knowledge base (embeddings, vector stores, RAG)
     - Site audit integration
     - Funnel analytics
     - Session recovery
     - DLQ admin
     - Monitoring/observability
   - **Views**: Conversation, knowledge, approval, changeset, voice, analytics
   - **Purpose**: Cross-cutting AI orchestration layer

4. **`apps/peoples/`** (USER MODEL)
   - **Models**: People (custom user), PeopleProfile, PeopleOrganizational
   - **Refactored**: From monolithic to modular (< 150 lines each)
   - **Relationships**: FK to Bt (client), FK to Bt (site)

### Database Relationships Discovered

```
Bt (Client/Site Hierarchy)
├── parent: FK to self (hierarchical)
├── siteincharge: FK to People
└── onboarding_sites: Reverse FK from OnboardingSite

OnboardingSite (Physical Location)
├── business_unit: FK to Bt
├── conversation_session: OneToOne to ConversationSession
├── zones: Reverse FK from OnboardingZone (1:N)
├── observations: Reverse FK (voice/photo/GPS capture)
├── photos: Reverse FK (vision API integration)
├── sops: Reverse FK (generated procedures)
└── coverage_plans: Reverse FK (guard shift planning)

OnboardingZone (Site Areas)
├── site: FK to OnboardingSite
├── observations: Reverse FK
├── assets: Reverse FK (cameras, DVRs, alarms)
├── checkpoints: Reverse FK (patrol verification)
└── meter_points: Reverse FK (utility tracking)

People (Workers)
├── client: FK to Bt (employer)
├── bu: FK to Bt (assigned site)
└── onboarding_request: Reverse from OnboardingRequest

OnboardingRequest (Worker Intake) ✅ SEPARATE APP
├── conversation_session: FK to ConversationSession
├── person_type: Employee/Contractor/etc.
├── current_state: 11-state workflow
└── tasks: Reverse FK from OnboardingTask

ConversationSession (SHARED KERNEL)
├── business_unit: FK to Bt
├── initiated_by: FK to People
├── onboarding_site: OneToOne (optional)
└── Used by: Client, Site, Worker onboarding
```

### Key Architectural Insights

#### ✅ Strengths:
1. **Already partially separated**: `people_onboarding` is a separate app
2. **Models comply with size limits**: All < 150 lines
3. **Clear domain separation**: Site != Worker onboarding
4. **Multi-tenant aware**: TenantAwareModel base class
5. **Security-first**: SecureFileDownloadService, proper permissions

#### ⚠️ Current Issues:
1. **Mixed concerns**: Site onboarding buried in main onboarding app
2. **Unclear boundaries**: What's "onboarding" vs "onboarding_api"?
3. **Shared kernel undefined**: ConversationSession used everywhere
4. **Potential coupling**: Direct FK references between contexts

---

## Bounded Context Definition

### Context 1: Client Onboarding (Business Relationship)

**Ubiquitous Language**:
- Client, Business Unit, Contract, Subscription, Billing
- Lead → Prospect → Active Client → Churned

**Bounded Models**:
```python
# apps/client_onboarding/models/
- BusinessUnit (Bt renamed for clarity)
- Contract
- Subscription
- ClientPreferences
```

**Responsibilities**:
- Establish business relationship
- Configure billing and contracts
- Set up organizational hierarchy
- Define client preferences

**Complexity**: LOW (configuration-driven)

**Lifecycle**: Months to years

**Dependencies**:
- Shared Kernel: ConversationSession (for conversational setup)
- Downstream: Site context (clients have sites)

---

### Context 2: Site Onboarding (Physical Location)

**Ubiquitous Language**:
- Site, Zone, Checkpoint, Post, SOP, Asset, Observation, Survey
- Survey → Planning → Setup → Operational → Decommission

**Bounded Models**:
```python
# apps/site_onboarding/models/
- OnboardingSite
- OnboardingZone (CRITICAL: zone-centric architecture)
- Observation (multimodal: voice + photo + GPS)
- SitePhoto (vision API integration)
- Asset (security equipment)
- Checkpoint (patrol verification)
- MeterPoint (utility tracking)
- SOP (generated procedures)
- CoveragePlan (guard scheduling)
```

**Responsibilities**:
- Conduct site surveys (voice-first, multimodal)
- Document physical layout and zones
- Identify security vulnerabilities
- Generate SOPs from observations
- Plan guard coverage
- Track assets and equipment
- Define patrol routes and checkpoints

**Complexity**: VERY HIGH
- Multimodal data capture
- Vision AI integration
- Regulatory compliance (RBI, ASIS, ISO)
- Geospatial analysis
- LLM-powered SOP generation

**Lifecycle**: Weeks to months (per site)

**Dependencies**:
- Upstream: Client context (site belongs to client)
- Shared Kernel: ConversationSession, AuthoritativeKnowledge
- Downstream: Worker context (workers assigned to sites)

---

### Context 3: Worker Onboarding (Human Resource)

**Ubiquitous Language**:
- Employee, Contractor, Consultant, Vendor Personnel, Temporary Worker
- Onboarding Request, Task, Provisioning, Training, Certification
- Requisition → Screening → Background Check → Provisioning → Training → Active

**Bounded Models**:
```python
# apps/people_onboarding/models/ ✅ ALREADY EXISTS
- OnboardingRequest
- OnboardingTask
- WorkerCertification (future)
- TrainingRecord (future)
- BackgroundCheck (future)
```

**Responsibilities**:
- Manage worker intake process
- Track onboarding checklist (documentation, verification, training)
- Handle background checks and certifications
- Provision access (badges, logins, equipment)
- Track training completion
- Manage different worker types (employee, contractor, vendor)

**Complexity**: HIGH
- Regulatory compliance (background checks)
- Multi-role support (employees, contractors, consultants)
- Document verification
- Training tracking
- Equipment provisioning

**Lifecycle**: Days to weeks (per worker)

**Dependencies**:
- Upstream: Client context (worker employed by client)
- Upstream: Site context (worker assigned to site)
- Shared Kernel: ConversationSession, People model

---

### Shared Kernel (Cross-Cutting Infrastructure)

**Purpose**: Common infrastructure used by ALL contexts

**Models**:
```python
# apps/core_onboarding/models/ (or apps/core/)
- ConversationSession (AI orchestration)
- LLMRecommendation (maker-checker pattern)
- AuthoritativeKnowledge (compliance knowledge base)
- AuthoritativeKnowledgeChunk (RAG)
- AIChangeSet (change management)
- AIChangeRecord (rollback capability)
- TypeAssist (classification system)
- GeofenceMaster (location definitions)
```

**Services**:
```python
# apps/core_onboarding/services/
- LLM services (Maker, Checker, Consensus)
- Knowledge services (embeddings, vector stores, RAG)
- Translation services
- Circuit breaker
- DLQ handler
```

**Background Tasks**:
```python
# background_tasks/
- onboarding_base_task.py (task infrastructure)
- onboarding_retry_strategies.py (resilience)
- dead_letter_queue.py (failure handling)
```

**Characteristics**:
- **Stability**: HIGH (changes slowly, affects all contexts)
- **Ownership**: Core platform team
- **Testing**: Extra rigorous (failures cascade)

---

## Architecture Decision Rationale

### Option A: Separate Microservices ❌ NOT RECOMMENDED

**Structure**:
```
┌─────────────────────────┐
│ Client Service          │
│ - Own database          │
│ - Own deployment        │
│ - REST API              │
└─────────────────────────┘
           ↓ HTTP
┌─────────────────────────┐
│ Site Service            │
│ - Own database          │
│ - Own deployment        │
│ - REST API              │
└─────────────────────────┘
           ↓ HTTP
┌─────────────────────────┐
│ Worker Service          │
│ - Own database          │
│ - Own deployment        │
│ - REST API              │
└─────────────────────────┘
```

**Pros**:
- ✅ Independent scaling
- ✅ Technology heterogeneity
- ✅ Independent deployment
- ✅ Team autonomy (physical boundaries)

**Cons**:
- ❌ **Distributed transactions**: Assigning worker to site = 3 service calls + saga pattern
- ❌ **Data consistency**: Eventual consistency unacceptable for security operations
- ❌ **Network latency**: Real-time checkpoint verification requires sub-100ms response
- ❌ **Operational cost**: 3x infrastructure (databases, load balancers, monitoring)
- ❌ **Deployment complexity**: Coordinated releases, version compatibility matrix
- ❌ **Testing complexity**: Integration tests require all services running
- ❌ **Data duplication**: Client info duplicated in Site and Worker services
- ❌ **Query complexity**: "Show all workers at all sites for client X" = N+1 HTTP calls

**When to reconsider**:
- Team size > 30 developers
- Independent scaling proven necessary
- Organizational boundaries exist (separate companies)

---

### Option B: Bounded Contexts in Monolith ✅ RECOMMENDED

**Structure**:
```
┌───────────────────────────────────────────────┐
│          Django Monolith                       │
│                                                │
│  ┌─────────────────┐  ┌──────────────────┐   │
│  │ Client Context  │  │ Site Context     │   │
│  │ - Bt           │  │ - OnboardingSite │   │
│  │ - Contract     │  │ - Zone           │   │
│  └────────┬────────┘  └────────┬─────────┘   │
│           │                     │              │
│           └─────────┬───────────┘              │
│                     │                          │
│           ┌─────────▼──────────┐               │
│           │ Worker Context     │               │
│           │ - OnboardingReq    │               │
│           │ - Task             │               │
│           └────────────────────┘               │
│                                                │
│           Shared Database (ACID)               │
│           Shared Infrastructure                │
└───────────────────────────────────────────────┘
```

**Pros**:
- ✅ **ACID transactions**: Worker assignment = single transaction, guaranteed consistency
- ✅ **Performance**: In-process calls (microseconds, not milliseconds)
- ✅ **Operational simplicity**: 1 deployment, 1 database, 1 monitoring stack
- ✅ **Data integrity**: Foreign keys enforced at database level
- ✅ **Query efficiency**: JOINs are fast, no N+1 HTTP problem
- ✅ **Testing simplicity**: Standard Django tests, no mocking HTTP
- ✅ **Domain clarity**: Bounded contexts provide clear separation
- ✅ **Shared kernel**: ConversationSession, knowledge base, AI services reused
- ✅ **Gradual extraction**: Can extract to microservices later if needed

**Cons**:
- ⚠️ **Scaling granularity**: Must scale entire application (but: premature optimization)
- ⚠️ **Deployment coupling**: Deploy all contexts together (but: faster releases)
- ⚠️ **Technology lock-in**: All contexts use Django (but: expertise in one stack better)

**Why it wins**:
1. **Your current scale doesn't justify microservices** (security guard ops is regional, not global scale)
2. **Domain coupling is real** (workers, sites, clients are operationally linked)
3. **ACID guarantees matter** (security operations can't tolerate eventual consistency)
4. **You already use this pattern** (Django monolith with modular apps)
5. **Industry consensus** (DDD says: bounded contexts first, microservices later)

---

### Option C: Current State (Mixed) ❌ NEEDS IMPROVEMENT

**Structure**:
```
apps/onboarding/          (EVERYTHING mixed together)
apps/people_onboarding/   (Worker onboarding separated)
apps/onboarding_api/      (Conversational AI mixed)
```

**Problems**:
- ⚠️ Site onboarding buried in generic "onboarding" app
- ⚠️ Unclear what "onboarding" means (client? site? conversation?)
- ⚠️ New developers confused about where to add code
- ⚠️ Testing difficult (can't test site onboarding in isolation)

---

## Implementation Roadmap

### Phase 1: Clarify Context Boundaries (2-3 weeks)

#### Week 1: Extract Site Context

**Create new app**:
```bash
python manage.py startapp site_onboarding
```

**Move models** (with backward compatibility shims):
```python
# apps/site_onboarding/models/
from apps.onboarding.models.site_onboarding import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto,
    Asset,
    Checkpoint,
    MeterPoint,
    SOP,
    CoveragePlan
)

# apps/onboarding/models/site_onboarding.py (SHIM for backward compatibility)
# Keep for 1 release, then remove
from apps.site_onboarding.models import *
import warnings
warnings.warn("Import from apps.site_onboarding instead", DeprecationWarning)
```

**Move services**:
```python
# apps/site_onboarding/services/
- site_audit_service.py
- zone_analysis_service.py
- sop_generation_service.py
- coverage_planning_service.py
```

**Move API endpoints**:
```python
# apps/site_onboarding/api/
- viewsets/site_viewsets.py
- serializers/site_serializers.py
- urls.py
```

#### Week 2: Clarify Client Context

**Rename for clarity**:
```bash
# Keep apps/onboarding/ but clarify it's client-focused
# OR rename to apps/client_onboarding/
```

**Extract client-specific models**:
```python
# apps/client_onboarding/models/ (or clarified apps/onboarding/)
- business_unit.py (Bt model)
- contract.py
- subscription.py
- client_preferences.py
```

**Define client services**:
```python
# apps/client_onboarding/services/
class ClientOnboardingService:
    def create_client(self, name, ...): ...
    def get_client_sites(self, client_id): ...  # Returns IDs, not objects
    def update_client_preferences(self, client_id, prefs): ...
```

#### Week 3: Define Shared Kernel

**Extract to core**:
```bash
mkdir -p apps/core_onboarding/
```

**Move shared models**:
```python
# apps/core_onboarding/models/
- conversation.py (ConversationSession)
- llm_recommendation.py
- knowledge.py (AuthoritativeKnowledge, chunks)
- changeset.py (AIChangeSet, AIChangeRecord)
- classification.py (TypeAssist, GeofenceMaster)
```

**Move orchestration**:
```python
# apps/core_onboarding/services/
- llm/ (Maker, Checker, Consensus)
- knowledge/ (embeddings, vector stores, RAG)
- integration/ (IntegrationAdapter)
- translation/
```

### Phase 2: Implement Context Interfaces (3-4 weeks)

#### Week 4-5: Service Layer

**Define context boundaries**:
```python
# apps/client_onboarding/services/client_service.py
class ClientService:
    """
    Public interface for Client context.
    NO direct model imports from other contexts allowed.
    """

    def create_client(self, name: str, type: str, preferences: dict) -> str:
        """Returns client_id (UUID string), NOT Bt object"""
        bt = Bt.objects.create(...)
        return str(bt.id)

    def get_client_details(self, client_id: str) -> dict:
        """Returns dict, NOT model instance"""
        bt = Bt.objects.get(id=client_id)
        return {
            'id': str(bt.id),
            'name': bt.buname,
            'type': bt.butype.name,
            ...
        }

# apps/site_onboarding/services/site_service.py
class SiteService:
    """
    Public interface for Site context.
    Takes client_id (string), NOT Bt object.
    """

    def create_site(self, client_id: str, name: str, type: str) -> str:
        """
        Creates site for given client.
        Uses client_id, does NOT import Client models.
        """
        from apps.client_onboarding.models import Bt  # Local import OK
        client = Bt.objects.get(id=client_id)

        site = OnboardingSite.objects.create(
            business_unit=client,  # FK allowed (same database)
            name=name,
            site_type=type
        )
        return str(site.id)

# apps/people_onboarding/services/worker_service.py
class WorkerService:
    """
    Public interface for Worker context.
    Takes site_id and client_id (strings).
    """

    def create_onboarding_request(
        self,
        person_type: str,
        client_id: str,
        site_id: str = None
    ) -> str:
        request = OnboardingRequest.objects.create(
            person_type=person_type,
            # Store IDs, resolve when needed
            context_data={'client_id': client_id, 'site_id': site_id}
        )
        return str(request.uuid)
```

#### Week 6-7: API Layer

**Context-specific URLs**:
```python
# intelliwiz_config/urls_optimized.py
urlpatterns = [
    # Context-specific endpoints
    path('api/v2/client-onboarding/', include('apps.client_onboarding.api.urls')),
    path('api/v2/site-onboarding/', include('apps.site_onboarding.api.urls')),
    path('api/v2/worker-onboarding/', include('apps.people_onboarding.api.urls')),

    # Shared orchestration
    path('api/v2/conversation/', include('apps.core_onboarding.api.urls')),

    # Legacy (keep for backward compatibility, deprecate later)
    path('api/v1/onboarding/', include('apps.onboarding.api.urls')),
]
```

### Phase 3: Extract Conversational AI (2-3 weeks)

#### Week 8-9: Orchestration Layer

**Purpose**: `apps/onboarding_api/` becomes pure orchestration

**Structure**:
```python
# apps/conversation_orchestration/ (renamed from onboarding_api)
├── services/
│   ├── conversation_handlers/
│   │   ├── client_handler.py  # Calls ClientService
│   │   ├── site_handler.py    # Calls SiteService
│   │   └── worker_handler.py  # Calls WorkerService
│   ├── llm/ (MOVE TO core_onboarding)
│   └── knowledge/ (MOVE TO core_onboarding)
├── models.py  # Only ConversationSession (MOVE TO core_onboarding)
└── views/
    ├── conversation_views.py  # Routes to correct handler
    └── analytics_views.py
```

**Handler pattern**:
```python
# apps/conversation_orchestration/services/conversation_handlers/site_handler.py
class SiteConversationHandler:
    """
    Handles conversational site onboarding.
    Uses SiteService (public interface), NOT direct models.
    """

    def __init__(self):
        self.site_service = SiteService()
        self.llm_service = get_llm_service()
        self.knowledge_service = get_knowledge_service()

    def process_user_input(self, session_id: str, user_input: str) -> dict:
        # Get session
        session = ConversationSession.objects.get(session_id=session_id)

        # Generate recommendation via LLM
        recommendation = self.llm_service.generate(user_input, session.context)

        # If user approves, create site via service (NOT direct model)
        if recommendation['action'] == 'create_site':
            site_id = self.site_service.create_site(
                client_id=session.context['client_id'],
                name=recommendation['site_name'],
                type=recommendation['site_type']
            )

            return {'site_id': site_id, 'status': 'created'}
```

#### Week 10: Background Tasks

**Organize by context**:
```python
# background_tasks/
├── client_onboarding/
│   └── client_tasks.py
├── site_onboarding/
│   └── site_tasks.py
├── worker_onboarding/
│   └── worker_tasks.py
├── shared/
│   ├── onboarding_base_task.py
│   ├── retry_strategies.py
│   └── dead_letter_queue.py
└── conversation/
    └── orchestration_tasks.py
```

### Phase 4: Testing & Documentation (2 weeks)

#### Week 11: Context Tests

**Isolated test suites**:
```python
# apps/client_onboarding/tests/
test_client_service.py       # Unit tests for ClientService
test_client_models.py         # Model tests
test_client_api.py            # API endpoint tests

# apps/site_onboarding/tests/
test_site_service.py
test_zone_analysis.py
test_sop_generation.py
test_site_api.py

# apps/people_onboarding/tests/
test_worker_service.py
test_onboarding_workflow.py
test_worker_api.py
```

**Integration tests** (cross-context):
```python
# tests/integration/
test_complete_onboarding_flow.py
"""
Tests full flow:
1. Create client (client context)
2. Create site for client (site context)
3. Create worker onboarding request (worker context)
4. Assign worker to site
5. Verify all contexts updated correctly
"""
```

#### Week 12: Documentation

**Context documentation**:
```markdown
# apps/client_onboarding/README.md
# Client Onboarding Context

## Purpose
Manage business relationships and client setup.

## Bounded Models
- BusinessUnit (Bt): Client hierarchy
- Contract: Service agreements
- Subscription: Billing setup

## Public API
- ClientService: Create, update, query clients
- ClientOnboardingViewSet: REST endpoints

## Dependencies
- Shared Kernel: ConversationSession, TypeAssist
- Downstream: Site context (clients have sites)
```

---

## Migration Strategy

### Strategy A: Big Bang Refactor ❌ HIGH RISK

**Approach**: Rename/move everything at once

**Timeline**: 4-6 weeks

**Pros**:
- Clean break
- No shims/deprecation
- Clear architecture immediately

**Cons**:
- HIGH regression risk (1000+ import changes)
- Entire team blocked during migration
- Rollback difficult
- Production outages likely

**Verdict**: NOT RECOMMENDED for production system

---

### Strategy B: Gradual Extraction ✅ RECOMMENDED

**Approach**: Extract one context per month with backward compatibility

**Timeline**: 3-4 months (phased)

**Migration Phases**:

#### Month 1: Extract Site Context
1. Create `apps/site_onboarding/`
2. Copy models from `apps/onboarding/models/site_onboarding.py`
3. Create shims in old location:
   ```python
   from apps.site_onboarding.models import *
   import warnings
   warnings.warn("Import from apps.site_onboarding", DeprecationWarning)
   ```
4. Update new code to import from new location
5. Leave old imports working (no breakage)
6. Deploy with both paths working

#### Month 2: Clarify Worker Context
1. `apps/people_onboarding/` already exists ✅
2. Add service layer (WorkerService)
3. Define public interface
4. Update documentation
5. No migration needed (already separated)

#### Month 3: Extract Client Context
1. Clarify `apps/onboarding/` is client-focused
2. OR rename to `apps/client_onboarding/`
3. Extract client-specific models (Bt, Contract)
4. Create ClientService
5. Update API endpoints
6. Create shims for backward compatibility

#### Month 4: Clean Up
1. Remove deprecated shims (require all imports updated)
2. Move shared models to `apps/core_onboarding/`
3. Refactor `apps/onboarding_api/` → `apps/conversation_orchestration/`
4. Update all documentation
5. Run full integration test suite
6. Celebrate! 🎉

**Benefits**:
- ✅ Zero downtime
- ✅ Gradual migration (can pause anytime)
- ✅ Backward compatible (no breakage)
- ✅ Team can continue feature work
- ✅ Rollback easy (just don't remove shims)

---

## Success Criteria

### How to Know If This Is Working

#### Developer Experience Metrics:

1. **Onboarding Time**
   - New developer can understand one context in < 30 minutes
   - Can make changes to context without understanding others
   - Clear where to add new features

2. **Code Organization**
   - ✅ Model files < 150 lines (already compliant)
   - ✅ No circular imports between contexts
   - ✅ Each context has independent test suite
   - ✅ API endpoints organized by context

3. **Build & Test Speed**
   - Can run tests for single context in isolation
   - Test suite completes in < 5 minutes
   - CI/CD passes consistently (> 95% success rate)

#### Architectural Health Metrics:

1. **Context Independence**
   - Site onboarding tests don't require client setup
   - Worker tests can use mock client/site IDs
   - Shared kernel has < 10% change rate (stable)

2. **API Clarity**
   - `/api/v2/client-onboarding/` endpoints obvious purpose
   - `/api/v2/site-onboarding/` endpoints obvious purpose
   - `/api/v2/worker-onboarding/` endpoints obvious purpose
   - No "where does this go?" questions

3. **Database Query Patterns**
   - Queries stay within context boundaries (except shared kernel FKs)
   - No accidental cross-context JOINs
   - Foreign keys used for strong relationships (client → site → worker)

#### Business Metrics:

1. **Feature Velocity**
   - Time to add site feature doesn't slow down
   - Worker features don't break site features
   - Clear ownership (site team owns site context)

2. **Bug Isolation**
   - Site bugs don't affect worker onboarding
   - Client bugs don't break site surveys
   - Blast radius < 1 context

3. **Deployment Confidence**
   - > 95% deployment success rate
   - Rollback time < 5 minutes
   - Zero-downtime deployments

---

## Decision Matrix: When to Reconsider Microservices

**Current Decision**: Bounded contexts in monolith ✅

**Reevaluate when**:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| **Team Size** | > 30 developers | Consider service split by team boundaries |
| **Scaling Needs** | Site context requires 10x scale vs others | Extract site to microservice |
| **Deployment Frequency** | > 10 deploys/day | Evaluate independent deployment needs |
| **Data Volume** | > 100M sites or workers | Consider read replicas or CQRS |
| **Geographic Distribution** | Multi-region with < 100ms latency req | Consider edge deployment |
| **Technology Heterogeneity** | Need to use Rust for site processing | Allow different stack per context |

**Red Flags (Don't Extract Yet)**:
- "It would be cleaner" (not a business reason)
- "We want to learn microservices" (use side project)
- "Microservices are best practice" (not for your scale)
- "Other companies do it" (they have different constraints)

---

## Conclusion & Next Steps

### Summary

**RECOMMENDATION**: 3 Bounded Contexts in Django Monolith

**Rationale**:
1. ✅ Domain naturally separates (clients, sites, workers)
2. ✅ You've already started (people_onboarding exists)
3. ✅ Avoids microservices complexity (distributed transactions, network, ops burden)
4. ✅ Maintains ACID guarantees (critical for security guard operations)
5. ✅ Keeps deployment simple (single service, proven infrastructure)
6. ✅ Aligned with DDD best practices (bounded contexts first)
7. ✅ Can extract to microservices later if scale demands (stepping stones)

**Architecture**:
```
Django Monolith
├── apps/client_onboarding/   (Business relationships)
├── apps/site_onboarding/     (Physical locations)
├── apps/people_onboarding/   (Worker intake) ✅ EXISTS
└── apps/core_onboarding/     (Shared kernel)
```

**Migration**: Gradual extraction over 3-4 months with backward compatibility

### Immediate Next Steps

**Week 1 Actions**:
1. ✅ Review this document with team
2. ✅ Decide on naming (keep `onboarding` or rename to `client_onboarding`?)
3. ✅ Create `apps/site_onboarding/` directory structure
4. ✅ Start model migration with shims

**Month 1 Goal**: Site context fully extracted, backward compatible

**Month 2 Goal**: Worker context clarified with service layer

**Month 3 Goal**: Client context separated

**Month 4 Goal**: Clean up, remove shims, full documentation

### Questions for Decision

1. **Naming**: Keep `apps/onboarding/` (clarify as client-focused) OR rename to `apps/client_onboarding/`?
2. **Timeline**: 3-4 months acceptable? Or need faster/slower?
3. **Team Structure**: Will teams align with contexts (site team, worker team)?
4. **Deployment Strategy**: Keep single deployment or move to separate deploys per context?
5. **Database Strategy**: Keep shared database or split later?

---

## Appendix: Research Sources

### Web Research (November 3, 2025):
1. **Multi-tenant architecture**: Relevant Software, Brocoders, AWS SaaS Lens
2. **Domain-driven design**: Vladikk.com, Microsoft Azure, Martin Fowler
3. **Facility management**: Trackforce, TrackTik, Belfry Software
4. **Microservices vs monolith**: Sam Newman, Eric Evans

### Codebase Analysis:
- Explored 70+ files across apps/onboarding/, apps/people_onboarding/, apps/onboarding_api/
- Analyzed models, services, views, background tasks
- Reviewed database relationships and foreign keys

### Industry Consensus:
- **2025 Trend**: Bounded contexts > Microservices for most teams
- **DDD Principle**: Biggest cohesive service first, split later
- **Scale Reality**: Microservices overhead justified at > 30 developers or 10x scale differences

---

**Document Version**: 1.0
**Last Updated**: November 3, 2025
**Author**: Claude Code (Architecture Analysis)
**Review Status**: Awaiting team feedback
**Next Review**: After Month 1 (site context extraction complete)
