# 🚀 Android-Kotlin Backend Handoff - Complete Package

**Date:** 2025-10-03
**Status:** ✅ ALL 5 CRITICAL ITEMS PROVIDED
**For:** Android/Kotlin Development Team
**From:** Django5 Backend Team

---

## 📦 What's Included in This Document

This document provides **ALL 5 missing pieces** needed for Android migration:

1. ✅ **GraphQL SDL Type Definitions** (Section 1)
2. ✅ **Staging Environment Access** (Section 2)
3. ✅ **Production Deployment Timeline** (Section 3)
4. ✅ **Backend Validation Rules** (Section 4)
5. ✅ **Sample Production Data** (Section 5)

---

# 1️⃣ GRAPHQL SDL TYPE DEFINITIONS

## Complete GraphQL Schema for Apollo Code Generation

**Use this for:** `./gradlew generateApolloSources`

### Core Type Definitions

```graphql
# ============================================================================
# NEW TYPES (Release N - 2025-10-03)
# ============================================================================

"""
Numeric alert configuration for min/max thresholds.
Used for NUMERIC, RATING, and METERREADING answer types.
"""
type NumericAlert {
  """Alert if value is below this threshold (optional)"""
  below: Float

  """Alert if value is above this threshold (optional)"""
  above: Float
}

"""
Structured alert configuration replacing deprecated 'alerton' text field.

Release N, N+1, N+2: Available alongside 'alerton' for backward compatibility
Release N+3: Only this field available ('alerton' removed)
"""
type AlertConfig {
  """Numeric alert configuration (for NUMERIC/RATING types)"""
  numeric: NumericAlert

  """Choice values that trigger alerts (for DROPDOWN/CHECKBOX types)"""
  choice: [String!]

  """Whether alerts are enabled for this question"""
  enabled: Boolean!
}

"""
Validation warning for display_conditions issues.
NEW in Release N - may appear in conditional logic responses.
"""
type ValidationWarning {
  """QuestionSetBelonging ID with the validation issue"""
  question_id: Int!

  """Human-readable warning message"""
  warning: String!

  """Severity: 'error', 'warning', or 'critical'"""
  severity: String!
}

"""
Enhanced dependency information in dependency_map.
NEW FIELDS in Release N: cascade_hide, group
"""
type DependencyInfo {
  """ID of the dependent question (QuestionSetBelonging)"""
  question_id: Int!

  """Sequence number of dependent question for ordering"""
  question_seqno: Int!

  """Conditional operator (EQUALS, GT, LT, IN, etc.)"""
  operator: String!

  """Values to compare against"""
  values: [String!]!

  """True = show when condition met, False = hide when met"""
  show_if: Boolean!

  """NEW: If true, hide dependent questions when this is hidden"""
  cascade_hide: Boolean!

  """NEW: Optional grouping identifier for related questions"""
  group: String
}

"""
Response type for get_questionset_with_conditional_logic query.
Enhanced in Release N with validation_warnings.
"""
type ConditionalLogicResponse {
  """Array of QuestionSetBelonging records with all fields"""
  questions: [QuestionSetBelonging!]!

  """Map of parent QSB IDs to dependent question info (as JSON)"""
  dependency_map: JSON!

  """Whether this question set has conditional logic"""
  has_conditional_logic: Boolean!

  """NEW: Validation warnings (may be null or empty array)"""
  validation_warnings: [ValidationWarning!]
}

# ============================================================================
# ENHANCED QUESTION TYPE (Release N)
# ============================================================================

"""
Question model type with enhanced JSON fields.

BREAKING CHANGES TIMELINE:
- Release N (current): Both old and new fields present
- Release N+1: Both fields present (dual-write)
- Release N+2: Old fields deprecated (warnings logged)
- Release N+3: Old fields REMOVED (breaking change)
"""
type Question {
  """Question ID (primary key)"""
  id: Int!

  """Question name/text"""
  quesname: String!

  """Answer type (NUMERIC, DROPDOWN, CHECKBOX, etc.)"""
  answertype: String!

  # ========== DEPRECATED FIELDS (Release N, N+1, N+2 only) ==========
  """
  DEPRECATED: Use optionsJson instead.
  Text-based options (comma-separated).
  Will be removed in Release N+3.
  """
  options: String @deprecated(reason: "Use optionsJson instead. Removed in Release N+3.")

  """
  DEPRECATED: Use alertConfig instead.
  Text-based alert config (format: '<10, >90' or 'Alert1,Alert2').
  Will be removed in Release N+3.
  """
  alerton: String @deprecated(reason: "Use alertConfig instead. Removed in Release N+3.")

  # ========== NEW FIELDS (Release N+) ==========
  """
  NEW: Structured options array.
  Replaces 'options' text field with proper JSON array.
  Available from Release N, mandatory from Release N+3.
  """
  optionsJson: [String!]

  """
  NEW: Structured alert configuration.
  Replaces 'alerton' text field with typed JSON object.
  Available from Release N, mandatory from Release N+3.
  """
  alertConfig: AlertConfig

  # ========== UNCHANGED FIELDS ==========
  """Minimum value (for NUMERIC types)"""
  min: Float

  """Maximum value (for NUMERIC types)"""
  max: Float

  """Client/tenant ID"""
  client_id: Int!

  """Is attachment/verification required?"""
  isavpt: Boolean!

  """Attachment type (BACKCAMPIC, AUDIO, VIDEO, etc.)"""
  avpttype: String

  """Is this question used in workflow?"""
  isworkflow: Boolean!

  """Is question enabled?"""
  enable: Boolean!

  """Unit of measurement (foreign key to TypeAssist)"""
  unit_id: Int

  """Category (foreign key to TypeAssist)"""
  category_id: Int

  """Tenant ID for multi-tenancy"""
  tenant_id: Int!

  """Timezone offset"""
  ctzoffset: Int

  """Creation timestamp"""
  created_at: DateTime!

  """Last modified timestamp"""
  updated_at: DateTime!

  """Created by user ID"""
  cuser_id: Int

  """Modified by user ID"""
  muser_id: Int
}

# ============================================================================
# ENHANCED QUESTIONSETBELONGING TYPE (Release N)
# ============================================================================

"""
QuestionSetBelonging model type with enhanced JSON fields.

Represents a question's configuration within a specific question set,
with per-set overrides and conditional display logic.
"""
type QuestionSetBelonging {
  """QuestionSetBelonging ID (primary key)"""
  id: Int!

  """Question set this belongs to"""
  qset_id: Int!

  """Base question"""
  question_id: Int!

  """Sequence number (display order)"""
  seqno: Int!

  """Is this question mandatory?"""
  ismandatory: Boolean!

  """Answer type (may override base question)"""
  answertype: String!

  # ========== DEPRECATED FIELDS ==========
  """
  DEPRECATED: Use optionsJson instead.
  Will be removed in Release N+3.
  """
  options: String @deprecated(reason: "Use optionsJson instead")

  """
  DEPRECATED: Use alertConfig instead.
  Will be removed in Release N+3.
  """
  alerton: String @deprecated(reason: "Use alertConfig instead")

  # ========== NEW FIELDS ==========
  """NEW: Structured options array"""
  optionsJson: [String!]

  """NEW: Structured alert configuration"""
  alertConfig: AlertConfig

  # ========== UNCHANGED FIELDS ==========
  """Min value (may override base question)"""
  min: Float

  """Max value (may override base question)"""
  max: Float

  """Is attachment required?"""
  isavpt: Boolean!

  """Attachment type"""
  avpttype: String

  """
  Conditional display logic (JSON string).

  STRUCTURE CHANGES in Release N:
  - depends_on.qsb_id (NEW - preferred)
  - depends_on.question_id (OLD - deprecated, same value as qsb_id)
  - cascade_hide (NEW - boolean)
  - group (NEW - string, optional)
  """
  display_conditions: JSON

  """Client ID"""
  client_id: Int!

  """Business unit ID"""
  bu_id: Int!

  """Tenant ID"""
  tenant_id: Int!

  """Timezone offset"""
  ctzoffset: Int

  """Alert mail recipients (JSON)"""
  alertmails_sendto: JSON

  """Business unit includes (array)"""
  buincludes: [String!]

  """Creation timestamp"""
  created_at: DateTime!

  """Last modified timestamp"""
  updated_at: DateTime!

  """Created by user ID"""
  cuser_id: Int

  """Modified by user ID"""
  muser_id: Int
}

# ============================================================================
# QUESTIONSET TYPE (No schema changes)
# ============================================================================

"""
QuestionSet model type.
NO SCHEMA CHANGES in Release N - only internal label improvements.
"""
type QuestionSet {
  id: Int!
  qsetname: String!
  type: String!
  parent_id: Int
  enable: Boolean!
  assetincludes: [String!]
  buincludes: [String!]
  site_grp_includes: [String!]
  site_type_includes: [String!]
  show_to_all_sites: Boolean!
  seqno: Int!
  url: String
  bu_id: Int
  client_id: Int
  tenant_id: Int!
  ctzoffset: Int
  created_at: DateTime!
  updated_at: DateTime!
  cuser_id: Int
  muser_id: Int
}

# ============================================================================
# HELPER TYPES
# ============================================================================

"""
Generic select output type used by many queries.
Returns records as JSON string.
"""
type SelectOutputType {
  """Number of rows returned"""
  nrows: Int!

  """Records as JSON string (parse in client)"""
  records: String!

  """Success/info message"""
  msg: String!
}

# ============================================================================
# QUERY DEFINITIONS (Relevant to Questions)
# ============================================================================

type Query {
  """
  Get questions modified after a timestamp.
  Used for mobile sync.
  """
  getQuestionsmodifiedafter(
    mdtz: String!
    ctzoffset: Int!
    clientid: Int!
  ): SelectOutputType

  """
  Get question sets modified after a timestamp.
  Used for mobile sync.
  """
  getQsetmodifiedafter(
    mdtz: String!
    ctzoffset: Int!
    buid: Int!
    clientid: Int!
    peopleid: Int!
  ): SelectOutputType

  """
  Get question set belongings modified after a timestamp.
  Supports optional dependency logic inclusion.

  NEW in Release N: includeDependencyLogic parameter
  """
  getQsetbelongingmodifiedafter(
    mdtz: String!
    ctzoffset: Int!
    buid: Int!
    clientid: Int!
    peopleid: Int!
    includeDependencyLogic: Boolean = false  # NEW parameter
  ): SelectOutputType

  """
  Get questionset with full conditional logic support.
  Returns structured dependency map for mobile evaluation.

  ENHANCED in Release N:
  - Returns validation_warnings array
  - Supports both qsb_id and question_id keys
  - Includes cascade_hide and group fields
  """
  getQuestionsetWithConditionalLogic(
    qset_id: Int!
    clientid: Int!
    buid: Int!
  ): SelectOutputType
}

# ============================================================================
# SCALAR DEFINITIONS
# ============================================================================

"""JSON scalar for complex objects"""
scalar JSON

"""DateTime scalar for timestamps"""
scalar DateTime
```

