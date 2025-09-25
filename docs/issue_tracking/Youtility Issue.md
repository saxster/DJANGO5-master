# Youtility Issue Tracker

## Conditional Question Logic Implementation

### Issue Description
Implemented conditional question logic system for mobile applications where questions can be shown/hidden based on previous answers.

**Requirements:**
- Questions in a questionset should only appear when specific conditions are met
- Mobile apps need structured dependency data to evaluate conditions client-side
- Web interface needed for easy configuration of dependencies
- Example: Questions 2-4 only show when Question 1 is answered "Yes"

### Technical Implementation

#### 1. Database Schema Changes
**File:** `apps/activity/models/question_model.py`

Added `display_conditions` JSON field to QuestionSetBelonging model:
```python
display_conditions = models.JSONField(
    _("Display Conditions"),
    encoder=DjangoJSONEncoder,
    null=True,
    blank=True,
    default=dict,
    help_text="JSON structure for conditional display logic"
)
```

**JSON Structure:**
```json
{
    "depends_on": {
        "question_id": 2,
        "operator": "EQUALS",
        "values": ["Yes"]
    },
    "show_if": true,
    "cascade_hide": false,
    "group": null
}
```

#### 2. Backend API Enhancements
**File:** `apps/activity/managers/question_manager.py`

- Added `get_questions_with_logic()` method for mobile API consumption
- Enhanced `handle_questionpostdata()` to process display_conditions
- Added HTML entity decoding for proper JSON parsing

**Key Fix:** HTML Entity Encoding Resolution
```python
# Decode HTML entities first, then parse JSON
decoded_json = html.unescape(R["display_conditions"])
display_conditions = json.loads(decoded_json)
```

#### 3. Web Interface Implementation
**Files:** 
- `frontend/static/assets/js/local/custom.js`
- `frontend/templates/activity/questionset_form.html`

**Features Added:**
- Dependency dropdown fields in question editor
- Dynamic population of parent questions
- Real-time value field updates based on parent question selection
- Enhanced table display showing dependency relationships
- Automatic table refresh after form submission

**JavaScript Functions:**
- `initializeDependencyFields()` - Populates dependency dropdowns
- `editorFieldsConfig()` - Adds depends_on and depends_on_value fields
- `editorAjaxData()` - Constructs display_conditions JSON for submission

#### 4. API Endpoints
**File:** `apps/activity/views/question_views.py`

Added API endpoints:
- `get_qsb_options` - Fetch parent question options and values
- Enhanced question data responses to include display_conditions

### Issues Resolved

#### Issue 1: JavaScript Selector Error
**Problem:** DataTables couldn't handle numeric IDs as CSS selectors
**Solution:** Changed from `table.row('#' + rowData)` to `table.rows({ selected: true })` approach

#### Issue 2: API 500 Error  
**Problem:** Wrong endpoint URL being called
**Solution:** Fixed URL from `/assets/checklists/?action=get_qsb_options` to `/assets/checklists/relationships/`

#### Issue 3: Null Pointer Error
**Problem:** JavaScript trying to access `data.alerton.length` when `data.alerton` was null
**Solution:** Added null safety checks: `data.alerton && data.alerton.length > 0`

#### Issue 4: Missing Action Parameter
**Problem:** DataTables Editor not sending required `action` parameter
**Solution:** Added explicit action determination: `d.action = currentRow && currentRow["pk"] ? "edit" : "create"`

#### Issue 5: HTML Entity Encoding
**Problem:** JSON data being HTML-encoded (`&quot;` instead of `"`) preventing parsing
**Solution:** Added HTML entity decoding before JSON parsing using `html.unescape()`

#### Issue 6: Table Not Refreshing
**Problem:** DataTable not showing updated dependencies after form submission
**Solution:** Added `postSubmit` event handler to force table reload

### Current Status: ✅ RESOLVED

**Working Features:**
- ✅ Conditional logic saved correctly to database
- ✅ Web interface for dependency configuration
- ✅ Mobile API returns structured dependency data
- ✅ Real-time UI updates and validation
- ✅ Proper error handling throughout system

**Test Results:**
```
Question ID 3: Type of work - depends on ID:2 = ['Yes']
Question ID 4: Name of vendors working in the flat - depends on ID:2 = ['Yes'] 
Question ID 5: Number of labours working - depends on ID:2 = ['Yes']
```

### Mobile Integration
Mobile applications can now consume the dependency data:

```json
{
    "questions": [...],
    "dependency_map": {
        "3": {
            "parent_question_id": 2,
            "question_seqno": 2,
            "operator": "EQUALS",
            "values": ["Yes"],
            "show_if": true
        }
    },
    "has_conditional_logic": true
}
```

### Usage Instructions

**For Web Users:**
1. Navigate to QuestionSet assignment page
2. Edit any question
3. Use "Depends On" dropdown to select parent question
4. Use "When Value Is" dropdown to select trigger value
5. Save - dependency is automatically applied

**For Mobile Developers:**
- Call `/assets/checklists/relationships/?action=get_questions_of_qset&qset_id=X`
- Use `dependency_map` to implement client-side show/hide logic
- Evaluate conditions when user answers parent questions

### Future Enhancements
- Support for multiple operators (NOT_EQUALS, CONTAINS, IN, GT, LT)
- Complex conditions with AND/OR logic
- Dependency chains (Question C depends on B, B depends on A)
- Visual dependency tree in web interface
- Bulk dependency operations

---

**Date Resolved:** September 12, 2025
**Resolved By:** Claude Code Assistant
**Status:** ✅ Complete and Production Ready