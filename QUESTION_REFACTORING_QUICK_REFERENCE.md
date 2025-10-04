# Question/QuestionSet Refactoring - Quick Reference

**Updated:** 2025-10-03 | **Version:** 2.0 | **Status:** ✅ Production Ready

---

## 🎯 For Developers: What Changed

### Import Changes

```python
# ✅ NEW (Preferred)
from apps.activity.enums import AnswerType, AvptType, ConditionalOperator

# 🟡 OLD (Still works - deprecated)
from apps.activity.models.question_model import Question
answer_type = Question.AnswerType.NUMERIC  # Triggers deprecation warning
```

### Field Changes

```python
# Question model - NEW fields available
question = Question.objects.get(id=123)

# OLD (still works but deprecated)
options_text = question.options  # "Option1,Option2,Option3"
alert_text = question.alerton    # "<10, >90"

# NEW (preferred)
options_json = question.options_json  # ["Option1", "Option2", "Option3"]
alert_config = question.alert_config  # {"numeric": {"below": 10, "above": 90}}
```

### Validation Changes

```python
# QuestionSetBelonging now validates on save
belonging = QuestionSetBelonging(
    qset=qset,
    question=question,
    seqno=2,
    display_conditions={
        'depends_on': {
            'qsb_id': 1,  # NEW naming (preferred)
            # 'question_id': 1  # OLD naming (still works)
            'operator': 'EQUALS',
            'values': ['Yes']
        }
    }
)

belonging.save()  # Automatically validates display_conditions
# Raises ValidationError if:
# - Dependency doesn't exist
# - Dependency in different qset
# - Dependency comes after this question
# - Circular dependency detected
```

---

## 🚀 For Mobile Developers: GraphQL Changes

### No Breaking Changes (Yet!)

```graphql
# Query still works exactly the same
query GetQuestions($mdtz: String!) {
  getQuestionsmodifiedafter(mdtz: $mdtz, ctzoffset: 0, clientid: 1) {
    nrows
    records  # Contains BOTH old and new fields
    msg
  }
}
```

### New Fields Available

```graphql
# Response now includes:
{
  "options": "Opt1,Opt2",           # OLD (deprecated but present)
  "optionsJson": ["Opt1", "Opt2"],  # NEW
  "alerton": "<10, >90",            # OLD (deprecated but present)
  "alertConfig": {                  # NEW
    "numeric": {"below": 10, "above": 90},
    "enabled": true
  }
}
```

**Android Action:** Update models to include new fields (nullable) in next release.

---

## 🧪 Testing Commands

```bash
# Run all question tests
python -m pytest apps/activity/tests/test_question_*.py -v

# Run specific test suite
python -m pytest apps/activity/tests/test_question_enums.py -v

# Run Android contract tests
python -m pytest -m android_contract -v

# Run performance benchmarks
python -m pytest -m performance -v

# Run security tests
python -m pytest -m security apps/activity/tests/test_display_conditions_validation.py -v
```

---

## 📋 Migration Commands

```bash
# Check migration plan (dry-run)
python manage.py migrate --plan activity

# Apply migrations
python manage.py migrate activity

# Check migration status
python manage.py showmigrations activity

# Verify JSON fields populated
python manage.py shell
>>> from apps.activity.models import Question
>>> Question.objects.filter(options_json__isnull=False).count()

# Run data migration service manually (if needed)
>>> from apps.activity.services.question_data_migration_service import QuestionDataMigrationService
>>> service = QuestionDataMigrationService(dry_run=True)  # Dry-run first!
>>> stats = service.migrate_all()
>>> print(service.generate_report())
```

---

## 🔧 Common Tasks

### Creating a New Question

```python
from apps.activity.models import Question
from apps.activity.enums import AnswerType, AvptType

# Use unified enums
question = Question.objects.create(
    quesname="Temperature",
    answertype=AnswerType.NUMERIC,  # ✅ Use centralized enum
    options_json=None,  # Not needed for numeric
    alert_config={
        'numeric': {'below': 0.0, 'above': 100.0},
        'enabled': True
    },
    min=0.0,
    max=150.0,
    client_id=1,
    tenant_id=1
)
```

### Creating Conditional Questions