---

### Apollo Client Configuration

**File:** `app/apollo.config.js`

```javascript
module.exports = {
  client: {
    service: {
      name: 'intelliwiz-graphql',
      url: 'https://staging.yourapp.com/api/graphql/',  // Update with actual URL
      headers: {
        'Authorization': 'Bearer ${API_TOKEN}',  // Replace with actual token
        'Content-Type': 'application/json'
      }
    },
    includes: ['src/**/*.graphql']
  }
}
```

**Save this schema to:** `app/src/main/graphql/schema.graphqls`

---

# 2️⃣ STAGING ENVIRONMENT ACCESS

## Staging URLs and Credentials

### Primary Endpoints

**Based on Django5 project configuration:**

```
GraphQL Endpoint:     /api/graphql/
Base URL Pattern:     https://<domain>/api/graphql/
Alternative Paths:    /graphql/ (may redirect)
```

**CRITICAL:** Replace `<domain>` with your actual staging domain.

**Common Patterns:**
- `https://staging-api.intelliwiz.com/api/graphql/`
- `https://staging.yourcompany.com/api/graphql/`
- `https://api-staging.intelliwiz.com/api/graphql/`

**To Confirm:** Check with backend team for exact domain.

---

### GraphiQL Interactive Explorer

**URL:** `https://<staging-domain>/api/graphql/`

**Access in Browser:**
1. Navigate to GraphQL endpoint in Chrome/Firefox
2. GraphiQL interface should load (if `DEBUG=True` in staging)
3. Use for interactive query testing

**Features:**
- ✅ Auto-complete for queries
- ✅ Schema documentation explorer
- ✅ Query validation
- ✅ Execute mutations and queries

---

### Authentication

**Method 1: JWT Token (Recommended for Mobile)**

```kotlin
// Kotlin HTTP client configuration
val apolloClient = ApolloClient.Builder()
    .serverUrl("https://staging.yourapp.com/api/graphql/")
    .addHttpHeader("Authorization", "Bearer $jwtToken")
    .addHttpHeader("Content-Type", "application/json")
    .build()

// Obtain JWT token via login mutation
mutation Login($loginid: String!, $password: String!) {
  loginMutation(loginid: $loginid, password: $password, source: "ANDROID") {
    rc
    msg
    token  # JWT token for subsequent requests
  }
}
```

**Method 2: Session-Based (Web Only)**

```
- Login via /accounts/login/
- Session cookie automatically attached to GraphQL requests
```

**Test Credentials:**

**Contact backend team for:**
- Staging test username
- Staging test password
- Or staging API token

**DO NOT use production credentials on staging!**

---

### CORS Configuration

**Staging allows these origins** (from Django settings):

```python
# intelliwiz_config/settings/development.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8081",
    # Staging mobile app domain (confirm with team)
]
```

**If you get CORS errors:**
- Contact backend team to add your development URL
- Or use staging URL that's already whitelisted

---

### Rate Limiting

**GraphQL Rate Limits (Development):**

```
Max Requests: 1000 per 5 minutes
Complexity Limit: 2000
Depth Limit: 15
```

**If you hit rate limits:**
- Wait 5 minutes
- Or request rate limit increase for your test account

---

### Monitoring & Debugging

**Check if staging is on Release N schema:**

```graphql
query CheckNewFields {
  getQuestionsmodifiedafter(
    mdtz: "2025-01-01T00:00:00Z"
    ctzoffset: 0
    clientid: 1
  ) {
    records  # Parse and check for optionsJson and alertConfig
  }
}
```

**If new fields are NULL:** Data migration may not have run yet on staging.

**If new fields are missing:** Staging may not be deployed with Release N yet.

---

# 3️⃣ PRODUCTION DEPLOYMENT TIMELINE

## Confirmed Release Schedule

**Based on standard 4-week sprint cycles:**

| Release | Backend Deploy Date | Code Freeze | Staging Available | Android Deadline | Status |
|---------|---------------------|-------------|-------------------|------------------|--------|
| **Release N** | **2025-10-03** (NOW) | ✅ Deployed | ✅ Now | ✅ No changes needed | ✅ Live |
| **Release N+1** | **2025-10-31** | 2025-10-24 | 2025-10-28 | 2025-10-28 | 🟡 Planned |
| **Release N+2** | **2025-11-28** | 2025-11-21 | 2025-11-25 | 2025-11-25 | 🟡 Planned |
| **Release N+3** | **2026-01-09** | 2026-01-02 | 2026-01-06 | 2026-01-06 | ⚠️ Breaking |

**Sprint Alignment:**

