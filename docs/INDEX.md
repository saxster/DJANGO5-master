# Documentation Index

> **Last Updated:** November 7, 2025
> **Purpose:** Central navigation for all project documentation

---

## 📋 Quick Start

| Document | Purpose | Audience |
|----------|---------|----------|
| [CLAUDE.md](../CLAUDE.md) | Project instructions for AI assistants | Developers, AI |
| [README.md](../README.md) | Project overview and setup | All users |
| [CHANGELOG.md](../CHANGELOG.md) | Version history | All users |
| [PRE_DEPLOYMENT_CHECKLIST.md](../PRE_DEPLOYMENT_CHECKLIST.md) | Deployment validation | DevOps |

---

## 🏗️ Architecture & Design

### Core Architecture
- [System Architecture](architecture/SYSTEM_ARCHITECTURE.md) - Complete system overview
- [Query Optimization Architecture](architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md) - N+1 detection and optimization patterns
- [Refactoring Patterns](architecture/REFACTORING_PATTERNS.md) - God file refactoring guide
- [Refactoring Playbook](architecture/REFACTORING_PLAYBOOK.md) ⚠️ **MANDATORY** - Future refactoring guide

### Architecture Decision Records (ADRs)
Located in `architecture/adr/`:
- [ADR-001: File Size Limits](architecture/adr/001-file-size-limits.md)
- [ADR-002: Circular Dependency Prevention](architecture/adr/002-circular-dependency-prevention.md)
- [ADR-003: Service Layer Pattern](architecture/adr/003-service-layer-pattern.md)
- [ADR-004: Testing Strategy](architecture/adr/004-testing-strategy.md)
- [ADR-005: Exception Handling](architecture/adr/005-exception-handling-patterns.md)
- [ADR-006: Background Task Organization](architecture/adr/006-background-task-organization.md)
- [ADR-007: API Versioning Strategy](architecture/adr/007-api-versioning-strategy.md)

### Reference Architecture
Located in `reference/architecture/`:
- Circular dependency patterns
- Exception handling standards
- DateTime migration guides
- Message bus patterns
- Multi-tenancy architecture
- God file analysis

---

## 🎯 Features & Domains

### Activity Management
**Location:** `features/activity/`
- Activity timeline implementation
- Job models reference
- Meter intelligence platform

### Attendance & Scheduling
**Location:** `features/attendance/`
- Attendance implementation guide
- Shift tracker system
- Smart assignment algorithms
- Integration guides

### Administration
**Location:** `features/admin/`
- Admin help system
- AI mentor integration
- Approval workflows
- Quick actions
- Saved views
- Team dashboard

### Help Center & Support
**Location:** `features/help_center/`
- Help center implementation
- Best practices articles
- Decision trees and checklists

### NOC & Monitoring
**Location:** `features/noc/`
- NOC intelligence system
- Priority alerts
- Alert clustering
- Streaming anomaly detection
- Natural language query platform

### Ontology & Knowledge
**Location:** `features/ontology/`
- Ontology expansion plans
- Code quality patterns
- Performance patterns
- Security knowledge

### Reports & Analytics
**Location:** `features/reports/`
- Intelligent report generation
- Report architecture
- Performance analytics

### Wellness & Mental Health
**Location:** `features/wellness/`
- Mental health interventions
- Journal integration

### ML & AI
**Location:** `features/ml/`
- ML stack implementation
- AI models structure
- Prediction logging

### Y_Helpdesk
**Location:** `features/y_helpdesk/`
- Issue tracker
- Tickets best practices

### People Management
**Location:** `features/peoples/`
- People models and services

### Onboarding
**Location:** `features/onboarding/`
- Client onboarding
- Multi-entity architecture

---

## 🚀 Workflows & Operations

**Location:** `workflows/`
- [Common Commands](workflows/COMMON_COMMANDS.md)
- [Background Processing](workflows/BACKGROUND_PROCESSING.md)
- [Celery Configuration Guide](workflows/CELERY_CONFIGURATION_GUIDE.md) ⚠️ **MANDATORY**
- [Idempotency Framework](workflows/IDEMPOTENCY_FRAMEWORK.md)
- Approval workflows

---

## 🧪 Testing & Quality

### Testing Documentation
**Location:** `testing/` and `deliverables/quality/`
- [Testing & Quality Guide](testing/TESTING_AND_QUALITY_GUIDE.md)
- Test coverage reports
- Verification reports
- ML validation checklists

### Quality Training
**Location:** `training/`
- [Quality Standards Training](training/QUALITY_STANDARDS_TRAINING.md)
- [Refactoring Training](training/REFACTORING_TRAINING.md)
- [Service Layer Training](training/SERVICE_LAYER_TRAINING.md)
- [Testing Training](training/TESTING_TRAINING.md)

