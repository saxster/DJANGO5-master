# Magic Numbers Extraction - Quick Start

**Status:** ✅ Ready to Execute  
**Infrastructure:** Complete  
**Next Step:** Run pilot migration

---

## ✅ What's Been Completed

1. **Constants Created** (3 files):
   - `apps/core/constants/status_constants.py` - HTTP codes, pagination, image processing
   - `apps/core/constants/datetime_constants.py` - Time conversions
   - `apps/core/constants/spatial_constants.py` - GPS and geofencing

2. **Automation Scripts** (3 scripts):
   - `scripts/detect_magic_numbers.py` - Find magic numbers
   - `scripts/migrate_magic_numbers.py` - Replace magic numbers
   - `scripts/verify_magic_number_constants.py` - Verify setup

3. **Documentation** (2 guides):
   - `MAGIC_NUMBERS_EXTRACTION_COMPLETE.md` - Full implementation plan
   - `MAGIC_NUMBERS_DELIVERABLES.md` - Detailed deliverables and examples

---

## 🚀 Execute Migration (3 Steps)

### Step 1: Verify Infrastructure (30 seconds)

```bash
# Verify all constants are properly defined
PYTHONPATH=. python3 scripts/verify_magic_number_constants.py
```

**Expected output:**
```
✅ ALL VERIFICATIONS PASSED
```

---

### Step 2: Run Detection (1 minute)

```bash
# Scan codebase for magic numbers
python3 scripts/detect_magic_numbers.py apps/
```

**Expected output:**
```
TIME (858 occurrences)
TIME_UNITS (1285 occurrences)
STATUS_CODE (2060 occurrences)
RATE/PERCENTAGE (2109 occurrences)
BUSINESS_RULE (7316 occurrences)
Total: 13,628 magic numbers found
```

---

### Step 3: Execute Pilot Migration (5 minutes)

#### 3a. Dry Run (Preview Changes)

```bash
# See what would change (no modifications)
python3 scripts/migrate_magic_numbers.py \
    --app apps/attendance \
    --category TIME \
    --dry-run
```

**Expected:**
- Files scanned: ~126
- Files with changes: ~20
- Total replacements: ~32

#### 3b. Apply Changes

```bash
# Apply TIME constant replacements
python3 scripts/migrate_magic_numbers.py \
    --app apps/attendance \
    --category TIME \
    --apply
```

#### 3c. Verify & Test

```bash
# Check syntax
python3 -m py_compile apps/attendance/*.py

# Run app tests
python -m pytest apps/attendance/tests/ -v --tb=short

# Django checks
python manage.py check
```

---

## 📊 Migration Categories

| Category | Command | Files Affected | Impact |
|----------|---------|----------------|--------|
| **TIME** | `--category TIME` | ~20 files | High (cache, calculations) |
| **STATUS_CODE** | `--category STATUS_CODE` | ~100 files | High (API responses) |
| **IMAGE** | `--category IMAGE` | ~5 files | Medium (image processing) |
| **ALL** | `--category ALL` | ~150 files | High (comprehensive) |

---

## 💡 Common Commands

### Scan Specific App
```bash
python3 scripts/detect_magic_numbers.py apps/attendance
python3 scripts/detect_magic_numbers.py apps/work_order_management
```

### Migrate by Category
```bash
# Time constants only
python3 scripts/migrate_magic_numbers.py --app apps/attendance --category TIME --apply

# HTTP status codes only  
python3 scripts/migrate_magic_numbers.py --all --category STATUS_CODE --apply

# Image processing
python3 scripts/migrate_magic_numbers.py --app apps/attendance --category IMAGE --apply

# Everything at once (use with caution!)
python3 scripts/migrate_magic_numbers.py --all --category ALL --apply
```

### Test After Migration
```bash
# Quick syntax check
python3 -m py_compile apps/attendance/*.py

# App-specific tests
python -m pytest apps/attendance/tests/ -v

# Full test suite
python -m pytest --cov=apps --tb=short

# Django system checks
python manage.py check
```

---

## 📝 What Gets Changed

### Example 1: Time Calculations

**Before:**
```python
duration_hours = time_diff.total_seconds() / 3600
cache.set(key, value, 60)
```

**After:**
```python
from apps.core.constants import SECONDS_IN_HOUR, SECONDS_IN_MINUTE

duration_hours = time_diff.total_seconds() / SECONDS_IN_HOUR
cache.set(key, value, SECONDS_IN_MINUTE)
```