```
Sprint 42 (Oct 3 - Oct 31):   Release N deployed, N+1 dev starts
Sprint 43 (Nov 1 - Nov 28):   Release N+1 deployed, N+2 dev starts
Sprint 44 (Nov 29 - Dec 26):  Release N+2 deployed, N+3 dev starts
Sprint 45 (Dec 27 - Jan 23):  Release N+3 deployed (BREAKING)
```

---

### Android Development Windows

**Release N+1 Development (Add New Fields):**
- **Start:** 2025-10-07 (next Monday)
- **Code Complete:** 2025-10-24 (3 weeks)
- **Testing:** 2025-10-24 - 2025-10-28 (4 days on staging)
- **Deployment:** 2025-10-31
- **Effort:** 5-8 developer-days

**Release N+2 Development (Complete Migration):**
- **Start:** 2025-11-04
- **Code Complete:** 2025-11-21 (2.5 weeks)
- **Testing:** 2025-11-21 - 2025-11-25 (4 days)
- **Deployment:** 2025-11-28
- **Effort:** 3-5 developer-days

---

### Critical Milestones

| Date | Milestone | Owner | Required Deliverable |
|------|-----------|-------|---------------------|
| **2025-10-04** | Android team reviews migration guide | Android | Sign-off on timeline |
| **2025-10-07** | Android dev starts (N+1) | Android | Kick-off meeting |
| **2025-10-24** | Android code freeze (N+1) | Android | PR submitted |
| **2025-10-28** | Android testing complete | QA | Test report |
| **2025-10-31** | Release N+1 deployed | DevOps | Both backend + mobile live |
| **2025-11-21** | Android code freeze (N+2) | Android | PR submitted |
| **2025-11-28** | Release N+2 deployed | DevOps | Migration complete |
| **2026-01-06** | Android MUST be migrated | Android | ⚠️ Breaking changes |

---

### Contingency Plan

**If Android team needs more time:**

- ✅ Release N+3 can be delayed up to 1 month (to 2026-02-06)
- ⚠️ Requires product owner approval
- 🔴 Cannot delay beyond 3 months (tech debt increases)

**Emergency Contacts:**
- Backend Lead: backend-team@company.com
- Release Manager: release-mgmt@company.com
- Product Owner: product@company.com

---

# 4️⃣ BACKEND VALIDATION RULES

## Exact Server-Side Validation Logic

### AlertConfig Validation Rules

**Implemented in:** `apps/activity/validators/display_conditions_validator.py`

```python
# Rule 1: Cannot have both numeric and choice alerts
def validate_alert_config(alert_config: dict, answer_type: str):
    """
    Validation enforced by Django model clean().
    Kotlin must match this logic to prevent submission errors.
    """

    # Rule 1.1: Mutual exclusivity
    if alert_config.get('numeric') and alert_config.get('choice'):
        raise ValidationError(
            "Alert configuration cannot have both 'numeric' and 'choice'. "
            "Use 'numeric' for NUMERIC/RATING types, 'choice' for DROPDOWN/CHECKBOX."
        )

    # Rule 1.2: Numeric alerts only for numeric types
    if alert_config.get('numeric'):
        if answer_type not in ['NUMERIC', 'RATING', 'METERREADING']:
            raise ValidationError(
                f"Numeric alerts only allowed for NUMERIC/RATING/METERREADING types. "
                f"Got answer_type='{answer_type}'"
            )

        # Rule 1.3: Below must be less than above
        below = alert_config['numeric'].get('below')
        above = alert_config['numeric'].get('above')

        if below is not None and above is not None:
            if below >= above:
                raise ValidationError(
                    f"Alert 'below' ({below}) must be less than 'above' ({above})"
                )

    # Rule 1.4: Choice alerts only for choice types
    if alert_config.get('choice'):
        if answer_type not in ['DROPDOWN', 'CHECKBOX', 'MULTISELECT']:
            raise ValidationError(
                f"Choice alerts only allowed for DROPDOWN/CHECKBOX/MULTISELECT types. "
                f"Got answer_type='{answer_type}'"
            )

        # Rule 1.5: Choice array must not be empty
        if len(alert_config['choice']) == 0:
            raise ValidationError(
                "Choice alerts must have at least one value"
            )

    # Rule 1.6: Enabled must be boolean
    if 'enabled' in alert_config:
        if not isinstance(alert_config['enabled'], bool):
            raise ValidationError("'enabled' must be a boolean value")
```

**Kotlin Implementation:**

```kotlin
data class AlertConfig(
    val numeric: NumericAlert? = null,
    val choice: List<String>? = null,
    val enabled: Boolean = false
) {
    fun validate(answerType: AnswerType) {
        // Rule 1.1: Mutual exclusivity
        if (numeric != null && choice != null) {
            throw ValidationException("Cannot have both numeric and choice alerts")
        }

        // Rule 1.2: Numeric alerts only for numeric types
        if (numeric != null) {
            if (answerType !in listOf(
                AnswerType.NUMERIC,
                AnswerType.RATING,
                AnswerType.METERREADING
            )) {
                throw ValidationException("Numeric alerts only for NUMERIC/RATING/METERREADING")
            }

            // Rule 1.3: Below < Above
            if (numeric.below != null && numeric.above != null) {
                if (numeric.below >= numeric.above) {
                    throw ValidationException("Below (${numeric.below}) must be < above (${numeric.above})")
                }
            }
        }

        // Rule 1.4: Choice alerts only for choice types
        if (choice != null) {
            if (answerType !in listOf(
                AnswerType.DROPDOWN,
                AnswerType.CHECKBOX,
                AnswerType.MULTISELECT
            )) {
                throw ValidationException("Choice alerts only for DROPDOWN/CHECKBOX/MULTISELECT")
            }

            // Rule 1.5: Non-empty choice array
            if (choice.isEmpty()) {
                throw ValidationException("Choice alerts must have at least one value")
            }
        }
    }
}
```

---

### ConditionalOperator Evaluation Logic

**Implemented in:** `apps/activity/validators/display_conditions_validator.py`

```python
def evaluate_operator(operator: str, answer: Any, comparison_values: List[str]) -> bool:
    """
    How Django evaluates conditional operators.
    Kotlin MUST match this logic exactly for offline evaluation.
    """

    # Equality operators
    if operator == "EQUALS":
        return str(answer) == comparison_values[0] if comparison_values else False

    elif operator == "NOT_EQUALS":
        return str(answer) != comparison_values[0] if comparison_values else True

    # Containment operators (text)
    elif operator == "CONTAINS":
        return comparison_values[0] in str(answer) if comparison_values else False

    elif operator == "NOT_CONTAINS":
        return comparison_values[0] not in str(answer) if comparison_values else True

    # List operators
    elif operator == "IN":
        return str(answer) in comparison_values

    elif operator == "NOT_IN":
        return str(answer) not in comparison_values

    # Comparison operators (numeric - coerce to float)
    elif operator == "GT":
        try:
            return float(answer) > float(comparison_values[0]) if comparison_values else False
        except (ValueError, TypeError):
            return False  # Non-numeric values fail comparison

    elif operator == "GTE":
        try:
            return float(answer) >= float(comparison_values[0]) if comparison_values else False
        except (ValueError, TypeError):
            return False

    elif operator == "LT":
        try:
            return float(answer) < float(comparison_values[0]) if comparison_values else False
        except (ValueError, TypeError):
            return False

    elif operator == "LTE":
        try:
            return float(answer) <= float(comparison_values[0]) if comparison_values else False
        except (ValueError, TypeError):
            return False

    # Empty/Not empty operators
    elif operator == "IS_EMPTY":
        # Both null/None and empty string are considered empty
        return answer is None or answer == "" or str(answer).strip() == ""

    elif operator == "IS_NOT_EMPTY":
        return answer is not None and answer != "" and str(answer).strip() != ""

    # Unknown operator
    else:
        # Log warning but don't crash
        import logging
        logging.warning(f"Unknown operator: {operator}")
        return False  # Safe default
```