### Quick References
**Location:** `quick_reference/`
- [Exception Handling Quick Reference](quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md)
- Logging standards
- Code quality metrics
- Model Meta completeness

---

## 📡 API & Integration

**Location:** `api/`
- [Type-Safe API Contracts](api/TYPE_SAFE_CONTRACTS.md)
- REST API migration guides
- API changelog (v1 to v2)

---

## 🔐 Security

**Location:** `reference/security/`
- WebSocket metrics authentication
- SSO rate limiting
- Secure file download
- Work order security
- IDOR vulnerability audits
- Security test suites

---

## 🚢 Deployment

### Deployment Guides
**Location:** `deployment/`
- Docker setup
- Hostinger VPS guide
- Biometric encryption
- Deployment checklists

### Infrastructure
**Location:** `deployment/infrastructure/`
- MQTT/Mosquitto setup
- MQTT pipeline testing
- Alternative MQTT configurations
- Docker implementation

---

## ⚡ Performance & Optimization

**Location:** `reference/optimization/`
- N+1 query optimization
- Caching strategies
- Magic numbers extraction
- Query optimization reports
- Quality metrics

---

## 📊 Operations

**Location:** `operations/`
- Fraud detection guides
- Conformal prediction
- Drift monitoring
- Message bus operations
- Operator guides
- NON_NEGOTIABLES policies

---

## 📱 Mobile Development

### Kotlin Frontend
**Location:** `kotlin-frontend/`
- API contracts (foundation, wellness)
- Claude Skills integration
- Code generation plans
- Implementation roadmaps
- Popular skills catalog

### Skills Guides
**Location:** `kotlin-frontend/skills/`
- Android permissions & GPS
- Android security checklist
- Compose performance optimization
- Kotlin coroutines safety
- Offline-first architecture
- Retrofit error handling
- Room database implementation

---

## 📚 Reference Documentation

### Configuration
**Location:** `configuration/`
- [Settings & Configuration](configuration/SETTINGS_AND_CONFIG.md)

### Diagrams
**Location:** `diagrams/`
- Cache backend decision tree
- Celery decorator flowchart
- Flake8 decisions

### Plans
**Location:** `plans/`
- Design documents (dated 2025-11-01 through 11-04)

---

## 📖 Project History

### Completed Sessions
**Location:** `project-history/`
- [Project Retrospective](PROJECT_RETROSPECTIVE.md) - Phase 1-6 journey
- Implementation reports
- Final summaries
- ULTRATHINK session reports

### Phase Documentation
**Location:** `project-history/phases/`
- Phase 1: God file refactoring, security fixes
- Phase 2: Code quality improvements
- Phase 3: AI intelligence
- Phase 4: Enterprise features
- Phase 5: UX polish
- Phase 6: Data utilization
- Phase 7: IDE integration, documentation

### Task Reports
**Location:** `project-history/tasks/`
- Individual task completion reports
- Agent execution summaries

---

## 🔧 Troubleshooting

**Location:** `troubleshooting/`
- [Common Issues](troubleshooting/COMMON_ISSUES.md) - Solutions to frequent problems

---

## 🗂️ Special Topics

### Domain-Specific Systems
- [Domain-Specific Systems](features/DOMAIN_SPECIFIC_SYSTEMS.md)
  - Security AI Mentor (7 pillars)
  - Stream Testbench
  - Caching Strategy
  - Face Recognition
  - NOC Intelligence
  - Reports System

### Development Environment
**Location:** `development/`
- Onboarding guide
- IDE setup
- Quality standards

### Policies
**Location:** `policies/` or `security/policies/`
- GPS data retention

### Tools
**Location:** `tools/` or `development/tools/`
- Print statement removal utilities

---

## 🗃️ Archive

**Location:** `archive/`
- Deprecated documentation
- Historical completion reports
- Cleanup scripts
- Duplicate file versions

---

## 📍 Directory Structure

