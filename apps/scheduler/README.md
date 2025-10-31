# Scheduler App

## ⚠️ Important Note about App Name

This app was previously misnamed due to legacy reasons. It is now correctly named `scheduler`. Renaming required coordinated changes across the codebase, including:

- Updating all URL patterns and references
- Modifying import statements across the codebase
- Potentially affecting database table names (if models are added)
- Updating deployment scripts and configurations
- Testing all functionality to ensure nothing breaks

## App Purpose

This Django app handles scheduling functionality for the YOUTILITY5 application, including:

- Internal tour scheduling
- External tour scheduling
- Task scheduling
- Schedule management and preview generation

## Architecture

### Current Structure
- **No Models**: This is a views-only app with no database models
- **Large Views File**: `views.py` (2300+ lines) - contains all view logic
- **Service Layer**: `services.py` - business logic extracted from views (new)
- **Utilities**: `utils.py` and `utils_new.py` - helper functions
- **Forms**: `forms.py` - form definitions

### Key Components

1. **Tour Management**
   - `Schd_I_TourFormJob` - Internal tour creation
   - `Schd_E_TourFormJob` - External tour creation
   - Tour update and retrieval views

2. **Task Management**
   - `SchdTaskFormJob` - Task creation and management
   - Task listing and updates

3. **Schedule Preview**
   - Cron expression validation
   - Schedule date generation

## Business Logic

Business logic has been extracted into service classes:

- `TourJobService` - Tour-related operations
- `TaskJobService` - Task-related operations
- `ScheduleService` - Schedule generation and validation

## Constants

Job-related constants are defined in `services.py` under `JobConstants` class. These should eventually be moved to a dedicated constants module.

## Future Improvements

1. **Break Down Views**: The 2300-line `views.py` should be split into logical modules
2. **Add Models**: Consider if any data should be modeled rather than handled in other apps
3. **Constants Module**: Move constants to `apps/core/constants.py`
4. **Error Handling**: Standardize exception handling using `apps.core.utils_new.error_handling`

## Dependencies

- `apps.activity` - Job and question models
- `apps.peoples` - User utilities and models
- `apps.core` - Core utilities and database helpers
- `croniter` - Cron expression parsing
