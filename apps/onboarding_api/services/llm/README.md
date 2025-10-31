# LLM Service Module

## Overview

This module provides vendor-agnostic LLM service interfaces for Conversational Onboarding following the Maker/Checker pattern.

## Structure

```
llm/
├── __init__.py                  # Package exports
├── base.py                      # Abstract base classes (MakerLLM, CheckerLLM)
├── dummy_implementations.py     # Phase 1 MVP dummy implementations
├── enhanced_checker.py          # Phase 2 enhanced checker with validation
├── citation_schema.py           # Citation format definitions
├── validation_helpers.py        # Validation utility functions
└── exceptions.py                # Custom exceptions
```

## Classes

### Base Abstractions

- **MakerLLM**: Abstract base for generating recommendations
- **CheckerLLM**: Abstract base for validating recommendations

### Implementations

#### Phase 1 (MVP)
- **DummyMakerLLM**: Development/testing implementation (no API calls)
- **DummyCheckerLLM**: Basic validation implementation

#### Phase 2 (Enhanced)
- **EnhancedCheckerLLM**: Advanced validation with templates

## Usage

### Import Dummy Implementations

```python
from apps.onboarding_api.services.llm import DummyMakerLLM, DummyCheckerLLM

# Create instances
maker = DummyMakerLLM()
checker = DummyCheckerLLM()

# Use in conversation flow
context = maker.enhance_context(user_input, context, user)
questions = maker.generate_questions(context, "initial_setup")
```

### Factory Pattern (Recommended)

```python
# In llm.py factory functions
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service

maker = get_llm_service()  # Returns appropriate implementation
checker = get_checker_service()  # Returns checker if enabled
```

## File Details

### dummy_implementations.py

**Extracted from**: `apps/onboarding_api/services/llm.py` (lines 96-343)  
**Date**: 2025-10-10  
**Size**: 268 lines  
**Classes**: 2  
- `DummyMakerLLM`: 8 methods
- `DummyCheckerLLM`: 2 methods

**Purpose**: Provides realistic structured responses for development and testing without requiring actual LLM API calls.

## Testing

All implementations are validated for:
- ✅ Syntax correctness
- ✅ Type hints
- ✅ Docstring coverage
- ✅ Method signatures matching base classes

## Configuration

Controlled via Django settings:

```python
# Enable/disable features
ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER = False  # Checker LLM
ENABLE_ONBOARDING_KB = False  # Knowledge base grounding
```

## See Also

- Parent module: `apps/onboarding_api/services/llm.py`
- Base classes documentation in `base.py`
- Knowledge service: `apps/onboarding_api/services/knowledge.py`