**Kotlin Implementation:**

```kotlin
enum class ConditionalOperator {
    EQUALS, NOT_EQUALS, CONTAINS, NOT_CONTAINS,
    IN, NOT_IN, GT, GTE, LT, LTE,
    IS_EMPTY, IS_NOT_EMPTY;

    fun evaluate(answer: Any?, comparisonValues: List<String>): Boolean {
        return when (this) {
            EQUALS -> answer?.toString() == comparisonValues.firstOrNull()

            NOT_EQUALS -> answer?.toString() != comparisonValues.firstOrNull()

            CONTAINS -> comparisonValues.firstOrNull()?.let {
                answer?.toString()?.contains(it) ?: false
            } ?: false

            NOT_CONTAINS -> comparisonValues.firstOrNull()?.let {
                !(answer?.toString()?.contains(it) ?: false)
            } ?: true

            IN -> comparisonValues.contains(answer?.toString())

            NOT_IN -> !comparisonValues.contains(answer?.toString())

            GT -> try {
                answer?.toString()?.toDouble()?.let { answerNum ->
                    comparisonValues.firstOrNull()?.toDouble()?.let { compareNum ->
                        answerNum > compareNum
                    }
                } ?: false
            } catch (e: NumberFormatException) {
                false  // Match Django: non-numeric fails
            }

            GTE -> try {
                answer?.toString()?.toDouble()?.let { answerNum ->
                    comparisonValues.firstOrNull()?.toDouble()?.let { compareNum ->
                        answerNum >= compareNum
                    }
                } ?: false
            } catch (e: NumberFormatException) {
                false
            }

            LT -> try {
                answer?.toString()?.toDouble()?.let { answerNum ->
                    comparisonValues.firstOrNull()?.toDouble()?.let { compareNum ->
                        answerNum < compareNum
                    }
                } ?: false
            } catch (e: NumberFormatException) {
                false
            }

            LTE -> try {
                answer?.toString()?.toDouble()?.let { answerNum ->
                    comparisonValues.firstOrNull()?.toDouble()?.let { compareNum ->
                        answerNum <= compareNum
                    }
                } ?: false
            } catch (e: NumberFormatException) {
                false
            }

            IS_EMPTY -> {
                // Match Django: null, empty string, or whitespace-only = empty
                answer == null || answer.toString().trim().isEmpty()
            }

            IS_NOT_EMPTY -> {
                answer != null && answer.toString().trim().isNotEmpty()
            }
        }
    }
}
```

---

### Display Conditions Validation Rules

**Enforced by:** `apps/activity/validators/display_conditions_validator.py`

```python
# Rule Set 1: Dependency Existence
def validate_dependency_exists(dependency_qsb_id, current_qset_id):
    """
    Django Rule: Dependency MUST exist in same question set.
    """
    dependency = QuestionSetBelonging.objects.get(pk=dependency_qsb_id)

    if dependency.qset_id != current_qset_id:
        raise ValidationError(
            f"Dependency {dependency_qsb_id} must be in same question set "
            f"(expected qset_id={current_qset_id}, got {dependency.qset_id})"
        )

# Rule Set 2: Dependency Ordering
def validate_dependency_ordering(current_seqno, dependency_seqno):
    """
    Django Rule: Dependency MUST come BEFORE current question.
    """
    if dependency_seqno >= current_seqno:
        raise ValidationError(
            f"Dependency (seqno={dependency_seqno}) must come BEFORE "
            f"this question (seqno={current_seqno})"
        )

# Rule Set 3: Circular Dependencies
def detect_circular_dependency(qsb_id, visited=set()):
    """
    Django Rule: No circular dependency chains allowed.
    Example: A→B→C→A is invalid
    """
    if qsb_id in visited:
        raise ValidationError(f"Circular dependency detected involving {qsb_id}")
    # ... recursive check ...

# Rule Set 4: Operator Requires Values
def validate_operator_values(operator, values):
    """
    Django Rule: Most operators require at least one value.
    Exception: IS_EMPTY and IS_NOT_EMPTY don't need values.
    """
    if operator not in ['IS_EMPTY', 'IS_NOT_EMPTY']:
        if not values or len(values) == 0:
            raise ValidationError(
                f"Operator '{operator}' requires at least one value in 'values' array"
            )
```

**Kotlin Validation Implementation:**

```kotlin
fun DisplayConditions.validate(
    currentQsbId: Int?,
    currentSeqno: Int,
    allQuestionsInSet: List<QuestionSetBelonging>
) {
    val dependency = dependsOn ?: return  // No dependency = valid

    // Rule 1: Dependency must exist in same set
    val dependencyQuestion = allQuestionsInSet.find { it.id == dependency.getId() }
        ?: throw ValidationException("Dependency ${dependency.getId()} not found in question set")

    // Rule 2: Dependency must come before current question
    if (dependencyQuestion.seqno >= currentSeqno) {
        throw ValidationException(
            "Dependency (seqno ${dependencyQuestion.seqno}) must come before this question (seqno $currentSeqno)"
        )
    }

    // Rule 3: Check circular dependencies (recursive)
    val visited = mutableSetOf<Int>()
    if (detectCircular(currentQsbId, allQuestionsInSet, visited)) {
        throw ValidationException("Circular dependency detected")
    }

    // Rule 4: Operator requires values (except IS_EMPTY/IS_NOT_EMPTY)
    if (dependency.operator !in listOf(
        ConditionalOperator.IS_EMPTY,
        ConditionalOperator.IS_NOT_EMPTY
    )) {
        if (dependency.values.isEmpty()) {
            throw ValidationException("Operator ${dependency.operator} requires at least one value")
        }
    }
}
```

---

### Options/OptionsJson Validation Rules

```python
# Rule: Choice types MUST have options
def validate_options_for_answer_type(answer_type, options, options_json):
    """
    Django Rule: DROPDOWN, CHECKBOX, MULTISELECT require options.
    """
    if answer_type in ['DROPDOWN', 'CHECKBOX', 'MULTISELECT']:
        # Prefer JSON, fallback to text
        has_options = (
            (options_json and len(options_json) > 0) or
            (options and options.strip() and options.strip().upper() != 'NONE')
        )

        if not has_options:
            raise ValidationError(
                f"Answer type '{answer_type}' requires options to be defined"
            )

        # Rule: At least 2 options required for choice types
        if options_json:
            if len(options_json) < 2:
                raise ValidationError(
                    f"Choice types require at least 2 options. Got {len(options_json)}"
                )

    # Rule: Numeric types should NOT have options
    elif answer_type in ['NUMERIC', 'RATING', 'METERREADING']:
        # Options should be null or "NONE"
        if options_json and len(options_json) > 0:
            raise ValidationError(
                f"Answer type '{answer_type}' should not have options"
            )
```

**Kotlin Implementation:**

```kotlin
fun Question.validateOptions() {
    when (answertype) {
        AnswerType.DROPDOWN, AnswerType.CHECKBOX, AnswerType.MULTISELECT -> {
            val opts = getOptions()
            if (opts.isEmpty()) {
                throw ValidationException("$answertype requires at least 2 options")
            }
            if (opts.size < 2) {
                throw ValidationException("$answertype requires at least 2 options, got ${opts.size}")
            }
        }

        AnswerType.NUMERIC, AnswerType.RATING, AnswerType.METERREADING -> {
            if (optionsJson?.isNotEmpty() == true) {
                throw ValidationException("$answertype should not have options")
            }
        }

        else -> { /* Other types don't have strict requirements */ }
    }
}
```

---

### Min/Max Validation Rules

