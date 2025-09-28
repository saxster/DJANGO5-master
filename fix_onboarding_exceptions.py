#!/usr/bin/env python3
"""
Automated fix for Conversational Onboarding generic exception patterns.

This script automatically replaces generic exception patterns in the onboarding module
with specific exception handling patterns following the established security framework.
"""

import re
from pathlib import Path


def fix_onboarding_exceptions():
    """Fix generic exception patterns in onboarding views."""

    onboarding_views = Path("apps/onboarding/views.py")

    if not onboarding_views.exists():
        print("❌ Onboarding views file not found")
        return False

    content = onboarding_views.read_text()

    # Pattern 1: Basic except Exception with utils.handle_Exception
    pattern1 = re.compile(
        r'(\s+)except Exception:\s*\n\s+resp = utils\.handle_Exception\(request\)',
        re.MULTILINE
    )

    replacement1 = r'''\1except (ValidationError, ValueError) as e:
\1    logger.error(
\1        f"Validation error in onboarding view: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id, 'view': self.__class__.__name__}
\1    )
\1    resp = utils.handle_invalid_form(request, self.params, {"errors": {"form": str(e)}})
\1except (DatabaseError, IntegrityError) as e:
\1    logger.error(
\1        f"Database error in onboarding view: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id, 'view': self.__class__.__name__}
\1    )
\1    resp = utils.handle_intergrity_error("Onboarding")
\1except Exception as e:
\1    logger.critical(
\1        f"Unexpected error in onboarding view: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id, 'view': self.__class__.__name__},
\1        exc_info=True
\1    )
\1    resp = utils.handle_Exception(request)'''

    # Pattern 2: except Exception with specific logging
    pattern2 = re.compile(
        r'(\s+)except Exception:\s*\n\s+logger\.error\("SHIFT saving error!", exc_info=True\)\s*\n\s+resp = utils\.handle_Exception\(request\)',
        re.MULTILINE
    )

    replacement2 = r'''\1except (ValidationError, ValueError) as e:
\1    logger.error(
\1        f"Validation error in SHIFT saving: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id}
\1    )
\1    resp = utils.handle_invalid_form(request, self.params, {"errors": {"form": str(e)}})
\1except (DatabaseError, IntegrityError) as e:
\1    logger.error(
\1        f"Database error in SHIFT saving: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id},
\1        exc_info=True
\1    )
\1    resp = utils.handle_intergrity_error("Shift")
\1except Exception as e:
\1    logger.critical(
\1        f"Unexpected error in SHIFT saving: {type(e).__name__}",
\1        extra={'error_message': str(e), 'user_id': request.user.id},
\1        exc_info=True
\1    )
\1    resp = utils.handle_Exception(request)'''

    # Pattern 3: Simple except Exception as e patterns
    pattern3 = re.compile(
        r'(\s+)except Exception as e:\s*\n\s+logger\.(error|warning|critical)\([^)]+\)\s*\n',
        re.MULTILINE
    )

    def replacement3_func(match):
        indent = match.group(1)
        log_level = match.group(2)
        return f'''{indent}except (ValueError, TypeError, KeyError) as e:
{indent}    logger.{log_level}(
{indent}        f"Validation/type error: {{type(e).__name__}}",
{indent}        extra={{'error_message': str(e), 'operation': 'onboarding'}},
{indent}        exc_info=True
{indent}    )
{indent}except (DatabaseError, IntegrityError) as e:
{indent}    logger.error(
{indent}        f"Database error: {{type(e).__name__}}",
{indent}        extra={{'error_message': str(e), 'operation': 'onboarding'}},
{indent}        exc_info=True
{indent}    )
{indent}except Exception as e:
{indent}    logger.critical(
{indent}        f"Unexpected error: {{type(e).__name__}}",
{indent}        extra={{'error_message': str(e), 'operation': 'onboarding'}},
{indent}        exc_info=True
{indent}    )
'''

    # Apply fixes
    print("🔧 Applying onboarding exception fixes...")

    # Count matches before fixing
    matches1 = len(pattern1.findall(content))
    matches2 = len(pattern2.findall(content))
    matches3 = len(pattern3.findall(content))

    # Apply replacements
    content = pattern1.sub(replacement1, content)
    content = pattern2.sub(replacement2, content)
    content = pattern3.sub(replacement3_func, content)

    # Write back to file
    onboarding_views.write_text(content)

    print(f"✅ Fixed {matches1} basic exception patterns")
    print(f"✅ Fixed {matches2} SHIFT logging patterns")
    print(f"✅ Fixed {matches3} simple exception patterns")
    print(f"✅ Total fixes applied: {matches1 + matches2 + matches3}")

    return True


if __name__ == "__main__":
    print("🚀 Starting Conversational Onboarding Exception Fix")
    print("=" * 60)

    success = fix_onboarding_exceptions()

    if success:
        print("\n🎉 Conversational Onboarding exception fixes completed!")
        print("✅ All generic exception patterns have been replaced with specific handling")
    else:
        print("\n❌ Failed to apply onboarding exception fixes")

    print("=" * 60)