### Example 2: HTTP Status Codes

**Before:**
```python
return JsonResponse(data, status=200)
return JsonResponse(error, status=404)
```

**After:**
```python
from apps.core.constants import HTTP_200_OK, HTTP_404_NOT_FOUND

return JsonResponse(data, status=HTTP_200_OK)
return JsonResponse(error, status=HTTP_404_NOT_FOUND)
```

### Example 3: Image Processing

**Before:**
```python
img.resize((512, 512))
cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
```

**After:**
```python
from apps.core.constants import IMAGE_MAX_DIMENSION, IMAGE_QUALITY_DEFAULT

img.resize((IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION))
cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_QUALITY_DEFAULT])
```

---

## ⚠️ Important Notes

### What the Script Does
- ✅ Replaces magic numbers with constants
- ✅ Adds necessary imports automatically
- ✅ Preserves original behavior
- ✅ Context-aware (avoids strings/comments)

### What the Script Doesn't Do
- ❌ Modify test files (by design)
- ❌ Modify migration files (by design)
- ❌ Change comments or docstrings
- ❌ Handle complex expressions (needs manual review)

### Limitations
- Only handles simple numeric literals
- May need manual review for:
  - Numbers in complex expressions
  - Business-specific thresholds
  - Calculated values

---

## 🎯 Recommended Execution Order

### Phase 1: Attendance App (Pilot)
```bash
# 1. Time constants
python3 scripts/migrate_magic_numbers.py --app apps/attendance --category TIME --apply

# 2. Image processing
python3 scripts/migrate_magic_numbers.py --app apps/attendance --category IMAGE --apply

# 3. Test
python -m pytest apps/attendance/tests/ -v
```

### Phase 2: HTTP Status Codes (All Apps)
```bash
# Preview scope
python3 scripts/migrate_magic_numbers.py --all --category STATUS_CODE --dry-run

# Apply changes
python3 scripts/migrate_magic_numbers.py --all --category STATUS_CODE --apply

# Test
python -m pytest --cov=apps --tb=short
```

### Phase 3: App-Specific Constants
Create business rule constants manually in each app:
- `apps/attendance/constants.py` - Fraud detection, GPS thresholds
- `apps/work_order_management/constants.py` - SLA hours
- `apps/noc/constants.py` - Telemetry thresholds

---

## 📈 Success Criteria

After migration, verify:

- [ ] ✅ All tests pass
- [ ] ✅ No new syntax errors
- [ ] ✅ No import errors
- [ ] ✅ API behavior unchanged
- [ ] ✅ Constants properly documented
- [ ] ✅ Type hints on all constants
- [ ] ✅ Zero performance regression

---

## 🆘 Troubleshooting

### Import Errors After Migration
```bash
# Check for circular imports
python manage.py check

# Verify constant definitions
PYTHONPATH=. python3 -c "from apps.core.constants import HTTP_200_OK; print(HTTP_200_OK)"
```

### Test Failures
```bash
# Run with verbose output
python -m pytest apps/attendance/tests/ -vv --tb=long

# Check specific test
python -m pytest apps/attendance/tests/test_signals.py::test_hours_calculation -vv
```

### Syntax Errors
```bash
# Check all files in app
python3 -m py_compile apps/attendance/*.py

# Check specific file
python3 -m py_compile apps/attendance/signals.py
```

---

## 📚 Additional Resources

- **Full Plan:** `MAGIC_NUMBERS_EXTRACTION_COMPLETE.md`
- **Deliverables:** `MAGIC_NUMBERS_DELIVERABLES.md`  
- **Constants Reference:** `apps/core/constants/`
- **CLAUDE.md Rules:** `.claude/rules.md` (Rule #11: No magic numbers)

---

## 🎉 Next Steps

1. **Verify setup:**
   ```bash
   PYTHONPATH=. python3 scripts/verify_magic_number_constants.py
   ```

2. **Run pilot migration:**
   ```bash
   python3 scripts/migrate_magic_numbers.py --app apps/attendance --category TIME --apply
   ```

3. **Test thoroughly:**
   ```bash
   python -m pytest apps/attendance/tests/ -v
   ```

4. **Expand to other categories** as confidence builds

---

**Ready to start? Run:**
```bash
PYTHONPATH=. python3 scripts/verify_magic_number_constants.py && \
python3 scripts/detect_magic_numbers.py apps/
```

Good luck! 🚀