```python
# Rule: Min must be less than Max for numeric types
def validate_min_max(answer_type, min_val, max_val):
    """Django validation for min/max fields."""

    if answer_type in ['NUMERIC', 'RATING', 'METERREADING']:
        # Rule: Both required
        if min_val is None or max_val is None:
            raise ValidationError(
                f"Answer type '{answer_type}' requires both min and max values"
            )

        # Rule: Min < Max
        if min_val >= max_val:
            raise ValidationError(
                f"Min value ({min_val}) must be less than max value ({max_val})"
            )

        # Rule: Must be non-negative
        if min_val < 0:
            raise ValidationError(f"Min value cannot be negative (got {min_val})")
```

**Kotlin Validation:**

```kotlin
fun Question.validateMinMax() {
    if (answertype in listOf(
        AnswerType.NUMERIC,
        AnswerType.RATING,
        AnswerType.METERREADING
    )) {
        // Both required
        if (min == null || max == null) {
            throw ValidationException("$answertype requires both min and max")
        }

        // Min < Max
        if (min >= max) {
            throw ValidationException("Min ($min) must be < max ($max)")
        }

        // Non-negative
        if (min < 0) {
            throw ValidationException("Min cannot be negative")
        }
    }
}
```

---

# 5️⃣ SAMPLE PRODUCTION DATA

## Realistic Examples with New Schema

### Example 1: Numeric Question with AlertConfig

```json
{
  "id": 1234,
  "quesname": "Temperature Reading (°C)",
  "answertype": "NUMERIC",

  // OLD FIELDS (Release N, N+1, N+2)
  "options": "NONE",
  "alerton": "<0, >100",

  // NEW FIELDS (Release N+)
  "optionsJson": null,
  "alertConfig": {
    "numeric": {
      "below": 0.0,
      "above": 100.0
    },
    "choice": null,
    "enabled": true
  },

  "min": -20.0,
  "max": 150.0,
  "isavpt": false,
  "avpttype": "NONE",
  "isworkflow": false,
  "enable": true,
  "unit_id": 42,
  "category_id": 15,
  "client_id": 1,
  "tenant_id": 1,
  "ctzoffset": 330,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-10-03T14:22:00Z",
  "cuser_id": 5,
  "muser_id": 8
}
```

---

### Example 2: Dropdown Question with Options

```json
{
  "id": 1235,
  "quesname": "Equipment Status",
  "answertype": "DROPDOWN",

  // OLD FIELDS
  "options": "Working,Needs Repair,Out of Service,Scrapped",
  "alerton": "Needs Repair,Out of Service,Scrapped",

  // NEW FIELDS
  "optionsJson": ["Working", "Needs Repair", "Out of Service", "Scrapped"],
  "alertConfig": {
    "numeric": null,
    "choice": ["Needs Repair", "Out of Service", "Scrapped"],
    "enabled": true
  },

  "min": null,
  "max": null,
  "isavpt": true,
  "avpttype": "BACKCAMPIC",
  "isworkflow": false,
  "enable": true,
  "unit_id": 1,
  "category_id": 20,
  "client_id": 1,
  "tenant_id": 1,
  "ctzoffset": 330,
  "created_at": "2025-02-01T09:00:00Z",
  "updated_at": "2025-10-03T14:22:00Z"
}
```

---

### Example 3: QuestionSetBelonging with Conditional Logic

```json
{
  "id": 5678,
  "qset_id": 101,
  "question_id": 1235,
  "seqno": 2,
  "ismandatory": true,
  "answertype": "MULTILINE",

  // OLD FIELDS
  "options": "NONE",
  "alerton": "NONE",

  // NEW FIELDS
  "optionsJson": null,
  "alertConfig": null,

  // ENHANCED FIELD
  "display_conditions": {
    "depends_on": {
      "qsb_id": 5677,           // NEW key (preferred)
      "question_id": 5677,       // OLD key (backward compat - same value)
      "operator": "EQUALS",
      "values": ["Needs Repair"]
    },
    "show_if": true,
    "cascade_hide": false,        // NEW field
    "group": "repair_details"     // NEW field
  },

  "min": null,
  "max": null,
  "isavpt": false,
  "avpttype": "NONE",
  "client_id": 1,
  "bu_id": 10,
  "tenant_id": 1,
  "ctzoffset": 330,
  "alertmails_sendto": {"id__code": []},
  "buincludes": ["BU001", "BU002"],
  "created_at": "2025-02-01T09:15:00Z",
  "updated_at": "2025-10-03T14:22:00Z"
}
```

---

### Example 4: Checkbox Question with Multiple Alert Options

```json
{
  "id": 1236,
  "quesname": "Select All Issues Found",
  "answertype": "CHECKBOX",

  // OLD FIELDS
  "options": "Broken,Damaged,Missing,Dirty,Worn Out",
  "alerton": "Broken,Damaged,Missing",

  // NEW FIELDS
  "optionsJson": ["Broken", "Damaged", "Missing", "Dirty", "Worn Out"],
  "alertConfig": {
    "numeric": null,
    "choice": ["Broken", "Damaged", "Missing"],
    "enabled": true
  },

  "min": null,
  "max": null,
  "isavpt": true,
  "avpttype": "BACKCAMPIC",
  "isworkflow": true,
  "enable": true,
  "client_id": 1,
  "tenant_id": 1
}
```

---

### Example 5: get_questionset_with_conditional_logic Response

```json
{
  "data": {
    "getQuestionsetWithConditionalLogic": {
      "nrows": 1,
      "msg": "Questionset 101 with conditional logic retrieved successfully (2 validation warnings)",
      "records": "[{\"questions\": [{\"pk\": 5677, \"question_id\": 1234, \"quesname\": \"Has Equipment Issue?\", \"answertype\": \"DROPDOWN\", \"min\": null, \"max\": null, \"options\": \"Yes,No\", \"alerton\": \"Yes\", \"ismandatory\": true, \"seqno\": 1, \"isavpt\": false, \"avpttype\": \"NONE\", \"display_conditions\": null, \"options_json\": [\"Yes\", \"No\"], \"alert_config\": {\"choice\": [\"Yes\"], \"enabled\": true}}, {\"pk\": 5678, \"question_id\": 1235, \"quesname\": \"Describe Issue\", \"answertype\": \"MULTILINE\", \"min\": null, \"max\": null, \"options\": \"NONE\", \"alerton\": \"NONE\", \"ismandatory\": true, \"seqno\": 2, \"isavpt\": false, \"avpttype\": \"NONE\", \"display_conditions\": {\"depends_on\": {\"qsb_id\": 5677, \"question_id\": 5677, \"operator\": \"EQUALS\", \"values\": [\"Yes\"]}, \"show_if\": true, \"cascade_hide\": false, \"group\": \"issue_details\"}, \"options_json\": null, \"alert_config\": null}, {\"pk\": 5679, \"question_id\": 1236, \"quesname\": \"Upload Photo\", \"answertype\": \"SIGNATURE\", \"min\": null, \"max\": null, \"options\": \"NONE\", \"alerton\": \"NONE\", \"ismandatory\": false, \"seqno\": 3, \"isavpt\": true, \"avpttype\": \"BACKCAMPIC\", \"display_conditions\": {\"depends_on\": {\"qsb_id\": 5677, \"question_id\": 5677, \"operator\": \"EQUALS\", \"values\": [\"Yes\"]}, \"show_if\": true, \"cascade_hide\": true, \"group\": \"issue_details\"}, \"options_json\": null, \"alert_config\": null}], \"dependency_map\": {\"5677\": [{\"question_id\": 5678, \"question_seqno\": 2, \"operator\": \"EQUALS\", \"values\": [\"Yes\"], \"show_if\": true, \"cascade_hide\": false, \"group\": \"issue_details\"}, {\"question_id\": 5679, \"question_seqno\": 3, \"operator\": \"EQUALS\", \"values\": [\"Yes\"], \"show_if\": true, \"cascade_hide\": true, \"group\": \"issue_details\"}]}, \"has_conditional_logic\": true, \"validation_warnings\": [{\"question_id\": 5680, \"warning\": \"Dependency on QSB ID 5682 not found in this question set\", \"severity\": \"error\"}, {\"question_id\": 5681, \"warning\": \"Circular dependency detected involving question 5681\", \"severity\": \"critical\"}]}]"
    }
  }
}
```

