# 🎯 Phases 2-5: Detailed Execution Plan
## Generic Exception Remediation - Complete Implementation Guide

**Project:** Exception Handling Remediation (Rule #11 Compliance)
**Current Status:** Phase 1 Complete (6 files, 15 violations fixed) ✅
**Remaining Work:** Phases 2-5 (~2,445 violations in ~498 files)
**Estimated Timeline:** 9-10 working days

---

## 📊 EXECUTION OVERVIEW

### Timeline Summary
| Phase | Duration | Files | Violations | Strategy |
|-------|----------|-------|------------|----------|
| Phase 1 | ✅ 2 days | 6 | 15 → 0 | Manual (COMPLETE) |
| Phase 2 | 3 days | 90 | ~200 | 30% manual, 70% patterns |
| Phase 3 | 3 days | 200 | ~800 | 40% manual, 60% patterns |
| Phase 4 | 2 days | 150 | ~600 | 50% manual, 50% patterns |
| Phase 5 | 2 days | N/A | Validation | Testing & deployment |
| **TOTAL** | **12 days** | **~450** | **~2,464** | **Mixed approach** |

---

## 🗓️ PHASE 2: CORE & SERVICE LAYER (Days 3-5)

### DAY 3: Core Utilities & Infrastructure

#### Morning Session (4 hours)

**TASK 2.1: Fix Core Utility Modules (apps/core/utils_new/)**
**Expected:** 10-15 files, ~25 violations

**Files to Fix:**
```bash
# List files with violations
apps/core/utils_new/upload_utils.py
apps/core/utils_new/business_logic.py
apps/core/utils_new/db_utils.py
apps/core/utils_new/file_utils.py
apps/core/utils_new/string_utils.py
apps/core/utils_new/sentinel_resolvers.py
```

**Fix Pattern:**
```python
# For utility functions, use specific exceptions based on operation:

# Database utilities
try:
    result = db_operation()
except (DatabaseError, OperationalError) as e:
    correlation_id = ErrorHandler.handle_exception(e, context={'operation': 'db_util'})
    raise DatabaseException(f"Database operation failed (ID: {correlation_id})") from e

# File utilities
try:
    file_result = file_operation()
except (OSError, IOError, PermissionError) as e:
    raise FileOperationException(f"File operation failed: {str(e)}") from e

# String/data utilities
try:
    processed = process_data()
except (ValueError, TypeError, AttributeError) as e:
    raise ValidationError(f"Data processing failed: {str(e)}") from e
```

**Validation Commands:**
```bash
# After fixing each file
python3 -m py_compile apps/core/utils_new/[filename].py

# Scan for remaining violations
find apps/core/utils_new/ -name "*.py" -exec grep -l "except Exception" {} \;

# Should return empty or significantly fewer files
```

#### Afternoon Session (4 hours)

**TASK 2.2: Fix Caching Layer**
**Expected:** 8-10 files, ~15 violations

**Files:**
```bash
apps/core/cache/__init__.py
apps/core/cache/materialized_view_select2.py
apps/core/cache/postgresql_select2.py
apps/core/caching/decorators.py
apps/core/caching/invalidation.py
apps/core/caching/utils.py
apps/core/caching/form_mixins.py
```

**Fix Pattern for Caching:**
```python
try:
    cached_value = cache.get(key)
    if cached_value is None:
        cached_value = expensive_operation()
        cache.set(key, cached_value, timeout=3600)
except (ConnectionError, TimeoutError) as e:
    logger.warning(f"Cache unavailable: {e}")
    # Fallback to direct computation
    cached_value = expensive_operation()
except (ValueError, TypeError) as e:
    logger.error(f"Cache data error: {e}")
    cache.delete(key)  # Clear corrupted cache
    cached_value = expensive_operation()
```

**TASK 2.3: Fix Core Managers**
**Expected:** 2-3 files, ~5 violations

```bash
apps/core/managers/tenant_manager.py
apps/core/managers/optimized_managers.py
```

**Fix Pattern:** Use `DatabaseError`, `ValidationError`, `ObjectDoesNotExist`

---

### DAY 4: Service Layer & Middleware

#### Morning Session (4 hours)

**TASK 2.4: Fix Core Service Layer (CRITICAL)**
**Expected:** 12-15 files, ~30 violations

**Priority Order:**
1. **CRITICAL (Manual Review Required):**
   ```bash
   apps/core/services/base_service.py          # Service base class - DONE partially in Phase 1
   apps/core/services/transaction_manager.py   # Has 6 violations
   apps/core/services/validation_service.py    # Has 3 violations
   apps/core/services/query_service.py         # Has 8 violations
   apps/core/services/response_service.py      # Has 2 violations
   ```

2. **HIGH (Pattern-based Fix):**
   ```bash
   apps/core/services/task_webhook_service.py  # Has 4 violations
   apps/core/services/query_optimization_service.py  # Has 3 violations
   apps/core/services/encryption_key_manager.py     # Has 7 violations
   apps/core/services/sql_injection_monitor.py      # Has 2 violations
   apps/core/services/sql_injection_scanner.py      # Has 1 violation
   ```

3. **MEDIUM (Can Use Templates):**
   ```bash
   apps/core/services/async_api_service.py     # Has 9 violations
   apps/core/services/async_pdf_service.py     # Has 7 violations
   apps/core/services/geofence_service.py      # Has 8 violations
   apps/core/services/speech_to_text_service.py  # Has 10 violations
   ```

**Fix Strategy by Service Type:**

**Transaction Manager:**
```python
try:
    saga_result = execute_saga(saga_id)
except (DatabaseError, IntegrityError) as e:
    logger.error(f"Transaction failed: {e}", exc_info=True)
    rollback_saga(saga_id)
    raise DatabaseException("Transaction rolled back") from e
except ValidationError as e:
    logger.warning(f"Validation failed in transaction: {e}")
    raise BusinessRuleValidationException(str(e)) from e
```

**API Service:**
```python
try:
    response = requests.post(endpoint, json=data, timeout=30)
    response.raise_for_status()
except requests.Timeout as e:
    raise IntegrationException("API timeout") from e
except requests.HTTPError as e:
    if e.response.status_code == 401:
        raise AuthenticationError("API auth failed")
    elif e.response.status_code >= 500:
        raise IntegrationException(f"API error: {e.response.status_code}")
    else:
        raise APIException(f"API request failed: {e.response.text}")
except requests.RequestException as e:
    raise IntegrationException("Network error") from e
```

#### Afternoon Session (4 hours)

**TASK 2.5: Fix Security Middleware (CRITICAL)**
**Expected:** 10-12 files, ~20 violations

**Files (All require manual review):**
```bash
apps/core/middleware/graphql_csrf_protection.py         # CRITICAL
apps/core/middleware/graphql_rate_limiting.py          # CRITICAL
apps/core/middleware/file_upload_security_middleware.py  # CRITICAL
apps/core/middleware/logging_sanitization.py           # CRITICAL
apps/core/middleware/performance_monitoring.py
apps/core/middleware/query_optimization_middleware.py
apps/core/middleware/smart_caching_middleware.py
apps/core/middleware/api_authentication.py             # CRITICAL
apps/core/middleware/graphql_origin_validation.py      # CRITICAL
```

**Middleware Exception Pattern:**
```python
def process_request(self, request):
    try:
        # Middleware logic
        validation_result = validate_request(request)
    except (ValidationError, ValueError) as e:
        logger.warning(f"Request validation failed: {e}", extra={
            'path': request.path,
            'method': request.method
        })
        return HttpResponseBadRequest("Invalid request")
    except PermissionDenied as e:
        logger.warning(f"Permission denied: {e}", extra={'user_id': request.user.id})
        raise  # Let Django handle
    except (DatabaseError, OperationalError) as e:
        logger.error(f"Database error in middleware: {e}", exc_info=True)
        return HttpResponse("Service unavailable", status=503)
```

---

### DAY 5: GraphQL Layer & Management Commands

#### Morning Session (4 hours)

**TASK 2.6: Fix GraphQL Layer (HIGHEST PRIORITY)**
**Expected:** 8-10 files, ~25 violations

**Critical Files:**
```bash
# MUST be fixed - SQL injection prevention
apps/core/queries/__init__.py                    # Core query module
apps/core/graphql_security.py                    # Security checks
apps/core/security/graphql_query_analysis.py    # Query analysis

# GraphQL service layer
apps/service/utils.py                            # 20 violations - CRITICAL
apps/service/mutations.py                        # Mutation handlers
apps/service/queries/*.py                        # Query resolvers
```

**GraphQL Exception Pattern:**
```python
# In resolvers
def resolve_field(self, info, **kwargs):
    try:
        result = fetch_data(kwargs)
        return result
    except (ValidationError, ValueError) as e:
        logger.warning(f"GraphQL validation error: {e}")
        raise GraphQLError(f"Invalid input: {str(e)}") from e
    except AuthenticationError as e:
        logger.warning(f"GraphQL auth error: {e}")
        raise GraphQLError("Authentication required") from e
    except (DatabaseError, OperationalError) as e:
        logger.error(f"GraphQL database error: {e}", exc_info=True)
        raise GraphQLError("Service temporarily unavailable") from e
    except PermissionDenied as e:
        raise GraphQLError("Permission denied") from e

# In mutations
@login_required
def mutate(cls, root, info, input):
    try:
        result = perform_mutation(input)
        return SuccessResponse(result=result)
    except AuthenticationError as e:
        raise GraphQLError("Authentication failed") from e
    except ValidationError as e:
        raise GraphQLError(f"Validation failed: {str(e)}") from e
    except IntegrityError as e:
        raise GraphQLError("Record already exists") from e
    except (DatabaseError, OperationalError) as e:
        logger.error(f"Database error in mutation: {e}", exc_info=True)
        raise GraphQLError("Service unavailable") from e
```

**Specific Fix for apps/service/utils.py (20 violations):**
This is the most critical file - requires careful manual review of each exception handler.

#### Afternoon Session (4 hours)

**TASK 2.7: Fix Management Commands**
**Expected:** 15-20 files, ~25 violations

```bash
apps/core/management/commands/rotate_encryption_keys.py
apps/core/management/commands/analyze_performance.py
apps/core/management/commands/warm_caches.py
apps/core/management/commands/invalidate_caches.py
apps/core/management/commands/audit_query_optimization.py
apps/core/management/commands/audit_graphql_security.py
apps/core/management/commands/audit_logging_security.py
```

**Management Command Pattern:**
```python
class Command(BaseCommand):
    def handle(self, *args, **options):
        try:
            result = perform_command_logic()
            self.stdout.write(self.style.SUCCESS(f"Success: {result}"))
        except (DatabaseError, OperationalError) as e:
            self.stdout.write(self.style.ERROR(f"Database error: {e}"))
            raise CommandError("Command failed due to database error")
        except (ValidationError, ValueError) as e:
            self.stdout.write(self.style.WARNING(f"Validation error: {e}"))
            raise CommandError(f"Invalid input: {str(e)}")
        except FileNotFoundError as e:
            self.stdout.write(self.style.ERROR(f"File not found: {e}"))
            raise CommandError("Required file missing")
```

**TASK 2.8: Phase 2 Validation & Testing**
```bash
# Validate all Phase 2 files
for file in apps/core/decorators.py apps/core/validation.py apps/core/services/*.py; do
    echo "Validating $file"
    grep -c "except Exception" "$file" || echo "✅ Clean"
done

# Run core tests
python3 -m pytest apps/core/tests/ -v --tb=short -x

# Security tests
python3 -m pytest -m security --tb=short -v

# Create Phase 2 completion report
# PHASE2_EXCEPTION_REMEDIATION_COMPLETE.md
```

**Phase 2 Deliverable:** `PHASE2_EXCEPTION_REMEDIATION_COMPLETE.md`

**Expected Phase 2 Results:**
- 85-90 core files fixed
- <10 violations remaining in core
- All core tests passing

---

## 🗓️ PHASE 3: BUSINESS LOGIC LAYER (Days 6-8)

### DAY 6: Scheduling & Activity Management

#### Morning Session (4 hours)

**TASK 3.1: Complete Scheduling App**
**Expected:** 10-12 files, ~35 violations

**Files:**
```bash
# Services (high priority)
apps/schedhuler/services/task_service.py              # 1 violation
apps/schedhuler/services/jobneed_management_service.py  # 1 violation
apps/schedhuler/services/cron_calculation_service.py  # 7 violations
apps/schedhuler/services.py                            # 3 violations

# Utils & views (medium priority)
apps/schedhuler/utils.py                               # 14 violations - CRITICAL
apps/schedhuler/views_optimized.py                    # 4 violations
apps/schedhuler/views_legacy.py                       # 2 violations
```

**Scheduler Exception Strategy:**
```python
# In scheduling services
try:
    task = create_scheduled_task(config)
except (ValidationError, ValueError) as e:
    raise SchedulingException(f"Invalid task configuration: {e}") from e
except IntegrityError as e:
    raise DatabaseIntegrityException(f"Task already exists: {e}") from e
except (DatabaseError, OperationalError) as e:
    logger.error(f"Database error in scheduling: {e}", exc_info=True)
    raise SchedulingException("Scheduling service unavailable") from e

# In cron calculation
try:
    next_run = calculate_next_run(cron_expression)
except ValueError as e:
    raise SchedulingException(f"Invalid cron expression: {e}") from e
except (OverflowError, OSError) as e:
    raise SchedulingException(f"Cron calculation failed: {e}") from e
```

#### Afternoon Session (4 hours)

**TASK 3.2: Fix Activity Management App**
**Expected:** 15-18 files, ~40 violations

**Files:**
```bash
# Views (user-facing - critical)
apps/activity/views/asset_views.py
apps/activity/views/job_views.py
apps/activity/views/location_views.py
apps/activity/views/attachment_views.py

# Services
apps/activity/services/question_service.py            # 9 violations

# Forms & Utils
apps/activity/forms/question_form.py
apps/activity/forms/location_form.py
apps/activity/utils.py
apps/activity/utils_orm.py                            # 1 violation
apps/activity/utils_conditions.py
```

**Activity Exception Strategy:**
```python
# In views
try:
    asset = Asset.objects.get(pk=asset_id)
    form = AssetForm(request.POST, instance=asset)
    if form.is_valid():
        form.save()
except Asset.DoesNotExist as e:
    return JsonResponse({'error': 'Asset not found'}, status=404)
except (ValidationError, ValueError) as e:
    return JsonResponse({'error': f'Validation failed: {e}'}, status=400)
except (PermissionDenied, SecurityException) as e:
    return JsonResponse({'error': 'Permission denied'}, status=403)
except (DatabaseError, OperationalError) as e:
    logger.error(f"Database error in asset update: {e}", exc_info=True)
    return JsonResponse({'error': 'Service unavailable'}, status=503)
```

---

### DAY 7: People, Onboarding & Reports

#### Morning Session (4 hours)

**TASK 3.3: Fix People App (Non-Critical Paths)**
**Expected:** 8-10 files, ~20 violations

**Phase 1 Already Fixed:** `apps/peoples/forms.py` ✅

**Remaining Files:**
```bash
apps/peoples/views.py                     # View handlers
apps/peoples/utils.py                     # Utility functions
apps/peoples/services.py                  # Service layer
apps/peoples/signals.py                   # Signal handlers
apps/peoples/managers.py                  # Custom managers
```

**People Exception Strategy:**
```python
try:
    user = People.objects.create_user(**user_data)
except IntegrityError as e:
    if 'unique constraint' in str(e).lower():
        raise UserManagementException("User already exists") from e
    raise DatabaseIntegrityException(str(e)) from e
except ValidationError as e:
    raise FormValidationException(f"Invalid user data: {e}") from e
except (DatabaseError, OperationalError) as e:
    raise UserManagementException("User creation service unavailable") from e
```

**TASK 3.4: Fix Onboarding App**
**Expected:** 10-12 files, ~30 violations

**Files:**
```bash
apps/onboarding/views.py                          # 3 violations
apps/onboarding/utils.py                          # 13 violations - CRITICAL
apps/onboarding/admin.py                          # 1 violation
apps/onboarding/forms.py
apps/onboarding/managers.py
apps/onboarding/bt_manager_orm.py

# API layer
apps/onboarding_api/views.py                      # 25 violations - CRITICAL
apps/onboarding_api/views_phase2.py              # 9 violations
apps/onboarding_api/middleware.py                 # 8 violations
```

**Onboarding Exception Strategy:**
```python
try:
    onboarding_step = process_conversational_step(user_input)
except ValidationError as e:
    raise OnboardingException(f"Invalid input: {e}") from e
except LLMServiceException as e:
    logger.error(f"AI service error: {e}")
    # Fallback to non-AI flow
    return fallback_response()
except (DatabaseError, OperationalError) as e:
    raise OnboardingException("Onboarding service unavailable") from e
```

#### Afternoon Session (4 hours)

**TASK 3.5: Fix Reports App**
**Expected:** 10-12 files, ~35 violations

**Files:**
```bash
apps/reports/views.py                             # 15 violations - CRITICAL
apps/reports/utils.py                             # 2 violations
apps/reports/services/secure_report_upload_service.py  # 4 violations
apps/reports/views_async_refactored.py           # 8 violations
apps/reports/forms.py
apps/reports/filters.py
```

**Reports Exception Strategy:**
```python
try:
    report_data = generate_report(report_config)
    pdf = create_pdf(report_data)
    save_report(pdf)
except (ValidationError, ValueError) as e:
    raise ReportValidationException(f"Invalid report config: {e}") from e
except (DatabaseError, OperationalError) as e:
    logger.error(f"Database error generating report: {e}", exc_info=True)
    raise ReportGenerationException("Report data unavailable") from e
except (OSError, IOError) as e:
    logger.error(f"File error generating report: {e}")
    raise FileOperationException("Report file generation failed") from e
except MemoryError as e:
    logger.critical(f"Memory exhausted generating report: {e}")
    raise SystemException("Report too large to generate") from e
```

---

### DAY 8: Work Orders, Helpdesk & Remaining Apps

#### Morning Session (4 hours)

**TASK 3.6: Fix Work Order Management**
**Expected:** 8-10 files, ~20 violations

```bash
apps/work_order_management/services.py
apps/work_order_management/views.py
apps/work_order_management/forms.py
apps/work_order_management/utils.py
apps/work_order_management/admin.py
```

**Work Order Exception Strategy:**
```python
try:
    work_order = WorkOrder.objects.create(**order_data)
    approval_result = request_approval(work_order)
except IntegrityError as e:
    raise WorkOrderException("Work order already exists") from e
except ValidationError as e:
    raise WorkOrderValidationException(f"Invalid work order: {e}") from e
except (DatabaseError, OperationalError) as e:
    raise WorkOrderException("Work order service unavailable") from e
```

**TASK 3.7: Fix Helpdesk/Ticketing**
**Expected:** 6-8 files, ~15 violations

```bash
apps/y_helpdesk/views.py                         # 1 violation
apps/y_helpdesk/managers.py                      # 2 violations
apps/y_helpdesk/utils.py
apps/y_helpdesk/forms.py
apps/y_helpdesk/admin.py
```

**Helpdesk Exception Strategy:**
```python
try:
    ticket = Ticket.objects.create(**ticket_data)
    escalation = auto_escalate_if_needed(ticket)
except ValidationError as e:
    raise HelpdeskException(f"Invalid ticket data: {e}") from e
except IntegrityError as e:
    raise HelpdeskException("Ticket already exists") from e
except (DatabaseError, OperationalError) as e:
    raise HelpdeskException("Ticketing service unavailable") from e
```

#### Afternoon Session (4 hours)

**TASK 3.8: Fix Remaining Business Apps**
```bash
# Smaller apps - can batch process
apps/reminder/                               # Admin, managers, models, views
apps/attendance/                             # Complex AI integration
apps/tenants/                                # Multi-tenancy
```

**TASK 3.9: Phase 3 Validation**
```bash
# Scan all business apps
python3 scripts/exception_scanner.py --path apps/schedhuler/ --strict
python3 scripts/exception_scanner.py --path apps/activity/ --strict
python3 scripts/exception_scanner.py --path apps/peoples/ --strict
python3 scripts/exception_scanner.py --path apps/onboarding/ --strict
python3 scripts/exception_scanner.py --path apps/reports/ --strict
python3 scripts/exception_scanner.py --path apps/work_order_management/ --strict
python3 scripts/exception_scanner.py --path apps/y_helpdesk/ --strict

# Run business logic tests
python3 -m pytest apps/schedhuler/tests/ -v
python3 -m pytest apps/activity/tests/ -v
python3 -m pytest apps/peoples/tests/ -v
python3 -m pytest apps/onboarding/tests/ -v
python3 -m pytest apps/reports/tests/ -v

# Create Phase 3 completion doc
# PHASE3_EXCEPTION_REMEDIATION_COMPLETE.md
```

**Phase 3 Expected Results:**
- 55-65 business logic files fixed
- Domain-specific exceptions implemented
- All business tests passing

---

## 🗓️ PHASE 4: INTEGRATION & UTILITY LAYERS (Days 9-10)

### DAY 9: External Integrations

#### Morning Session (4 hours)

**TASK 4.1: Fix MQTT Integration**
**Expected:** 4-5 files, ~10 violations

```bash
apps/mqtt/client.py
apps/mqtt/tests/test_client.py
```

**MQTT Exception Pattern:**
```python
try:
    mqtt_client.connect(broker_host, broker_port)
    mqtt_client.publish(topic, payload)
except (ConnectionError, TimeoutError) as e:
    correlation_id = ErrorHandler.handle_exception(e)
    raise MQTTConnectionException(f"MQTT connection failed (ID: {correlation_id})") from e
except (ValueError, TypeError) as e:
    raise MQTTValidationException(f"Invalid MQTT payload: {e}") from e
except OSError as e:
    raise MQTTException(f"MQTT system error: {e}") from e
```

**TASK 4.2: Fix API Layer**
**Expected:** 6-8 files, ~15 violations

```bash
apps/api/middleware.py
apps/api/mobile_consumers.py
apps/api/mobile_routing.py
apps/api/graphql/enhanced_schema.py
apps/api/graphql/dataloaders.py
```

#### Afternoon Session (4 hours)

**TASK 4.3: Fix Face Recognition (COMPLEX - Manual Review)**
**Expected:** 6-8 files, ~73 violations

**Critical AI/ML Files:**
```bash
apps/face_recognition/enhanced_engine.py              # 21 violations
apps/face_recognition/ai_enhanced_engine.py          # 14 violations
apps/face_recognition/integrations.py                 # 11 violations
apps/face_recognition/analytics.py                   # 11 violations
apps/face_recognition/signals.py                     # 10 violations
apps/face_recognition/services.py                    # 6 violations
```

**Face Recognition Exception Pattern:**
```python
try:
    face_encoding = face_engine.encode(image)
    match_result = face_engine.match(face_encoding, database)
except (IOError, OSError) as e:
    raise BiometricImageException(f"Image processing failed: {e}") from e
except (ValueError, TypeError) as e:
    raise BiometricValidationException(f"Invalid image format: {e}") from e
except TimeoutError as e:
    raise BiometricServiceException("Recognition timeout") from e
except ModuleNotFoundError as e:
    logger.critical(f"AI model not loaded: {e}")
    raise BiometricSystemException("AI model unavailable") from e
except MemoryError as e:
    logger.critical(f"Memory exhausted in face recognition: {e}")
    raise SystemException("Insufficient resources") from e
```

**TASK 4.4: Fix Journal & Wellness System**
**Expected:** 10-12 files, ~60 violations

```bash
apps/journal/views.py                                 # 9 violations
apps/journal/search.py                                # 14 violations
apps/journal/mqtt_integration.py                     # 14 violations
apps/journal/permissions.py                          # 6 violations
apps/journal/graphql_schema.py                       # 6 violations
apps/journal/signals.py                              # 6 violations
apps/journal/middleware.py                           # 2 violations
apps/journal/services/pattern_analyzer.py            # 1 violation
```

---

### DAY 10: Background Tasks & Utilities

#### Morning Session (4 hours)

**TASK 4.5: Fix Background Tasks (CRITICAL)**
**Expected:** 8-10 files, ~120 violations

**High Priority:**
```bash
background_tasks/tasks.py                            # 32 violations - CRITICAL
background_tasks/onboarding_tasks_phase2.py         # 31 violations
background_tasks/journal_wellness_tasks.py          # 20 violations
background_tasks/personalization_tasks.py           # 14 violations
background_tasks/onboarding_tasks.py                # 9 violations
background_tasks/ai_testing_tasks.py                # 8 violations
background_tasks/utils.py                            # 7 violations
background_tasks/report_tasks.py                    # 4 violations
```

**Background Task Pattern:**
```python
from celery import shared_task
from celery.exceptions import Retry

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def background_process(self, data):
    try:
        # Task logic
        result = process_data(data)
        return {'status': 'success', 'result': result}

    except (ValidationError, ValueError, TypeError) as e:
        # Don't retry - bad data won't improve
        logger.error(f"Task validation error: {e}", extra={'task_id': self.request.id})
        return {'status': 'failed', 'error': f'Invalid data: {str(e)}'}

    except (DatabaseError, OperationalError) as e:
        # Retry with exponential backoff
        logger.error(f"Task database error: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except (IntegrationException, ConnectionError, TimeoutError) as e:
        # Retry with longer backoff
        logger.error(f"Task integration error: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))

    except MemoryError as e:
        # Don't retry - system resource issue
        logger.critical(f"Task memory error: {e}")
        return {'status': 'failed', 'error': 'System resources exhausted'}
```

#### Afternoon Session (4 hours)

**TASK 4.6: Fix Remaining Integration Apps**
```bash
# Stream Testbench
apps/streamlab/views.py                              # 4 violations
apps/streamlab/services/event_capture.py            # 6 violations
apps/streamlab/services/pii_redactor.py             # 1 violation
apps/streamlab/services/visual_diff_processor.py    # 2 violations
apps/streamlab/consumers.py                          # 3 violations

# Issue Tracker
apps/issue_tracker/

# Mentor API
apps/mentor_api/views.py                            # 9 violations
```

**TASK 4.7: Fix Utility Scripts**
```bash
scripts/utilities/*.py                               # ~30 violations across utilities
scripts/migration/*.py
scripts/*.py (root level)
```

**TASK 4.8: Phase 4 Validation**
```bash
# Validate integration apps
python3 scripts/exception_scanner.py --path apps/mqtt/ --strict
python3 scripts/exception_scanner.py --path apps/face_recognition/ --strict
python3 scripts/exception_scanner.py --path apps/api/ --strict
python3 scripts/exception_scanner.py --path background_tasks/ --strict

# Run integration tests
python3 -m pytest tests/integration/ -v --tb=short

# Test MQTT specifically
python3 -m pytest apps/mqtt/tests/ -v

# Test background tasks
python3 -m pytest background_tasks/tests/ -v

# Create Phase 4 completion doc
# PHASE4_EXCEPTION_REMEDIATION_COMPLETE.md
```

---

## 🗓️ PHASE 5: VALIDATION & DEPLOYMENT (Days 11-12)

### DAY 11: Comprehensive Testing

#### Morning Session (4 hours)

**TASK 5.1: Final Codebase Scan**
```bash
# Complete codebase scan
python3 scripts/exception_scanner.py --path apps/ --strict --format json > final_scan_report.json

# Analyze results
python3 scripts/exception_scanner.py --path apps/ --priority-list

# Target: <50 violations remaining (<2%)

# Document any remaining violations
# Create REMAINING_VIOLATIONS_DOCUMENTED.md
```

**TASK 5.2: Execute Comprehensive Test Suite**
```bash
# Full test suite with coverage
python3 -m pytest \
    --cov=apps \
    --cov-report=html:coverage_reports/html \
    --cov-report=term \
    --tb=short \
    -v

# Target: >80% coverage, all tests passing

# Security-specific tests
python3 -m pytest -m security --tb=short -v

# Exception handling tests
python3 -m pytest apps/core/tests/test_*exception* -v
python3 -m pytest apps/core/tests/test_phase1_exception_remediation.py -v

# Integration tests
python3 -m pytest tests/integration/ -v

# Unit tests by app
python3 -m pytest apps/peoples/tests/ -v
python3 -m pytest apps/activity/tests/ -v
python3 -m pytest apps/schedhuler/tests/ -v
python3 -m pytest apps/onboarding/tests/ -v
python3 -m pytest apps/reports/tests/ -v
```

#### Afternoon Session (4 hours)

**TASK 5.3: Performance & Security Validation**

**Performance Testing:**
```bash
# Stream Testbench performance
python3 testing/stream_load_testing/spike_test.py

# Database performance
python3 testing/load_testing/database_performance_test.py

# Health check load test
python3 testing/load_testing/health_check_load_test.py

# API load testing
python3 tests/api/performance/test_load_testing.py

# Acceptance: <5% regression
```

**Security Testing:**
```bash
# SQL injection penetration
python3 apps/core/tests/test_sql_injection_penetration.py

# Comprehensive security integration
python3 apps/core/tests/test_security_integration_comprehensive.py

# GraphQL security
python3 apps/core/tests/test_graphql_security_integration.py

# Race condition tests
python3 race_condition_penetration_test.py

# Acceptance: All security tests pass
```

---

### DAY 12: Documentation & Deployment

#### Morning Session (4 hours)

**TASK 5.4: Complete Final Documentation**

**Create/Update:**
1. **`PHASES_2_5_COMPLETE.md`**
   - Summary of Phases 2-5
   - Final metrics and statistics
   - Lessons learned

2. **`EXCEPTION_HANDLING_MIGRATION_GUIDE.md`**
   - Team onboarding guide
   - Pattern examples by use case
   - Common pitfalls and solutions

3. **Update `docs/EXCEPTION_HANDLING_PATTERNS.md`**
   - Add all new patterns discovered
   - Integration-specific examples
   - Background task retry patterns

4. **Update `.claude/rules.md`**
   - Mark Rule #11 as ENFORCED ✅
   - Add validation commands
   - Update compliance checklist

**TASK 5.5: Create Exception Monitoring Dashboard**

**Document for Ops Team:**
```python
# apps/core/monitoring/exception_monitor.py

EXCEPTION_MONITORING_CONFIG = {
    'enabled': True,
    'correlation_id_tracking': True,
    'real_time_alerts': {
        'SecurityException': {
            'severity': 'immediate',
            'notification': ['security-team@company.com'],
            'threshold': 1  # Alert on any occurrence
        },
        'DatabaseException': {
            'severity': 'high',
            'notification': ['ops-team@company.com'],
            'threshold': 10  # Alert if >10/hour
        },
        'ValidationException': {
            'severity': 'medium',
            'threshold': 50  # Alert if >50/hour
        }
    },
    'pattern_analysis': {
        'enabled': True,
        'ml_anomaly_detection': True,
        'correlation_id_clustering': True
    },
    'metrics': {
        'exception_frequency_by_type': True,
        'exception_resolution_time': True,
        'exception_impact_analysis': True
    }
}
```

#### Afternoon Session (4 hours)

**TASK 5.6: CI/CD Pipeline Integration**

**Update `.github/workflows/code-quality.yml`:**
```yaml
name: Code Quality - Exception Handling Validation

on: [push, pull_request]

jobs:
  exception-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt

      - name: Validate Exception Handling
        run: |
          python3 scripts/exception_scanner.py --path apps/ --strict

      - name: Check for violations
        run: |
          VIOLATIONS=$(python3 scripts/exception_scanner.py --path apps/ --format json | jq '.summary.total_occurrences')
          if [ "$VIOLATIONS" -gt 50 ]; then
            echo "❌ Too many generic exception patterns: $VIOLATIONS"
            echo "Target: <50 violations (<2%)"
            exit 1
          fi
          echo "✅ Exception handling validation passed: $VIOLATIONS violations"

      - name: Run exception handling tests
        run: |
          python3 -m pytest apps/core/tests/test_*exception* -v
```

**TASK 5.7: Pre-commit Hook Validation**
```bash
# Verify pre-commit hook is working
cat .githooks/pre-commit

# Test the hook
echo "except Exception: pass" > /tmp/test_violation.py
git add /tmp/test_violation.py
git commit -m "test: should fail"
# Should fail and prevent commit

# Clean up
rm /tmp/test_violation.py
git reset HEAD /tmp/test_violation.py
```

**TASK 5.8: Deployment Preparation**

**Create Deployment Checklist:**
- [ ] All Phases 1-4 complete
- [ ] <50 violations remaining (<2%)
- [ ] All tests passing (>80% coverage)
- [ ] Performance within SLA (<5% regression)
- [ ] Security tests passing (100%)
- [ ] Documentation complete
- [ ] CI/CD pipeline enforcing
- [ ] Rollback plan documented
- [ ] Monitoring dashboard configured

**Create Rollback Procedure:**
```bash
# Tag current state
git tag -a exception-remediation-v1.0 -m "Complete exception handling remediation"
git push origin exception-remediation-v1.0

# Feature flag for staged rollout
ENHANCED_EXCEPTION_HANDLING_ENABLED=True
ENHANCED_EXCEPTION_HANDLING_ROLLOUT_PERCENTAGE=10  # Start at 10%

# Rollback command (if needed)
git revert exception-remediation-v1.0
# OR
ENHANCED_EXCEPTION_HANDLING_ENABLED=False
```

**TASK 5.9: Create Final Summary Report**

**File:** `PHASES_2_5_COMPLETE.md`

Contents:
- Complete before/after metrics
- All files fixed (list)
- Test results summary
- Performance impact analysis
- Security improvement quantification
- Team migration guide
- Deployment notes

---

## 📋 FILE-BY-FILE CHECKLIST

### Top 50 High-Priority Files (Order of Execution)

#### Phase 2 - Core Infrastructure
- [x] apps/core/decorators.py (2 violations) - ✅ FIXED
- [x] apps/core/validation.py (2 violations) - ✅ FIXED
- [ ] apps/core/services/transaction_manager.py (6 violations)
- [ ] apps/core/services/query_service.py (8 violations)
- [ ] apps/core/services/base_service.py (6 violations)
- [ ] apps/core/services/validation_service.py (3 violations)
- [ ] apps/core/services/task_webhook_service.py (4 violations)
- [ ] apps/core/services/encryption_key_manager.py (7 violations)
- [ ] apps/core/middleware/graphql_csrf_protection.py
- [ ] apps/core/middleware/graphql_rate_limiting.py

#### Phase 2 - GraphQL (CRITICAL)
- [ ] apps/service/utils.py (20 violations) - **HIGHEST PRIORITY**
- [ ] apps/core/queries/__init__.py
- [ ] apps/core/graphql_security.py

#### Phase 3 - Business Logic
- [ ] apps/schedhuler/utils.py (14 violations)
- [ ] apps/reports/views.py (15 violations)
- [ ] apps/onboarding/utils.py (13 violations)
- [ ] apps/activity/services/question_service.py (9 violations)
- [ ] apps/onboarding_api/views.py (25 violations)

#### Phase 4 - Integrations
- [ ] background_tasks/tasks.py (32 violations)
- [ ] background_tasks/onboarding_tasks_phase2.py (31 violations)
- [ ] background_tasks/journal_wellness_tasks.py (20 violations)
- [ ] apps/face_recognition/enhanced_engine.py (21 violations)
- [ ] apps/face_recognition/ai_enhanced_engine.py (14 violations)
- [ ] apps/journal/search.py (14 violations)
- [ ] apps/journal/mqtt_integration.py (14 violations)

---

## 🎯 SUCCESS METRICS & VALIDATION

### Quantitative Targets

| Metric | Target | Current | Phase 5 Target |
|--------|--------|---------|----------------|
| Violations Remaining | <50 | 2,445 | <50 (98% reduction) |
| Files Fixed | >90% | 9 (~2%) | >450 (90%+) |
| Test Coverage | >80% | N/A | >80% |
| Correlation ID Coverage | 100% | 100% (fixed files) | 100% |
| Performance Regression | <5% | N/A | <5% |
| Security Tests Pass | 100% | N/A | 100% |

### Qualitative Targets
- [ ] All exceptions are specific and actionable
- [ ] Error messages aid debugging without exposing internals
- [ ] Exception hierarchy matches business domains
- [ ] No silent failures in any code path
- [ ] CI/CD pipeline enforces Rule #11
- [ ] Team migration guide complete

---

## 🚀 EXECUTION COMMANDS REFERENCE

### Daily Workflow

**Start of Day:**
```bash
# Pull latest changes
git pull origin main

# Create daily branch
git checkout -b fix/exception-remediation-day-N

# Scan target files
python3 scripts/exception_scanner.py --path [target_path] --priority-list
```

**During Day:**
```bash
# Fix file
# Edit file following patterns from Phase 1

# Validate syntax
python3 -m py_compile [fixed_file].py

# Check for remaining violations
grep -c "except Exception" [fixed_file].py
# Should return 0

# Run relevant tests
python3 -m pytest [related_tests] -v
```

**End of Day:**
```bash
# Final validation
python3 scripts/exception_scanner.py --path [day_target_path] --strict

# Run test suite
python3 -m pytest [affected_apps] -v

# Commit progress
git add .
git commit -m "fix: eliminate generic exceptions in [module] (Day N)"

# Push and create PR
git push origin fix/exception-remediation-day-N
gh pr create --title "Exception Remediation Day N: [Module]" --body "..."
```

---

## 📊 ESTIMATED EFFORT BREAKDOWN

### By File Volume
- **Phase 1:** 6 files × 2 hours/file = 12 hours ✅ DONE
- **Phase 2:** 90 files × 0.5 hours/file = 45 hours (3 days)
- **Phase 3:** 200 files × 0.4 hours/file = 80 hours (3 days)
- **Phase 4:** 150 files × 0.3 hours/file = 45 hours (2 days)
- **Phase 5:** Testing & validation = 16 hours (2 days)
- **TOTAL:** ~200 hours (12 working days at 8 hrs/day)

### By Violation Count
- **CRITICAL (0-20 violations/file):** 5 hours/file (manual review)
- **HIGH (10-15 violations/file):** 2 hours/file
- **MEDIUM (5-10 violations/file):** 1 hour/file
- **LOW (1-5 violations/file):** 0.5 hours/file

---

## 🔄 CONTINUOUS VALIDATION CHECKLIST

### After Each File Fix
- [ ] Syntax validation: `python3 -m py_compile [file].py`
- [ ] Violation check: `grep -c "except Exception" [file].py` returns 0
- [ ] Relevant tests pass
- [ ] No new imports breaking dependencies

### After Each Day
- [ ] Scanner shows progress: `python3 scripts/exception_scanner.py --path [day_module]`
- [ ] Test suite passes: `python3 -m pytest [day_module]/tests/ -v`
- [ ] Git commit with descriptive message
- [ ] Update progress tracking document

### After Each Phase
- [ ] Complete scanner validation (0 violations in phase scope)
- [ ] All tests passing (>80% coverage)
- [ ] Performance benchmarks (no regressions)
- [ ] Security tests passing
- [ ] Phase completion document created
- [ ] Git tag created: `git tag phase-N-complete`

---

## 🎯 FINAL DELIVERABLES

### Code Deliverables
- [ ] ~450 files with specific exception handling
- [ ] 0 generic `except Exception:` patterns (or <50)
- [ ] 100% correlation ID coverage
- [ ] Comprehensive test suite (>100 tests)

### Documentation Deliverables
- [x] PHASE1_EXCEPTION_REMEDIATION_COMPLETE.md ✅
- [ ] PHASE2_EXCEPTION_REMEDIATION_COMPLETE.md
- [ ] PHASE3_EXCEPTION_REMEDIATION_COMPLETE.md
- [ ] PHASE4_EXCEPTION_REMEDIATION_COMPLETE.md
- [ ] PHASES_2_5_COMPLETE.md
- [ ] EXCEPTION_HANDLING_MIGRATION_GUIDE.md
- [ ] Updated docs/EXCEPTION_HANDLING_PATTERNS.md

### Infrastructure Deliverables
- [ ] CI/CD pipeline enforcing Rule #11
- [ ] Pre-commit hooks validated
- [ ] Exception monitoring dashboard configured
- [ ] Deployment plan approved
- [ ] Rollback procedure documented

---

## ✅ READY FOR EXECUTION

**This plan provides:**
- ✅ Day-by-day task breakdown
- ✅ File-by-file prioritization
- ✅ Specific fix patterns for each scenario
- ✅ Validation commands at each step
- ✅ Clear success metrics
- ✅ Risk mitigation strategies

**Total estimated effort:** 9-10 additional working days to complete Phases 2-5

**Current status:** Phase 1 complete, Phase 2 started (3%), ready to proceed with systematic execution

**Next action:** Begin Day 3 tasks (Phase 2 core utilities and caching layer)

---

**Document Version:** 1.0
**Last Updated:** 2025-09-27
**Compliance:** `.claude/rules.md` Rule #11