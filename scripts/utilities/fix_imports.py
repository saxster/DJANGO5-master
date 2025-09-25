#!/usr/bin/env python3
"""Quick script to add Jobneed imports to report methods"""

import re

# Read the file
with open('apps/core/queries.py', 'r') as f:
    content = f.read()

# Find all report method definitions that don't already have the import
report_methods = re.findall(r'(@staticmethod\s+)?def \w*report[^(]*\([^)]*\):[^"]*"""[^"]*"""', content, re.DOTALL)

# Pattern to add import after docstring
pattern = r'((@staticmethod\s+)?def (\w*report[^(]*)\([^)]*\):\s*"""\s*[^"]*\s*""")(\s*)((?!from apps\.activity\.models\.job_model import Jobneed))'

# Replacement with import
replacement = r'\1\4from apps.activity.models.job_model import Jobneed\nfrom datetime import datetime\n\n'

# Apply the replacement
new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

# Write back
with open('apps/core/queries.py', 'w') as f:
    f.write(new_content)

print("Added imports to report methods")