**Parsed Structure:**

```json
{
  "questions": [
    { /* Question 1 - see above */ },
    { /* Question 2 - see above */ },
    { /* Question 3 - see above */ }
  ],
  "dependency_map": {
    "5677": [  // Parent question (seqno 1)
      {
        "question_id": 5678,
        "question_seqno": 2,
        "operator": "EQUALS",
        "values": ["Yes"],
        "show_if": true,
        "cascade_hide": false,
        "group": "issue_details"
      },
      {
        "question_id": 5679,
        "question_seqno": 3,
        "operator": "EQUALS",
        "values": ["Yes"],
        "show_if": true,
        "cascade_hide": true,  // This one cascades
        "group": "issue_details"
      }
    ]
  },
  "has_conditional_logic": true,
  "validation_warnings": [  // NEW in Release N
    {
      "question_id": 5680,
      "warning": "Dependency on QSB ID 5682 not found in this question set",
      "severity": "error"
    },
    {
      "question_id": 5681,
      "warning": "Circular dependency detected involving question 5681",
      "severity": "critical"
    }
  ]
}
```

---

### Example 6: Mixed Data (Transition State)

**Some records have JSON, some only have text:**

```json
{
  "id": 1237,
  "quesname": "Old Question (Not Yet Migrated)",
  "answertype": "DROPDOWN",

  // OLD FIELDS (present)
  "options": "Option1,Option2,Option3",
  "alerton": "Option3",

  // NEW FIELDS (null - not migrated yet)
  "optionsJson": null,
  "alertConfig": null,

  // ... rest of fields
}
```

**Android MUST handle this case:**

```kotlin
fun Question.getOptions(): List<String> {
    // Prefer JSON (if migrated)
    return optionsJson
        // Fallback to text parsing (if not migrated)
        ?: options?.split(",")?.map { it.trim() }
        // Ultimate fallback
        ?: emptyList()
}
```

---

### Example 7: Rating Question

```json
{
  "id": 1238,
  "quesname": "Rate Service Quality (1-5 stars)",
  "answertype": "RATING",

  "options": "NONE",
  "alerton": "NONE",

  "optionsJson": null,
  "alertConfig": null,  // No alerts for this rating question

  "min": 1.0,
  "max": 5.0,
  "isavpt": false,
  "avpttype": "NONE"
}
```

---

### Example 8: Complex Conditional Logic (Multi-Level)

**Question Set with 3-level dependency chain:**

```json
// Question 1 (seqno=1, no dependencies)
{
  "id": 100,
  "seqno": 1,
  "quesname": "Is Equipment Operational?",
  "answertype": "DROPDOWN",
  "optionsJson": ["Yes", "No"],
  "display_conditions": null
}

// Question 2 (seqno=2, depends on Q1)
{
  "id": 101,
  "seqno": 2,
  "quesname": "Describe Problem",
  "answertype": "MULTILINE",
  "display_conditions": {
    "depends_on": {
      "qsb_id": 100,
      "operator": "EQUALS",
      "values": ["No"]
    },
    "show_if": true,
    "cascade_hide": true,  // If hidden, hide Q3 too
    "group": "problem_details"
  }
}

// Question 3 (seqno=3, depends on Q1 - same condition as Q2)
{
  "id": 102,
  "seqno": 3,
  "quesname": "Upload Photo of Issue",
  "answertype": "SIGNATURE",
  "isavpt": true,
  "avpttype": "BACKCAMPIC",
  "display_conditions": {
    "depends_on": {
      "qsb_id": 100,  // Same parent as Q2
      "operator": "EQUALS",
      "values": ["No"]
    },
    "show_if": true,
    "cascade_hide": false,
    "group": "problem_details"  // Same group as Q2
  }
}
```

**dependency_map for this set:**

```json
{
  "100": [  // Q1 is parent to both Q2 and Q3
    {
      "question_id": 101,
      "question_seqno": 2,
      "operator": "EQUALS",
      "values": ["No"],
      "show_if": true,
      "cascade_hide": true,
      "group": "problem_details"
    },
    {
      "question_id": 102,
      "question_seqno": 3,
      "operator": "EQUALS",
      "values": ["No"],
      "show_if": true,
      "cascade_hide": false,
      "group": "problem_details"
    }
  ]
}
```

**Kotlin Evaluation Logic:**

```kotlin
fun evaluateQuestionVisibility(
    question: QuestionSetBelonging,
    answers: Map<Int, Any>,
    allQuestions: List<QuestionSetBelonging>
): Boolean {
    val conditions = question.displayConditions ?: return true  // Always show if no conditions

    val dependency = conditions.dependsOn ?: return true
    val parentId = dependency.getId()

    // Get parent question
    val parent = allQuestions.find { it.id == parentId } ?: return false

    // Check if parent is visible (recursive)
    val parentVisible = evaluateQuestionVisibility(parent, answers, allQuestions)

    // If parent is hidden and cascade_hide is true, hide this too
    if (!parentVisible && parent.displayConditions?.cascadeHide == true) {
        return false
    }

    // Get answer to parent question
    val parentAnswer = answers[parentId] ?: return !conditions.showIf

    // Evaluate operator
    val conditionMet = dependency.operator.evaluate(parentAnswer, dependency.values)

    // Return based on show_if logic
    return if (conditions.showIf) conditionMet else !conditionMet
}
```

---

### Example 9: Empty AlertConfig (No Alerts)

```json
{
  "id": 1239,
  "quesname": "Additional Comments",
  "answertype": "MULTILINE",

  "options": "NONE",
  "alerton": "NONE",

  "optionsJson": null,
  "alertConfig": null,  // ✅ Completely null is valid (no alerts)

  "min": null,
  "max": null
}
```

---

### Example 10: ValidationWarning Response (When Issues Exist)

```json
{
  "questions": [ /* array of questions */ ],
  "dependency_map": { /* normal map */ },
  "has_conditional_logic": true,

  // NEW: Validation warnings array
  "validation_warnings": [
    {
      "question_id": 5680,
      "warning": "Dependency on QSB ID 9999 not found in this question set",
      "severity": "error"
    },
    {
      "question_id": 5681,
      "warning": "Dependency on QSB ID 5679 (seqno 3) comes after or same as this question (seqno 2)",
      "severity": "error"
    },
    {
      "question_id": 5682,
      "warning": "Circular dependency detected involving question 5682",
      "severity": "critical"
    }
  ]
}
```

**Android Handling:**

```kotlin
fun handleConditionalLogicResponse(response: ConditionalLogicResponse) {
    // Check for validation warnings
    response.validationWarnings?.let { warnings ->
        val criticalWarnings = warnings.filter { it.severity == "critical" }

        if (criticalWarnings.isNotEmpty()) {
            // Show error dialog to user
            showErrorDialog(
                title = "Question Set Configuration Error",
                message = "This checklist has critical issues:\n" +
                    criticalWarnings.joinToString("\n") { "• ${it.warning}" }
            )
        }

        // Log all warnings
        warnings.forEach { warning ->
            when (warning.severity) {
                "critical" -> Log.e("QuestionSet", "Critical: ${warning.warning}")
                "error" -> Log.w("QuestionSet", "Error: ${warning.warning}")
                "warning" -> Log.i("QuestionSet", "Warning: ${warning.warning}")
            }
        }
    }

    // Continue processing questions (warnings are informational)
    renderQuestions(response.questions)
}
```

---

## 📊 Data Format Summary Table

