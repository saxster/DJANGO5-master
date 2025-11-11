#!/usr/bin/env python3
"""Split peoples/forms.py into logical modules."""

import os
from pathlib import Path

# Read original file
original_file = Path("apps/peoples/forms.py")
with open(original_file, 'r') as f:
    content = f.read()

# Common imports for all form files
common_imports = """from django import forms
from django.conf import settings
from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse
import logging
import zlib
import binascii

import apps.peoples.models as pm  # people-models
from apps.activity.models.location_model import Location
from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from django_select2 import forms as s2forms
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)
import re
from apps.peoples.utils import create_caps_choices_for_peopleform

from apps.core.utils_new.code_validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
    NAME_VALIDATOR,
    validate_peoplecode,
    validate_loginid,
    validate_mobile_number,
    validate_name,
)

# Security form utilities
from apps.core.validation import SecureFormMixin, SecureCharField
"""

# Split points (line numbers based on class definitions)
splits = {
    'authentication_forms.py': (1, 123),  # LoginForm
    'user_forms.py': (124, 329),  # PeopleForm
    'group_forms.py': (330, 481),  # PgroupForm, SiteGroupForm, PeopleGroupForm, PgbelongingForm, CapabilityForm
    'extras_forms.py': (482, 703),  # PeopleExtrasForm, NoSiteForm
}

# Create forms directory
forms_dir = Path("apps/peoples/forms")
forms_dir.mkdir(exist_ok=True)

# Split content into lines
lines = content.split('\n')

# Extract each section
for filename, (start, end) in splits.items():
    # Extract the section (lines are 1-indexed)
    section_lines = lines[start-1:end]
    section_content = '\n'.join(section_lines)
    
    # Remove original imports if present
    if section_content.startswith('from django'):
        # Find where the imports end
        import_end = 0
        for i, line in enumerate(section_lines):
            if line.strip() and not (line.startswith('from ') or line.startswith('import ') or line.startswith('#')):
                import_end = i
                break
        section_content = '\n'.join(section_lines[import_end:])
    
    # Write to new file
    output_file = forms_dir / filename
    with open(output_file, 'w') as f:
        f.write(common_imports)
        f.write('\n\n')
        f.write(section_content.lstrip())
    
    print(f"Created {output_file} ({len(section_lines)} lines)")

# Create __init__.py
init_content = '''"""
Peoples forms module - split for maintainability.

Exports all forms for backward compatibility.
"""

from .authentication_forms import LoginForm
from .user_forms import PeopleForm
from .group_forms import (
    PgroupForm,
    SiteGroupForm,
    PeopleGroupForm,
    PgbelongingForm,
    CapabilityForm,
)
from .extras_forms import PeopleExtrasForm, NoSiteForm

__all__ = [
    'LoginForm',
    'PeopleForm',
    'PgroupForm',
    'SiteGroupForm',
    'PeopleGroupForm',
    'PgbelongingForm',
    'CapabilityForm',
    'PeopleExtrasForm',
    'NoSiteForm',
]
'''

with open(forms_dir / '__init__.py', 'w') as f:
    f.write(init_content)

print(f"Created {forms_dir / '__init__.py'}")

# Rename original file as backup
backup_file = Path("apps/peoples/forms.py.backup")
original_file.rename(backup_file)
print(f"Backed up original to {backup_file}")

print("\n✅ Split complete! All forms now accessible via apps.peoples.forms")