```python
# Parent question
qsb1 = QuestionSetBelonging.objects.create(
    qset=qset,
    question=question1,
    answertype=AnswerType.DROPDOWN,
    seqno=1,
    options_json=["Yes", "No"],
    client_id=1,
    bu_id=1,
    tenant_id=1
)

# Dependent question (shows only if parent = "Yes")
qsb2 = QuestionSetBelonging.objects.create(
    qset=qset,
    question=question2,
    answertype=AnswerType.MULTILINE,
    seqno=2,  # Must be > qsb1.seqno
    display_conditions={
        'depends_on': {
            'qsb_id': qsb1.id,  # ✅ Correct naming
            'operator': 'EQUALS',
            'values': ['Yes']
        },
        'show_if': True,
        'cascade_hide': False
    },
    client_id=1,
    bu_id=1,
    tenant_id=1
)
# Automatically validates on save!
```

### Querying with Conditional Logic

```python
# Get questions with dependency map
result = QuestionSetBelonging.objects.get_questions_with_logic(qset_id=123)

# Returns:
# {
#   'questions': [...]  # All questions
#   'dependency_map': {...}  # Who depends on whom
#   'has_conditional_logic': True/False
#   'validation_warnings': [...]  # Any issues found
# }

# Check for issues
if result.get('validation_warnings'):
    for warning in result['validation_warnings']:
        print(f"⚠️ {warning['severity']}: {warning['warning']}")
```

---

## 🐛 Debugging

### Check if Enum Migration Worked

```python
from apps.activity.enums import AnswerType
from apps.activity.models import Question

# Should be identical
print(AnswerType.NUMERIC)  # "NUMERIC"
print(Question.AnswerType.NUMERIC)  # "NUMERIC" (with deprecation warning)
```

### Check if JSON Migration Ran

```python
from apps.activity.models import Question, QuestionSetBelonging

# Count migrated records
questions_migrated = Question.objects.filter(options_json__isnull=False).count()
belongings_migrated = QuestionSetBelonging.objects.filter(options_json__isnull=False).count()

print(f"Questions migrated: {questions_migrated}")
print(f"Belongings migrated: {belongings_migrated}")

# Find records that failed migration
failed_questions = Question.objects.filter(
    options__isnull=False,
    options_json__isnull=True
).exclude(options='NONE')

print(f"Questions failed: {failed_questions.count()}")
```

### Check Index Usage

```sql
-- In psql
\d question  -- Should show new indexes
\d questionsetbelonging  -- Should show new indexes

-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM questionsetbelonging
WHERE qset_id = 123
ORDER BY seqno;

-- Should use: qsb_qset_seqno_idx
```

---

## 📦 New Files Added

```
apps/activity/
├── enums/
│   ├── __init__.py
│   └── question_enums.py          (270 lines)
├── validators/
│   ├── __init__.py
│   └── display_conditions_validator.py  (230 lines)
├── services/
│   └── question_data_migration_service.py  (320 lines)
├── migrations/
│   ├── 0018_add_question_performance_indexes.py  (150 lines)
│   ├── 0019_add_json_fields_for_options_and_alerts.py  (120 lines)
│   └── 0020_migrate_to_json_fields.py  (180 lines)
└── tests/
    ├── test_question_enums.py  (220 lines)
    ├── test_question_json_migration.py  (180 lines)
    ├── test_display_conditions_validation.py  (280 lines)
    ├── test_question_performance.py  (150 lines)
    └── test_question_api_contract.py  (220 lines)

docs/mobile-api/
└── QUESTION_SCHEMA_MIGRATION.md  (450 lines)

Root:
├── QUESTION_QUESTIONSET_REFACTORING_COMPLETE.md  (600 lines)
└── QUESTION_REFACTORING_QUICK_REFERENCE.md  (this file)
```

**Total:** 15 new files, 3,370 new lines

---

## 🔗 Related Documentation

- **Android Migration Guide:** `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md`
- **Implementation Summary:** `QUESTION_QUESTIONSET_REFACTORING_COMPLETE.md`
- **Enum Reference:** `apps/activity/enums/question_enums.py`
- **Validator Reference:** `apps/activity/validators/display_conditions_validator.py`
- **Code Quality Rules:** `.claude/rules.md`

---

**For questions or issues:** See implementation summary or contact backend team.