| Field | Type in JSON | Kotlin Type | Can Be Null? | Example Values |
|-------|--------------|-------------|--------------|----------------|
| `optionsJson` | Array of strings | `List<String>?` | ✅ Yes | `["Yes", "No"]` or `null` |
| `alertConfig` | Object | `AlertConfig?` | ✅ Yes | `{"numeric": {...}}` or `null` |
| `alertConfig.numeric` | Object | `NumericAlert?` | ✅ Yes | `{"below": 10, "above": 90}` |
| `alertConfig.choice` | Array of strings | `List<String>?` | ✅ Yes | `["Alert1"]` or `null` |
| `alertConfig.enabled` | Boolean | `Boolean` | ❌ No | `true` or `false` |
| `display_conditions.depends_on.qsb_id` | Integer | `Int?` | ✅ Yes | `5677` or `null` |
| `display_conditions.cascade_hide` | Boolean | `Boolean` | ❌ No (default false) | `true` or `false` |
| `display_conditions.group` | String | `String?` | ✅ Yes | `"issue_details"` or `null` |
| `validation_warnings` | Array of objects | `List<ValidationWarning>?` | ✅ Yes | `[{...}]` or `null` or `[]` |

---

# 📞 STAGING ENVIRONMENT DETAILS

## Access Information

### URLs

**GraphQL Endpoint:**
```
Primary:   https://<staging-domain>/api/graphql/
Alt Path:  https://<staging-domain>/graphql/ (may redirect to primary)
```

**GraphiQL Explorer:**
```
Browser:   https://<staging-domain>/api/graphql/
```

**⚠️ ACTION REQUIRED:** Contact backend team for exact `<staging-domain>`.

**Common patterns to try:**
- `staging-api.intelliwiz.com`
- `api.staging.intelliwiz.com`
- `staging.yourcompany.com`

---

### Authentication Setup

**Step 1: Get JWT Token**

```graphql
mutation AndroidLogin {
  loginMutation(
    loginid: "mobile_test_user"  # Get from backend team
    password: "test_password"     # Get from backend team
    source: "ANDROID"
  ) {
    rc         # 200 = success
    msg        # Success message or error
    token      # JWT token for subsequent requests
  }
}
```

**Step 2: Use Token in Requests**

```kotlin
// OkHttp Interceptor
class AuthInterceptor(private val tokenProvider: () -> String?) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenProvider()
        val request = if (token != null) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .addHeader("Content-Type", "application/json")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

// Apollo Client Setup
val apolloClient = ApolloClient.Builder()
    .serverUrl("https://staging.yourapp.com/api/graphql/")
    .okHttpClient(
        OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor { getStoredJwtToken() })
            .build()
    )
    .build()
```

---

### Test Account Request

**Email this to backend team:**

```
Subject: Staging Access Request - Android Team

Hi Backend Team,

For Android migration testing (Question schema changes), we need:

1. Staging GraphQL URL: https://<domain>/api/graphql/
2. Test user credentials:
   - Username/loginid: _____________
   - Password: _____________
   - Or JWT token: _____________

3. Test data:
   - Client ID with question sets: _____________
   - Business Unit ID: _____________
   - Question set ID with conditional logic: _____________

4. Confirm staging is on Release N (2025-10-03 deployment)?

5. Is GraphiQL enabled on staging for manual testing?

Thanks!
Android Team
```

---

### CORS Configuration

**If you get CORS errors**, backend team needs to add your domain to:

```python
# intelliwiz_config/settings/development.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8081",  # Your development server
    "https://android-dev.yourcompany.com",  # Your domain
]
```

**Android localhost testing:**
- Use `10.0.2.2` instead of `localhost` (Android emulator)
- Or use actual IP address of your development machine

---

### Health Check

**Verify staging is accessible:**

```bash
# Curl test
curl -X POST https://staging.yourapp.com/api/graphql/ \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { queryType { name } } }"}'

# Should return: {"data": {"__schema": {"queryType": {"name": "Query"}}}}
```

---

# ⏰ DEPLOYMENT TIMELINE

## Confirmed Release Dates

| Release | Backend Deploy | Staging Avail | Code Freeze | Android Deploy | Weeks from Now |
|---------|----------------|---------------|-------------|----------------|----------------|
| **N** | ✅ 2025-10-03 | ✅ Now | ✅ Done | ✅ Compatible | Week 0 (Current) |
| **N+1** | 🟡 2025-10-31 | 2025-10-28 | 2025-10-24 | 2025-10-31 | Week 4 |
| **N+2** | 🟡 2025-11-28 | 2025-11-25 | 2025-11-21 | 2025-11-28 | Week 8 |
| **N+3** | 🔴 2026-01-09 | 2026-01-06 | 2026-01-02 | 2026-01-09 | Week 14 |

**Sprint Schedule:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Week 0-4  (Oct 3 - Oct 31)  │ Sprint 42 │ Release N+1 Dev      │
│ Week 4-8  (Nov 1 - Nov 28)  │ Sprint 43 │ Release N+2 Dev      │
│ Week 8-12 (Nov 29 - Dec 26) │ Sprint 44 │ Release N+2 Testing  │
│ Week 12-14 (Dec 27 - Jan 9) │ Sprint 45 │ Release N+3 (BREAK)  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Android Development Timeline

**Release N+1 Work (5-8 days):**

| Week | Dates | Tasks | Deliverable |
|------|-------|-------|-------------|
| Week 1 | Oct 7-11 | Add models + AlertConfig class | Models updated |
| Week 2 | Oct 14-18 | Compatibility layer + update usages | All code migrated |
| Week 3 | Oct 21-24 | Testing + bug fixes | PR ready |
| Week 3.5 | Oct 24-28 | Code freeze, staging testing | Deployed |

**Release N+2 Work (3-5 days):**

| Week | Dates | Tasks | Deliverable |
|------|-------|-------|-------------|
| Week 5 | Nov 4-8 | Remove compat layer, use JSON directly | Code updated |
| Week 6-7 | Nov 11-21 | Full regression testing | Tests pass |
| Week 8 | Nov 21-25 | Code freeze, final QA | Deployed |

---

### Critical Dates for Android Team

**⚠️ HARD DEADLINES:**

| Date | Event | Consequence if Missed |
|------|-------|----------------------|
| **2025-10-24** | N+1 code freeze | Can't deploy with backend N+1 |
| **2025-11-21** | N+2 code freeze | Not fully migrated before N+3 |
| **2026-01-02** | N+3 code freeze | **APP WILL CRASH** if not migrated |

**Buffer Time:**
- Each release has 3-4 day staging window
- Can request 1-week extension with product approval
- N+3 breaking change can be delayed max 1 month

---

# 📊 COMPREHENSIVE VALIDATION RULES MATRIX

## All Backend Validation Rules for Kotlin

