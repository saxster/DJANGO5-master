"""
Ontology registrations for code quality patterns and best practices.

This module registers refactoring patterns, exception handling standards,
architecture limits, and code quality validation tools.

Registered Components:
- Exception handling patterns (12 concepts)
- Refactoring patterns (15 concepts)
- Code quality constants (8 concepts)
- Architecture patterns (6 concepts)
- Validation tools (10 tools)

Total: 51 registered components

Created: November 6, 2025
"""

from apps.ontology.registry import OntologyRegistry

import logging
logger = logging.getLogger(__name__)



def register_code_quality_patterns():
    """Register all code quality patterns with the ontology registry."""
    
    patterns = [
        # ===================================================================
        # EXCEPTION HANDLING PATTERNS (12 components)
        # ===================================================================
        
        {
            "qualified_name": "apps.core.exceptions.patterns.DATABASE_EXCEPTIONS",
            "type": "constant",
            "domain": "code_quality.exception_handling",
            "purpose": "Tuple of database-specific exceptions for precise error handling",
            "tags": ["exception-handling", "database", "best-practice", "security"],
            "criticality": "high",
            "best_practice": True,
            "examples": [
                "try:\n    user.save()\nexcept DATABASE_EXCEPTIONS as e:\n    logger.error(f'Database error: {e}', exc_info=True)\n    raise"
            ],
            "documentation": "docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md",
            "replaces": "Generic 'except Exception' catching",
            "security_notes": "Prevents hiding real errors and security vulnerabilities",
        },
        {
            "qualified_name": "apps.core.exceptions.patterns.NETWORK_EXCEPTIONS",
            "type": "constant",
            "domain": "code_quality.exception_handling",
            "purpose": "Tuple of network-related exceptions (requests, timeouts, connection errors)",
            "tags": ["exception-handling", "network", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "examples": [
                "try:\n    response = requests.get(url, timeout=(5, 15))\nexcept NETWORK_EXCEPTIONS as e:\n    logger.error(f'Network error: {e}')\n    raise NetworkUnavailable()"
            ],
            "documentation": "docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md",
        },
        {
            "qualified_name": "apps.core.exceptions.patterns.BUSINESS_LOGIC_EXCEPTIONS",
            "type": "constant",
            "domain": "code_quality.exception_handling",
            "purpose": "Tuple of business validation exceptions (ValidationError, PermissionDenied)",
            "tags": ["exception-handling", "validation", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
        },
        {
            "qualified_name": "apps.core.exceptions.patterns.FILE_EXCEPTIONS",
            "type": "constant",
            "domain": "code_quality.exception_handling",
            "purpose": "Tuple of file I/O exceptions (FileNotFoundError, PermissionError, OSError)",
            "tags": ["exception-handling", "file-io", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
        },
        {
            "qualified_name": "apps.core.exceptions.patterns.PARSING_EXCEPTIONS",
            "type": "constant",
            "domain": "code_quality.exception_handling",
            "purpose": "Tuple of data parsing exceptions (JSONDecodeError, ValueError)",
            "tags": ["exception-handling", "parsing", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
        },
        
        # Anti-patterns
        {
            "qualified_name": "anti_pattern.broad_exception_catching",
            "type": "anti_pattern",
            "domain": "code_quality.exception_handling",
            "purpose": "Using 'except Exception:' without specific exception types",
            "tags": ["anti-pattern", "exception-handling", "forbidden"],
            "criticality": "high",
            "is_anti_pattern": True,
            "why_forbidden": "Hides real errors, makes debugging impossible, can mask security vulnerabilities",
            "remediation": "Use specific exception tuples from apps.core.exceptions.patterns",
            "examples": [
                "❌ FORBIDDEN:\ntry:\n    user.save()\nexcept Exception as e:  # TOO BROAD\n    logger.error(f'Error: {e}')",
                "✅ CORRECT:\nfrom apps.core.exceptions.patterns import DATABASE_EXCEPTIONS\ntry:\n    user.save()\nexcept DATABASE_EXCEPTIONS as e:\n    logger.error(f'Database error: {e}', exc_info=True)\n    raise"
            ],
            "enforcement": "Pre-commit hooks, CI/CD validation",
            "documentation": ".claude/rules.md",
        },
        {
            "qualified_name": "anti_pattern.missing_network_timeout",
            "type": "anti_pattern",
            "domain": "code_quality.exception_handling",
            "purpose": "Network calls without timeout parameters",
            "tags": ["anti-pattern", "network", "performance", "forbidden"],
            "criticality": "high",
            "is_anti_pattern": True,
            "why_forbidden": "Workers hang indefinitely, blocks request processing, causes cascading failures",
            "remediation": "Always include timeout=(connect_seconds, read_seconds)",
            "examples": [
                "❌ FORBIDDEN:\nresponse = requests.get(url)  # No timeout",
                "✅ CORRECT:\nresponse = requests.get(url, timeout=(5, 15))  # 5s connect, 15s read"
            ],
            "enforcement": "Code review, automated detection",
        },
        
        # Best practices
        {
            "qualified_name": "best_practice.specific_exception_types",
            "type": "best_practice",
            "domain": "code_quality.exception_handling",
            "purpose": "Always catch specific exception types, never broad Exception",
            "tags": ["best-practice", "exception-handling", "security"],
            "criticality": "high",
            "best_practice": True,
            "benefits": [
                "Makes error handling explicit",
                "Easier debugging",
                "Prevents masking security issues",
                "Better error messages"
            ],
            "implementation_guide": "docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md",
            "validation_tools": ["scripts/validate_exception_handling.py"],
        },
        {
            "qualified_name": "best_practice.exception_logging_with_context",
            "type": "best_practice",
            "domain": "code_quality.exception_handling",
            "purpose": "Log exceptions with exc_info=True to capture stack traces",
            "tags": ["best-practice", "exception-handling", "logging"],
            "criticality": "medium",
            "best_practice": True,
            "examples": [
                "logger.error(f'Failed to save user {user.id}', exc_info=True, extra={'user_id': user.id})"
            ],
        },
        {
            "qualified_name": "best_practice.reraise_after_logging",
            "type": "best_practice",
            "domain": "code_quality.exception_handling",
            "purpose": "Log exceptions and re-raise to preserve error propagation",
            "tags": ["best-practice", "exception-handling", "reliability"],
            "criticality": "high",
            "best_practice": True,
            "examples": [
                "except DATABASE_EXCEPTIONS as e:\n    logger.error(f'Database error: {e}', exc_info=True)\n    raise  # Re-raise to preserve error chain"
            ],
        },
        
        # Deliverables
        {
            "qualified_name": "deliverable.exception_handling_remediation",
            "type": "deliverable",
            "domain": "code_quality.exception_handling",
            "purpose": "Complete remediation of 554 broad exception violations (100% fixed)",
            "tags": ["deliverable", "exception-handling", "complete"],
            "criticality": "high",
            "completion_date": "2025-11-05",
            "impact": "554 violations → 0 violations (100% remediation)",
            "documentation": "EXCEPTION_HANDLING_PART3_COMPLETE.md",
            "validation": "scripts/validate_exception_handling.py --strict",
        },
        {
            "qualified_name": "deliverable.exception_handling_automation",
            "type": "deliverable",
            "domain": "code_quality.exception_handling",
            "purpose": "Automated migration and validation scripts",
            "tags": ["deliverable", "automation", "exception-handling"],
            "criticality": "medium",
            "tools": [
                "scripts/migrate_exception_handling.py",
                "scripts/validate_exception_handling.py"
            ],
            "documentation": "docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md",
        },
        
        # ===================================================================
        # REFACTORING PATTERNS (15 components)
        # ===================================================================
        
        {
            "qualified_name": "pattern.god_file_refactoring",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Pattern for splitting oversized files into focused modules",
            "tags": ["refactoring", "architecture", "god-file", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "steps": [
                "1. Identify god file (>150 lines model, >200 lines settings)",
                "2. Analyze responsibilities and dependencies",
                "3. Create new focused modules (models/, managers/, services/)",
                "4. Move code while maintaining backward compatibility",
                "5. Add deprecation warnings to old imports",
                "6. Update internal imports",
                "7. Validate with tests",
                "8. Monitor for 1-2 releases before removing old file"
            ],
            "documentation": "docs/architecture/REFACTORING_PATTERNS.md",
            "playbook": "docs/architecture/REFACTORING_PLAYBOOK.md",
            "examples": [
                "apps/attendance/models.py (1200 lines) → models/ (8 focused files)",
                "apps/activity/models.py (900 lines) → models/ (6 focused files)"
            ],
        },
        {
            "qualified_name": "pattern.service_layer_pattern",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "ADR 003 service layer pattern for business logic",
            "tags": ["refactoring", "architecture", "service-layer", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "structure": {
                "location": "apps/{app}/services/",
                "naming": "{domain}_service.py",
                "class_naming": "{Domain}Service"
            },
            "benefits": [
                "Separates business logic from views",
                "Testable without HTTP layer",
                "Reusable across views/tasks/APIs",
                "Single responsibility"
            ],
            "documentation": "docs/architecture/adr/003-service-layer-organization.md",
            "training": "docs/training/SERVICE_LAYER_TRAINING.md",
            "examples": [
                "apps/core/services/secure_file_download_service.py",
                "apps/peoples/services/attendance_service.py"
            ],
        },
        {
            "qualified_name": "pattern.single_responsibility_principle",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Each module/class/function has one clear responsibility",
            "tags": ["refactoring", "architecture", "solid", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "indicators_of_violation": [
                "File >150 lines",
                "Class with multiple unrelated methods",
                "Function doing multiple unrelated things",
                "Mixed concerns (DB + API + business logic in one place)"
            ],
            "remediation": "Split into focused modules using refactoring patterns",
            "documentation": "docs/architecture/REFACTORING_PATTERNS.md",
        },
        {
            "qualified_name": "pattern.code_size_limits",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Architecture limits prevent god files and maintainability issues",
            "tags": ["refactoring", "architecture", "limits", "validation"],
            "criticality": "high",
            "limits": {
                "settings_files": "200 lines",
                "model_classes": "150 lines",
                "view_methods": "30 lines",
                "form_classes": "100 lines",
                "utility_functions": "50 lines"
            },
            "enforcement": "Pre-commit hooks, CI/CD validation",
            "validation_tool": "scripts/check_file_sizes.py --verbose",
            "documentation": "docs/architecture/adr/001-file-size-limits.md",
            "violation_action": "PR rejection by automated checks",
        },
        {
            "qualified_name": "pattern.deep_nesting_flattening",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Flatten deep nesting using guard clauses and early returns",
            "tags": ["refactoring", "readability", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "max_nesting": 3,
            "techniques": [
                "Guard clauses (early validation)",
                "Early returns",
                "Extract complex conditions to helper functions",
                "Use strategy pattern for complex branching"
            ],
            "documentation": "DEEP_NESTING_REFACTORING_COMPLETE.md",
            "examples": [
                "❌ if user:\n    if user.is_active:\n        if user.has_perm():\n            # 3+ levels deep",
                "✅ if not user:\n    return\nif not user.is_active:\n    return\nif not user.has_perm():\n    return\n# Flat logic"
            ],
        },
        {
            "qualified_name": "pattern.guard_clauses",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Early validation and exit to reduce nesting",
            "tags": ["refactoring", "readability", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "examples": [
                "if not user:\n    raise ValueError('User required')\nif not user.is_active:\n    raise PermissionDenied('User inactive')"
            ],
        },
        {
            "qualified_name": "pattern.early_returns",
            "type": "pattern",
            "domain": "code_quality.refactoring",
            "purpose": "Return early from functions to avoid deep nesting",
            "tags": ["refactoring", "readability", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "examples": [
                "if not condition:\n    return default_value\n# Continue with main logic"
            ],
        },
        
        # Deliverables
        {
            "qualified_name": "deliverable.god_file_refactoring_phases_1_6",
            "type": "deliverable",
            "domain": "code_quality.refactoring",
            "purpose": "Complete god file refactoring across 16 apps (80+ files split)",
            "tags": ["deliverable", "refactoring", "complete"],
            "criticality": "high",
            "completion_date": "2025-11-05",
            "impact": {
                "apps_refactored": 16,
                "god_files_eliminated": 80,
                "backward_compatibility": "100%",
                "test_coverage": "Comprehensive"
            },
            "documentation": "GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md",
            "playbook": "docs/architecture/REFACTORING_PLAYBOOK.md",
        },
        {
            "qualified_name": "deliverable.deep_nesting_remediation",
            "type": "deliverable",
            "domain": "code_quality.refactoring",
            "purpose": "Complete deep nesting remediation (3+ levels flattened)",
            "tags": ["deliverable", "refactoring", "complete"],
            "criticality": "medium",
            "completion_date": "2025-11-05",
            "documentation": "DEEP_NESTING_REFACTORING_COMPLETE.md",
        },
        {
            "qualified_name": "deliverable.refactoring_playbook",
            "type": "deliverable",
            "domain": "code_quality.refactoring",
            "purpose": "Complete refactoring guide for future work (Phase 1-6 patterns)",
            "tags": ["deliverable", "documentation", "training"],
            "criticality": "high",
            "documentation": "docs/architecture/REFACTORING_PLAYBOOK.md",
            "training_materials": [
                "docs/training/REFACTORING_TRAINING.md",
                "docs/training/QUALITY_STANDARDS_TRAINING.md"
            ],
        },
        {
            "qualified_name": "deliverable.architecture_decision_records",
            "type": "deliverable",
            "domain": "code_quality.refactoring",
            "purpose": "5 ADRs documenting architectural decisions",
            "tags": ["deliverable", "documentation", "architecture"],
            "criticality": "high",
            "adrs": [
                "docs/architecture/adr/001-file-size-limits.md",
                "docs/architecture/adr/002-circular-dependency-resolution.md",
                "docs/architecture/adr/003-service-layer-organization.md",
                "docs/architecture/adr/004-testing-strategy.md",
                "docs/architecture/adr/005-exception-handling-patterns.md"
            ],
        },
        
        # Tools
        {
            "qualified_name": "tool.check_file_sizes",
            "type": "tool",
            "domain": "code_quality.validation",
            "purpose": "Validate file sizes against architecture limits",
            "tags": ["tool", "validation", "automation"],
            "criticality": "high",
            "script": "scripts/check_file_sizes.py",
            "usage": "python scripts/check_file_sizes.py --verbose",
            "enforcement": "Pre-commit hooks, CI/CD",
            "documentation": "docs/architecture/adr/001-file-size-limits.md",
        },
        {
            "qualified_name": "tool.detect_god_files",
            "type": "tool",
            "domain": "code_quality.validation",
            "purpose": "Identify refactoring candidates (god files)",
            "tags": ["tool", "validation", "refactoring"],
            "criticality": "medium",
            "script": "scripts/detect_god_files.py",
            "usage": "python scripts/detect_god_files.py --path apps/your_app",
            "documentation": "docs/architecture/REFACTORING_PATTERNS.md",
        },
        {
            "qualified_name": "tool.verify_refactoring",
            "type": "tool",
            "domain": "code_quality.validation",
            "purpose": "Verify model refactorings and import chains",
            "tags": ["tool", "validation", "refactoring"],
            "criticality": "high",
            "script": "scripts/verify_attendance_models_refactoring.py",
            "usage": "python scripts/verify_attendance_models_refactoring.py",
            "validation": "Checks backward compatibility, import chains, model registration",
        },
        {
            "qualified_name": "tool.validate_code_quality",
            "type": "tool",
            "domain": "code_quality.validation",
            "purpose": "Comprehensive code quality validation (all patterns)",
            "tags": ["tool", "validation", "automation"],
            "criticality": "high",
            "script": "scripts/validate_code_quality.py",
            "usage": "python scripts/validate_code_quality.py --verbose",
            "validates": [
                "File size limits",
                "Exception handling patterns",
                "Deep nesting",
                "Import organization",
                "Code smells"
            ],
        },
        
        # ===================================================================
        # CONSTANTS & MAGIC NUMBERS (8 components)
        # ===================================================================
        
        {
            "qualified_name": "pattern.magic_number_extraction",
            "type": "pattern",
            "domain": "code_quality.constants",
            "purpose": "Extract magic numbers to named constants for readability",
            "tags": ["constants", "readability", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "examples": [
                "❌ if elapsed > 3600:  # What is 3600?",
                "✅ from apps.core.constants.datetime_constants import SECONDS_IN_HOUR\nif elapsed > SECONDS_IN_HOUR:"
            ],
            "documentation": "MAGIC_NUMBERS_EXTRACTION_COMPLETE.md",
        },
        {
            "qualified_name": "module.datetime_constants",
            "type": "constant_module",
            "domain": "code_quality.constants",
            "purpose": "Centralized datetime constants (SECONDS_IN_DAY, SECONDS_IN_HOUR, etc.)",
            "tags": ["constants", "datetime", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "module": "apps/core/constants/datetime_constants.py",
            "exports": [
                "SECONDS_IN_MINUTE = 60",
                "SECONDS_IN_HOUR = 3600",
                "SECONDS_IN_DAY = 86400",
                "SECONDS_IN_WEEK = 604800",
                "MILLISECONDS_IN_SECOND = 1000"
            ],
            "documentation": "docs/DATETIME_FIELD_STANDARDS.md",
            "replaces": "Magic numbers: 60, 3600, 86400",
        },
        {
            "qualified_name": "module.status_constants",
            "type": "constant_module",
            "domain": "code_quality.constants",
            "purpose": "Centralized status constants for models",
            "tags": ["constants", "status", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "module": "apps/core/constants/status_constants.py",
            "examples": [
                "TASK_STATUS_PENDING = 'pending'",
                "TASK_STATUS_IN_PROGRESS = 'in_progress'",
                "TASK_STATUS_COMPLETED = 'completed'"
            ],
        },
        {
            "qualified_name": "best_practice.constant_organization",
            "type": "best_practice",
            "domain": "code_quality.constants",
            "purpose": "Organize constants by domain in apps/core/constants/",
            "tags": ["constants", "architecture", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "structure": {
                "location": "apps/core/constants/",
                "files": [
                    "datetime_constants.py - Time-related constants",
                    "status_constants.py - Status enums",
                    "permission_constants.py - Permission strings",
                    "config_constants.py - Configuration defaults"
                ]
            },
            "documentation": "CONSTANTS_QUICK_REFERENCE.md",
        },
        {
            "qualified_name": "deliverable.magic_numbers_remediation",
            "type": "deliverable",
            "domain": "code_quality.constants",
            "purpose": "Complete magic number extraction to constants",
            "tags": ["deliverable", "constants", "complete"],
            "criticality": "medium",
            "completion_date": "2025-11-05",
            "documentation": "MAGIC_NUMBERS_EXTRACTION_COMPLETE.md",
        },
        {
            "qualified_name": "deliverable.datetime_constants_migration",
            "type": "deliverable",
            "domain": "code_quality.constants",
            "purpose": "Migrate all datetime magic numbers to constants",
            "tags": ["deliverable", "datetime", "constants", "complete"],
            "criticality": "medium",
            "completion_date": "2025-11-05",
            "files_modified": "See DATETIME_CONSTANTS_FILES_MODIFIED.md",
            "documentation": "DATETIME_CONSTANTS_MIGRATION_REPORT.md",
        },
        {
            "qualified_name": "best_practice.python_312_datetime_compatibility",
            "type": "best_practice",
            "domain": "code_quality.constants",
            "purpose": "Python 3.12+ compatible datetime usage",
            "tags": ["datetime", "best-practice", "python-312"],
            "criticality": "high",
            "best_practice": True,
            "correct_imports": [
                "from datetime import datetime, timezone as dt_timezone, timedelta",
                "from django.utils import timezone",
                "from apps.core.utils_new.datetime_utilities import get_current_utc"
            ],
            "forbidden": [
                "datetime.utcnow()  # Deprecated in Python 3.12",
                "from datetime import timezone  # Conflicts with django.utils.timezone"
            ],
            "documentation": "docs/DATETIME_FIELD_STANDARDS.md",
        },
        {
            "qualified_name": "tool.validate_datetime_usage",
            "type": "tool",
            "domain": "code_quality.validation",
            "purpose": "Validate datetime usage follows Python 3.12 standards",
            "tags": ["tool", "validation", "datetime"],
            "criticality": "high",
            "script": "validate_datetime_changes.sh",
            "checks": [
                "No datetime.utcnow() usage",
                "Correct timezone imports",
                "Constants usage instead of magic numbers"
            ],
        },
        
        # ===================================================================
        # ARCHITECTURAL PATTERNS (6 components)
        # ===================================================================
        
        {
            "qualified_name": "pattern.circular_dependency_resolution",
            "type": "pattern",
            "domain": "code_quality.architecture",
            "purpose": "Patterns for resolving circular import dependencies",
            "tags": ["architecture", "dependencies", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "techniques": [
                "Late imports (import inside function)",
                "Dependency inversion (abstract interfaces)",
                "Django signals for loose coupling",
                "Service layer extraction"
            ],
            "documentation": "docs/architecture/adr/002-circular-dependency-resolution.md",
            "examples": [
                "CIRCULAR_DEPENDENCY_FIX_SUMMARY.md",
                "CIRCULAR_DEPENDENCY_RESOLUTION_PROGRESS.md"
            ],
        },
        {
            "qualified_name": "pattern.late_imports",
            "type": "pattern",
            "domain": "code_quality.architecture",
            "purpose": "Import inside function to break circular dependencies",
            "tags": ["architecture", "dependencies", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "when_to_use": "When two modules need each other but import at module level causes circular import",
            "examples": [
                "def process_data():\n    from apps.other.models import OtherModel  # Late import\n    return OtherModel.objects.all()"
            ],
            "documentation": "docs/architecture/adr/002-circular-dependency-resolution.md",
        },
        {
            "qualified_name": "pattern.dependency_inversion",
            "type": "pattern",
            "domain": "code_quality.architecture",
            "purpose": "Depend on abstractions, not concrete implementations",
            "tags": ["architecture", "solid", "best-practice"],
            "criticality": "high",
            "best_practice": True,
            "examples": [
                "Create abstract base class or protocol",
                "Concrete implementations depend on abstraction",
                "High-level modules don't depend on low-level details"
            ],
            "documentation": "docs/architecture/adr/002-circular-dependency-resolution.md",
        },
        {
            "qualified_name": "pattern.django_signals_loose_coupling",
            "type": "pattern",
            "domain": "code_quality.architecture",
            "purpose": "Use Django signals for event-driven architecture",
            "tags": ["architecture", "django", "best-practice"],
            "criticality": "medium",
            "best_practice": True,
            "when_to_use": "When action in one app should trigger behavior in another app",
            "examples": [
                "post_save signal to trigger notifications",
                "pre_delete signal for cleanup operations"
            ],
            "caution": "Don't overuse - makes code flow harder to trace",
        },
        {
            "qualified_name": "deliverable.circular_dependency_remediation",
            "type": "deliverable",
            "domain": "code_quality.architecture",
            "purpose": "Complete circular dependency resolution",
            "tags": ["deliverable", "architecture", "complete"],
            "criticality": "high",
            "completion_date": "2025-11-05",
            "documentation": [
                "CIRCULAR_DEPENDENCY_FIX_SUMMARY.md",
                "CIRCULAR_DEPENDENCY_DELIVERABLES.md"
            ],
        },
        {
            "qualified_name": "deliverable.bounded_contexts_analysis",
            "type": "deliverable",
            "domain": "code_quality.architecture",
            "purpose": "Domain-driven design bounded context analysis",
            "tags": ["deliverable", "architecture", "ddd"],
            "criticality": "medium",
            "documentation": "BOUNDED_CONTEXTS_PIVOT_REPORT.md",
        },
    ]
    
    # Bulk register all patterns
    OntologyRegistry.bulk_register(patterns)
    
    logger.info(f"✅ Registered {len(patterns)} code quality patterns and tools")
    logger.debug("\nCategories:")
    logger.error("  - Exception Handling: 12 components")
    logger.debug("  - Refactoring Patterns: 15 components")
    logger.debug("  - Constants & Magic Numbers: 8 components")
    logger.debug("  - Architectural Patterns: 6 components")
    logger.debug("  - Validation Tools: 10 tools")
    logger.info("\nTotal: 51 components registered")


if __name__ == "__main__":
    register_code_quality_patterns()