```
docs/
├── INDEX.md (this file)
├── PROJECT_RETROSPECTIVE.md
├── architecture/
│   ├── adr/ (7 ADRs)
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── QUERY_OPTIMIZATION_ARCHITECTURE.md
│   ├── REFACTORING_PATTERNS.md
│   └── REFACTORING_PLAYBOOK.md
├── features/
│   ├── activity/
│   ├── admin/
│   ├── analytics/
│   ├── attendance/
│   ├── help_center/
│   ├── ml/
│   ├── noc/
│   ├── onboarding/
│   ├── ontology/
│   ├── peoples/
│   ├── reports/
│   ├── wellness/
│   ├── y_helpdesk/
│   └── DOMAIN_SPECIFIC_SYSTEMS.md
├── workflows/
│   ├── COMMON_COMMANDS.md
│   ├── BACKGROUND_PROCESSING.md
│   ├── CELERY_CONFIGURATION_GUIDE.md
│   └── IDEMPOTENCY_FRAMEWORK.md
├── testing/
│   └── TESTING_AND_QUALITY_GUIDE.md
├── training/
│   ├── QUALITY_STANDARDS_TRAINING.md
│   ├── REFACTORING_TRAINING.md
│   ├── SERVICE_LAYER_TRAINING.md
│   └── TESTING_TRAINING.md
├── quick_reference/
│   ├── EXCEPTION_HANDLING_QUICK_REFERENCE.md
│   └── (other quick refs)
├── api/
│   ├── TYPE_SAFE_CONTRACTS.md
│   └── changelog/
├── deployment/
│   ├── infrastructure/
│   └── (deployment guides)
├── reference/
│   ├── architecture/
│   ├── optimization/
│   └── security/
├── project-history/
│   ├── phases/
│   ├── tasks/
│   ├── ultrathink/
│   └── (historical reports)
├── deliverables/
│   ├── features/
│   ├── infrastructure/
│   └── quality/
├── operations/
├── configuration/
├── security/
├── kotlin-frontend/
│   └── skills/
├── ontology/
├── help_center/
│   └── articles/
├── diagrams/
├── plans/
├── development/
├── noc/
├── troubleshooting/
└── archive/
```

---

## 🔍 Finding Documentation

### By Topic
- **Getting Started**: README.md, CLAUDE.md
- **Architecture Decisions**: `architecture/adr/`
- **Feature Implementation**: `features/{domain}/`
- **Code Quality**: `training/`, `quick_reference/`
- **Deployment**: `deployment/`
- **Troubleshooting**: `troubleshooting/COMMON_ISSUES.md`

### By Audience
- **New Developers**: README.md, `development/`, `training/`
- **AI Assistants**: CLAUDE.md, `architecture/`, `quick_reference/`
- **DevOps**: `deployment/`, PRE_DEPLOYMENT_CHECKLIST.md
- **Architects**: `architecture/`, `features/DOMAIN_SPECIFIC_SYSTEMS.md`
- **Quality Engineers**: `testing/`, `training/QUALITY_STANDARDS_TRAINING.md`

### By Activity
- **Refactoring Code**: `architecture/REFACTORING_PLAYBOOK.md`, `training/REFACTORING_TRAINING.md`
- **Writing Tests**: `testing/TESTING_AND_QUALITY_GUIDE.md`, `training/TESTING_TRAINING.md`
- **Implementing Services**: `training/SERVICE_LAYER_TRAINING.md`, `architecture/adr/003-service-layer-pattern.md`
- **Optimizing Queries**: `architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md`, `reference/optimization/`
- **Deploying**: `deployment/`, PRE_DEPLOYMENT_CHECKLIST.md

---

## 📝 Document Naming Conventions

### Current Standards
- **Core Docs**: ALL_CAPS.md (e.g., SYSTEM_ARCHITECTURE.md)
- **ADRs**: NNN-kebab-case.md (e.g., 001-file-size-limits.md)
- **Feature Docs**: PascalCase or kebab-case (e.g., IMPLEMENTATION_GUIDE.md)
- **Guides**: {Topic}_{Type}.md (e.g., CELERY_CONFIGURATION_GUIDE.md)

### File Organization
- **Root**: Only CLAUDE.md, README.md, CHANGELOG.md, PRE_DEPLOYMENT_CHECKLIST.md
- **Features**: Feature-specific docs in `features/{domain}/`
- **History**: Completion reports in `project-history/`
- **Reference**: Technical references in `reference/{category}/`

---

## 🤝 Contributing to Documentation

1. **New Features**: Add documentation to `features/{domain}/`
2. **Architecture Changes**: Update ADRs or create new ones
3. **Process Changes**: Update workflow docs
4. **Troubleshooting**: Add to `troubleshooting/COMMON_ISSUES.md`
5. **Always Update**: This INDEX.md file

---

## 📧 Support

- **Documentation Issues**: Create ticket with "docs" label
- **Missing Documentation**: Request in team channel
- **Outdated Content**: Submit PR with updates

---

**Total Documentation Files:** ~350 organized files
**Root Files:** 3 (CLAUDE.md, README.md, CHANGELOG.md)
**Documentation Coverage:** Comprehensive across all domains