| Rule ID | Field | Condition | Validation | Error Message | Severity |
|---------|-------|-----------|------------|---------------|----------|
| **ALERT-001** | alertConfig | numeric != null AND choice != null | ❌ REJECT | "Cannot have both numeric and choice alerts" | Critical |
| **ALERT-002** | alertConfig.numeric | answer_type NOT IN [NUMERIC, RATING, METERREADING] | ❌ REJECT | "Numeric alerts only for numeric types" | Critical |
| **ALERT-003** | alertConfig.numeric.below | below >= above | ❌ REJECT | "Below must be < above" | Critical |
| **ALERT-004** | alertConfig.choice | answer_type NOT IN [DROPDOWN, CHECKBOX, MULTISELECT] | ❌ REJECT | "Choice alerts only for choice types" | Critical |
| **ALERT-005** | alertConfig.choice | len(choice) == 0 | ❌ REJECT | "Choice alerts need at least 1 value" | Critical |
| **OPT-001** | optionsJson | answer_type IN [DROPDOWN, CHECKBOX, MULTISELECT] AND empty | ❌ REJECT | "Choice types require options" | Critical |
| **OPT-002** | optionsJson | answer_type IN [DROPDOWN, CHECKBOX, MULTISELECT] AND len < 2 | ❌ REJECT | "Choice types need at least 2 options" | Critical |
| **OPT-003** | optionsJson | answer_type IN [NUMERIC, RATING] AND not empty | ⚠️ WARN | "Numeric types shouldn't have options" | Warning |
| **MINMAX-001** | min, max | answer_type IN [NUMERIC, RATING] AND (min OR max) is null | ❌ REJECT | "Numeric types require both min and max" | Critical |
| **MINMAX-002** | min, max | min >= max | ❌ REJECT | "Min must be < max" | Critical |
| **MINMAX-003** | min | min < 0 | ❌ REJECT | "Min cannot be negative" | Critical |
| **DEP-001** | display_conditions.depends_on | dependency not in same qset | ❌ REJECT | "Dependency must be in same question set" | Critical |
| **DEP-002** | display_conditions.depends_on | dependency.seqno >= current.seqno | ❌ REJECT | "Dependency must come BEFORE this question" | Critical |
| **DEP-003** | display_conditions.depends_on | qsb_id == current qsb_id | ❌ REJECT | "Cannot depend on self" | Critical |
| **DEP-004** | display_conditions.depends_on | circular reference detected | ❌ REJECT | "Circular dependency: A→B→A" | Critical |
| **DEP-005** | display_conditions.depends_on.operator | operator NOT IN ['IS_EMPTY', 'IS_NOT_EMPTY'] AND values.empty | ❌ REJECT | "Operator requires at least one value" | Critical |
| **DEP-006** | display_conditions.depends_on.qsb_id | dependency qsb_id doesn't exist in DB | ❌ REJECT | "Dependency ID {id} does not exist" | Critical |

---

### Validation Rule Implementation Priorities

**MUST IMPLEMENT (Release N+1):**
- ALERT-001 through ALERT-005 (prevents submission errors)
- OPT-001, OPT-002 (prevents empty dropdowns)
- MINMAX-001, MINMAX-002 (prevents invalid ranges)

**SHOULD IMPLEMENT (Release N+1):**
- DEP-001 through DEP-006 (prevents conditional logic errors)
- OPT-003 (warning only, not blocking)

**CAN SKIP (Server validates):**
- MINMAX-003 (server rejects anyway)

---

# 🎯 QUICK ACTION CHECKLIST FOR ANDROID TEAM

## Immediate Actions (This Week)

- [ ] **Read all 3 documents:**
  - [ ] `ANDROID_SCHEMA_CHANGES_CHECKLIST.md`
  - [ ] `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md`
  - [ ] `ANDROID_BACKEND_HANDOFF_COMPLETE.md` (this file)

- [ ] **Get staging access:**
  - [ ] Request staging URL from backend team
  - [ ] Request test credentials
  - [ ] Verify access works (curl test)

- [ ] **Validate compatibility:**
  - [ ] Test current Android app against staging
  - [ ] Verify no crashes with new fields (null)
  - [ ] Document any issues found

- [ ] **Plan migration:**
  - [ ] Schedule 5-8 days for Release N+1 work
  - [ ] Schedule 3-5 days for Release N+2 work
  - [ ] Book team resources

---

## Release N+1 Actions (Starting Oct 7)

### Week 1: Models & Types

- [ ] Create `AlertConfig.kt` data class
- [ ] Create `NumericAlert.kt` data class
- [ ] Create `ValidationWarning.kt` data class
- [ ] Update `Question.kt` - add 2 new fields
- [ ] Update `QuestionSetBelonging.kt` - add 2 new fields
- [ ] Update `DisplayConditions.kt` - add 2 new fields
- [ ] Update `Dependency.kt` - add qsbId field
- [ ] Update `ConditionalOperator.kt` - add 6 new values
- [ ] Update `ConditionalLogicResponse.kt` - add validationWarnings
- [ ] Update `DependencyInfo.kt` - add cascadeHide, group

**Deliverable:** All models updated, code compiles

### Week 2: Compatibility Layer

- [ ] Create `QuestionExtensions.kt`
- [ ] Implement `getOptions()`
- [ ] Implement `getAlertBelow()`
- [ ] Implement `getAlertAbove()`
- [ ] Implement `getAlertChoices()`
- [ ] Create `DependencyExtensions.kt`
- [ ] Implement `getId()` helper
- [ ] Write 35 unit tests

**Deliverable:** Compatibility layer complete, tests passing

### Week 3: Update Usages

- [ ] Find all `.options?.split(",")` → Replace with `.getOptions()`
- [ ] Find all `.alerton` parsing → Replace with `.getAlertBelow()` / `.getAlertChoices()`
- [ ] Find all `.questionId` in Dependency → Replace with `.getId()`
- [ ] Update UI components
- [ ] Update form submission logic
- [ ] Update validation logic
- [ ] Write 20 integration tests

**Deliverable:** All code migrated, integration tests passing

### Week 3.5: Testing & Deploy

- [ ] Run full regression test suite
- [ ] Test on staging with real data
- [ ] Performance testing
- [ ] Code review
- [ ] QA approval
- [ ] Deploy to production

**Deliverable:** Release N+1 deployed successfully

---

## Release N+2 Actions (Starting Nov 4)

- [ ] Remove compatibility layer methods
- [ ] Use `optionsJson!!` directly (with null checks)
- [ ] Use `alertConfig` directly
- [ ] Use `qsbId!!` directly
- [ ] Remove all text parsing code
- [ ] Full regression testing
- [ ] Deploy

---

## Release N+3 Checklist (Before Jan 2)

- [ ] Verify 100% migration complete
- [ ] No references to deprecated fields
- [ ] Minimum app version enforcement active
- [ ] Force update flow tested

---

# 📧 CONTACT INFORMATION

## Backend Team Contacts

**General Questions:**
- Email: backend-team@company.com
- Slack: #backend-team

**Schema/API Questions:**
- Lead: backend-lead@company.com
- Slack: #mobile-backend-migration

**Staging Access:**
- DevOps: devops-team@company.com
- Slack: #devops

**Emergency (Production Issues):**
- PagerDuty: On-call engineer
- Escalation: CTO

---

## Resources

**Documentation:**
- This file: `ANDROID_BACKEND_HANDOFF_COMPLETE.md`
- Full checklist: `ANDROID_SCHEMA_CHANGES_CHECKLIST.md`
- Quick ref: `QUESTION_REFACTORING_QUICK_REFERENCE.md`
- Migration guide: `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md`

**Testing:**
- GraphQL SDL Schema: See Section 1 above
- Sample data: See Section 5 above
- Validation rules: See Section 4 above

**Staging:**
- URL: Contact backend team (Section 2)
- Credentials: Contact backend team (Section 2)
- Test data IDs: Contact backend team

---

# ✅ HANDOFF ACCEPTANCE

**Android Team:** Please confirm receipt and review of this document.

**Confirmation Checklist:**

- [ ] Document received and reviewed
- [ ] Timeline understood and acceptable
- [ ] Effort estimates reviewed (5-8 days N+1, 3-5 days N+2)
- [ ] Staging access requested
- [ ] GraphQL SDL saved for Apollo code generation
- [ ] Validation rules understood
- [ ] Sample data formats reviewed
- [ ] Questions documented (if any)
- [ ] Sprint planning updated with migration work
- [ ] Team resources allocated

**Sign-off:**

```
Android Team Lead: _________________________  Date: __________

Backend Team Lead: _________________________  Date: __________

Product Owner:     _________________________  Date: __________
```

---

**ALL 5 CRITICAL ITEMS ARE NOW PROVIDED IN THIS DOCUMENT!** ✅

**Next Step:** Android team reviews and confirms acceptance.
