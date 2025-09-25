# Circular Import Fix Summary

## Problem
After converting PostgreSQL functions to Django ORM, we encountered circular import errors when starting the Django server.

## Root Cause
The circular import chain was:
```
onboarding.models → onboarding.managers → core.utils → core.utils_new.db_utils → 
activity.models.asset_model → activity.managers.asset_manager → activity.managers.job_manager_orm → 
core.queries → onboarding.models
```

## Solution Applied

### 1. Moved Model Imports Inside Methods
- In `apps/core/queries.py`: Removed all model imports from the top of the file and moved them inside individual methods
- In `apps/onboarding/bt_manager_orm.py`: Moved model imports inside methods
- In `apps/onboarding/managers.py`: Import `BtManagerORM` inside methods instead of at module level

### 2. Fixed Syntax Error
- In `apps/activity/managers/job_manager_orm.py`: Fixed a syntax error where `< /dev/null |` was accidentally inserted in a Q filter

### 3. Removed Unnecessary Import
- In `apps/activity/managers/asset_manager.py`: Removed the import of `JobneedManagerORM` as it wasn't being used

## Files Modified

1. **apps/core/queries.py**
   - Moved all model imports inside methods to avoid circular dependencies
   - Models affected: Bt, TypeAssist, Capability, Jobneed, JobneedDetails, Asset, AssetLog, Attachment, Ticket, EscalationMatrix, People, PeopleEventlog

2. **apps/onboarding/bt_manager_orm.py**
   - Moved imports of Bt, TypeAssist, People, Pgbelonging inside methods

3. **apps/onboarding/managers.py**
   - Import BtManagerORM inside each method that uses it instead of at module level

4. **apps/activity/managers/job_manager_orm.py**
   - Fixed syntax error in get_jobneedmodifiedafter method

5. **apps/activity/managers/asset_manager.py**
   - Removed unused import of JobneedManagerORM

## Benefits

1. **No Circular Imports**: The application now starts without import errors
2. **Lazy Loading**: Models are only imported when actually needed
3. **Better Performance**: Methods that don't use certain models won't trigger their import
4. **Maintainability**: Clear separation of concerns with imports close to usage

## Testing

After the fixes:
- All imports work correctly
- No circular import errors
- Django server starts successfully
- ORM implementations are ready to use

## Best Practices Going Forward

1. When creating utility modules that might be imported by models, avoid importing models at the module level
2. Use local imports inside methods when there's a risk of circular dependencies
3. Keep manager implementations separate from model definitions
4. Consider using Django's `apps.get_model()` for dynamic model loading if needed